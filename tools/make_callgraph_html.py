# -*- coding: utf-8 -*-
"""
 * 文件名：make_callgraph_html.py
 * 作用：渲染可拖拽的函数调用示意图
 * 作者：qiqiwang07
 * 更新：2026-11-20
 *
 * 布局与交互：
 *   1. 每个函数是一个方框，同类函数在同一列
 *   2. 方框可以在自己那一列里上下拖动，连线实时跟随
 *   3. 悬停方框/连线显示详情；点击方框跳转
 *   4. 拖动后的位置记在浏览器本地，刷新后保留
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
  * { box-sizing:border-box; }
  body { margin:0; background:#fff; color:#1f2329;
         font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
         user-select:none; }
  header { display:flex; align-items:center; gap:16px; padding:14px 22px;
           border-bottom:1px solid #eee; flex-wrap:wrap; }
  header h1 { font-size:17px; margin:0; font-weight:600; }
  .tabs { display:flex; gap:6px; margin-left:auto; }
  .tab { padding:6px 16px; border:1px solid #ddd; border-radius:20px;
         background:#fff; cursor:pointer; font-size:13px; color:#444; }
  .tab.on { background:var(--accent); border-color:var(--accent); color:#fff; }
  .bar { display:flex; gap:10px; align-items:center; padding:10px 22px; flex-wrap:wrap; }
  .bar input { flex:0 0 320px; padding:7px 12px; border:1px solid #ddd;
               border-radius:8px; font-size:13px; outline:none; }
  .bar input:focus { border-color:var(--accent); }
  .hint { font-size:12px; color:var(--weak); }
  #stage { overflow:auto; padding-bottom:40px; }
  svg text { font-family:inherit; }
  .node { cursor:grab; }
  .node:active { cursor:grabbing; }
  .box { fill:#fff; stroke:var(--line); stroke-width:2; }
  .node:hover .box { fill:var(--soft); }
  .node.cur .box { fill:#e8f0ff; stroke-width:2.8; }
  .node.dragging .box { stroke:var(--accent); stroke-width:2.8; }
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
const byName = new Map();
FUNCS.forEach(f => { if (!byName.has(f.name)) byName.set(f.name, []); byName.get(f.name).push(f); });

const BW = 200, BH = 50, GAP = 14, COLGAP = 150, TOP = 74, BOTTOMPAD = 40;

const tip = document.getElementById('tip');
const esc = s => String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

function showTip(e, html){
  tip.innerHTML = html; tip.style.opacity = 1;
  const pad = 14, r = tip.getBoundingClientRect();
  let x = e.clientX + pad, y = e.clientY + pad;
  if (x + r.width  > innerWidth  - 8) x = e.clientX - r.width  - pad;
  if (y + r.height > innerHeight - 8) y = e.clientY - r.height - pad;
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
}
const hideTip = () => { tip.style.opacity = 0; };

function docLine(f){
  if (f.doc) return f.doc.length > 26 ? f.doc.slice(0,26) + '…' : f.doc;
  return '调用 ' + (f.calls ? f.calls.length : 0) + ' 个 · 被调用 ' + (f.in_degree || 0) + ' 次';
}

function boxTip(f){
  return '<b>' + esc(f.name) + '()</b><br>' +
    (f.file ? esc(f.file) + (f.line ? ':' + f.line : '') + '<br>'
            : '<span style="color:#ffcf80">库函数 / 未找到定义</span><br>') +
    '<span style="opacity:.88">' + esc(f.doc || '（无说明）') + '</span><br>' +
    '<span style="opacity:.68">调用 ' + (f.calls ? f.calls.length : 0) +
    ' 个 · 被调用 ' + (f.in_degree || 0) + ' 次</span>';
}

/* ---------- 位置记忆 ---------- */
function posKey(id){ return 'cgpos2:' + (location.hash === '#global' ? 'g:' : 's:') + id; }
function loadPos(id){ const v = localStorage.getItem(posKey(id)); return v == null ? null : +v; }
function savePos(id, y){ try { localStorage.setItem(posKey(id), String(Math.round(y))); } catch(e){} }

/* ---------- 通用渲染器 ---------- */
function render(model){
  const cols = model.cols;
  const rows = Math.max(1, ...cols.map(c => c.nodes.length));
  const W = 30 + cols.length * (BW + COLGAP) + 40;
  const H = TOP + rows * (BH + GAP) + BOTTOMPAD;

  const svg = [];
  svg.push('<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '" id="cg">');
  svg.push('<defs><marker id="ar" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
         + '<path d="M0,0 L10,4 L0,8 z" fill="#3a3a3a"/></marker></defs>');

  const nodes = new Map();
  const edges = [];

  model.edges.forEach((e, i) => { svg.push('<path class="link" data-e="' + i + '" d=""></path>'); });

  cols.forEach((col, ci) => {
    const x = 30 + ci * (BW + COLGAP);
    svg.push('<text class="colhead" x="' + x + '" y="30">' + esc(col.head) + '</text>');
    if (col.sub) svg.push('<text class="colsub" x="' + x + '" y="48">' + esc(col.sub) + '</text>');
    col.nodes.forEach((f, i) => {
      let y = TOP + i * (BH + GAP);
      const saved = loadPos(f.key);
      if (saved != null) y = saved;
      svg.push('<g class="node' + (f.cur ? ' cur' : '') + '" data-key="' + esc(f.key) + '" transform="translate(0,' + y + ')">');
      svg.push('<rect class="box" x="' + x + '" y="0" width="' + BW + '" height="' + BH + '" rx="10"></rect>');
      svg.push('<text class="t" x="' + (x + 12) + '" y="21">' +
               esc(f.name.length > 22 ? f.name.slice(0,21) + '…' : f.name) + '()</text>');
      svg.push('<text class="s" x="' + (x + 12) + '" y="37">' + esc(docLine(f)) + '</text>');
      svg.push('</g>');
      nodes.set(f.key, { x: x, y: y, w: BW, h: BH, data: f });
    });
  });

  svg.push('</svg>');
  document.getElementById('stage').innerHTML = svg.join('');

  const svgEl = document.getElementById('cg');
  const paths = svgEl.querySelectorAll('path.link');
  model.edges.forEach((e, i) => edges.push({ from: e.from, to: e.to, el: paths[i] }));

  function refreshEdges(){
    edges.forEach(e => {
      const a = nodes.get(e.from), b = nodes.get(e.to);
      if (!a || !b) { e.el.setAttribute('d', ''); return; }
      const x1 = a.x + a.w, y1 = a.y + a.h / 2;
      const x2 = b.x - 4,   y2 = b.y + b.h / 2;
      if (x2 <= x1) { e.el.setAttribute('d', ''); return; }
      const mx = (x1 + x2) / 2;
      e.el.setAttribute('d',
        'M' + x1 + ',' + y1 + ' C' + (mx - 30) + ',' + y1 + ' ' + (mx + 30) + ',' + y2 + ' ' + x2 + ',' + y2);
    });
  }
  refreshEdges();

  /* ---------- 拖动 ---------- */
  let drag = null;
  svgEl.querySelectorAll('g.node').forEach(g => {
    const key = g.dataset.key;
    const node = nodes.get(key);

    g.addEventListener('pointerdown', ev => {
      ev.preventDefault();
      const pt = svgPoint(svgEl, ev);
      drag = { key: key, g: g, grab: pt.y - node.y, moved: false };
      g.classList.add('dragging');
      try { g.setPointerCapture(ev.pointerId); } catch (e) {}   /* 捕获指针，移出方框也能继续拖 */
    });
    g.addEventListener('pointermove', ev => {
      if (!drag || drag.key !== key) return;
      const pt = svgPoint(svgEl, ev);
      let ny = pt.y - drag.grab;
      ny = Math.max(TOP, Math.min(ny, H - BH - 10));   /* 只在本列垂直范围内移动 */
      if (Math.abs(ny - node.y) > 0.1) drag.moved = true;
      node.y = ny;
      g.setAttribute('transform', 'translate(0,' + ny + ')');
      refreshEdges();
    });
    const endDrag = () => {
      if (!drag || drag.key !== key) return;
      g.classList.remove('dragging');
      savePos(key, node.y);
      drag = null;
    };
    g.addEventListener('pointerup', ev => {
      try { g.releasePointerCapture(ev.pointerId); } catch (e) {}
      endDrag();
    });
    g.addEventListener('pointercancel', endDrag);

    g.addEventListener('mousemove', ev => { if (!drag) showTip(ev, boxTip(node.data)); });
    g.addEventListener('mouseleave', () => { if (!drag) hideTip(); });
    g.addEventListener('click', () => {
      if (drag && drag.moved) return;
      const f = node.data;
      if (!f.def) return;
      document.querySelectorAll('.tab').forEach(t => t.classList.toggle('on', t.dataset.view === 'single'));
      document.getElementById('q').value = f.name;
      renderSingle(f.name);
    });
  });

  edges.forEach(e => {
    e.el.addEventListener('mousemove', ev => {
      const a = nodes.get(e.from), b = nodes.get(e.to);
      if (!a || !b) return;
      showTip(ev, '<b>' + esc(a.data.name) + ' → ' + esc(b.data.name) + '</b><br>' +
        esc(a.data.file || '外部') + '<br>↓<br>' + esc(b.data.file || '外部') + '<br>' +
        '<span style="opacity:.8">' + esc(b.data.doc || '（无说明）') + '</span>');
    });
    e.el.addEventListener('mouseleave', hideTip);
  });
}

function svgPoint(svgEl, ev){
  const r = svgEl.getBoundingClientRect();
  return { x: ev.clientX - r.left, y: ev.clientY - r.top };
}

/* ---------- 视图一：一个函数 ---------- */
function renderSingle(name, pick){
  const cands = byName.get(name) || [];
  const dup = document.getElementById('dup');
  if (!cands.length){
    document.getElementById('stage').innerHTML =
      '<p style="color:#888;padding:24px">没有找到名为 ' + esc(name) + ' 的函数</p>';
    document.getElementById('hint').textContent = '共 ' + FUNCS.length + ' 个函数';
    return;
  }
  const f = cands[pick || 0] || cands[0];

  if (cands.length > 1){
    dup.style.display = '';
    dup.innerHTML = cands.map((x,i) => '<option value="' + i + '"' + ((pick||0)===i ? ' selected' : '') +
      '>' + esc(x.file) + ':' + x.line + '</option>').join('');
    dup.onchange = () => renderSingle(f.name, +dup.value);
  } else { dup.style.display = 'none'; }

  const callers = [];
  const seenC = new Set();
  FUNCS.forEach(x => {
    if (x.calls.includes(f.name) && x.name !== f.name && !seenC.has(x.name)){
      seenC.add(x.name);
      callers.push({ key: 'c:' + x.id, name: x.name, doc: x.doc, file: x.file, line: x.line,
                     calls: x.calls, in_degree: x.in_degree, def: x });
    }
  });
  callers.sort((a,b) => (b.in_degree||0) - (a.in_degree||0));

  const callees = [];
  const seenE = new Set();
  f.calls.forEach(c => {
    if (seenE.has(c)) return;
    seenE.add(c);
    const d = (byName.get(c) || [])[0];
    callees.push(d
      ? { key: 'e:' + d.id, name: d.name, doc: d.doc, file: d.file, line: d.line,
          calls: d.calls, in_degree: d.in_degree, def: d }
      : { key: 'x:' + c, name: c, doc: '', file: '', line: 0, calls: [], in_degree: 0, def: null });
  });
  callees.sort((a,b) => (b.in_degree||0) - (a.in_degree||0));

  const cur = { key: 'cur:' + f.id, name: f.name, doc: f.doc, file: f.file, line: f.line,
                calls: f.calls, in_degree: f.in_degree, def: f, cur: true };

  const edges = [];
  callers.forEach(c => edges.push({ from: c.key, to: cur.key }));
  callees.forEach(c => edges.push({ from: cur.key, to: c.key }));

  render({
    cols: [
      { head: '调用者（谁调用它）', sub: callers.length + ' 个', nodes: callers },
      { head: '这个函数', sub: '（当前查看）', nodes: [cur] },
      { head: '被调用者（它调用了谁）', sub: callees.length + ' 个', nodes: callees }
    ],
    edges: edges
  });

  document.getElementById('hint').textContent =
    f.name + '：调用者 ' + callers.length + ' 个 · 被调用 ' + callees.length +
    ' 个 · ' + f.file + ':' + f.line + '　（方框可在本列上下拖动）';
}

/* ---------- 视图二：全部函数 ---------- */
function renderGlobal(filter){
  const kw = (filter || '').trim().toLowerCase();
  const list = FUNCS.filter(f => !kw || f.name.toLowerCase().includes(kw) || f.file.toLowerCase().includes(kw));

  const groups = new Map();
  list.forEach(f => { if (!groups.has(f.file)) groups.set(f.file, []); groups.get(f.file).push(f); });
  const files = [...groups.keys()].sort((a,b) => groups.get(b).length - groups.get(a).length);

  const cols = files.map(file => ({
    head: file.split('/').pop(),
    sub: file + ' · ' + groups.get(file).length + ' 个函数',
    nodes: groups.get(file).map(f => ({
      key: 'g:' + f.id, name: f.name, doc: f.doc, file: f.file, line: f.line,
      calls: f.calls, in_degree: f.in_degree, def: f
    }))
  }));

  const keyByFile = new Map();
  cols.forEach((c, ci) => keyByFile.set(files[ci], c.nodes));
  const edges = [];
  let count = 0;
  cols.forEach((c, ci) => {
    c.nodes.forEach(f => {
      (f.calls || []).forEach(cn => {
        const tgts = byName.get(cn) || [];
        tgts.forEach(t => {
          if (count >= 300) return;
          if (t.file === files[ci]) return;
          const tn = (keyByFile.get(t.file) || []).find(x => x.name === t.name);
          if (!tn) return;
          edges.push({ from: f.key, to: tn.key });
          count++;
        });
      });
    });
  });

  render({ cols: cols, edges: edges });
  document.getElementById('hint').textContent =
    list.length + ' 个函数 / ' + files.length + ' 个文件（每个文件一列，方框可在本列上下拖动）';
}

/* ---------- 交互 ---------- */
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

if (location.hash === '#global'){
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
        raise SystemExit('缺少 %s' % DATA)
    data = json.load(io.open(DATA, encoding='utf-8'))
    html = TEMPLATE.replace('__DATA__', json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, 'w', encoding='utf-8').write(html)
    print('已生成 %s（%.1f KB）' % (OUT, os.path.getsize(OUT) / 1024))


if __name__ == '__main__':
    main()
