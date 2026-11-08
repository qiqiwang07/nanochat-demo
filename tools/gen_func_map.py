#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
 * 文件名：gen_func_map.py
 * 作用：扫描项目所有 .py / .c 文件，生成函数调用关系文档 docs/FUNC_MAP.md
 * 依赖：Python 3.8+ 标准库（ast、re、os）
 * 作者：qiqiwang07
 * 更新：2026-11-07
"""
import ast  # 解析 Python 源码，得到函数定义与调用关系
import os  # 拼路径、遍历目录
import re  # 正则匹配 C 语言的函数定义与调用
import sys  # 退出码

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录
OUT_DIR = os.path.join(ROOT, 'docs')  # 文档输出目录
OUT_FILE = os.path.join(OUT_DIR, 'FUNC_MAP.md')  # 最终生成的 markdown 文件

# 扫描时跳过的目录，避免把第三方库和虚拟环境也算进来
SKIP_DIRS = {'.git', '.venv', 'node_modules', '__pycache__', 'build', 'dist',
             'venv', 'site-packages', 'LAwPY', 'elements of math', '.ipynb_checkpoints'}

# C 语言里看起来像语句的关键字，用于排除误判为函数调用的词
C_KEYWORDS = {'if', 'for', 'while', 'switch', 'return', 'sizeof', 'else', 'do', 'case'}


def walk_sources():
    """遍历项目，产出 (相对路径, 绝对路径, 扩展名) 三元组。"""
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # 就地过滤目录，避免递归进去
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.')]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in ('.py', '.c', '.h'):
                continue
            abspath = os.path.join(dirpath, fn)
            relpath = os.path.relpath(abspath, ROOT).replace('\\', '/')
            yield relpath, abspath, ext


def parse_python(path):
    """用 ast 解析 Python 文件，返回 {函数名: {"calls": set(), "calls_raw": set()}}。"""
    try:
        # 读源码；errors="ignore" 防止个别乱码字节让整份文件解析失败
        src = open(path, encoding='utf-8', errors='ignore').read()
        tree = ast.parse(src)  # 构建语法树
    except Exception as e:
        print('跳过（解析失败）%s: %s' % (path, e), file=sys.stderr)
        return {}

    funcs = {}  # 收集本文件里定义的所有函数
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            calls = set()  # 本函数内部调用的函数名（直接调用）
            calls_raw = set()  # 包括 self.xxx 这种带点的调用，保留原始写法
            # 遍历函数体里的每个节点，找 Call 表达式
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                fn = sub.func  # 被调用者的表达式
                if isinstance(fn, ast.Name):
                    calls.add(fn.id)  # 直接调用：foo()
                elif isinstance(fn, ast.Attribute):
                    # 形如 obj.method()；obj 是 Name 时记录 obj.method
                    base = ''
                    if isinstance(fn.value, ast.Name):
                        base = fn.value.id + '.'
                    calls_raw.add(base + fn.attr)
            funcs[node.name] = {'calls': calls, 'calls_raw': calls_raw}
    return funcs


def strip_comments_and_strings(text):
    """把 C 源码里的注释和字符串替换成空格，避免关键字误判。"""
    # 去掉块注释
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    # 去掉行注释
    text = re.sub(r'//[^\n]*', ' ', text)
    # 去掉字符串字面量（含转义）
    text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", "''", text)
    return text


def parse_c(path):
    """用正则解析 C 文件，返回 {函数名: {"calls": set(), "calls_raw": set()}}。"""
    try:
        src = open(path, encoding='utf-8', errors='ignore').read()
    except Exception as e:
        print('跳过（读取失败）%s: %s' % (path, e), file=sys.stderr)
        return {}

    clean = strip_comments_and_strings(src)  # 先清掉注释和字符串
    funcs = {}

    # 匹配函数定义：类型 函数名(参数) {     —— 粗略匹配，够用
    pattern = re.compile(
        r'^[ \t]*(?:static\s+|inline\s+|extern\s+)*'
        r'(?:[A-Za-z_][\w \t]*?\**)\s+'      # 返回类型
        r'([A-Za-z_]\w*)\s*\([^;{)]*\)\s*\{',  # 函数名 + 参数表 + 左花括号
        re.M)

    matches = list(pattern.finditer(clean))
    for idx, m in enumerate(matches):
        name = m.group(1)  # 函数名
        if name in C_KEYWORDS:
            continue
        body_start = m.end()  # 函数体起点（左花括号之后）
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(clean)
        body = clean[body_start:body_end]  # 粗略的函数体范围

        # 在函数体内找所有 xxx( 形式的调用
        calls = set()
        for cm in re.finditer(r'\b([A-Za-z_]\w*)\s*\(', body):
            callee = cm.group(1)
            if callee in C_KEYWORDS or callee == name:
                continue
            calls.add(callee)
        funcs[name] = {'calls': calls, 'calls_raw': set()}
    return funcs


def build_reverse(all_funcs):
    """构造反向索引：{被调用函数: [调用它的函数...]}，用于"谁调用了它"。"""
    rev = {}
    for fpath, funcs in all_funcs.items():
        for fname, info in funcs.items():
            all_calls = set(info['calls'])  # 直接调用集合
            all_calls |= {c.split('.')[-1] for c in info['calls_raw']}  # 把 obj.method 也归一化成 method
            for c in all_calls:
                rev.setdefault(c, []).append('%s :: %s' % (fpath, fname))
    return rev


def main():
    """主流程：扫描 → 解析 → 汇总 → 写 markdown。"""
    all_funcs = {}  # {相对路径: {函数名: 信息}}

    print('扫描 %s ...' % ROOT)
    for relpath, abspath, ext in sorted(walk_sources()):
        if ext == '.py':
            funcs = parse_python(abspath)  # Python 走 ast
        else:
            funcs = parse_c(abspath)  # C 走正则
        if funcs:
            all_funcs[relpath] = funcs
            print('  %-52s %3d 个函数' % (relpath, len(funcs)))

    rev = build_reverse(all_funcs)  # 反向索引

    os.makedirs(OUT_DIR, exist_ok=True)  # 确保 docs 目录存在
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write('# 函数调用关系表\n\n')
        f.write('> 本文档由 `tools/gen_func_map.py` 自动生成，**请勿手工编辑**。\n')
        f.write('> 重新生成：`python tools/gen_func_map.py`\n\n')

        total_funcs = sum(len(v) for v in all_funcs.values())
        total_calls = sum(len(i['calls']) + len(i['calls_raw']) for v in all_funcs.values() for i in v.values())
        f.write('## 总览\n\n')
        f.write('| 指标 | 数值 |\n|---|---|\n')
        f.write('| 文件数 | %d |\n' % len(all_funcs))
        f.write('| 函数总数 | %d |\n' % total_funcs)
        f.write('| 调用关系统计 | %d 条 |\n\n' % total_calls)

        f.write('| 文件 | 函数数 |\n|---|---|\n')
        for path in sorted(all_funcs):
            f.write('| `%s` | %d |\n' % (path, len(all_funcs[path])))
        f.write('\n')

        # 逐文件展开
        for path in sorted(all_funcs):
            funcs = all_funcs[path]
            f.write('---\n\n## `%s`\n\n' % path)
            for fname in sorted(funcs):
                info = funcs[fname]
                calls = set(info['calls'])
                calls |= {c.split('.')[-1] for c in info['calls_raw']}
                calls.discard(fname)  # 去掉自调用，避免噪声

                f.write('### `%s()`\n\n' % fname)
                if calls:
                    f.write('**调用：** %s\n\n' % '、'.join('`%s`' % c for c in sorted(calls)))
                else:
                    f.write('**调用：** 无（叶子函数）\n\n')

                # 谁调用了它（可能跨文件）
                callers = rev.get(fname, [])
                callers = [c for c in callers if not c.endswith(':: ' + fname)]
                if callers:
                    uniq = sorted(set(callers))
                    f.write('**被调用：** %s\n\n' % '、'.join('`%s`' % c for c in uniq[:12]))
                else:
                    f.write('**被调用：** 无（入口函数或未被引用）\n\n')

    print('\n已生成: %s' % OUT_FILE)
    print('文件 %d 个，函数 %d 个' % (len(all_funcs), total_funcs))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
