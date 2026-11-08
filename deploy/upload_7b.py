"""上传 7B 模型到服务器（分块传输，带进度）。"""
import os
import time

import paramiko

HOST, USER, PWD = '1.117.113.68', 'qiqiwang', 'wzw0702'
LOCAL = r'C:\Users\Lenovo\ai\models\qwen7b.gguf'
REMOTE = '/home/qiqiwang/models/qwen7b.gguf'

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PWD, timeout=25)

# 先删掉服务器上那个没下完的老分片，省空间
i, o, e = c.exec_command('rm -f /home/qiqiwang/models/qwen2.5-7b-instruct-q4_k_m-0000*.gguf; df -h /home | tail -1')
print('清理旧文件:', o.read().decode().strip())

size = os.path.getsize(LOCAL)
remote_size = 0
try:
    remote_size = c.open_sftp().stat(REMOTE).st_size
except Exception:
    remote_size = 0

if remote_size >= size:
    print('服务器上已存在完整文件: %.1f MB' % (remote_size / 1e6))
else:
    print('开始上传 %.1f MB（服务器已有 %.1f MB）' % (size / 1e6, remote_size / 1e6))
    sftp = c.open_sftp()
    last = [0]

    def progress(sent, total):
        pct = sent * 100 // total
        if pct >= last[0] + 5:
            last[0] = pct - pct % 5
            print('  %d%%  %.0f / %.0f MB' % (pct, sent / 1e6, total / 1e6), flush=True)

    t0 = time.time()
    sftp.put(LOCAL, REMOTE, callback=progress, confirm=True)
    dt = time.time() - t0
    print('上传完成 %.0fs (%.1f MB/s)' % (dt, size / 1e6 / dt))
    sftp.close()

i, o, e = c.exec_command('ls -lah /home/qiqiwang/models/qwen7b.gguf')
print(o.read().decode().strip())
c.close()
