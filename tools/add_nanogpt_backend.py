# -*- coding: utf-8 -*-
"""给 serve_r1.py 增加 nanogpt 后端：用自研 C 模型替代 llama-server。"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\tools\serve_r1.py'
t = io.open(P, encoding='utf-8').read()

FIXES = []

# 1) 引入 subprocess 与 codecs
FIXES.append((
    'import re  # 正则清洗回答里的出处措辞',
    'import re  # 正则清洗回答里的出处措辞\n'
    'import subprocess  # 调用自研的 nanogpt 可执行文件\n'
    'import codecs  # 增量解码：C 模型逐字节输出，需要拼成完整 UTF-8 字符'
))

# 2) 新增后端配置
FIXES.append((
    'LLAMA = "http://127.0.0.1:8080/v1/chat/completions"  # 默认后端地址，可通过 --llama 覆盖',
    'LLAMA = "http://127.0.0.1:8080/v1/chat/completions"  # 默认后端地址，可通过 --llama 覆盖\n'
    'BACKEND = "llama"  # 后端类型：llama（外部模型）或 nanogpt（自研 C 模型）\n'
    'NP_BIN = os.path.join(HERE, "nanogpt")  # 自研模型可执行文件路径\n'
    'NP_CORPUS = CORPUS  # 自研模型用的语料（决定字符表）\n'
    'NP_WEIGHTS = os.path.join(HERE, "selfmade.bin")  # 自研模型权重\n'
    'NP_LEN = 260  # 自研模型单次生成多少个字符'
))

# 3) 新增自研模型的流式生成函数
FIXES.append((
    'def load_sessions() -> None:',
    '''def stream_nanogpt(prompt: str, usage_out: dict):
    """调用自研 C 模型（nanogpt raw 模式），把输出逐字符转成文本增量。

    为什么用子进程：C 模型是命令行程序，没有 HTTP 接口；
    它每次生成一个字符就 flush，所以这里能拿到真正的流式输出。
    """
    cmd = [NP_BIN, "raw", NP_CORPUS, NP_WEIGHTS, prompt, str(NP_LEN)]  # 命令：只输出正文
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)  # 无缓冲，立刻能读
    dec = codecs.getincrementaldecoder("utf-8")("ignore")  # 增量解码器，处理被切断的多字节字符
    n_out = 0  # 统计生成的字符数，当作 token 数展示
    try:
        while True:  # 逐字节读取
            b = proc.stdout.read(1)  # 一次一个字节，保证不粘包
            if not b:  # 进程结束
                break
            s = dec.decode(b)  # 解码（可能返回空串，表示字符还没凑齐）
            if s:
                n_out += len(s)  # 计数
                yield s  # 交给上层推给浏览器
    finally:
        try:
            proc.wait(timeout=5)  # 等进程退出，避免僵尸进程
        except Exception:
            proc.kill()  # 超时就强杀
    usage_out["in"] = len(prompt)  # 粗略统计输入长度
    usage_out["out"] = n_out  # 输出字符数


def load_sessions() -> None:'''
))

# 4) /chat 里按后端分流
FIXES.append((
    '''            try:  # 后端可能报错（模型崩溃、超时）
                for delta in stream_llama(msgs, usage, req_max):  # 逐个增量
                    acc.append(delta)  # 累积
                    emit({"delta": delta})  # 立刻推给浏览器''',
    '''            try:  # 后端可能报错（模型崩溃、超时）
                if BACKEND == "nanogpt":  # 自研 C 模型：直接续写文本
                    prompt = text + "\\n"  # 用问题本身当提示，让模型接着往下写
                    for delta in stream_nanogpt(prompt, usage):  # 逐字符增量
                        acc.append(delta)  # 累积
                        emit({"delta": delta})  # 立刻推给浏览器
                else:  # 外部模型
                    for delta in stream_llama(msgs, usage, req_max):  # 逐个增量
                        acc.append(delta)  # 累积
                        emit({"delta": delta})  # 立刻推给浏览器'''
))

# 5) 命令行参数
FIXES.append((
    '    ap.add_argument("--no-rag", action="store_true")  # 开关：完全关闭检索，用于对比测试',
    '    ap.add_argument("--no-rag", action="store_true")  # 开关：完全关闭检索，用于对比测试\n'
    '    ap.add_argument("--backend", default="llama", choices=["llama", "nanogpt"])  # 选择后端\n'
    '    ap.add_argument("--np-bin", default=NP_BIN)  # 自研模型可执行文件\n'
    '    ap.add_argument("--np-weights", default=NP_WEIGHTS)  # 自研模型权重\n'
    '    ap.add_argument("--np-len", type=int, default=NP_LEN)  # 自研模型生成长度'
))

FIXES.append((
    '    LLAMA = args.llama  # 应用后端地址\n    MAX_NEW = args.max_new  # 应用生成长度',
    '    LLAMA = args.llama  # 应用后端地址\n'
    '    MAX_NEW = args.max_new  # 应用生成长度\n'
    '    global BACKEND, NP_BIN, NP_WEIGHTS, NP_LEN  # 需要写入模块级配置\n'
    '    BACKEND = args.backend  # 后端类型\n'
    '    NP_BIN = args.np_bin  # 自研模型路径\n'
    '    NP_WEIGHTS = args.np_weights  # 权重路径\n'
    '    NP_LEN = args.np_len  # 生成长度'
))

applied = 0
for old, new in FIXES:
    if old in t:
        t = t.replace(old, new, 1)
        applied += 1
    else:
        print('✘ 未匹配:', old.split('\n')[0][:60])

ast.parse(t)  # 语法检查
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('nanogpt 后端补丁应用 %d / %d 处' % (applied, len(FIXES)))
