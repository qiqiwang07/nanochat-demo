"""给 chat.html 加实时进度提示：显示已等待秒数 + 阶段文字，避免"看起来没反应"。"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\bin\chat.html'
t = io.open(P, encoding='utf-8').read()

# 1) 加等待提示的 CSS
old_css = """  .loading { display: flex; gap: 4px; padding: 6px 0; align-items: center; }"""
new_css = """  .loading { display: flex; gap: 4px; padding: 6px 0; align-items: center; }
  /* 等待提示：告诉用户已经过了多久，否则 7B 模型几十秒不出字会让人以为没发出去 */
  .waiting { display: flex; align-items: center; gap: 8px; color: var(--text-2); font-size: 13.5px; }
  .waiting .sec { color: var(--accent); font-variant-numeric: tabular-nums; font-weight: 500; }"""
assert old_css in t
t = t.replace(old_css, new_css, 1)

# 2) 把加载动画替换成带秒数的提示
old_loading = """  const { bubble, meta } = addRow('ai');                   // 预留 AI 气泡，后面往里填
  bubble.innerHTML = '<div class="loading"><span></span><span></span><span></span></div>';  // 先显示三个点"""
new_loading = """  const { bubble, meta } = addRow('ai');                   // 预留 AI 气泡，后面往里填
  // 显示"三个点 + 已等待 N 秒"，让用户知道请求确实发出去了
  bubble.innerHTML = '<div class="waiting">' +
    '<span class="loading"><span></span><span></span><span></span></span>' +
    '<span class="tip">正在检索知识库…</span>' +
    '<span class="sec">0s</span></div>';
  const waitStart = Date.now();                            // 记录起始时间
  const secEl = bubble.querySelector('.sec');              // 秒数显示
  const tipEl = bubble.querySelector('.tip');              // 阶段文字
  const timer = setInterval(() => {                        // 每秒刷新一次
    const s = Math.floor((Date.now() - waitStart) / 1000); // 已等待秒数
    if (secEl) secEl.textContent = s + 's';                // 更新秒数
    if (tipEl) {                                           // 分阶段提示，让等待有进度感
      if (s < 8) tipEl.textContent = '正在检索知识库…';
      else if (s < 35) tipEl.textContent = '模型正在读题…';
      else tipEl.textContent = '模型正在思考，7B 模型在 CPU 上较慢，请稍候…';
    }
  }, 1000);"""
assert old_loading in t
t = t.replace(old_loading, new_loading, 1)

# 3) 首帧到达时清掉计时器
old_start = """          if (!started) { started = true; bubble.textContent = ''; }  // 第一帧到达，清掉加载动画"""
new_start = """          if (!started) {
            started = true;
            clearInterval(timer);                          // 停止计时
            bubble.textContent = '';                       // 清掉等待提示
          }"""
assert old_start in t
t = t.replace(old_start, new_start, 1)

# 4) 结束时无论如何都要清计时器
old_end = """  } catch (e) {
    if (!acc) bubble.textContent = '连接失败，请稍后重试';   // 一个字都没收到才提示失败
  }"""
new_end = """  } catch (e) {
    if (!acc) bubble.textContent = '连接失败，请稍后重试';   // 一个字都没收到才提示失败
  }
  clearInterval(timer);                                    // 无论成功失败都停止计时，避免定时器泄漏"""
assert old_end in t
t = t.replace(old_end, new_end, 1)

# 5) 修掉结束判定：原来看 textContent 是否含 'loading'，现在文本已经变了
old_final = """  if (!acc) {                                              // 流结束但没有任何内容
    if (!bubble.textContent || bubble.textContent.includes('loading')) {
      bubble.textContent = '（没有收到回复）';              // 明确告知
    }
  } else {"""
new_final = """  if (!acc) {                                              // 流结束但没有任何内容
    if (!started && !bubble.textContent.includes('连接失败')) {  // 一直没收到内容，也没报错
      bubble.textContent = '（没有收到回复，可能是后端超时）';   // 明确告知
    }
  } else {"""
assert old_final in t
t = t.replace(old_final, new_final, 1)

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('chat.html 已加入实时进度提示')
