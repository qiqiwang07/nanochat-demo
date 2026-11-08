#!/bin/bash
# 启动 7B 模型（Qwen2.5-7B-Instruct，分片形式）
MODEL_DIR=/home/qiqiwang/models
SHARD1=$MODEL_DIR/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf
LOG=/home/qiqiwang/llama7b.log

pkill -f 'llama-server -m' 2>/dev/null
sleep 2

echo "启动模型: $SHARD1"
cd /home/qiqiwang/llama.cpp/build/bin || exit 1

setsid bash -c "exec ./llama-server -m $SHARD1 --host 127.0.0.1 --port 8080 -c 8192 -t 8" \
  > $LOG 2>&1 < /dev/null &

for i in $(seq 1 90); do
  sleep 1
  if curl -s -m 2 http://127.0.0.1:8080/health 2>/dev/null | grep -q ok; then
    echo "✅ 7B 模型启动成功，用时 ${i}s"
    echo "内存占用:"
    free -h | head -2
    exit 0
  fi
  if [ $((i % 15)) -eq 0 ]; then
    echo "  等待中... ${i}s"
  fi
done

echo "❌ 启动失败，日志："
tail -25 $LOG
exit 1
