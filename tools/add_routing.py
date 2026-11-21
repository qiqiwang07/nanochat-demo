# -*- coding: utf-8 -*-
"""三级路由：算式直接算 / 事实题查库直出 / 难题才交给模型思考。

为什么要这样：
    实测 DeepSeek-R1 蒸馏版无法关闭思考——max_tokens 给小了，它把额度全用在
    思考上，正文为零；chat_template_kwargs 的 enable_thinking 也被忽略。
    所以"要不要思考"只能在模型外面按题型决定。
"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

# 1) 加难度判定与检索直出
HELPER = '''def classify(text: str) -> str:
    """判断题型：calc（纯算式）/ lookup（事实查询）/ think（需要推理）。

    规则判据来自实测：
      - 算式题交给 C 引擎，毫秒级且绝对准确
      - 短事实题直接检索知识库，比让 8B 模型思考快 20 倍
      - 其余才交给模型，并给足思考预算
    """
    s = text.strip()
    cjk = sum(1 for ch in s if '\\u4e00' <= ch <= '\\u9fff')  # 中文字数
    if extract_expr(s) and cjk <= 6:                          # 几乎是纯符号算式
        return 'calc'
    lookup_heads = ('什么是', '什么叫', '是什么', '谁是', '哪一年', '哪里', '多少', '几位',
                    '的作者', '的作者是谁', '解释一下', '定义')
    think_keys = ('为什么', '证明', '推导', '分析', '比较', '评价', '写一篇', '写一段',
                  '作文', '代码', '实现', '设计', '优化', '如何', '怎样', '步骤')
    if any(k in s for k in think_keys):                       # 出现推理/创作类关键词
        return 'think'
    if len(s) <= 40 and any(s.startswith(h) or h in s for h in lookup_heads):
        return 'lookup'                                       # 短事实题，查库即可
    if len(s) <= 25:                                          # 很短的问句，先试检索
        return 'lookup'
    return 'think'


def lookup_answer(text: str) -> str:
    """从知识库里挑一段最相关的原文作为回答，并做句子边界裁剪。"""
    hits = retrieve(text, 1)                                  # 取最相关的一段
    if not hits:
        return ''                                             # 没命中就交给模型
    body = hits[0].strip()
    if len(body) > 420:                                       # 控制长度
        cut = max(body.rfind('。', 0, 420), body.rfind('\\n', 0, 420))
        body = body[:cut + 1] if cut > 120 else body[:420]
    return '【知识库检索】\\n' + body                             # 标明来源是检索而非生成


'''

anchor = 'def stream_nanogpt(prompt: str, usage_out: dict):'
assert anchor in t, '找不到插入点'
t = t.replace(anchor, HELPER + anchor, 1)

# 2) 在 /chat 里按题型分流
OLD = '''            # ---- 推理链验证流程 ----
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

NEW = '''            # ---- 先快速判断题型，再决定要不要让模型思考 ----
            chain_answer = ""                         # 不走模型的直接答案
            expr = extract_expr(text)                 # 提取算式
            route = classify(text) if BACKEND != "nanogpt" else "think"  # 自研模型不做路由

            if route == 'calc' and expr:              # 一级：纯算式，C 引擎毫秒级出结果
                rep = run_reason(expr)                # 分解 + 逐步求值 + 自检
                if rep:
                    body = rep[rep.find('【思考过程】'):] if '【思考过程】' in rep else rep
                    chain_answer = '【精确计算】\\n问题：' + expr + '\\n' + body
                    expr = ''                         # 跳过后续模型链路
            elif route == 'lookup':                   # 二级：事实题，直接查知识库
                got = lookup_answer(text)             # 检索最相关原文
                if got:
                    chain_answer = got                # 直出，不调用模型
                    expr = ''

            if expr and route == 'think' and BACKEND != "nanogpt":  # 三级：需要思考的题交给模型'''

assert OLD in t, '未匹配路由段'
t = t.replace(OLD, NEW, 1)

ast.parse(t)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('三级路由已加入')
