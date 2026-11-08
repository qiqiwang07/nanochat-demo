import ast
import os
import subprocess
import time

TOOLS = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
INST = os.path.join(os.environ['USERPROFILE'], 'AI助手')

s = open(TOOLS, encoding='utf-8').read()

if 'load_olympiad(OLYMPIAD)' not in s.split('def main')[1]:
    old = '        build_index(args.corpus)'
    new = '        build_index(args.corpus)\n        load_olympiad(OLYMPIAD)'
    if old in s:
        s = s.replace(old, new, 1)
        print('已加入 load_olympiad 调用')
    else:
        print('未匹配 build_index 调用，检查缩进')
        for i, l in enumerate(s.split('\n'), 1):
            if 'build_index' in l:
                print(i, repr(l))
else:
    print('已有 load_olympiad 调用')

ast.parse(s)
open(TOOLS, 'w', encoding='utf-8').write(s)

# 同步成安装目录版本（相对路径）
t = s
t = t.replace('BIN_DIR = r"C:\\Users\\Lenovo\\ai\\nanochat-demo\\bin"',
              'BIN_DIR = os.path.dirname(os.path.abspath(__file__))')
t = t.replace('SESS_DIR = r"C:\\Users\\Lenovo\\ai\\nanochat-demo\\data\\r1_sessions"',
              'SESS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")')
t = t.replace('CORPUS = r"C:\\Users\\Lenovo\\ai\\nanochat-demo\\data\\book_corpus.txt"',
              'CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus.txt")')
t = t.replace('OLYMPIAD = r"C:\\Users\\Lenovo\\ai\\nanochat-demo\\data\\olympiad_index.json"',
              'OLYMPIAD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "olympiad_index.json")')
open(os.path.join(INST, 'serve_r1.py'), 'w', encoding='utf-8').write(t)
print('安装目录已同步')

# 杀掉所有旧的 serve_r1 进程
out = subprocess.run(['wmic', 'process', 'where', "name like '%python%'", 'get', 'ProcessId,CommandLine'],
                     capture_output=True, text=True, encoding='utf-8', errors='ignore').stdout
killed = 0
for line in out.split('\n'):
    if 'serve_r1' in line:
        parts = line.split()
        for p in parts[::-1]:
            if p.isdigit():
                subprocess.run(['taskkill', '/F', '/PID', p], capture_output=True)
                killed += 1
                break
print('已结束旧进程:', killed)
