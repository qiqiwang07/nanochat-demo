"""把回答风格从「极简」改成「详细、有交流感」。"""
import ast
import os

INST = os.path.join(os.environ['USERPROFILE'], 'AI助手')
TOOLS = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'

OLD = '''            brief = ("要求：用不超过 60 个字直接给出结论，最多再补一句解释。"
                     "不要写“好的/我来想想/首先”这类过程话，不要复述题目。")'''

NEW = '''            brief = ("回答要求：像朋友聊天一样，讲得详细一点、展开一点——"
                     "先说结论，再解释为什么，然后补充要点、例子或注意事项。"
                     "篇幅 300-600 字为宜，分点或分段都行。"
                     "不要只回一两句话，也不要写“好的/我来想想/首先”这类空话，不要复述题目。")'''

MATH_OLD = '''                grounded = ("下面给出几道相似题目及其标准解答，请参考它们的解题思路和书写格式，"
                            "解答用户提出的新题目。\\n"
                            "要求：写清完整推理步骤，最后用 \\\\boxed{} 给出答案；"
                            "不要提及“相似题/参考/资料”这些字眼。\\n\\n"'''

MATH_NEW = '''                grounded = ("下面给出几道相似题目及其标准解答，请参考它们的解题思路和书写格式，"
                            "解答用户提出的新题目。\\n"
                            "要求：写清完整推理步骤（每一步说清楚为什么这么做），"
                            "最后用 \\\\boxed{} 给出答案；答完可以补充一句思路小结或易错点提醒。"
                            "不要提及“相似题/参考/资料”这些字眼。\\n\\n"'''


def patch(path):
    s = open(path, encoding='utf-8').read()
    changed = 0
    if OLD in s:
        s = s.replace(OLD, NEW, 1)
        changed += 1
    elif '像朋友聊天一样' in s:
        changed += 1
        print('  普通提示词已是新版')

    if MATH_OLD in s:
        s = s.replace(MATH_OLD, MATH_NEW, 1)
        changed += 1
    elif '思路小结或易错点提醒' in s:
        changed += 1
        print('  数学提示词已是新版')
    else:
        print('  数学提示词未匹配，检查原文')

    ast.parse(s)
    open(path, 'w', encoding='utf-8').write(s)
    return changed


print('修改 tools 版本:')
patch(TOOLS)
print('修改安装目录版本:')
patch(os.path.join(INST, 'serve_r1.py'))
