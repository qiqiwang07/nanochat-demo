"""测试必应搜索的抓取与解析效果。"""
import re
import urllib.parse
import urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
      'Accept-Language': 'zh-CN,zh;q=0.9'}


def search(q, n=5):
    """抓必应中文搜索结果，返回 [(标题, 链接, 摘要)]。"""
    url = 'https://cn.bing.com/search?q=' + urllib.parse.quote(q) + '&setlang=zh-CN&count=10'
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode('utf-8', 'ignore')
    out = []
    for block in re.findall(r'<li class="b_algo".*?</li>', html, re.S):
        m = re.search(r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not m:
            continue
        link = m.group(1)
        title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        # 摘要：取 <p> 里的文字
        sm = re.search(r'<p[^>]*>(.*?)</p>', block, re.S)
        snippet = re.sub(r'<[^>]+>', '', sm.group(1)).strip() if sm else ''
        out.append((title, link, snippet))
        if len(out) >= n:
            break
    return out, len(html)


if __name__ == '__main__':
    for q in ['今天的新闻', 'Python 是什么语言', '勾股定理 证明']:
        try:
            res, size = search(q)
            print('查: %s（页面 %d KB，%d 条）' % (q, size // 1024, len(res)))
            for t, u, s in res[:3]:
                print('   ·', t[:40])
                print('     ', u[:70])
                print('     ', s[:80])
        except Exception as e:
            print('查 %s 失败: %s' % (q, e))
        print()
