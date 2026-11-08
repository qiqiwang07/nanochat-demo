import os
import zipfile

D = '/home/qiqiwang/airelay/dist'
files = [
    'ai.cmd', 'ai.ps1', 'i.ps1',
    'worker.py', 'serve_r1.py', 'agent_r1.py', 'chat.html', 'config.json',
    'llama-server.exe', 'model.gguf', 'python-3.12.10-amd64.exe',
    'README.txt',
]
out = os.path.join(D, 'ai.zip')
missing = [f for f in files if not os.path.exists(os.path.join(D, f))]
print('缺少文件:', missing)
with zipfile.ZipFile(out, 'w', zipfile.ZIP_STORED) as z:
    for f in files:
        p = os.path.join(D, f)
        if os.path.exists(p):
            z.write(p, f)
print('ai.zip 生成完成: %.1f MB' % (os.path.getsize(out) / 1e6))
