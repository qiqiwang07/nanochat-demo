# 变更记录

## 2026-11-07

### 部署
- 服务器改用 **Qwen2.5-7B-Instruct**（4.4 GB，Q4_K_M），替换原来的 DeepSeek-R1-1.5B
- 7B 在服务器 8 核 CPU 上约 **6 token/秒**，回答质量显著提升（能举例、能做矩阵演算）
- 1.5B 模型文件保留在 `~/models/model.gguf`，需要时可切回

### 功能
- 网页服务增加 `/dl/` 文件分发，支持 **HTTP Range 断点续传**（1 GB 安装包不再怕断线）
- 服务默认监听 `0.0.0.0`，可用 `--bind` 指定；通过 nginx 转发到 `c-learning.oprfin.com`
- 界面改为豆包风格：左侧会话栏、居中欢迎页、代码块带复制按钮、深色模式

### 优化
- 检索参数下调：教材片段 700→400 字、教材取 2 段、题库取 1 道、解答截断 1600→900 字
- 首字延迟从 **85 秒降到 34-44 秒**（输入 token 从 1599 降到约 700）
- 修复流式输出被吞的问题：去掉「积累 200 字才输出」的门槛，Qwen 短回答不再丢失

### 工程
- 新增 `CONTRIBUTING.md`：注释规范（逻辑行必须中文注释）、提交规范、三处同步要求
- 新增 `tools/sync.ps1`：一条命令完成「本地 → GitHub → 服务器」同步并校验 MD5
- 新增 `tools/gen_func_map.py` 与 `docs/FUNC_MAP.md`：自动生成函数调用关系表
- `tools/serve_r1.py` 全部逻辑行加中文注释，并改为相对路径（Windows/Linux 通用）
- 修复提示词被模型照抄成「解释为什么：」「补充要点：」小标题的问题

### 修正
- `.ps1` 脚本必须存为 **UTF-8 with BOM**，否则 PowerShell 5.1 按 GBK 读会报语法错误
- 部署脚本的 `$ErrorActionPreference` 改为 `Continue`，避免 git/scp 的 stderr 被当成致命错误
