# -*- coding: utf-8 -*-
"""让拖拽使用 pointer capture：鼠标移出方框后仍能继续拖（否则一离开就断）。"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\make_callgraph_html.py'
t = io.open(P, encoding='utf-8').read()

OLD = """    g.addEventListener('pointerdown', ev => {
      ev.preventDefault();
      const pt = svgPoint(svgEl, ev);
      drag = { key: key, g: g, grab: pt.y - node.y, moved: false };
      g.classList.add('dragging');
    });"""
NEW = """    g.addEventListener('pointerdown', ev => {
      ev.preventDefault();
      const pt = svgPoint(svgEl, ev);
      drag = { key: key, g: g, grab: pt.y - node.y, moved: false };
      g.classList.add('dragging');
      try { g.setPointerCapture(ev.pointerId); } catch (e) {}   /* 捕获指针，移出方框也能继续拖 */
    });"""
assert OLD in t, '未匹配 pointerdown'
t = t.replace(OLD, NEW, 1)

OLD2 = """    g.addEventListener('pointerup', endDrag);
    g.addEventListener('pointerleave', ev => { if (drag && drag.key === key && ev.buttons === 0) endDrag(); });"""
NEW2 = """    g.addEventListener('pointerup', ev => {
      try { g.releasePointerCapture(ev.pointerId); } catch (e) {}
      endDrag();
    });
    g.addEventListener('pointercancel', endDrag);"""
assert OLD2 in t, '未匹配 pointerup'
t = t.replace(OLD2, NEW2, 1)

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已加入指针捕获')
