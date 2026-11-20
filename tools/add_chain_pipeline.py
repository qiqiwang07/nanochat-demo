# -*- coding: utf-8 -*-
"""把推理链验证接到网页：模型出思路 → C 引擎逐步验算 → 有错就让它重写。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

FIXES = []

# 1) 非流式调用 + 链验证封装
FIXES.append((
    'def run_reason(expr: str) -> str:',
    '''def llama_once(messages, max_tokens=400):
    """非流式调用一次模型，用于"先拿到完整推理链再验证"的场景。"""
    body = {"messages": messages, "max_tokens": max_tokens, "temperature": 0.2,  # 低温让格式更稳定
            "top_p": 0.9, "repeat_penalty": 1.05}  # 采样参数
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")  # 中文不转义
    req = urllib.request.Request(LLAMA, data=data, headers={"Content-Type": "application/json"})  # 构造请求
    with urllib.request.urlopen(req, timeout=600) as r:  # 600 秒超时
        j = json.loads(r.read().decode("utf-8"))  # 解析完整响应
    msg = j["choices"][0]["message"]  # 取回答
    return (msg.get("content") or "").strip()  # 只要正文


def run_chain(steps: str):
    """调用 C 引擎验证推理链，返回 (是否全对, 可信答案文本, 完整输出)。"""
    try:  # 子进程可能失败
        r = subprocess.run([NP_BIN, "chain", steps], capture_output=True, timeout=20,  # 20 秒足够
                           encoding="utf-8", errors="ignore")  # 容错解码
        out = (r.stdout or "").strip()  # 标准输出就是验证报告
        ok = (r.returncode == 0)  # 返回 0 表示所有步骤都通过
        ans = ""  # 可信答案
        for line in out.splitlines():  # 找【可信答案】那一行
            if line.startswith("【可信答案】"):  # 命中
                ans = line.replace("【可信答案】", "").strip()  # 取出内容
        return (ok, ans, out)  # 三件套
    except Exception:  # 失败
        return (False, "", "")  # 安全返回


def run_reason(expr: str) -> str:'''
))

# 2) /chat 里改成"推理链验证"流程
FIXES.append((
    '''            # 思考第一步：如果问题里有算式，先用精确推理引擎算出来（不靠模型猜）
            expr = extract_expr(text)  # 提取算式
            reasoning = run_reason(expr) if expr else ""  # 调 C 引擎求值与自检
            if reasoning:  # 有结果就注入提示，让模型照着"已验证的过程"回答
                verified = ("下面是用精确算法验证过的计算过程，请据此回答，不要自己另算：\\n"
                            + reasoning + "\\n\\n问题：" + text)
                msgs = s["messages"][:-1] + [{"role": "user", "content": verified}]
''',
    '''            # ---- 推理链验证流程 ----
            # 让模型给出分步推理，每一步都用 C 引擎重算；错的那一步反馈回去让它重写。
            chain_answer = ""  # 最终要展示给用户的文本
            expr = extract_expr(text)  # 先看问题里有没有可算的算式
            if expr and BACKEND != "nanogpt":  # 自研模型不会写推理链，跳过这条路径
                fmt = ("只输出计算步骤，不要任何解释。每步格式严格为 算式=结果，用分号分隔，"
                       "最后一步的结果就是答案。例如：3+5=8;8*2=16")  # 强约束格式
                try:  # 模型调用可能失败
                    chain = llama_once([{"role": "user", "content": text + "\\n" + fmt}], 300)  # 第一轮：模型出思路
                except Exception:  # 失败就退回普通流程
                    chain = ""
                for attempt in range(2):  # 最多两轮：第一轮 + 一次纠错
                    ok, ans, report = run_chain(chain)  # C 引擎逐步验算
                    if ok:  # 全部步骤通过
                        chain_answer = ("【推理链验证】\\n" + report.split("【汇总】")[0].strip()
                                        + "\\n\\n【结论】" + ans + "（每一步都由精确计算器复核通过）")  # 组合展示文本
                        break  # 结束循环
                    if attempt == 0:  # 第一轮有错，把错处反馈给模型重写
                        fix = ("你上一步算错了。验证报告如下，请只输出修正后的整条推理链"
                               "（格式仍然是 算式=结果，分号分隔，不要解释）：\\n" + report)
                        try:
                            chain = llama_once([{"role": "user", "content": text + "\\n" + fix}], 300)  # 第二轮
                        except Exception:  # 失败就放弃纠错
                            break
                    else:  # 两轮都不对，如实告知
                        chain_answer = ("【推理链验证】\\n" + report.strip()
                                        + "\\n\\n【结论】模型给出的推理链存在错误步骤，无法给出可信答案。")  # 诚实说明
'''))

# 3) 如果有 chain_answer，就直接推它，不再调用模型
FIXES.append((
    '''                if BACKEND == "nanogpt":  # 自研 C 模型：直接续写文本''',
    '''                if chain_answer:  # 推理链已验证，直接把它作为回答推给用户
                    for ch in chain_answer:  # 逐字发送，保持流式观感
                        acc.append(ch)
                        emit({"delta": ch})
                elif BACKEND == "nanogpt":  # 自研 C 模型：直接续写文本'''
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
print('推理链验证接入 %d / %d 处' % (applied, len(FIXES)))
