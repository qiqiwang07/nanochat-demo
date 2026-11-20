# -*- coding: utf-8 -*-
"""C 函数说明的兜底：函数上方没注释时，取函数体第一段注释。"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\gen_call_graph.py'
t = io.open(P, encoding='utf-8').read()

OLD = '''        # 取紧邻函数上方的那段注释；中间夹着代码就不算（避免抓到上个函数体内的注释）
        doc = first_sentence(prev_comment(src, m.start()))
        if doc and set(doc) <= set('-= '):      # 纯横线的分区标题，不算说明
            doc = \'\''''

NEW = '''        # 取紧邻函数上方的那段注释；中间夹着代码就不算（避免抓到上个函数体内的注释）
        doc = first_sentence(prev_comment(src, m.start()))
        if doc and set(doc) <= set('-= '):      # 纯横线的分区标题，不算说明
            doc = ''
        if not doc:
            # 兜底：很多 C 函数把说明写在函数体第一行，这时取函数体里的第一段注释
            inner = re.search(r'/\\*(.*?)\\*/', src[m.end():m.end() + 400], re.S)
            if inner:
                doc = first_sentence(inner.group(1))'''

assert OLD in t, '未匹配'
t = t.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已加入兜底逻辑')
