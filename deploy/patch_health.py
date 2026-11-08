import os

STAGE = r'C:\Users\Lenovo\ai\nanochat-demo\deploy\stage'

# serve_r1.py：在 do_GET 里加 /health
p = os.path.join(STAGE, 'serve_r1.py')
s = open(p, encoding='utf-8').read()
old = '        if u.path in ("/", "/chat.html"):'
new = ('        if u.path == "/health":\n'
       '            self._send(json.dumps({"ok": True}).encode())\n'
       '        elif u.path in ("/", "/chat.html"):')
if old in s:
    s = s.replace(old, new, 1)
    open(p, 'w', encoding='utf-8').write(s)
    print('serve_r1.py 已加 /health')
else:
    print('serve_r1.py 未找到模式')

# agent_r1.py：同样加 /health
p = os.path.join(STAGE, 'agent_r1.py')
s = open(p, encoding='utf-8').read()
old = '        if self.path in ("/", "/chat.html", "/agent"):'
new = ('        if self.path == "/health":\n'
       '            self._send(json.dumps({"ok": True}).encode())\n'
       '        elif self.path in ("/", "/chat.html", "/agent"):')
if old in s:
    s = s.replace(old, new, 1)
    open(p, 'w', encoding='utf-8').write(s)
    print('agent_r1.py 已加 /health')
else:
    print('agent_r1.py 未找到模式')

# 语法检查
import ast
for f in ('serve_r1.py', 'agent_r1.py', 'worker.py', 'ai.ps1'):
    path = os.path.join(STAGE, f)
    if f.endswith('.py'):
        try:
            ast.parse(open(path, encoding='utf-8').read())
            print(f, 'OK')
        except SyntaxError as e:
            print(f, '语法错误:', e)
