"""测试 7B 模型的速度和回答质量。"""
import json
import time
import urllib.request

URL = 'http://127.0.0.1:8080/v1/chat/completions'


def ask(q, max_tokens=600):
    body = {
        'messages': [{'role': 'user', 'content': q}],
        'max_tokens': max_tokens,
        'temperature': 0.7,
        'top_p': 0.9,
    }
    req = urllib.request.Request(URL,
                                 data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        j = json.loads(r.read().decode())
    dt = time.time() - t0
    u = j.get('usage', {})
    ct = u.get('completion_tokens', 0)
    msg = j['choices'][0]['message']
    text = (msg.get('content') or '').strip()
    return text, ct, dt, (ct / dt if dt else 0)


tests = [
    ('什么是正交矩阵？', 500),
    ('用 Python 写一个快速排序，并解释时间复杂度', 700),
    ('解释一下为什么天空是蓝色的', 500),
]

for q, mt in tests:
    text, ct, dt, sp = ask(q, mt)
    print('=' * 70)
    print('问：%s' % q)
    print('速度：%d token / %.1fs = %.1f token/秒' % (ct, dt, sp))
    print('-' * 70)
    print(text[:1200])
    print()
