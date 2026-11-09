"""把 nanogpt.c 末尾（Chain 结构到文件结束）替换成带注释的版本。"""
import io

SRC = r'C:\Users\Lenovo\ai\nanochat-demo\src\nanogpt.c'
NEW = r'C:\Users\Lenovo\ai\nanochat-demo\src\_tail_section_commented.c'

text = io.open(SRC, encoding='utf-8').read()
new_block = io.open(NEW, encoding='utf-8').read()

# 从「Chain 结构体」开始一直替换到文件末尾
anchor = '/* ====================== 逐步验算 + 投票 ================================ */'
i = text.find(anchor)
if i < 0:
    raise SystemExit('锚点未找到')

head = text[:i]
out = head + new_block
io.open(SRC, 'w', encoding='utf-8', newline='\n').write(out)
print('替换完成：原 %d 字符 -> 新 %d 字符' % (len(text), len(out)))
