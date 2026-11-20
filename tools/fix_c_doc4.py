# -*- coding: utf-8 -*-
"""去掉函数体内的兜底注释提取：宁可显示"无说明"，也不能显示错的说明。"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\gen_call_graph.py'
t = io.open(P, encoding='utf-8').read()

OLD = '''        if not doc:
            # 兜底：很多 C 函数把说明写在函数体第一行，这时取函数体里的第一段注释
            inner = re.search(r'/\\*(.*?)\\*/', src[m.end():m.end() + 400], re.S)
            if inner:
                doc = first_sentence(inner.group(1))'''

NEW = '''        # 不做"取函数体内第一条注释"的兜底：实测会张冠李戴（取到别的函数的注释），
        # 宁可显示"无说明"，也不能显示错的说明。'''

assert OLD in t, '未匹配兜底段'
t = t.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已移除兜底')
