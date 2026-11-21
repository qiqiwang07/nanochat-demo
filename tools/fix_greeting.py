# -*- coding: utf-8 -*-
"""修三件事：
1. 打招呼直接回答，不调模型（"你好"不该被当成知识问答）
2. 去掉界面上多余的【回答】标题
3. 只在模型真的思考时才显示【思考】标题
"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

# ---- 1) classify 增加 greet 分支 ----
OLD = """    # 一级：纯符号算式 → C 引擎
    if extract_expr(s) and cjk <= 6:
        return 'calc'"""
NEW = """    # 一级：纯符号算式 → C 引擎
    if extract_expr(s) and cjk <= 6:
        return 'calc'

    # 问候语：直接回一句，不浪费模型算力，也避免被当成知识问答
    greetings = ('你好', '您好', '在吗', 'hi', 'hello', '嗨', '哈喽', '早上好', '晚上好', '谢谢', '多谢')
    if len(s) <= 12 and any(s.lower().startswith(g) or s.lower() == g for g in greetings):
        return 'greet'"""
assert OLD in t, '找不到 calc 分支'
t = t.replace(OLD, NEW, 1)

# 路由分支里加 greet
OLD2 = """            if route == 'calc' and expr:              # 一级：纯算式，C 引擎毫秒级出结果"""
NEW2 = """            if route == 'greet':                      # 问候语：直接回应，不调模型
                chain_answer = ('你好！我是这个系统里的 AI 助手。\\n\\n'
                                '我可以：\\n'
                                '- 做精确计算（直接给算式，我用程序算，不会算错）\\n'
                                '- 回答知识问题（先查本地知识库，含数学、文学、编程）\\n'
                                '- 写作文、写代码、解释概念\\n\\n'
                                '直接说你想问什么就行。')
            elif route == 'calc' and expr:            # 一级：纯算式，C 引擎毫秒级出结果"""
assert OLD2 in t, '找不到路由入口'
t = t.replace(OLD2, NEW2, 1)

# ---- 2) 去掉【回答】标题，思考标题按需 ----
OLD3 = '''            if rc:
                if not sent_think:                  # 首次思考，发标题
                    sent_think = True
                    yield "【思考】\\\\n"
                think.append(rc)
                yield rc                            # 实时转发，保活
            if ct:
                if not sent_ans:                    # 首次正文，切段
                    sent_ans = True
                    yield "\\\\n\\\\n【回答】\\\\n"
                answer.append(ct)
                yield ct'''
NEW3 = '''            if rc:
                if not sent_think:                  # 只有真的在思考时才显示标题
                    sent_think = True
                    yield "> 思考中…\\\\n\\\\n"
                think.append(rc)
                yield rc                            # 实时转发，保活
            if ct:
                if not sent_ans:                    # 思考结束开始作答，插一个分隔
                    sent_ans = True
                    if sent_think:                  # 之前有思考才需要分隔线
                        yield "\\\\n\\\\n---\\\\n\\\\n"
                answer.append(ct)
                yield ct'''
if OLD3 in t:
    t = t.replace(OLD3, NEW3, 1)
else:
    print('注意：流式标题段未匹配，跳过')

ast.parse(t)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已修：问候直达、去掉多余标题')
