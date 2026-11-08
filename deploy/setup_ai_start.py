"""服务器端统一启动脚本：模型 + Web 服务 + 下载分发。"""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('1.117.113.68', 22, 'qiqiwang', 'wzw0702', timeout=25)


def run(cmd, t=300):
    i, o, e = c.exec_command(cmd, timeout=t)
    return (o.read().decode('utf-8', 'ignore') + e.read().decode('utf-8', 'ignore')).strip()


script = r'''#!/bin/bash
# 启动云端 AI 助手全部服务
APP=/home/qiqiwang/airelay/app

# 1) 模型推理服务（8080）
if ! curl -s -m 2 http://127.0.0.1:8080/health | grep -q ok; then
  echo "[1/2] 启动模型服务..."
  bash /home/qiqiwang/start_llama.sh || exit 1
else
  echo "[1/2] 模型服务已在运行"
fi

# 2) Web 服务（7000，nginx 转发于此；同时提供 /dl/ 下载）
pkill -f 'airelay/server_cloud.py' 2>/dev/null
pkill -f 'airelay/app/serve_r1.py' 2>/dev/null
sleep 1
ln -sfn /home/qiqiwang/airelay/dist $APP/dist
echo "[2/2] 启动 Web 服务..."
setsid nohup python3 $APP/serve_r1.py --port 7000 --max-new 1500 \
  > $APP/app.log 2>&1 < /dev/null &

for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
  sleep 1
  if curl -s -m 2 http://127.0.0.1:7000/health | grep -q ok; then
    echo ""
    echo "======================================"
    echo "  云端 AI 助手已就绪（用时 ${i}s）"
    echo "  网页:   http://c-learning.oprfin.com/"
    echo "  下载:   http://c-learning.oprfin.com/dl/i.ps1"
    echo "======================================"
    exit 0
  fi
done
echo "启动失败，日志："
tail -20 $APP/app.log
exit 1
'''

sftp = c.open_sftp()
with sftp.open('/home/qiqiwang/ai_start.sh', 'w') as f:
    f.write(script)
sftp.close()
print(run('chmod +x /home/qiqiwang/ai_start.sh && bash /home/qiqiwang/ai_start.sh', 180))
print()
print('=== 进程状态 ===')
print(run("ps aux | grep -E 'llama-server|serve_r1' | grep -v grep | awk '{print $2, $11, $12, $13}'"))
print()
print('=== 内存 ===')
print(run('free -h | head -2'))
c.close()
