# -*- coding: utf-8 -*-
"""限制思考长度：给模型加系统提示，要求思考不超过 100 字，并压低输出预算。

为什么这么做：
    实测这个 8B 推理模型回答"什么是素数"时思考了 1461 字、用了 373 秒。
    它对简单问题也会长篇自我论证。加系统提示是最省事、且不改模型的办法。
"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

# 1) 在"链验证"之前，按题型给 msgs 加系统提示
OLD = '''            route = classify(text) if BACKEND != "nanogpt" else "think"  # 自研模型不做路由'''
NEW = '''            route = classify(text) if BACKEND != "nanogpt" else "think"  # 自研模型不做路由

            if route == 'think' and BACKEND != "nanogpt":
                # 限制思考长度：8B 推理模型对简单问题也会想几千字，必须用提示词压住
                msgs = [{"role": "system", "content":
                         "你是简洁的中文助手。回答前先在内部简要思考，思考不超过 100 字，"
                         "然后直接给出答案。不要复述题目，不要写“好的”“让我想想”。"}] + msgs'''
assert OLD in t, '找不到路由行'
t = t.replace(OLD, NEW, 1)

# 2) 思考题的输出预算收窄（思考短了，正文也用不了那么多）
OLD2 = '''                req_max = max(MAX_NEW, 3000) if math_hits else MAX_NEW  # 数学题解答长，给更大额度'''
NEW2 = '''                req_max = max(MAX_NEW, 3000) if math_hits else MAX_NEW  # 数学题解答长，给更大额度
            if route == 'think' and not math_hits and not is_essay and not is_code:
                req_max = min(req_max, 900)  # 思考 + 正文的总额度，防止无限扩写'''
assert OLD2 in t, '找不到 req_max 行'
t = t.replace(OLD2, NEW2, 1)

ast.parse(t)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已加入思考长度限制')
