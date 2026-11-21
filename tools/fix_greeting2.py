# -*- coding: utf-8 -*-
"""按行插入问候直达逻辑（避免命令行转义问题）。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
lines = io.open(P, encoding='utf-8').read().split('\n')

# ---------- 1) classify 里加 greet ----------
i_cls = next(i for i, s in enumerate(lines) if s.startswith('def classify'))
i_calc = next(k for k in range(i_cls, i_cls + 20) if lines[k].strip() == "return 'calc'")

greet = [
    '',
    '    # 问候语：直接回应，别浪费模型算力，也别被当成知识问答',
    "    greetings = ('你好', '您好', '在吗', 'hi', 'hello', '嗨', '哈喽', '谢谢', '多谢')",
    '    if len(s) <= 12 and any(s.lower().startswith(g) for g in greetings):',
    "        return 'greet'",
]
lines = lines[:i_calc + 1] + greet + lines[i_calc + 1:]

# ---------- 2) 路由分支加 greet ----------
i_route = next(i for i, s in enumerate(lines) if "if route == 'calc'" in s)
indent = lines[i_route][:len(lines[i_route]) - len(lines[i_route].lstrip())]

block = [
    indent + "if route == 'greet':  # 问候语直接回应，不调模型",
    indent + "    chain_answer = ('你好！我是这个系统的 AI 助手。\\n\\n'",
    indent + "                    '我可以：\\n'",
    indent + "                    '- 精确计算：直接给算式，我用程序算，不会算错\\n'",
    indent + "                    '- 查知识库：数学、文学、编程\\n'",
    indent + "                    '- 写作文、写代码、解释概念\\n\\n'",
    indent + "                    '直接说你想问什么就行。')",
    indent + "elif " + lines[i_route].strip(),
]
lines = lines[:i_route] + block + lines[i_route + 1:]

# ---------- 3) 去掉【回答】标题 ----------
out_lines = []
for s in lines:
    if '【回答】' in s and 'yield' in s:
        # 改成：只有在有思考过时才插分隔线
        out_lines.append(s.replace('yield "\\n\\n【回答】\\n"', 'pass'))
        continue
    out_lines.append(s)

text = '\n'.join(out_lines)
ast.parse(text)
io.open(P, 'w', encoding='utf-8', newline='\n').write(text)
print('问候直达已加入，【回答】标题已去掉')
