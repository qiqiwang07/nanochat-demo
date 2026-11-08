"""把原始分片上传到服务器（支持断点续传），然后用分片名启动。"""
import os
import time

import paramiko

HOST, USER, PWD = '1.117.113.68', 'qiqiwang', 'wzw0702'
SHARD_DIR = r'C:\Users\Lenovo\ai\models\qwen7b'
SHARDS = ['qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf',
          'qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf']
REMOTE_DIR = '/home/qiqiwang/models'


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, USER, PWD, timeout=25, banner_timeout=25, auth_timeout=25)
    return c


def rsize(c, path):
    try:
        sftp = c.open_sftp()
        try:
            return sftp.stat(path).st_size
        finally:
            sftp.close()
    except Exception:
        return 0


# 先把合并文件改名，避免和分片冲突；同时用合并文件的前 3993MB 作为分片1的起点
c = connect()
i, o, e = c.exec_command('ls -l %s/qwen7b.gguf' % REMOTE_DIR)
print(o.read().decode().strip())
c.close()

merged_remote = REMOTE_DIR + '/qwen7b.gguf'
merged_local = os.path.getsize(r'C:\Users\Lenovo\ai\models\qwen7b.gguf')

# 分片1 的大小
s1_local = os.path.join(SHARD_DIR, SHARDS[0])
s1_size = os.path.getsize(s1_local)
print('分片1 应为 %.1f MB' % (s1_size / 1e6))

# 检查合并文件是否包含分片1的全部内容（合并文件 = 分片1 + 分片2）
c = connect()
have = rsize(c, merged_remote)
print('服务器合并文件: %.1f MB' % (have / 1e6))
if have >= s1_size:
    # 截断合并文件得到分片1
    i, o, e = c.exec_command('cd %s && cp qwen7b.gguf %s && truncate -s %d %s && ls -l %s' % (
        REMOTE_DIR, SHARDS[0], s1_size, SHARDS[0], SHARDS[0]))
    print('生成分片1:', o.read().decode().strip())
c.close()

# 上传分片2
c = connect()
local2 = os.path.join(SHARD_DIR, SHARDS[1])
remote2 = REMOTE_DIR + '/' + SHARDS[1]
size2 = os.path.getsize(local2)
have2 = rsize(c, remote2)
print('分片2: 本地 %.1f MB, 服务器 %.1f MB' % (size2 / 1e6, have2 / 1e6))

for attempt in range(1, 15):
    if have2 >= size2:
        break
    try:
        sftp = c.open_sftp()
        with open(local2, 'rb') as f:
            f.seek(have2)
            rf = sftp.open(remote2, 'ab')
            rf.set_pipelined(True)
            chunk = 4 << 20
            sent = have2
            while True:
                data = f.read(chunk)
                if not data:
                    break
                rf.write(data)
                sent += len(data)
                pct = int(sent * 100 / size2)
                if pct % 10 < 2:
                    print('  分片2 %d%%  %.0f/%.0f MB' % (pct, sent / 1e6, size2 / 1e6), flush=True)
            rf.close()
        sftp.close()
    except Exception as ex:
        print('  中断: %s，重连续传' % str(ex)[:60], flush=True)
        try:
            c.close()
        except Exception:
            pass
        time.sleep(4)
        c = connect()
    have2 = rsize(c, remote2)

i, o, e = c.exec_command('ls -l %s/*.gguf' % REMOTE_DIR)
print(o.read().decode().strip())
c.close()
