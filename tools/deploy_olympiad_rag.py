import os
import shutil

SRC = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
DATA = r'C:\Users\Lenovo\ai\nanochat-demo\data'
INST = os.path.join(os.environ['USERPROFILE'], 'AI助手')

s = open(SRC, encoding='utf-8').read()

# 换成相对于脚本目录的路径（便于整体拷贝到别的电脑）
s = s.replace('BIN_DIR = r"C:\\Users\\Lenovo\\ai\\nanochat-demo\\bin"',
              'BIN_DIR = os.path.dirname(os.path.abspath(__file__))')
s = s.replace('SESS_DIR = r"C:\\Users\\Lenovo\\ai\\nanochat-demo\\data\\r1_sessions"',
              'SESS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")')
s = s.replace('CORPUS = r"C:\\Users\\Lenovo\\ai\\nanochat-demo\\data\\book_corpus.txt"',
              'CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "corpus.txt")')
s = s.replace('OLYMPIAD = r"C:\\Users\\Lenovo\\ai\\nanochat-demo\\data\\olympiad_index.json"',
              'OLYMPIAD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "olympiad_index.json")')

# 启动时加载题库
if 'load_olympiad(OLYMPIAD)' not in s:
    s = s.replace('    if not args.no_rag:\n        build_index(args.corpus)',
                  '    if not args.no_rag:\n        build_index(args.corpus)\n        load_olympiad(OLYMPIAD)')

open(os.path.join(INST, 'serve_r1.py'), 'w', encoding='utf-8').write(s)
print('安装目录 serve_r1.py 已更新（相对路径 + 加载题库）')

for src, dst in [(os.path.join(DATA, 'olympiad_index.json'), 'olympiad_index.json'),
                 (os.path.join(DATA, 'book_corpus.txt'), 'corpus.txt')]:
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(INST, dst))
        print('复制', dst, '%.1f MB' % (os.path.getsize(src) / 1e6))

import ast
ast.parse(open(os.path.join(INST, 'serve_r1.py'), encoding='utf-8').read())
print('语法 OK')
