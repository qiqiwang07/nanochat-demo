# -*- coding: utf-8 -*-
"""把每次回答的思考过程落盘成 markdown 文件，并可在线查看。

文件内容结构（类似 DeepSeek 的思考展示）：
    # 问题
    ## 思考过程
    ## 回答
    ## 元信息（耗时、token、来源）
"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

changed = []

# ---------- 1) 目录与保存函数 ----------
if 'THINK_DIR' not in t:
    t = t.replace(
        'SESS_DIR = os.path.join(HERE, "sessions")',
        'SESS_DIR = os.path.join(HERE, "sessions")  # 会话记录\n'
        'THINK_DIR = os.path.join(HERE, "thinking")  # 思考过程落盘目录', 1)
    changed.append('目录常量')

if 'def save_thinking(' not in t:
    HELPER = '''def save_thinking(sid: str, question: str, think: str, answer: str,
                  usage: dict, sources=None) -> str:
    """把一次问答的完整思考过程写成 markdown，返回文件路径。

    为什么单独落盘：思考过程很有价值（复盘、审计、教学），
    但它太长，不适合塞进会话记录里，所以单独存。
    """
    os.makedirs(THINK_DIR, exist_ok=True)
    ts = time.strftime('%Y%m%d_%H%M%S')
    path = os.path.join(THINK_DIR, '%s_%s.md' % (ts, sid or 'anon'))
    lines = ['# 问题', '', question or '（空）', '']
    if think:
        lines += ['## 思考过程', '', think.strip(), '']
    lines += ['## 回答', '', (answer or '').strip(), '']
    lines += ['---', '',
              '- 时间：%s' % time.strftime('%Y-%m-%d %H:%M:%S'),
              '- 会话：%s' % (sid or '匿名'),
              '- 输入 token：%d' % usage.get('in', 0),
              '- 输出 token：%d' % usage.get('out', 0)]
    if sources:
        lines += ['', '## 来源']
        for i, (title, link, _) in enumerate(sources, 1):
            lines.append('%d. [%s](%s)' % (i, title, link))
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\\n'.join(lines) + '\\n')
    return path


'''
    t = t.replace('def load_sessions() -> None:', HELPER + 'def load_sessions() -> None:', 1)
    changed.append('保存函数')

# ---------- 2) 回答结束后落盘 ----------
OLD = '            if web_sources:                              # 联网过就把来源发出去'
NEW = '''            try:  # 落盘失败不影响回答
                save_thinking(sid, text, usage.get("think", ""), raw_ans, usage, web_sources)
            except Exception as e:
                print("[thinking] 保存失败:", e, flush=True)

            if web_sources:                              # 联网过就把来源发出去'''
if OLD in t:
    t = t.replace(OLD, NEW, 1)
    changed.append('落盘调用')

# ---------- 3) 路由：列出/查看思考文件 ----------
OLD_GET = '''        elif u.path == "/sessions":  # 左侧会话列表'''
NEW_GET = '''        elif u.path == "/thinking":  # 查看思考过程文件
            qs = parse_qs(u.query)
            name = (qs.get("f") or [""])[0]  # 指定文件名就返回内容
            if name:  # 单文件
                fp = os.path.join(THINK_DIR, os.path.basename(name))  # 防目录穿越
                if os.path.isfile(fp):
                    with open(fp, "rb") as f:
                        self._send(f.read(), "text/markdown")
                else:
                    self._send(b'{"error":"not found"}')
            else:  # 列出最近的
                os.makedirs(THINK_DIR, exist_ok=True)
                files = sorted(os.listdir(THINK_DIR), reverse=True)[:50]
                data = [{"name": f, "size": os.path.getsize(os.path.join(THINK_DIR, f))}
                        for f in files if f.endswith(".md")]
                self._send(json.dumps({"files": data}, ensure_ascii=False).encode())
        elif u.path == "/sessions":  # 左侧会话列表'''
if OLD_GET in t:
    t = t.replace(OLD_GET, NEW_GET, 1)
    changed.append('查看接口')

ast.parse(t)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已改动：' + '、'.join(changed))
