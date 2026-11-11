// 从 chat.html 抽出 renderMD，用 Node 直接测渲染结果（无需浏览器）
const fs = require('fs');
const path = 'C:/Users/Lenovo/ai/nanochat-demo/bin/chat.html';
const html = fs.readFileSync(path, 'utf8');

// 取出 escapeHtml 与 renderMD 两个函数
function grab(name) {
  const start = html.indexOf('function ' + name + '(');
  if (start < 0) throw new Error('找不到 ' + name);
  let depth = 0, i = html.indexOf('{', start);
  const begin = start;
  for (let j = i; j < html.length; j++) {
    if (html[j] === '{') depth++;
    else if (html[j] === '}') { depth--; if (depth === 0) return html.slice(begin, j + 1); }
  }
  throw new Error('括号不匹配: ' + name);
}

const code = grab('escapeHtml') + '\n' + grab('renderMD') + '\nmodule.exports = { renderMD };';
const sandbox = { module: { exports: {} } };
const fn = new Function('module', code + '\nreturn module.exports;');
const { renderMD } = fn(sandbox.module);

const sample = [
  '### 一、什么是正交矩阵',
  '',
  '正交矩阵满足 **Q^T Q = I**，也可以写成 \\(Q^{-1} = Q^T\\)。',
  '',
  '- 行列式为 ±1',
  '- 列向量构成标准正交基',
  '',
  '1. 第一步',
  '2. 第二步',
  '',
  '> 注意：这里容易搞混。',
  '',
  '| 名称 | 性质 |',
  '|---|---|',
  '| 正交 | 保长度 |',
  '',
  '```python',
  'print("hi")',
  '```',
  '',
  '最终答案：\\boxed{3}',
].join('\n');

const out = renderMD(sample);
console.log('===== 渲染后的 HTML =====');
console.log(out);
console.log();
console.log('===== 检查项 =====');
const checks = [
  ['标题 h3', /<h3>一、什么是正交矩阵<\/h3>/],
  ['粗体 strong', /<strong>Q\^T Q = I<\/strong>/],
  ['行内公式 mathin', /class="mathin"/],
  ['无序列表 ul', /<ul>\s*<li>/],
  ['有序列表 ol', /<ol>\s*<li>/],
  ['引用 blockquote', /<blockquote>/],
  ['表格 table', /<table>/],
  ['代码块 codebox', /class="codebox"/],
  ['boxed 转成 3', />3</],
  ['无残留占位符', /^(?![\s\S]*\u0000)/],
];
let ok = 0;
for (const [name, re] of checks) {
  const pass = re.test(out);
  if (pass) ok++;
  console.log((pass ? '  ✅ ' : '  ❌ ') + name);
}
console.log('\n通过 ' + ok + '/' + checks.length);
