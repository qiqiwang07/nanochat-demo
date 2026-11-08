#!/bin/bash
# 启动云端 llama-server（模型推理）
cd /home/qiqiwang/llama.cpp/build/bin || exit 1
pkill -f 'llama-server -m' 2>/dev/null
sleep 1
setsid nohup ./llama-server -m /home/qiqiwang/models/model.gguf \
  --host 127.0.0.1 --port 8080 -c 16384 -t 8 --reasoning-budget 0 \
  > /home/qiqiwang/llama_srv.log 2>&1 < /dev/null &
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40; do
  sleep 1
  if curl -s -m 2 http://127.0.0.1:8080/health | grep -q ok; then
    echo "llama-server 启动成功，用时 ${i}s"
    exit 0
  fi
done
echo "启动超时，日志尾部："
tail -20 /home/qiqiwang/llama_srv.log
exit 1
