# -*- coding: utf-8 -*-
"""给 nanogpt 加 raw 模式：只输出生成的正文，不带任何提示文字，供网页服务流式调用。

用法：./nanogpt raw <corpus.txt> <权重.bin> "问题"
输出：只把生成的字符写到 stdout，每生成一个字符就 flush（前端能流式显示）
"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\src\nanogpt.c'
t = io.open(P, encoding='utf-8').read()

# 1) 在 generate 之后插入 generate_raw
anchor = '/* ------------------------------ 梯度检查 --------------------------------'
NEW_FUNC = '''/* ------------------------------ 纯文本生成（给网页服务用）--------------------------
 * 与 generate() 的区别：不打印任何表头、提示词回显、结束语，
 * 只把模型新生成的字符逐个写到 stdout 并立即 flush，方便上层流式转发。 */
static void generate_raw(const char *prompt, int nchars) {
    static int ctx[8192];                          /* 上下文缓冲 */
    int n = str_to_ids(prompt, ctx, 8000);         /* 提示词编码 */
    if (n == 0) { ctx[n++] = str_to_ids("\\n", ctx + n, 1); }  /* 空提示兜底 */
    int savedB = B;                                /* 保存 batch 设置 */
    B = 1;                                         /* 单序列生成 */
    for (int s = 0; s < nchars; s++) {             /* 逐字符生成 */
        int len = n < T ? n : T;                   /* 上下文不超过窗口 */
        BT = len;                                  /* 本次前向长度 */
        for (int t = 0; t < len; t++) { xs[t] = ctx[n - len + t]; ys[t] = 0; }  /* 填输入 */
        forward();                                 /* 前向 */
        float *lg = h_logits + (size_t)(len - 1) * VOCAB;  /* 最后一个位置的分布 */
        float temp = 0.8f, sum = 0.0f, probs[VOCAB];  /* 温度与概率表 */
        float kth = -1e30f;                        /* top-40 阈值 */
        for (int v = 0; v < VOCAB; v++) if (lg[v] > kth) kth = lg[v];  /* 取最大 */
        for (int r = 0; r < 39; r++) {             /* 找到第 40 大 */
            float best = -1e30f;
            for (int v = 0; v < VOCAB; v++) if (lg[v] < kth && lg[v] > best) best = lg[v];
            kth = best;
        }
        float mxl = -1e30f;                        /* 用于数值稳定的最大值 */
        for (int v = 0; v < VOCAB; v++) if (lg[v] > mxl) mxl = lg[v];
        for (int v = 0; v < VOCAB; v++) {          /* 计算截断后的概率 */
            if (lg[v] < kth) { probs[v] = 0.0f; continue; }
            float e = (lg[v] - mxl) / temp;        /* 减最大值再除温度 */
            if (e > 60.0f) e = 60.0f;              /* 防 exp 溢出 */
            probs[v] = expf(e);
            sum += probs[v];
        }
        float r = frand() * sum, acc = 0.0f;       /* 轮盘赌落点 */
        int pick = VOCAB - 1;                      /* 兜底 */
        for (int v = 0; v < VOCAB; v++) { acc += probs[v]; if (r <= acc) { pick = v; break; } }
        ctx[n++] = pick;                           /* 接进上下文 */
        char ob[8];                                /* 输出的 UTF-8 字节 */
        int k = id_to_out(pick, ob);               /* 编码 */
        fwrite(ob, 1, (size_t)k, stdout);          /* 只写正文，不加任何装饰 */
        fflush(stdout);                            /* 立即刷出，上层才能流式收到 */
    }
    B = savedB; BT = B * T;                        /* 恢复现场 */
}

'''
if anchor not in t:
    raise SystemExit('找不到插入锚点')
t = t.replace(anchor, NEW_FUNC + anchor, 1)

# 2) 在 main 里加 raw 分支（放在 sample 之前）
old = '    if (strcmp(mode, "sample") == 0) {'
new = '''    if (strcmp(mode, "raw") == 0) {
        /* raw <corpus> <weights.bin> "问题" [生成长度] —— 只输出正文，供网页服务调用 */
        if (argc < 5) {                            /* 需要权重和问题 */
            fprintf(stderr, "用法: nanogpt raw <corpus.txt> <权重.bin> \\"问题\\" [长度]\\n");
            return 1;
        }
        if (load_weights(argv[3]) != 0) return 1;  /* 加载权重 */
        char *q = to_utf8(argv[4]);                /* 命令行可能是 GBK，转 UTF-8 */
        int n = argc > 5 ? atoi(argv[5]) : 260;    /* 默认生成 260 个字符 */
        generate_raw(q, n);                        /* 只输出正文 */
        free(q);                                   /* 释放转换结果 */
        return 0;
    }

    if (strcmp(mode, "sample") == 0) {'''
assert old in t, '找不到 sample 分支'
t = t.replace(old, new, 1)

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('已加入 raw 模式')
