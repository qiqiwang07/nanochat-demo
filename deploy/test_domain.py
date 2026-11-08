"""通过域名完整测试：普通问题 + 奥数题 + 下载入口。"""
import json
import time
import urllib.request

BASE = 'http://c-learning.oprfin.com/'


def stream_chat(q, timeout=900):
    body = json.dumps({'text': q, 'session': ''}, ensure_ascii=False).encode()
    req = urllib.request.Request(BASE + 'chat', data=body,
                                 headers={'Content-Type': 'application/json'})
    t0 = time.time()
    acc, first, usage, refs = '', None, {}, None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode('utf-8', 'ignore').strip()
            if not line.startswith('data:'):
                continue
            p = line[5:].strip()
            if p == '[DONE]':
                break
            try:
                j = json.loads(p)
            except Exception:
                continue
            if j.get('delta'):
                if first is None:
                    first = time.time() - t0
                acc += j['delta']
            if j.get('usage'):
                usage = j['usage']
            if 'refs' in j:
                refs = j['refs']
    return acc, first, time.time() - t0, usage, refs


print('=== 测试 1：普通问题 ===')
ans, first, total, usage, _ = stream_chat('什么是正交矩阵？一句话说明')
print('首字 %.1fs / 总 %.1fs / token %s' % (first or -1, total, usage))
print('回答:', ans.strip()[:220])

print()
print('=== 测试 2：奥数题 ===')
q = '求所有正整数 n，使得 n^3 + 1 能被 n + 1 整除'
ans2, first2, total2, usage2, refs2 = stream_chat(q)
print('首字 %.1fs / 总 %.1fs / 相似题 %s / token %s' % (first2 or -1, total2, refs2, usage2))
print('回答摘要:', ans2.strip()[:300].replace('\n', ' '))
print('...结尾:', ans2.strip()[-250:].replace('\n', ' '))

print()
print('=== 测试 3：下载入口 ===')
for f in ('i.ps1', 'ai.zip'):
    try:
        req = urllib.request.Request(BASE + 'dl/' + f)
        with urllib.request.urlopen(req, timeout=30) as r:
            n = len(r.read(2048))
            print('  /dl/%-8s → HTTP %d, %s MB, 读取 %d 字节' % (
                f, r.status, round((r.headers.get('Content-Length') or 0) / 1e6, 1), n))
    except Exception as e:
        print('  /dl/%-8s → 失败: %s' % (f, e))
