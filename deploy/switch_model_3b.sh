#!/bin/bash
# 切换到 Llama-3.2-3B-Instruct（小模型，CPU 上快）
MODEL=/home/qiqiwang/models/llama32-3b.gguf
LOG=/home/qiqiwang/llama_3b.log

[ -f "$MODEL" ] || { echo "模型不存在: $MODEL"; exit 1; }

pkill -f 'llama-server -m' 2>/dev/null
sleep 3

cd /home/qiqiwang/llama.cpp/build/bin || exit 1
setsid bash -c "exec ./llama-server -m $MODEL --host 127.0.0.1 --port 8080 -c 4096 -t 5 --threads-batch 8" \
  > $LOG 2>&1 < /dev/null &

for i in $(seq 1 60); do
  sleep 2
  if curl -s -m 2 http://127.0.0.1:8080/health 2>/dev/null | grep -q ok; then
    echo "✅ Llama-3.2-3B 已就绪"
    free -h | head -2
    exit 0
  fi
done
echo "启动超时"
tail -20 $LOG
exit 1
