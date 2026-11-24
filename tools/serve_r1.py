"""
 * 文件名：serve_r1.py
 * 作用：网页版 AI 助手的服务端 —— 对话接口、会话管理、教材与题库检索（RAG）、token 统计
 * 依赖：Python 3.8+ 标准库；本地 llama-server（默认 http://127.0.0.1:8080）
 * 作者：qiqiwang07
 * 更新：2026-11-07
 *
 * 数据流：
 *     浏览器  ──SSE──►  本服务  ──HTTP──►  llama-server（GGUF 模型）
 *                          │
 *                          └─►  sessions/*.json（会话落盘）
 *
 * 用法：
 *     python serve_r1.py [--port 8091] [--bind 0.0.0.0] [--llama http://127.0.0.1:8080] [--max-new 800]
"""
import argparse  # 解析命令行参数，端口和后端地址都可配置
import json  # 读写 JSON（请求体、响应体、会话文件）
import os  # 路径拼接、目录创建、文件存在性检查
import re  # 正则清洗回答里的出处措辞
import subprocess  # 调用自研的 nanogpt 可执行文件
import codecs  # 增量解码：C 模型逐字节输出，需要拼成完整 UTF-8 字符
import threading  # 线程锁，保护 sessions 字典的并发写
import time  # 计时（统计生成耗时）与生成会话 ID
import urllib.parse  # 联网搜索时给关键词做 URL 编码
import urllib.request  # 向 llama-server 发 HTTP 请求（标准库，无需第三方依赖）
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # 内置 HTTP 服务，线程模型支持并发
from urllib.parse import urlparse, parse_qs  # 解析 URL 路径与查询参数

HERE = os.path.dirname(os.path.abspath(__file__))  # 本文件所在目录，兼容 Windows 与 Linux 两种路径分隔符
BIN_DIR = HERE  # 静态文件（chat.html）与脚本同目录，方便整体拷贝部署
SESS_DIR = os.path.join(HERE, "sessions")  # 会话记录
THINK_DIR = os.path.join(HERE, "thinking")  # 思考过程落盘目录  # 会话记录目录，放在脚本同级，避免依赖外部绝对路径
CORPUS = os.path.join(HERE, "corpus.txt")  # 教材语料文件，缺失时检索自动降级为不用教材
OLYMPIAD = os.path.join(HERE, "olympiad_index.json")  # 奥数题库索引，含题目与标准解答

LLAMA = "http://127.0.0.1:8080/v1/chat/completions"  # 简单模式：小模型，快
LLAMA_THINK = "http://127.0.0.1:8081/v1/chat/completions"  # 思考模式：推理模型，慢但会分析
BACKEND = "llama"  # 后端类型：llama（外部模型）或 nanogpt（自研 C 模型）
NP_BIN = os.path.join(HERE, "nanogpt")  # 自研模型可执行文件路径
NP_CORPUS = os.path.join(HERE, "corpus_self.txt")  # 自研模型专用语料：必须与训练时一致，否则字符表对不上
NP_WEIGHTS = os.path.join(HERE, "selfmade.bin")  # 自研模型权重
NP_LEN = 260  # 自研模型单次生成多少个字符
MAX_NEW = 800  # 默认单次最多生成多少 token，可通过 --max-new 覆盖

sessions = {}  # 内存中的会话表：{会话ID: {"title": 标题, "messages": [{"role","content"}]}}
chunks = []  # 教材切块后的文本片段，供检索使用
chunk_grams = []  # 与 chunks 一一对应的字符二元组集合，预先算好避免每次查询重复计算
gram_df = {}  # 每个二元组出现在多少个片段里（文档频率），用于算 IDF 权重
gram_idf = {}  # 预先算好的逆文档频率：越罕见的词权重越高
olympiad = []  # 奥数题库：[{"q": 题目, "a": 标准解答, "_g": 题干二元组集合}]
lock = threading.Lock()  # 保护 sessions 的并发访问，HTTP 服务是多线程的


def _grams(s: str) -> set:
    """把字符串切成字符二元组集合，用于相似度计算。

    为什么用二元组而不是分词：中文没有空格，按字切二元组不依赖词典，
    对数学符号（$、\\、^）也天然兼容。
    """
    s = "".join(ch for ch in s if not ch.isspace())  # 先去掉所有空白，避免换行影响二元组
    return {s[i:i + 2] for i in range(len(s) - 1)}  # 用集合去重，只关心"出现过"而非频次


def load_olympiad(path: str) -> None:
    """加载奥数题库索引，并把题干的二元组预先算好。"""
    global olympiad  # 需要改写模块级变量
    if not os.path.exists(path):  # 文件不存在就跳过，不影响基础问答
        print("未找到奥数题库:", path, flush=True)  # flush 保证日志立刻可见，便于排查启动问题
        return  # 直接返回，olympiad 保持为空列表
    try:  # 读取可能因文件损坏失败，用 try 保护启动流程
        data = json.load(open(path, encoding="utf-8"))  # 一次性读入，题库只有几 MB
    except Exception as e:  # 捕获所有异常并打印原因
        print("奥数题库读取失败:", e, flush=True)  # 明确告知失败原因
        return  # 失败则降级为无题库模式
    for it in data:  # 逐条预处理
        it["_g"] = _grams(it.get("q", ""))  # 预先计算题干二元组，检索时直接用
    olympiad = data  # 替换模块级引用
    print("奥数题库: %d 道（含标准解答）" % len(olympiad), flush=True)  # 启动日志，确认题库已加载


def retrieve_olympiad(query: str, k: int = 2, min_score: float = 0.12):
    """按题干字符二元组重合度找相似题，返回 [(相似度, 题, 解答)]。

    为什么只在题干上做匹配：解答里全是公式和步骤，匹配解答会引入噪声，
    题干才是"题型"的最佳代表。
    """
    if not olympiad:  # 题库为空直接返回空结果，避免无谓计算
        return []  # 空列表表示没有可用参考
    qg = _grams(query)  # 把用户问题也切成二元组
    if not qg:  # 问题太短（少于 2 个字符）时无法匹配
        return []  # 返回空
    scored = []  # 收集 (分数, 题目对象)
    for it in olympiad:  # 遍历全部题目，题库只有 2000 多道，暴力比对可接受
        dg = it.get("_g") or set()  # 取出预计算的题干二元组
        if not dg:  # 题干为空则跳过，避免除零
            continue  # 进入下一条
        inter = len(qg & dg)  # 交集大小即共同出现的二元组数量
        if inter < 8:  # 重合太少说明毫无关系，提前剪枝省算力
            continue  # 跳过
        score = inter / ((len(qg) ** 0.5) * (len(dg) ** 0.5))  # 余弦式归一化，避免长题干占优
        if score >= min_score:  # 低于阈值视为不相关，宁缺毋滥
            scored.append((score, it))  # 记录候选
    scored.sort(key=lambda x: -x[0])  # 按分数从高到低排序
    return [(s, it["q"], it["a"]) for s, it in scored[:k]]  # 只取前 k 条，控制提示词长度


def build_index(path: str, size: int = 400, overlap: int = 60) -> None:
    """把教材切成固定长度的片段并预计算二元组。

    片段长度 400 是权衡结果：太大导致提示词过长、预填充变慢；
    太小则信息不完整，模型看不到上下文。
    overlap 60 是为了避免答案正好被切在边界处。
    """
    global chunks, chunk_grams  # 改写模块级变量
    if not os.path.exists(path):  # 语料缺失时只告警，不影响其他功能
        print("未找到教材语料:", path, flush=True)  # 提示路径，便于排查部署问题
        return  # 返回，chunks 保持为空
    text = open(path, encoding="utf-8", errors="ignore").read()  # 忽略个别坏字节，保证能读进来
    t0 = time.time()  # 记录建索引耗时
    raw, step = [], size - overlap  # raw 收集片段；step 是滑动步长
    for i in range(0, max(1, len(text) - size // 2), step):  # 按步长滑动切块
        c = text[i:i + size].strip()  # 取出一个片段并去掉首尾空白
        if len(c) >= 200:  # 太短的片段（书页页眉、目录项）没有信息量，丢弃
            raw.append(c)  # 收下这个片段
    chunk_grams = [_grams(c) for c in raw]  # 一次性算完所有片段的二元组
    chunks = raw  # 替换模块级引用
    # 统计文档频率：一个二元组出现在越多片段里，说明它越普通（如"的作""作者"），检索时应该降权
    global gram_df, gram_idf
    gram_df = {}
    for gs in chunk_grams:  # 遍历每个片段
        for g in gs:  # 逐个二元组
            gram_df[g] = gram_df.get(g, 0) + 1  # 计数
    n = max(1, len(chunks))  # 片段总数
    gram_idf = {g: __import__("math").log(1.0 + n / df) for g, df in gram_df.items()}  # IDF = ln(1 + N/df)
    print(f"教材索引: {len(chunks)} 段，{len(text)/1e6:.1f} M 字符，用时 {time.time()-t0:.1f}s", flush=True)  # 启动日志


def retrieve(query: str, k: int = 4) -> list:
    """从教材片段里找与问题最相关的几段，返回文本列表。

    与题库检索的区别：这里只要片段文本（当背景材料），不需要成对的问答。
    """
    if not chunks:  # 没建索引就直接返回
        return []  # 空列表
    qg = _grams(query)  # 问题切二元组
    if not qg:  # 问题太短
        return []  # 无结果
    scored = []  # 收集 (分数, 片段下标)
    for i, dg in enumerate(chunk_grams):  # 遍历所有片段
        if not dg:  # 空片段跳过
            continue  # 下一条
        common = qg & dg  # 共同出现的二元组
        if len(common) < 2:  # 少于 2 个共同二元组基本是巧合，直接跳过
            continue  # 下一条
        # IDF 加权求和：命中"静夜""夜思"这类稀有词得分高，命中"作者""是什么"这类常见词得分低
        s = 0.0
        for g in common:
            s += gram_idf.get(g, 1.0)  # 没见过的词给默认权重 1
        scored.append((s / (len(dg) ** 0.25), i))  # 只做很弱的长度归一化，长片段仍可胜出
    scored.sort(reverse=True)  # 分数高的在前
    return [chunks[i] for _, i in scored[:k]]  # 返回片段文本


def strip_thinking(text: str) -> str:
    """剥离推理模型的思考过程，只保留最终答案。

    DeepSeek-R1 这类模型会先输出  thinking... 再给答案，
    直接展示会让用户看到大段自我独白。
    """
    for marker in ("</think>", "<｜end▁of▁thinking｜>"):  # 两种常见的思考结束标记
        if marker in text:  # 找到标记
            text = text.rsplit(marker, 1)[1]  # 取最后一个标记之后的内容
    return text.strip()  # 去掉首尾空白


def strip_refs(text: str) -> str:
    """去掉回答里的出处措辞（"根据资料1"、"教材中提到"等）。

    为什么要洗：检索内容塞进提示词后，模型很容易复述"资料里说"，
    用户会觉得像在念稿子，不像自然对话。
    """
    if not text:  # 空文本直接返回，避免无谓的正则处理
        return text  # 原样返回
    pats = [  # 逐个匹配常见的出处句式
        r"根据\s*资料\s*\d+[，,、：:]*",  # 根据资料1
        r"参考\s*资料\s*\d+[，,、：:]*",  # 参考资料2
        r"资料\s*\d+\s*[中里]?(提到|指出|表明|说明)[，,：:]?",  # 资料1中提到
        r"根据\s*(教材|课本|原书|书中)[，,：:]?",  # 根据教材
        r"教材\s*[中里](提到|指出|表明|说明)[，,：:]?",  # 教材中指出
        r"《[^》]{2,20}》\s*[中里]?(提到|指出|表明|说明)?[，,：:]?",  # 《线性代数不难》中提到
        r"(第\s*\d+(\.\d+)*\s*[章节])\s*(提到|指出|表明|说明)?[，,：:]?",  # 第3章指出
    ]
    out = text  # 在副本上操作，避免改到调用方数据
    for p in pats:  # 依次替换为空串
        out = re.sub(p, "", out)  # 删除匹配到的出处措辞
    out = re.sub(r"^(嗯|哦|啊|好的|好吧|行|我来想想|让我想想|首先)[，,。；;、\s]*", "", out)  # 去掉开场废话
    return re.sub(r"\n{3,}", "\n\n", out).strip()  # 压缩多余空行并去首尾空白


def stream_llama(messages, usage_out: dict, max_tokens=None, url=None, temperature=0.7):
    """向 llama-server 请求流式输出，同时转发"思考"与"回答"。

    url 为空时用默认（简单模式）模型；思考模式传 8081 的地址。

    为什么连思考也要推给前端：
        nginx 默认 60 秒读超时。推理模型思考时如果前端收不到任何字节，
        连接会被掐断（实测表现为 60.1 秒后返回空）。转发思考既保活，
        也让用户看到模型在想什么。
    """
    body = {                                       # OpenAI 兼容请求体
        "messages": messages,
        "max_tokens": int(max_tokens or MAX_NEW),
        "temperature": temperature,          # 事实题用低温度，减少编造 
        "top_p": 0.9,
        "repeat_penalty": 1.05,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    target = url or LLAMA                              # 简单模式用默认地址，思考模式用 8081
    req = urllib.request.Request(target, data=data, headers={"Content-Type": "application/json"})
    t0 = time.time()
    think, answer = [], []                          # 分别收集思考与正文
    sent_think = sent_ans = False                   # 两个区段的标题是否已发
    with urllib.request.urlopen(req, timeout=900) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                j = json.loads(payload)
            except Exception:
                continue
            u = j.get("usage")
            if u:                                   # 用量信息
                usage_out["in"] = int(u.get("prompt_tokens") or 0)
                usage_out["out"] = int(u.get("completion_tokens") or 0)
            ch = j.get("choices") or [{}]
            delta = ch[0].get("delta") or {}
            rc = delta.get("reasoning_content") or ""   # 思考增量
            ct = delta.get("content") or ""             # 正文增量
            if rc:
                if not sent_think:                  # 首次思考，发标题
                    sent_think = True
                    yield "【思考】\n"
                think.append(rc)
                yield rc                            # 实时转发，保活
            if ct:
                if not sent_ans:                    # 首次正文
                    sent_ans = True
                    if sent_think:                  # 之前有思考，才插一条分隔线；否则直接开始回答
                        yield "\n\n---\n\n"
                answer.append(ct)
                yield ct
    usage_out["think"] = "".join(think)
    usage_out["answer"] = "".join(answer)
    print("[llama] 思考 %d 字 / 回答 %d 字 / %.1fs"
          % (len(usage_out["think"]), len(answer), time.time() - t0), flush=True)


def extract_expr(text: str) -> str:
    """从问题里挑出一个可计算的算式；挑不到返回空串。"""
    best = ""
    for m in re.finditer(r"[0-9][0-9\s.()+\-*/^%]*[0-9]", text):
        cand = m.group(0).strip()
        if not any(op in cand for op in "+-*/^%"):
            continue
        if len(cand) > len(best):
            best = cand
    return best


def run_reason(expr: str) -> str:
    """调用自研 C 推理引擎，返回完整的思考过程文本（失败返回空串）。"""
    try:
        r = subprocess.run([NP_BIN, "reason", expr], capture_output=True, timeout=20,
                           encoding="utf-8", errors="ignore")
        out = (r.stdout or "").strip()
        return out if "【结论】" in out else ""
    except Exception:
        return ""


def run_chain(steps: str):
    """调用 C 引擎验证推理链，返回 (是否全对, 可信答案, 完整输出)。"""
    try:
        r = subprocess.run([NP_BIN, "chain", steps], capture_output=True, timeout=20,
                           encoding="utf-8", errors="ignore")
        out = (r.stdout or "").strip()
        ok = (r.returncode == 0)
        ans = ""
        for line in out.splitlines():
            if line.startswith("【可信答案】"):
                ans = line.replace("【可信答案】", "").strip()
        return (ok, ans, out)
    except Exception:
        return (False, "", "")


def llama_once(messages, max_tokens=400):
    """非流式调用一次模型，用于需要"先拿到完整文本再处理"的场景。"""
    body = {"messages": messages, "max_tokens": max_tokens, "temperature": 0.2,
            "top_p": 0.9, "repeat_penalty": 1.05}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(LLAMA, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        j = json.loads(r.read().decode("utf-8"))
    msg = j["choices"][0]["message"]
    return ((msg.get("content") or "").strip()
            or (msg.get("reasoning_content") or "").strip())


def stream_nanogpt(prompt: str, usage_out: dict):
    """调用自研 C 模型（raw 模式），把输出逐字符转成文本增量。"""
    cmd = [NP_BIN, "raw", NP_CORPUS, NP_WEIGHTS, prompt, str(NP_LEN)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    dec = codecs.getincrementaldecoder("utf-8")("ignore")
    n_out = 0
    try:
        while True:
            b = proc.stdout.read(1)
            if not b:
                break
            s = dec.decode(b)
            if s:
                n_out += len(s)
                yield s
    finally:
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    usage_out["in"] = len(prompt)
    usage_out["out"] = n_out


def key_terms(text: str) -> list:
    """从问题里抽出实词片段，用于校验检索结果是否真的相关。"""
    s = text
    for w in ('什么是', '什么叫', '是什么', '请问', '解释一下', '简单说明', '一句话',
              '的作者是谁', '的作者', '是谁', '多少', '有哪些', '都有谁',
              # 提问残渣：不剔掉会变成"个什么样"这种假关键词，导致误报"资料里没有"
              '是什么样的人', '是个什么样的人', '是什么样', '是个什么样', '什么样',
              '怎么样', '介绍', '评价', '说说', '是个', '一个人', '个',
              '的', '是', '请', '吗', '呢', '人', '？', '?', '。'):
        s = s.replace(w, ' ')
    out = []
    for seg in s.split():
        seg = seg.strip('《》「」“”"\'()（）')
        if len(seg) >= 2:
            out.append(seg)
    return out


def lookup_answer(text: str) -> str:
    """从知识库挑一段原文回答；必须真含关键词，否则返回空交给模型。"""
    terms = key_terms(text)
    if not terms:
        return ''
    hits = retrieve(text, 3)
    for h in hits:
        pos = -1
        for term in terms:
            pos = h.find(term)
            if pos >= 0:
                break
        if pos < 0:
            continue
        best_para = ''
        for para in h.split('\n'):
            para = para.strip()
            if not para:
                continue
            # 跳过问句和题目（"请证明…""Q7 用Python…"不是答案）
            if '？' in para or '?' in para or para.startswith('请') or para.startswith('Q'):
                continue
            # 跳过教材的过渡句/目录话术：含关键词但什么都没说
            if any(w in para for w in ('本节', '篇幅', '走马观花', '下一页', '目录',
                                       '习题', '练习', '小结', '如前所述',
                                       '见下文', '稍后介绍', '不再赘述')):
                continue
            if len(para) < 20:          # 太短的片段多半是标题或残句
                continue
            for term in terms:
                if term in para and len(para) > len(best_para):
                    best_para = para
                    break
        if best_para:
            if len(best_para) > 400:
                cut = best_para.rfind('。', 0, 400)
                best_para = best_para[:cut + 1] if cut > 80 else best_para[:400]
            return '【知识库检索】\n' + best_para
        # 没有段落通过过滤：宁可放弃，也不返回大段无关原文
        continue
    return ''


def web_query(text: str) -> str:
    """把口语化的问题洗成适合搜索的关键词。

    反例：搜「三国演义里孙权是个什么样的人」会返回 PTA/ACM 完全无关的结果，
          因为搜索引擎把「什么样的人」当成了主题词。
    做法：去掉疑问句式和虚词，只留实体。
    """
    s = text
    for w in ('是个什么样的人', '是什么样的人', '什么样的人', '是个怎么样的人',
              '怎么样了', '怎么样', '是什么', '是谁', '为什么', '介绍一下', '介绍',
              '评价一下', '评价', '说说', '告诉我', '请问', '想问', '一下',
              '的', '吗', '呢', '？', '?', '。', '帮我', '查查', '查一下'):
        s = s.replace(w, ' ')
    parts = [x for x in s.split() if x.strip()]
    q = ' '.join(parts).strip()
    return q[:30] if q else text[:20]


def web_search(query: str, n: int = 4):
    """用必应中文搜索，返回 [(标题, 链接, 摘要)]；失败返回空列表。

    为什么用必应：服务器在国内，Google / DuckDuckGo / 维基都不通，
    实测百度与必应中国可访问，必应的 HTML 结构也更好解析。
    """
    try:
        url = 'https://cn.bing.com/search?q=' + urllib.parse.quote(query) + '&setlang=zh-CN&count=10'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9'})
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode('utf-8', 'ignore')
    except Exception as e:
        print('[web] 搜索失败:', e, flush=True)
        return []
    out = []
    for block in re.findall(r'<li class="b_algo".*?</li>', html, re.S):
        m = re.search(r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not m:
            continue
        link = m.group(1)
        title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        sm = re.search(r'<p[^>]*>(.*?)</p>', block, re.S)
        snippet = re.sub(r'<[^>]+>', '', sm.group(1)).strip() if sm else ''
        snippet = snippet.replace('&ensp;', ' ').replace('&#0183;', '·')
        if title and snippet:
            out.append((title, link, snippet))
        if len(out) >= n:
            break
    return out


def fetch_page(url: str, limit: int = 700) -> str:
    """抓一个网页并抽出正文文本（去掉脚本、样式、标签）。失败返回空串。"""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9'})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read(400000)                      # 最多读 400KB，防止大页面拖死
        html = raw.decode('utf-8', 'ignore')
    except Exception:
        return ''
    # 去掉脚本、样式、注释
    html = re.sub(r'<script[\s\S]*?</script>', ' ', html, flags=re.I)
    html = re.sub(r'<style[\s\S]*?</style>', ' ', html, flags=re.I)
    html = re.sub(r'<!--[\s\S]*?-->', ' ', html)
    # 段落优先：只保留 <p> 里的文字，通常就是正文
    paras = re.findall(r'<p[^>]*>(.*?)</p>', html, re.S)
    text = ' '.join(re.sub(r'<[^>]+>', '', p) for p in paras)
    if len(text) < 80:                                # 没有 <p> 就退回全文本
        text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&nbsp;|&ensp;|&#0183;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:limit]


def web_grounded(query: str, results) -> str:
    """把搜索结果拼成给模型的材料；顺手抓前两条的正文，信息更实。"""
    parts = []
    for i, (title, link, snippet) in enumerate(results, 1):
        body = fetch_page(link) if i <= 2 else ''      # 只抓前两条，控制耗时
        detail = body if len(body) > len(snippet) else snippet
        parts.append('【资料%d】%s\n%s' % (i, title, detail[:600]))
    return ('以下是刚从网上搜到的资料，请据此回答。\n'
            '要求一：结合资料给准确回答；资料没提到的具体事实（数字、年份、人名）不要编造。\n'
            '要求二：如果资料没有直接回答问题的关键部分，第一句必须写'
            '\"资料里没有直接提到……\"，说明缺的是什么，再讲资料里确有的内容。\n\n'
            + '\n\n'.join(parts) + '\n\n用户问题：' + query)


def format_sources(results) -> str:
    """回答末尾附来源列表。"""
    if not results:
        return ''
    lines = ['', '', '---', '**来源**']
    for i, (title, link, _) in enumerate(results, 1):
        lines.append('%d. [%s](%s)' % (i, title[:50], link))
    return '\n'.join(lines)


def faith_check(answer: str, context: str, question: str):
    """检查回答里的事实性内容是否有依据。

    做法：抽出答案里的数字和《》书名，逐个看在材料或问题里有没有。
    返回 (无依据的条目列表)。宁可误报，也不要让编造的数字混过去。
    """
    if not answer:
        return []
    src = (context or "") + (question or "")
    bad = []
    # 数字：日期、年份、数量、百分比
    for num in re.findall(r"\d+(?:\.\d+)?", answer):
        if num not in src and len(num) >= 2:      # 单个数字太常见，跳过
            bad.append(num)
    # 书名号里的名字：人物、作品、机构
    for name in re.findall(r"《([^》]{2,20})》", answer):
        if name not in src:
            bad.append("《%s》" % name)
    # 重合度：答案和材料几乎没有共同词组，说明它在自己发挥
    if context:
        grams = set()
        for i in range(len(context) - 2):
            grams.add(context[i:i + 3])
        hit = sum(1 for i in range(len(answer) - 2) if answer[i:i + 3] in grams)
        total = max(1, len(answer) - 2)
        if total > 40 and hit / total < 0.05:      # 长答案里几乎找不到材料原句
            bad.append("（整体内容与资料重合度很低，可能是模型自行发挥）")

    # 去重并保序
    seen, out = set(), []
    for x in bad:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out[:8]


def missing_disclosure(answer: str, context: str, question: str) -> str:
    """检查是否该声明"资料里没有"，返回要补的话（不需要补则返回空串）。

    判定：问题里的关键词有相当一部分在材料中完全没有出现，
          而回答里又没有出现任何"没提到/没查到"之类的声明。
    """
    if not answer or not context:
        return ""
    said = ("没有直接提到", "没有提到", "没提到", "没有查到", "没查到",
            "资料里没有", "材料里没有", "无法确定", "没有相关内容", "没有涉及")
    if any(k in answer for k in said):
        return ""                                  # 已经声明过，不重复
    terms = key_terms(question)                    # 问题里的实词
    if not terms:
        return ""
    missing = [w for w in terms if w not in context]
    if len(missing) >= max(1, len(terms) // 2):     # 一半以上关键词材料里都没有
        return ("\n\n---\n**说明**：以上回答中，资料里没有直接提到 %s 的相关内容，"
                "这部分属于模型根据常识的补充，请谨慎采信。" % "、".join(missing[:4]))
    return ""


def classify(text: str) -> str:
    """判断题型：calc（纯算式）/ lookup（事实查询）/ think（需要推理或创作）。

    实测依据：
      - 算式题交 C 引擎，毫秒级且绝对准确
      - 事实题直接检索，比 8B 模型思考快 20 倍
      - 生成/推理题必须走模型，否则会拿无关原文糊弄
    """
    s = text.strip()
    cjk = sum(1 for ch in s if '\u4e00' <= ch <= '\u9fff')
    if extract_expr(s) and cjk <= 6:
        return 'calc'

    # 问候语：直接回应，别浪费模型算力，也别让 3B 模型把"你好"当知识题乱编
    greetings = ('你好', '您好', '在吗', 'hi', 'hello', '嗨', '哈喽', '谢谢', '多谢')
    if len(s) <= 12 and any(s.lower().startswith(g) for g in greetings):
        return 'greet'

    think_keys = ('写', '代码', '函数', '程序', '实现', '算法', '编程', '作文', '议论文',
                  '记叙文', '散文', '诗', '为什么', '证明', '推导', '分析', '比较',
                  '评价', '设计', '优化', '如何', '怎样', '步骤', '计算', '求')
    if any(k in s for k in think_keys):
        return 'think'
    # 联网意图：时效性强、必须查外部信息、或明确要求上网查
    web_keys = ('最新', '今天', '现在', '新闻', '最近', '多少钱', '官网', '查一下', '搜一下',
                '上网', '网上', '股价', '天气', '比分', '发布', '几号')
    if any(k in s for k in web_keys):
        return 'web'

    lookup_heads = ('什么是', '什么叫', '是什么', '谁是', '的作者', '的作者是谁',
                    '多少', '几位', '哪一年', '解释一下', '定义',
                    # 人物/作品评价类：这类最容易编，必须先去查资料
                    '什么样', '怎么样', '介绍', '评价', '说说', '是个', '事迹', '生平')
    if any(s.startswith(h) or h in s for h in lookup_heads):
        return 'lookup'
    return 'think'


def save_thinking(sid: str, question: str, think: str, answer: str,
                  usage: dict, sources=None) -> str:
    """把一次问答的完整思考过程写成 markdown，返回文件路径。

    为什么单独落盘：思考过程很有价值（复盘、审计、教学），
    但它太长，不适合塞进会话记录里，所以单独存。
    """
    os.makedirs(THINK_DIR, exist_ok=True)
    ts = time.strftime('%Y%m%d_%H%M%S')
    path = os.path.join(THINK_DIR, '%s_%s.md' % (ts, sid or 'anon'))
    lines = ['# 问题', '', question or '（空）', '']
    if think:
        lines += ['## 思考过程', '', think.strip(), '']
    lines += ['## 回答', '', (answer or '').strip(), '']
    lines += ['---', '',
              '- 时间：%s' % time.strftime('%Y-%m-%d %H:%M:%S'),
              '- 会话：%s' % (sid or '匿名'),
              '- 输入 token：%d' % usage.get('in', 0),
              '- 输出 token：%d' % usage.get('out', 0)]
    if sources:
        lines += ['', '## 来源']
        for i, (title, link, _) in enumerate(sources, 1):
            lines.append('%d. [%s](%s)' % (i, title, link))
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return path


def load_sessions() -> None:
    """启动时把磁盘上的历史会话读回内存，实现重启不丢记录。"""
    os.makedirs(SESS_DIR, exist_ok=True)  # 目录不存在就创建，避免首次启动报错
    for fn in os.listdir(SESS_DIR):  # 遍历会话目录
        if fn.endswith(".json"):  # 只处理 json 文件
            try:  # 单个文件损坏不应阻断整体加载
                with open(os.path.join(SESS_DIR, fn), encoding="utf-8") as f:  # 以 UTF-8 读，保证中文正常
                    sessions[fn[:-5]] = json.load(f)  # 文件名去掉 .json 就是会话 ID
            except Exception:  # 忽略损坏文件
                pass  # 继续加载下一个


def save_session(sid: str) -> None:
    """把指定会话写回磁盘，保证断电或重启后记录还在。"""
    os.makedirs(SESS_DIR, exist_ok=True)  # 确保目录存在
    with open(os.path.join(SESS_DIR, sid + ".json"), "w", encoding="utf-8") as f:  # 覆盖写，内容总是最新
        json.dump(sessions[sid], f, ensure_ascii=False, indent=1)  # 中文不转义，便于人工查看


def new_sid() -> str:
    """生成会话 ID：毫秒时间戳取后 9 位，够短又基本不重复。"""
    return "r%d" % (int(time.time() * 1000) % 10 ** 9)  # 加 r 前缀便于识别是本服务生成的


class Handler(BaseHTTPRequestHandler):
    """HTTP 请求处理器：GET 出页面和会话，POST 处理对话与新建会话。"""

    protocol_version = "HTTP/1.1"  # 用 1.1 才支持 keep-alive，减少连接开销

    def log_message(self, fmt, *args):
        """屏蔽默认的访问日志：每个请求打一行会污染容器日志，改为自己按需打印。"""
        pass  # 故意留空

    def _send(self, body: bytes, ctype: str = "application/json"):
        """统一的普通响应发送（非流式）。"""
        self.send_response(200)  # 固定 200，错误通过 body 里的 error 字段表达
        self.send_header("Content-Type", ctype + "; charset=utf-8")  # 显式声明 UTF-8，避免浏览器乱码
        self.send_header("Content-Length", str(len(body)))  # 必须给长度，否则客户端不知道何时读完
        self.send_header("Cache-Control", "no-store")  # 禁止缓存，否则改了页面用户看不到
        self.end_headers()  # 结束响应头
        self.wfile.write(body)  # 写响应体

    def _serve_file(self, name: str) -> None:
        """分发安装包等大文件，支持 Range 断点续传。

        为什么需要 Range：1 GB 的安装包在移动网络下很容易断，
        支持续传后客户端可以接着下，而不是从头再来。
        """
        base = os.path.join(HERE, "dist")  # 分发目录，软链到 airelay/dist
        p = os.path.join(base, os.path.basename(name))  # basename 去掉路径部分，防止目录穿越
        if not os.path.isfile(p):  # 文件不存在
            self.send_response(404)  # 返回 404
            self.send_header("Content-Length", "0")  # 空响应体
            self.end_headers()  # 结束头部
            return  # 处理完毕
        size = os.path.getsize(p)  # 文件总大小，用于计算 Content-Length 与 Content-Range
        ctype = "application/octet-stream"  # 默认二进制流
        low = name.lower()  # 统一小写便于判断扩展名
        if low.endswith(".ps1") or low.endswith(".txt") or low.endswith(".bat"):  # 文本类
            ctype = "text/plain; charset=utf-8"  # 声明编码，避免下载后中文乱码
        elif low.endswith(".json"):  # JSON 类
            ctype = "application/json; charset=utf-8"  # JSON 的 MIME
        start, end, status = 0, size - 1, 200  # 默认返回整个文件
        rng = self.headers.get("Range")  # 客户端可能带了断点续传请求头
        if rng and rng.startswith("bytes="):  # 形如 bytes=100-200
            try:  # 解析失败就退化为完整下载
                spec = rng[6:].split(",")[0]  # 只支持单区间，多区间退化为首个
                a, _, b = spec.partition("-")  # 拆出起止
                start = int(a) if a.strip() else 0  # 缺省从 0 开始
                end = int(b) if b.strip() else size - 1  # 缺省到文件末尾
                if start >= size:  # 起点越界说明文件被改小了
                    start = 0  # 退回从头开始
                if end >= size or end < start:  # 终点越界或倒序都修正
                    end = size - 1  # 取到末尾
                status = 206  # 206 表示部分内容，客户端据此续传
            except Exception:  # 解析异常
                start, end, status = 0, size - 1, 200  # 回退为完整下载
        length = end - start + 1  # 本次实际发送的字节数
        self.send_response(status)  # 200 或 206
        self.send_header("Content-Type", ctype)  # 内容类型
        self.send_header("Content-Length", str(length))  # 关键：必须是区间长度而非文件长度
        self.send_header("Accept-Ranges", "bytes")  # 告知客户端支持续传
        if status == 206:  # 部分响应必须带 Content-Range
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))  # 起止与总长
        self.send_header("Content-Disposition", 'attachment; filename="%s"' % os.path.basename(p))  # 触发浏览器下载
        self.send_header("X-Accel-Buffering", "no")  # 让 nginx 不缓冲，否则大文件下载会卡住超时
        self.end_headers()  # 结束头部
        try:  # 客户端可能中途断开，避免异常刷屏
            with open(p, "rb") as f:  # 二进制读
                f.seek(start)  # 定位到续传起点
                remain = length  # 还要发多少字节
                while remain > 0:  # 分块发送
                    b = f.read(min(1 << 20, remain))  # 每次最多 1 MB，兼顾内存与效率
                    if not b:  # 读到头了（文件被截断）
                        break  # 结束
                    self.wfile.write(b)  # 写出
                    remain -= len(b)  # 递减剩余量
        except Exception as e:  # 通常是客户端断开
            print("send file error:", e, flush=True)  # 记录但不影响其他请求

    def do_GET(self):
        """处理 GET：首页、健康检查、会话列表、单个会话、文件下载。"""
        u = urlparse(self.path)  # 解析出路径与查询串
        if u.path == "/health":  # 健康检查，供 nginx 和运维探活
            self._send(json.dumps({"ok": True}).encode())  # 返回最小 JSON
        elif u.path.startswith("/dl/"):  # 安装包下载
            self._serve_file(u.path[4:])  # 去掉 "/dl/" 前缀取文件名
        elif u.path in ("/callgraph", "/callgraph.html"):  # 函数调用示意图页面
            p2 = os.path.join(HERE, "callgraph.html")  # 与脚本同目录
            if os.path.isfile(p2):  # 存在才返回
                with open(p2, "rb") as f2:  # 二进制读
                    self._send(f2.read(), "text/html")  # 以 HTML 返回
            else:  # 文件缺失
                self._send(b'{"error":"callgraph.html not found"}')  # 明确报错
        elif u.path in ("/", "/chat.html"):  # 首页与显式页面路径都返回同一份 HTML
            p = os.path.join(BIN_DIR, "chat.html")  # 页面文件位置
            with open(p, "rb") as f:  # 二进制读，避免编码转换
                self._send(f.read(), "text/html")  # 以 HTML 类型返回
        elif u.path == "/thinking":  # 查看思考过程文件
            qs = parse_qs(u.query)
            name = (qs.get("f") or [""])[0]  # 指定文件名就返回内容
            if name:  # 单文件
                fp = os.path.join(THINK_DIR, os.path.basename(name))  # 防目录穿越
                if os.path.isfile(fp):
                    with open(fp, "rb") as f:
                        self._send(f.read(), "text/markdown")
                else:
                    self._send(b'{"error":"not found"}')
            else:  # 列出最近的
                os.makedirs(THINK_DIR, exist_ok=True)
                files = sorted(os.listdir(THINK_DIR), reverse=True)[:50]
                data = [{"name": f, "size": os.path.getsize(os.path.join(THINK_DIR, f))}
                        for f in files if f.endswith(".md")]
                self._send(json.dumps({"files": data}, ensure_ascii=False).encode())
        elif u.path == "/sessions":  # 左侧会话列表
            data = [{"id": k, "title": v.get("title") or "新会话"} for k, v in sessions.items()]  # 只暴露必要字段
            data.sort(key=lambda x: x["id"], reverse=True)  # ID 含时间戳，倒序即最近在前
            self._send(json.dumps({"sessions": data}, ensure_ascii=False).encode())  # 序列化返回
        elif u.path == "/session":  # 取某个会话的完整记录
            sid = (parse_qs(u.query).get("id") or [""])[0]  # 从查询串取 id，缺省为空串
            s = sessions.get(sid)  # 查内存表
            log = ""  # 拼成前端能解析的文本格式
            if s:  # 会话存在才拼
                for m in s["messages"]:  # 逐条消息
                    log += ("### User: " if m["role"] == "user" else "### Assistant: ") + m["content"] + "\n"  # 用固定前缀区分角色
            self._send(json.dumps({"log": log}, ensure_ascii=False).encode())  # 返回拼接结果
        else:  # 未知路径
            self._send(b'{"error":"not found"}')  # 统一错误响应

    def do_POST(self):
        """处理 POST：新建会话、对话（流式）。"""
        u = urlparse(self.path)  # 解析路径
        n = int(self.headers.get("Content-Length") or 0)  # 读取请求体长度
        raw = self.rfile.read(n) if n else b"{}"  # 按长度读请求体，缺省给空 JSON
        try:  # 请求体可能是畸形 JSON
            body = json.loads(raw or b"{}")  # 解析
        except Exception:  # 解析失败
            body = {}  # 退化为空字典，后续按缺省值处理

        if u.path == "/new":  # 新建会话
            sid = new_sid()  # 生成新 ID
            sessions[sid] = {"title": "", "messages": []}  # 初始化空会话
            save_session(sid)  # 立即落盘，保证刷新页面后还在
            self._send(json.dumps({"id": sid}).encode())  # 返回新 ID
        elif u.path == "/chat":  # 核心对话接口
            text = (body.get("text") or "").strip()  # 用户问题，去掉首尾空白
            mode = (body.get("mode") or "simple").strip()  # 模式：simple 简单 / think 思考
            model_url = LLAMA  # 两个模式都用本地 llama 模型（8081 的 DeepSeek 已下线）
            # 思考模式与简单模式的区别在提示词和题库检索，不在模型
            sid = body.get("session") or ""  # 客户端传来的会话 ID
            if sid not in sessions:  # 没带或带了个不存在的 ID
                sid = new_sid()  # 新建一个，避免把消息丢进不存在的会话
                sessions[sid] = {"title": "", "messages": []}  # 初始化
            s = sessions[sid]  # 取出会话对象
            s["messages"].append({"role": "user", "content": text})  # 先记录用户消息
            if not s["title"]:  # 标题只在第一条消息时设置
                s["title"] = text[:20]  # 取前 20 字做标题，够用又不撑破侧边栏
            # 判断是不是写作任务：作文要的是成篇的文字，和"问知识点"完全不同，需要单独处理
            essay_kw = ("作文", "议论文", "记叙文", "说明文", "散文", "写一篇", "写段", "写一封",
                        "帮我写", "演讲稿", "读后感", "观后感")
            is_essay = any(k in text for k in essay_kw)  # 命中任一关键词即视为写作任务
            # 判断是不是编程任务：既要提到代码相关词，又要带动作，避免"什么是算法"这类纯概念问题被误判
            code_topic = ("代码", "函数", "程序", "算法", "脚本", "python", "Python", "c语言", "C语言",
                          "javascript", "JavaScript", "java", "sql", "SQL", "html", "排序", "递归",
                          "指针", "链表", "二叉树", "编译", "数组", "字典", "class", "def")
            code_action = ("写", "实现", "编", "生成", "改", "修", "优化", "调试", "报错", "错误", "不会")
            is_code = (any(k in text for k in code_topic) and any(k in text for k in code_action)) \
                      or any(k in text for k in ("为什么报错", "报错了", "运行不了", "跑不起来", "语法错误"))
            # 思考模式多取几道相似题做参考；简单模式只要 1 道，省预填充
            math_hits = retrieve_olympiad(text, 3 if mode == "think" else 1)
            bank_hit = math_hits[0] if (mode == "think" and math_hits and math_hits[0][0] >= 0.85) else None
            hits = retrieve(text, 1)  # 只取 1 段：片段越多预填充越慢，首字延迟越高
            style_hits = retrieve("好词好句 优美句子 名言警句 开头 结尾 排比 描写", 1) if is_essay else []  # 写作任务额外取一段素材
            route = classify(text) if BACKEND != "nanogpt" else "think"  # 自研模型不做路由


            msgs = list(s["messages"])  # 复制一份对话历史，避免改动原始记录

            if route == 'think' and mode == 'simple' and BACKEND != "nanogpt":
                # 简单模式：小模型，要求直接给结论，控制篇幅
                msgs = [{"role": "system", "content":
                         "你是简洁的中文助手。直接给出答案，控制在 200 字以内，"
                         "不要长篇铺陈，不要复述题目。"}] + msgs
            brief = ("回答要详实自然，像跟朋友解释一样：把内容讲清楚，可以举例。"  # 只提要求不列结构，避免被照抄成小标题
                     "篇幅 300-600 字。"  # 控制篇幅
                     "直接给内容，不要写“先说结论/解释为什么/补充要点”这类格式说明，"  # 明确禁止复述提示词
                     "用 Markdown 排版：分点用 - 列表，重点用 **加粗**，标题用 ###。"  # 让前端能渲染出层次
                     "也不要写“好的/我来想想/首先”，不要复述题目。")  # 禁止开场空话
            if is_essay:  # 写作任务：要求成篇、有结构、有文采
                ref = ("\n\n【可参考的好词好句】\n" + style_hits[0][:300]) if style_hits else ""  # 素材截短，控制预填充
                msgs = s["messages"][:-1] + [{
                    "role": "user",
                    "content": ("请写一篇完整的作文。\n"
                                "要求：\n"
                                "1. 结构完整：开头点题，中间分 3-4 段展开，结尾升华；\n"
                                "2. 内容具体：多用具体事例、细节描写，不要空喊口号；\n"
                                "3. 语言有文采：适当使用成语、排比、比喻，可引用诗词或名言；\n"
                                "4. 篇幅 700-900 字；\n"
                                "5. 直接给正文，不要解释你的写作思路。\n\n"
                                "题目：" + text + ref)}]
                req_max = 2200  # 800 字中文大约要 700-900 token，留足余量防止被截断
            elif is_code:  # 编程任务：要求完整可运行代码 + 简要说明
                ref = ""
                if hits:  # 有编程素材就带上，截短控制预填充
                    ref = "\n\n【可参考的知识点】\n" + hits[0][:300]
                msgs = s["messages"][:-1] + [{
                    "role": "user",
                    "content": ("请完成下面的编程任务。\n"
                                "要求：\n"
                                "1. 给出**完整可运行**的代码，包含必要的 import 和入口；\n"
                                "2. 用 ```语言 代码块包裹；\n"
                                "3. 关键行写中文注释说明为什么这么做；\n"
                                "4. 代码之后用几句话说明思路、复杂度、以及需要注意的边界情况；\n"
                                "5. 如果用户是在问报错，先说明错误原因，再给修正后的完整代码。\n\n"
                                "任务：" + text + ref)}]
                req_max = 1800  # 代码通常比文字长，给足额度
            elif math_hits:  # 是数学题：注入相似题与标准解答
                refs = "\n\n".join(  # 把多道参考题拼成一段
                    "【相似题%d】\n题目：%s\n标准解答：%s" % (i + 1, q, a[:500])  # 解答截到 500 字：只保留思路即可，太长会拖慢预填充
                    for i, (sc, q, a) in enumerate(math_hits))  # 逐条格式化
                if mode == "think":  # 思考模式：要求写出完整推理，不许提参考
                    grounded = ("下面给出几道相似题及其标准解答，仅供你参考解题方法。\n"
                                "要求：\n"
                                "1. 一步一步推理，每一步都写清楚依据（用了什么定理、为什么成立）；\n"
                                "2. 不许跳步，不许只给答案；\n"
                                "3. 如果某一步需要计算，把算式写出来并算出结果；\n"
                                "4. 最后用 \\boxed{} 给出答案；\n"
                                "5. 不要提\"相似题\"\"参考\"\"资料\"这些字眼。\n\n"
                                + refs + "\n\n【需要解答的题目】\n" + text)
                    msgs = s["messages"][:-1] + [{"role": "user", "content": grounded}]
                else:
                    grounded = ("下面给出几道相似题目及其标准解答，请参考它们的解题思路和书写格式，"  # 明确告诉模型参考什么
                            "解答用户提出的新题目。\n"  # 任务说明
                            "要求：写清完整推理步骤（每一步说清楚为什么这么做），"  # 要求步骤完整
                            "最后用 \\boxed{} 给出答案；答完可以补充一句思路小结或易错点提醒。"  # 统一答案格式
                            "不要提及“相似题/参考/资料”这些字眼。\n\n"  # 禁止暴露参考来源
                            + refs + "\n\n【需要解答的题目】\n" + text)  # 拼上真正要答的题目
                    msgs = s["messages"][:-1] + [{"role": "user", "content": grounded}]  # 用注入后的提示替换最后一条用户消息
            elif hits and any(t in hits[0] for t in key_terms(text)):  # 片段必须真含关键词才注入
                # 3B 小模型很容易被无关材料带偏（问"素数"却照着"Lp 范数"往下编），所以加校验
                ctx = "\n\n".join(h[:200] for h in hits)  # 每段截到 200 字，控制预填充耗时
                grounded = ("以下是一些参考材料，请据此回答。不要说明内容来自哪里，"  # 提示模型别说出处
                            "不要提资料、教材或书名。\n"
                            "铁律一：材料里没有的具体事实（数字、年份、人名、书名）一律不许编。\n"
                            "铁律二：如果材料没有直接回答问题的关键部分，回答的第一句必须写明"
                            "\"资料里没有直接提到……\"，说清缺的是哪一点，然后再讲材料里确实有的内容。\n"
                            "不许用模糊说法蒙混（如\"大致\"\"一般来说\"），缺就是缺。\n"
                            + brief + "\n\n" + ctx + "\n\n问题：" + text)  # 材料 + 要求 + 问题
                msgs = s["messages"][:-1] + [{"role": "user", "content": grounded}]  # 同样替换最后一条
            else:  # 检索没命中，或片段不相关：直接回答
                msgs = s["messages"][:-1] + [{"role": "user", "content": text + "\n\n" + brief}]  # 只加回答要求
            ref_count = len(math_hits) + (0 if math_hits else len(hits)) + len(style_hits)  # 统计参考了多少条，前端可展示
            if not is_essay and not is_code:  # 写作与编程分支已自行设过额度，其余按题目类型给
                req_max = max(MAX_NEW, 3000) if math_hits else MAX_NEW  # 数学题解答长，给更大额度
            if route == 'think' and not math_hits and not is_essay and not is_code:
                req_max = min(req_max, 700) if mode == 'simple' else 2200  # 简单模式收窄，思考模式放宽
            self.send_response(200)  # 开始流式响应
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")  # SSE 类型
            self.send_header("Cache-Control", "no-store")  # 流式内容不能缓存
            self.send_header("Connection", "close")  # 明确关闭连接，避免代理层缓冲
            self.end_headers()  # 结束头部，之后都是数据帧
            usage = {}  # 收集 token 统计
            acc = []  # 累积完整回答，用于落盘
            def emit(obj):  # 发送一个 SSE 事件
                """把字典编码成 SSE 帧并立即刷新，保证浏览器实时收到。"""
                self.wfile.write(b"data: " + json.dumps(obj, ensure_ascii=False).encode() + b"\n\n")  # SSE 帧格式固定
                self.wfile.flush()  # 强制刷出，否则会攒在缓冲区
            # ---- 先快速判断题型，再决定要不要让模型思考 ----
            chain_answer = ""                         # 不走模型的直接答案
            web_sources = []                          # 联网来源，回答完附在末尾
            expr = extract_expr(text)                 # 提取算式


            if bank_hit:                              # 题库里有几乎一样的题：直接给标准解答
                sc, q0, a0 = bank_hit                 # 相似度、原题、标准解答
                chain_answer = ("【题库命中】这道题在本地题库里有原题，直接给标准解答（没上网）：\n\n"
                                "**题目**\n%s\n\n**解答**\n%s" % (q0, a0))

            elif route == 'greet':                    # 问候语：直接回应，不调模型
                chain_answer = ('你好！我是这个系统的 AI 助手。\n\n'
                                '我可以：\n'
                                '- 精确计算：直接给算式，我用程序算，不会算错\n'
                                '- 查知识库：数学、文学、编程\n'
                                '- 写作文、写代码、解释概念\n\n'
                                '直接说你想问什么就行。')
            elif route == 'calc' and expr:            # 一级：纯算式，C 引擎毫秒级出结果
                rep = run_reason(expr)                # 分解 + 逐步求值 + 自检
                if rep:
                    body = rep[rep.find('【思考过程】'):] if '【思考过程】' in rep else rep
                    chain_answer = '【精确计算】\n问题：' + expr + '\n' + body
                    expr = ''                         # 跳过后续模型链路
            elif route == 'web' and BACKEND != "nanogpt" and mode != 'think':  # 思考模式要求离线，跳过联网
                results = web_search(web_query(text))     # 先洗干净再搜，否则会搜跑偏
                if results:
                    msgs = [{"role": "user", "content": web_grounded(text, results)}]
                    web_sources = results                  # 回答后附来源
                    req_max = 800 if mode == 'simple' else 1500
                else:                                      # 没搜到就照常回答
                    msgs = s["messages"][:-1] + [{"role": "user", "content": text + "\n" + brief}]
            elif route == 'lookup':                   # 二级：事实题，直接查知识库
                got = lookup_answer(text)             # 检索最相关原文
                if got:
                    chain_answer = got                # 直出，不调用模型
                    expr = ''
                else:                                 # 知识库没有 → 先联网找依据
                    results = web_search(web_query(text))
                    if results:
                        msgs = [{"role": "user", "content": web_grounded(text, results)}]
                        web_sources = results
                        route = "web"                 # 后续按"有材料"处理
                    else:                             # 联网也没有 → 如实说，不编
                        chain_answer = ("这个问题我的知识库里没有相关资料，联网也没搜到可靠来源。\n\n"
                                        "我宁可说不知道，也不编一个像模像样的答案给你。\n\n"
                                        "你可以把问题说得更具体些，或者换个说法再问一次。")

            if expr and route == 'think' and BACKEND != "nanogpt":  # 三级：需要思考的题交给模型
                fmt = ("只输出计算步骤，不要任何解释。每步格式严格为 算式=结果，用分号分隔，"
                       "最后一步的结果就是答案。例如：3+5=8;8*2=16")  # 强约束格式
                try:  # 模型调用可能失败
                    chain = llama_once([{"role": "user", "content": text + "\n" + fmt}], 300)  # 第一轮：模型出思路
                except Exception:  # 失败就退回普通流程
                    chain = ""
                for attempt in range(2):  # 最多两轮：第一轮 + 一次纠错
                    ok, ans, report = run_chain(chain)  # C 引擎逐步验算
                    if ok:  # 全部步骤通过
                        chain_answer = (report.split("【汇总】")[0].strip()
                                        + "\n\n【结论】" + ans + "（每一步都由精确计算器复核通过）")  # 组合展示文本
                        break  # 结束循环
                    if attempt == 0:  # 第一轮有错，把错处反馈给模型重写
                        fix = ("你上一步算错了。验证报告如下，请只输出修正后的整条推理链"
                               "（格式仍然是 算式=结果，分号分隔，不要解释）：\n" + report)
                        try:
                            chain = llama_once([{"role": "user", "content": text + "\n" + fix}], 300)  # 第二轮
                        except Exception:  # 失败就放弃纠错
                            break
                    else:  # 两轮都不对，如实告知
                        chain_answer = (report.strip()
                                        + "\n\n【结论】模型给出的推理链存在错误步骤，无法给出可信答案。")  # 诚实说明

            try:  # 后端可能报错（模型崩溃、超时）
                if chain_answer:  # 推理链已验证，直接把它作为回答推给用户
                    for ch in chain_answer:  # 逐字发送，保持流式观感
                        acc.append(ch)
                        emit({"delta": ch})
                elif BACKEND == "nanogpt":  # 自研模型后端（只有在 --backend nanogpt 时才走这里）
                    # 思考模式现在走本地 llama 模型 + 奥数题库，不再依赖 DeepSeek，也不联网。
                    # 它只有 136 万参数、字符级建模，不会回答问题，只会接着往下写文本。
                    prompt = text + "\n"  # 用问题本身当提示，让模型接着往下写
                    for delta in stream_nanogpt(prompt, usage):  # 逐字符增量
                        acc.append(delta)  # 累积
                        emit({"delta": delta})  # 立刻推给浏览器
                else:  # 外部模型
                    temp = 0.25 if (web_sources or hits) else 0.7  # 有材料时用低温，纯闲聊用常温
                    for delta in stream_llama(msgs, usage, req_max, model_url, temp):  # 逐个增量（按模式选模型）
                        acc.append(delta)  # 累积
                        emit({"delta": delta})  # 立刻推给浏览器
            except Exception as e:  # 记录错误到对话里，用户能看到原因
                emit({"delta": "\n[后端出错：%s]" % e})  # 以文本形式回传
            raw_ans = usage.get("answer") or usage.get("think") or "".join(acc)  # 优先正文，其次思考
            ans = strip_refs(raw_ans) or "（模型没有给出答案）"  # 清洗出处措辞并兜底
            try:  # 落盘失败不影响回答
                save_thinking(sid, text, usage.get("think", ""), raw_ans, usage, web_sources)
            except Exception as e:
                print("[thinking] 保存失败:", e, flush=True)

            # 材料没覆盖到关键部分时，必须明确声明，不许含糊带过
            if hits or web_sources:
                ctx_for_gap = "\n".join(h for h in (hits or [])) + \
                              "\n".join("%s %s" % (t_, s_) for t_, _, s_ in (web_sources or []))
                gap_note = missing_disclosure(raw_ans, ctx_for_gap, text)
                if gap_note:
                    emit({"delta": gap_note})
                    acc.append(gap_note)

            # 事实核对：只在有材料的场景做（查库、联网），没材料的闲聊无从核对
            if hits or web_sources:
                ctx_all = "\n".join(h for h in (hits or [])) + \
                          "\n".join("%s %s" % (t_, s_) for t_, _, s_ in (web_sources or []))
                unsupported = faith_check(raw_ans, ctx_all, text)
                if unsupported:
                    note = ("\n\n---\n**提示**：以下内容在查到的资料里没有依据，"
                            "可能是模型自行补充的，请谨慎采信：%s" % "、".join(unsupported))
                    emit({"delta": note})
                    acc.append(note)

            if web_sources:                              # 联网过就把来源发出去
                src = format_sources(web_sources)
                emit({"delta": src})
                acc.append(src)
            s["messages"].append({"role": "assistant", "content": ans})  # 记录助手回答
            save_session(sid)  # 落盘
            emit({"session": sid, "refs": ref_count,  # 最后一帧带上会话 ID 和引用数
                  "usage": {"in": usage.get("in", 0), "out": usage.get("out", 0),  # 输入输出 token
                            "total": usage.get("in", 0) + usage.get("out", 0),  # 合计
                            "model": usage.get("out", 0)}})  # 前端展示"模型消耗"
            self.wfile.write(b"data: [DONE]\n\n")  # SSE 结束标记
            self.wfile.flush()  # 刷出
            self.close_connection = True  # 主动断开，避免 keep-alive 把连接占住
        else:  # 未知 POST 路径
            self._send(b'{"error":"not found"}')  # 统一错误


def main() -> int:
    """程序入口：解析参数、加载索引、启动 HTTP 服务。"""
    global LLAMA, MAX_NEW, BACKEND, NP_BIN, NP_WEIGHTS, NP_LEN  # 需要在函数内覆盖这些模块级配置
    ap = argparse.ArgumentParser()  # 创建参数解析器
    ap.add_argument("--port", type=int, default=8091)  # 监听端口
    ap.add_argument("--bind", default="0.0.0.0", help="监听地址")  # 0.0.0.0 允许外部访问，127.0.0.1 只允许本机
    ap.add_argument("--llama", default=LLAMA)  # 后端地址
    ap.add_argument("--max-new", type=int, default=800)  # 默认生成长度
    ap.add_argument("--corpus", default=CORPUS)  # 教材语料路径
    ap.add_argument("--no-rag", action="store_true")  # 开关：完全关闭检索，用于对比测试
    ap.add_argument("--backend", default="llama", choices=["llama", "nanogpt"])  # 选择后端
    ap.add_argument("--np-bin", default=NP_BIN)  # 自研模型可执行文件
    ap.add_argument("--np-weights", default=NP_WEIGHTS)  # 自研模型权重
    ap.add_argument("--np-len", type=int, default=NP_LEN)  # 自研模型生成长度
    args = ap.parse_args()  # 解析命令行
    LLAMA = args.llama  # 应用后端地址
    MAX_NEW = args.max_new  # 应用生成长度
    BACKEND = args.backend  # 后端类型
    NP_BIN = args.np_bin  # 自研模型路径
    NP_WEIGHTS = args.np_weights  # 权重路径
    NP_LEN = args.np_len  # 生成长度
    if not args.no_rag:  # 默认开启检索
        build_index(args.corpus)  # 建教材索引
        load_olympiad(OLYMPIAD)  # 加载奥数题库
    load_sessions()  # 读回历史会话
    srv = ThreadingHTTPServer((args.bind, args.port), Handler)  # 线程化 HTTP 服务，支持并发请求
    print(f"AI 服务已启动: http://{args.bind}:{args.port}  (后端 {LLAMA})", flush=True)  # 启动日志
    srv.serve_forever()  # 阻塞运行
    return 0  # 正常情况下不会走到这里


if __name__ == "__main__":
    raise SystemExit(main())  # 以 main 的返回值作为退出码
