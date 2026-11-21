# -*- coding: utf-8 -*-
"""检索直出改为返回"命中关键词的那一整段"，而不是固定宽度的窗口。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

OLD = '''        # 以命中位置为中心，向左右各取一段，再按句子边界收尾
        left = max(0, pos - 160)
        right = min(len(h), pos + 260)
        body = h[left:right].strip()
        cut = max(body.rfind('。'), body.rfind('\\n'))
        if cut > 60:
            body = body[:cut + 1]                 # 截到完整句子
        return '【知识库检索】\\n' + body'''

NEW = '''        # 优先返回包含关键词的那一整段（段落比固定窗口更完整、更连贯）
        best_para = ''
        for para in h.split('\\n'):               # 按行切成段落
            para = para.strip()
            if not para:
                continue
            for term in terms:                    # 这段里含关键词就用它
                if term in para and len(para) > len(best_para):
                    best_para = para
                    break
        if best_para:
            if len(best_para) > 400:              # 太长就按句号截断
                cut = best_para.rfind('。', 0, 400)
                best_para = best_para[:cut + 1] if cut > 80 else best_para[:400]
            return '【知识库检索】\\n' + best_para

        # 没有完整段落时退回窗口截取
        left = max(0, pos - 120)
        right = min(len(h), pos + 280)
        body = h[left:right].strip()
        cut = max(body.rfind('。'), body.rfind('\\n'))
        if cut > 60:
            body = body[:cut + 1]
        return '【知识库检索】\\n' + body'''

assert OLD in t, '未匹配窗口截取段'
t = t.replace(OLD, NEW, 1)
ast.parse(t)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已改为按段落返回')
