# -*- coding: utf-8 -*-
"""
 * 文件名：gen_call_graph.py
 * 作用：扫描项目源码，生成调用图数据 docs/call_graph.json，供可视化页面使用
 * 依赖：Python 3.8+ 标准库
 * 作者：qiqiwang07
 * 更新：2026-11-10
 *
 * 输出结构：
 *   {
 *     "generated": "时间",
 *     "functions": [
 *        {"id": "文件::函数名", "name": "函数名", "file": "相对路径",
 *         "doc": "它做什么（取自文档字符串/前导注释）",
 *         "lang": "py|c",
 *         "calls": ["被调用函数名", ...]}
 *     ]
 *   }
"""
import ast
import io
import json
import os
import re
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'docs', 'call_graph.json')

# 跳过目录
SKIP = {'.git', '.venv', 'node_modules', '__pycache__', 'build', 'dist', 'venv',
        'site-packages', 'LAwPY', 'elements of math', '.ipynb_checkpoints'}

C_KEYWORDS = {'if', 'for', 'while', 'switch', 'return', 'sizeof', 'else', 'do', 'case', 'printf', 'fprintf'}


def walk(exts):
    """遍历项目，产出 (相对路径, 绝对路径, 扩展名)。"""
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP and not d.startswith('.')]
        for fn in sorted(filenames):
            ext = os.path.splitext(fn)[1].lower()
            if ext in exts:
                ap = os.path.join(dirpath, fn)
                yield os.path.relpath(ap, ROOT).replace('\\', '/'), ap, ext


def first_sentence(text, limit=90):
    """从文档字符串/注释里取第一句有意义的话，作为"它做了什么"。"""
    if not text:
        return ''
    text = text.strip()
    text = re.sub(r'^[\s\*#/]+', '', text)          # 去掉注释符号
    text = re.sub(r'[-=*_]{4,}', ' ', text)          # 去掉装饰性横线，只留标题文字
    for line in text.split('\n'):
        line = line.strip().strip('*').strip()
        if not line:
            continue
        line = re.sub(r'\s+', ' ', line)             # 压缩空白
        if len(line) > limit:
            line = line[:limit] + '…'
        return line
    return ''


def parse_py(path):
    """解析 Python：函数名、文档字符串、内部调用的函数名。"""
    try:
        src = io.open(path, encoding='utf-8', errors='ignore').read()
        tree = ast.parse(src)
    except Exception:
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = set()
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                f = sub.func
                if isinstance(f, ast.Name):
                    calls.add(f.id)
                elif isinstance(f, ast.Attribute):
                    calls.add(f.attr)
        doc = ast.get_docstring(node) or ''
        out.append({'name': node.name, 'doc': first_sentence(doc), 'calls': sorted(calls), 'line': node.lineno})
    return out


def prev_comment(src, pos):
    """返回紧贴 pos 之前的那段 /* */ 注释内容；中间若有代码则返回空串。

    为什么不能取"前 600 字里最后一段注释"：那样会抓到上一个函数体内部的注释，
    导致说明张冠李戴（比如 xrand 显示成别的函数的注释）。
    """
    # 从函数定义往前找最近的一段注释，允许中间隔着空白与预处理指令
    # （很多 C 文件写成：分区注释 → #define → 函数）
    j = src.rfind('/*', 0, max(0, pos - 4000))   # 先定位到更早的搜索起点
    j = src.rfind('/*', 0, pos - 1)              # 最近一个注释开头
    while j >= 0:                                # 逐个往前试
        end = src.find('*/', j + 2)              # 该注释的结尾
        if end < 0:                              # 注释没闭合，放弃
            return ''
        between = src[end + 2:pos]               # 注释与函数之间的内容
        # 只允许空白、空注释、预处理指令；一旦出现真正的代码就说明这段注释不是给本函数的
        ok = True
        for line in between.split('\n'):
            s = line.strip()
            if not s:                            # 空行
                continue
            if s.startswith('#') or s.startswith('//'):   # 预处理指令或行注释
                continue
            ok = False                            # 出现代码
            break
        if ok:
            body = src[j + 2:end]                # 去掉 /* 与 */
            line_start = src.rfind('\n', 0, j) + 1
            if not src[line_start:j].strip():    # 注释必须独占行首，排除行尾注释
                return body
            return ''                            # 行尾注释不算函数说明
        j = src.rfind('/*', 0, j)                # 再往前找
    return ''


def parse_c(path):
    """解析 C：函数名、前导注释、内部调用的函数名。"""
    try:
        src = io.open(path, encoding='utf-8', errors='ignore').read()
    except Exception:
        return []

    # 先保留注释用于提取说明，再用去注释版本找函数边界
    clean = re.sub(r'/\*.*?\*/', lambda m: ' ' * len(m.group(0)), src, flags=re.S)
    clean = re.sub(r'//[^\n]*', lambda m: ' ' * len(m.group(0)), clean)
    clean = re.sub(r'"(?:\\.|[^"\\])*"', '""', clean)

    pat = re.compile(r'^[ \t]*(?:static\s+|inline\s+|extern\s+)*(?:[A-Za-z_][\w \t]*?\**)\s+'
                     r'([A-Za-z_]\w*)\s*\([^;{)]*\)\s*\{', re.M)
    matches = list(pat.finditer(clean))
    out = []
    for idx, m in enumerate(matches):
        name = m.group(1)
        if name in C_KEYWORDS:
            continue
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(clean)
        body = clean[m.end():body_end]
        calls = set()
        for cm in re.finditer(r'\b([A-Za-z_]\w*)\s*\(', body):
            c = cm.group(1)
            if c in C_KEYWORDS or c == name:
                continue
            calls.add(c)
        # 取紧邻函数上方的那段注释；中间夹着代码就不算（避免抓到上个函数体内的注释）
        doc = first_sentence(prev_comment(src, m.start()))
        # 清洗后只剩空白的（纯横线）才丢弃，有文字的保留（如"矩阵乘法（累加语义）"）
        if doc and not doc.strip(' -=*'):
            doc = ''
        # 不做"取函数体内第一条注释"的兜底：实测会张冠李戴（取到别的函数的注释），
        # 宁可显示"无说明"，也不能显示错的说明。
        out.append({'name': name, 'doc': doc, 'calls': sorted(calls),
                    'line': src[:m.start()].count('\n') + 1})
    return out


def main():
    """主流程：扫描 → 解析 → 汇总 → 写 JSON。"""
    funcs = []
    for rel, ap, ext in walk(('.py', '.c')):
        items = parse_py(ap) if ext == '.py' else parse_c(ap)
        for it in items:
            funcs.append({
                'id': '%s::%s' % (rel, it['name']),
                'name': it['name'],
                'file': rel,
                'lang': 'py' if ext == '.py' else 'c',
                'doc': it['doc'],
                'calls': it['calls'],
                'line': it.get('line', 0),
            })

    # 统计"被调用次数"，用来衡量一个函数有多关键
    call_count = {}
    for f in funcs:
        for c in f['calls']:
            call_count[c] = call_count.get(c, 0) + 1
    for f in funcs:
        f['in_degree'] = call_count.get(f['name'], 0)

    data = {'generated': time.strftime('%Y-%m-%d %H:%M'), 'functions': funcs}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, indent=1)

    print('已生成 %s' % OUT)
    print('函数 %d 个，文件 %d 个' % (len(funcs), len({f['file'] for f in funcs})))


if __name__ == '__main__':
    main()
