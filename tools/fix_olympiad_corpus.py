"""把奥数语料里的字面量换行符转成真正的换行，并过滤掉图形代码。"""
import json
import os
import re

import pandas as pd

DATA = r'C:\Users\Lenovo\ai\nanochat-demo\data'
OUT = os.path.join(DATA, 'olympiad_corpus.txt')


def unescape(s: str) -> str:
    # 只把真正代表换行的 \n 换成换行；\nabla、\neq、\times 这类 LaTeX 命令不能动
    s = str(s).replace('\\r\\n', '\n')
    s = re.sub(r'\\n(?![A-Za-z])', '\n', s)
    s = re.sub(r'\\t(?![A-Za-z])', ' ', s)
    return s


hard = pd.read_parquet(os.path.join(DATA, 'math_hard_zh.parquet'))
written = 0
n_hard = 0
skipped = 0

with open(OUT, 'w', encoding='utf-8') as out:
    for _, row in hard.iterrows():
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
        a = unescape(a)
        q = unescape(q)
        if '[asy]' in a:
            skipped += 1
            continue
        block = '### 题目：%s\n### 解答：%s\n\n' % (q.strip(), a.strip())
        out.write(block)
        written += len(block)
        n_hard += 1

    basic = 0
    with open(os.path.join(DATA, 'math_zh_1m.json'), encoding='utf-8') as f:
        for i, line in enumerate(f):
            if basic >= 30000 or written >= 7_000_000:
                break
            if i % 9 != 0:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            t = obj.get('text', '')
            if '解方程' in t or '计算 ' in t:
                continue
            if '### Human: ' not in t or '### Assistant: ' not in t:
                continue
            head, _, tail = t.partition('### Assistant: ')
            q2 = head.replace('### Human: ', '').strip()
            a2 = tail.strip()
            if len(q2) < 8 or not a2:
                continue
            block = '### 题目：%s\n### 解答：%s\n\n' % (q2, a2)
            out.write(block)
            written += len(block)
            basic += 1

print('奥数题 %d 条（跳过图形题 %d），基础题 %d 条' % (n_hard, skipped, basic))
print('语料大小 %.2f MB' % (os.path.getsize(OUT) / 1e6))
