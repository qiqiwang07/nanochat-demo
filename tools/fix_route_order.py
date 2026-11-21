# -*- coding: utf-8 -*-
"""把题型判定与系统提示前移到构造 msgs 之前，修复 UnboundLocalError。"""
import ast
import io
import re

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

# 1) 摘出当前的 route 判定块
m = re.search(r'[ \t]*route = classify\(text\).*?\+ msgs\n', t, re.S)
assert m, '找不到 route 判定块'
block = m.group(0)
t = t[:m.start()] + t[m.end():]

# 2) 调整缩进与内容：判定放在 msgs 之前，系统提示也一起
new_block = '''            route = classify(text) if BACKEND != "nanogpt" else "think"  # 题型：calc/lookup/think

'''
# 提取原来的系统提示部分（如果有）
sys_part = ''
if '你是简洁的中文助手' in block:
    sm = re.search(r'[ \t]*msgs = \[\{"role": "system".*?\+ msgs\n', block, re.S)
    if sm:
        sys_part = sm.group(0)

# 3) 插到 msgs = list(...) 之前
anchor = '            msgs = list(s["messages"])  # 复制一份对话历史，避免改动原始记录'
assert anchor in t, '找不到 msgs 构造行'
t = t.replace(anchor, new_block + sys_part + anchor, 1)

ast.parse(t)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('route 已前移；系统提示存在:', bool(sys_part))
