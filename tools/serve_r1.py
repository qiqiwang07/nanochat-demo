"""AI 助手服务（快速版）：后端用 llama-server（GGUF 4bit），带教材检索。

结构：
   浏览器  ──►  serve_r1.py (8091, 本文件)  ──►  llama-server (8080, GGUF 模型)

本文件负责：网页、会话管理、教材检索（RAG）、token 统计、去掉出处措辞。

用法：
    python serve_r1.py [--port 8091] [--llama http://127.0.0.1:8080] [--max-new 800]
"""
import argparse
import json
import os
import re
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BIN_DIR = r"C:\Users\Lenovo\ai\nanochat-demo\bin"
SESS_DIR = r"C:\Users\Lenovo\ai\nanochat-demo\data\r1_sessions"
CORPUS = r"C:\Users\Lenovo\ai\nanochat-demo\data\book_corpus.txt"
OLYMPIAD = r"C:\Users\Lenovo\ai\nanochat-demo\data\olympiad_index.json"

LLAMA = "http://127.0.0.1:8080/v1/chat/completions"
MAX_NEW = 800

sessions = {}
chunks = []
chunk_grams = []
olympiad = []          # [{"q":题目, "a":标准解答, "_g":题干二元组}]
lock = threading.Lock()


def load_olympiad(path: str) -> None:
    """加载奥数题库索引（题目+标准解答）。"""
    global olympiad
    if not os.path.exists(path):
        print("未找到奥数题库:", path, flush=True)
        return
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print("奥数题库读取失败:", e, flush=True)
        return
    for it in data:
        it["_g"] = _grams(it.get("q", ""))
    olympiad = data
    print("奥数题库: %d 道（含标准解答）" % len(olympiad), flush=True)


def retrieve_olympiad(query: str, k: int = 2, min_score: float = 0.12):
    """按题干字符二元组重合度找相似题，返回 [(相似度, 题, 解答)]。"""
    if not olympiad:
        return []
    qg = _grams(query)
    if not qg:
        return []
    scored = []
    for it in olympiad:
        dg = it.get("_g") or set()
        if not dg:
            continue
        inter = len(qg & dg)
        if inter < 8:
            continue
        score = inter / ((len(qg) ** 0.5) * (len(dg) ** 0.5))
        if score >= min_score:
            scored.append((score, it))
    scored.sort(key=lambda x: -x[0])
    return [(s, it["q"], it["a"]) for s, it in scored[:k]]


# ------------------------------ 教材检索 ------------------------------
def _grams(s: str) -> set:
    s = "".join(ch for ch in s if not ch.isspace())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def build_index(path: str, size: int = 400, overlap: int = 60) -> None:
    global chunks, chunk_grams
    if not os.path.exists(path):
        print("未找到教材语料:", path, flush=True)
        return
    text = open(path, encoding="utf-8", errors="ignore").read()
    t0 = time.time()
    raw, step = [], size - overlap
    for i in range(0, max(1, len(text) - size // 2), step):
        c = text[i:i + size].strip()
        if len(c) >= 200:
            raw.append(c)
    chunk_grams = [_grams(c) for c in raw]
    chunks = raw
    print(f"教材索引: {len(chunks)} 段，{len(text)/1e6:.1f} M 字符，用时 {time.time()-t0:.1f}s", flush=True)


def retrieve(query: str, k: int = 4) -> list:
    if not chunks:
        return []
    qg = _grams(query)
    if not qg:
        return []
    scored = []
    for i, dg in enumerate(chunk_grams):
        if not dg:
            continue
        inter = len(qg & dg)
        if inter >= 3:
            scored.append((inter / (len(dg) ** 0.5), i))
    scored.sort(reverse=True)
    return [chunks[i] for _, i in scored[:k]]


# ------------------------------ 回答清洗 ------------------------------
def strip_thinking(text: str) -> str:
    for marker in ("</think>", "<｜end▁of▁thinking｜>"):
        if marker in text:
            text = text.rsplit(marker, 1)[1]
    return text.strip()


def strip_refs(text: str) -> str:
    if not text:
        return text
    pats = [
        r"根据\s*资料\s*\d+[，,、：:]*",
        r"参考\s*资料\s*\d+[，,、：:]*",
        r"资料\s*\d+\s*[中里]?(提到|指出|表明|说明)[，,：:]?",
        r"根据\s*(教材|课本|原书|书中)[，,：:]?",
        r"教材\s*[中里](提到|指出|表明|说明)[，,：:]?",
        r"《[^》]{2,20}》\s*[中里]?(提到|指出|表明|说明)?[，,：:]?",
        r"(第\s*\d+(\.\d+)*\s*[章节])\s*(提到|指出|表明|说明)?[，,：:]?",
    ]
    out = text
    for p in pats:
        out = re.sub(p, "", out)
    # 去掉“嗯，”/“好的，”/“我来想想”这类开场废话
    out = re.sub(r"^(嗯|哦|啊|好的|好吧|行|我来想想|让我想想|首先)[，,。；;、\s]*", "", out)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


# ------------------------------ 调用后端 ------------------------------
def stream_llama(messages, usage_out: dict, max_tokens=None):
    """向 llama-server 请求流式输出，逐个产出文本增量；usage 写进 usage_out。"""
    body = {
        "messages": messages,
        "max_tokens": int(max_tokens or MAX_NEW),
        "temperature": 0.7,
        "top_p": 0.9,
        "repeat_penalty": 1.05,
        "stream": True,
        "stream_options": {"include_usage": True},
        "stop": ["\n\n\n", "好的，我来", "嗯，我来"],
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(LLAMA, data=data, headers={"Content-Type": "application/json"})
    t0 = time.time()
    started = False
    pre = ""
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
            if u:
                usage_out["in"] = int(u.get("prompt_tokens") or 0)
                usage_out["out"] = int(u.get("completion_tokens") or 0)
            ch = j.get("choices") or [{}]
            delta = (ch[0].get("delta") or {}).get("content") or ""
            if not delta:
                continue
            if not started:
                pre += delta
                # 推理模型才需要剥掉思考标记；Qwen 这类直接输出
                if "</think>" in pre:
                    pre = pre.split("</think>", 1)[1]
                pre = pre.lstrip("\n")
                if pre:
                    started = True
                    yield pre
                    pre = ""
            else:
                yield delta
    dt = time.time() - t0
    print(f"[llama] 输出 {usage_out.get('out', 0)} token / {dt:.1f}s", flush=True)


# ------------------------------ 会话 ------------------------------
def load_sessions() -> None:
    os.makedirs(SESS_DIR, exist_ok=True)
    for fn in os.listdir(SESS_DIR):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(SESS_DIR, fn), encoding="utf-8") as f:
                    sessions[fn[:-5]] = json.load(f)
            except Exception:
                pass


def save_session(sid: str) -> None:
    os.makedirs(SESS_DIR, exist_ok=True)
    with open(os.path.join(SESS_DIR, sid + ".json"), "w", encoding="utf-8") as f:
        json.dump(sessions[sid], f, ensure_ascii=False, indent=1)


def new_sid() -> str:
    return "r%d" % (int(time.time() * 1000) % 10 ** 9)


# ------------------------------ HTTP ------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, body: bytes, ctype: str = "application/json"):
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/chat.html"):
            p = os.path.join(BIN_DIR, "chat.html")
            with open(p, "rb") as f:
                self._send(f.read(), "text/html")
        elif u.path == "/sessions":
            data = [{"id": k, "title": v.get("title") or "新会话"} for k, v in sessions.items()]
            data.sort(key=lambda x: x["id"], reverse=True)
            self._send(json.dumps({"sessions": data}, ensure_ascii=False).encode())
        elif u.path == "/session":
            sid = (parse_qs(u.query).get("id") or [""])[0]
            s = sessions.get(sid)
            log = ""
            if s:
                for m in s["messages"]:
                    log += ("### User: " if m["role"] == "user" else "### Assistant: ") + m["content"] + "\n"
            self._send(json.dumps({"log": log}, ensure_ascii=False).encode())
        else:
            self._send(b'{"error":"not found"}')

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            body = {}

        if u.path == "/new":
            sid = new_sid()
            sessions[sid] = {"title": "", "messages": []}
            save_session(sid)
            self._send(json.dumps({"id": sid}).encode())

        elif u.path == "/chat":
            text = (body.get("text") or "").strip()
            sid = body.get("session") or ""
            if sid not in sessions:
                sid = new_sid()
                sessions[sid] = {"title": "", "messages": []}
            s = sessions[sid]
            s["messages"].append({"role": "user", "content": text})
            if not s["title"]:
                s["title"] = text[:20]

            # 先看是不是数学题：是的话检索相似题 + 标准解答作为参考
            math_hits = retrieve_olympiad(text, 1)
            hits = retrieve(text, 2)
            msgs = list(s["messages"])
            brief = ("回答要求：像朋友聊天一样，讲得详细一点、展开一点——"
                     "先说结论，再解释为什么，然后补充要点、例子或注意事项。"
                     "篇幅 300-600 字为宜，分点或分段都行。"
                     "不要只回一两句话，也不要写“好的/我来想想/首先”这类空话，不要复述题目。")
            if math_hits:
                refs = "\n\n".join(
                    "【相似题%d】\n题目：%s\n标准解答：%s" % (i + 1, q, a[:900])
                    for i, (sc, q, a) in enumerate(math_hits))
                grounded = ("下面给出几道相似题目及其标准解答，请参考它们的解题思路和书写格式，"
                            "解答用户提出的新题目。\n"
                            "要求：写清完整推理步骤（每一步说清楚为什么这么做），"
                            "最后用 \\boxed{} 给出答案；答完可以补充一句思路小结或易错点提醒。"
                            "不要提及“相似题/参考/资料”这些字眼。\n\n"
                            + refs + "\n\n【需要解答的题目】\n" + text)
                msgs = s["messages"][:-1] + [{"role": "user", "content": grounded}]
            elif hits:
                ctx = "\n\n".join(hits)
                grounded = ("以下是一些参考材料，请据此回答。不要说明内容来自哪里，"
                            "不要提资料、教材或书名。" + brief + "\n\n" + ctx + "\n\n问题：" + text)
                msgs = s["messages"][:-1] + [{"role": "user", "content": grounded}]
            else:
                msgs = s["messages"][:-1] + [{"role": "user", "content": text + "\n\n" + brief}]
            ref_count = len(math_hits) + (0 if math_hits else len(hits))
            # 数学题解答长，给更大的输出额度
            req_max = max(MAX_NEW, 3000) if math_hits else MAX_NEW

            # 流式输出（SSE）
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            usage = {}
            acc = []

            def emit(obj):
                self.wfile.write(b"data: " + json.dumps(obj, ensure_ascii=False).encode() + b"\n\n")
                self.wfile.flush()

            try:
                for delta in stream_llama(msgs, usage, req_max):
                    acc.append(delta)
                    emit({"delta": delta})
            except Exception as e:
                emit({"delta": "\n[后端出错：%s]" % e})
            ans = strip_refs("".join(acc)) or "（模型没有给出答案）"
            s["messages"].append({"role": "assistant", "content": ans})
            save_session(sid)
            emit({"session": sid, "refs": ref_count,
                  "usage": {"in": usage.get("in", 0), "out": usage.get("out", 0),
                            "total": usage.get("in", 0) + usage.get("out", 0),
                            "model": usage.get("out", 0)}})
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
            self.close_connection = True
        else:
            self._send(b'{"error":"not found"}')


def main() -> int:
    global LLAMA, MAX_NEW
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8091)
    ap.add_argument("--bind", default="0.0.0.0", help="监听地址")
    ap.add_argument("--llama", default=LLAMA)
    ap.add_argument("--max-new", type=int, default=800)
    ap.add_argument("--corpus", default=CORPUS)
    ap.add_argument("--no-rag", action="store_true")
    args = ap.parse_args()
    LLAMA = args.llama
    MAX_NEW = args.max_new
    if not args.no_rag:
        build_index(args.corpus)
        load_olympiad(OLYMPIAD)
    load_sessions()
    srv = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"AI 服务已启动: http://127.0.0.1:{args.port}  (后端 {LLAMA})", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
