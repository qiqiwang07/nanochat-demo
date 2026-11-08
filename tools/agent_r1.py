"""会动手的 AI 助手（agent 版，确定性流水线）

流程（不依赖模型自主决策，弱模型也能可靠完成）：
    1. 看工作目录，挑出要改的文件
    2. 读原文件内容
    3. 让模型生成修改后的完整内容
    4. 写回文件
    5. 运行验证（.py 用 python，.bat 用 cmd，其它跳过）
    6. 让模型看运行结果，判断是否成功并解释

用法：
    python agent_r1.py [--port 8092] [--workspace <目录>]
"""
import argparse
import json
import os
import re
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LLAMA = "http://127.0.0.1:8080/v1/chat/completions"
WORKSPACE = r"C:\Users\Lenovo\ai\agent-workspace"
CMD_TIMEOUT = 60
MAX_READ = 6000


def llama_chat(messages, max_tokens=600, temperature=0.2) -> str:
    body = {"messages": messages, "max_tokens": max_tokens,
            "temperature": temperature, "top_p": 0.9, "repeat_penalty": 1.05}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(LLAMA, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        j = json.loads(r.read().decode("utf-8"))
    msg = j["choices"][0]["message"]
    txt = (msg.get("content") or "").strip()
    if not txt:
        txt = (msg.get("reasoning_content") or "")
        for mk in ("</think>", "<｜end▁of▁thinking｜>"):
            if mk in txt:
                txt = txt.rsplit(mk, 1)[1]
    for mk in ("</think>", "<｜end▁of▁thinking｜>"):
        if mk in txt:
            txt = txt.rsplit(mk, 1)[1]
    return txt.strip()


def strip_fence(s: str) -> str:
    """从模型输出里只提取代码，丢掉解释文字。"""
    s = s.strip()
    m = re.search(r"```[a-zA-Z0-9]*\n(.*?)```", s, re.S)
    if m:
        return m.group(1).rstrip()
    # 没有代码块：丢掉尾部的中文说明行
    out = []
    for ln in s.splitlines():
        stripped = ln.strip()
        if not stripped:
            out.append(ln)
            continue
        has_cjk = re.search(r"[\u4e00-\u9fff]", stripped)
        is_code = (stripped.startswith(("#", "import ", "from ", "def ", "class ", "@"))
                   or any(t in stripped for t in ("(", ")", "=", ":", '"', "'", "print")))
        if has_cjk and not is_code:
            break                      # 遇到纯中文说明，后面都不要了
        out.append(ln)
    return "\n".join(out).rstrip()


def safe_path(rel: str) -> str:
    root = os.path.abspath(WORKSPACE)
    p = os.path.abspath(os.path.join(root, rel.replace("\\", "/").lstrip("/")))
    if not (p == root or p.startswith(root + os.sep)):
        raise ValueError("路径越界")
    return p


def pick_file(task: str, emit) -> str:
    files = [f for f in sorted(os.listdir(WORKSPACE)) if os.path.isfile(os.path.join(WORKSPACE, f))]
    emit("工作目录里有: %s\n\n" % ", ".join(files[:20]))
    if not files:
        return ""
    # 任务里直接点名文件最可靠
    for f in files:
        if f in task:
            return f
    prompt = ("用户任务：%s\n\n工作目录文件列表：%s\n\n"
              "请只输出要修改的那个文件名，不要输出其他任何内容。" % (task, ", ".join(files)))
    try:
        ans = llama_chat([{"role": "user", "content": prompt}], max_tokens=24)
    except Exception:
        return files[0]
    ans = ans.replace("`", "").strip()
    for f in files:
        if f in ans:
            return f
    return files[0]


def run_verify(fname: str) -> str:
    ext = os.path.splitext(fname)[1].lower()
    if ext == ".py":
        cmd = "python %s" % fname
    elif ext in (".bat", ".cmd"):
        cmd = "cmd /c %s" % fname
    else:
        return "（该文件类型不自动运行）"
    try:
        r = subprocess.run(cmd, shell=True, cwd=WORKSPACE, capture_output=True,
                           timeout=CMD_TIMEOUT, encoding="utf-8", errors="ignore")
        out = (r.stdout or "") + (("\n[stderr] " + r.stderr) if r.stderr else "")
        return "运行 `%s` → 退出码 %d\n%s" % (cmd, r.returncode, out[:2000])
    except subprocess.TimeoutExpired:
        return "运行 `%s` 超时（%d 秒）" % (cmd, CMD_TIMEOUT)
    except Exception as e:
        return "运行失败: %s" % e


def handle_task(task: str, emit) -> None:
    fname = pick_file(task, emit)
    if not fname:
        emit("工作目录是空的，先放一个文件进来。")
        return

    # 读
    path = safe_path(fname)
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            old = f.read()[:MAX_READ]
    except Exception as e:
        emit("读取 %s 失败: %s" % (fname, e))
        return
    emit("▶ 读取 %s（%d 字节）\n" % (fname, len(old.encode('utf-8'))))

    # 改：让模型输出完整新内容
    prompt = ("下面是一个文件的完整内容：\n```\n%s\n```\n\n"
              "任务：%s\n\n"
              "请输出修改后的完整文件内容。只输出文件内容本身，"
              "不要解释，不要加 markdown 代码块标记。" % (old, task))
    emit("▶ 让模型生成修改后的内容…\n")
    try:
        new = strip_fence(llama_chat([{"role": "user", "content": prompt}], max_tokens=1200, temperature=0.2))
    except Exception as e:
        emit("模型调用失败: %s" % e)
        return
    if not new.strip():
        emit("模型没有返回内容，任务中止。")
        return
    if new.strip() == old.strip():
        emit("▶ 模型生成的内容与原文相同，未改动。\n")

    # 写
    backup = path + ".bak"
    try:
        with open(backup, "w", encoding="utf-8") as f:
            f.write(old)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        emit("▶ 已写入 %s（原文件备份为 %s）\n" % (fname, os.path.basename(backup)))
    except Exception as e:
        emit("写入失败: %s" % e)
        return

    # 运行验证
    emit("▶ 运行验证…\n")
    result = run_verify(fname)
    emit("   " + result.replace("\n", "\n   ")[:800] + "\n")
    ok = "退出码 0" in result

    # 判定：成功与否由退出码决定，模型只负责解释
    verdict_prompt = ("文件已按任务修改并运行。任务：%s\n\n运行结果：\n%s\n\n"
                      "运行%s。请用一两句话说明哪里符合要求、哪里可能还有问题，不要贴代码。"
                      % (task, result[:1500], "成功" if ok else "失败"))
    emit("▶ 让模型解释结果…\n\n")
    try:
        verdict = llama_chat([{"role": "user", "content": verdict_prompt}], max_tokens=200, temperature=0.3)
    except Exception as e:
        verdict = "（解释失败：%s）" % e
    for mk in ("</think>",):
        if mk in verdict:
            verdict = verdict.rsplit(mk, 1)[1]

    head = "✅ 已完成并验证通过" if ok else "⚠️ 运行失败（退出码非 0），修改已保留，可继续让我修"
    emit("%s\n\n%s" % (head, verdict.strip()))
    if not ok:
        emit("\n备份文件：%s（如需回滚可直接替换）" % os.path.basename(backup))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, body: bytes, ctype="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/chat.html", "/agent"):
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bin", "chat.html")
            with open(p, "rb") as f:
                self._send(f.read(), "text/html")
        else:
            self._send(b'{"error":"not found"}')

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            body = {}
        if self.path != "/chat":
            self._send(b'{"error":"not found"}')
            return
        text = (body.get("text") or "").strip()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        lock = threading.Lock()

        def emit(s: str):
            with lock:
                self.wfile.write(b"data: " + json.dumps({"delta": s}, ensure_ascii=False).encode() + b"\n\n")
                self.wfile.flush()

        try:
            handle_task(text, emit)
        except Exception as e:
            emit("\n[出错：%s]" % e)
        self.wfile.write(b'data: {"usage":{"in":0,"out":0,"total":0,"model":0}}\n\n')
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True


def main() -> int:
    global WORKSPACE
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8092)
    ap.add_argument("--workspace", default=WORKSPACE)
    args = ap.parse_args()
    WORKSPACE = os.path.abspath(args.workspace)
    os.makedirs(WORKSPACE, exist_ok=True)
    print(f"工作目录: {WORKSPACE}", flush=True)
    print(f"会动手的 AI 已启动: http://127.0.0.1:{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
