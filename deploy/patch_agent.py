import os

STAGE = r'C:\Users\Lenovo\ai\nanochat-demo\deploy\stage'
p = os.path.join(STAGE, 'agent_r1.py')
s = open(p, encoding='utf-8').read()

# 1) 提示词更明确：必须真的改动
old_prompt = ('    prompt = ("下面是一个文件的完整内容：\\n```\\n%s\\n```\\n\\n"\n'
              '              "任务：%s\\n\\n"\n'
              '              "请输出修改后的完整文件内容。只输出文件内容本身，"\n'
              '              "不要解释，不要加 markdown 代码块标记。" % (old, task))')
new_prompt = ('    prompt = ("下面是一个文件的完整内容：\\n```\\n%s\\n```\\n\\n"\n'
              '              "任务：%s\\n\\n"\n'
              '              "请输出修改后的**完整**文件内容，必须真的按任务改动"\n'
              '              "（改数字、改字符串、改逻辑都要落到代码上）。\\n"\n'
              '              "只输出文件内容本身，不要解释，不要加 markdown 代码块标记。" % (old, task))')
if old_prompt in s:
    s = s.replace(old_prompt, new_prompt, 1)
    print('提示词已加强')
else:
    print('提示词模式未匹配')

# 2) 记录是否真的改动
old_chk = ('    if new.strip() == old.strip():\n'
           '        emit("▶ 模型生成的内容与原文相同，未改动。\\n")')
new_chk = ('    changed = new.strip() != old.strip()\n'
           '    if not changed:\n'
           '        emit("▶ 注意：模型返回的内容与原文完全相同，文件没有被真正修改。\\n")')
if old_chk in s:
    s = s.replace(old_chk, new_chk, 1)
    print('改写检查已加入')
else:
    print('改写检查模式未匹配')

# 3) 结论：没改动就不能说成功
old_head = ('    head = "✅ 已完成并验证通过" if ok else "⚠️ 运行失败（退出码非 0），修改已保留，可继续让我修"')
new_head = ('    if not changed:\n'
            '        head = "⚠️ 文件没有实际改动（模型没按任务修改），请换个更具体的说法重试"\n'
            '    elif ok:\n'
            '        head = "✅ 已修改并验证通过"\n'
            '    else:\n'
            '        head = "⚠️ 运行失败（退出码非 0），修改已保留，可继续让我修"')
if old_head in s:
    s = s.replace(old_head, new_head, 1)
    print('结论逻辑已修正')
else:
    print('结论模式未匹配')

open(p, 'w', encoding='utf-8').write(s)

import ast
ast.parse(open(p, encoding='utf-8').read())
print('agent_r1.py 语法 OK')
