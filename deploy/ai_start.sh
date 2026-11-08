#!/bin/bash
# 启动云端 AI 助手服务（前端 + 模型），监听 0.0.0.0:7000
APP=/home/qiqiwang/airelay/app
cd $APP || exit 1

echo "[1/2] 检查模型服务..."
if ! curl -s -m 2 http://127.0.0.1:8080/health | grep -q ok; then
  bash /home/qiqiwang/start_llama.sh || exit 1
else
  echo "      模型已在运行"
fi

echo "[2/2] 重启网页服务（0.0.0.0:7000）..."
pkill -f 'airelay/server_cloud.py' 2>/dev/null
pkill -f 'airelay/app/serve_r1.py' 2>/dev/null
sleep 2
ln -sfn /home/qiqiwang/airelay/dist $APP/dist
setsid nohup python3 $APP/serve_r1.py --port 7000 --bind 0.0.0.0 --max-new 1500 \
  > $APP/app.log 2>&1 < /dev/null &

for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  sleep 1
  if curl -s -m 2 http://127.0.0.1:7000/health | grep -q ok; then
    echo ""
    echo "=========================================="
    echo "  已就绪"
    echo "  网页:   http://1.117.113.68:7000/"
    echo "  下载:   http://1.117.113.68:7000/dl/i.ps1"
    echo "=========================================="
    ss -lnt | grep 7000
    exit 0
  fi
done
echo "启动失败："
tail -15 $APP/app.log
exit 1
