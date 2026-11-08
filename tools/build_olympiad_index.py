"""把 2017 道奥数题建成检索索引（题目 + 标准解答成对保存）。

输出：data/olympiad_index.json
"""
import json
import os

import pandas as pd

DATA = r'C:\Users\Lenovo\ai\nanochat-demo\data'
OUT = os.path.join(DATA, 'olympiad_index.json')


def unescape(s: str) -> str:
    import re
    s = str(s).replace('\\r\\n', '\n')
    s = re.sub(r'\\n(?![A-Za-z])', '\n', s)
    s = re.sub(r'\\t(?![A-Za-z])', ' ', s)
    return s


df = pd.read_parquet(os.path.join(DATA, 'math_hard_zh.parquet'))
items = []
for _, row in df.iterrows():
    q = a = ''
    for m in row['messages']:
        if not isinstance(m, dict):
            continue
        if m.get('role') == 'user':
            q = m.get('content', '')
        elif m.get('role') == 'assistant':
            a = m.get('content', '')
    if not q or not a:
        continue
    a = unescape(a).strip()
    q = unescape(q).strip()
    if '[asy]' in a:          # 跳过带图形代码的
        continue
    items.append({'q': q, 'a': a})

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(items, f, ensure_ascii=False)

print('索引条目: %d 道' % len(items))
print('文件大小: %.2f MB' % (os.path.getsize(OUT) / 1e6))
print('样例题目:', items[0]['q'][:80])
print('样例解答长度:', len(items[0]['a']), '字符')
