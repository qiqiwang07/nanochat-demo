# -*- coding: utf-8 -*-
"""去掉重复的【推理链验证】标题（report 本身已包含该标题）。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

# report 的开头已经是【推理链验证】，这里不再重复添加
before = t
t = t.replace('("【推理链验证】\\n" + report.split("【汇总】")[0].strip()',
              '(report.split("【汇总】")[0].strip()')
t = t.replace('("【推理链验证】\\n" + report.strip()',
              '(report.strip()')

if t != before:
    ast.parse(t)
    io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
    print('已去掉重复标题')
else:
    print('没有变化，请检查文件内容')

for i, ln in enumerate(t.split('\n'), 1):
    if 'chain_answer = (' in ln:
        print('%d: %s' % (i, ln.strip()[:80]))
