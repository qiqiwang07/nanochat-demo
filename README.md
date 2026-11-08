# nanochat-demo —— 用 C 从零训练和运行 AI

全部代码为 **C 语言**，不依赖 Python/PyTorch。模型在本机 CPU 上自己训练，网页/窗口界面也是 C 写的。

## 目录结构

```
nanochat-demo/
├── bin/      程序与运行时文件（可直接运行的 exe、网页、模型权重、题库、会话存档）
├── src/      C 源码
├── data/     训练语料与数据集（大文件，训练时才用）
├── tools/    辅助脚本（Python 生成语料、合并/构建脚本）
├── docs/     文档
├── logs/     训练日志
└── chargpt.exe  字符级训练程序（临时放在根目录）
```

### bin/ —— 直接运行这个目录里的东西

| 文件 | 作用 |
|---|---|
| `gui.exe` | 桌面窗口版对话程序（`AI 助手（纯 C）` 窗口） |
| `server.exe` | 网页版服务（带左侧会话栏的界面） |
| `chat.html` | 网页界面（左侧新会话 + 历史会话，右侧对话区） |
| `zhchat.bin` / `zhchat_corpus.txt` | 自己训练的中文聊天模型与对应语料（词表随语料恢复） |
| `helloalgo.bin` / `helloalgo_corpus.txt` | 用《Hello 算法》训练的知识模型 |
| `solver.exe` | 作业助手（题库检索 + 精确计算） |
| `db_questions.txt` / `db_answers.txt` | 19.5 万道中文应用题题库（solver 用） |
| `sessions/` | 网页版的历史会话存档 |
| `start_ai.bat` | 启动窗口版 |

**运行（工作目录必须是 bin）**

```powershell
cd C:\Users\Lenovo\ai\nanochat-demo\bin

.\gui.exe    zhchat_corpus.txt zhchat.bin          # 窗口版聊天
.\server.exe zhchat_corpus.txt zhchat.bin 8090     # 网页版（自动开浏览器）
.\solver.exe                                       # 作业助手（交互）
```

### src/ —— 源码

| 文件 | 说明 |
|---|---|
| `nanogpt.c` | 核心：GPT 前向/手写反向传播/AdamW/权重存取/采样/考试/思考模式 |
| `solver.c` | 作业助手：精确算术 + 一元一次方程 + 中文题型规则 + 题库检索 |
| `gui.c` | Win32 窗口版（`nanogpt.c` + 工具 + 窗口代码合并产物） |
| `server.c` | 网页版服务（同上 + HTTP 服务 + 多会话） |
| `ai.c` | 统一命令行聊天（工具 + 神经聊天） |
| `nanogpt_dbl.c` | 双精度版本，仅用于梯度验证 |
| `qwen.c` | 纯 C 的 GGUF 解析/推理引擎（实验） |
| `test_answer.c` | 应答流程的控制台测试 |
| `drive_gui.c` | 远程驱动窗口的小工具（调试用） |

### 编译

```powershell
cd C:\Users\Lenovo\ai\nanochat-demo
# 常规模型（字节级词表）
gcc -O3 -march=native -fopenmp -o bin\nanogpt.exe src\nanogpt.c -lm
# 字符级模型（一个汉字一个 token，输出不会乱码）
gcc -O3 -march=native -fopenmp -DCHARLEVEL -o bin\chargpt.exe src\nanogpt.c -lm
# 窗口版 / 网页版
gcc -O3 -march=native -fopenmp -mwindows -o bin\gui.exe src\gui.c -lm
gcc -O3 -march=native -fopenmp -o bin\server.exe src\server.c -lm -lws2_32
# 作业助手
gcc -O2 -o bin\solver.exe src\solver.c -lm
```

## 训练自己的模型

```powershell
cd C:\Users\Lenovo\ai\nanochat-demo\bin
# 字节级：nanogpt.exe train <语料> <步数> <输出.bin>
.\nanogpt.exe train ..\data\helloalgo_corpus.txt 1200 helloalgo.bin
# 字符级（推荐中文）：chargpt.exe（编译时加 -DCHARLEVEL）
.\chargpt.exe train ..\data\某语料.txt 1200 某模型.bin
```

训练完成后，用同一份语料启动界面即可：
```powershell
.\gui.exe ..\data\某语料.txt 某模型.bin
```

## 已知限制

- 模型规模小（0.89M ~ 3.2M 参数），能模仿语言形式和题材，**不具备真正的推理解题能力**。
- `solver.exe` 的答案来自规则与题库检索，可靠但只覆盖已知题型。
- 全部在本机 CPU 上运行，训练速度约 0.3~1 秒/步。
