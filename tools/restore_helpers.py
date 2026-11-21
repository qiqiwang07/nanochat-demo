# -*- coding: utf-8 -*-
"""补回被误删的辅助函数：算式提取、精确推理、模型单次调用、链验证、自研模型流式、路由与检索直出。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

BLOCK = '''def extract_expr(text: str) -> str:
    """从问题里挑出一个可计算的算式；挑不到返回空串。"""
    best = ""
    for m in re.finditer(r"[0-9][0-9\\s.()+\\-*/^%]*[0-9]", text):
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
              '的作者是谁', '的作者', '是谁', '多少', '有哪些', '都有谁', '怎么样',
              '的', '是', '请', '吗', '呢', '？', '?', '。'):
        s = s.replace(w, ' ')
    out = []
    for seg in s.split():
        seg = seg.strip('《》「」“”"\\'()（）')
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
        for para in h.split('\\n'):
            para = para.strip()
            if not para:
                continue
            for term in terms:
                if term in para and len(para) > len(best_para):
                    best_para = para
                    break
        if best_para:
            if len(best_para) > 400:
                cut = best_para.rfind('。', 0, 400)
                best_para = best_para[:cut + 1] if cut > 80 else best_para[:400]
            return '【知识库检索】\\n' + best_para
        left = max(0, pos - 120)
        right = min(len(h), pos + 280)
        body = h[left:right].strip()
        cut = max(body.rfind('。'), body.rfind('\\n'))
        if cut > 60:
            body = body[:cut + 1]
        return '【知识库检索】\\n' + body
    return ''


def classify(text: str) -> str:
    """判断题型：calc（纯算式）/ lookup（事实查询）/ think（需要推理或创作）。

    实测依据：
      - 算式题交 C 引擎，毫秒级且绝对准确
      - 事实题直接检索，比 8B 模型思考快 20 倍
      - 生成/推理题必须走模型，否则会拿无关原文糊弄
    """
    s = text.strip()
    cjk = sum(1 for ch in s if '\\u4e00' <= ch <= '\\u9fff')
    if extract_expr(s) and cjk <= 6:
        return 'calc'
    think_keys = ('写', '代码', '函数', '程序', '实现', '算法', '编程', '作文', '议论文',
                  '记叙文', '散文', '诗', '为什么', '证明', '推导', '分析', '比较',
                  '评价', '设计', '优化', '如何', '怎样', '步骤', '计算', '求')
    if any(k in s for k in think_keys):
        return 'think'
    lookup_heads = ('什么是', '什么叫', '是什么', '谁是', '的作者', '的作者是谁',
                    '多少', '几位', '哪一年', '解释一下', '定义')
    if any(s.startswith(h) or h in s for h in lookup_heads):
        return 'lookup'
    return 'think'


'''

anchor = 'def load_sessions() -> None:'
assert anchor in t, '找不到插入锚点'
t = t.replace(anchor, BLOCK + anchor, 1)
ast.parse(t)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('辅助函数已补回')
