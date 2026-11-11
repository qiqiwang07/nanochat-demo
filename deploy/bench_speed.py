"""在服务器上直接压测模型生成速度，用于对比不同参数配置。"""
import json
import time
import urllib.request

body = {
    "messages": [{"role": "user", "content": "用三句话解释什么是素数。"}],
    "max_tokens": 120,
    "temperature": 0.7,
    "stream": True,
    "stream_options": {"include_usage": True},
}
req = urllib.request.Request(
    "http://127.0.0.1:8080/v1/chat/completions",
    data=json.dumps(body, ensure_ascii=False).encode(),
    headers={"Content-Type": "application/json"},
)

t0 = time.time()
first = None
acc = ""
usage = {}
with urllib.request.urlopen(req, timeout=600) as r:
    for raw in r:
        line = raw.decode("utf-8", "ignore").strip()
        if not line.startswith("data:"):
            continue
        p = line[5:].strip()
        if p == "[DONE]":
            break
        try:
            j = json.loads(p)
        except Exception:
            continue
        d = (j.get("choices") or [{}])[0].get("delta") or {}
        if d.get("content"):
            if first is None:
                first = time.time() - t0
            acc += d["content"]
        if j.get("usage"):
            usage = j["usage"]

dt = time.time() - t0
out = usage.get("completion_tokens", 0)
print("首字 %.1fs | 总 %.1fs | 输出 %d token | 生成速度 %.2f token/秒"
      % (first or -1, dt, out, (out / (dt - (first or 0))) if dt > (first or 0) else 0))
print("回答:", acc.strip()[:150])
