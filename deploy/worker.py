"""本地工作进程（在这台有模型的电脑上运行）

作用：主动连到云端中转服务，领任务 → 用本地 llama-server 生成回答 →
      把结果流式推回云端 → 用户在网页上看到答案。

优点：本机不需要公网 IP，也不需要在路由器上开端口，是主动向外连接。

用法：
    python worker.py [--server http://1.117.113.68:7000] [--token wzw7000relay]
"""
import argparse
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

SRV = "http://1.117.113.68:80"
HOST_HEADER = "c-learning.oprfin.com"   # 通过 nginx 转发到 7000 的域名
TOKEN = "wzw7000relay"
LLAMA = "http://127.0.0.1:8080/v1/chat/completions"
MAX_NEW = 400
CORPUS = r"C:\Users\Lenovo\ai\nanochat-demo\data\book_corpus.txt"

chunks = []
chunk_grams = []


def _request(method, path, body=None, timeout=40):
    """向中转服务发请求。支持用 Host 头走 nginx（服务器没开放 7000 端口时）。"""
    u = urlparse(SRV)
    conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=timeout)
    headers = {}
    data = None
    if HOST_HEADER:
        headers["Host"] = HOST_HEADER
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=data, headers=headers)
    resp = conn.getresponse()
    raw = resp.read()
    conn.close()
    return resp.status, raw


def _grams(s):
    s = "".join(ch for ch in s if not ch.isspace())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def build_index(path):
    global chunks, chunk_grams
    if not os.path.exists(path):
        print("没有教材语料，跳过检索", flush=True)
        return
    text = open(path, encoding="utf-8", errors="ignore").read()
    raw = []
    step = 600
    for i in range(0, max(1, len(text) - 350), step):
        c = text[i:i + 700].strip()
        if len(c) >= 200:
            raw.append(c)
    chunks = raw
    chunk_grams = [_grams(c) for c in raw]
    print("教材索引: %d 段" % len(chunks), flush=True)


def retrieve(q, k=3):
    if not chunks:
        return []
    qg = _grams(q)
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


def post(path, obj, timeout=30):
    st, raw = _request("POST", path, obj, timeout)
    return raw


def poll():
    try:
        st, raw = _request("GET", "/worker/poll?token=" + TOKEN, None, timeout=40)
        if st == 204:
            return None
        return json.loads(raw) if raw else None
    except Exception as e:
        print("poll 失败:", e, flush=True)
        return None


def send_chunk(tid, delta):
    try:
        post("/worker/chunk", {"id": tid, "delta": delta, "token": TOKEN})
    except Exception as e:
        print("chunk 失败:", e, flush=True)


def send_done(tid, usage):
    try:
        post("/worker/done", {"id": tid, "usage": usage, "token": TOKEN})
    except Exception as e:
        print("done 失败:", e, flush=True)


def answer(tid, text):
    hits = retrieve(text, 3)
    if hits:
        prompt = ("以下是一些参考材料，请据此回答。不要说明内容来自哪里，不要提资料或书名。"
                  "用不超过 80 个字直接给结论，最多再补一句解释。\n\n"
                  + "\n\n".join(hits) + "\n\n问题：" + text)
    else:
        prompt = text + "\n\n要求：用不超过 80 个字直接给结论。"
    body = {"messages": [{"role": "user", "content": prompt}], "max_tokens": MAX_NEW,
            "temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.05,
            "stream": True, "stream_options": {"include_usage": True}}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(LLAMA, data=data, headers={"Content-Type": "application/json"})
    usage = {"in": 0, "out": 0, "total": 0, "model": 0}
    started = False
    pre = ""
    buf = ""
    last = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
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
                    usage = {"in": int(u.get("prompt_tokens") or 0),
                             "out": int(u.get("completion_tokens") or 0),
                             "total": int(u.get("total_tokens") or 0),
                             "model": int(u.get("completion_tokens") or 0)}
                ch = j.get("choices") or [{}]
                delta = (ch[0].get("delta") or {}).get("content") or ""
                if not delta:
                    continue
                if not started:
                    pre += delta
                    for mk in ("</think>", "<｜end▁of▁thinking｜>"):
                        if mk in pre:
                            pre = pre.split(mk, 1)[1]
                            started = True
                            break
                    if not started and len(pre) > 200:
                        started = True
                    if started:
                        buf += pre.lstrip("\n")
                        pre = ""
                else:
                    buf += delta
                now = time.time()
                if len(buf) >= 24 or now - last > 0.25:
                    send_chunk(tid, buf)
                    buf = ""
                    last = now
    except Exception as e:
        send_chunk(tid, "\n[本地模型出错：%s]" % e)
    if buf:
        send_chunk(tid, buf)
    send_done(tid, usage)
    print("已回复任务 %s（%d token）" % (tid, usage["out"]), flush=True)


def main():
    global SRV, TOKEN, HOST_HEADER
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default=SRV, help="中转服务地址，例如 http://1.117.113.68:80")
    ap.add_argument("--host-header", default=HOST_HEADER, help="走 nginx 时使用的 Host 头")
    ap.add_argument("--token", default=TOKEN)
    ap.add_argument("--no-rag", action="store_true")
    args = ap.parse_args()
    SRV = args.server.rstrip("/")
    HOST_HEADER = args.host_header
    TOKEN = args.token
    print("中转服务:", SRV, "| Host:", HOST_HEADER, flush=True)
    if not args.no_rag:
        build_index(CORPUS)
    print("等待任务…（Ctrl+C 退出）", flush=True)
    idle = 0
    while True:
        task = poll()
        if not task:
            idle += 1
            if idle % 10 == 0:
                print("仍在等待（本地模型端口 8080 需保持运行）", flush=True)
            time.sleep(0.5)
            continue
        idle = 0
        print("收到任务 %s: %s" % (task.get("id"), (task.get("text") or "")[:40]), flush=True)
        try:
            answer(task["id"], task.get("text") or "")
        except Exception as e:
            send_chunk(task["id"], "\n[处理失败：%s]" % e)
            send_done(task["id"], {})


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("已退出")
