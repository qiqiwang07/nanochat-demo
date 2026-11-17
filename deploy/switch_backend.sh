#!/bin/bash
# 切换网页服务后端：bash switch_backend.sh [nanogpt|llama]
#   nanogpt —— 使用自研 C 模型（app 目录下的 nanogpt + selfmade.bin）
#   llama   —— 使用 llama-server 上的外部模型
BACKEND="${1:-nanogpt}"

cd /home/qiqiwang/airelay/app || exit 1

# 先停掉旧进程
pkill -9 -f serve_r1.py 2>/dev/null
sleep 2

# 按后端类型组装参数
EXTRA=""
if [ "$BACKEND" = "nanogpt" ]; then
  EXTRA="--backend nanogpt --np-weights selfmade.bin --np-len 200"
else
  EXTRA="--backend llama"
fi

# 后台启动，脱离终端
setsid bash -c "exec python3 serve_r1.py --port 7000 --bind 0.0.0.0 --max-new 2000 $EXTRA" >> app.log 2>&1 < /dev/null &

# 最多等 20 秒
i=0
while [ $i -lt 20 ]; do
  sleep 1
  i=$((i + 1))
  if curl -s -m 2 http://127.0.0.1:7000/health | grep -q ok; then
    echo "启动成功：后端=$BACKEND"
    exit 0
  fi
done

echo "启动失败"
tail -10 app.log
