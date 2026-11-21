# -*- coding: utf-8 -*-
"""改进检索直出：必须真的包含问题里的关键词，并且以命中位置为中心截取。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

OLD_START = 'def lookup_answer(text: str) -> str:'
OLD_END = "    return '【知识库检索】\\n' + body                             # 标明来源是检索而非生成"

i = t.find(OLD_START)
j = t.find(OLD_END)
assert i > 0 and j > i, '找不到 lookup_answer'

NEW = '''def key_terms(text: str) -> list:
    """从问题里抽出实词片段，用于校验检索结果是否真的相关。

    做法：去掉常见疑问词与虚词，剩下连续的中文片段就是关键词候选。
    """
    s = text
    for w in ('什么是', '什么叫', '是什么', '请问', '解释一下', '简单说明', '一句话',
              '的作者是谁', '的作者', '是谁', '多少', '有哪些', '都有谁', '怎么样',
              '的', '是', '请', '吗', '呢', '？', '?', '。'):
        s = s.replace(w, ' ')                     # 疑问词和虚词替换成空格，起到切分作用
    out = []
    for seg in s.split():                         # 切出来的片段
        seg = seg.strip('《》「」“”"\\'()（）')
        if len(seg) >= 2:                         # 至少两个字才算关键词
            out.append(seg)
    return out


def lookup_answer(text: str) -> str:
    """从知识库挑一段原文作为回答；要求真的包含关键词，否则返回空交给模型。"""
    terms = key_terms(text)                       # 关键词
    if not terms:
        return ''
    hits = retrieve(text, 3)                      # 取前 3 段候选
    for h in hits:
        pos = -1
        for term in terms:                        # 找任一关键词在原文里的位置
            pos = h.find(term)
            if pos >= 0:
                break
        if pos < 0:                               # 这段没命中任何关键词，换下一段
            continue
        # 以命中位置为中心，向左右各取一段，再按句子边界收尾
        left = max(0, pos - 160)
        right = min(len(h), pos + 260)
        body = h[left:right].strip()
        cut = max(body.rfind('。'), body.rfind('\\n'))
        if cut > 60:
            body = body[:cut + 1]                 # 截到完整句子
        return '【知识库检索】\\n' + body
    return ''                                     # 全都没命中，交给模型回答
'''

t = t[:i] + NEW + t[j + len(OLD_END):]
ast.parse(t)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('检索直出已加关键词校验')
