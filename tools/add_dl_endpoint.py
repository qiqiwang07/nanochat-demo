"""给 serve_r1.py 加上 /dl/ 下载分发（替代原来的中转服务），并生成服务器版。"""
import ast
import os

INST = os.path.join(os.environ['USERPROFILE'], 'AI助手')
SRC = os.path.join(INST, 'serve_r1.py')
s = open(SRC, encoding='utf-8').read()

if 'u.path.startswith("/dl/")' in s:
    print('已有 /dl/ 处理')
else:
    old = '''        if u.path == "/health":
            self._send(json.dumps({"ok": True}).encode())'''
    new = '''        if u.path == "/health":
            self._send(json.dumps({"ok": True}).encode())
        elif u.path.startswith("/dl/"):
            self._serve_file(u.path[4:])'''
    if old in s:
        s = s.replace(old, new, 1)
        print('已挂接 /dl/ 路由')
    else:
        print('未匹配 /health 路由')
        for i, l in enumerate(s.split('\n'), 1):
            if '/health' in l:
                print(i, repr(l))

    # 加入文件分发方法（支持 Range 断点续传）
    helper = '''
    def _serve_file(self, name: str) -> None:
        """分发安装包等文件，支持 Range 断点续传。"""
        import os as _os
        base = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "dist")
        p = _os.path.join(base, _os.path.basename(name))
        if not _os.path.isfile(p):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        size = _os.path.getsize(p)
        ctype = "application/octet-stream"
        low = name.lower()
        if low.endswith(".ps1") or low.endswith(".txt") or low.endswith(".bat"):
            ctype = "text/plain; charset=utf-8"
        elif low.endswith(".json"):
            ctype = "application/json; charset=utf-8"
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
        self.send_header("Content-Disposition", 'attachment; filename="%s"' % _os.path.basename(p))
        self.send_header("X-Accel-Buffering", "no")
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

    def do_POST(self):'''
    if 'def do_POST(self):' in s and '_serve_file' not in s:
        s = s.replace('\n    def do_POST(self):', helper, 1)
        print('已加入 _serve_file 方法')

ast.parse(s)
open(SRC, 'w', encoding='utf-8').write(s)
print('serve_r1.py 更新完成（含 /dl/ 分发）')
