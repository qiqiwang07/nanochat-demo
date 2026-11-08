"""把奥数题库整理成训练语料（UTF-8 纯文本，模型直接吃的格式）。

来源：
  math_hard_zh.parquet   2209 道奥数级难题（中文题干 + 逐步解答）
  math_zh_1m.json        100 万条基础题（### Human / ### Assistant 格式）

输出：
  olympiad_corpus.txt
"""
import json
import os

import pandas as pd

DATA = r'C:\Users\Lenovo\ai\nanochat-demo\data'
OUT = os.path.join(DATA, 'olympiad_corpus.txt')
MAX_BASIC = 40000          # 基础题最多取多少条
MAX_CHARS = 8_000_000      # 语料总上限（字符）

def norm(s: str) -> str:
    s = str(s).replace('\r\n', '\n').strip()
    # 压掉多余空行
    while '\n\n\n' in s:
        s = s.replace('\n\n\n', '\n\n')
    return s

written = 0
n_items = 0

with open(OUT, 'w', encoding='utf-8') as out:
    # ---------- 1) 奥数级难题：全部收进来 ----------
    hard = pd.read_parquet(os.path.join(DATA, 'math_hard_zh.parquet'))
    n_hard = 0
    for _, row in hard.iterrows():
        msgs = row['messages']
        q = a = ''
        for m in msgs:
            role = m.get('role') if isinstance(m, dict) else None
            content = m.get('content') if isinstance(m, dict) else ''
            if role == 'user':
                q = content
            elif role == 'assistant':
                a = content
        if not q or not a:
            continue
        block = "### 题目：%s\n### 解答：%s\n\n" % (norm(q), norm(a))
        out.write(block)
        written += len(block)
        n_items += 1
        n_hard += 1
    print('奥数难题: %d 条, %.1f 万字符' % (n_hard, written / 1e4), flush=True)

    # ---------- 2) 基础题：抽样补充（偏应用题，跳过纯方程）----------
    basic = 0
    with open(os.path.join(DATA, 'math_zh_1m.json'), encoding='utf-8') as f:
        for i, line in enumerate(f):
            if basic >= MAX_BASIC or written >= MAX_CHARS:
                break
            if i % 7 != 0:                     # 抽样
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            text = obj.get('text') or ''
            if '解方程' in text or '计算 ' in text:
                continue                        # 太机械的算式不要
            if '### Human: ' not in text or '### Assistant: ' not in text:
                continue
            head, _, tail = text.partition('### Assistant: ')
            q = head.replace('### Human: ', '').strip()
            a = tail.strip()
            if len(q) < 8 or not a:
                continue
            block = "### 题目：%s\n### 解答：%s\n\n" % (norm(q), norm(a))
            out.write(block)
            written += len(block)
            basic += 1
            n_items += 1
    print('基础题: %d 条, 累计 %.1f 万字符' % (basic, written / 1e4), flush=True)

print('总共 %d 条, %.2f MB' % (n_items, written / 1e6), flush=True)
print('输出:', OUT)
