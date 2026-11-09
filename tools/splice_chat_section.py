"""用锚点把 nanogpt.c 中"对话模式"到"算术考试"整段替换成带注释的版本。"""
import io

SRC = r'C:\Users\Lenovo\ai\nanochat-demo\src\nanogpt.c'
NEW = r'C:\Users\Lenovo\ai\nanochat-demo\src\_chat_section_commented.c'

text = io.open(SRC, encoding='utf-8').read()
new_block = io.open(NEW, encoding='utf-8').read()

start_anchor = 'static int ctx_append(int *ctx, int n, const char *s) {'
# 结束锚点：算术考试函数结束后的空行 + 下一段标题
end_anchor = '/* ====================== 精确算术（独立于模型的验算器）==================== */'

i = text.find(start_anchor)
j = text.find(end_anchor)
if i < 0 or j < 0 or j <= i:
    raise SystemExit('锚点未找到: i=%d j=%d' % (i, j))

# 保留结束锚点之前的所有内容，中间整段替换
head = text[:i]
tail = text[j:]
out = head + new_block.rstrip('\n') + '\n\n' + tail

io.open(SRC, 'w', encoding='utf-8', newline='\n').write(out)
print('替换完成：原 %d 字符 → 新 %d 字符' % (len(text), len(out)))
print('被替换的区间: %d ~ %d（%d 字符）' % (i, j, j - i))
