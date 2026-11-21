# -*- coding: utf-8 -*-
"""按实际内容替换 classify 的关键词规则，并把思考流式转发加入 stream_llama。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

# ---- 1) 路由关键词：把"写/代码/函数/算法/计算/求"提到最高优先级 ----
OLD = """    lookup_heads = ('什么是', '什么叫', '是什么', '谁是', '哪一年', '哪里', '多少', '几位',
                    '的作者', '的作者是谁', '解释一下', '定义')
    think_keys = ('为什么', '证明', '推导', '分析', '比较', '评价', '写一篇', '写一段',
                  '作文', '代码', '实现', '设计', '优化', '如何', '怎样', '步骤')"""

NEW = """    # 需要生成/推理的题优先判定，避免"写代码""写作文"被误当成查资料
    think_keys = ('写', '代码', '函数', '程序', '实现', '算法', '编程', '作文', '议论文',
                  '记叙文', '散文', '诗', '为什么', '证明', '推导', '分析', '比较',
                  '评价', '设计', '优化', '如何', '怎样', '步骤', '计算', '求')
    lookup_heads = ('什么是', '什么叫', '是什么', '谁是', '哪一年', '哪里', '多少', '几位',
                    '的作者', '的作者是谁', '解释一下', '定义')"""

assert OLD in t, '找不到路由关键词段'
t = t.replace(OLD, NEW, 1)

# ---- 2) stream_llama：转发 reasoning_content ----
start = t.find('def stream_llama(messages, usage_out: dict, max_tokens=None):')
end = t.find('def load_sessions() -> None:')
assert start > 0 and end > start, '找不到 stream_llama 区间'

NEW_STREAM = '''def stream_llama(messages, usage_out: dict, max_tokens=None):
    """向 llama-server 请求流式输出，同时转发"思考"与"回答"。

    为什么连思考也要推给前端：
        nginx 默认 60 秒读超时。推理模型思考时如果前端收不到任何字节，
        连接会被掐断（实测表现为 60.1 秒后返回空）。转发思考既保活，
        也让用户看到模型在想什么。
    """
    body = {                                       # OpenAI 兼容请求体
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
    think, answer = [], []                          # 分别收集思考与正文
    sent_think = sent_ans = False                   # 两个区段的标题是否已发
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
            if u:                                   # 用量信息
                usage_out["in"] = int(u.get("prompt_tokens") or 0)
                usage_out["out"] = int(u.get("completion_tokens") or 0)
            ch = j.get("choices") or [{}]
            delta = ch[0].get("delta") or {}
            rc = delta.get("reasoning_content") or ""   # 思考增量
            ct = delta.get("content") or ""             # 正文增量
            if rc:
                if not sent_think:                  # 首次思考，发标题
                    sent_think = True
                    yield "【思考】\\n"
                think.append(rc)
                yield rc                            # 实时转发，保活
            if ct:
                if not sent_ans:                    # 首次正文，切段
                    sent_ans = True
                    yield "\\n\\n【回答】\\n"
                answer.append(ct)
                yield ct
    usage_out["think"] = "".join(think)
    usage_out["answer"] = "".join(answer)
    print("[llama] 思考 %d 字 / 回答 %d 字 / %.1fs"
          % (len(usage_out["think"]), len(answer), time.time() - t0), flush=True)


'''

t = t[:start] + NEW_STREAM + t[end:]

# ---- 3) 落盘优先用正文 ----
OLD_SAVE = '            ans = strip_refs("".join(acc)) or "（模型没有给出答案）"  # 清洗出处措辞并兜底'
NEW_SAVE = ('            raw_ans = usage.get("answer") or usage.get("think") or "".join(acc)  # 优先正文，其次思考\n'
            '            ans = strip_refs(raw_ans) or "（模型没有给出答案）"  # 清洗出处措辞并兜底')
if OLD_SAVE in t:
    t = t.replace(OLD_SAVE, NEW_SAVE, 1)
else:
    print('注意：未找到落盘行，跳过')

ast.parse(t)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已替换路由与流式输出')
