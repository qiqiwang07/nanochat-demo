import ast
import os
import re

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
s = open(P, encoding='utf-8').read()

# 1) stream_llama 支持每次调用临时指定 max_tokens
s = s.replace(
    'def stream_llama(messages, usage_out: dict):',
    'def stream_llama(messages, usage_out: dict, max_tokens=None):')
s = s.replace(
    '        "max_tokens": MAX_NEW,',
    '        "max_tokens": int(max_tokens or MAX_NEW),')

# 2) reply_to 也支持透传（如果存在）
s = s.replace(
    'def reply_to(messages) -> tuple:',
    'def reply_to(messages, max_tokens=None) -> tuple:')

# 3) /chat 里数学题用更大的额度
s = s.replace(
    '            ref_count = len(math_hits) + (0 if math_hits else len(hits))',
    '            ref_count = len(math_hits) + (0 if math_hits else len(hits))\n'
    '            # 数学题解答长，给更大的输出额度\n'
    '            req_max = max(MAX_NEW, 3000) if math_hits else MAX_NEW')

s = s.replace(
    '                for delta in stream_llama(msgs, usage):',
    '                for delta in stream_llama(msgs, usage, req_max):')

ast.parse(s)
open(P, 'w', encoding='utf-8').write(s)
print('serve_r1.py 已支持数学题更大输出额度')

# 4) 同步到安装目录（保持相对路径风格）
INST = os.path.join(os.environ['USERPROFILE'], 'AI助手')
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
