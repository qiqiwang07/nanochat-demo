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
import threading  # 线程锁，保护 sessions 字典的并发写
import time  # 计时（统计生成耗时）与生成会话 ID
import urllib.request  # 向 llama-server 发 HTTP 请求（标准库，无需第三方依赖）
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # 内置 HTTP 服务，线程模型支持并发
from urllib.parse import urlparse, parse_qs  # 解析 URL 路径与查询参数

HERE = os.path.dirname(os.path.abspath(__file__))  # 本文件所在目录，兼容 Windows 与 Linux 两种路径分隔符
BIN_DIR = HERE  # 静态文件（chat.html）与脚本同目录，方便整体拷贝部署
SESS_DIR = os.path.join(HERE, "sessions")  # 会话记录目录，放在脚本同级，避免依赖外部绝对路径
CORPUS = os.path.join(HERE, "corpus.txt")  # 教材语料文件，缺失时检索自动降级为不用教材
OLYMPIAD = os.path.join(HERE, "olympiad_index.json")  # 奥数题库索引，含题目与标准解答

LLAMA = "http://127.0.0.1:8080/v1/chat/completions"  # 默认后端地址，可通过 --llama 覆盖
MAX_NEW = 800  # 默认单次最多生成多少 token，可通过 --max-new 覆盖

sessions = {}  # 内存中的会话表：{会话ID: {"title": 标题, "messages": [{"role","content"}]}}
chunks = []  # 教材切块后的文本片段，供检索使用
chunk_grams = []  # 与 chunks 一一对应的字符二元组集合，预先算好避免每次查询重复计算
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
        inter = len(qg & dg)  # 共同二元组数量
        if inter >= 3:  # 门槛比题库低，因为教材是泛泛背景，不必精准
            scored.append((inter / (len(dg) ** 0.5), i))  # 只做单向归一化，长片段不会过度占优
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


def stream_llama(messages, usage_out: dict, max_tokens=None):
    """向 llama-server 请求流式输出，逐个产出文本增量，usage 写进 usage_out。

    这是生成器：调用方每拿到一个增量就可以立刻推给浏览器，
    从而产生"打字机"效果，而不是等整段生成完。
    """
    body = {  # 组装 OpenAI 兼容的请求体
        "messages": messages,  # 对话历史（含提示词注入）
        "max_tokens": int(max_tokens or MAX_NEW),  # 本次最多生成多少 token
        "temperature": 0.7,  # 采样温度，0.7 兼顾稳定与自然
        "top_p": 0.9,  # 核采样，截掉长尾避免说出离谱内容
        "repeat_penalty": 1.05,  # 轻微惩罚重复，防止小模型复读
        "stream": True,  # 开启流式，这是打字机效果的前提
        "stream_options": {"include_usage": True},  # 让最后一个分片带上 token 统计
        "stop": ["\n\n\n", "好的，我来", "嗯，我来"],  # 命中这些串就停止，防止模型自问自答
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")  # 手工编码，中文不转义以省字节
    req = urllib.request.Request(LLAMA, data=data, headers={"Content-Type": "application/json"})  # 构造请求
    t0 = time.time()  # 记录起始时间，用于日志统计
    started = False  # 标记是否已经开始向调用方产出内容
    pre = ""  # 首块缓冲，用于处理可能的思考标记
    with urllib.request.urlopen(req, timeout=900) as r:  # 900 秒超时，CPU 推理长文本可能很慢
        for raw in r:  # 逐行读取 SSE 流
            line = raw.decode("utf-8", "ignore").strip()  # 解码并去掉首尾空白
            if not line.startswith("data:"):  # 只处理数据行，忽略空行和注释
                continue  # 跳过
            payload = line[5:].strip()  # 去掉 "data:" 前缀
            if payload == "[DONE]":  # 流结束标记
                break  # 退出循环
            try:  # 分片可能因为网络截断而不完整，用 try 保护
                j = json.loads(payload)  # 解析单个分片
            except Exception:  # 解析失败说明该分片损坏
                continue  # 跳过这个分片，不影响整体
            u = j.get("usage")  # 只有最后一个分片或开启 include_usage 时才有
            if u:  # 有统计信息就更新
                usage_out["in"] = int(u.get("prompt_tokens") or 0)  # 输入 token 数
                usage_out["out"] = int(u.get("completion_tokens") or 0)  # 输出 token 数
            ch = j.get("choices") or [{}]  # 容错：异常分片可能没有 choices
            delta = (ch[0].get("delta") or {}).get("content") or ""  # 取出本分片的文本增量
            if not delta:  # 空增量（如首个分片只有 role 字段）直接跳过
                continue  # 继续读下一行
            if not started:  # 还没开始产出，先做首块处理
                pre += delta  # 累积到缓冲区
                if "</think>" in pre:  # 推理模型可能自带思考块
                    pre = pre.split("</think>", 1)[1]  # 丢掉思考部分，只留答案
                pre = pre.lstrip("\n")  # 去掉开头换行，避免气泡顶部空白
                if pre:  # 缓冲区有内容才输出
                    started = True  # 标记已开始
                    yield pre  # 交出第一批文本
                    pre = ""  # 清空缓冲
            else:  # 已经开始了，直接转发增量
                yield delta  # 交给调用方推给浏览器
    dt = time.time() - t0  # 计算总耗时
    print(f"[llama] 输出 {usage_out.get('out', 0)} token / {dt:.1f}s", flush=True)  # 记录到日志，便于对比性能


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
        elif u.path in ("/", "/chat.html"):  # 首页与显式页面路径都返回同一份 HTML
            p = os.path.join(BIN_DIR, "chat.html")  # 页面文件位置
            with open(p, "rb") as f:  # 二进制读，避免编码转换
                self._send(f.read(), "text/html")  # 以 HTML 类型返回
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
            sid = body.get("session") or ""  # 客户端传来的会话 ID
            if sid not in sessions:  # 没带或带了个不存在的 ID
                sid = new_sid()  # 新建一个，避免把消息丢进不存在的会话
                sessions[sid] = {"title": "", "messages": []}  # 初始化
            s = sessions[sid]  # 取出会话对象
            s["messages"].append({"role": "user", "content": text})  # 先记录用户消息
            if not s["title"]:  # 标题只在第一条消息时设置
                s["title"] = text[:20]  # 取前 20 字做标题，够用又不撑破侧边栏
            math_hits = retrieve_olympiad(text, 1)  # 先判断是不是数学题，数学题才检索题库
            hits = retrieve(text, 2)  # 再检索教材片段作为背景知识
            msgs = list(s["messages"])  # 复制一份对话历史，避免改动原始记录
            brief = ("回答要详实自然，像跟朋友解释一样：把内容讲清楚，可以举例。"  # 只提要求不列结构，避免被照抄成小标题
                     "篇幅 300-600 字。"  # 控制篇幅
                     "直接给内容，不要写“先说结论/解释为什么/补充要点”这类格式说明，"  # 明确禁止复述提示词
                     "也不要写“好的/我来想想/首先”，不要复述题目。")  # 禁止开场空话
            if math_hits:  # 是数学题：注入相似题与标准解答
                refs = "\n\n".join(  # 把多道参考题拼成一段
                    "【相似题%d】\n题目：%s\n标准解答：%s" % (i + 1, q, a[:900])  # 解答截断到 900 字，控制提示词长度
                    for i, (sc, q, a) in enumerate(math_hits))  # 逐条格式化
                grounded = ("下面给出几道相似题目及其标准解答，请参考它们的解题思路和书写格式，"  # 明确告诉模型参考什么
                            "解答用户提出的新题目。\n"  # 任务说明
                            "要求：写清完整推理步骤（每一步说清楚为什么这么做），"  # 要求步骤完整
                            "最后用 \\boxed{} 给出答案；答完可以补充一句思路小结或易错点提醒。"  # 统一答案格式
                            "不要提及“相似题/参考/资料”这些字眼。\n\n"  # 禁止暴露参考来源
                            + refs + "\n\n【需要解答的题目】\n" + text)  # 拼上真正要答的题目
                msgs = s["messages"][:-1] + [{"role": "user", "content": grounded}]  # 用注入后的提示替换最后一条用户消息
            elif hits:  # 不是数学题但有教材片段：注入背景材料
                ctx = "\n\n".join(hits)  # 拼接片段
                grounded = ("以下是一些参考材料，请据此回答。不要说明内容来自哪里，"  # 提示模型别说出处
                            "不要提资料、教材或书名。" + brief + "\n\n" + ctx + "\n\n问题：" + text)  # 材料 + 要求 + 问题
                msgs = s["messages"][:-1] + [{"role": "user", "content": grounded}]  # 同样替换最后一条
            else:  # 都没有：直接回答
                msgs = s["messages"][:-1] + [{"role": "user", "content": text + "\n\n" + brief}]  # 只加回答要求
            ref_count = len(math_hits) + (0 if math_hits else len(hits))  # 统计参考了多少条，前端可展示
            req_max = max(MAX_NEW, 3000) if math_hits else MAX_NEW  # 数学题解答长，给更大额度
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
            try:  # 后端可能报错（模型崩溃、超时）
                for delta in stream_llama(msgs, usage, req_max):  # 逐个增量
                    acc.append(delta)  # 累积
                    emit({"delta": delta})  # 立刻推给浏览器
            except Exception as e:  # 记录错误到对话里，用户能看到原因
                emit({"delta": "\n[后端出错：%s]" % e})  # 以文本形式回传
            ans = strip_refs("".join(acc)) or "（模型没有给出答案）"  # 清洗出处措辞并兜底
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
    global LLAMA, MAX_NEW  # 需要覆盖模块级默认值
    ap = argparse.ArgumentParser()  # 创建参数解析器
    ap.add_argument("--port", type=int, default=8091)  # 监听端口
    ap.add_argument("--bind", default="0.0.0.0", help="监听地址")  # 0.0.0.0 允许外部访问，127.0.0.1 只允许本机
    ap.add_argument("--llama", default=LLAMA)  # 后端地址
    ap.add_argument("--max-new", type=int, default=800)  # 默认生成长度
    ap.add_argument("--corpus", default=CORPUS)  # 教材语料路径
    ap.add_argument("--no-rag", action="store_true")  # 开关：完全关闭检索，用于对比测试
    args = ap.parse_args()  # 解析命令行
    LLAMA = args.llama  # 应用后端地址
    MAX_NEW = args.max_new  # 应用生成长度
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
