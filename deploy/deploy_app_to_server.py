"""把对话服务（含题库检索 + 下载分发）部署到云端服务器，并切换到服务器本地模型。"""
import os
import time

import paramiko

HOST, USER, PWD = '1.117.113.68', 'qiqiwang', 'wzw0702'
INST = os.path.join(os.environ['USERPROFILE'], 'AI助手')
REMOTE = '/home/qiqiwang/airelay/app'

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, 22, USER, PWD, timeout=25)


def run(cmd, t=300):
    i, o, e = c.exec_command(cmd, timeout=t)
    return (o.read().decode('utf-8', 'ignore') + e.read().decode('utf-8', 'ignore')).strip()


print(run('mkdir -p %s/sessions && echo ok' % REMOTE))

sftp = c.open_sftp()
files = [
    (os.path.join(INST, 'serve_r1.py'), 'serve_r1.py'),
    (os.path.join(INST, 'chat.html'), 'chat.html'),
    (os.path.join(INST, 'olympiad_index.json'), 'olympiad_index.json'),
    (os.path.join(INST, 'corpus.txt'), 'corpus.txt'),
]
for local, name in files:
    if not os.path.exists(local):
        print('缺少本地文件:', local)
        continue
    t0 = time.time()
    sftp.put(local, REMOTE + '/' + name)
    print('上传 %-22s %.1f MB (%.0fs)' % (name, os.path.getsize(local) / 1e6, time.time() - t0))
sftp.close()

# 用 serve_r1 替换原来的中转服务：它需要监听 7000（nginx 转发目标）
start = r'''#!/bin/bash
# 启动云端 AI 助手（llama-server 推理 + serve_r1 网页服务）
APP=/home/qiqiwang/airelay/app
cd $APP || exit 1

# 1) 模型服务
if ! curl -s -m 2 http://127.0.0.1:8080/health | grep -q ok; then
  bash /home/qiqiwang/start_llama.sh || exit 1
fi

# 2) 停掉旧的中转进程（占用 7000 的那个）
pkill -f 'airelay/server_cloud.py' 2>/dev/null
pkill -f 'airelay/app/serve_r1.py' 2>/dev/null
sleep 1

# 3) 启动网页服务（监听 7000，nginx 转发到这里）
setsid nohup python3 $APP/serve_r1.py --port 7000 --max-new 1500 \
  > /home/qiqiwang/airelay/app/app.log 2>&1 < /dev/null &

for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  sleep 1
  if curl -s -m 2 http://127.0.0.1:7000/health | grep -q ok; then
    echo "AI 助手服务已启动（端口 7000），用时 ${i}s"
    exit 0
  fi
done
echo "启动超时，日志："
tail -20 $APP/app.log
exit 1
'''
sftp = c.open_sftp()
with sftp.open('/home/qiqiwang/start_app.sh', 'w') as f:
    f.write(start)
sftp.close()

print(run('chmod +x /home/qiqiwang/start_app.sh && bash /home/qiqiwang/start_app.sh', 180))
print('--- app.log ---')
print(run('tail -8 /home/qiqiwang/airelay/app/app.log'))
c.close()
