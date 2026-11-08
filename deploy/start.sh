#!/bin/bash
# 启动云端中转服务（端口 7000）
cd /home/qiqiwang/airelay || exit 1
pkill -f "airelay/server_cloud.py" 2>/dev/null
sleep 1
setsid nohup python3 /home/qiqiwang/airelay/server_cloud.py > /home/qiqiwang/airelay/server.log 2>&1 < /dev/null &
sleep 2
if ss -lnt 2>/dev/null | grep -q ':7000'; then
  echo "started ok, listening on 7000"
else
  echo "failed to start, log:"
  tail -20 /home/qiqiwang/airelay/server.log
fi
