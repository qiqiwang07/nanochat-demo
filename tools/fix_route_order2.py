# -*- coding: utf-8 -*-
"""按行精确移动 route 判定与系统提示到 msgs 构造之前。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
lines = io.open(P, encoding='utf-8').read().split('\n')

def find(pred, start=0):
    """返回第一处满足条件的行号。"""
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i
    return -1

# 定位
i_msgs = find(lambda s: 'msgs = list(s["messages"])' in s)
i_route = find(lambda s: s.strip().startswith('route = classify(text)'))
i_sys = find(lambda s: s.strip().startswith('if route == \'think\' and BACKEND != "nanogpt"'))
assert i_msgs > 0 and i_route > 0 and i_sys > 0, (i_msgs, i_route, i_sys)

# 取出 route 行（单行）
route_line = lines[i_route]
del lines[i_route]
if i_sys > i_route:
    i_sys -= 1

# 取出系统提示块：从 i_sys 起，直到包含 '+ msgs' 的行
j = i_sys
while j < len(lines) and '+ msgs' not in lines[j]:
    j += 1
sys_block = lines[i_sys:j + 1]
del lines[i_sys:j + 1]

# 重新定位 msgs 行并插入
i_msgs = find(lambda s: 'msgs = list(s["messages"])' in s)
assert i_msgs > 0
indent = ' ' * (len(lines[i_msgs]) - len(lines[i_msgs].lstrip()))
insert = [indent + route_line.strip(), ''] + sys_block + ['']
lines = lines[:i_msgs] + insert + lines[i_msgs:]

out = '\n'.join(lines)
ast.parse(out)
io.open(P, 'w', encoding='utf-8', newline='\n').write(out)
print('已移动：route 与系统提示置于 msgs 之前')
