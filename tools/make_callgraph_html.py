# -*- coding: utf-8 -*-
"""
 * 文件名：make_callgraph_html.py
 * 作用：把 docs/call_graph.json 渲染成可交互的「多列方框」示意图
 * 作者：qiqiwang07
 * 更新：2026-11-20
 *
 * 布局规则（按需求）：
 *   1. 每一个函数都是独立的一个方框
 *   2. 同类函数排在同一列：
 *        - 单函数视图：左列=调用者，中列=当前函数，右列=被调用者
 *        - 全局视图：每个文件一列，文件内所有函数排在该列
 *   3. 鼠标悬停在方框或连线上都会显示详情
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
  :root { --line:#1a1a1a; --weak:#9aa0a6; --accent:#1a6fff; --soft:#eef4ff; }
  * { box-sizing: border-box; }
  body { margin:0; background:#fff; color:#1f2329;
         font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; }
  header { display:flex; align-items:center; gap:16px; padding:14px 22px;
           border-bottom:1px solid #eee; flex-wrap:wrap; }
  header h1 { font-size:17px; margin:0; font-weight:600; }
  .tabs { display:flex; gap:6px; margin-left:auto; }
  .tab { padding:6px 16px; border:1px solid #ddd; border-radius:20px;
         background:#fff; cursor:pointer; font-size:13px; color:#444; }
  .tab.on { background:var(--accent); border-color:var(--accent); color:#fff; }
  .bar { display:flex; gap:10px; align-items:center; padding:10px 22px; flex-wrap:wrap; }
  .bar input { flex:0 0 340px; padding:7px 12px; border:1px solid #ddd;
               border-radius:8px; font-size:13px; outline:none; }
  .bar input:focus { border-color:var(--accent); }
  .hint { font-size:12px; color:var(--weak); }
  #stage { overflow:auto; padding:0 0 40px; }
  svg text { font-family:inherit; }
  .box { fill:#fff; stroke:var(--line); stroke-width:2; cursor:pointer; }
  .box:hover { fill:var(--soft); }
  .box.cur { fill:#e8f0ff; stroke-width:2.8; }
  .link { fill:none; stroke:#3a3a3a; stroke-width:1.5; opacity:.5; cursor:pointer; }
  .link:hover { stroke:var(--accent); stroke-width:2.6; opacity:1; }
  .t { font-size:12.5px; fill:#1f2329; pointer-events:none; }
  .s { font-size:10.5px; fill:#8a9099; pointer-events:none; }
  .colhead { font-size:13px; font-weight:600; fill:#444; }
  .colsub { font-size:11px; fill:#9aa0a6; }
  #tip { position:fixed; pointer-events:none; z-index:99; max-width:440px;
         background:rgba(24,26,30,.96); color:#fff; padding:10px 13px;
         border-radius:8px; font-size:12.5px; line-height:1.65; opacity:0;
         transition:opacity .12s; box-shadow:0 6px 22px rgba(0,0,0,.28); }
  #tip b { color:#8fc0ff; }
</style>
</head>
<body>
<header>
  <h1>函数调用示意图</h1>
  <div class="tabs">
    <button class="tab on" data-view="single">一个函数</button>
    <button class="tab" data-view="global">全部函数</button>
  </div>
</header>
<div class="bar">
  <input id="q" placeholder="输入函数名，例如 forward / load_weights / retrieve">
  <select id="dup" style="display:none;padding:7px 10px;border:1px solid #ddd;border-radius:8px;font-size:12.5px"></select>
  <span class="hint" id="hint"></span>
</div>
<div id="stage"></div>
<div id="tip"></div>

<script>
const DATA = __DATA__;
const FUNCS = DATA.functions;
const byName = new Map();          /* 名字 → 定义列表 */
FUNCS.forEach(f => {
  if (!byName.has(f.name)) byName.set(f.name, []);
  byName.get(f.name).push(f);
});

const tip = document.getElementById('tip');
function docLine(f){
  /* 有说明就显示说明，没有就显示调用统计，避免满屏无说明 */
  if (f.doc) return f.doc.length > 26 ? f.doc.slice(0, 26) + '…' : f.doc;
  return '调用 ' + (f.calls ? f.calls.length : 0) + ' 个 · 被调用 ' + (f.in_degree || 0) + ' 次';
}

function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function showTip(e, html){
  tip.innerHTML = html; tip.style.opacity = 1;
  const pad=14, r=tip.getBoundingClientRect();
  let x=e.clientX+pad, y=e.clientY+pad;
  if (x+r.width  > innerWidth-8)  x = e.clientX-r.width-pad;
  if (y+r.height > innerHeight-8) y = e.clientY-r.height-pad;
  tip.style.left=x+'px'; tip.style.top=y+'px';
}
function hideTip(){ tip.style.opacity=0; }

/* 方框尺寸与列间距 */
const BW = 200, BH = 50, GAP = 14, COLGAP = 150, TOP = 74;

/* 画一列函数方框，返回每个方框的中心 y */
function drawColumn(svg, x, list, head, sub, curName, clickable){
  let out = [];
  svg.push('<text class="colhead" x="' + x + '" y="30">' + esc(head) + '</text>');
  if (sub) svg.push('<text class="colsub" x="' + x + '" y="48">' + esc(sub) + '</text>');
  list.forEach((f, i) => {
    const y = TOP + i * (BH + GAP);
    const isCur = (f.name === curName);
    svg.push('<rect class="box' + (isCur ? ' cur' : '') + '" data-id="' + esc(f.id || '') +
             '" x="' + x + '" y="' + y + '" width="' + BW + '" height="' + BH + '" rx="10"></rect>');
    svg.push('<text class="t" x="' + (x + 12) + '" y="' + (y + 21) + '">' +
             esc(f.name.length > 22 ? f.name.slice(0, 21) + '…' : f.name) + '()</text>');
    svg.push('<text class="s" x="' + (x + 12) + '" y="' + (y + 37) + '">' +
             esc(docLine(f)) + '</text>');
    out.push({ f: f, x: x, y: y, cy: y + BH / 2 });
  });
  return out;
}

/* 画连线：从 (x1,y1) 到 (x2,y2) 的三次贝塞尔 */
function drawLink(svg, x1, y1, x2, y2, label, idx){
  const mx = (x1 + x2) / 2;
  const d = 'M' + x1 + ',' + y1 + ' C' + (mx - 30) + ',' + y1 + ' ' + (mx + 30) + ',' + y2 + ' ' + x2 + ',' + y2;
  svg.push('<path class="link" d="' + d + '" marker-end="url(#ar)" data-i="' + idx + '"></path>');
}

/* ---------------- 视图一：一个函数（三列，每个函数一个方框） ---------------- */
function renderSingle(name, pick){
  const cands = byName.get(name) || [];
  const stage = document.getElementById('stage');
  if (!cands.length){
    stage.innerHTML = '<p style="color:#888;padding:24px">没有找到名为 ' + esc(name) + ' 的函数</p>';
    document.getElementById('hint').textContent = '共 ' + FUNCS.length + ' 个函数';
    return;
  }
  const f = cands[pick || 0] || cands[0];
  /* 同名函数可能有多个定义（不同文件），给一个下拉让人选 */
  const dup = document.getElementById('dup');
  if (cands.length > 1) {
    dup.style.display = '';
    dup.innerHTML = cands.map((x, i) => '<option value="' + i + '"' +
      ((pick || 0) === i ? ' selected' : '') + '>' + esc(x.file) + ':' + x.line + '</option>').join('');
    dup.onchange = () => { renderSingle(f.name, +dup.value); };
  } else { dup.style.display = 'none'; }
  /* 调用者：全项目里调用了这个名字的函数（去重） */
  const callers = FUNCS.filter(x => x.calls.includes(f.name) && x.name !== f.name)
                       .filter((x, i, a) => a.findIndex(y => y.name === x.name) === i)
                       .slice(0, 14);
  /* 被调用者：当前函数调用的每个函数（去重，保留未定义条目） */
  const callees = [];
  const seen = new Set();
  f.calls.forEach(c => {
    if (seen.has(c)) return;
    seen.add(c);
    const def = (byName.get(c) || [])[0];
    callees.push(def || { id: 'ext::' + c, name: c, doc: '库函数 / 未找到定义', file: '', in_degree: 0 });
  });
  callees.sort((a, b) => (b.in_degree || 0) - (a.in_degree || 0));

  const rows = Math.max(callers.length, callees.length, 1);
  const W = 40 + BW + COLGAP + BW + COLGAP + BW + 60;
  const H = TOP + rows * (BH + GAP) + 40;
  const x1 = 30, x2 = x1 + BW + COLGAP, x3 = x2 + BW + COLGAP;

  const svg = [];
  svg.push('<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '">');
  svg.push('<defs><marker id="ar" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
         + '<path d="M0,0 L10,4 L0,8 z" fill="#3a3a3a"/></marker></defs>');

  const cLeft  = drawColumn(svg, x1, callers,  '调用者（谁调用它）', callers.length + ' 个', null, true);
  const cMid   = drawColumn(svg, x2, [f],      '这个函数', '(当前查看)', f.name, true);
  const cRight = drawColumn(svg, x3, callees,  '被调用者（它调用了谁）', callees.length + ' 个', null, true);

  /* 左 → 中 的线 */
  cLeft.forEach((c, i) => {
    drawLink(svg, c.x + BW, c.cy, x2 - 6, cMid[0].cy + (i - (cLeft.length-1)/2) * 10, '', 1000 + i);
  });
  /* 中 → 右 的线 */
  cRight.forEach((c, i) => {
    drawLink(svg, x2 + BW, cMid[0].cy + (i - (cRight.length-1)/2) * 10, c.x - 6, c.cy, '', i);
  });
  svg.push('</svg>');

  stage.innerHTML = svg.join('');

  /* 连线悬停：显示目标函数的详情 */
  stage.querySelectorAll('path.link').forEach(p => {
    const i = +p.dataset.i;
    const target = i >= 1000 ? callers[i - 1000] : callees[i];
    if (!target) return;
    p.addEventListener('mousemove', e => showTip(e, boxTip(target)));
    p.addEventListener('mouseleave', hideTip);
  });
  /* 方框悬停 */
  stage.querySelectorAll('rect.box').forEach(r => {
    const id = r.dataset.id;
    const obj = FUNCS.find(x => x.id === id) || callees.find(x => x.id === id);
    if (!obj) return;
    r.addEventListener('mousemove', e => showTip(e, boxTip(obj)));
    r.addEventListener('mouseleave', hideTip);
    r.addEventListener('click', () => {
      if (obj && obj.name) { document.getElementById('q').value = obj.name; renderSingle(obj.name); }
    });
  });

  document.getElementById('hint').textContent =
    f.name + '：调用者 ' + callers.length + ' 个 · 被调用 ' + callees.length + ' 个 · ' + f.file + ':' + f.line;
}

function boxTip(f){
  return '<b>' + esc(f.name) + '()</b><br>' +
    (f.file ? esc(f.file) + (f.line ? ':' + f.line : '') + '<br>' : '<span style="color:#ffcf80">库函数 / 未找到定义</span><br>') +
    '<span style="opacity:.88">' + esc(f.doc || '（无说明）') + '</span>' +
    '<br><span style="opacity:.68">调用 ' + (f.calls ? f.calls.length : 0) + ' 个 · 被调用 ' + (f.in_degree || 0) + ' 次</span>';
}

/* ---------------- 视图二：全部函数（按文件分列，每个函数一个方框） ---------------- */
function renderGlobal(filter){
  const stage = document.getElementById('stage');
  const kw = (filter || '').trim().toLowerCase();
  const list = FUNCS.filter(f => !kw || f.name.toLowerCase().includes(kw) || f.file.toLowerCase().includes(kw));

  /* 按文件分组 */
  const groups = new Map();
  list.forEach(f => {
    if (!groups.has(f.file)) groups.set(f.file, []);
    groups.get(f.file).push(f);
  });
  const files = [...groups.keys()].sort((a, b) => groups.get(b).length - groups.get(a).length);
  const maxRows = Math.max(...files.map(k => groups.get(k).length), 1);

  const W = 30 + files.length * (BW + COLGAP);
  const H = TOP + maxRows * (BH + GAP) + 40;
  const svg = [];
  svg.push('<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '">');
  svg.push('<defs><marker id="ar" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
         + '<path d="M0,0 L10,4 L0,8 z" fill="#3a3a3a"/></marker></defs>');

  const colIndex = new Map();   /* 文件 → 列号 */
  files.forEach((file, ci) => {
    const x = 30 + ci * (BW + COLGAP);
    colIndex.set(file, ci);
    const g = groups.get(file);
    svg.push('<text class="colhead" x="' + x + '" y="30">' + esc(file.split('/').pop()) + '</text>');
    svg.push('<text class="colsub" x="' + x + '" y="48">' + esc(file) + ' · ' + g.length + ' 个函数</text>');
    g.forEach((f, i) => {
      const y = TOP + i * (BH + GAP);
      f._cx = x; f._cy = y + BH / 2;
      svg.push('<rect class="box" data-id="' + esc(f.id) + '" x="' + x + '" y="' + y +
               '" width="' + BW + '" height="' + BH + '" rx="10"></rect>');
      svg.push('<text class="t" x="' + (x + 12) + '" y="' + (y + 21) + '">' +
               esc(f.name.length > 22 ? f.name.slice(0, 21) + '…' : f.name) + '()</text>');
      svg.push('<text class="s" x="' + (x + 12) + '" y="' + (y + 37) + '">' +
               esc(docLine(f)) + '</text>');
    });
  });

  /* 跨文件调用连线（只连不同文件的，避免同列乱线） */
  let li = 0;
  const drawn = [];
  list.forEach(f => {
    f.calls.forEach(cn => {
      const tgts = byName.get(cn) || [];
      tgts.forEach(t => {
        if (t.file === f.file) return;             /* 同文件不画，方框挨着看不清 */
        if (typeof f._cx !== 'number' || typeof t._cx !== 'number') return;
        if (li > 400) return;                       /* 限制条数，避免卡顿 */
        const d = 'M' + (f._cx + BW) + ',' + f._cy + ' C' + (f._cx + BW + 60) + ',' + f._cy +
                  ' ' + (t._cx - 60) + ',' + t._cy + ' ' + (t._cx - 4) + ',' + t._cy;
        svg.push('<path class="link" d="' + d + '" data-i="' + li + '" style="opacity:.22"></path>');
        drawn.push({ from: f, to: t });
        li++;
      });
    });
  });
  svg.push('</svg>');
  stage.innerHTML = svg.join('');

  stage.querySelectorAll('rect.box').forEach(r => {
    const obj = FUNCS.find(x => x.id === r.dataset.id);
    if (!obj) return;
    r.addEventListener('mousemove', e => showTip(e, boxTip(obj)));
    r.addEventListener('mouseleave', hideTip);
    r.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.toggle('on', t.dataset.view === 'single'));
      document.getElementById('q').value = obj.name;
      renderSingle(obj.name);
    });
  });
  stage.querySelectorAll('path.link').forEach(p => {
    const d = drawn[+p.dataset.i];
    if (!d) return;
    p.addEventListener('mousemove', e => showTip(e,
      '<b>' + esc(d.from.name) + ' → ' + esc(d.to.name) + '</b><br>' +
      esc(d.from.file) + '<br>↓<br>' + esc(d.to.file) + '<br><span style="opacity:.8">' +
      esc(d.to.doc || '（无说明）') + '</span>'));
    p.addEventListener('mouseleave', hideTip);
  });

  document.getElementById('hint').textContent =
    list.length + ' 个函数 / ' + files.length + ' 个文件（每个文件一列，同一文件的函数排在同一列）';
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
  timer = setTimeout(() => view === 'single' ? renderSingle(q.value || 'forward') : renderGlobal(q.value), 220);
});

if (location.hash === '#global') {   /* 直接打开全局视图 */
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('on', x.dataset.view === 'global'));
  view = 'global'; renderGlobal('');
} else {
  renderSingle('forward');
}
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
    print('已生成 %s（%.1f KB，%d 个函数）' % (OUT, os.path.getsize(OUT) / 1024, len(data['functions'])))


if __name__ == '__main__':
    main()
