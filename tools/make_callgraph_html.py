# -*- coding: utf-8 -*-
"""
 * 文件名：make_callgraph_html.py
 * 作用：把 docs/call_graph.json 渲染成可交互的示意图页面 bin/callgraph.html
 * 依赖：Python 3.8+ 标准库
 * 作者：qiqiwang07
 * 更新：2026-11-20
 *
 * 页面形态（对应手绘草图）：
 *   左列：小方框 = 被调用的各个函数
 *   右列：大方框 = 当前这个函数「做了什么」
 *   中间：弯曲箭头汇聚，鼠标悬停箭头显示这一次调用的详情
 *   第二个视图：全局总览，按文件聚合，显示一天的调用热度
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'docs', 'call_graph.json')
OUT = os.path.join(ROOT, 'bin', 'callgraph.html')

TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>函数调用示意图</title>
<style>
  :root {
    --line: #1a1a1a; --bg: #ffffff; --weak: #9aa0a6;
    --accent: #1a6fff; --soft: #eef4ff;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: #1f2329;
    font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  }
  header {
    display: flex; align-items: center; gap: 16px;
    padding: 14px 22px; border-bottom: 1px solid #eee; flex-wrap: wrap;
  }
  header h1 { font-size: 17px; margin: 0; font-weight: 600; }
  .tabs { display: flex; gap: 6px; margin-left: auto; }
  .tab {
    padding: 6px 16px; border: 1px solid #ddd; border-radius: 20px;
    background: #fff; cursor: pointer; font-size: 13px; color: #444;
  }
  .tab.on { background: var(--accent); border-color: var(--accent); color: #fff; }
  .bar { display: flex; gap: 10px; align-items: center; padding: 10px 22px; flex-wrap: wrap; }
  .bar input {
    flex: 0 0 320px; padding: 7px 12px; border: 1px solid #ddd;
    border-radius: 8px; font-size: 13px; outline: none;
  }
  .bar input:focus { border-color: var(--accent); }
  .hint { font-size: 12px; color: var(--weak); }
  #stage { padding: 6px 22px 40px; overflow: auto; }
  svg text { font-family: inherit; }
  .box { fill: #fff; stroke: var(--line); stroke-width: 2.2; }
  .box.big { stroke-width: 2.6; }
  .box:hover { fill: var(--soft); }
  .link { fill: none; stroke: var(--line); stroke-width: 1.6; opacity: .55; cursor: pointer; }
  .link:hover { stroke: var(--accent); stroke-width: 2.6; opacity: 1; }
  .ttl { font-size: 13px; fill: #1f2329; pointer-events: none; }
  .sub { font-size: 11px; fill: var(--weak); pointer-events: none; }
  #tip {
    position: fixed; pointer-events: none; z-index: 99; max-width: 420px;
    background: rgba(24,26,30,.95); color: #fff; padding: 10px 13px;
    border-radius: 8px; font-size: 12.5px; line-height: 1.6; opacity: 0;
    transition: opacity .12s; box-shadow: 0 6px 22px rgba(0,0,0,.25);
  }
  #tip b { color: #8fc0ff; }
  .legend { font-size: 12px; color: var(--weak); padding: 0 22px 10px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; padding: 0 22px 30px; }
  .card { border: 1.6px solid var(--line); border-radius: 12px; padding: 10px 12px; cursor: default; }
  .card:hover { background: var(--soft); }
  .card .n { font-size: 13.5px; font-weight: 600; }
  .card .d { font-size: 12px; color: #555; margin-top: 4px; line-height: 1.5; }
  .card .m { font-size: 11px; color: var(--weak); margin-top: 6px; }
</style>
</head>
<body>
<header>
  <h1>函数调用示意图</h1>
  <div class="tabs">
    <button class="tab on" data-view="single">一个函数做了什么</button>
    <button class="tab" data-view="global">全部函数（一天下来）</button>
  </div>
</header>

<div class="bar" id="bar">
  <input id="q" placeholder="搜索函数名，例如 forward / load_weights / retrieve">
  <span class="hint" id="hint"></span>
</div>

<div id="stage"></div>
<div class="legend" id="legend"></div>
<div class="grid" id="grid" style="display:none"></div>

<div id="tip"></div>

<script>
const DATA = __DATA__;   /* 由生成脚本注入 */
const FUNCS = DATA.functions;
const byName = new Map();          /* 函数名 → 所有同名定义 */
FUNCS.forEach(f => {
  if (!byName.has(f.name)) byName.set(f.name, []);
  byName.get(f.name).push(f);
});

const tip = document.getElementById('tip');
function showTip(evt, html) {      /* 跟随鼠标显示提示 */
  tip.innerHTML = html;
  tip.style.opacity = 1;
  const pad = 14;
  let x = evt.clientX + pad, y = evt.clientY + pad;
  const r = tip.getBoundingClientRect();
  if (x + r.width > window.innerWidth - 8) x = evt.clientX - r.width - pad;
  if (y + r.height > window.innerHeight - 8) y = evt.clientY - r.height - pad;
  tip.style.left = x + 'px';
  tip.style.top = y + 'px';
}
function hideTip() { tip.style.opacity = 0; }

function esc(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/* ---------------- 视图一：一个函数做了什么 ---------------- */
function renderSingle(fnName) {
  const cands = byName.get(fnName) || [];
  const stage = document.getElementById('stage');
  const grid = document.getElementById('grid');
  const legend = document.getElementById('legend');
  grid.style.display = 'none';
  stage.style.display = 'block';

  if (!cands.length) {              /* 没找到 */
    stage.innerHTML = '<p style="color:#888;padding:20px">没有找到名为 ' + esc(fnName) + ' 的函数</p>';
    legend.textContent = '';
    document.getElementById('hint').textContent = '共 ' + FUNCS.length + ' 个函数';
    return;
  }

  const f = cands[0];               /* 默认取第一个同名定义 */
  const callees = [];               /* 左侧小框：它调用的函数 */
  const seen = new Set();
  f.calls.forEach(c => {
    if (seen.has(c)) return;
    seen.add(c);
    const defs = byName.get(c) || [];
    callees.push({ name: c, doc: defs.length ? defs[0].doc : '', file: defs.length ? defs[0].file : '', deg: defs.length ? defs[0].in_degree : 0, known: defs.length > 0 });
  });
  callees.sort((a, b) => b.deg - a.deg);   /* 被调用次数多的排前面 */

  const rows = Math.max(callees.length, 1);
  const rowH = 74;                          /* 每行高度 */
  const W = 1000;
  const H = Math.max(320, rows * rowH + 80);
  const leftX = 30, leftW = 210, leftH = 46;
  const rightX = 620, rightW = 330, rightH = 130;
  const rightY = Math.max(30, (H - rightH) / 2);

  let svg = '<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '">';
  svg += '<defs><marker id="ar" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
       + '<path d="M0,0 L10,4 L0,8 z" fill="#1a1a1a"/></marker></defs>';

  /* 左侧小框 + 曲线 */
  callees.forEach((c, i) => {
    const y = 40 + i * rowH;
    const cy = y + leftH / 2;
    /* 贝塞尔曲线：从小框右边出发，先向右再弯向大框左侧 */
    const x1 = leftX + leftW, y1 = cy;
    const x2 = rightX - 6, y2 = rightY + rightH / 2 + (i - (callees.length - 1) / 2) * 16;
    const mx = (x1 + x2) / 2;
    const d = 'M' + x1 + ',' + y1 + ' C' + (mx - 40) + ',' + y1 + ' ' + (mx + 10) + ',' + y2 + ' ' + x2 + ',' + y2;
    svg += '<path class="link" d="' + d + '" marker-end="url(#ar)" data-i="' + i + '"></path>';

    svg += '<rect class="box" x="' + leftX + '" y="' + y + '" width="' + leftW + '" height="' + leftH + '" rx="10"></rect>';
    svg += '<text class="ttl" x="' + (leftX + 12) + '" y="' + (y + 20) + '">' + esc(c.name) + '</text>';
    svg += '<text class="sub" x="' + (leftX + 12) + '" y="' + (y + 36) + '">'
         + (c.known ? '被调用 ' + c.deg + ' 次' : '未找到定义（库函数）') + '</text>';
  });

  /* 右侧大框：当前函数 */
  svg += '<rect class="box big" x="' + rightX + '" y="' + rightY + '" width="' + rightW + '" height="' + rightH + '" rx="14"></rect>';
  svg += '<text class="ttl" x="' + (rightX + 16) + '" y="' + (rightY + 26) + '" style="font-size:15px;font-weight:600">'
       + esc(f.name) + '()</text>';
  const docLines = wrapText(f.doc || '（这个函数没有写说明）', 26).slice(0, 3);
  docLines.forEach((ln, i) => {
    svg += '<text class="sub" x="' + (rightX + 16) + '" y="' + (rightY + 50 + i * 18) + '" style="font-size:12px;fill:#555">'
         + esc(ln) + '</text>';
  });
  svg += '<text class="sub" x="' + (rightX + 16) + '" y="' + (rightY + rightH - 14) + '">'
       + esc(f.file) + ':' + f.line + ' · 调用了 ' + f.calls.length + ' 个函数</text>';
  svg += '</svg>';

  stage.innerHTML = svg;

  /* 悬停到曲线上显示这次调用的详情 */
  stage.querySelectorAll('path.link').forEach(p => {
    const c = callees[+p.dataset.i];
    p.addEventListener('mousemove', ev => {
      showTip(ev, '<b>' + esc(c.name) + '</b><br>' +
        (c.known ? esc(c.file) + '<br>' : '<span style="color:#ffcf80">找不到定义，可能是库函数</span><br>') +
        '<span style="opacity:.85">' + esc(c.doc || '（无说明）') + '</span>' +
        (c.known ? '<br><span style="opacity:.7">全项目被调用 ' + c.deg + ' 次</span>' : ''));
    });
    p.addEventListener('mouseleave', hideTip);
  });

  document.getElementById('hint').textContent =
    '当前：' + f.name + '（' + f.file + '） · 左侧 ' + callees.length + ' 个被调用函数';
  legend.textContent = '把鼠标放到弯曲箭头上可以看这次调用的详情；同名函数有 ' +
    (cands.length > 1 ? cands.length + ' 个定义，当前展示第一个' : '1 个定义');
}

function wrapText(s, per) {
  const out = [];
  let cur = '';
  for (const ch of String(s)) {
    cur += ch;
    if (cur.length >= per) { out.push(cur); cur = ''; }
  }
  if (cur) out.push(cur);
  return out;
}

/* ---------------- 视图二：全部函数（一天下来） ---------------- */
function renderGlobal(filter) {
  const stage = document.getElementById('stage');
  const grid = document.getElementById('grid');
  const legend = document.getElementById('legend');
  stage.style.display = 'none';
  grid.style.display = 'grid';

  const kw = (filter || '').trim().toLowerCase();
  const list = FUNCS.filter(f => !kw || f.name.toLowerCase().includes(kw) || f.file.toLowerCase().includes(kw));
  const sorted = list.slice().sort((a, b) => b.in_degree - a.in_degree || a.name.localeCompare(b.name));

  grid.innerHTML = sorted.slice(0, 400).map(f =>
    '<div class="card" data-id="' + esc(f.id) + '">' +
      '<div class="n">' + esc(f.name) + '</div>' +
      '<div class="d">' + esc(f.doc || '（无说明）') + '</div>' +
      '<div class="m">' + esc(f.file) + ' · 调用 ' + f.calls.length + ' 个 · 被调用 ' + f.in_degree + ' 次</div>' +
    '</div>').join('');

  document.getElementById('hint').textContent = '共 ' + list.length + ' 个函数，按被调用次数排序（最多显示 400 个）';
  legend.textContent = '点击任意卡片，查看这个函数「做了什么」的示意图';

  grid.querySelectorAll('.card').forEach(card => {
    card.addEventListener('click', () => {
      const id = card.dataset.id;
      const f = FUNCS.find(x => x.id === id);
      if (!f) return;
      document.querySelectorAll('.tab').forEach(t => t.classList.toggle('on', t.dataset.view === 'single'));
      document.getElementById('q').value = f.name;
      renderSingle(f.name);
    });
  });
}

/* ---------------- 交互 ---------------- */
let view = 'single';
document.querySelectorAll('.tab').forEach(t => {
  t.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('on'));
    t.classList.add('on');
    view = t.dataset.view;
    const v = document.getElementById('q').value;
    if (view === 'single') renderSingle(v || 'forward');
    else renderGlobal(v);
  });
});

const q = document.getElementById('q');
let timer = null;
q.addEventListener('input', () => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    if (view === 'single') renderSingle(q.value || 'forward');
    else renderGlobal(q.value);
  }, 220);
});

/* 启动：默认展示项目主流程里的 forward */
renderSingle('forward');
</script>
</body>
</html>
'''


def main():
    """读数据 → 注入模板 → 写 HTML。"""
    if not os.path.exists(DATA):
        raise SystemExit('缺少 %s，请先运行 tools/gen_call_graph.py' % DATA)
    data = json.load(io.open(DATA, encoding='utf-8'))
    html = TEMPLATE.replace('__DATA__', json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, 'w', encoding='utf-8').write(html)
    size = os.path.getsize(OUT)
    print('已生成 %s（%.1f KB，%d 个函数）' % (OUT, size / 1024, len(data['functions'])))


if __name__ == '__main__':
    main()
