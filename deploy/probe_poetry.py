"""探测 chinese-poetry 仓库里哪些文件可下载、体积多大。"""
import json
import urllib.request

BASE = 'https://cdn.jsdelivr.net/gh/chinese-poetry/chinese-poetry@master/'

# 候选文件：覆盖唐诗、宋词、诗经、楚辞、蒙学、四书五经
CANDIDATES = [
    '蒙学/tangshisanbaishou.json',
    '蒙学/qianjiashi.json',
    '蒙学/songcisanbaishou.json',
    '诗经/shijing.json',
    '楚辞/chuci.json',
    '四书五经/lunyu.json',
    '四书五经/daxue.json',
    '四书五经/zhongyong.json',
    '论语/lunyu.json',
    '唐诗/poet.tang.0.json',
    '宋词/ci.song.0.json',
    '曹操诗集/caocao.json',
    '纳兰性德/纳兰性德诗集.json',
    '水墨唐诗/shuimotangshi.json',
    '全唐诗/poet.tang.0.json',
]


def probe(path):
    """返回 (状态码, 字节数) 或 (错误, 0)。"""
    url = BASE + urllib.parse.quote(path)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
            return (r.status, len(data), data[:60])
    except Exception as e:
        return (str(e)[:40], 0, b'')


import urllib.parse  # noqa: E402

for p in CANDIDATES:
    code, size, head = probe(p)
    if code == 200:
        print('✔ %-42s %8.1f KB  %s' % (p, size / 1024, head[:40].decode('utf-8', 'ignore')))
    else:
        print('✘ %-42s %s' % (p, code))
