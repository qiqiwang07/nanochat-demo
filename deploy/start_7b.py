"""在服务器上启动 7B 模型，测试速度，然后切换网页服务后端。"""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('1.117.113.68', 22, 'qiqiwang', 'wzw0702', timeout=25)


def run(cmd, t=300):
    i, o, e = c.exec_command(cmd, timeout=t)
    return (o.read().decode('utf-8', 'ignore') + e.read().decode('utf-8', 'ignore')).strip()


# 1) 停掉旧模型，启动 7B
print('=== 启动 7B 模型（上下文 8192，8 线程）===')
print(run('pkill -f "llama-server -m" 2>/dev/null; sleep 2; echo 旧模型已停'))

start7b = r'''#!/bin/bash
cd /home/qiqiwang/llama.cpp/build/bin || exit 1
setsid nohup ./llama-server -m /home/qiqiwang/models/qwen7b.gguf \
  --host 127.0.0.1 --port 8080 -c 8192 -t 8 \
  > /home/qiqiwang/llama7b.log 2>&1 < /dev/null &
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50 51 52 53 54 55 56 57 58 59 60; do
  sleep 1
  if curl -s -m 2 http://127.0.0.1:8080/health | grep -q ok; then
    echo "7B 模型启动成功，用时 ${i}s"
    exit 0
  fi
done
echo "启动超时："
tail -20 /home/qiqiwang/llama7b.log
exit 1
'''
sftp = c.open_sftp()
with sftp.open('/home/qiqiwang/start_7b.sh', 'w') as f:
    f.write(start7b)
sftp.close()
print(run('chmod +x /home/qiqiwang/start_7b.sh && bash /home/qiqiwang/start_7b.sh', 120))
print(run('tail -3 /home/qiqiwang/llama7b.log'))
print(run('free -h | head -2'))
c.close()
