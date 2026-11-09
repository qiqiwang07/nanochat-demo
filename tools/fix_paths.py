"""把 serve_r1.py 的 Windows 绝对路径改成相对脚本目录的路径，让同一份代码在服务器也能跑。"""
import ast
import os

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
OLD_NEW = [
    ('BIN_DIR = r"C:\\Users\\Lenovo\\ai\\nanochat-demo\\bin"',
     'HERE = os.path.dirname(os.path.abspath(__file__))  # 本文件目录，兼容 Windows/Linux\nBIN_DIR = HERE'),
    ('SESS_DIR = r"C:\\Users\\Lenovo\\ai\\nanochat-demo\\data\\r1_sessions"',
     'SESS_DIR = os.path.join(HERE, "sessions")  # 会话记录放在脚本同级 sessions 目录'),
    ('CORPUS = r"C:\\Users\\Lenovo\\ai\\nanochat-demo\\data\\book_corpus.txt"',
     'CORPUS = os.path.join(HERE, "corpus.txt")  # 教材语料'),
    ('OLYMPIAD = r"C:\\Users\\Lenovo\\ai\\nanochat-demo\\data\\olympiad_index.json"',
     'OLYMPIAD = os.path.join(HERE, "olympiad_index.json")  # 奥数题库索引'),
]

s = open(P, encoding='utf-8').read()
changed = 0
for old, new in OLD_NEW:
    if old in s:
        s = s.replace(old, new, 1)
        changed += 1

if changed:
    ast.parse(s)  # 语法检查，避免改坏
    open(P, 'w', encoding='utf-8').write(s)
    print('已替换 %d 处路径' % changed)
else:
    print('没有需要替换的内容（可能已是相对路径）')

# 打印最终结果确认
for i, line in enumerate(open(P, encoding='utf-8'), 1):
    if line.startswith(('HERE =', 'BIN_DIR =', 'SESS_DIR =', 'CORPUS =', 'OLYMPIAD =')):
        print('%4d  %s' % (i, line.rstrip()))
