import os

P = r'C:\Users\Lenovo\ai\nanochat-demo\deploy\server_cloud.py'
s = open(P, encoding='utf-8').read()

old = '''            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", 'attachment; filename="%s"' % name)
            self.send_header("X-Accel-Buffering", "no")     # 大文件也不让 nginx 缓冲
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                with open(p, "rb") as f:
                    while True:
                        b = f.read(1 << 20)
                        if not b:
                            break
                        self.wfile.write(b)
            except Exception as e:'''

new = '''            # 支持断点续传（Range 请求）
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
            except Exception as e:'''

if old in s:
    s = s.replace(old, new, 1)
    open(P, 'w', encoding='utf-8').write(s)
    print('已加入断点续传支持')
else:
    print('未匹配到目标代码')

import ast
ast.parse(open(P, encoding='utf-8').read())
print('语法 OK')
