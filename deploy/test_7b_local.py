"""在服务器本地测试 7B + 网页服务（不用 shell 引号，避免转义问题）。"""
import paramiko

script = r'''
import json, time, urllib.request

def chat(q, max_tokens=200):
    body = {"messages": [{"role": "user", "content": q}],
            "max_tokens": max_tokens, "temperature": 0.7}
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
                                 data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        j = json.loads(r.read().decode())
    dt = time.time() - t0
    msg = j["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    reasoning = (msg.get("reasoning_content") or "").strip()
    print("  耗时 %.1fs, content %d 字, reasoning %d 字" % (dt, len(content), len(reasoning)))
    print("  content: %r" % content[:300])
    return content

print("=== 直接测模型 ===")
chat("什么是矩阵的秩")

print()
print("=== 测网页服务 SSE ===")
body = json.dumps({"text": "什么是矩阵的秩", "session": ""}, ensure_ascii=False).encode()
req = urllib.request.Request("http://127.0.0.1:7000/chat", data=body,
                             headers={"Content-Type": "application/json"})
t0 = time.time()
acc = []
with urllib.request.urlopen(req, timeout=900) as r:
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
        if j.get("delta"):
            acc.append(j["delta"])
        if j.get("usage"):
            print("  usage:", j["usage"])
print("  耗时 %.1fs, 收到 %d 个 delta, 合计 %d 字" % (time.time()-t0, len(acc), sum(len(x) for x in acc)))
print("  内容:", "".join(acc)[:400])
'''

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('1.117.113.68', 22, 'qiqiwang', 'wzw0702', timeout=25)
sftp = c.open_sftp()
with sftp.open('/tmp/t7b.py', 'w') as f:
    f.write(script)
sftp.close()
i, o, e = c.exec_command('python3 /tmp/t7b.py', timeout=900)
print(o.read().decode('utf-8', 'ignore'))
err = e.read().decode('utf-8', 'ignore')
if err.strip():
    print('STDERR:', err[:600])
c.close()
