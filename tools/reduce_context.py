"""减小注入的检索上下文，降低预填充耗时（首字延迟的主因）。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

FIXES = [
    # 教材片段只取 1 段（原来 2 段，每段 400 字 ≈ 250 token）
    ('            hits = retrieve(text, 2)  # 再检索教材片段作为背景知识',
     '            hits = retrieve(text, 1)  # 只取 1 段：片段越多预填充越慢，首字延迟越高'),
    # 注入时把片段截到 320 字，控制 token 数
    ('                ctx = "\\n\\n".join(hits)  # 拼接片段',
     '                ctx = "\\n\\n".join(h[:320] for h in hits)  # 每段截到 320 字，约 200 token，兼顾信息量与速度'),
]

applied = 0
for old, new in FIXES:
    if old in t:
        t = t.replace(old, new, 1)
        applied += 1
    else:
        print('未匹配:', old[:60])

ast.parse(t)  # 语法检查
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已修改 %d 处' % applied)
