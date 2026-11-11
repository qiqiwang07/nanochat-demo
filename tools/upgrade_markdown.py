# -*- coding: utf-8 -*-
"""重写 chat.html 的 Markdown 渲染器，支持标题/列表/引用/表格/粗斜体/公式，并加对应样式。"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\bin\chat.html'
t = io.open(P, encoding='utf-8').read()

NEW_RENDER = r'''function renderMD(text) {
  // 把模型输出的 Markdown 渲染成 HTML。
  // 为什么不用第三方库：整个页面要能在内网/离线环境跑，不引外部 CDN。
  let s = escapeHtml(text);                                // 先整体转义，后面再插入受控标签

  const blocks = [];                                       // 暂存代码块，避免被后续规则破坏
  const maths = [];                                        // 暂存公式，最后按行内/块级还原

  // 1) 代码块 ```lang\n...\n```
  s = s.replace(/```([a-zA-Z0-9+#]*)\n?([\s\S]*?)```/g, (m, lang, code) => {
    const i = blocks.length;                               // 记录序号
    blocks.push({ lang: lang || 'text', code: code.replace(/\n$/, '') });  // 去掉末尾换行
    return `\u0000B${i}\u0000`;                            // 占位符
  });

  // 2) 公式：先抽出来，避免里面的 * _ \ 被当成 Markdown
  //    块级 $$...$$ 或 \[...\]
  s = s.replace(/\$\$([\s\S]+?)\$\$/g, (m, e) => {
    const i = maths.length; maths.push({ block: true, tex: e.trim() });
    return `\u0000M${i}\u0000`;
  });
  s = s.replace(/\\\[([\s\S]+?)\\\]/g, (m, e) => {
    const i = maths.length; maths.push({ block: true, tex: e.trim() });
    return `\u0000M${i}\u0000`;
  });
  //    行内 \(...\) 或 $...$
  s = s.replace(/\\\(([\s\S]+?)\\\)/g, (m, e) => {
    const i = maths.length; maths.push({ block: false, tex: e.trim() });
    return `\u0000M${i}\u0000`;
  });
  s = s.replace(/\$([^$\n]+?)\$/g, (m, e) => {
    const i = maths.length; maths.push({ block: false, tex: e.trim() });
    return `\u0000M${i}\u0000`;
  });

  // 3) 标题：# ~ ######
  s = s.replace(/^######\s+(.+)$/gm, '<h5>$1</h5>');
  s = s.replace(/^#####\s+(.+)$/gm, '<h5>$1</h5>');
  s = s.replace(/^####\s+(.+)$/gm, '<h4>$1</h4>');
  s = s.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
  s = s.replace(/^##\s+(.+)$/gm, '<h3>$1</h3>');
  s = s.replace(/^#\s+(.+)$/gm, '<h3>$1</h3>');

  // 4) 分隔线
  s = s.replace(/^\s*(---|\*\*\*|___)\s*$/gm, '<hr>');

  // 5) 引用块
  s = s.replace(/^&gt;\s?(.*)$/gm, '<blockquote>$1</blockquote>');
  s = s.replace(/<\/blockquote>\n<blockquote>/g, '<br>');

  // 6) 行内代码（在粗斜体之前，避免里面的符号被处理）
  const inlines = [];
  s = s.replace(/`([^`\n]+)`/g, (m, code) => {
    const i = inlines.length; inlines.push(code);
    return `\u0000C${i}\u0000`;
  });

  // 7) 粗体、斜体、删除线
  s = s.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/__([^_\n]+)__/g, '<strong>$1</strong>');
  s = s.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '<em>$1</em>');
  s = s.replace(/~~([^~\n]+)~~/g, '<del>$1</del>');

  // 8) 表格：连续的 | a | b | 行
  s = s.replace(/((?:^\s*\|.*\|\s*$\n?){2,})/gm, (m) => {
    const rows = m.trim().split('\n').filter(r => r.trim());  // 逐行
    if (rows.length < 2) return m;                             // 至少两行才算表格
    let html = '<div class="tablewrap"><table>';
    rows.forEach((row, idx) => {
      const cells = row.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map(c => c.trim());
      if (cells.every(c => /^:?-{2,}:?$/.test(c))) return;      // 跳过分隔行 |---|---|
      const tag = idx === 0 ? 'th' : 'td';                     // 第一行当表头
      html += '<tr>' + cells.map(c => `<${tag}>${c}</${tag}>`).join('') + '</tr>';
    });
    return html + '</table></div>';
  });

  // 9) 列表：先处理无序，再处理有序
  s = s.replace(/^[ \t]*[-*+]\s+(.+)$/gm, '<li>$1</li>');
  s = s.replace(/(<li>[\s\S]*?<\/li>)(?!\s*<li>)/g, '<ul>$1</ul>');
  s = s.replace(/^[ \t]*\d+[.)]\s+(.+)$/gm, '<li>$1</li>');
  s = s.replace(/(<li>[\s\S]*?<\/li>)(?!\s*<li>)/g, (m) => {
    return m.includes('<ul>') ? m : '<ol>' + m + '</ol>';     // 避免把已有 ul 再包一层
  });
  // 合并被段落标签切碎的连续 li
  s = s.replace(/<\/li>\s*\n\s*<li>/g, '</li><li>');

  // 10) 段落：按空行切分
  s = s.split(/\n{2,}/).map(p => {
    const trimmed = p.trim();
    if (!trimmed) return '';
    if (/^<(h\d|ul|ol|li|div|blockquote|hr|table)/.test(trimmed)) return trimmed;  // 已是块级元素
    if (trimmed.includes('\u0000B') && trimmed.length < 40) return trimmed;        // 纯代码块占位
    return '<p>' + trimmed.replace(/\n/g, '<br>') + '</p>';  // 普通段落，段内换行用 br
  }).join('');

  // 11) 还原行内代码
  s = s.replace(/\u0000C(\d+)\u0000/g, (m, i) => `<code class="ic">${escapeHtml(inlines[i])}</code>`);

  // 12) 还原公式：去掉 LaTeX 定界符和常见命令，按代码样式显示
  s = s.replace(/\u0000M(\d+)\u0000/g, (m, i) => {
    const it = maths[i];
    let tex = it.tex;
    tex = tex.replace(/^\s*\\displaystyle\s*/, '');                       // 去样式命令
    tex = tex.replace(/\\boxed\s*\{([^{}]*)\}/g, '$1');                   // \boxed{x} → x
    tex = tex.replace(/\\text\s*\{([^{}]*)\}/g, '$1');                    // \text{中文} → 中文
    tex = tex.replace(/\\mathrm\s*\{([^{}]*)\}/g, '$1');
    tex = tex.replace(/\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, '($1)/($2)');  // 分数改成 a/b
    tex = tex.replace(/\\sqrt\s*\{([^{}]*)\}/g, '√($1)');
    tex = tex.replace(/\\(cdot|times)/g, '×');
    tex = tex.replace(/\\div/g, '÷');
    tex = tex.replace(/\\(le|leq)/g, '≤');
    tex = tex.replace(/\\(ge|geq)/g, '≥');
    tex = tex.replace(/\\neq/g, '≠');
    tex = tex.replace(/\\pm/g, '±');
    tex = tex.replace(/\\infty/g, '∞');
    tex = tex.replace(/\\sum/g, 'Σ');
    tex = tex.replace(/\\int/g, '∫');
    tex = tex.replace(/\\(alpha|beta|gamma|delta|theta|lambda|mu|pi|sigma|omega)/g, (mm, g) => {
      const greek = { alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', theta: 'θ',
                      lambda: 'λ', mu: 'μ', pi: 'π', sigma: 'σ', omega: 'ω' };
      return greek[g] || g;
    });
    tex = tex.replace(/\\[a-zA-Z]+\s*/g, '');                             // 其余未知命令直接丢掉
    tex = tex.replace(/[{}]/g, ' ');                                      // 花括号改成空格
    tex = tex.replace(/\s+/g, ' ').trim();                                // 压缩空白
    const cls = it.block ? 'mathblock' : 'mathin';
    return `<code class="${cls}">${escapeHtml(tex)}</code>`;
  });

  // 13) 还原代码块
  s = s.replace(/\u0000B(\d+)\u0000/g, (m, i) => {
    const b = blocks[i];
    return `<div class="codebox"><div class="codehead"><span>${escapeHtml(b.lang)}</span>` +
           `<button class="cp" onclick="copyCode(this)">复制</button></div>` +
           `<pre>${escapeHtml(b.code)}</pre></div>`;          // 代码二次转义，防注入
  });

  return s;                                                  // 返回渲染好的 HTML
}
'''

start = t.find('function renderMD(text) {')
end = t.find('window.copyCode')
if start < 0 or end < 0 or end <= start:
    raise SystemExit('找不到 renderMD 区间')
t = t[:start] + NEW_RENDER + '\n' + t[end:]

# 追加样式（插在 </style> 之前）
CSS = '''
  /* ---- Markdown 渲染样式：让标题、列表、引用、表格、公式都好看 ---- */
  .bubble h3 { font-size: 16.5px; font-weight: 600; margin: 18px 0 8px; color: var(--text); }
  .bubble h4, .bubble h5 { font-size: 15.5px; font-weight: 600; margin: 14px 0 6px; }
  .bubble h3:first-child, .bubble h4:first-child { margin-top: 0; }
  .bubble ul, .bubble ol { margin: 8px 0 10px; padding-left: 24px; }
  .bubble li { margin: 5px 0; line-height: 1.7; }
  .bubble ul li { list-style: disc; }
  .bubble ol li { list-style: decimal; }
  .bubble blockquote {
    border-left: 3px solid var(--accent);
    background: var(--accent-soft);
    margin: 10px 0; padding: 8px 14px; border-radius: 0 8px 8px 0;
    color: var(--text-2);
  }
  .bubble hr { border: none; border-top: 1px solid var(--line); margin: 16px 0; }
  .bubble em { font-style: italic; }
  .bubble del { text-decoration: line-through; opacity: .65; }
  .bubble .tablewrap { overflow-x: auto; margin: 10px 0; }
  .bubble table { border-collapse: collapse; font-size: 14px; min-width: 50%; }
  .bubble th, .bubble td { border: 1px solid var(--code-border); padding: 6px 12px; text-align: left; }
  .bubble th { background: var(--code-bg); font-weight: 600; }
  /* 公式：没有引入 KaTeX，用等宽字体 + 底色呈现，可读且不依赖网络 */
  .bubble code.mathin {
    background: var(--code-bg); border: 1px solid var(--code-border);
    padding: 1px 6px; border-radius: 5px; font-size: 13.5px;
    font-family: "Cambria Math", "Latin Modern Math", Consolas, monospace; color: var(--text);
  }
  .bubble code.mathblock {
    display: block; background: var(--code-bg); border: 1px solid var(--code-border);
    padding: 10px 14px; border-radius: 8px; margin: 10px 0;
    font-size: 13.5px; white-space: pre-wrap;
    font-family: "Cambria Math", "Latin Modern Math", Consolas, monospace; color: var(--text);
  }
'''
t = t.replace('</style>', CSS + '</style>', 1)

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('渲染器已重写，样式已追加')
