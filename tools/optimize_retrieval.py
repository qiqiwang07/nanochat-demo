"""优化检索：减少上下文长度，让首字更快。

改动：
1. 教材片段从 700 字降到 400 字（信息量够，但提示词短一半）
2. 教材只取 2 段（原来 3 段）
3. 题库相似题只取 1 道，且解答截断到 900 字（原来 1600）
4. 普通问题不做教材检索（除非是明确的知识型问题）
"""
import ast
import os

FILES = [
    r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py',
    os.path.join(os.environ['USERPROFILE'], 'AI助手', 'serve_r1.py'),
]

for path in FILES:
    s = open(path, encoding='utf-8').read()
    orig = s

    # 1) 教材片段更短
    s = s.replace('def build_index(path: str, size: int = 700, overlap: int = 100) -> None:',
                  'def build_index(path: str, size: int = 400, overlap: int = 60) -> None:')

    # 2) 检索数量减少
    s = s.replace('            math_hits = retrieve_olympiad(text, 2)',
                  '            math_hits = retrieve_olympiad(text, 1)')
    s = s.replace('            hits = retrieve(text, 3)',
                  '            hits = retrieve(text, 2)')

    # 3) 题库解答截断
    s = s.replace('"【相似题%d】\\n题目：%s\\n标准解答：%s" % (i + 1, q, a[:1600])',
                  '"【相似题%d】\\n题目：%s\\n标准解答：%s" % (i + 1, q, a[:900])')

    if s != orig:
        ast.parse(s)
        open(path, 'w', encoding='utf-8').write(s)
        print('%s: 已优化' % os.path.basename(path))
    else:
        print('%s: 无变化（可能已优化过）' % os.path.basename(path))

# 验证改动
print()
print('=== 验证 ===')
for i, line in enumerate(open(FILES[0], encoding='utf-8'), 1):
    if 'retrieve(' in line and 'def ' not in line or 'size: int = 400' in line or 'a[:900]' in line:
        print(i, line.strip()[:90])
