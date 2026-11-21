#!/bin/bash
# 下载 Llama-3.2-3B-Instruct（Q4_K_M，约 2 GB），用于替换当前的 8B 推理模型
# 目的：CPU 上跑得快，回答不再需要几分钟
set -u
URL="https://modelscope.cn/api/v1/models/unsloth/Llama-3.2-3B-Instruct-GGUF/repo?Revision=master&FilePath=Llama-3.2-3B-Instruct-Q4_K_M.gguf"
OUT="/home/qiqiwang/models/llama32-3b.gguf"
LOG="/home/qiqiwang/models/dl_llama3b.log"

echo "开始下载 $(date)" > "$LOG"
for i in 1 2 3 4 5 6 7 8; do
  echo "=== 第 $i 次 $(date) ===" >> "$LOG"
  curl -L --retry 3 --retry-delay 3 -C - -H "User-Agent: Mozilla/5.0" \
       -o "$OUT" "$URL" >> "$LOG" 2>&1
  size=$(stat -c %s "$OUT" 2>/dev/null || echo 0)
  echo "当前 $size 字节" >> "$LOG"
  if [ "$size" -gt 1900000000 ]; then
    echo "下载完成 $(date)" >> "$LOG"
    exit 0
  fi
  sleep 5
done
echo "重试次数用尽 $(date)" >> "$LOG"
exit 1
