"""云端中转服务（部署在服务器上，监听 7000）

分工：
    浏览器  ──►  本服务(7000)  ◄── 长轮询 ──  本地电脑上的 worker（跑 AI）

本服务不跑模型，只负责转发。

启动：
    nohup python3 server_cloud.py > server.log 2>&1 &
"""
import json
import os
import queue
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get("PORT", "7000"))
TOKEN = os.environ.get("RELAY_TOKEN", "wzw7000relay")
BASE = os.path.dirname(os.path.abspath(__file__))

lock = threading.Lock()
tasks = {}              # id -> {"text", "chunks", "done", "usage", "ts"}
pending = queue.Queue()  # 待 worker 处理的任务 id


def new_task(text: str) -> str:
    tid = uuid.uuid4().hex[:12]
    with lock:
        tasks[tid] = {"text": text, "chunks": [], "done": False,
                      "usage": {}, "ts": time.time(), "seen": 0}
    pending.put(tid)
    return tid


def cleanup() -> None:
    now = time.time()
    with lock:
        for k in [k for k, v in tasks.items() if now - v["ts"] > 900]:
            tasks.pop(k, None)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (time.strftime("%H:%M:%S"), fmt % args), flush=True)

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _page(self, name):
        p = os.path.join(BASE, name)
        try:
            with open(p, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            self._page("chat_cloud.html")
        elif u.path == "/health":
            self._json({"ok": True, "tasks": len(tasks), "workers_waiting": 0})
        elif u.path == "/worker/poll":
            if (q.get("token") or [""])[0] != TOKEN:
                self._json({"error": "bad token"}, 403)
                return
            cleanup()
            try:
                tid = pending.get(timeout=25)
            except queue.Empty:
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            with lock:
                t = tasks.get(tid)
            if not t:
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self._json({"id": tid, "text": t["text"]})
        elif u.path.startswith("/dl/"):
            name = os.path.basename(u.path[4:])
            p = os.path.join(BASE, "dist", name)
            if not name or not os.path.exists(p) or not os.path.isfile(p):
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            size = os.path.getsize(p)
            ctype = "application/octet-stream"
            if name.endswith(".ps1"):
                ctype = "text/plain; charset=utf-8"
            elif name.endswith(".json"):
                ctype = "application/json; charset=utf-8"
            elif name.endswith(".txt") or name.endswith(".bat"):
                ctype = "text/plain; charset=utf-8"
            # 支持断点续传（Range 请求）
            start, end, status = 0, size - 1, 200
            rng = self.headers.get("Range")
            if rng and rng.startswith("bytes="):
                try:
                    spec = rng[6:].split(",")[0]
                    a, _, b = spec.partition("-")
                    start = int(a) if a.strip() else 0
                    end = int(b) if b.strip() else size - 1
                    if start >= size:
                        start = 0
                    if end >= size or end < start:
                        end = size - 1
                    status = 206
                except Exception:
                    start, end, status = 0, size - 1, 200
            length = end - start + 1

            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            if status == 206:
                self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % name)
            self.send_header("X-Accel-Buffering", "no")     # 大文件也不让 nginx 缓冲
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                with open(p, "rb") as f:
                    f.seek(start)
                    remain = length
                    while remain > 0:
                        b = f.read(min(1 << 20, remain))
                        if not b:
                            break
                        self.wfile.write(b)
                        remain -= len(b)
            except Exception as e:
                print("send file error:", e, flush=True)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            body = {}

        if u.path == "/chat":
            text = (body.get("text") or "").strip()
            if not text:
                self._json({"error": "empty"}, 400)
                return
            tid = new_task(text)
            # SSE 转发
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")     # 关键：让 nginx 不缓冲流式输出
            self.send_header("Connection", "close")
            self.end_headers()
            deadline = time.time() + 240
            sent = 0
            try:
                while time.time() < deadline:
                    with lock:
                        t = tasks.get(tid)
                        if not t:
                            break
                        chunks = t["chunks"][sent:]
                        sent = len(t["chunks"])
                        done = t["done"]
                        usage = t["usage"]
                    for c in chunks:
                        self.wfile.write(b"data: " + json.dumps({"delta": c}, ensure_ascii=False).encode() + b"\n\n")
                        self.wfile.flush()
                    if done:
                        self.wfile.write(b"data: " + json.dumps({"usage": usage}, ensure_ascii=False).encode() + b"\n\n")
                        break
                    if time.time() > deadline - 200 and not chunks:
                        # 长时间没有 worker 响应
                        pass
                    time.sleep(0.08)
                if time.time() >= deadline:
                    msg = json.dumps({"delta": "\n[超时：本地电脑没有响应，请确认 worker 在运行]"},
                                     ensure_ascii=False).encode("utf-8")
                    self.wfile.write(b"data: " + msg + b"\n\n")
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except Exception as e:
                print("stream error:", e, flush=True)
            self.close_connection = True
            return

        if u.path == "/worker/chunk":
            if (body.get("token") or "") != TOKEN:
                self._json({"error": "bad token"}, 403)
                return
            with lock:
                t = tasks.get(body.get("id"))
                if t:
                    t["chunks"].append(body.get("delta") or "")
            self._json({"ok": True})
            return

        if u.path == "/worker/done":
            if (body.get("token") or "") != TOKEN:
                self._json({"error": "bad token"}, 403)
                return
            with lock:
                t = tasks.get(body.get("id"))
                if t:
                    t["done"] = True
                    t["usage"] = body.get("usage") or {}
            self._json({"ok": True})
            return

        self._json({"error": "not found"}, 404)


def main() -> None:
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("relay server on 0.0.0.0:%d" % PORT, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
