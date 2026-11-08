import ast
import os
import re

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
s = open(P, encoding='utf-8').read()

# refs 字段改为使用 ref_count
s2 = s.replace('"refs": len(hits),', '"refs": ref_count,')
if s2 != s:
    s = s2
    print('refs 已改为 ref_count')
else:
    print('refs 未找到，检查实际写法')
    for i, line in enumerate(s.split('\n'), 1):
        if 'refs' in line:
            print(i, line.strip())

ast.parse(s)
print('语法 OK')
open(P, 'w', encoding='utf-8').write(s)

# 同时同步到安装目录（用户实际运行的那份）
inst = os.path.join(os.environ['USERPROFILE'], 'AI助手')
if os.path.isdir(inst):
    open(os.path.join(inst, 'serve_r1.py'), 'w', encoding='utf-8').write(s)
    print('已同步到安装目录')
