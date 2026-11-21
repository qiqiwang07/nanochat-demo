# -*- coding: utf-8 -*-
"""纯算式题直接由 C 引擎作答，不调用模型：又快又准，还省算力。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

OLD = '''            # ---- 推理链验证流程 ----
            # 让模型给出分步推理，每一步都用 C 引擎重算；错的那一步反馈回去让它重写。
            chain_answer = ""  # 最终要展示给用户的文本
            expr = extract_expr(text)  # 先看问题里有没有可算的算式
            if expr and BACKEND != "nanogpt":  # 自研模型不会写推理链，跳过这条路径'''

NEW = '''            # ---- 推理链验证流程 ----
            # 让模型给出分步推理，每一步都用 C 引擎重算；错的那一步反馈回去让它重写。
            chain_answer = ""  # 最终要展示给用户的文本
            expr = extract_expr(text)  # 先看问题里有没有可算的算式

            # 纯算式（几乎没有中文描述）直接用精确引擎作答：不调模型，1 秒内出结果
            cjk = sum(1 for ch in text if '\\u4e00' <= ch <= '\\u9fff')  # 统计中文个数
            if expr and cjk <= 6:  # 中文很少，说明就是想算这个式子
                rep = run_reason(expr)  # C 引擎：分解 + 逐步求值 + 自检
                if rep:  # 拿到结果就直接回答
                    head = '【精确计算】'  # 标明来源
                    body = rep.split('【问题】', 1)[-1]  # 去掉重复的题面
                    chain_answer = head + '\\n问题：' + expr + '\\n' + body[body.find('【思考过程】'):]
                    expr = ''  # 清空，跳过后面的模型链路

            if expr and BACKEND != "nanogpt":  # 自研模型不会写推理链，跳过这条路径'''

assert OLD in t, '未匹配推理链入口'
t = t.replace(OLD, NEW, 1)
ast.parse(t)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已加入纯算式快速通道')
