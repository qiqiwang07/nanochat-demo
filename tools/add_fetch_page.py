# -*- coding: utf-8 -*-
"""联网增强：搜索后抓取前两条结果的网页正文，给模型真实材料。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

# ---------- 1) 网页正文抓取 ----------
if 'def fetch_page(' not in t:
    HELPER = '''def fetch_page(url: str, limit: int = 700) -> str:
    """抓一个网页并抽出正文文本（去掉脚本、样式、标签）。失败返回空串。"""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9'})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read(400000)                      # 最多读 400KB，防止大页面拖死
        html = raw.decode('utf-8', 'ignore')
    except Exception:
        return ''
    # 去掉脚本、样式、注释
    html = re.sub(r'<script[\\s\\S]*?</script>', ' ', html, flags=re.I)
    html = re.sub(r'<style[\\s\\S]*?</style>', ' ', html, flags=re.I)
    html = re.sub(r'<!--[\\s\\S]*?-->', ' ', html)
    # 段落优先：只保留 <p> 里的文字，通常就是正文
    paras = re.findall(r'<p[^>]*>(.*?)</p>', html, re.S)
    text = ' '.join(re.sub(r'<[^>]+>', '', p) for p in paras)
    if len(text) < 80:                                # 没有 <p> 就退回全文本
        text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'&nbsp;|&ensp;|&#0183;', ' ', text)
    text = re.sub(r'\\s+', ' ', text).strip()
    return text[:limit]


'''
    t = t.replace('def web_grounded(', HELPER + 'def web_grounded(', 1)

# ---------- 2) web_grounded 带上网页正文 ----------
OLD = '''def web_grounded(query: str, results) -> str:
    """把搜索结果拼成给模型的材料，要求它据此作答。"""
    parts = []
    for i, (title, link, snippet) in enumerate(results, 1):
        parts.append('【资料%d】%s\\n%s' % (i, title, snippet[:300]))'''
NEW = '''def web_grounded(query: str, results) -> str:
    """把搜索结果拼成给模型的材料；顺手抓前两条的正文，信息更实。"""
    parts = []
    for i, (title, link, snippet) in enumerate(results, 1):
        body = fetch_page(link) if i <= 2 else ''      # 只抓前两条，控制耗时
        detail = body if len(body) > len(snippet) else snippet
        parts.append('【资料%d】%s\\n%s' % (i, title, detail[:600]))'''
assert OLD in t, '找不到 web_grounded'
t = t.replace(OLD, NEW, 1)

ast.parse(t)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已加网页正文抓取')
