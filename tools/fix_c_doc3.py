# -*- coding: utf-8 -*-
"""说明提取精修：排除"行尾注释"和"分区标题"，只保留真正的函数说明。"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\gen_call_graph.py'
t = io.open(P, encoding='utf-8').read()

OLD = '''    j = src.rfind('/*', 0, i)                    # 找对应的注释开头
    if j < 0:
        return ''
    return src[j + 2:i - 1]                      # 去掉 /* 与 */'''

NEW = '''    j = src.rfind('/*', 0, i)                    # 找对应的注释开头
    if j < 0:
        return ''
    # 只认"独占一行"的注释；同一行前面还有代码的，是给上一句代码写的行尾注释
    line_start = src.rfind('\\n', 0, j) + 1
    if src[line_start:j].strip():
        return ''
    return src[j + 2:i - 1]                      # 去掉 /* 与 */'''

assert OLD in t, '未匹配 prev_comment'
t = t.replace(OLD, NEW, 1)

# 分区标题（一堆横线加标题）不算说明
OLD2 = '''        if doc and set(doc) <= set('-= '):      # 纯横线的分区标题，不算说明
            doc = \'\''''
NEW2 = '''        if doc and (set(doc) <= set('-= ') or doc.startswith('---')):
            doc = ''      # 纯横线的分区标题，不算说明'''
assert OLD2 in t, '未匹配分区标题过滤'
t = t.replace(OLD2, NEW2, 1)

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已精修')
