import json
import urllib.request

body = {
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 20,
    "stream": True,
    "stream_options": {"include_usage": True},
}
req = urllib.request.Request(
    "http://127.0.0.1:8080/v1/chat/completions",
    data=json.dumps(body, ensure_ascii=False).encode(),
    headers={"Content-Type": "application/json"},
)
n = 0
with urllib.request.urlopen(req, timeout=180) as r:
    for raw in r:
        line = raw.decode("utf-8", "ignore").strip()
        if not line:
            continue
        n += 1
        if n <= 8:
            print(repr(line[:240]))
print("总行数:", n)
