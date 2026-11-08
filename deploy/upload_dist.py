import os
import sys
import time

import paramiko

HOST, USER, PWD = '1.117.113.68', 'qiqiwang', 'wzw0702'
DIST = r'C:\Users\Lenovo\ai\nanochat-demo\deploy\dist'
REMOTE = '/home/qiqiwang/airelay/dist'

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PWD, timeout=25)

i, o, e = c.exec_command('mkdir -p %s && echo ok' % REMOTE, timeout=30)
print(o.read().decode().strip())

sftp = c.open_sftp()
for name in ['worker.py', 'config.json', 'i.ps1', 'llama-server.exe', 'model.gguf']:
    local = os.path.join(DIST, name)
    remote = REMOTE + '/' + name
    size = os.path.getsize(local)
    # 跳过已上传
    try:
        if sftp.stat(remote).st_size == size:
            print('跳过（已存在）:', name, flush=True)
            continue
    except Exception:
        pass
    t0 = time.time()
    print('上传 %s (%.1f MB)...' % (name, size / 1e6), flush=True)
    sftp.put(local, remote,
             callback=lambda done, total: None,
             confirm=True)
    dt = time.time() - t0
    print('  完成 %.0fs (%.1f MB/s)' % (dt, size / 1e6 / max(dt, 0.1)), flush=True)
sftp.close()
c.close()
print('ALL DONE')
