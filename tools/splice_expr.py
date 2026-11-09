"""替换 nanogpt.c 中的表达式解析器与 gen_text 段。"""
import io

SRC = r'C:\Users\Lenovo\ai\nanochat-demo\src\nanogpt.c'
NEW = r'C:\Users\Lenovo\ai\nanochat-demo\src\_expr_section.c'

text = io.open(SRC, encoding='utf-8').read()
new_block = io.open(NEW, encoding='utf-8').read()

start = '/* ====================== 精确算术（独立于模型的验算器）==================== */'
end = '/* ====================== 逐步验算 + 投票 ================================ */'

i = text.find(start)
j = text.find(end)
if i < 0 or j < 0 or j <= i:
    raise SystemExit('锚点未找到: i=%d j=%d' % (i, j))

out = text[:i] + new_block.rstrip('\n') + '\n\n' + text[j:]
io.open(SRC, 'w', encoding='utf-8', newline='\n').write(out)
print('替换完成：原 %d 字符 -> 新 %d 字符' % (len(text), len(out)))
