"""让网页服务监听所有网卡（0.0.0.0），这样可以用 IP:端口 直接访问。"""
import ast
import os

INST = os.path.join(os.environ['USERPROFILE'], 'AI助手')
p = os.path.join(INST, 'serve_r1.py')
s = open(p, encoding='utf-8').read()

# 1) 增加 --bind 参数
if '"--bind"' not in s:
    s = s.replace(
        '    ap.add_argument("--port", type=int, default=8091)',
        '    ap.add_argument("--port", type=int, default=8091)\n'
        '    ap.add_argument("--bind", default="0.0.0.0", help="监听地址，0.0.0.0 表示允许外部访问")')
    print('已加 --bind 参数')

# 2) 用 args.bind 绑定
s = s.replace(
    'srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)',
    'srv = ThreadingHTTPServer((args.bind, args.port), Handler)')
s = s.replace(
    'print(f"AI 服务已启动: http://127.0.0.1:{args.port}  (后端 {LLAMA})", flush=True)',
    'print(f"AI 服务已启动: http://{args.bind}:{args.port}  (后端 {LLAMA})", flush=True)')

ast.parse(s)
open(p, 'w', encoding='utf-8').write(s)
print('serve_r1.py 已支持 --bind')

# 确认
for i, line in enumerate(open(p, encoding='utf-8'), 1):
    if 'args.bind' in line:
        print(i, line.strip())
