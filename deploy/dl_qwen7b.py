"""在服务器上下载 Qwen2.5-7B-Instruct Q4_K_M（分片，多线程并发）。"""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('1.117.113.68', 22, 'qiqiwang', 'wzw0702', timeout=25)

script = r'''
import os, threading, time, urllib.request

REPO = 'Qwen/Qwen2.5-7B-Instruct-GGUF'
PARTS = ['qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf',
         'qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf']
DEST = '/home/qiqiwang/models'
UA = {'User-Agent': 'Mozilla/5.0'}
NTHREAD = 6

os.makedirs(DEST, exist_ok=True)

for part in PARTS:
    out = os.path.join(DEST, part)
    url = 'https://hf-mirror.com/%s/resolve/main/%s' % (REPO, part)
    req = urllib.request.Request(url, headers=dict(UA, Range='bytes=0-0'))
    with urllib.request.urlopen(req, timeout=120) as r:
        total = int(r.headers['Content-Range'].split('/')[1])
    if os.path.exists(out) and os.path.getsize(out) == total:
        print('%s 已完整 (%.0f MB)' % (part, total / 1e6), flush=True)
        continue
    # 断点续传
    have = os.path.getsize(out) if os.path.exists(out) else 0
    if have >= total:
        have = 0
    if not os.path.exists(out):
        open(out, 'wb').close()
    print('%s 总 %.0f MB，已下载 %.0f MB' % (part, total / 1e6, have / 1e6), flush=True)

    rest = total - have
    step = rest // NTHREAD + 1
    segs = [(have + i * step, min(total - 1, have + (i + 1) * step - 1)) for i in range(NTHREAD)]
    segs = [(a, b) for a, b in segs if a <= b]
    done = [0]
    lock = threading.Lock()

    def worker(a, b):
        try:
            rq = urllib.request.Request(url, headers=dict(UA, Range='bytes=%d-%d' % (a, b)))
            with urllib.request.urlopen(rq, timeout=1800) as resp, open(out, 'r+b') as f:
                f.seek(a)
                pos = a
                while pos <= b:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    pos += len(chunk)
                    with lock:
                        done[0] += len(chunk)
        except Exception as e:
            print('  分片出错 %d-%d: %s' % (a, b, e), flush=True)

    th = [threading.Thread(target=worker, args=s) for s in segs]
    t0 = time.time()
    for t in th:
        t.start()
    for t in th:
        t.join()
    dt = time.time() - t0
    size = os.path.getsize(out)
    print('%s 完成 %.0f MB / %.0fs (%.1f MB/s)' % (part, size / 1e6, dt, size / 1e6 / max(dt, 1)), flush=True)

    if size != total:
        print('  !! 大小不符: %d vs %d' % (size, total), flush=True)

# 合并
merged = os.path.join(DEST, 'qwen7b.gguf')
if not os.path.exists(merged) or os.path.getsize(merged) < 4e9:
    print('合并分片...', flush=True)
    with open(merged, 'wb') as w:
        for part in PARTS:
            p = os.path.join(DEST, part)
            with open(p, 'rb') as r:
                while True:
                    b = r.read(8 << 20)
                    if not b:
                        break
                    w.write(b)
    print('合并完成: %.1f MB' % (os.path.getsize(merged) / 1e6), flush=True)
else:
    print('合并文件已存在: %.1f MB' % (os.path.getsize(merged) / 1e6), flush=True)
'''

sftp = c.open_sftp()
with sftp.open('/tmp/dl_qwen7b.py', 'w') as f:
    f.write(script)
sftp.close()

i, o, e = c.exec_command('cd /tmp && nohup python3 -u dl_qwen7b.py > /tmp/dl_qwen7b.log 2>&1 &', timeout=30)
o.read()
print('下载已在后台启动，日志: /tmp/dl_qwen7b.log')
c.close()
