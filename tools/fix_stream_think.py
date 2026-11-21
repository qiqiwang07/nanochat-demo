# -*- coding: utf-8 -*-
"""流式输出同时转发"思考过程"和"回答"，并修正题型路由。

为什么必须转发思考：
    nginx 默认 proxy_read_timeout 60 秒。推理模型思考时前端一个字都收不到，
    连接会被 nginx 掐断（测试里那些 60.1 秒空响应的就是它）。
    把 reasoning_content 也实时推出去，既保活，又能让用户看到"它在想"。
"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

# ---------- 1) 重写 stream_llama ----------
start = t.find('def stream_llama(messages, usage_out: dict, max_tokens=None):')
end = t.find('def load_sessions() -> None:')
assert start > 0 and end > start, '找不到 stream_llama'

NEW_STREAM = '''def stream_llama(messages, usage_out: dict, max_tokens=None):
    """向 llama-server 请求流式输出，同时转发"思考"与"回答"。

    输出格式约定：
        思考阶段：先发 "【思考】\\n"，随后是逐字的思考内容
        回答阶段：发 "\\n\\n【回答】\\n"，随后是正文
    这样前端能一直收到数据，不会被 nginx 的 60 秒超时掐断。
    """
    body = {  # OpenAI 兼容请求体
        "messages": messages,
        "max_tokens": int(max_tokens or MAX_NEW),
        "temperature": 0.7,
        "top_p": 0.9,
        "repeat_penalty": 1.05,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(LLAMA, data=data, headers={"Content-Type": "application/json"})
    t0 = time.time()
    think = []          # 思考内容
    answer = []         # 正文
    sent_think = False  # 是否已发出思考标题
    sent_ans = False    # 是否已发出回答标题

    with urllib.request.urlopen(req, timeout=900) as r:
        for raw in r:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                j = json.loads(payload)
            except Exception:
                continue
            u = j.get("usage")
            if u:                                     # 最后一个分片带用量
                usage_out["in"] = int(u.get("prompt_tokens") or 0)
                usage_out["out"] = int(u.get("completion_tokens") or 0)
            ch = j.get("choices") or [{}]
            delta = ch[0].get("delta") or {}
            rc = delta.get("reasoning_content") or ""  # 思考增量
            ct = delta.get("content") or ""            # 正文增量
            if rc:
                if not sent_think:                     # 第一次思考，先发个标题
                    sent_think = True
                    yield "【思考】\\n"
                think.append(rc)
                yield rc                               # 实时转发，起到保活作用
            if ct:
                if not sent_ans:                       # 第一次正文，切换到回答
                    sent_ans = True
                    yield "\\n\\n【回答】\\n"
                answer.append(ct)
                yield ct
    usage_out["think"] = "".join(think)                # 交给调用方决定是否落盘
    usage_out["answer"] = "".join(answer)
    dt = time.time() - t0
    print("[llama] 思考 %d 字 / 回答 %d 字 / %.1fs" % (len(usage_out["think"]), len(answer), dt), flush=True)


'''

t = t[:start] + NEW_STREAM + t[end:]

# ---------- 2) 修正题型路由 ----------
OLD_ROUTE = '''    s = text.strip()
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
    return 'think\''''

NEW_ROUTE = '''    s = text.strip()
    cjk = sum(1 for ch in s if '\\u4e00' <= ch <= '\\u9fff')  # 中文字数

    # 一级：纯符号算式 → C 引擎
    if extract_expr(s) and cjk <= 6:
        return 'calc'

    # 需要生成/推理的题：优先级最高，绝不能走查库（否则会拿一段无关原文糊弄）
    think_keys = ('写', '代码', '函数', '程序', '实现', '算法', '编程', '作文', '议论文',
                  '记叙文', '散文', '诗', '为什么', '证明', '推导', '分析', '比较',
                  '评价', '设计', '优化', '如何', '怎样', '步骤', '计算', '求')
    if any(k in s for k in think_keys):
        return 'think'

    # 二级：明确的"查资料"问法 → 检索直出
    lookup_heads = ('什么是', '什么叫', '是什么', '谁是', '的作者', '的作者是谁',
                    '多少', '几位', '哪一年', '解释一下', '定义')
    if any(s.startswith(h) or h in s for h in lookup_heads):
        return 'lookup'

    # 其余交给模型
    return 'think\''''

assert OLD_ROUTE in t, '找不到路由规则'
t = t.replace(OLD_ROUTE, NEW_ROUTE, 1)

# ---------- 3) 落盘用回答而不是思考 ----------
OLD_SAVE = '''            ans = strip_refs("".join(acc)) or "（模型没有给出答案）"  # 清洗出处措辞并兜底'''
NEW_SAVE = '''            raw_ans = usage.get("answer") or usage.get("think") or "".join(acc)  # 有正文用正文，没有就用思考
            ans = strip_refs(raw_ans) or "（模型没有给出答案）"  # 清洗出处措辞并兜底'''
assert OLD_SAVE in t, '找不到落盘行'
t = t.replace(OLD_SAVE, NEW_SAVE, 1)

ast.parse(t)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已重写流式输出与路由')
