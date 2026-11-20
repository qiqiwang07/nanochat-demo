# -*- coding: utf-8 -*-
"""修正同名函数下拉选择与 URL hash 支持，避免上一次补丁引入不存在的函数。"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\make_callgraph_html.py'
t = io.open(P, encoding='utf-8').read()

# 1) renderSingle 支持指定第几个同名定义
t = t.replace('function renderSingle(name){', 'function renderSingle(name, pick){', 1)
t = t.replace('  const f = cands[0];\n', '  const f = cands[pick || 0] || cands[0];\n', 1)

# 2) 下拉框回调改成调用 renderSingle
t = t.replace(
    "    dup.onchange = () => { const k = +dup.value; if (cands[k]) renderOne(cands[k], cands.filter((_, j) => j === k)); };",
    "    dup.onchange = () => { renderSingle(f.name, +dup.value); };", 1)

# 3) 下拉框要选中当前项
t = t.replace(
    "    dup.innerHTML = cands.map((x, i) => '<option value=\"' + i + '\">' + esc(x.file) + ':' + x.line + '</option>').join('');",
    "    dup.innerHTML = cands.map((x, i) => '<option value=\"' + i + '\"' +\n"
    "      ((pick || 0) === i ? ' selected' : '') + '>' + esc(x.file) + ':' + x.line + '</option>').join('');", 1)

# 4) 启动时支持 #global，方便直接打开全局视图
t = t.replace(
    "renderSingle('forward');",
    "if (location.hash === '#global') {   /* 直接打开全局视图 */\n"
    "  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('on', x.dataset.view === 'global'));\n"
    "  view = 'global'; renderGlobal('');\n"
    "} else {\n"
    "  renderSingle('forward');\n"
    "}", 1)

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已修正')
