# -*- coding: utf-8 -*-
"""
 * 文件名：test_suite.py
 * 作用：对线上 AI 助手跑一套测试题，自动判分并生成报告
 * 用法：python tools/test_suite.py [--url http://c-learning.oprfin.com/chat] [--out 报告路径]
 * 作者：qiqiwang07
 * 更新：2026-11-20
 *
 * 判分方式分三类：
 *   1. 数值题：用 Python 精确计算标准答案，比对回答里的数字
 *   2. 知识点题：检查回答是否包含关键实体（如"李白""曹雪芹"）
 *   3. 格式题：检查长度、是否含代码块、是否堆废话
"""
import argparse
import json
import re
import time
import urllib.request

DEFAULT_URL = 'http://c-learning.oprfin.com/chat'

# 测试题：(分类, 问题, 判分方式, 判分参数)
CASES = [
    # ---------- 算术（可精确判分）----------
    ('算术', '17*23+45 等于多少', 'number', 17 * 23 + 45),
    ('算术', '1234 - 567 + 89 等于多少', 'number', 1234 - 567 + 89),
    ('算术', '(12.5-2.5)*4/2 等于多少', 'number', (12.5 - 2.5) * 4 / 2),
    ('算术', '2 的 10 次方是多少', 'number', 1024),
    ('算术', '365 乘以 24 等于多少', 'number', 365 * 24),
    # ---------- 应用题（需要多步推理）----------
    ('应用题', '小明有 15 元，买了 3 支笔，每支 2.5 元，还剩多少钱', 'number', 15 - 3 * 2.5),
    ('应用题', '一个长方形长 8 米宽 5 米，它的周长是多少米', 'number', 2 * (8 + 5)),
    ('应用题', '100 元买 7 个 12 元的本子，还剩多少元', 'number', 100 - 7 * 12),
    # ---------- 数学概念（知识点）----------
    ('数学概念', '什么是正交矩阵？简单说明', 'keywords', ['正交']),
    ('数学概念', '什么是素数？', 'keywords', ['素数']),
    ('数学概念', '解释一下什么是向量', 'keywords', ['向量']),
    # ---------- 文学（知识点）----------
    ('文学', '《静夜思》的作者是谁', 'keywords', ['李白']),
    ('文学', '《红楼梦》的作者是谁', 'keywords', ['曹雪芹']),
    ('文学', '唐宋八大家都有谁', 'keywords', ['韩愈', '柳宗元', '苏轼']),
    ('文学', '背一下《静夜思》全诗', 'keywords', ['床前明月光', '低头思故乡']),
    # ---------- 作文（长度 + 主题）----------
    ('作文', '写一篇关于坚持的短议论文，300 字左右', 'length', (200, 1200)),
    # ---------- 编程（代码块）----------
    ('编程', '用 Python 写一个冒泡排序函数', 'code', 'def'),
    ('编程', '用 C 写一个求数组最大值的函数', 'code', 'int'),
    # ---------- 表达质量（反废话）----------
    ('表达', '用一句话说明什么是勾股定理', 'nofiller', None),
]


def ask(url, question, timeout=900):
    """向服务端提问，返回 (回答文本, 首字秒, 总秒, token 统计)。"""
    body = json.dumps({'text': question, 'session': ''}, ensure_ascii=False).encode()
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
    t0 = time.time()
    acc = ''
    first = None
    usage = {}
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode('utf-8', 'ignore').strip()
            if not line.startswith('data:'):
                continue
            p = line[5:].strip()
            if p == '[DONE]':
                break
            try:
                j = json.loads(p)
            except Exception:
                continue
            if j.get('delta'):
                if first is None:
                    first = time.time() - t0
                acc += j['delta']
            if j.get('usage'):
                usage = j['usage']
    return acc.strip(), (first if first is not None else -1), time.time() - t0, usage


def extract_numbers(text):
    """从回答里提取所有数字（含小数与负数）。"""
    return [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', text)]


def grade(kind, arg, answer):
    """按判分方式给出 (是否通过, 说明)。"""
    if kind == 'number':                       # 数值题：答案里出现期望值
        want = float(arg)
        nums = extract_numbers(answer)
        for n in nums:
            if abs(n - want) <= max(1e-6, abs(want) * 1e-9):
                return True, '命中数值 %.10g' % want
        return False, '未找到 %.10g（回答里的数字：%s）' % (
            want, ', '.join('%g' % x for x in nums[:6]) if nums else '无')

    if kind == 'keywords':                     # 知识点题：包含关键实体
        hit = [k for k in arg if k in answer]
        if len(hit) >= max(1, (len(arg) + 1) // 2):
            return True, '命中关键词：%s' % '、'.join(hit)
        return False, '只命中 %s' % ('、'.join(hit) if hit else '无')

    if kind == 'length':                       # 作文：长度在区间内
        lo, hi = arg
        n = len(answer)
        return (lo <= n <= hi), '长度 %d 字（要求 %d-%d）' % (n, lo, hi)

    if kind == 'code':                         # 编程：有代码块且含关键字
        has_block = '```' in answer
        has_kw = arg in answer
        return (has_block and has_kw), '代码块 %s，含 %s %s' % (
            '有' if has_block else '无', arg, '有' if has_kw else '无')

    if kind == 'nofiller':                     # 表达：不该以废话开头
        bad = ('好的', '当然可以', '我来想想', '首先，我需要')
        start = answer[:12]
        for b in bad:
            if start.startswith(b):
                return False, '开头是废话：%s' % b
        return len(answer) > 8, '%d 字' % len(answer)

    return False, '未知判分方式'


def main():
    """跑完所有题目并输出报告。"""
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', default=DEFAULT_URL)
    ap.add_argument('--out', default='')
    ap.add_argument('--only', default='', help='只跑某个分类')
    args = ap.parse_args()

    rows = []
    ok = 0
    total = 0
    print('测试地址：%s\n' % args.url)
    for kind, q, gkind, garg in CASES:
        if args.only and args.only != kind:
            continue
        total += 1
        try:
            ans, first, dt, usage = ask(args.url, q)
            passed, note = grade(gkind, garg, ans)
        except Exception as e:                 # 请求失败也记一条
            ans, first, dt, usage = '', -1, 0, {}
            passed, note = False, '请求失败：%s' % str(e)[:60]
        if passed:
            ok += 1
        rows.append({
            'cat': kind, 'q': q, 'pass': passed, 'note': note,
            'first': first, 'dt': dt,
            'tok_in': usage.get('in', 0), 'tok_out': usage.get('out', 0),
            'ans': ans,
        })
        print('%s [%s] %s' % ('✅' if passed else '❌', kind, q))
        print('    首字 %.1fs / 总 %.1fs / 输出 %d token · %s' % (
            first, dt, usage.get('out', 0), note))
        print('    %s' % ans[:80].replace('\n', ' '))
        print()

    print('=' * 60)
    print('通过 %d / %d' % (ok, total))
    by_cat = {}
    for r in rows:
        c = by_cat.setdefault(r['cat'], [0, 0])
        c[1] += 1
        if r['pass']:
            c[0] += 1
    for c, (a, b) in by_cat.items():
        print('  %-8s %d/%d' % (c, a, b))

    if args.out:                               # 写 markdown 报告
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write('# 测试报告\n\n')
            f.write('时间：%s\n\n' % time.strftime('%Y-%m-%d %H:%M'))
            f.write('通过 **%d / %d**\n\n' % (ok, total))
            f.write('| 分类 | 问题 | 结果 | 首字 | 总耗时 | 说明 |\n|---|---|---|---|---|---|\n')
            for r in rows:
                f.write('| %s | %s | %s | %.1fs | %.1fs | %s |\n' % (
                    r['cat'], r['q'].replace('|', '/'), '✅' if r['pass'] else '❌',
                    r['first'], r['dt'], r['note'].replace('|', '/')))
            f.write('\n## 回答摘录\n\n')
            for r in rows:
                f.write('### %s\n\n%s\n\n**回答**：\n\n```\n%s\n```\n\n' % (r['q'], r['note'], r['ans'][:600]))
        print('\n报告已写入 %s' % args.out)
    return 0 if ok == total else 1


if __name__ == '__main__':
    raise SystemExit(main())
