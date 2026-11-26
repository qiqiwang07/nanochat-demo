# 用免费 GPU 训自己的模型：操作手册

> 目标：在 Google Colab / Kaggle 的免费显卡上，训练一个 **2800 万参数**的自研模型。
> 所有权重都是你自己训的，只是借它的显卡算。
> 预计：**3-5 小时**（可以分两次），花费 **0 元**。

---

## 一、准备什么

| 文件 | 在哪 | 说明 |
|---|---|---|
`corpus.txt` | 服务器 `/home/qiqiwang/airelay/app/corpus.txt` | 8.9 MB 中文语料 |
`colab_train.py` | 项目 `tools/colab_train.py` | 训练脚本（已写好） |

先把这两个文件下载到你电脑上。

---

## 二、Colab 操作步骤（推荐）

### 第 1 步：打开 Colab

1. 浏览器打开 <https://colab.research.google.com>
2. 用 Google 账号登录（没有就注册一个，免费）
3. 点 **「新建笔记本」**

### 第 2 步：开 GPU

1. 菜单栏 **「代码执行程序」→「更改运行时类型」**
2. 硬件加速器选 **T4 GPU**
3. 点「保存」

> 验证：随便运行一句 `import torch; print(torch.cuda.get_device_name(0))`
> 显示 `Tesla T4` 就对了。

### 第 3 步：上传文件

1. 点左侧 **文件夹图标**（📁）
2. 把 `corpus.txt` 和 `colab_train.py` 拖进 `/content` 目录
3. 等上传完（8.9 MB，大约 1 分钟）

> 或者用代码上传：
> ```python
> from google.colab import files
> files.upload()   # 会弹出选择文件的对话框
> ```

### 第 4 步：开始训练

新建一个代码格，输入：

```python
!python colab_train.py --data corpus.txt --steps 12000
```

按 **Shift+Enter** 运行。

### 第 5 步：看着它跑

你会看到这样的输出：

```
设备: cuda Tesla T4
语料 6337979 字符
词表 1200，token 6337979
参数量 28.3M
step    50/12000  loss 6.8123  lr 1.2e-04  12s  43000 tok/s
step   100/12000  loss 5.9041  lr 2.4e-04  25s  42000 tok/s
...
```

几个关键数字：

| 指标 | 正常范围 | 含义 |
|---|---|---|
参数量 | 28M 左右 | 比现在的 4.8M 大 6 倍 |
速度 | 40000 tok/s | T4 的正常水平 |
loss | 从 6.8 降到 2 以下 | 在学 |
总时长 | 3-5 小时 | 看步数 |

**训练期间不要关浏览器标签**（可以切到别的标签，但 Colab 页面要留着）。

### 第 6 步：中途断了怎么办

Colab 免费版可能因闲置断开。脚本**每 1000 步自动存检查点**，所以不用怕。

重新连接后：

```python
# 断线后先看看跑到哪了
!ls -lh model.pt
# 然后从上次的位置继续（步数改成剩下的）
!python colab_train.py --data corpus.txt --steps 6000
```

> 注意：目前的脚本是「从头重跑」而不是「从检查点续训」。
> 如果真断了，告诉我，我给你加一个 `--resume` 参数。

### 第 7 步：下载结果

训练完成后，左侧文件面板会出现：

```
model.pt     （约 110 MB）
vocab.json   （词表）
```

1. 右键 → 「下载」
2. 或者用代码打包下载：

```python
!zip -q result.zip model.pt vocab.json
from google.colab import files
files.download('result.zip')
```

### 第 8 步：把文件给我

把 `model.pt` 和 `vocab.json` 放到 `C:\Users\Lenovo\ai\models\` 下，告诉我一声。

我会做三件事：
1. 用 `convert_to_nanogpt.py` 转成 C 程序能读的格式
2. 在服务器上编译 x86-64 的 nanogpt 并加载权重
3. 测准确率，和现在 4.8M 版本做对比

---

## 三、Kaggle 操作步骤（备选）

Kaggle 每周给 **30 小时** GPU，比 Colab 稳定。

1. 打开 <https://www.kaggle.com>，注册登录
2. 右上角 **「Create」→「New Notebook」**
3. 右侧面板 **「Session options」→ Accelerator 选 `GPU T4 x2`**
4. 上传数据：右侧 **「Add Data」→「Upload」**，把 `corpus.txt` 传上去
5. 上传脚本：新建一个 cell，粘贴：

```python
%%writefile colab_train.py
# 把 colab_train.py 的全部内容粘贴到这里
```

6. 运行：

```python
!python colab_train.py --data /kaggle/input/你的数据集名/corpus.txt --steps 12000
```

7. 结果在 `/kaggle/working/`，可以下载

---

## 四、可能遇到的问题

| 现象 | 原因 | 怎么办 |
|---|---|---|
`CUDA out of memory` | 显存不够 | 把 `--batch` 从 16 改成 8 |
跑得很慢（<10000 tok/s） | 没开 GPU | 检查运行时类型是不是 T4 |
`FileNotFoundError: corpus.txt` | 文件没上传 | 左侧文件面板确认在 `/content` 下 |
训练断开 | 免费额度限制 | 重新连上继续跑，检查点在 `model.pt` |
loss 不降 | 学习率太大 | 加 `--lr 3e-4` 试试 |

---

## 五、参数怎么调

| 参数 | 默认 | 说明 |
|---|---|---|
`--steps` | 12000 | 训练步数，越多越好，但更久 |
`--batch` | 16 | 显存不够就调小 |
`--ctx` | 512 | 上下文长度 |
`--nlayer` | 8 | 层数，想更大就加到 12 |
`--nembd` | 512 | 宽度，想更大就加到 768 |
`--mlp` | 1536 | 前馈层宽度 |
`--lr` | 6e-4 | 学习率 |

**想更聪明**（但更慢）：

```python
!python colab_train.py --data corpus.txt --steps 20000 --nlayer 12 --nembd 768 --mlp 3072 --batch 8
```

这样约 **8500 万参数**，需要 10 小时以上，可能得分两次跑。

**想快点看到结果**：

```python
!python colab_train.py --data corpus.txt --steps 4000 --nlayer 6 --nembd 384
```

约 **1200 万参数**，1 小时左右。

---

## 六、要知道的代价

| 项目 | 说明 |
|---|---|
**数据上传** | 8.9 MB 语料会传到 Google 服务器 |
**结果不保证** | 2800 万参数仍然不能像 7B 模型那样对话，但比 4.8M 强很多 |
**可能要调** | 转换后的权重第一次加载如果输出乱码，需要加 `--transpose` 重转一次 |
**无 SLA** | 免费额度随时可能变，Colab 会杀长时间空闲的会话 |

---

## 七、一句话总结

> 你负责：打开 Colab、上传两个文件、点运行、等着、下载。
> 我负责：训练脚本、权重转换、部署测试。
> 花的是 Google 的电，训的是你自己的模型。
