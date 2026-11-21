#!/bin/bash
# 下载 DeepSeek-R1-Distill-Llama-8B（Q4_K_M），用于替换 Qwen
# 断点续传 + 多次重试，适合长时间下载
set -u
URL="https://modelscope.cn/api/v1/models/unsloth/DeepSeek-R1-Distill-Llama-8B-GGUF/repo?Revision=master&FilePath=DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf"
OUT="/home/qiqiwang/models/deepseek-r1-8b.gguf"
LOG="/home/qiqiwang/models/dl_deepseek.log"

echo "开始下载 $(date)" > "$LOG"
for i in 1 2 3 4 5 6 7 8 9 10; do
  echo "=== 第 $i 次尝试 $(date) ===" >> "$LOG"
  curl -L --retry 3 --retry-delay 3 -C - -H "User-Agent: Mozilla/5.0" \
       -o "$OUT" "$URL" >> "$LOG" 2>&1
  size=$(stat -c %s "$OUT" 2>/dev/null || echo 0)
  echo "当前大小: $size 字节" >> "$LOG"
  if [ "$size" -gt 4500000000 ]; then
    echo "下载完成 $(date)" >> "$LOG"
    exit 0
  fi
  sleep 5
done
echo "重试次数用尽 $(date)" >> "$LOG"
exit 1
