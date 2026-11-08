#!/bin/bash
# 启动云端 AI 助手（8000 端口，彻底脱离 SSH 会话）
APP=/home/qiqiwang/airelay/app
PORT=8000
cd $APP || exit 1

echo "[1/3] 检查模型服务..."
if ! curl -s -m 2 http://127.0.0.1:8080/health | grep -q ok; then
  bash /home/qiqiwang/start_llama.sh || exit 1
else
  echo "      模型已在运行（15-16 token/秒）"
fi

echo "[2/3] 停止旧进程..."
pkill -9 -f 'airelay/app/serve_r1.py' 2>/dev/null
pkill -9 -f 'airelay/server_cloud.py' 2>/dev/null
sleep 2
ln -sfn /home/qiqiwang/airelay/dist $APP/dist

echo "[3/3] 启动网页服务（0.0.0.0:$PORT）..."
export PORT
# 用 setsid + 重定向全部 fd，确保脱离会话
setsid bash -c "exec python3 $APP/serve_r1.py --port $PORT --bind 0.0.0.0 --max-new 1500" \
  >> $APP/app.log 2>&1 < /dev/null &
disown 2>/dev/null

for i in $(seq 1 20); do
  sleep 1
  if curl -s -m 2 "http://127.0.0.1:$PORT/health" | grep -q ok; then
    echo ""
    echo "=========================================="
    echo "  已就绪"
    echo "  网页:   http://1.117.113.68:$PORT/"
    echo "  下载:   http://1.117.113.68:$PORT/dl/i.ps1"
    echo "=========================================="
    ss -lnt | grep ":$PORT" || true
    exit 0
  fi
done
echo "启动失败："
tail -20 $APP/app.log
exit 1
