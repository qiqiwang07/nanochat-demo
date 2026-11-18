# -*- coding: utf-8 -*-
"""让网页助手"会思考"：先检测算式，用 C 的推理引擎精确求解，再把过程喂给模型。

为什么这样才是"思考"而不是"猜"：
    模型算 17*23 可能错，但它照着"已验证的推导过程"复述就几乎不会错。
    所以顺序是：精确计算 → 校验 → 让模型解释，而不是让模型自己算。
"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

FIXES = []

# 1) 新增算式检测与调用推理引擎的函数
FIXES.append((
    'def stream_nanogpt(prompt: str, usage_out: dict):',
    '''def extract_expr(text: str) -> str:
    """从问题里挑出一个可计算的算式；挑不到返回空串。

    只接受"数字 + 运算符 + 括号"的组合，避免把普通文字当公式去算。
    """
    best = ""  # 候选里最长的那一段最可能是用户想算的式子
    for m in re.finditer(r"[0-9][0-9\\s.()+\\-*/^%]*[0-9]", text):  # 以数字开头结尾
        cand = m.group(0).strip()  # 去掉首尾空白
        if not any(op in cand for op in "+-*/^%"):  # 没有任何运算符就不算算式
            continue  # 继续找
        if len(cand) > len(best):  # 取最长的
            best = cand
    return best  # 没有就返回空串


def run_reason(expr: str) -> str:
    """调用自研 C 推理引擎，返回完整的思考过程文本（失败返回空串）。"""
    try:  # 子进程可能失败（文件缺失、超时）
        r = subprocess.run([NP_BIN, "reason", expr], capture_output=True, timeout=20,  # 20 秒足够
                           encoding="utf-8", errors="ignore")  # 容错解码
        out = (r.stdout or "").strip()  # 只取标准输出
        return out if "【结论】" in out else ""  # 必须有结论才算成功
    except Exception:  # 任何异常都当作没有推理结果
        return ""


def stream_nanogpt(prompt: str, usage_out: dict):'''
))

# 2) 在 /chat 里：先把算式算准，再交给模型
FIXES.append((
    '''            try:  # 后端可能报错（模型崩溃、超时）
                if BACKEND == "nanogpt":  # 自研 C 模型：直接续写文本''',
    '''            # 思考第一步：如果问题里有算式，先用精确推理引擎算出来（不靠模型猜）
            expr = extract_expr(text)  # 提取算式
            reasoning = run_reason(expr) if expr else ""  # 调 C 引擎求值与自检
            if reasoning:  # 有结果就注入提示，让模型照着"已验证的过程"回答
                verified = ("下面是用精确算法验证过的计算过程，请据此回答，不要自己另算：\\n"
                            + reasoning + "\\n\\n问题：" + text)
                msgs = s["messages"][:-1] + [{"role": "user", "content": verified}]

            try:  # 后端可能报错（模型崩溃、超时）
                if BACKEND == "nanogpt":  # 自研 C 模型：直接续写文本'''
))

applied = 0
for old, new in FIXES:
    if old in t:
        t = t.replace(old, new, 1)
        applied += 1
    else:
        print('✘ 未匹配:', old.split('\n')[0][:60])

ast.parse(t)  # 语法检查
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('思考链路已接入 %d / %d 处' % (applied, len(FIXES)))
