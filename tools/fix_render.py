# -*- coding: utf-8 -*-
"""修正渲染器的三个问题：ul/ol 嵌套错误、裸 \\boxed 不转换、指数花括号丢分组。"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\bin\chat.html'
t = io.open(P, encoding='utf-8').read()

# 1) 列表改成逐行解析，避免 ul 被 ol 再包一层
old_list = '''  // 9) 列表：先处理无序，再处理有序
  s = s.replace(/^[ \\t]*[-*+]\\s+(.+)$/gm, '<li>$1</li>');
  s = s.replace(/(<li>[\\s\\S]*?<\\/li>)(?!\\s*<li>)/g, '<ul>$1</ul>');
  s = s.replace(/^[ \\t]*\\d+[.)]\\s+(.+)$/gm, '<li>$1</li>');
  s = s.replace(/(<li>[\\s\\S]*?<\\/li>)(?!\\s*<li>)/g, (m) => {
    return m.includes('<ul>') ? m : '<ol>' + m + '</ol>';     // 避免把已有 ul 再包一层
  });
  // 合并被段落标签切碎的连续 li
  s = s.replace(/<\\/li>\\s*\\n\\s*<li>/g, '</li><li>');'''

new_list = '''  // 9) 列表：逐行解析，边扫边开关 ul/ol，避免两种列表互相嵌套
  {
    const src = s.split('\\n');                              // 按行拆开
    const dst = [];                                          // 输出行
    let typ = null;                                          // 当前所在列表类型
    const close = () => { if (typ) { dst.push('</' + typ + '>'); typ = null; } };  // 结束当前列表
    for (const ln of src) {
      const mu = ln.match(/^[ \\t]*[-*+]\\s+(.+)$/);          // 无序项
      const mo = ln.match(/^[ \\t]*\\d+[.)]\\s+(.+)$/);       // 有序项
      if (mu || mo) {
        const want = mu ? 'ul' : 'ol';                       // 目标类型
        if (typ !== want) { close(); dst.push('<' + want + '>'); typ = want; }  // 类型变了就换标签
        dst.push('<li>' + (mu ? mu[1] : mo[1]) + '</li>');   // 追加列表项
      } else {
        close();                                             // 非列表行，先关掉列表
        dst.push(ln);                                        // 原样输出
      }
    }
    close();                                                 // 收尾关闭
    s = dst.join('\\n');
  }'''
assert old_list in t, '未找到列表段'
t = t.replace(old_list, new_list, 1)

# 2) 公式里先把 ^{...} / _{...} 转成 ^(...) / _(...)，保住分组
old_math = '''    tex = tex.replace(/[{}]/g, ' ');                                      // 花括号改成空格'''
new_math = '''    // 上标/下标的花括号转成括号，保住分组：Q^{-1} → Q^(-1)
    tex = tex.replace(/\\^\\s*\\{([^{}]*)\\}/g, '^($1)');
    tex = tex.replace(/_\\s*\\{([^{}]*)\\}/g, '_($1)');
    tex = tex.replace(/[{}]/g, ' ');                                      // 剩余花括号改成空格'''
assert old_math in t, '未找到公式花括号处理'
t = t.replace(old_math, new_math, 1)

# 3) 正文里裸的 \boxed{...} 也转成醒目的答案
old_boxed = '''  // 10) 段落：按空行切分'''
new_boxed = '''  // 9.5) 正文里没被公式包裹的 \\boxed{答案} 也高亮出来（数学题常用）
  s = s.replace(/\\\\boxed\\s*\\{([^{}]*)\\}/g, '<strong class="answer">$1</strong>');

  // 10) 段落：按空行切分'''
assert old_boxed in t, '未找到段落切分'
t = t.replace(old_boxed, new_boxed, 1)

# 4) 答案样式
old_css = '''  .bubble code.mathblock {'''
new_css = '''  .bubble strong.answer {
    display: inline-block; background: #fff4d6; color: #8a5a00;
    border: 1px solid #f0d089; padding: 2px 10px; border-radius: 6px;
    font-weight: 700; font-size: 15px;
  }
  @media (prefers-color-scheme: dark) {
    .bubble strong.answer { background: #3a2f12; color: #ffd479; border-color: #6b5420; }
  }
  .bubble code.mathblock {'''
assert old_css in t, '未找到公式样式锚点'
t = t.replace(old_css, new_css, 1)

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('渲染器已修正')
