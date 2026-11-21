#!/bin/bash
# 切换到 DeepSeek-R1-Distill-Llama-8B，替换掉 Qwen
# 用法：bash switch_model_deepseek.sh
MODEL=/home/qiqiwang/models/deepseek-r1-8b.gguf
LOG=/home/qiqiwang/llama_deepseek.log

if [ ! -f "$MODEL" ]; then
  echo "模型文件不存在: $MODEL"
  exit 1
fi

echo "停掉旧模型..."
pkill -f 'llama-server -m' 2>/dev/null
sleep 3

echo "启动 DeepSeek-R1-Distill-Llama-8B..."
cd /home/qiqiwang/llama.cpp/build/bin || exit 1
setsid bash -c "exec ./llama-server -m $MODEL --host 127.0.0.1 --port 8080 -c 4096 -t 5 --threads-batch 8" \
  > $LOG 2>&1 < /dev/null &

# 等它就绪（8B 模型加载比 7B 慢一些）
for i in $(seq 1 90); do
  sleep 2
  if curl -s -m 2 http://127.0.0.1:8080/health 2>/dev/null | grep -q ok; then
    echo "✅ 模型已就绪（${i}0 秒内）"
    free -h | head -2
    exit 0
  fi
done

echo "❌ 启动超时，日志："
tail -20 $LOG
exit 1
