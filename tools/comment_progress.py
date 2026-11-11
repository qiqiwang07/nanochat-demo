# -*- coding: utf-8 -*-
"""统计各源码文件的注释覆盖率，给出加注释工作的准确进度。"""
import io
import os
import re

ROOT = r'C:\Users\Lenovo\ai\nanochat-demo'

# 已经处理过的文件
DONE = {
    'tools/serve_r1.py', 'tools/agent_r1.py', 'bin/chat.html', 'src/nanogpt.c',
}


def coverage(path):
    """返回 (总行数, 有注释的行数, 覆盖率)。"""
    try:
        text = io.open(path, encoding='utf-8', errors='ignore').read()
    except Exception:
        return (0, 0, 0.0)
    lines = text.split('\n')
    total = 0
    commented = 0
    for ln in lines:
        s = ln.strip()
        if not s:                      # 空行不算
            continue
        total += 1
        # 统计：行内注释、整行注释、Python docstring 行
        if ('/*' in s) or s.startswith('//') or s.startswith('#') or s.startswith('"""') or s.startswith("'''"):
            commented += 1
    return (total, commented, commented / total * 100 if total else 0.0)


def scan(subdir, exts):
    """扫描某个子目录下的指定扩展名文件。"""
    out = []
    base = os.path.join(ROOT, subdir)
    if not os.path.isdir(base):
        return out
    for fn in sorted(os.listdir(base)):
        if not fn.endswith(exts):
            continue
        if fn.startswith('_'):
            continue
        full = os.path.join(base, fn)
        if not os.path.isfile(full):
            continue
        rel = subdir + '/' + fn
        t, c, pct = coverage(full)
        out.append((rel, t, c, pct, rel in DONE))
    return out


rows = scan('src', ('.c',)) + scan('tools', ('.py',))

print('%-34s %7s %7s %8s' % ('文件', '有效行', '有注释', '覆盖率'))
print('-' * 62)
for rel, t, c, pct, done in rows:
    flag = '✓' if done else ' '
    print('%-32s %7d %7d %7.0f%%  %s' % (rel, t, c, pct, flag))

print()
done_rows = [r for r in rows if r[4]]
todo_rows = [r for r in rows if not r[4]]
dt = sum(r[1] for r in done_rows)
dc = sum(r[2] for r in done_rows)
tt = sum(r[1] for r in rows)
print('已批注: %d 个文件, %d / %d 行 (%.0f%%)' % (len(done_rows), dc, dt, dc / dt * 100 if dt else 0))
print('待批注: %d 个文件, %d 行' % (len(todo_rows), tt - dt))
print('整体进度: %d / %d 行 (%.0f%%)' % (dc, tt, dc / tt * 100 if tt else 0))
