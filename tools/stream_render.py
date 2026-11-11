# -*- coding: utf-8 -*-
"""流式输出时边生成边渲染 Markdown（节流），而不是先显示纯文本再一次性替换。"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\bin\chat.html'
t = io.open(P, encoding='utf-8').read()

old = '''        if (obj.delta) {                                   // 文本增量帧
          if (!started) {
            started = true;
            clearInterval(timer);                          // 停止计时
            bubble.textContent = '';                       // 清掉等待提示
          }
          acc += obj.delta;                                // 累积完整回答
          bubble.textContent = acc;                        // 流式阶段用纯文本，避免半截 Markdown 渲染错乱
          scrollBottom();                                  // 跟着滚动
        }'''

new = '''        if (obj.delta) {                                   // 文本增量帧
          if (!started) {
            started = true;
            clearInterval(timer);                          // 停止计时
            bubble.textContent = '';                       // 清掉等待提示
            lastRender = 0;                                // 重置渲染时间戳
          }
          acc += obj.delta;                                // 累积完整回答
          const now = Date.now();                          // 当前时间
          // 每 500ms 渲染一次，兼顾"看得见格式"和"不卡顿"；段落未写完时渲染也不会崩
          if (acc.length > 120 && now - lastRender > 500) {
            bubble.innerHTML = renderMD(acc);              // 边生成边渲染
            lastRender = now;                              // 记录渲染时刻
          } else {
            bubble.textContent = acc;                      // 还没到渲染间隔就先显示纯文本
          }
          scrollBottom();                                  // 跟着滚动
        }'''

assert old in t, '未找到流式渲染片段'
t = t.replace(old, new, 1)

# 声明 lastRender
old2 = '''  let acc = '', usage = null, sid = current, started = false;  // 累积文本、用量、会话ID、是否已开始'''
new2 = '''  let acc = '', usage = null, sid = current, started = false;  // 累积文本、用量、会话ID、是否已开始
  let lastRender = 0;                                      // 上次渲染时间，用于节流'''
assert old2 in t, '未找到 acc 声明'
t = t.replace(old2, new2, 1)

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已开启流式渲染')
