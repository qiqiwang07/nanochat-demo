"""修复 nanogpt.c 的两个既有 bug：
1. 语料太小时验证集跨度变成负数，取模后越界读导致崩溃（0xC0000005）
2. 训练/验证切分没给验证集留够一个上下文长度
"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\src\nanogpt.c'
t = io.open(P, encoding='utf-8').read()

FIXES = []

# 修复 1：sample_batch 跨度为负时夹到 1
FIXES.append((
    '    long lo = val_split ? ntrain : 0;',
    '''    long span = (val_split ? ntrain + nval : ntrain) - (val_split ? ntrain : 0) - T - 1;  /* 可用起点范围 */
    if (span <= 0) span = 1;                       /* 语料太小时跨度会变负，取模后成天文数字导致越界，这里夹到 1 */
    long lo = val_split ? ntrain : 0;'''
))

# 修复 1b：把取模改成用 span
FIXES.append((
    '        long start = lo + (long)(xrand() % (unsigned)(hi - lo - T - 1));',
    '        long start = lo + (long)(xrand() % (unsigned)span);  /* 用夹过的 span，避免负数取模 */'
))

# 修复 2：字符级切分
FIXES.append((
    '        ntrain = (long)(ncorpus * 0.98);           /* 前 98% 做训练 */',
    '''        ntrain = (long)(ncorpus * 0.98);           /* 前 98% 做训练 */
        if (ncorpus - ntrain < T + 2) ntrain = ncorpus - (T + 2);  /* 验证集至少留一个上下文，否则采样越界 */
        if (ntrain < 1) ntrain = 1;                /* 极小语料兜底 */'''
))

# 修复 3：字节级切分
FIXES.append((
    '        ntrain = (long)(ncorpus * 0.98);           /* 训练/验证切分 */',
    '''        ntrain = (long)(ncorpus * 0.98);           /* 训练/验证切分 */
        if (ncorpus - ntrain < T + 2) ntrain = ncorpus - (T + 2);  /* 同上：验证集不能短于上下文 */
        if (ntrain < 1) ntrain = 1;                /* 兜底 */'''
))

applied = 0
for old, new in FIXES:
    if old in t:
        t = t.replace(old, new, 1)
        applied += 1
    else:
        print('未匹配:', old[:60])

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已应用 %d / %d 处修复' % (applied, len(FIXES)))
