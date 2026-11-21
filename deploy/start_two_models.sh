#!/bin/bash
# 同时运行两个模型：
#   8080 = Llama-3.2-3B-Instruct（简单模式，快）
#   8081 = DeepSeek-R1-Distill-Llama-8B（思考模式，会推理但慢）
# 内存合计约 7 GB，服务器 31 GB 够用。
BIN=/home/qiqiwang/llama.cpp/build/bin/llama-server
M_SMALL=/home/qiqiwang/models/llama32-3b.gguf
M_THINK=/home/qiqiwang/models/deepseek-r1-8b.gguf

pkill -f 'llama-server -m' 2>/dev/null
sleep 3

cd /home/qiqiwang/llama.cpp/build/bin || exit 1

echo "启动简单模式模型（3B，8080）..."
setsid bash -c "exec ./llama-server -m $M_SMALL --host 127.0.0.1 --port 8080 -c 4096 -t 5 --threads-batch 8" \
  > /home/qiqiwang/llama_small.log 2>&1 < /dev/null &

sleep 8

echo "启动思考模式模型（8B，8081）..."
setsid bash -c "exec ./llama-server -m $M_THINK --host 127.0.0.1 --port 8081 -c 4096 -t 5 --threads-batch 8" \
  > /home/qiqiwang/llama_think.log 2>&1 < /dev/null &

# 等两个都就绪
ok1=0; ok2=0
for i in $(seq 1 90); do
  sleep 2
  if [ $ok1 -eq 0 ] && curl -s -m 2 http://127.0.0.1:8080/health 2>/dev/null | grep -q ok; then
    ok1=1; echo "  ✅ 简单模式（3B）就绪"
  fi
  if [ $ok2 -eq 0 ] && curl -s -m 2 http://127.0.0.1:8081/health 2>/dev/null | grep -q ok; then
    ok2=1; echo "  ✅ 思考模式（8B）就绪"
  fi
  if [ $ok1 -eq 1 ] && [ $ok2 -eq 1 ]; then
    free -h | head -2
    exit 0
  fi
done

echo "超时：简单=$ok1 思考=$ok2"
tail -10 /home/qiqiwang/llama_small.log
tail -10 /home/qiqiwang/llama_think.log
exit 1
