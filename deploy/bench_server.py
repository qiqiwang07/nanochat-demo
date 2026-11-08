"""在服务器本地测一下 llama-server 的生成速度。"""
import json
import time

import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('1.117.113.68', 22, 'qiqiwang', 'wzw0702', timeout=25)


def run(cmd, t=300):
    i, o, e = c.exec_command(cmd, timeout=t)
    return (o.read().decode('utf-8', 'ignore') + e.read().decode('utf-8', 'ignore')).strip()


script = r'''
import json, time, urllib.request
body = {"messages": [{"role": "user", "content": "用三句话解释什么是矩阵的秩。"}],
        "max_tokens": 200, "temperature": 0.7}
req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
                             data=json.dumps(body, ensure_ascii=False).encode(),
                             headers={"Content-Type": "application/json"})
t0 = time.time()
with urllib.request.urlopen(req, timeout=300) as r:
    j = json.loads(r.read().decode())
dt = time.time() - t0
u = j.get("usage", {})
ct = u.get("completion_tokens", 0)
print("completion_tokens=%d elapsed=%.1fs speed=%.1f tok/s" % (ct, dt, ct / dt if dt else 0))
print((j["choices"][0]["message"].get("content") or "")[:300])
'''

sftp = c.open_sftp()
with sftp.open('/tmp/bench.py', 'w') as f:
    f.write(script)
sftp.close()
print(run('python3 /tmp/bench.py', 300))
c.close()
