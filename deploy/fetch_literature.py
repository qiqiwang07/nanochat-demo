# -*- coding: utf-8 -*-
"""
下载中国古典文学语料，转成纯文本，供 RAG 检索使用。

来源：chinese-poetry 数据集（公共领域古典文学，无版权问题）
输出：/home/qiqiwang/airelay/app/literature.txt
"""
import io
import json
import os
import urllib.parse
import urllib.request

BASE = 'https://cdn.jsdelivr.net/gh/chinese-poetry/chinese-poetry@master/'
OUT = '/home/qiqiwang/airelay/app/literature.txt'

# 要下载的文件（都是公共领域的古籍）
FILES = [
    ('蒙学/tangshisanbaishou.json', '唐诗三百首'),
    ('蒙学/qianjiashi.json', '千家诗'),
    ('诗经/shijing.json', '诗经'),
    ('楚辞/chuci.json', '楚辞'),
    ('论语/lunyu.json', '论语'),
    ('四书五经/daxue.json', '大学'),
    ('四书五经/zhongyong.json', '中庸'),
    ('曹操诗集/caocao.json', '曹操诗集'),
    ('纳兰性德/纳兰性德诗集.json', '纳兰性德词集'),
    ('水墨唐诗/shuimotangshi.json', '唐诗选'),
    ('全唐诗/poet.tang.0.json', '全唐诗（一）'),
    ('宋词/ci.song.0.json', '宋词（一）'),
]

# 每条记录最多保留多少字，避免单条过长挤占检索片段
MAX_RECORD = 400


def fetch(path):
    """下载一个 JSON 文件并解析，失败返回 None。"""
    url = BASE + urllib.parse.quote(path)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print('  下载失败 %s: %s' % (path, str(e)[:60]))
        return None


def texts_of(obj, depth=0):
    """递归收集 JSON 里的所有字符串字段，按顺序返回。"""
    out = []
    if depth > 6:
        return out
    if isinstance(obj, str):
        s = obj.strip()
        if s:
            out.append(s)
    elif isinstance(obj, list):
        for it in obj:
            out.extend(texts_of(it, depth + 1))
    elif isinstance(obj, dict):
        for k in ('title', 'rhythmic', 'chapter', 'section', 'author'):
            if isinstance(obj.get(k), str) and obj[k].strip():
                out.append(obj[k].strip())
        for k in ('content', 'paragraphs', 'para', 'chapter'):
            if k in obj:
                got = texts_of(obj[k], depth + 1)
                if got:
                    out.extend(got)
    return out


def flatten(data, book):
    """把一份 JSON 摊平成若干条文本记录。"""
    records = []

    def walk(node):
        """深度优先遍历，遇到含正文的字典就产出一条记录。"""
        if isinstance(node, list):
            for it in node:
                walk(it)
        elif isinstance(node, dict):
            body = None
            for k in ('paragraphs', 'para', 'content'):
                v = node.get(k)
                if isinstance(v, str) and v.strip():
                    body = v.strip()
                elif isinstance(v, list) and v and all(isinstance(x, str) for x in v):
                    body = '\n'.join(x.strip() for x in v if x.strip())
            if body:
                head = []
                for k in ('title', 'rhythmic', 'chapter', 'section', 'author'):
                    if isinstance(node.get(k), str) and node[k].strip():
                        head.append(node[k].strip())
                text = '《%s》%s\n%s' % (book, ' '.join(head), body)
                if len(text) > MAX_RECORD:
                    text = text[:MAX_RECORD]
                records.append(text)
            else:
                for v in node.values():
                    if isinstance(v, (list, dict)):
                        walk(v)
        return

    walk(data)
    return records


def main():
    """主流程：逐个下载 → 摊平 → 写文件。"""
    all_records = []
    for path, book in FILES:
        print('下载 %s ...' % book)
        data = fetch(path)
        if data is None:
            continue
        if isinstance(data, dict) and 'content' in data and isinstance(data['content'], list):
            recs = flatten(data['content'], book)
        else:
            recs = flatten(data, book)
        print('  %s: %d 条' % (book, len(recs)))
        all_records.extend(recs)

    # 去重但保持顺序
    seen = set()
    uniq = []
    for r in all_records:
        if r not in seen:
            seen.add(r)
            uniq.append(r)

    with io.open(OUT, 'w', encoding='utf-8') as f:
        for r in uniq:
            f.write(r)
            f.write('\n\n')

    size = os.path.getsize(OUT)
    print('\n完成：%d 条，%.1f KB -> %s' % (len(uniq), size / 1024, OUT))


if __name__ == '__main__':
    main()
