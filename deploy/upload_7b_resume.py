"""上传 7B 模型到服务器（支持断点续传，连接中断自动重试）。"""
import os
import time

import paramiko

HOST, USER, PWD = '1.117.113.68', 'qiqiwang', 'wzw0702'
LOCAL = r'C:\Users\Lenovo\ai\models\qwen7b.gguf'
REMOTE = '/home/qiqiwang/models/qwen7b.gguf'

local_size = os.path.getsize(LOCAL)
print('本地文件: %.1f MB' % (local_size / 1e6))


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PWD, timeout=25, banner_timeout=25, auth_timeout=25)
    return c


def remote_size(c):
    try:
        sftp = c.open_sftp()
        try:
            n = sftp.stat(REMOTE).st_size
        finally:
            sftp.close()
        return n
    except Exception:
        return 0


for attempt in range(1, 21):
    c = connect()
    have = remote_size(c)
    print('第 %d 次尝试，服务器已有 %.1f MB / %.1f MB (%.1f%%)' % (
        attempt, have / 1e6, local_size / 1e6, have * 100 / local_size), flush=True)
    if have >= local_size:
        break
    try:
        sftp = c.open_sftp()
        # 追加模式写入剩余部分
        with open(LOCAL, 'rb') as f:
            f.seek(have)
            rf = sftp.open(REMOTE, 'ab')
            rf.set_pipelined(True)
            chunk = 4 << 20
            sent = have
            last_pct = -1
            while True:
                data = f.read(chunk)
                if not data:
                    break
                rf.write(data)
                sent += len(data)
                pct = int(sent * 100 / local_size)
                if pct >= last_pct + 2:
                    last_pct = pct
                    print('  %d%%  %.0f / %.0f MB' % (pct, sent / 1e6, local_size / 1e6), flush=True)
            rf.close()
        sftp.close()
    except Exception as ex:
        print('  中断: %s，5 秒后续传' % str(ex)[:80], flush=True)
        try:
            c.close()
        except Exception:
            pass
        time.sleep(5)
        continue
    c.close()
    break

# 最终校验
c = connect()
final = remote_size(c)
i, o, e = c.exec_command('ls -l %s' % REMOTE)
print(o.read().decode().strip())
c.close()
print('完成: 服务器 %.1f MB / 本地 %.1f MB → %s' % (
    final / 1e6, local_size / 1e6, '一致 ✅' if final == local_size else '不一致 ❌'))
