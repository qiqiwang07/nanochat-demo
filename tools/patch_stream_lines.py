"""按行号替换 stream_llama 的预输出逻辑（避免中文匹配问题）。"""
import ast
import os

FILES = [
    r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py',
    os.path.join(os.environ['USERPROFILE'], 'AI助手', 'serve_r1.py'),
]

NEW_BLOCK = '''            if not started:
                pre += delta
                # 推理模型才需要剥掉思考标记；Qwen 这类直接输出
                if "</think>" in pre:
                    pre = pre.split("</think>", 1)[1]
                pre = pre.lstrip("\\n")
                if pre:
                    started = True
                    yield pre
                    pre = ""
            else:
                yield delta
'''

for path in FILES:
    lines = open(path, encoding='utf-8').read().split('\n')
    # 找到 "if not started:" 那一行（在 stream_llama 内）
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == 'if not started:' and i > 150:
            start = i
            break
    if start is None:
        print('%s: 未找到起始行' % os.path.basename(path))
        continue
    # 找到对应的 "yield delta" 结束行（缩进回到 else 里的 yield delta）
    end = None
    for j in range(start + 1, min(start + 20, len(lines))):
        if lines[j].strip() == 'yield delta' and lines[j].startswith('                yield'):
            end = j
            break
    if end is None:
        print('%s: 未找到结束行' % os.path.basename(path))
        continue
    new_lines = lines[:start] + NEW_BLOCK.rstrip('\n').split('\n') + lines[end + 1:]
    s = '\n'.join(new_lines)
    try:
        ast.parse(s)
    except SyntaxError as e:
        print('%s: 替换后语法错误 %s' % (os.path.basename(path), e))
        continue
    open(path, 'w', encoding='utf-8').write(s)
    print('%s: 已替换第 %d-%d 行' % (os.path.basename(path), start + 1, end + 1))
