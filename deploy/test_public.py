"""通过公网 nginx 测试：问一道奥数题 + 检查下载入口。"""
import json
import time
import urllib.request

BASE = 'http://1.117.113.68/'
HOST = 'c-learning.oprfin.com'


def stream_chat(q, timeout=900):
    body = json.dumps({'text': q, 'session': ''}, ensure_ascii=False).encode()
    req = urllib.request.Request(BASE + 'chat', data=body, headers={
        'Content-Type': 'application/json', 'Host': HOST})
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


print('=== 公网测试 1：奥数题 ===')
q = '计算最小的正整数 n，使得 sum_{k=0}^{n} log2(1 + 1/2^(2^k)) >= 1 + log2(2014/2015)'
ans, first, total, usage, refs = stream_chat(q)
print('首字 %.1fs / 总 %.1fs / 相似题 %s / token %s' % (first or -1, total, refs, usage))
print('答案结尾:', ans.strip()[-200:].replace('\n', ' '))

print()
print('=== 公网测试 2：普通问题 ===')
ans2, first2, total2, usage2, _ = stream_chat('什么是特征值？一句话说明')
print('首字 %.1fs / 总 %.1fs / token %s' % (first2 or -1, total2, usage2))
print('答案:', ans2.strip()[:200].replace('\n', ' '))

print()
print('=== 下载入口检查 ===')
for f in ('i.ps1', 'ai.zip'):
    try:
        req = urllib.request.Request(BASE + 'dl/' + f, headers={'Host': HOST})
        with urllib.request.urlopen(req, timeout=30) as r:
            n = len(r.read(2048))
            print('  /dl/%s → HTTP %d, 长度 %s MB, 读取 %d 字节' % (
                f, r.status, round((r.headers.get('Content-Length') or 0) / 1e6, 1), n))
    except Exception as e:
        print('  /dl/%s → 失败: %s' % (f, e))
