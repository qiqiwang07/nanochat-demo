# -*- coding: utf-8 -*-
"""给服务端加联网能力：必应中文搜索 → 摘要喂给模型 → 回答后附来源。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

# ---------- 1) 插入搜索函数 ----------
HELPER = '''def web_search(query: str, n: int = 4):
    """用必应中文搜索，返回 [(标题, 链接, 摘要)]；失败返回空列表。

    为什么用必应：服务器在国内，Google / DuckDuckGo / 维基都不通，
    实测百度与必应中国可访问，而必应的 HTML 结构更好解析。
    """
    try:
        url = 'https://cn.bing.com/search?q=' + urllib.parse.quote(query) + '&setlang=zh-CN&count=10'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9'})
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode('utf-8', 'ignore')
    except Exception as e:
        print('[web] 搜索失败:', e, flush=True)
        return []
    out = []
    for block in re.findall(r'<li class="b_algo".*?</li>', html, re.S):
        m = re.search(r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not m:
            continue
        link = m.group(1)
        title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        sm = re.search(r'<p[^>]*>(.*?)</p>', block, re.S)
        snippet = re.sub(r'<[^>]+>', '', sm.group(1)).strip() if sm else ''
        snippet = snippet.replace('&ensp;', ' ').replace('&#0183;', '·')
        if title and snippet:
            out.append((title, link, snippet))
        if len(out) >= n:
            break
    return out


def web_grounded(query: str, results) -> str:
    """把搜索结果拼成给模型的材料，要求它据此回答。"""
    parts = []
    for i, (title, link, snippet) in enumerate(results, 1):
        parts.append('【资料%d】%s\\n%s' % (i, title, snippet[:300]))
    return ('以下是刚刚从网上搜到的资料，请据此回答用户的问题。\\n'
            '要求：结合资料给出准确回答，可以说明信息来自哪一条资料；\\n'
            '资料没提到的内容不要编造，直接说明没查到。\\n\\n'
            + '\\n\\n'.join(parts) + '\\n\\n用户问题：' + query)


def format_sources(results) -> str:
    """回答末尾附上来源列表。"""
    if not results:
        return ''
    lines = ['', '', '---', '**来源**']
    for i, (title, link, _) in enumerate(results, 1):
        lines.append('%d. [%s](%s)' % (i, title[:50], link))
    return '\\n'.join(lines)


'''

anchor = 'def classify(text: str) -> str:'
assert anchor in t, '找不到 classify'
t = t.replace(anchor, HELPER + anchor, 1)

# ---------- 2) 路由加 web 判定 ----------
OLD_ROUTE = """    # 二级：明确的"查资料"问法 → 检索直出"""
NEW_ROUTE = """    # 联网意图：时效性、外部信息、明确要求上网查
    web_keys = ('最新', '今天', '现在', '新闻', '最近', '多少钱', '官网', '查一下', '搜一下',
                '上网', '网上', '股价', '天气', '比分', '发布', '几号')
    if any(k in s for k in web_keys):
        return 'web'

    # 二级：明确的"查资料"问法 → 检索直出"""
assert OLD_ROUTE in t, '找不到路由插入点'
t = t.replace(OLD_ROUTE, NEW_ROUTE, 1)

# ---------- 3) do_POST 里处理 web 路由 ----------
OLD_FLOW = """            elif route == 'lookup':                   # 二级：事实题，直接查知识库"""
NEW_FLOW = """            elif route == 'web' and mode != 'nanogpt':   # 联网：先搜，再让模型据此回答
                results = web_search(text)                # 必应中文搜索
                if results:                               # 搜到就把资料喂给模型
                    msgs = [{"role": "user", "content": web_grounded(text, results)}]
                    web_sources = results                 # 记下来，回答后附来源
                    req_max = 800 if mode == 'simple' else 1500
                else:                                     # 没搜到就照常回答
                    msgs = s["messages"][:-1] + [{"role": "user", "content": text + "\\n" + brief}]
            elif route == 'lookup':                   # 二级：事实题，直接查知识库"""
assert OLD_FLOW in t, '找不到 lookup 分支'
t = t.replace(OLD_FLOW, NEW_FLOW, 1)

# ---------- 4) 声明 web_sources ----------
OLD_DECL = "            chain_answer = \"\"                         # 不走模型的直接答案"
NEW_DECL = ("            chain_answer = \"\"                         # 不走模型的直接答案\n"
            "            web_sources = []                          # 联网搜索的来源，回答完附在末尾")
assert OLD_DECL in t, '找不到 chain_answer 声明'
t = t.replace(OLD_DECL, NEW_DECL, 1)

# ---------- 5) 回答结束后附来源 ----------
OLD_END = '''            ans = strip_refs(raw_ans) or "（模型没有给出答案）"  # 清洗出处措辞并兜底'''
NEW_END = '''            ans = strip_refs(raw_ans) or "（模型没有给出答案）"  # 清洗出处措辞并兜底
            if web_sources:                              # 联网搜索过就把来源发给前端
                src = format_sources(web_sources)
                emit({"delta": src})
                acc.append(src)'''
assert OLD_END in t, '找不到落盘行'
t = t.replace(OLD_END, NEW_END, 1)

# ---------- 6) 补 import ----------
if 'import urllib.parse' not in t:
    t = t.replace('import urllib.request  # 向 llama-server 发 HTTP 请求（标准库，无需第三方依赖）',
                  'import urllib.request  # 向 llama-server 发 HTTP 请求（标准库，无需第三方依赖）\n'
                  'import urllib.parse  # 联网搜索时对关键词做 URL 编码', 1)

ast.parse(t)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('联网能力已接入')
