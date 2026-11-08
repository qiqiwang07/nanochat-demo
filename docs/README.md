# nanochat-demo：用纯 C 训练和查询 AI

这个目录里全部是 **C 语言程序**，不依赖 Python、PyTorch 或 BLAS。
编译器：MinGW gcc（`C:\mingw64\bin\gcc.exe`）。

---

## 一、`nanogpt.c` —— 自己的 GPT，前向 / 反向 / AdamW 全在 C 里

一个 decoder-only Transformer（字节级词表），手写解析梯度，无第三方数值库。

```powershell
gcc -O3 -march=native -fopenmp -o nanogpt.exe nanogpt.c -lm

.\nanogpt.exe check  corpus.txt                       # 梯度检查（数值 vs 解析）
.\nanogpt.exe train  corpus.txt 1500 demo.bin         # 训练 1500 步并存权重
.\nanogpt.exe sample corpus.txt demo.bin "The "       # 加载权重续写
.\nanogpt.exe resume corpus.txt demo.bin 300 out.bin  # 断点续训
.\nanogpt.exe chat   dialog_corpus.txt chat2.bin      # 对话（交互式）
.\nanogpt.exe chat   dialog_corpus.txt chat2.bin "你好"   # 对话（单次）
.\nanogpt.exe ask    math_corpus.txt math.bin "题目"   # 解题（模仿格式）
```

**反向传播经过验证**：`nanogpt_dbl.c` 是同一份代码的双精度版本（`float`→`double`），
用方向导数法检查 20 个参数张量，最大相对误差 1.07e-2，其中 `lm_head`/`lm_bias` 达 4.8e-8。
float32 版里 10%~25% 的偏差来自浮点噪声和 ReLU 折点，不是公式错误。

### 训练结果

| 语料 | 模型 | 步数 | loss | 验证 loss | 耗时 |
|---|---|---|---|---|---|
| ClimbMix 网页文本 4 MB | 2 层 / 宽 64 / 上下文 64 / 0.116M 参数 | 3000 | 4.56 → 1.61 | 1.771 | 2.4 分钟 |
| smol-smoltalk 对话 6 MB | 4 层 / 宽 128 / 上下文 256 / 0.85M 参数 | 1600 | 4.57 → 1.49 | 1.391 | 24 分钟 |
| cn-k12 题目解答 1 MB | 4 层 / 宽 128 / 上下文 256 / 0.89M 参数 | 1500 | 5.55 → 0.93 | **0.896** | 20 分钟 |

速度约 40~50 GFLOPS（OpenMP 多线程），比同机 PyTorch CPU 版快约 20 倍。

**结论（重要）**：0.85M 参数的中文/英文模型只能模仿语言形式，**不会真正解题**。
给它做过的题，它会输出格式正确的 LaTeX 答案，但数字基本是错的——它学的是"答案长什么样"，
而不是推理。想做真正的作业助手，请看下面的 `solver.c`。

---

## 二、`solver.c` —— 作业助手（这个是真的能用）

```powershell
gcc -O2 -o solver.exe solver.c -lm
.\solver.exe                                          # 交互模式
.\solver.exe calc  "12+15*3"                          # 精确算术
.\solver.exe solve "2x+3=7"                           # 一元一次方程
.\solver.exe ask   "一件衣服打八折后多少钱？"           # 相似题检索
```

三种能力：

1. **精确算术**：`+ - * / ^ % ( )`，百分号是后缀（`200*80% = 160`）。递归下降解析器，结果精确。
2. **一元一次方程**：解析成 `ax+b` 形式求解。`3x-1=x/2+4` → `x = 2`。
3. **题型规则引擎**（工具增强的核心）：识别中文题面里的题型和数字角色，直接列式并精确计算，
   输出会带上「列式」，每个结果都能手工核对。支持：

   | 题型 | 例子 | 列式 |
   |---|---|---|
   | 折扣 · 求现价 | 原价 200 元，打八折多少钱 | `200*80% = 160` |
   | 折扣 · 求原价 | 打七五折后 45 元，原价多少 | `45/75% = 60` |
   | 折扣 · 方向不确定 | 只给折扣和一个金额 | 给出式子和提醒 |
   | 百分比 · 降价/涨价 | 原价 300，降价 20%，现价 | `300*(1-20%) = 240` |
   | 总价 | 每千克 6 元，买 5 千克 | `6*5 = 30` |
   | 求剩余 | 12 个苹果吃了 3 个 | `12-3 = 9` |
   | 求和 | 一班 40 人，二班 38 人，共多少人 | `40+38 = 78` |
   | 平均数 | 五次成绩 85/90/95/88/92，平均分 | `(85+90+95+88+92)/5 = 90` |
   | 行程 · 求路程 | 速度 60，行驶 3 小时 | `60*3 = 180` |

   中文数字（八折、七五折、百分之二十、三个）都做了 UTF-8 解码支持。
4. **相似题检索**（兜底）：题型认不出来时，题库是 **195,179 道中文小学数学应用题**
   （`db_questions.txt` / `db_answers.txt`，每题带标准答案和列式）。用**字符三元组 +
   TF-IDF 余弦相似度**匹配，返回最相似的 3 道题及其解法，并明确标注"仅供参考"。

**这三分工是关键**：规则负责"看懂题型"，计算器负责"算数"，检索负责"找不到题型时给参考"。
所有数字都来自精确计算，不是模型编的——这就是"工具增强的小模型"与"直接让模型算"的本质区别。

### 题库来源
`MU-NLPC/Calc-ape210k`（Hugging Face，经 hf-mirror 下载），字段
`question_chinese` / `result` / `equation`。

---

## 三、其它文件

| 文件 | 说明 |
|---|---|
| `corpus.txt` | 网页文本语料（从 climbmix 分片提取） |
| `dialog_corpus.txt` | 对话语料（从 smol-smoltalk 导出，`### User:` / `### Assistant:` 格式） |
| `math_corpus.txt` | 题目解答语料（从 cn-k12 导出，`### Problem:` / `### Solution:`） |
| `ape210k.parquet` / `cn_k12.parquet` | 下载的原始数据集 |
| `nanogpt_dbl.c` / `nanogpt_dbl.exe` | 双精度版本，仅用于梯度验证 |
| `demo.bin` / `chat.bin` / `chat2.bin` / `math.bin` | 训练好的权重（含 AdamW 动量，可续训） |
| `logs\` | 各次训练的完整日志 |

## 四、已知限制

- **不具备推理能力**：所有神经网络部分都只是"语言形式模仿器"。
- **检索不是理解**：相似题助手给出的是题库里的原答案，需要学生自己对应题意。
- 没有 GPU，训练/推理都是 CPU；注意力是朴素 O(T²) 实现，上下文越长越慢。
- `solver.exe` 在中文 Windows 上会把命令行参数从 GBK 转成 UTF-8；若你的控制台已是
  UTF-8（`chcp 65001`），程序会自动识别并跳过转换。
