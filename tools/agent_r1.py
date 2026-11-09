"""
 * 文件名：agent_r1.py
 * 作用：会动手的 AI 助手 —— 能改文件、能运行程序、看结果再判断
 * 依赖：Python 3.8+ 标准库；本地 llama-server（默认 http://127.0.0.1:8080）
 * 作者：qiqiwang07
 * 更新：2026-11-07
 *
 * 为什么用「确定性流水线」而不是让模型自主调用工具：
 *     1.5B/7B 这类小模型对 function calling 的格式遵循很差，
 *     自由发挥经常输出不合法 JSON 或干脆不调用工具。
 *     所以把流程固定成 6 步，模型只在"生成新内容"和"解释结果"两处出力，
 *     这样即使模型很弱，整个流程也不会崩。
 *
 * 流程：
 *     1. 列工作目录，挑出要改的文件
 *     2. 读原文件内容
 *     3. 让模型生成修改后的完整内容
 *     4. 写回文件（原文件存 .bak 备份）
 *     5. 运行验证（.py 用 python，.bat 用 cmd，其它跳过）
 *     6. 让模型看运行结果，判断是否成功并解释
 *
 * 用法：
 *     python agent_r1.py [--port 8092] [--bind 127.0.0.1] [--workspace <目录>]
"""
import argparse  # 解析命令行参数
import json  # 读写 JSON 请求与响应
import os  # 路径拼接、目录遍历
import re  # 正则：提取代码块、剔除中文说明
import subprocess  # 运行被测程序，拿到退出码与输出
import threading  # 线程锁，保护 SSE 写操作
import time  # 预留的计时接口（当前主流程未强依赖）
import urllib.request  # 调用 llama-server（仅标准库，无需第三方）
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # 内置 HTTP 服务

LLAMA = "http://127.0.0.1:8080/v1/chat/completions"  # 后端地址，可通过 --llama 覆盖
WORKSPACE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace")  # 默认工作目录：脚本同级 workspace
CMD_TIMEOUT = 60  # 运行被测程序的最长等待秒数，防止死循环卡住服务
MAX_READ = 6000  # 单次最多读取多少字符，避免超大文件把提示词撑爆


def llama_chat(messages, max_tokens=600, temperature=0.2) -> str:
    """调用 llama-server 做一次非流式对话，返回纯文本回答。

    温度取 0.2 而非 0.7：改代码要求稳定复现，不需要发散；
    温度高会让模型"自由发挥"改出意料之外的内容。
    """
    body = {"messages": messages, "max_tokens": max_tokens,  # 对话历史与长度上限
            "temperature": temperature, "top_p": 0.9, "repeat_penalty": 1.05}  # 采样参数
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")  # 中文不转义，省字节
    req = urllib.request.Request(LLAMA, data=data, headers={"Content-Type": "application/json"})  # 构造请求
    with urllib.request.urlopen(req, timeout=600) as r:  # 600 秒超时：CPU 推理长代码可能很慢
        j = json.loads(r.read().decode("utf-8"))  # 读取并解析完整响应
    msg = j["choices"][0]["message"]  # 取第一个候选的 message 对象
    txt = (msg.get("content") or "").strip()  # 优先用 content（最终答案）
    if not txt:  # content 为空说明模型把内容放进了思考字段
        txt = (msg.get("reasoning_content") or "")  # 取出思考文本
        for mk in ("</think>", "<｜end▁of▁thinking｜>"):  # 兼容两种结束标记
            if mk in txt:  # 找到标记
                txt = txt.rsplit(mk, 1)[1]  # 只保留标记后的内容
    for mk in ("</think>", "<｜end▁of▁thinking｜>"):  # 再兜底清一次（content 里也可能带标记）
        if mk in txt:  # 命中
            txt = txt.rsplit(mk, 1)[1]  # 截断思考部分
    return txt.strip()  # 去掉首尾空白后返回


def strip_fence(s: str) -> str:
    """从模型输出里只提取代码，丢掉解释性文字。

    为什么需要：模型经常在代码前后加"这是修改后的代码："之类的说明，
    如果原样写回文件，会直接造成语法错误（之前就踩过这个坑）。
    """
    s = s.strip()  # 先去掉首尾空白
    m = re.search(r"```[a-zA-Z0-9]*\n(.*?)```", s, re.S)  # 优先找 markdown 代码块
    if m:  # 找到了代码块
        return m.group(1).rstrip()  # 返回块内内容，去掉末尾换行
    out = []  # 没有代码块时的备用策略：逐行过滤
    for ln in s.splitlines():  # 逐行检查
        stripped = ln.strip()  # 去掉行首尾空白用于判断
        if not stripped:  # 空行保留（保持代码结构）
            out.append(ln)  # 收集
            continue  # 继续下一行
        has_cjk = re.search(r"[\u4e00-\u9fff]", stripped)  # 是否含中文
        is_code = (stripped.startswith(("#", "import ", "from ", "def ", "class ", "@"))  # 明显的代码行
                   or any(t in stripped for t in ("(", ")", "=", ":", '"', "'", "print")))  # 含代码符号
        if has_cjk and not is_code:  # 纯中文且不像代码 = 说明文字
            break  # 说明文字通常在最末尾，遇到就直接截断
        out.append(ln)  # 认为是代码，保留
    return "\n".join(out).rstrip()  # 拼回字符串


def safe_path(rel: str) -> str:
    """把相对路径解析成绝对路径，并确保没有跑出工作目录。

    安全要点：如果用户/模型传了 ../../etc/passwd 这种路径，
    直接 open() 会读到系统文件，所以必须校验前缀。
    """
    root = os.path.abspath(WORKSPACE)  # 工作目录的绝对路径
    p = os.path.abspath(os.path.join(root, rel.replace("\\", "/").lstrip("/")))  # 统一分隔符并解析
    if not (p == root or p.startswith(root + os.sep)):  # 必须严格在 root 之内
        raise ValueError("路径越界")  # 越界直接抛错，绝不写入
    return p  # 返回安全的绝对路径


def pick_file(task: str, emit) -> str:
    """从工作目录里挑出任务要改的那个文件。

    策略：优先用"任务里直接点名"（最可靠），
    其次才让模型判断，最后兜底取第一个文件。
    """
    files = [f for f in sorted(os.listdir(WORKSPACE)) if os.path.isfile(os.path.join(WORKSPACE, f))]  # 只列文件，忽略子目录
    emit("工作目录里有: %s\n\n" % ", ".join(files[:20]))  # 告知用户可改哪些文件
    if not files:  # 目录为空
        return ""  # 返回空表示无法继续
    for f in files:  # 先做精确匹配
        if f in task:  # 任务文本里出现了文件名
            return f  # 直接采用，不需要模型介入
    prompt = ("用户任务：%s\n\n工作目录文件列表：%s\n\n"  # 让模型判断的文件列表
              "请只输出要修改的那个文件名，不要输出其他任何内容。" % (task, ", ".join(files)))  # 强约束输出格式
    try:  # 模型调用可能失败
        ans = llama_chat([{"role": "user", "content": prompt}], max_tokens=24)  # 只要短输出
    except Exception:  # 后端不可用
        return files[0]  # 兜底用第一个文件
    ans = ans.replace("`", "").strip()  # 去掉可能带的引号反引号
    for f in files:  # 从模型输出里找文件名
        if f in ans:  # 命中
            return f  # 采用
    return files[0]  # 都没命中就取第一个


def run_verify(fname: str) -> str:
    """运行修改后的文件做验证，返回可读的结果文本。

    只对 .py 和 .bat 自动运行：这两种有明确的执行入口；
    其它类型（如 .txt/.md）运行没有意义，直接说明跳过。
    """
    ext = os.path.splitext(fname)[1].lower()  # 取扩展名并转小写
    if ext == ".py":  # Python 脚本
        cmd = "python %s" % fname  # 用 python 运行
    elif ext in (".bat", ".cmd"):  # Windows 批处理
        cmd = "cmd /c %s" % fname  # 交给 cmd 执行
    else:  # 其它类型
        return "（该文件类型不自动运行）"  # 明确告知跳过
    try:  # 运行可能超时或失败
        r = subprocess.run(cmd, shell=True, cwd=WORKSPACE, capture_output=True,  # 在工作目录下执行，捕获输出
                           timeout=CMD_TIMEOUT, encoding="utf-8", errors="ignore")  # 超时保护 + 容错解码
        out = (r.stdout or "") + (("\n[stderr] " + r.stderr) if r.stderr else "")  # 合并标准输出与错误输出
        return "运行 `%s` → 退出码 %d\n%s" % (cmd, r.returncode, out[:2000])  # 截断过长输出，避免刷屏
    except subprocess.TimeoutExpired:  # 超时
        return "运行 `%s` 超时（%d 秒）" % (cmd, CMD_TIMEOUT)  # 明确告知超时
    except Exception as e:  # 其它异常（如文件不存在）
        return "运行失败: %s" % e  # 返回原因


def handle_task(task: str, emit) -> None:
    """执行一次完整的修改任务，进度通过 emit 实时推给前端。"""
    fname = pick_file(task, emit)  # 第一步：确定要改哪个文件
    if not fname:  # 没文件可用
        emit("工作目录是空的，先放一个文件进来。")  # 告知用户
        return  # 结束
    path = safe_path(fname)  # 解析出安全路径
    try:  # 读取可能失败（编码/权限）
        with open(path, encoding="utf-8", errors="ignore") as f:  # 容错读取
            old = f.read()[:MAX_READ]  # 只取前 MAX_READ 字符，控制提示词长度
    except Exception as e:  # 读取失败
        emit("读取 %s 失败: %s" % (fname, e))  # 告知原因
        return  # 结束
    emit("▶ 读取 %s（%d 字节）\n" % (fname, len(old.encode('utf-8'))))  # 报告已读取
    prompt = ("下面是一个文件的完整内容：\n```\n%s\n```\n\n"  # 把原文件完整贴给模型
              "任务：%s\n\n"  # 说明要做什么
              "请输出修改后的完整文件内容。只输出文件内容本身，"  # 要求输出完整内容而非 diff
              "不要解释，不要加 markdown 代码块标记。" % (old, task))  # 禁止加说明文字
    emit("▶ 让模型生成修改后的内容…\n")  # 报告正在生成
    try:  # 模型调用可能失败
        new = strip_fence(llama_chat([{"role": "user", "content": prompt}], max_tokens=1200, temperature=0.2))  # 生成并清洗
    except Exception as e:  # 失败
        emit("模型调用失败: %s" % e)  # 告知原因
        return  # 结束
    if not new.strip():  # 模型返回空
        emit("模型没有返回内容，任务中止。")  # 终止流程，避免把文件写空
        return  # 结束
    changed = new.strip() != old.strip()  # 记录是否真的改动了
    if not changed:  # 内容没变
        emit("▶ 注意：模型返回的内容与原文完全相同，文件没有被真正修改。\n")  # 明确告知，不假装成功
    backup = path + ".bak"  # 备份文件名
    try:  # 写文件可能失败（权限/磁盘满）
        with open(backup, "w", encoding="utf-8") as f:  # 先写备份
            f.write(old)  # 备份原始内容
        with open(path, "w", encoding="utf-8") as f:  # 再覆盖原文件
            f.write(new)  # 写入新内容
        emit("▶ 已写入 %s（原文件备份为 %s）\n" % (fname, os.path.basename(backup)))  # 报告结果
    except Exception as e:  # 写入失败
        emit("写入失败: %s" % e)  # 告知原因
        return  # 结束
    emit("▶ 运行验证…\n")  # 报告开始运行
    result = run_verify(fname)  # 运行修改后的文件
    emit("   " + result.replace("\n", "\n   ")[:800] + "\n")  # 缩进展示运行输出
    ok = "退出码 0" in result  # 只有退出码 0 才算运行成功
    verdict_prompt = ("文件已按任务修改并运行。任务：%s\n\n运行结果：\n%s\n\n"  # 把任务与结果一起给模型
                      "运行%s。请用一两句话说明哪里符合要求、哪里可能还有问题，不要贴代码。"  # 只让模型解释，不让它下结论
                      % (task, result[:1500], "成功" if ok else "失败"))  # 明确告诉它运行结果的好坏
    emit("▶ 让模型解释结果…\n\n")  # 报告正在解释
    try:  # 解释可能失败
        verdict = llama_chat([{"role": "user", "content": verdict_prompt}], max_tokens=200, temperature=0.3)  # 生成解释
    except Exception as e:  # 失败
        verdict = "（解释失败：%s）" % e  # 返回错误说明，不中断流程
    for mk in ("</think>",):  # 兜底清理思考标记
        if mk in verdict:  # 命中
            verdict = verdict.rsplit(mk, 1)[1]  # 截断
    if not changed:  # 没改动时不能说成功
        head = "⚠️ 文件没有实际改动（模型没按任务修改），请换个更具体的说法重试"  # 明确提示
    elif ok:  # 改动了且运行通过
        head = "✅ 已修改并验证通过"  # 成功
    else:  # 改动了但运行失败
        head = "⚠️ 运行失败（退出码非 0），修改已保留，可继续让我修"  # 提示可继续迭代
    emit("%s\n\n%s" % (head, verdict.strip()))  # 先给结论再给解释
    if not ok:  # 失败时告知备份位置
        emit("\n备份文件：%s（如需回滚可直接替换）" % os.path.basename(backup))  # 方便用户回滚


class Handler(BaseHTTPRequestHandler):
    """HTTP 处理器：GET 出页面，POST 是流式的任务执行接口。"""

    protocol_version = "HTTP/1.1"  # 用 1.1 支持 keep-alive

    def log_message(self, fmt, *args):
        """屏蔽默认访问日志，避免每个请求刷一行。"""
        pass  # 故意留空

    def _send(self, body: bytes, ctype="application/json"):
        """发送普通（非流式）响应。"""
        self.send_response(200)  # 固定 200
        self.send_header("Content-Type", ctype + "; charset=utf-8")  # 明确编码
        self.send_header("Content-Length", str(len(body)))  # 给出长度
        self.end_headers()  # 结束头部
        self.wfile.write(body)  # 写响应体

    def do_GET(self):
        """首页返回与对话版相同的界面。"""
        if self.path in ("/", "/chat.html", "/agent"):  # 三个路径都认
            # 页面可能与本脚本同目录（服务器部署），也可能在 ../bin（本地开发），两处都找
            here = os.path.dirname(os.path.abspath(__file__))  # 本脚本目录
            p = os.path.join(here, "chat.html")  # 优先同目录
            if not os.path.exists(p):  # 同目录没有再找 bin
                p = os.path.join(here, "..", "bin", "chat.html")  # 本地开发时的位置
            p = os.path.abspath(p)  # 规范化，便于错误信息可读
            with open(p, "rb") as f:  # 二进制读
                self._send(f.read(), "text/html")  # 以 HTML 返回
        else:  # 未知路径
            self._send(b'{"error":"not found"}')  # 统一错误

    def do_POST(self):
        """接收任务，边执行边用 SSE 推送进度。"""
        n = int(self.headers.get("Content-Length") or 0)  # 请求体长度
        raw = self.rfile.read(n) if n else b"{}"  # 读取请求体
        try:  # 可能是畸形 JSON
            body = json.loads(raw or b"{}")  # 解析
        except Exception:  # 解析失败
            body = {}  # 退化为空字典
        if self.path != "/chat":  # 只处理 /chat
            self._send(b'{"error":"not found"}')  # 其它路径 404
            return  # 结束
        text = (body.get("text") or "").strip()  # 取任务描述
        self.send_response(200)  # 开始流式响应
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")  # SSE 类型
        self.send_header("Cache-Control", "no-store")  # 不缓存
        self.send_header("Connection", "close")  # 关闭连接，避免代理缓冲
        self.end_headers()  # 结束头部
        lock = threading.Lock()  # 同一个 emit 可能被多线程调用，加锁防穿插
        def emit(s: str):  # 定义推送函数
            """把一段文本作为 SSE 事件发给浏览器。"""
            with lock:  # 保证一次写完
                self.wfile.write(b"data: " + json.dumps({"delta": s}, ensure_ascii=False).encode() + b"\n\n")  # SSE 帧
                self.wfile.flush()  # 立即刷出
        try:  # 任务执行可能抛异常
            handle_task(text, emit)  # 走完整流水线
        except Exception as e:  # 任何异常都转成对话文本，不让连接挂掉
            emit("\n[出错：%s]" % e)  # 回传错误
        self.wfile.write(b'data: {"usage":{"in":0,"out":0,"total":0,"model":0}}\n\n')  # 占位统计，前端需要该字段
        self.wfile.write(b"data: [DONE]\n\n")  # 结束标记
        self.wfile.flush()  # 刷出
        self.close_connection = True  # 主动断开


def main() -> int:
    """程序入口：解析参数、准备工作目录、启动服务。"""
    global WORKSPACE  # 需要覆盖模块级默认值
    ap = argparse.ArgumentParser()  # 参数解析器
    ap.add_argument("--port", type=int, default=8092)  # 监听端口
    ap.add_argument("--bind", default="127.0.0.1", help="监听地址")  # 默认只允许本机
    ap.add_argument("--workspace", default=WORKSPACE)  # 工作目录
    args = ap.parse_args()  # 解析
    WORKSPACE = os.path.abspath(args.workspace)  # 转绝对路径
    os.makedirs(WORKSPACE, exist_ok=True)  # 目录不存在就创建
    print(f"工作目录: {WORKSPACE}", flush=True)  # 启动日志
    print(f"会动手的 AI 已启动: http://{args.bind}:{args.port}", flush=True)  # 启动日志
    ThreadingHTTPServer((args.bind, args.port), Handler).serve_forever()  # 线程化服务，阻塞运行
    return 0  # 正常不会执行到这里


if __name__ == "__main__":
    raise SystemExit(main())  # 用 main 返回值作为退出码
