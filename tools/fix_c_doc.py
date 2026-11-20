# -*- coding: utf-8 -*-
"""修正 C 函数说明的提取：只取紧贴函数定义上方的那段注释。"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\gen_call_graph.py'
t = io.open(P, encoding='utf-8').read()

HELPER = '''def prev_comment(src, pos):
    """返回紧贴 pos 之前的那段 /* */ 注释内容；中间若有代码则返回空串。

    为什么不能取"前 600 字里最后一段注释"：那样会抓到上一个函数体内部的注释，
    导致说明张冠李戴（比如 xrand 显示成别的函数的注释）。
    """
    i = pos - 1
    while i >= 0 and src[i] in ' \\t\\r\\n':      # 跳过空白
        i -= 1
    if i < 1 or src[i - 1:i + 1] != '*/':       # 前面不是注释结尾
        return ''
    j = src.rfind('/*', 0, i)                    # 找对应的注释开头
    if j < 0:
        return ''
    return src[j + 2:i - 1]                      # 去掉 /* 与 */


def parse_c(path):'''

OLD_DOC = '''        # 取函数定义前的最后一段注释作为说明
        head = src[max(0, m.start() - 600):m.start()]
        cm2 = list(re.finditer(r'/\\*(.*?)\\*/', head, re.S))
        doc = first_sentence(cm2[-1].group(1)) if cm2 else \'\''''

NEW_DOC = '''        # 取紧邻函数上方的那段注释；中间夹着代码就不算（避免抓到上个函数体内的注释）
        doc = first_sentence(prev_comment(src, m.start()))'''

changed = 0
if OLD_DOC in t:
    t = t.replace(OLD_DOC, NEW_DOC, 1)
    changed += 1
else:
    print('说明提取段未匹配')

if 'def prev_comment(' not in t:
    t = t.replace('def parse_c(path):', HELPER, 1)
    changed += 1
else:
    print('helper 已存在')

# 分区标题这类"注释"不是说明，过滤掉
t = t.replace(
    "        doc = first_sentence(prev_comment(src, m.start()))",
    "        doc = first_sentence(prev_comment(src, m.start()))\n"
    "        if doc and set(doc) <= set('-= '):      # 纯横线的分区标题，不算说明\n"
    "            doc = ''", 1)

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已修改 %d 处' % changed)
