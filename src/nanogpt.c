/* ============================================================================
 * nanogpt.c -- 一个用纯 C 写的迷你 GPT 语言模型
 *
 * 没有任何 Python / PyTorch / BLAS：词表构建、批采样、前向传播、手写反向传播
 * （每一步梯度都是解析推导），AdamW 参数更新、文本生成，全部在本文件的 C 代码内。
 *
 * 架构（与 nanochat 同源的 decoder-only Transformer，缩小版）：
 *     x = token嵌入 + 位置嵌入
 *     每层:  x += Wo @ MHA(RMSNorm(x))       因果多头自注意力
 *            x += W2 @ ReLU(W1 @ RMSNorm(x))  前馈网络
 *     输出:  logits = lm_head @ RMSNorm(x)    损失 = 逐位置交叉熵
 *
 * 编译:  gcc -O3 -march=native -fopenmp -o nanogpt.exe nanogpt.c -lm
 * 用法:  nanogpt.exe check  <corpus.txt>              梯度检查（数值 vs 解析）
 *        nanogpt.exe train  <corpus.txt> [steps]      训练
 *        nanogpt.exe sample <corpus.txt> ["prompt"]   生成文本
 * ==========================================================================*/
#include <stdio.h>   /* printf / fopen / fread，用于日志输出与权重存取 */
#include <stdlib.h>  /* malloc / calloc / exit，用于张量分配与致命错误退出 */
#include <string.h>  /* memcpy / memset / strcmp，用于张量拷贝与参数名比较 */
#include <math.h>    /* expf / sqrtf / logf，用于损失、归一化、采样 */
#include <time.h>    /* time，用于随机种子与耗时统计 */
#include <stdint.h>  /* int32_t，权重文件头固定用 32 位整数，保证跨平台一致 */
#ifdef _WIN32
#include <windows.h> /* SetConsoleOutputCP，让中文日志在 Windows 控制台正常显示 */
#endif

/* ------------------------------ 超参数 ----------------------------------
 * 四个尺寸参数可在编译时用 -D 覆盖，例如大模型：
 *   gcc -DNLAYER=6 -DNEMBD=192 -DNHEAD=6 -DMLP=768 ...
 * 权重文件里记录了架构，加载时会校验，不匹配会拒绝加载。 */
#ifndef NLAYER
#define NLAYER   4           /* 层数：越多表达能力越强，但显存/内存与耗时线性增长 */
#endif
#ifndef NEMBD
#define NEMBD    128         /* 隐藏维度：注意力与 FFN 的通道数 */
#endif
#ifndef NHEAD
#define NHEAD    4           /* 注意力头数：每个头看到 NEMBD/NHEAD 维子空间 */
#endif
#ifndef MLP
#define MLP      512         /* 前馈网络中间层宽度，通常是 NEMBD 的 4 倍 */
#endif
#ifdef CHARLEVEL
#define VOCAB    1200        /* 字符级词表：最多 1200 个不同字符（汉字/字母/符号） */
#else
#define VOCAB    256         /* 字节级词表：覆盖全部字节 */
#endif
#define HD       (NEMBD / NHEAD)  /* 每个头的维度，必须整除，否则注意力无法拆分 */
#define RMS_EPS  1e-5f            /* RMSNorm 的分母保护项，防止全零输入导致除零 */

static int B = 8;            /* batch：一次前向同时处理多少条序列，越大梯度越稳但更吃内存 */
static int T = 256;          /* 上下文：字符级时 256 个字符，决定模型一次能看多远 */
static int BT;               /* B*T：所有张量按"总行数"分配，行数就是 batch×时间步 */

/* ------------------------------ 参数表 ---------------------------------- */
typedef struct {
    const char *name;        /* 参数名，仅用于打印与按名字查找（如 "L0.Wqkv"） */
    int n;                   /* 元素个数，决定分配与清零的范围 */
    float *p, *g, *m, *v;    /* 数值 / 梯度 / AdamW 一阶、二阶动量 */
} Param;

static Param params[160];    /* 静态数组而非链表：参数总量在编译期可估，省掉指针开销 */
static int   nparams = 0;    /* 当前已注册的参数个数 */

static float *falloc(int n) {
    /* 分配 n 个 float 并清零：清零很重要，否则梯度累加会读到野值 */
    float *p = (float *)calloc((size_t)n, sizeof(float));  /* calloc 自带清零语义 */
    if (!p) { fprintf(stderr, "out of memory\n"); exit(1); }  /* 无法继续，直接退出而不是返回空指针 */
    return p;                /* 返回可用指针 */
}
static Param *add_param(const char *name, int n) {
    /* 注册一个参数张量，并一次性分配 p/g/m/v 四套缓冲区 */
    Param *q = &params[nparams++];   /* 取下一个槽位 */
    q->name = strdup(name);          /* 必须复制：调用方复用了同一个栈缓冲 */
    q->n = n;                        /* 记录元素数 */
    q->p = falloc(n); q->g = falloc(n); q->m = falloc(n); q->v = falloc(n);  /* 权重、梯度、动量一、动量二 */
    return q;                        /* 返回句柄供全局变量保存 */
}

/* ------------------------------ 随机数 ---------------------------------- */
static unsigned long long rng_state = 0x853c49e6748fea9bULL;  /* 固定种子，保证实验可复现 */
static unsigned int xrand(void) {
    /* xorshift64*：无依赖、速度快、统计性质足够训练用 */
    rng_state ^= rng_state >> 12;    /* 右移混淆高位 */
    rng_state ^= rng_state << 25;    /* 左移混淆低位 */
    rng_state ^= rng_state >> 27;    /* 再右移，打散相关性 */
    return (unsigned int)((rng_state * 0x2545F4914F6CDD1DULL) >> 32);  /* 乘常数后取高位输出 */
}
static float frand(void) {
    /* 生成 [0,1) 的均匀分布浮点：取 24 位有效数字，正好是 float 的尾数精度 */
    return (float)(xrand() >> 8) * (1.0f / 16777216.0f);  /* 16777216 = 2^24 */
}
static float nrand(void) {
    /* Box-Muller 变换：由两个均匀分布得到标准正态分布，用于参数初始化 */
    float u1 = frand() + 1e-7f, u2 = frand();  /* 加 1e-7 避免 log(0) */
    return sqrtf(-2.0f * logf(u1)) * cosf(6.28318530718f * u2);  /* 2π 用字面量，省一次常量加载 */
}

/* ------------------------------ 矩阵乘法（累加语义）--------------------
 * 权重统一按 [in][out] 行主序存放。
 *   mm_nn: C[M,N] += A[M,K] @ B[K,N]            (B 为 [in][out])
 *   mm_nt: C[M,N] += A[M,K] @ B[N,K]^T          (反传 dx)
 *   mm_tn: C[K,N] += A[M,K]^T @ B[M,N]          (反传 dW)
 * 注意都是 "+=" 而不是 "="：反向传播里同一个缓冲区会被多条路径累加。 */
#define PARFOR _Pragma("omp parallel for")  /* 预留的并行编译指示宏 */
static void mm_nn(const float *A, const float *Bm, float *C, int M, int K, int N) {
    /* C[M,N] += A[M,K] @ B[K,N]：前向传播的主运算 */
#ifdef _OPENMP
#pragma omp parallel for
#endif
    for (int i = 0; i < M; i++) {                 /* 逐行（逐 token）处理 */
        float *crow = C + (size_t)i * N;          /* 当前输出行，按 size_t 偏移防溢出 */
        for (int k = 0; k < K; k++) {             /* 遍历输入维度累积 */
            float a = A[(size_t)i * K + k];       /* 取出系数 */
            if (a == 0.0f) continue;              /* 稀疏跳过：ReLU 后大量为 0，能省不少时间 */
            const float *brow = Bm + (size_t)k * N;  /* 第 k 个输入对应的权重行 */
            for (int j = 0; j < N; j++) crow[j] += a * brow[j];  /* 整行乘加，连续访存 */
        }
    }
}
static void mm_nt(const float *A, const float *Bm, float *C, int M, int K, int N) {
    /* C[M,N] += A[M,K] @ B[N,K]^T：B 按输出维优先存放，常用于反传求 dx */
#ifdef _OPENMP
#pragma omp parallel for
#endif
    for (int i = 0; i < M; i++) {                 /* 逐行 */
        const float *arow = A + (size_t)i * K;    /* 当前输入行 */
        float *crow = C + (size_t)i * N;          /* 当前输出行 */
        for (int n = 0; n < N; n++) {             /* 逐输出通道 */
            const float *brow = Bm + (size_t)n * K;  /* 该通道对应的权重行 */
            float s = 0.0f;                       /* 点积累加器 */
            for (int k = 0; k < K; k++) s += arow[k] * brow[k];  /* 点积 */
            crow[n] += s;                         /* 累加到输出 */
        }
    }
}
static void mm_tn(const float *A, const float *Bm, float *C, int M, int K, int N) {
    /* C[K,N] += A[M,K]^T @ B[M,N]：外层权重梯度 dW 的计算方式，不并行避免写冲突 */
    for (int i = 0; i < M; i++) {                 /* 逐行 */
        const float *arow = A + (size_t)i * K;    /* 当前输入行（对 K 求梯度时的系数） */
        const float *brow = Bm + (size_t)i * N;   /* 当前梯度行 */
        for (int k = 0; k < K; k++) {             /* 逐输入维度 */
            float a = arow[k];                    /* 该维度的激活值 */
            float *crow = C + (size_t)k * N;      /* 对应的权重梯度行 */
            for (int j = 0; j < N; j++) crow[j] += a * brow[j];  /* 外积累加 */
        }
    }
}

/* ------------------------------ 参数 ------------------------------------ */
static Param *p_tok, *p_pos, *p_lm, *b_lm;   /* token 嵌入、位置嵌入、输出投影、输出偏置 */
static Param *Wqkv[NLAYER], *b_qkv[NLAYER], *Wo[NLAYER], *b_o[NLAYER];  /* 每层的注意力量重与偏置 */
static Param *W1[NLAYER], *b_1[NLAYER], *W2[NLAYER], *b_2[NLAYER];      /* 每层前馈网络的两层 */

/* ------------------------------ 激活缓存（每层独立！）-------------------
 * 为什么每层单独存：反向传播要用到各层前向的中间结果，
 * 如果共用一块缓冲，后面的层会覆盖前面层的值，梯度就算错了。 */
static float *h_emb;                    /* 嵌入，即第 0 层输入 */
static float *h_inv1[NLAYER], *h_ln1[NLAYER], *h_qkv[NLAYER], *h_att[NLAYER];  /* 归一化系数、归一化输出、QKV、注意力分数 */
static float *h_ao[NLAYER], *h_x1[NLAYER], *h_inv2[NLAYER], *h_ln2[NLAYER];    /* 注意力输出、残差1、归一化2相关 */
static float *h_pre[NLAYER], *h_act[NLAYER], *h_h2[NLAYER], *h_x2[NLAYER];     /* FFN 中间量、激活值、FFN 输出、残差2 */
static float *h_invf, *h_xf, *h_logits;  /* 最终归一化系数、最终隐藏状态、输出 logits */

static float *g_xin[NLAYER], *g_ln1[NLAYER], *g_qkv[NLAYER], *g_ao[NLAYER];    /* 反向传播中逐层的梯度缓冲 */
static float *g_ln2[NLAYER], *g_pre[NLAYER], *g_act[NLAYER], *g_xout[NLAYER];  /* 同上，供 FFN 与残差使用 */
static float *g_xf, *g_logits, *g_scratch;  /* 最终层梯度、logits 梯度、通用临时缓冲 */

static int *xs, *ys;  /* 当前批次的输入 token 与目标 token（目标 = 输入右移一位） */

static void alloc_activations(void) {
    /* 一次性分配所有激活与梯度缓冲，避免训练循环里反复 malloc */
    size_t BTC  = (size_t)BT * NEMBD;        /* 每个位置 NEMBD 维 */
    size_t BT3C = (size_t)BT * 3 * NEMBD;    /* QKV 拼在一起，所以是 3 倍 */
    size_t BTMLP= (size_t)BT * MLP;          /* FFN 中间层更宽 */
    size_t BTV  = (size_t)BT * VOCAB;        /* logits 是词表大小 */
    size_t ATT  = (size_t)NHEAD * B * T * T; /* 注意力分数矩阵：每个头、每条序列、T×T */

    h_emb = falloc(BTC);                     /* 嵌入输出 */
    h_invf = falloc(BT); h_xf = falloc(BTC); h_logits = falloc(BTV);  /* 最终层的三个缓冲 */
    g_xf = falloc(BTC); g_logits = falloc(BTV); g_scratch = falloc(BTC);  /* 对应梯度 */
    for (int l = 0; l < NLAYER; l++) {       /* 每层独立分配，互不覆盖 */
        h_inv1[l] = falloc(BT);   h_ln1[l] = falloc(BTC);  h_qkv[l] = falloc(BT3C);   /* 归一化与 QKV */
        h_att[l]  = falloc(ATT);  h_ao[l]  = falloc(BTC);  h_x1[l]  = falloc(BTC);    /* 注意力与残差 */
        h_inv2[l] = falloc(BT);   h_ln2[l] = falloc(BTC);  h_pre[l] = falloc(BTMLP);  /* 第二个归一化与 FFN 输入 */
        h_act[l]  = falloc(BTMLP);h_h2[l]  = falloc(BTC);  h_x2[l]  = falloc(BTC);    /* FFN 激活与输出 */

        g_xin[l]  = falloc(BTC);  g_ln1[l] = falloc(BTC);  g_qkv[l] = falloc(BT3C);   /* 反向梯度：入口、归一化1、QKV */
        g_ao[l]   = falloc(BTC);  g_ln2[l] = falloc(BTC);  g_pre[l] = falloc(BTMLP);  /* 注意力输出、归一化2、FFN 输入 */
        g_act[l]  = falloc(BTMLP);g_xout[l]= falloc(BTC);                            /* FFN 激活、出口 */
    }
    xs = (int *)calloc(BT, sizeof(int));     /* 输入 token 编号 */
    ys = (int *)calloc(BT, sizeof(int));     /* 目标 token 编号 */
}

static void zero_grads(void) {
    /* 每个训练步开始前必须清零梯度，否则上一批的梯度会累积进来 */
    for (int i = 0; i < nparams; i++)        /* 遍历所有参数张量 */
        memset(params[i].g, 0, (size_t)params[i].n * sizeof(float));  /* 按字节清零最快 */
}

/* ------------------------------ 初始化 ---------------------------------- */
static int is_bias(const char *name) {
    /* 判断参数名是不是偏置：偏置初始化为 0，权重才用随机初始化 */
    return strstr(name, ".b") != NULL || strstr(name, "bias") != NULL;  /* 兼容两种命名约定 */
}
static void init_params(void) {
    /* 按 Transformer 的标准布局注册所有参数张量 */
    p_tok = add_param("tok_emb", VOCAB * NEMBD);   /* 词嵌入矩阵：词表 × 维度 */
    p_pos = add_param("pos_emb", T * NEMBD);       /* 位置嵌入：学出来的绝对位置编码 */
    for (int l = 0; l < NLAYER; l++) {             /* 每层一套参数 */
        char buf[64];                              /* 参数名缓冲 */
        snprintf(buf, sizeof buf, "L%d.Wqkv", l); Wqkv[l] = add_param(buf, 3 * NEMBD * NEMBD);  /* Q/K/V 合并成一个矩阵，省一次乘法 */
        snprintf(buf, sizeof buf, "L%d.bqkv", l); b_qkv[l] = add_param(buf, 3 * NEMBD);         /* 对应的偏置 */
        snprintf(buf, sizeof buf, "L%d.Wo",   l); Wo[l]   = add_param(buf, NEMBD * NEMBD);      /* 注意力输出投影 */
        snprintf(buf, sizeof buf, "L%d.bo",   l); b_o[l]  = add_param(buf, NEMBD);              /* 输出投影偏置 */
        snprintf(buf, sizeof buf, "L%d.W1",   l); W1[l]   = add_param(buf, NEMBD * MLP);        /* FFN 第一层：升维 */
        snprintf(buf, sizeof buf, "L%d.b1",   l); b_1[l]  = add_param(buf, MLP);                /* FFN 第一层偏置 */
        snprintf(buf, sizeof buf, "L%d.W2",   l); W2[l]   = add_param(buf, MLP * NEMBD);        /* FFN 第二层：降维 */
        snprintf(buf, sizeof buf, "L%d.b2",   l); b_2[l]  = add_param(buf, NEMBD);              /* FFN 第二层偏置 */
    }
    p_lm = add_param("lm_head", NEMBD * VOCAB);    /* 输出投影到词表 */
    b_lm = add_param("lm_bias", VOCAB);            /* 输出偏置 */

    long total = 0;                                /* 统计总参数量 */
    for (int i = 0; i < nparams; i++) {            /* 逐个张量初始化 */
        Param *q = &params[i];                     /* 当前张量 */
        total += q->n;                             /* 累加参数量 */
        if (is_bias(q->name)) { memset(q->p, 0, (size_t)q->n * sizeof(float)); continue; }  /* 偏置置零 */
        float scale = strcmp(q->name, "lm_head") == 0 ? 0.001f : 0.02f;  /* 输出层用小方差，减少初始 logits 的噪声 */
        for (int j = 0; j < q->n; j++) q->p[j] = scale * nrand();        /* 其余权重用正态分布 */
    }
    printf("参数张量 %d 个，参数总量 %ld (%.3fM)\n", nparams, total, total / 1e6);  /* 报告规模，便于判断是否超出内存 */
}

/* ------------------------------ RMSNorm --------------------------------
 * 为什么用 RMSNorm 而不是 LayerNorm：不需要减均值，少一次遍历，
 * 且经验上对语言模型效果几乎一致（LLaMA 系列都用它）。 */
static void rmsnorm_fwd(const float *x, float *out, float *inv_out, int rows) {
    /* 前向：out = x / sqrt(mean(x^2) + eps)，逐行独立归一化 */
    for (int r = 0; r < rows; r++) {                       /* 逐行（逐 token）处理 */
        const float *xr = x + (size_t)r * NEMBD;           /* 当前行数据 */
        float ss = 0.0f;                                   /* 平方和 */
        for (int c = 0; c < NEMBD; c++) ss += xr[c] * xr[c];  /* 累加平方 */
        float inv = 1.0f / sqrtf(ss / NEMBD + RMS_EPS);    /* 取倒数平方根，加 eps 防除零 */
        inv_out[r] = inv;                                  /* 缓存系数，反向传播要用 */
        float *orow = out + (size_t)r * NEMBD;             /* 输出行 */
        for (int c = 0; c < NEMBD; c++) orow[c] = xr[c] * inv;  /* 缩放 */
    }
}
static void rmsnorm_bwd(const float *x, const float *inv, const float *dy,
                        float *dx, int rows) {
    /* 反向：对 y = x * g 求导，g 依赖 x 自身，所以梯度有一项修正 */
    for (int r = 0; r < rows; r++) {                       /* 逐行 */
        const float *xr = x + (size_t)r * NEMBD;           /* 前向输入 */
        const float *dr = dy + (size_t)r * NEMBD;          /* 上游梯度 */
        float *dxr = dx + (size_t)r * NEMBD;               /* 下游梯度（累加） */
        float g = inv[r], s = 0.0f;                        /* 缓存的系数与点积累加器 */
        for (int c = 0; c < NEMBD; c++) s += dr[c] * xr[c];  /* 计算 g 对 x 的导数所需的点积 */
        float k = g * g * g * s / NEMBD;                   /* 修正项系数 */
        for (int c = 0; c < NEMBD; c++) dxr[c] += g * dr[c] - k * xr[c];  /* 主项减修正项 */
    }
}

/* ------------------------------ 前向传播 -------------------------------- */
static void forward(void) {
    /* 嵌入：把 token 编号换成向量，再加上位置编码 */
    for (int i = 0; i < BT; i++) {                    /* 遍历批次里的每个位置 */
        int tok = xs[i], t = i % T;                   /* i%T 得到该位置在序列中的序号 */
        const float *te = p_tok->p + (size_t)tok * NEMBD;  /* 该 token 的词嵌入行 */
        const float *pe = p_pos->p + (size_t)t * NEMBD;    /* 该位置的位置嵌入行 */
        float *o = h_emb + (size_t)i * NEMBD;         /* 输出行 */
        for (int c = 0; c < NEMBD; c++) o[c] = te[c] + pe[c];  /* 直接相加，最经典的做法 */
    }

    const float *x_in = h_emb;                        /* 逐层传递的隐藏状态，起始为嵌入 */
    for (int l = 0; l < NLAYER; l++) {                /* 逐层前向 */
        /* ---- 注意力子层 ---- */
        rmsnorm_fwd(x_in, h_ln1[l], h_inv1[l], BT);   /* 先归一化，稳定数值 */
        memset(h_qkv[l], 0, (size_t)BT * 3 * NEMBD * sizeof(float));  /* mm_nn 是累加语义，必须先清零 */
        mm_nn(h_ln1[l], Wqkv[l]->p, h_qkv[l], BT, NEMBD, 3 * NEMBD);  /* 一次算出 Q、K、V */
        for (int i = 0; i < BT; i++) {                /* 加上 QKV 偏置 */
            float *q = h_qkv[l] + (size_t)i * 3 * NEMBD;  /* 当前行的 QKV 起点 */
            for (int c = 0; c < 3 * NEMBD; c++) q[c] += b_qkv[l]->p[c];  /* 偏置对 Q/K/V 三段共用同一组下标 */
        }

        float scale = 1.0f / sqrtf((float)HD);        /* 缩放因子 1/sqrt(d_k)，防止点积随维度爆炸 */
#ifdef _OPENMP
#pragma omp parallel for collapse(2)                  /* batch 与 head 两个维度都可并行 */
#endif
        for (int b = 0; b < B; b++) {                 /* 逐条序列 */
            for (int h = 0; h < NHEAD; h++) {         /* 逐个头 */
                int hoff = h * HD;                    /* 该头在 NEMBD 维里的起始偏移 */
                for (int t = 0; t < T; t++) {         /* 逐时间步（当前 token） */
                    const float *q = h_qkv[l] + ((size_t)(b * T + t) * 3 * NEMBD) + hoff;  /* 当前 token 的 Q */
                    float *att = h_att[l] + (((size_t)b * NHEAD + h) * T + t) * T;         /* 该头的注意力分数行 */
                    float maxs = -1e30f;              /* 用于 softmax 的数值稳定（减去最大值） */
                    for (int u = 0; u <= t; u++) {    /* 因果掩码：只能看自己和之前的 token */
                        const float *k = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + NEMBD + hoff;  /* K 在第二段 */
                        float s = 0.0f;               /* 点积累加器 */
                        for (int d = 0; d < HD; d++) s += q[d] * k[d];  /* q·k */
                        s *= scale;                   /* 缩放 */
                        att[u] = s;                   /* 暂存分数 */
                        if (s > maxs) maxs = s;       /* 记录最大值 */
                    }
                    float sum = 0.0f;                 /* softmax 分母 */
                    for (int u = 0; u <= t; u++) { att[u] = expf(att[u] - maxs); sum += att[u]; }  /* 减最大值再取指数，防溢出 */
                    float inv = 1.0f / sum;           /* 归一化因子 */
                    for (int u = 0; u <= t; u++) att[u] *= inv;  /* 得到概率分布，原地覆盖 */

                    float *ao = h_ao[l] + (size_t)(b * T + t) * NEMBD + hoff;  /* 该头的输出 */
                    for (int d = 0; d < HD; d++) ao[d] = 0.0f;                  /* 清零后累加 */
                    for (int u = 0; u <= t; u++) {                              /* 对所有可见位置加权求和 */
                        const float *v = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + 2 * NEMBD + hoff;  /* V 在第三段 */
                        float a = att[u];                                       /* 权重 */
                        for (int d = 0; d < HD; d++) ao[d] += a * v[d];         /* 加权累加 */
                    }
                }
            }
        }

        memset(g_scratch, 0, (size_t)BT * NEMBD * sizeof(float));   /* 复用为投影输出 */
        mm_nn(h_ao[l], Wo[l]->p, g_scratch, BT, NEMBD, NEMBD);      /* 多头拼接后做输出投影 */
        for (int i = 0; i < BT; i++) {                              /* 残差连接 + 偏置 */
            const float *xi = x_in + (size_t)i * NEMBD;             /* 子层输入 */
            const float *ao = g_scratch + (size_t)i * NEMBD;        /* 子层输出 */
            float *x1 = h_x1[l] + (size_t)i * NEMBD;                /* 残差后的结果 */
            for (int c = 0; c < NEMBD; c++) x1[c] = xi[c] + ao[c] + b_o[l]->p[c];  /* x + 子层(x) + b */
        }

        /* ---- 前馈子层 ---- */
        rmsnorm_fwd(h_x1[l], h_ln2[l], h_inv2[l], BT);              /* 第二个 RMSNorm */
        memset(h_pre[l], 0, (size_t)BT * MLP * sizeof(float));      /* 清零，mm_nn 是累加 */
        mm_nn(h_ln2[l], W1[l]->p, h_pre[l], BT, NEMBD, MLP);        /* 升维投影 */
        for (int i = 0; i < BT; i++) {                              /* 加偏置并做 ReLU */
            float *pr = h_pre[l] + (size_t)i * MLP;                 /* 升维后的值 */
            float *ac = h_act[l] + (size_t)i * MLP;                 /* 激活后的值 */
            for (int j = 0; j < MLP; j++) {
                float v = pr[j] + b_1[l]->p[j];                     /* 先加偏置 */
                pr[j] = v;                                          /* 反向传播要用加偏置后的值判断 ReLU 是否激活 */
                ac[j] = v > 0.0f ? v : 0.0f;          /* ReLU */
            }
        }
        memset(h_h2[l], 0, (size_t)BT * NEMBD * sizeof(float));     /* 清零 */
        mm_nn(h_act[l], W2[l]->p, h_h2[l], BT, MLP, NEMBD);         /* 降维投影 */
        for (int i = 0; i < BT; i++) {                              /* 第二次残差连接 */
            const float *x1 = h_x1[l] + (size_t)i * NEMBD;          /* 子层输入 */
            const float *hh = h_h2[l] + (size_t)i * NEMBD;          /* 子层输出 */
            float *x2 = h_x2[l] + (size_t)i * NEMBD;                /* 本层最终输出 */
            for (int c = 0; c < NEMBD; c++) x2[c] = x1[c] + hh[c] + b_2[l]->p[c];  /* x + FFN(x) + b */
        }
        x_in = h_x2[l];                                /* 本层输出 = 下一层输入 */
    }

    /* ---- 输出层 ---- */
    rmsnorm_fwd(x_in, h_xf, h_invf, BT);                        /* 最后一层归一化 */
    memset(h_logits, 0, (size_t)BT * VOCAB * sizeof(float));    /* 清零 */
    mm_nn(h_xf, p_lm->p, h_logits, BT, NEMBD, VOCAB);           /* 投影到词表维度 */
    for (int i = 0; i < BT; i++)                                /* 加输出偏置 */
        for (int v = 0; v < VOCAB; v++) h_logits[(size_t)i * VOCAB + v] += b_lm->p[v];  /* 每个词表项一个偏置 */
}

/* softmax + 交叉熵，并把 dL/dlogits 写进 g_logits */
static float loss_and_grad(void) {
    /* 为什么把损失和梯度写在一起：交叉熵对 logits 的导数有解析式 p - onehot，
       直接在同一个循环里算完最省事，也避免重复遍历 */
    float loss = 0.0f, scale = 1.0f / (float)BT;  /* scale 用于对 batch 取平均 */
    for (int i = 0; i < BT; i++) {                 /* 逐位置 */
        float *lg = h_logits + (size_t)i * VOCAB;  /* 当前位置的 logits，会被原地改成概率 */
        float maxl = lg[0];                        /* 数值稳定：先找最大值 */
        for (int v = 1; v < VOCAB; v++) if (lg[v] > maxl) maxl = lg[v];  /* 取最大 logit */
        float sum = 0.0f;                          /* 指数和 */
        for (int v = 0; v < VOCAB; v++) { lg[v] = expf(lg[v] - maxl); sum += lg[v]; }  /* 减最大值再取指数，防溢出 */
        float inv = 1.0f / sum;                    /* 归一化因子 */
        for (int v = 0; v < VOCAB; v++) lg[v] *= inv;  /* 原地变成概率分布 */
        int target = ys[i];                        /* 正确的下一个 token */
        loss += -logf(lg[target] + 1e-9f);         /* 加 1e-9 防 log(0) 得到 inf */
        float *dl = g_logits + (size_t)i * VOCAB;  /* 本位置的梯度缓冲 */
        for (int v = 0; v < VOCAB; v++) dl[v] = (lg[v] - (v == target ? 1.0f : 0.0f)) * scale;  /* softmax 的雅可比：p - onehot */
    }
    return loss * scale;                          /* 返回平均损失 */
}

/* ------------------------------ 反向传播 -------------------------------- */
static void backward(void) {
    /* 从输出层开始，逐层把梯度往回传；每一步都是上一层输入梯度的累加 */
    memset(g_xf, 0, (size_t)BT * NEMBD * sizeof(float));           /* 清零，mm_nt 是累加 */
    mm_nt(g_logits, p_lm->p, g_xf, BT, VOCAB, NEMBD);              /* dxf   */
    mm_tn(h_xf, g_logits, p_lm->g, BT, NEMBD, VOCAB);              /* dW_lm */
    for (int i = 0; i < BT; i++)                                    /* 输出偏置的梯度 */
        for (int v = 0; v < VOCAB; v++) b_lm->g[v] += g_logits[(size_t)i * VOCAB + v];  /* 偏置梯度 = 各位置梯度之和 */

    float *d_out = g_scratch;                                       /* 上一层输出梯度 */
    memset(g_xout[NLAYER - 1], 0, (size_t)BT * NEMBD * sizeof(float));  /* 清零 */
    rmsnorm_bwd(h_x2[NLAYER - 1], h_invf, g_xf, g_xout[NLAYER - 1], BT);  /* 穿过最后的 RMSNorm */
    memcpy(d_out, g_xout[NLAYER - 1], (size_t)BT * NEMBD * sizeof(float));  /* 复制到工作缓冲，避免反复寻址 */

    for (int l = NLAYER - 1; l >= 0; l--) {                          /* 从最后一层往回 */
        const float *x_in = (l == 0) ? h_emb : h_x2[l - 1];          /* 本层输入：第 0 层是嵌入，否则是上一层输出 */

        /* ---- 前馈子层反向 ---- */
        memset(g_xin[l], 0, (size_t)BT * NEMBD * sizeof(float));      /* 清零，下面会累加两条支路 */
        memcpy(g_xin[l], d_out, (size_t)BT * NEMBD * sizeof(float));   /* 恒等支路 → x1 */
        for (int i = 0; i < BT; i++)                                   /* FFN 输出偏置的梯度 */
            for (int c = 0; c < NEMBD; c++) b_2[l]->g[c] += d_out[(size_t)i * NEMBD + c];  /* 求和 */

        memset(g_act[l], 0, (size_t)BT * MLP * sizeof(float));         /* 清零 */
        mm_nt(d_out, W2[l]->p, g_act[l], BT, NEMBD, MLP);              /* d act */
        mm_tn(h_act[l], d_out, W2[l]->g, BT, MLP, NEMBD);              /* dW2   */

        for (int i = 0; i < BT; i++) {                                 /* 穿过 ReLU */
            const float *pr = h_pre[l] + (size_t)i * MLP;              /* 加偏置后的值 */
            const float *ga = g_act[l] + (size_t)i * MLP;              /* 激活后的梯度 */
            float *gp = g_pre[l] + (size_t)i * MLP;                    /* 激活前的梯度 */
            for (int j = 0; j < MLP; j++) gp[j] = pr[j] > 0.0f ? ga[j] : 0.0f;  /* ReLU'：>0 才传梯度 */
        }
        memset(g_ln2[l], 0, (size_t)BT * NEMBD * sizeof(float));       /* 清零 */
        mm_nt(g_pre[l], W1[l]->p, g_ln2[l], BT, MLP, NEMBD);           /* d ln2 */
        mm_tn(h_ln2[l], g_pre[l], W1[l]->g, BT, NEMBD, MLP);           /* dW1   */
        for (int i = 0; i < BT; i++)                                    /* FFN 第一层偏置梯度 */
            for (int j = 0; j < MLP; j++) b_1[l]->g[j] += g_pre[l][(size_t)i * MLP + j];  /* 求和 */
        rmsnorm_bwd(h_x1[l], h_inv2[l], g_ln2[l], g_xin[l], BT);        /* → x1，累加到恒等支路上 */

        /* ---- 注意力子层反向 ---- */
        memset(g_ao[l], 0, (size_t)BT * NEMBD * sizeof(float));        /* 清零 */
        memcpy(g_ao[l], g_xin[l], (size_t)BT * NEMBD * sizeof(float));  /* 恒等支路 → x_in */
        for (int i = 0; i < BT; i++)                                    /* 注意力输出偏置梯度 */
            for (int c = 0; c < NEMBD; c++) b_o[l]->g[c] += g_ao[l][(size_t)i * NEMBD + c];  /* 求和 */

        memset(g_ln1[l], 0, (size_t)BT * NEMBD * sizeof(float));       /* 暂存 d(ao投影前) */
        mm_nt(g_ao[l], Wo[l]->p, g_ln1[l], BT, NEMBD, NEMBD);           /* d ao  */
        mm_tn(h_ao[l], g_ao[l], Wo[l]->g, BT, NEMBD, NEMBD);            /* dWo   */

        const float *dao = g_ln1[l];                                    /* 注意力的上游梯度 */
        memset(g_qkv[l], 0, (size_t)BT * 3 * NEMBD * sizeof(float));    /* 清零，Q/K/V 梯度会累加 */
        float scale = 1.0f / sqrtf((float)HD);                          /* 与前向一致的缩放 */
#ifdef _OPENMP
#pragma omp parallel for collapse(2)                                   /* 与前面一样按 batch×head 并行 */
#endif
        for (int b = 0; b < B; b++) {                                   /* 逐序列 */
            for (int h = 0; h < NHEAD; h++) {                           /* 逐头 */
                int hoff = h * HD;                                      /* 头的起始偏移 */
                float datt[8192];                                       /* 该行的注意力梯度，栈上固定大小 */
                for (int t = 0; t < T; t++) {                           /* 逐时间步 */
                    const float *att = h_att[l] + (((size_t)b * NHEAD + h) * T + t) * T;  /* 前向的概率 */
                    const float *do_ = dao + (size_t)(b * T + t) * NEMBD + hoff;          /* 该位置的上游梯度 */
                    float *dq = g_qkv[l] + ((size_t)(b * T + t) * 3 * NEMBD) + hoff;      /* Q 的梯度 */
                    float dsum = 0.0f;                                  /* softmax 反向需要的点积和 */
                    for (int u = 0; u <= t; u++) {                      /* 先算 dL/datt */
                        const float *v = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + 2 * NEMBD + hoff;  /* V */
                        float s = 0.0f;                                 /* 点积 */
                        for (int d = 0; d < HD; d++) s += do_[d] * v[d];  /* do · v */
                        datt[u] = s;                                    /* 暂存 */
                        dsum += s * att[u];                             /* 累加 softmax 修正项 */
                    }
                    for (int d = 0; d < HD; d++) dq[d] = 0.0f;          /* Q 梯度先清零 */
                    for (int u = 0; u <= t; u++) {                      /* 对每个可见位置回传 */
                        float ds = att[u] * (datt[u] - dsum);          /* softmax 反向 */
                        const float *v  = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + 2 * NEMBD + hoff;  /* 前向 V */
                        float *dv = g_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + 2 * NEMBD + hoff;        /* V 梯度 */
                        for (int d = 0; d < HD; d++) dv[d] += att[u] * do_[d];  /* dV += att * do */
                        const float *q = h_qkv[l] + ((size_t)(b * T + t) * 3 * NEMBD) + hoff;  /* 前向 Q */
                        const float *k = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + NEMBD + hoff;  /* 前向 K */
                        float *dk = g_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + NEMBD + hoff;        /* K 梯度 */
                        for (int d = 0; d < HD; d++) {                  /* Q、K 的梯度 */
                            dq[d] += ds * k[d] * scale;                 /* dQ += ds * K * scale */
                            dk[d] += ds * q[d] * scale;                 /* dK += ds * Q * scale */
                        }
                    }
                }
            }
        }

        memset(g_ln1[l], 0, (size_t)BT * NEMBD * sizeof(float));        /* 复用缓冲存 d(ln1) */
        mm_nt(g_qkv[l], Wqkv[l]->p, g_ln1[l], BT, 3 * NEMBD, NEMBD);    /* d ln1  */
        mm_tn(h_ln1[l], g_qkv[l], Wqkv[l]->g, BT, NEMBD, 3 * NEMBD);    /* dWqkv  */
        for (int i = 0; i < BT; i++)                                     /* QKV 偏置梯度 */
            for (int c = 0; c < 3 * NEMBD; c++) b_qkv[l]->g[c] += g_qkv[l][(size_t)i * 3 * NEMBD + c];  /* 求和 */

        /* g_xin[l] 此刻已经是完整的 dL/dx1(= dL/d attn投影 也等于恒等支路对 x_in 的贡献)，
           再补上经过 RMSNorm1 的那条支路，就得到 dL/d(x_in) */
        rmsnorm_bwd(x_in, h_inv1[l], g_ln1[l], g_xin[l], BT);

        memcpy(d_out, g_xin[l], (size_t)BT * NEMBD * sizeof(float));
    }

    /* 嵌入梯度 */
    for (int i = 0; i < BT; i++) {
        int tok = xs[i], t = i % T;
        const float *d = d_out + (size_t)i * NEMBD;
        for (int c = 0; c < NEMBD; c++) {
            p_tok->g[(size_t)tok * NEMBD + c] += d[c];
            p_pos->g[(size_t)t * NEMBD + c]   += d[c];
        }
    }
}

/* ------------------------------ AdamW ---------------------------------- */
static float grad_norm(void) {
    /* 计算所有参数梯度的全局 L2 范数，用于按范数裁剪 */
    double s = 0.0;                                  /* 用 double 累加，避免几百万项相加丢精度 */
    for (int i = 0; i < nparams; i++)                /* 遍历每个张量 */
        for (int j = 0; j < params[i].n; j++)        /* 遍历每个元素 */
            s += (double)params[i].g[j] * params[i].g[j];  /* 累加平方 */
    return (float)sqrt(s);                           /* 开方得到范数 */
}
static void adamw_step(float lr, int step) {
    /* AdamW：带权重衰减的 Adam，衰减项与梯度更新解耦（这是 W 的含义） */
    float b1 = 0.9f, b2 = 0.95f, eps = 1e-8f, wd = 0.01f;  /* 一阶/二阶动量系数、数值保护、权重衰减 */
    float bc1 = 1.0f - powf(b1, (float)step);        /* 一阶动量的偏差修正，step 越小修正越强 */
    float bc2 = 1.0f - powf(b2, (float)step);        /* 二阶动量的偏差修正 */
    float gn = grad_norm();                          /* 当前梯度范数 */
    float clip = gn > 1.0f ? 1.0f / gn : 1.0f;      /* 全局梯度裁剪：范数超过 1 就整体缩小，防梯度爆炸 */
    for (int i = 0; i < nparams; i++) {              /* 逐个张量更新 */
        Param *q = &params[i];                       /* 当前张量 */
        for (int j = 0; j < q->n; j++) {             /* 逐个元素更新 */
            float g = q->g[j] * clip;                /* 应用裁剪系数 */
            q->m[j] = b1 * q->m[j] + (1 - b1) * g;   /* 一阶动量：梯度的指数滑动平均 */
            q->v[j] = b2 * q->v[j] + (1 - b2) * g * g;  /* 二阶动量：梯度平方的滑动平均 */
            float mh = q->m[j] / bc1, vh = q->v[j] / bc2;  /* 偏差修正后的动量 */
            q->p[j] -= lr * (mh / (sqrtf(vh) + eps) + wd * q->p[j]);  /* 参数更新：自适应步长 + 解耦衰减 */
        }
    }
}

/* ------------------------------ 语料与词表 ------------------------------ */
static unsigned char *corpus;   /* 原始语料字节流 */
static int  *tokens;            /* 编码后的 token 序列，训练直接取这个 */
static long  ncorpus, ntrain, nval;  /* 总长、训练段长度、验证段长度 */

#ifdef CHARLEVEL
/* ===== 字符级：一个汉字就是一个 token，模型只能吐出完整字符，不会出乱码 ===== */
static int  vocab_cp[VOCAB];          /* id -> Unicode 码点 */
#define CMAP 8192                     /* 字符哈希表容量，2 的幂便于用掩码取模 */
static int  cmap_cp[CMAP];            /* 键：码点，-1 表示空槽 */
static int  cmap_id[CMAP];            /* 值：对应的 id */
static void cmap_init(void) { for (int i = 0; i < CMAP; i++) cmap_cp[i] = -1; }  /* 全部标空 */
static int char_id(int cp) {
    /* 开放寻址哈希查找：码点 -> id，找不到返回 0（未知字符） */
    unsigned h = (unsigned)cp * 2654435761u;   /* 乘法散列，把码点打散 */
    int b = (int)(h & (CMAP - 1));             /* 起始槽位 */
    while (cmap_cp[b] != -1) {                 /* 线性探测 */
        if (cmap_cp[b] == cp) return cmap_id[b];  /* 命中 */
        b = (b + 1) & (CMAP - 1);              /* 下一个槽位，掩码实现环形 */
    }
    return 0;                                  /* 没找到 */
}
static void cmap_put(int cp, int id) {
    /* 插入或更新一个映射 */
    unsigned h = (unsigned)cp * 2654435761u;   /* 与查找一致 */
    int b = (int)(h & (CMAP - 1));             /* 起始槽位 */
    while (cmap_cp[b] != -1 && cmap_cp[b] != cp) b = (b + 1) & (CMAP - 1);  /* 找到空槽或同键 */
    cmap_cp[b] = cp; cmap_id[b] = id;          /* 写入 */
}
static int u8_get(const unsigned char *p, int *len) {
    /* UTF-8 解码：返回码点，*len 是消耗的字节数 */
    if (p[0] < 0x80) { *len = 1; return p[0]; }  /* ASCII 单字节 */
    if ((p[0] & 0xE0) == 0xC0) { *len = 2; return ((p[0] & 0x1F) << 6) | (p[1] & 0x3F); }  /* 两字节 */
    if ((p[0] & 0xF0) == 0xE0) { *len = 3; return ((p[0] & 0x0F) << 12) | ((p[1] & 0x3F) << 6) | (p[2] & 0x3F); }  /* 三字节，汉字大多在这 */
    *len = 4; return ((p[0] & 0x07) << 18) | ((p[1] & 0x3F) << 12) | ((p[2] & 0x3F) << 6) | (p[3] & 0x3F);  /* 四字节，emoji 等 */
}
static int u8_put(int cp, char *buf) {
    /* UTF-8 编码：把码点写进 buf，返回字节数 */
    if (cp < 0x80) { buf[0] = (char)cp; return 1; }  /* ASCII */
    if (cp < 0x800) { buf[0] = (char)(0xC0 | (cp >> 6)); buf[1] = (char)(0x80 | (cp & 0x3F)); return 2; }  /* 两字节 */
    if (cp < 0x10000) { buf[0] = (char)(0xE0 | (cp >> 12)); buf[1] = (char)(0x80 | ((cp >> 6) & 0x3F)); buf[2] = (char)(0x80 | (cp & 0x3F)); return 3; }  /* 三字节 */
    buf[0] = (char)(0xF0 | (cp >> 18)); buf[1] = (char)(0x80 | ((cp >> 12) & 0x3F));  /* 四字节高两位 */
    buf[2] = (char)(0x80 | ((cp >> 6) & 0x3F)); buf[3] = (char)(0x80 | (cp & 0x3F));  /* 四字节低两位 */
    return 4;  /* 返回消耗的字节数 */
}
#else
static unsigned char vocab[VOCAB];  /* 字节级：id -> 字节值 */
static int   byte2id[256];          /* 字节 -> id */
#endif

/* UTF-8 字符串 -> id 序列 */
static int str_to_ids(const char *s, int *out, int maxn) {
    /* 把提示词转成模型可吃的 id 序列，返回个数 */
    int n = 0;                                     /* 已转换个数 */
#ifdef CHARLEVEL
    const unsigned char *p = (const unsigned char *)s;  /* 按字节游标前进 */
    while (*p && n < maxn) { int len; int cp = u8_get(p, &len); out[n++] = char_id(cp); p += len; }  /* 逐字符解码 */
#else
    while (s[n] && n < maxn) { out[n] = byte2id[(unsigned char)s[n]]; n++; }  /* 逐字节查表 */
#endif
    return n;                                      /* 返回数量 */
}
/* id -> 文本字节，返回字节数 */
static int id_to_out(int id, char *out) {
    /* 把模型输出的 id 还原成可打印字节 */
#ifdef CHARLEVEL
    return u8_put(vocab_cp[id], out);              /* 字符级：编码成 UTF-8 */
#else
    out[0] = (char)vocab[id];                      /* 字节级：直接是那个字节 */
    return 1;                                      /* 单字节 */
#endif
}

static int load_corpus(const char *path) {
    /* 读取语料、建立词表、把全文编码成 token 序列 */
    FILE *f = fopen(path, "rb");                   /* 二进制读，避免 Windows 把 \r\n 换掉 */
    if (!f) { fprintf(stderr, "打不开语料: %s\n", path); return -1; }  /* 打不开就报错退出 */
    fseek(f, 0, SEEK_END); ncorpus = ftell(f); fseek(f, 0, SEEK_SET);  /* 先取文件大小再回到开头 */
    corpus = (unsigned char *)malloc((size_t)ncorpus);  /* 一次性读进内存 */
    if (fread(corpus, 1, (size_t)ncorpus, f) != (size_t)ncorpus) { fclose(f); return -1; }  /* 读不全说明文件异常 */
    fclose(f);                                     /* 及时关闭句柄 */

    if (ncorpus < 1000) {                          /* 几百字节的语料训练不出东西 */
        fprintf(stderr, "语料太小（%ld 字节），至少需要 1000 字节\n", ncorpus);
        return -1;                                 /* 拒绝训练 */
    }
#ifdef CHARLEVEL
    {
        static int freq[0x10000];                  /* 只统计 BMP 内的码点，覆盖所有常用汉字 */
        memset(freq, 0, sizeof freq);              /* 清零计数 */
        long ncp = 0;                              /* 字符总数 */
        for (long i = 0; i < ncorpus; ) {          /* 第一遍：统计频次 */
            int len; int cp = u8_get(corpus + i, &len);  /* 解码一个字符 */
            if (cp > 0 && cp < 0x10000) freq[cp]++;      /* 只统计 BMP */
            i += len; ncp++;                             /* 前进 */
        }
        cmap_init();                               /* 准备哈希表 */
        int k = 0;                                 /* 已选字符数 */
        for (; k < VOCAB; k++) {                   /* 选频次最高的 VOCAB 个字符 */
            int best = -1; long bestc = 0;         /* 本轮最优 */
            for (int c = 1; c < 0x10000; c++)      /* 线性扫描，只在启动时做一次可接受 */
                if (freq[c] > bestc) { bestc = freq[c]; best = c; }  /* 找最大 */
            if (best < 0) break;                   /* 没有更多字符了 */
            freq[best] = 0;                        /* 标记已选，下次跳过 */
            vocab_cp[k] = best;                    /* 记录 id -> 码点 */
            cmap_put(best, k);                     /* 建立反向映射 */
        }
        for (; k < VOCAB; k++) { vocab_cp[k] = 0xFFFD; }   /* 剩余槽位占位 */
        int *tok = (int *)malloc(sizeof(int) * (size_t)(ncp + 1));  /* 预分配 token 数组 */
        long nt = 0;                               /* 实际 token 数 */
        for (long i = 0; i < ncorpus; ) {          /* 第二遍：编码全文 */
            int len; int cp = u8_get(corpus + i, &len);
            tok[nt++] = char_id(cp);               /* 查表转 id，未知字符映射到 0 */
            i += len;                              /* 前进 */
        }
        tokens = tok;                              /* 保存结果 */
        ncorpus = nt;                       /* 这里是"字符数" */
        ntrain = (long)(ncorpus * 0.98);           /* 前 98% 做训练 */
        if (ncorpus - ntrain < T + 2) ntrain = ncorpus - (T + 2);  /* 验证集至少留一个上下文，否则采样越界 */
        if (ntrain < 1) ntrain = 1;                /* 极小语料兜底 */
        nval = ncorpus - ntrain;                   /* 后 2% 做验证，用来判断是否过拟合 */
        printf("语料 %ld 个字符 | 训练 %ld | 验证 %ld | 字表 %d 个字符\n", ncorpus, ntrain, nval, k);
        return 0;                                  /* 成功 */
    }
#else
    {
        long freq[256];                            /* 字节频次 */
        memset(freq, 0, sizeof freq);
        for (long i = 0; i < ncorpus; i++) freq[corpus[i]]++;  /* 统计每个字节出现次数 */
        for (int k = 0; k < VOCAB; k++) {          /* 按频次从高到低填词表 */
            int best = -1; long bestc = -1;
            for (int b = 0; b < 256; b++) {        /* 找当前最高频且未用过的字节 */
                int used = 0;
                for (int j = 0; j < k; j++) if (vocab[j] == b) { used = 1; break; }  /* 是否已选 */
                if (!used && freq[b] > bestc) { bestc = freq[b]; best = b; }        /* 更新最优 */
            }
            vocab[k] = (unsigned char)best;        /* 记录 */
        }
        for (int b = 0; b < 256; b++) byte2id[b] = 0;      /* 默认都映射到 0 */
        for (int k = 0; k < VOCAB; k++) byte2id[vocab[k]] = k;  /* 建立反向映射 */
        tokens = (int *)malloc((size_t)ncorpus * sizeof(int));  /* 每个字节一个 token */
        for (long i = 0; i < ncorpus; i++) tokens[i] = byte2id[corpus[i]];  /* 编码 */
        ntrain = (long)(ncorpus * 0.98);           /* 训练/验证切分 */
        if (ncorpus - ntrain < T + 2) ntrain = ncorpus - (T + 2);  /* 同上：验证集不能短于上下文 */
        if (ntrain < 1) ntrain = 1;                /* 兜底 */
        nval   = ncorpus - ntrain;
        printf("语料 %ld 字节 | 训练 %ld | 验证 %ld | 字符表 %d 种\n", ncorpus, ntrain, nval, VOCAB);
        return 0;                                  /* 成功 */
    }
#endif
}
static void sample_batch(int val_split) {
    /* 从语料里随机截取 B 条长度 T 的片段作为一批训练数据 */
    long span = (val_split ? ntrain + nval : ntrain) - (val_split ? ntrain : 0) - T - 1;  /* 可用起点范围 */
    if (span <= 0) span = 1;                       /* 语料太小时跨度会变负，取模后成天文数字导致越界，这里夹到 1 */
    long lo = val_split ? ntrain : 0;              /* 验证集从 ntrain 之后开始 */
    long hi = val_split ? ntrain + nval : ntrain;  /* 结束位置 */
    for (int b = 0; b < B; b++) {                  /* 逐条序列 */
        long start = lo + (long)(xrand() % (unsigned)span);  /* 用夹过的 span，避免负数取模 */  /* 随机起点，保证后面有 T+1 个 token */
        for (int t = 0; t < T; t++) {              /* 逐位置 */
            xs[b * T + t] = tokens[start + t];     /* 输入：当前位置的 token */
            ys[b * T + t] = tokens[start + t + 1]; /* 目标：下一个位置的 token（语言模型的自监督目标） */
        }
    }
}
static float eval_loss(int batches) {
    /* 在验证集上估平均损失，不更新参数 */
    float tot = 0.0f;                              /* 累加损失 */
    for (int i = 0; i < batches; i++) { sample_batch(1); forward(); tot += loss_and_grad(); }  /* 每批都重新采样 */
    return tot / batches;                          /* 返回平均 */
}

/* ------------------------------ 文本生成 -------------------------------- */
static void generate(const char *prompt, int nchars) {
    /* 自回归生成：每次前向算出下一个 token 的分布，采样一个接上去 */
    static int ctx[8192];                          /* 上下文：提示词 + 已生成的 token */
    int n = str_to_ids(prompt, ctx, 8000);         /* 提示词编码进上下文 */
    if (n == 0) { ctx[n++] = str_to_ids("\n", ctx + n, 1); }  /* 空提示词就用换行开头，避免空上下文 */

    int savedB = B;                                /* 保存原 batch 大小，生成只用 1 条序列 */
    B = 1;                                    /* 生成只用一条序列 */
    printf("--- 生成 %d 字符 | 提示: \"%s\" ---\n", nchars, prompt);  /* 打印表头 */
    for (int i = 0; i < n; i++) { char ob[8]; int k = id_to_out(ctx[i], ob); fwrite(ob, 1, (size_t)k, stdout); }  /* 先回显提示词 */
    for (int s = 0; s < nchars; s++) {             /* 逐个生成字符 */
        int len = n < T ? n : T;                   /* 上下文不能超过模型窗口，超了就只取最后 T 个 */
        BT = len;                                  /* 本次前向的序列长度 */
        for (int t = 0; t < len; t++) { xs[t] = ctx[n - len + t]; ys[t] = 0; }  /* 填入输入，目标不用 */
        forward();                                 /* 跑一次前向拿到 logits */
        float *lg = h_logits + (size_t)(len - 1) * VOCAB;  /* 只关心最后一个位置（要预测的下一个字符） */
        /* top-40 + 稳定 softmax + 温度 0.7：小模型这样吐字才连贯 */
        float kth = -1e30f;                        /* 找第 40 大的 logit 作为阈值 */
        for (int v = 0; v < VOCAB; v++) if (lg[v] > kth) kth = lg[v];  /* 先取最大值 */
        for (int r = 0; r < 39; r++) {             /* 再做 39 轮"找次大"，得到第 40 大 */
            float best = -1e30f;                   /* 本轮最大 */
            for (int v = 0; v < VOCAB; v++) if (lg[v] < kth && lg[v] > best) best = lg[v];  /* 只在比当前阈值小的里找 */
            kth = best;                            /* 更新阈值 */
        }
        float probs[VOCAB], sum = 0.0f, temp = 0.7f;  /* 概率、归一化因子、温度 */
        for (int v = 0; v < VOCAB; v++) {          /* 只保留 top-40，其余概率为 0 */
            if (lg[v] < kth) { probs[v] = 0.0f; continue; }  /* 长尾直接砍掉，避免采样到离谱字符 */
            float e = (lg[v] - kth) / temp;        /* 减去阈值做数值稳定，再除以温度 */
            if (e > 60.0f) e = 60.0f;              /* 防 exp 溢出成 inf */
            probs[v] = expf(e);                    /* 指数化 */
            sum += probs[v];                       /* 累加分母 */
        }
        float r = frand() * sum, acc = 0.0f;       /* 在 [0,sum) 里取一个随机数 */
        int pick = VOCAB - 1;                      /* 兜底选最后一个 */
        for (int v = 0; v < VOCAB; v++) { acc += probs[v]; if (r <= acc) { pick = v; break; } }  /* 轮盘赌采样 */
        ctx[n++] = pick;                           /* 采到的 id 接进上下文 */
        { char ob[8]; int k = id_to_out(pick, ob); fwrite(ob, 1, (size_t)k, stdout); }  /* 立刻打印，形成流式输出 */
        fflush(stdout);                            /* 不缓冲，否则看起来像卡住 */
    }
    printf("\n--- 结束 ---\n");                    /* 生成结束 */
    BT = B * T; B = savedB;                        /* 恢复全局状态，避免影响后续计算 */
}

/* ------------------------------ 梯度检查 --------------------------------
 * float32 下逐元素中心差分会被精度噪声淹没（真梯度 ~1e-4 时噪声 ~5e-4）。
 * 因此主要用“方向导数”检查：把整个参数张量沿随机单位方向 d 移动 ±eps，
 * 比较 (L(p+eps*d)-L(p-eps*d))/(2eps) 与 sum_j g_j*d_j。
 * 信号是整张量的梯度，远大于噪声，能同时覆盖该张量的所有元素。 */
static int gradcheck(void) {
    /* 用数值差分验证手写反向传播是否写对了，这是纯 C 实现最需要的自检 */
    printf("\n=== 梯度检查 ===\n（逐张量方向导数 + 逐元素抽查，float32 精度）\n");
    int savedB = B;                                /* 保存现场 */
    B = 2; BT = B * T;                             /* 用小 batch，数值误差更可控 */
    alloc_activations();                           /* 分配激活缓冲 */
    sample_batch(0);                               /* 取一批训练数据 */
    zero_grads();                                  /* 梯度清零 */
    forward();                                     /* 前向 */
    loss_and_grad();                               /* 算损失与输出层梯度 */
    backward();                                    /* 反向，得到所有解析梯度 */

    /* 步长选择：float32 下 expf/logf 会给 loss 带来 ~1e-6 的绝对误差。
       数值差分 2*eps*|g| 必须远大于它，否则就是纯噪声。
       eps=0.2 时沿单位方向的每元素扰动约 0.2/sqrt(n)≈0.004，曲率误差仍很小。 */
    float eps = 0.2f;                              /* 差分步长 */
    float noise_floor = 1e-4f;      /* 方向导数低于此值即视为噪声不可分辨 */
    float worst_dir = 0.0f;                        /* 记录最差相对误差 */
    int bad = 0;                                   /* 记录超阈值的张量个数 */

    /* 1) 方向导数：每个参数张量一次 */
    printf("\n--- [1] 方向导数（覆盖每个张量的全部元素）---\n");
    for (int pi = 0; pi < nparams; pi++) {         /* 逐个参数张量 */
        Param *q = &params[pi];                    /* 当前张量 */
        float *dir = (float *)malloc((size_t)q->n * sizeof(float));  /* 随机方向向量 */
        double norm = 0.0;                         /* 用于归一化 */
        for (int j = 0; j < q->n; j++) { dir[j] = frand() * 2.0f - 1.0f; norm += (double)dir[j] * dir[j]; }  /* 随机初始化到 [-1,1] */
        norm = sqrt(norm) + 1e-12;                 /* 加 1e-12 防全零向量除零 */
        for (int j = 0; j < q->n; j++) dir[j] = (float)(dir[j] / norm);  /* 归一化成单位向量 */

        double ana = 0.0;                          /* 解析方向导数 */
        for (int j = 0; j < q->n; j++) ana += (double)q->g[j] * dir[j];  /* 梯度与方向的内积 */

        for (int j = 0; j < q->n; j++) q->p[j] += eps * dir[j];   /* 参数沿方向前进 eps */
        forward(); double lp = loss_and_grad();                   /* 算 L(p+eps*d) */
        for (int j = 0; j < q->n; j++) q->p[j] -= 2.0f * eps * dir[j];  /* 反向越过原点 */
        forward(); double lm = loss_and_grad();                   /* 算 L(p-eps*d) */
        for (int j = 0; j < q->n; j++) q->p[j] += eps * dir[j];   /* 恢复原参数 */

        double num = (lp - lm) / (2.0 * eps);      /* 中心差分得到数值方向导数 */
        double denom = fabs(num) + fabs(ana) + 1e-6;  /* 相对误差的分母，加 1e-6 防零 */
        double rel = fabs(num - ana) / denom;      /* 相对误差 */
        int noisy = fabs(ana) < noise_floor;      /* 梯度太小，float32 分辨不了 */
        int ok = rel < 0.08;                       /* 8% 以内算通过，float32 下放宽一些 */
        if (rel > worst_dir && !noisy) worst_dir = rel;  /* 记录最差（忽略噪声项） */
        if (!ok && !noisy) bad++;                  /* 统计失败张量 */
        printf("  %s %-10s 数值=%+.6e 解析=%+.6e 相对误差=%.2e %s\n",  /* 打印对比 */
               ok ? "✔" : (noisy ? "~" : "✘"), q->name, num, ana, rel,  /* 状态、名字、两个值、误差 */
               noisy ? "(信号低于噪声门限，跳过)" : "");  /* 噪声项的说明 */
        free(dir);                                 /* 释放方向向量 */
    }

    /* 2) 逐元素抽查：只覆盖梯度足够大的元素（小梯度在 float32 下必然被噪声主导） */
    printf("\n--- [2] 逐元素抽查（只比较 |梯度| > 1e-3 的位置）---\n");
    zero_grads(); forward(); loss_and_grad(); backward();  /* 重新算一次干净梯度（前面的扰动已还原，但保险起见） */
    float worst_el = 0.0f;                         /* 最差逐元素误差 */
    int checked = 0, skipped = 0;                  /* 统计：已检查 / 因太小跳过 */
    for (int pi = 0; pi < nparams; pi++) {         /* 逐张量 */
        Param *q = &params[pi];                    /* 当前张量 */
        for (int k = 0; k < 2; k++) {              /* 每个张量抽查 2 个元素，控制总耗时 */
            int idx = (int)(xrand() % (unsigned)q->n);  /* 随机下标 */
            float ana = q->g[idx];                 /* 解析梯度 */
            if (fabsf(ana) < 1e-3f) { skipped++; continue; }  /* 太小会被噪声淹没，跳过 */
            float orig = q->p[idx];                /* 记住原值 */
            q->p[idx] = orig + eps; forward(); float lp = loss_and_grad();  /* 加 eps 后的损失 */
            q->p[idx] = orig - eps; forward(); float lm = loss_and_grad();  /* 减 eps 后的损失 */
            q->p[idx] = orig;                      /* 还原 */
            float num = (lp - lm) / (2 * eps);     /* 中心差分 */
            float rel = fabsf(num - ana) / (fabsf(num) + fabsf(ana) + 1e-6f);  /* 相对误差 */
            if (rel > worst_el) worst_el = rel;    /* 更新最差 */
            if (rel > 0.05f) {                     /* 超过 5% 认为是错误 */
                bad++;                             /* 计数 */
                printf("  ✘ %-10s idx=%6d 数值=%+.6e 解析=%+.6e 相对误差=%.2e\n",  /* 打印细节便于定位 */
                       q->name, idx, num, ana, rel);
            }
            checked++;                             /* 计数 */
        }
    }
    printf("  比较 %d 处（%d 处因梯度太小跳过），最大相对误差 %.3e\n", checked, skipped, worst_el);  /* 汇总 */
    printf("\n方向导数最大相对误差 %.3e → %s\n", worst_dir,  /* 总判定 */
           worst_dir < 0.05 ? "反向传播正确 ✔" : "反向传播有误 ✘");
    B = savedB; BT = B * T;                        /* 恢复现场 */
    return bad ? 1 : 0;                            /* 返回非 0 表示有错，主程序据此设置退出码 */
}

/* ------------------------------ 训练 ------------------------------------ */
static void train(int steps) {
    /* 主训练循环：采样 → 前向 → 损失 → 反向 → AdamW 更新 */
    printf("\n=== 训练 %d 步 ===\n", steps);
    printf("配置: %d 层 | 宽度 %d | %d 头 | 上下文 %d | batch %d | 每步 %d token\n\n",
           NLAYER, NEMBD, NHEAD, T, B, B * T);     /* 打印配置，便于复现实验 */
    clock_t t0 = clock();                          /* 计时起点 */
    float best_val = 1e9f;                         /* 记录最好的验证损失 */
    int warm = steps / 10 + 1;                     /* 预热步数：总步数的 10%，至少 1 步 */
    for (int step = 1; step <= steps; step++) {    /* 逐步训练 */
        float lr;                                  /* 本步学习率 */
        if (step <= warm) lr = 3e-3f * step / (float)warm;  /* 预热：从 0 线性升到 3e-3，避免一开始就大步长炸掉 */
        else {                                     /* 预热之后 */
            float prog = (float)(step - warm) / (float)(steps - warm);  /* 剩余进度 0→1 */
            lr = 3e-3f * 0.5f * (1.0f + cosf(3.14159265f * prog));  /* 余弦退火：平滑降到 0 */
        }
        sample_batch(0);                           /* 取一批训练数据 */
        forward();                                 /* 前向 */
        float loss = loss_and_grad();              /* 算损失 */
        zero_grads();                              /* 梯度清零（必须在 backward 之前） */
        backward();                                /* 反向传播，梯度累加到各参数 */
        adamw_step(lr, step);                      /* 更新参数 */

        if (step == 1 || step % 50 == 0) {         /* 定期打印进度 */
            double secs = (double)(clock() - t0) / CLOCKS_PER_SEC;  /* 已耗时 */
            printf("step %5d/%d | 训练 loss %.4f | lr %.2e | %6.1fs | %.0f ms/step\n",  /* 一行概览 */
                   step, steps, loss, lr, secs, secs * 1000.0 / step);  /* 参数与速率 */
            fflush(stdout);                        /* 立即刷出，方便边训边看 */
        }
        if (step % 500 == 0) {                     /* 每 500 步验证一次 */
            float vl = eval_loss(10);              /* 用 10 批估验证损失 */
            printf("             验证 loss %.4f%s\n", vl, vl < best_val ? "  (新低)" : "");  /* 提示是否改善 */
            if (vl < best_val) best_val = vl;      /* 更新最好记录 */
        }
    }
    printf("\n训练完成，用时 %.1f 秒，最终验证 loss %.4f\n",  /* 收尾报告 */
           (double)clock() / CLOCKS_PER_SEC, eval_loss(20));  /* 用 20 批做更稳的估计 */
}


/* ------------------------------ 权重存取 --------------------------------
 * 自描述二进制格式，便于断点续训：
 *   magic "NANOGPT1" | 6×int32 (版本, NLAYER, NEMBD, NHEAD, MLP, T)
 *   VOCAB 字节字符表 | int32 张量个数
 *   每个张量: char name[32] | int32 n | float p[n] | float m[n] | float v[n]
 * 一并保存 AdamW 一阶/二阶动量，加载后可以无缝继续训练。 */
static const char SAVE_MAGIC[8] = {'N','A','N','O','G','P','T','1'};

static int save_weights(const char *path) {
    /* 把词表、超参、所有张量的 p/m/v 一起写盘 */
    FILE *f = fopen(path, "wb");                   /* 二进制写，避免换行转换破坏数据 */
    if (!f) { fprintf(stderr, "无法写入: %s\n", path); return -1; }
    int32_t hdr[6] = {1, NLAYER, NEMBD, NHEAD, MLP, T};  /* 版本号 + 五个架构参数 */
    long bytes = 0;                                /* 统计写出的字节数 */
    bytes += (long)fwrite(SAVE_MAGIC, 1, 8, f);    /* 魔数，加载时用于识别文件类型 */
    bytes += (long)fwrite(hdr, sizeof(int32_t), 6, f);  /* 架构头，加载时校验 */
#ifdef CHARLEVEL
    bytes += (long)fwrite(vocab_cp, sizeof(int), VOCAB, f);  /* 字符级：存码点表 */
#else
    bytes += (long)fwrite(vocab, 1, VOCAB, f);     /* 字节级：存字节表 */
#endif
    int32_t np = nparams;                          /* 张量个数 */
    bytes += (long)fwrite(&np, sizeof(int32_t), 1, f);
    for (int i = 0; i < nparams; i++) {            /* 逐个张量写 */
        char name[32];                             /* 定长名字，便于二进制读写 */
        memset(name, 0, sizeof name);              /* 先清零，保证尾部是 0 不是脏数据 */
        strncpy(name, params[i].name, 31);         /* 最多 31 字节，留一位给结尾 0 */
        int32_t n = params[i].n;                   /* 元素数 */
        bytes += (long)fwrite(name, 1, 32, f);     /* 名字 */
        bytes += (long)fwrite(&n, sizeof(int32_t), 1, f);  /* 长度 */
        bytes += (long)fwrite(params[i].p, sizeof(float), n, f);  /* 权重 */
        bytes += (long)fwrite(params[i].m, sizeof(float), n, f);  /* 一阶动量 */
        bytes += (long)fwrite(params[i].v, sizeof(float), n, f);  /* 二阶动量 */
    }
    fclose(f);                                     /* 关闭并刷盘 */
    printf("权重已保存: %s (%.2f MB，含 AdamW 动量)\n", path, bytes / 1e6);  /* 报告大小 */
    return 0;                                      /* 成功 */
}

static int load_weights(const char *path) {
    /* 读取权重并做三重校验：魔数、架构、张量名，任何一项不符都拒绝加载 */
    FILE *f = fopen(path, "rb");                   /* 二进制读 */
    if (!f) { fprintf(stderr, "无法读取权重: %s\n", path); return -1; }
    char magic[8]; int32_t hdr[6];                 /* 魔数与架构头 */
    if (fread(magic, 1, 8, f) != 8 || memcmp(magic, SAVE_MAGIC, 8) != 0) {  /* 校验魔数 */
        fprintf(stderr, "不是本程序保存的权重文件: %s\n", path);
        fclose(f); return -1;                      /* 及时关文件再返回 */
    }
    if (fread(hdr, sizeof(int32_t), 6, f) != 6) { fclose(f); return -1; }  /* 读架构头 */
    if (hdr[1] != NLAYER || hdr[2] != NEMBD || hdr[3] != NHEAD ||  /* 逐项比对 */
        hdr[4] != MLP || hdr[5] != T) {
        fprintf(stderr, "架构不匹配：文件是 %d层/%d宽/%d头/MLP%d/上下文%d，"  /* 说明文件里的配置 */
                        "本程序是 %d/%d/%d/%d/%d\n",
                hdr[1], hdr[2], hdr[3], hdr[4], hdr[5],
                NLAYER, NEMBD, NHEAD, MLP, T);     /* 说明当前程序的配置 */
        fclose(f); return -1;                      /* 不匹配就不加载，避免读到错位数据 */
    }
#ifdef CHARLEVEL
    if (fread(vocab_cp, sizeof(int), VOCAB, f) != VOCAB) { fclose(f); return -1; }  /* 读码点表 */
    cmap_init();                                   /* 重建哈希表 */
    for (int k = 0; k < VOCAB; k++) cmap_put(vocab_cp[k], k);  /* 码点 → id */
#else
    if (fread(vocab, 1, VOCAB, f) != VOCAB) { fclose(f); return -1; }  /* 读字节表 */
    for (int b = 0; b < 256; b++) byte2id[b] = 0;  /* 默认映射 */
    for (int k = 0; k < VOCAB; k++) byte2id[vocab[k]] = k;  /* 字节 → id */
#endif

    int32_t np = 0;                                /* 张量个数 */
    if (fread(&np, sizeof(int32_t), 1, f) != 1 || np != nparams) {  /* 个数必须一致 */
        fprintf(stderr, "参数张量个数不匹配（文件 %d，程序 %d）\n", np, nparams);
        fclose(f); return -1;
    }
    for (int i = 0; i < nparams; i++) {            /* 逐个张量读 */
        char name[32]; int32_t n = 0;              /* 名字与长度 */
        if (fread(name, 1, 32, f) != 32) { fclose(f); return -1; }
        if (fread(&n, sizeof(int32_t), 1, f) != 1 ||  /* 读长度 */
            n != params[i].n || strncmp(name, params[i].name, 31) != 0) {  /* 长度与名字都要对上，防止顺序错位 */
            fprintf(stderr, "张量 %d 不匹配（文件 %s / 程序 %s）\n", i, name, params[i].name);
            fclose(f); return -1;
        }
        if (fread(params[i].p, sizeof(float), n, f) != (size_t)n) { fclose(f); return -1; }  /* 权重 */
        if (fread(params[i].m, sizeof(float), n, f) != (size_t)n) { fclose(f); return -1; }  /* 一阶动量 */
        if (fread(params[i].v, sizeof(float), n, f) != (size_t)n) { fclose(f); return -1; }  /* 二阶动量 */
    }
    fclose(f);                                     /* 读取完成 */
    printf("已加载权重: %s\n", path);              /* 成功日志 */
    return 0;                                      /* 成功 */
}

/* ------------------------------ 对话模式 -------------------------------- */
/* ====================== 对话模式（新增注释版） ====================== */
static int ctx_append(int *ctx, int n, const char *s) {
    /* 往上下文追加一段文本，返回新的长度；留 2 个槽位给结尾 */
    return n + str_to_ids(s, ctx + n, 8190 - n);   /* 最多写到 8190，防止越界 */
}

/* 从 ctx 继续采样，边生成边打印；遇到停止串就停下并把它从 ctx 里去掉。
   返回新增字符数。 */
static int chat_generate(int *ctx, int *n, int maxchars, const char *stop) {
    int savedB = B;                                /* 保存 batch 大小，生成完要还原 */
    int stop_ids[16];                              /* 停止串的 id 序列 */
    int stoplen = str_to_ids(stop, stop_ids, 16);  /* 停止串也变成 id 序列比较 */
    int start = *n;                                /* 记录起始长度，用于算新增字符数 */
    B = 1;                                         /* 生成只用一条序列 */
    for (int s = 0; s < maxchars; s++) {           /* 最多生成 maxchars 个字符 */
        int len = *n < T ? *n : T;                 /* 上下文窗口上限，超了只取最近 T 个 */
        BT = len;                                  /* 本次前向长度 */
        for (int t = 0; t < len; t++) { xs[t] = ctx[*n - len + t]; ys[t] = 0; }  /* 填输入，生成时不用目标 */
        forward();                                 /* 前向 */
        float *lg = h_logits + (size_t)(len - 1) * VOCAB;  /* 最后一个位置的 logits 决定下一个字符 */
        float temp = 0.85f, sum = 0.0f, probs[VOCAB];  /* 温度略高，对话更自然 */
        /* top-k=20：把其余 logits 压成 0，避免反复吐同一句套话 */
        float kth = -1e30f;                        /* 阈值初值 */
        for (int v = 0; v < VOCAB; v++) if (lg[v] > kth) kth = lg[v];  /* 先取最大值 */
        for (int r = 0; r < 19; r++) {              /* 迭代 19 次得到第 20 大的值 */
            float best = -1e30f;                   /* 本轮最大 */
            for (int v = 0; v < VOCAB; v++) if (lg[v] < kth && lg[v] > best) best = lg[v];  /* 只在比阈值小的里找 */
            kth = best;                            /* 更新阈值 */
        }
        for (int v = 0; v < VOCAB; v++) {          /* 计算截断后的概率 */
            if (lg[v] < kth) { probs[v] = 0.0f; continue; }  /* 长尾砍掉 */
            probs[v] = expf((lg[v] - kth) / temp);  /* 减去阈值做数值稳定，再除温度 */
            sum += probs[v];                       /* 累加分母 */
        }
        float r = frand() * sum, acc = 0.0f;       /* 轮盘赌的随机落点 */
        int pick = VOCAB - 1;                      /* 兜底选最后一个 */
        for (int v = 0; v < VOCAB; v++) { acc += probs[v]; if (r <= acc) { pick = v; break; } }  /* 采样 */
        if (*n >= 8190) break;                     /* 上下文满了就停 */
        ctx[(*n)++] = pick;                        /* 接进上下文 */
        { char ob[8]; int k = id_to_out(pick, ob); fwrite(ob, 1, (size_t)k, stdout); }  /* 立即打印 */
        fflush(stdout);                            /* 刷出，形成打字机效果 */
        if (*n - start >= stoplen) {                 /* 命中停止串？ */
            int match = 1;                         /* 假定匹配 */
            for (int k = 0; k < stoplen; k++)      /* 逐字符比对尾部 */
                if (ctx[*n - stoplen + k] != stop_ids[k]) { match = 0; break; }  /* 有一个不符就不匹配 */
            if (match) { *n -= stoplen; break; }   /* 去掉停止串本身，不留在上下文里 */
        }
    }
    B = savedB; BT = B * T;                        /* 恢复现场，避免影响后续计算 */
    return *n - start;                             /* 返回新增字符数 */
}

/* chat_mode：不传 question 就是交互式；传了就是问一句答一句然后退出 */
static void chat_mode(const char *once) {
    static int ctx[8192];                          /* 对话上下文 */
    static char line[2048];                        /* 用户输入缓冲 */
    int n = 0;                                     /* 当前上下文长度 */
    printf("\n================ C 版迷你对话模型 ================\n");
    printf("直接输入问题回车；quit 退出；clear 重开对话。\n");
    printf("（0.8M 参数、纯 C 训练，回答会很幼稚，请见谅）\n");  /* 先打预防针，避免期待过高 */
    printf("==================================================\n");
    for (;;) {                                     /* 交互循环 */
        if (once) {                                /* 一次性模式：把参数当问题 */
            strncpy(line, once, sizeof line - 1);  /* 复制问题 */
            line[sizeof line - 1] = 0;             /* 保证结尾有 0 */
        } else {                                   /* 交互模式 */
            printf("\n你: "); fflush(stdout);      /* 提示符立即显示 */
            if (!fgets(line, sizeof line, stdin)) { printf("\n再见！\n"); break; }  /* EOF 退出 */
            line[strcspn(line, "\r\n")] = 0;       /* 去掉行尾换行 */
            if (!strcmp(line, "quit") || !strcmp(line, "exit")) { printf("再见！\n"); break; }  /* 退出命令 */
            if (!strcmp(line, "clear")) { n = 0; printf("[对话已清空]\n"); continue; }  /* 清空上下文 */
            if (!line[0]) continue;                /* 空行忽略 */
        }
        n = ctx_append(ctx, n, "### User: ");      /* 按训练语料的固定格式拼接 */
        n = ctx_append(ctx, n, line);              /* 用户问题 */
        n = ctx_append(ctx, n, "\n### Assistant:");  /* 提示模型该它说了 */
        if (n > 6000) {                              /* 太长了就只留最近一段 */
            int keep = 3000;                       /* 保留最近 3000 个 token */
            memmove(ctx, ctx + (n - keep), (size_t)keep * sizeof(int));  /* 前移覆盖旧内容 */
            n = keep;                              /* 更新长度 */
        }
        printf("AI:");                             /* 提示符 */
        chat_generate(ctx, &n, 300, "\n###");      /* 生成回答，遇到下一个 ### 就停 */
        printf("\n");                              /* 换行 */
        n = ctx_append(ctx, n, "\n");              /* 回答后补一个换行，为下一轮做准备 */
        if (once) break;                           /* 一次性模式只答一次 */
    }
}

/* ------------------------------ 解题模式 -------------------------------- */
static void ask_mode(const char *question) {
    /* 用「题目 → 解答」的固定格式让模型续写解答 */
    static int ctx[8192];                          /* 上下文 */
    int n = 0;                                     /* 长度 */
    n = ctx_append(ctx, n, "### Problem: ");       /* 题目标记 */
    n = ctx_append(ctx, n, question);              /* 题目内容 */
    n = ctx_append(ctx, n, "\n### Solution:");     /* 解答标记，模型从这里开始续写 */
    printf("### Problem: %s\n### Solution:", question);  /* 回显题面 */
    chat_generate(ctx, &n, 500, "\n###");          /* 生成解答，遇到下一个 ### 停 */
    printf("\n");                                  /* 收尾换行 */
}

/* ====================== 命令行中文编码（GBK -> UTF-8）=================== */
static int looks_utf8(const char *s) {
    /* 检查字符串是否已经是合法 UTF-8：Windows 控制台默认 GBK，需要转换 */
    for (const unsigned char *p = (const unsigned char *)s; *p; ) {  /* 逐字节扫描 */
        if (*p < 0x80) { p++; continue; }          /* ASCII 直接跳过 */
        int n = (*p >= 0xF0) ? 4 : (*p >= 0xE0) ? 3 : (*p >= 0xC0) ? 2 : 0;  /* 按首字节判断长度 */
        if (!n) return 0;                          /* 非法首字节 */
        for (int i = 1; i < n; i++) if ((p[i] & 0xC0) != 0x80) return 0;  /* 后续字节必须是 10xxxxxx */
        p += n;                                    /* 跳到下一个字符 */
    }
    return 1;                                      /* 全部合法 */
}
static char *to_utf8(const char *s) {
    /* 把可能是 GBK 的命令行参数转成 UTF-8；非 Windows 直接复制 */
#ifdef _WIN32
    if (!looks_utf8(s)) {                          /* 不是 UTF-8 才转换 */
        int wlen = MultiByteToWideChar(CP_ACP, 0, s, -1, NULL, 0);  /* 先算宽字符所需长度 */
        if (wlen > 0) {
            wchar_t *w = (wchar_t *)malloc(sizeof(wchar_t) * (size_t)wlen);  /* 分配宽字符缓冲 */
            MultiByteToWideChar(CP_ACP, 0, s, -1, w, wlen);  /* GBK → UTF-16 */
            int ulen = WideCharToMultiByte(CP_UTF8, 0, w, -1, NULL, 0, NULL, NULL);  /* 算 UTF-8 所需长度 */
            char *u = (char *)malloc((size_t)ulen);  /* 分配结果缓冲 */
            WideCharToMultiByte(CP_UTF8, 0, w, -1, u, ulen, NULL, NULL);  /* UTF-16 → UTF-8 */
            free(w);                               /* 释放中间缓冲 */
            return u;                              /* 返回转换结果（调用方负责释放） */
        }
    }
#endif
    char *u = (char *)malloc(strlen(s) + 1);       /* 已是 UTF-8：直接复制 */
    strcpy(u, s);                                  /* 拷贝内容 */
    return u;                                      /* 返回副本，保持统一的释放语义 */
}

/* ====================== 算术考试（用精确计算器判分）===================== */
static int gen_text(const char *prompt, char *out, int maxch, float temp);  /* 前向声明 */

static void arith_eval(const char *testfile) {
    /* 跑算术测试集，统计准确率；判分用精确整数比较，不受模型随机性影响 */
    FILE *f = fopen(testfile, "r");                /* 打开测试文件 */
    if (!f) { printf("打不开测试集: %s\n", testfile); return; }  /* 打不开就提示并返回 */
    char line[256];                                /* 行缓冲 */
    int total = 0, ok = 0;                         /* 总题数与答对数 */
    int ct[3] = {0, 0, 0}, co[3] = {0, 0, 0};      /* 0 一位数 1 两位数 2 乘法 */
    static char out[64];                           /* 模型输出缓冲 */
    while (fgets(line, sizeof line, f)) {          /* 逐行读题 */
        int a, b, expect;                          /* 两个操作数与期望答案 */
        char op;                                   /* 运算符 */
        if (sscanf(line, "%d%c%d\t%d", &a, &op, &b, &expect) != 4) continue;  /* 格式不符就跳过 */
        char prompt[160];                          /* 给模型的提示 */
        snprintf(prompt, sizeof prompt, "%d%c%d=", a, op, b);  /* 例如 "3+5=" */
        gen_text(prompt, out, 12, 0.01f);          /* 接近贪婪解码，减少随机性 */
        int got = (int)strtol(out, NULL, 10);      /* 把输出前导数字转成整数 */
        int cat = (op == '*') ? 2 : ((a > 9 || b > 9) ? 1 : 0);  /* 归类：乘法 / 两位数 / 一位数 */
        total++; ct[cat]++;                        /* 计数 */
        if (got == expect) { ok++; co[cat]++; }    /* 答对则累加 */
        if (total <= 6) {                       /* 前几题打印出来看模型到底输出了什么 */
            char shown[32];                        /* 截断展示，避免刷屏 */
            size_t k = 0;                          /* 已复制长度 */
            while (out[k] && out[k] != '\n' && k < sizeof shown - 1) { shown[k] = out[k]; k++; }  /* 只取第一行 */
            shown[k] = 0;                          /* 结尾补 0 */
            printf("  例 %d%c%d：期望 %d，模型 \"%s\" %s\n",  /* 展示对错 */
                   a, op, b, expect, shown, got == expect ? "✔" : "✘");
        }
    }
    fclose(f);                                     /* 关闭文件 */
    printf("\n===== 算术准确率（共 %d 题，判分用精确计算器）=====\n", total);
    const char *names[3] = {"一位数加减", "两位数加减", "乘法表  "};  /* 分类名 */
    for (int i = 0; i < 3; i++)                    /* 逐类报告 */
        printf("  %s : %4d/%-4d = %5.1f%%\n", names[i], co[i], ct[i],  /* 对/总 */
               ct[i] ? 100.0 * co[i] / ct[i] : 0.0);  /* 三目防止除零 */
    printf("  ------------------------------ \n");
    printf("  总计        : %4d/%-4d = %5.1f%%\n", ok, total, total ? 100.0 * ok / total : 0.0);  /* 汇总 */
}

/* ====================== 精确算术（独立于模型的验算器）====================
 * 递归下降解析，算出来的结果是精确的 double，
 * 用来判断模型给的数值对不对——模型可以乱说，计算器不会。
 * 优先级（低到高）：expr(+ -) → term(* /) → pow(^ %) → prim(数字/括号/负号) */
static const char *EP;                             /* 全局游标，指向当前解析位置 */
static double e_expr(void);                        /* 前向声明，供括号递归调用 */

static void e_skip(void) {
    /* 跳过空白字符，让后面判断符号时不用关心空格 */
    while (*EP == ' ' || *EP == '\t') EP++;        /* 空格和制表符都跳过 */
}

static double e_prim(void) {
    /* 最底层：括号、正负号、数字字面量 */
    e_skip();                                      /* 先跳过空白 */
    if (*EP == '(') { EP++; double v = e_expr(); e_skip(); if (*EP == ')') EP++; return v; }  /* 括号里递归回顶层 */
    if (*EP == '-') { EP++; return -e_prim(); }    /* 一元负号 */
    if (*EP == '+') { EP++; return e_prim(); }     /* 一元正号，直接忽略 */
    char *end; double v = strtod(EP, &end);        /* 解析数字，end 指向数字之后 */
    if (end == EP) return NAN;                     /* 一个字符都没吃掉，说明不是数字 */
    EP = end; return v;                            /* 前进游标并返回数值 */
}

static double e_pow(void) {
    /* 幂运算，右结合：2^3^2 = 2^(3^2) */
    double b = e_prim();                           /* 底数 */
    for (;;) {                                     /* 循环处理连续的 ^ 与 % */
        e_skip();                                  /* 跳过空白 */
        if (*EP == '^') { EP++; b = pow(b, e_pow()); }  /* 右结合靠递归实现 */
        else if (*EP == '%') { EP++; b = b / 100.0; }   /* 百分号是后缀：80% = 0.8 */
        else break;                                /* 没有更多运算符 */
    }
    return b;                                      /* 返回结果 */
}

static double e_term(void) {
    /* 乘除，左结合 */
    double v = e_pow();                            /* 第一个操作数 */
    for (;;) {                                     /* 循环处理 * 和 / */
        e_skip();                                  /* 跳过空白 */
        if (*EP == '*') { EP++; v *= e_pow(); }    /* 乘法 */
        else if (*EP == '/') { EP++; double r = e_pow(); v = (r == 0) ? NAN : v / r; }  /* 除零返回 NaN 而不是崩溃 */
        else break;                                /* 结束 */
    }
    return v;                                      /* 返回结果 */
}

static double e_expr(void) {
    /* 加减，优先级最低，是入口 */
    double v = e_term();                           /* 第一个项 */
    for (;;) {                                     /* 循环处理 + 和 - */
        e_skip();                                  /* 跳过空白 */
        if (*EP == '+') { EP++; v += e_term(); }   /* 加法 */
        else if (*EP == '-') { EP++; v -= e_term(); }  /* 减法 */
        else break;                                /* 结束 */
    }
    return v;                                      /* 返回结果 */
}

static double eval_expr(const char *s) {
    /* 对外接口：把游标重置到字符串开头，然后开始解析 */
    EP = s;                                        /* 重置全局游标 */
    return e_expr();                               /* 从最低优先级开始 */
}

/* ====================== 生成到缓冲区（不打印）=========================== */
static int gen_text(const char *prompt, char *out, int maxch, float temp) {
    /* 与 generate() 类似，但结果写进缓冲区而不是打印，供程序内部调用 */
    static int ctx[8192];                          /* 上下文 */
    int n = str_to_ids(prompt, ctx, 8000);         /* 提示词编码 */
    int savedB = B, m = 0;                         /* 保存 batch；m 是已写字节数 */
    B = 1;                                         /* 单序列生成 */
    for (int s = 0; s < maxch; s++) {              /* 最多生成 maxch 个字符 */
        int len = n < T ? n : T;                   /* 上下文窗口 */
        BT = len;                                  /* 本次前向长度 */
        for (int t = 0; t < len; t++) { xs[t] = ctx[n - len + t]; ys[t] = 0; }  /* 填输入 */
        forward();                                 /* 前向 */
        float *lg = h_logits + (size_t)(len - 1) * VOCAB;  /* 最后一个位置的分布 */
        float kth = -1e30f;                     /* top-30 采样 */
        for (int v = 0; v < VOCAB; v++) if (lg[v] > kth) kth = lg[v];  /* 取最大 */
        for (int r = 0; r < 29; r++) {             /* 找第 30 大 */
            float best = -1e30f;                   /* 本轮最大 */
            for (int v = 0; v < VOCAB; v++) if (lg[v] < kth && lg[v] > best) best = lg[v];  /* 找次大 */
            kth = best;                            /* 更新 */
        }
        float probs[VOCAB], sum = 0.0f;            /* 概率与归一化因子 */
        float mxl = -1e30f;                     /* 用最大 logit 做稳定归一化 */
        for (int v = 0; v < VOCAB; v++) if (lg[v] > mxl) mxl = lg[v];  /* 取全局最大 */
        for (int v = 0; v < VOCAB; v++) {          /* 计算概率 */
            if (lg[v] < kth) { probs[v] = 0.0f; continue; }  /* top-30 之外砍掉 */
            float e = (lg[v] - mxl) / temp;        /* 减去最大再除温度 */
            if (e > 60.0f) e = 60.0f;           /* 防 exp 溢出（temp 很小时尤其重要） */
            probs[v] = expf(e); sum += probs[v];   /* 指数化并累加 */
        }
        float r = frand() * sum, acc = 0.0f;       /* 随机落点 */
        int pick = VOCAB - 1;                      /* 兜底 */
        for (int v = 0; v < VOCAB; v++) { acc += probs[v]; if (r <= acc) { pick = v; break; } }  /* 采样 */
        ctx[n++] = pick;                           /* 接进上下文 */
        if (m + 8 < maxch) {                       /* 留足空间再写，防越界 */
            int k = id_to_out(pick, out + m);      /* 写进输出缓冲 */
            m += k;                                /* 前进 */
        }
        if (m >= 4 && out[m-1] == '#' && out[m-2] == '#' && out[m-3] == '#') break;  /* 遇到 ### 标记就停 */
    }
    out[m] = 0;                                    /* 补字符串结尾 */
    B = savedB; BT = B * T;                        /* 恢复现场 */
    return m;                                      /* 返回写入的字节数 */
}

/* ====================== 逐步验算 + 投票 ================================ */
typedef struct {
    char   steps[1024];      /* 模型输出的推理步骤原文 */
    char   answer[64];       /* 模型声称的答案 */
    int    n_step, n_ok;     /* 总步骤数 / 通过验算的步骤数 */
    double last_ok;          /* 最后一个通过验算的步骤的值，作为最终答案 */
    int    has_answer;       /* 是否所有步骤都通过（1 表示可信） */
} Chain;

static void verify_chain(const char *gen, Chain *c) {
    /* 把模型生成的分步推理拆开，每一步用精确计算器复核，全部对才算可信 */
    memset(c, 0, sizeof *c);                       /* 清零，避免残留上一次的状态 */
    c->last_ok = NAN;                              /* NaN 表示还没有可用值 */
    const char *th = strstr(gen, "### 思考:");     /* 找思考段的起点 */
    if (!th) th = gen; else th += strlen("### 思考:");  /* 没有标记就从头算 */
    const char *ans = strstr(th, "### 答案:");     /* 找答案段的起点 */
    size_t thlen = ans ? (size_t)(ans - th) : strlen(th);  /* 思考段的长度 */
    if (thlen >= sizeof c->steps) thlen = sizeof c->steps - 1;  /* 截断到缓冲区大小 */
    memcpy(c->steps, th, thlen);                   /* 复制思考段 */
    c->steps[thlen] = 0;                           /* 手动补结尾 0 */
    if (ans) {                                     /* 有答案段就解析 */
        ans += strlen("### 答案:");                /* 跳过标记 */
        while (*ans == ' ') ans++;                 /* 跳过前导空格 */
        size_t k = 0;                              /* 已复制长度 */
        while (ans[k] && ans[k] != '\n' && ans[k] != '#' && k < sizeof c->answer - 1) {  /* 读到换行或下一个标记 */
            c->answer[k] = ans[k]; k++;
        }
        c->answer[k] = 0;                          /* 结尾 */
    }
    /* 按 ';' 切分步骤，逐步用精确计算器验算（不用 strtok_r，避免平台差异） */
    const char *p = c->steps;                      /* 游标 */
    char tok[512];                                 /* 单步缓冲 */
    while (*p) {                                   /* 逐段处理 */
        const char *semi = strchr(p, ';');         /* 找分号 */
        size_t len = semi ? (size_t)(semi - p) : strlen(p);  /* 本段长度 */
        if (len >= sizeof tok) len = sizeof tok - 1;  /* 截断 */
        memcpy(tok, p, len); tok[len] = 0;         /* 复制到缓冲 */
        p = semi ? semi + 1 : p + strlen(p);       /* 前进到下一段 */
        char *t = tok;                             /* 段首 */
        while (*t == ' ') t++;                     /* 跳过空格 */
        char *eq = strrchr(t, '=');                /* 找最后一个等号，形如 "1+2=3" */
        if (!eq) continue;                         /* 没有等号说明不是一步算式 */
        *eq = 0;                                   /* 等号左边是表达式 */
        char *valstr = eq + 1;                     /* 右边是模型声称的值 */
        while (*valstr == ' ') valstr++;           /* 跳过空格 */
        double claimed = atof(valstr);             /* 模型算出的值 */
        double got = eval_expr(t);                 /* 用精确计算器重新算 */
        c->n_step++;                               /* 步骤计数 */
        if (!isnan(got) && fabs(got - claimed) <= 1e-4 * fmax(1.0, fabs(claimed))) {  /* 相对误差 1e-4 内算对 */
            c->n_ok++;                             /* 通过 */
            c->last_ok = got;                      /* 记住这个可信值 */
        }
    }
    c->has_answer = (c->n_step > 0 && c->n_ok == c->n_step);  /* 全部步骤通过才可信 */
}

static void think_mode(const char *problem, int n_samples) {
    /* 采样多条推理链，逐条验算，挑出最好的那条 */
    char prompt[1024], gen[2048];                  /* 提示词与生成缓冲 */
    snprintf(prompt, sizeof prompt, "### 题目: %s\n### 思考:", problem);  /* 按训练格式拼提示 */
    Chain best, cur;                               /* 最好的链与当前链 */
    memset(&best, 0, sizeof best);                 /* 清零 */
    best.n_ok = -1;                                /* 用 -1 表示还没有候选 */
    printf("\n【题目】%s\n", problem);
    printf("【模型】我们自己用 C 训练的 nanogpt（%d 层 / 宽度 %d）\n\n", NLAYER, NEMBD);
    for (int k = 0; k < n_samples; k++) {          /* 采样 n_samples 次 */
        gen_text(prompt, gen, 260, 0.75f);         /* 生成一条推理链 */
        verify_chain(gen, &cur);                   /* 逐步验算 */
        printf("【思路 %d】%.*s\n", k + 1, (int)strcspn(cur.steps, "\n"), cur.steps);  /* 只打印第一行，避免刷屏 */
        printf("         验算 %d/%d 步通过", cur.n_ok, cur.n_step);  /* 通过率 */
        if (cur.has_answer) printf("  → 推出 %.10g\n", cur.last_ok);  /* 全通过，给出结果 */
        else printf("  → 有步骤不成立，不可信\n");  /* 有错，明确说明不可信 */
        if (cur.n_ok > best.n_ok) { best = cur; }  /* 保留通过步数最多的一条 */
    }
    printf("\n【选定】思路 %d（%d/%d 步通过验算）\n", best.n_ok + 1, best.n_ok, best.n_step);  /* 报告选择 */
    if (best.has_answer) {                         /* 最好的那条全通过 */
        printf("【答案】%.10g\n", best.last_ok);   /* 输出答案 */
        printf("【依据】答案由 C 写的精确计算器从最后一步算出，不是模型猜的数字。\n");  /* 强调可信来源 */
    } else {                                       /* 没有任何一条全通过 */
        printf("【答案】给不出可信答案：所有思路都过不了验算。\n");  /* 诚实说明 */
        printf("【说明】这超出 0.89M 参数模型的能力了。要么用 solver.exe 的规则题型，要么换更大的模型。\n");  /* 给出下一步建议 */
    }
}

/* ------------------------------ 入口 ------------------------------------ */
int main(int argc, char **argv) {
    /* 按第一个参数分派到不同子命令 */
#ifdef _WIN32
    SetConsoleOutputCP(65001);       /* 控制台按 UTF-8 输出，中文不乱码 */
#endif
    const char *mode = argc > 1 ? argv[1] : "train";   /* 默认训练 */
    const char *path = argc > 2 ? argv[2] : "corpus.txt";  /* 默认语料 */

    if (load_corpus(path) != 0) return 1;          /* 语料是必需的，失败就退出 */
    BT = B * T;                                    /* 计算总行数 */
    init_params();                                 /* 注册并初始化参数 */

    if (strcmp(mode, "check") == 0) return gradcheck();  /* 梯度检查不需要激活缓冲，提前返回 */

    alloc_activations();                           /* 其余模式都要分配激活缓冲 */

    if (strcmp(mode, "ask") == 0) {
        /* ask <corpus> <weights.bin> "题目" */
        const char *wpath = argc > 3 ? argv[3] : NULL;  /* 权重路径 */
        if (!wpath || argc < 5) {                  /* 参数不足 */
            fprintf(stderr, "用法: nanogpt ask <corpus.txt> <权重.bin> \"题目\"\n");
            return 1;                              /* 返回非 0 表示用法错误 */
        }
        if (load_weights(wpath) != 0) return 1;    /* 加载权重失败就退出 */
        ask_mode(argv[4]);                         /* 进入解题模式 */
        return 0;                                  /* 成功 */
    }

    if (strcmp(mode, "arith_eval") == 0) {
        /* arith_eval <corpus> <weights.bin> <testfile> */
        if (argc < 5) {                            /* 需要测试集路径 */
            fprintf(stderr, "用法: nanogpt arith_eval <corpus.txt> <权重.bin> <测试集.txt>\n");
            return 1;
        }
        if (load_weights(argv[3]) != 0) return 1;  /* 加载权重 */
        arith_eval(argv[4]);                       /* 跑测试 */
        return 0;
    }

    if (strcmp(mode, "think") == 0) {
        /* think <corpus> <weights.bin> "题目" [样本数] */
        const char *wpath = argc > 3 ? argv[3] : NULL;
        if (!wpath || argc < 5) {
            fprintf(stderr, "用法: nanogpt think <corpus.txt> <权重.bin> \"题目\" [样本数=8]\n");
            return 1;
        }
        if (load_weights(wpath) != 0) return 1;    /* 加载权重 */
        char *q = to_utf8(argv[4]);                /* 命令行中文可能是 GBK，先转 UTF-8 */
        think_mode(q, argc > 5 ? atoi(argv[5]) : 8);  /* 默认采样 8 条 */
        free(q);                                   /* 释放转换结果 */
        return 0;
    }

    if (strcmp(mode, "chat") == 0) {
        /* chat <corpus> <weights.bin> ["单个问题"] */
        const char *wpath = argc > 3 ? argv[3] : NULL;
        if (!wpath) {                              /* 必须有权重 */
            fprintf(stderr, "用法: nanogpt chat <corpus.txt> <权重.bin> [\"问题\"]\n");
            return 1;
        }
        if (load_weights(wpath) != 0) return 1;    /* 加载权重 */
        chat_mode(argc > 4 ? argv[4] : NULL);      /* 有第 5 个参数就是一次性问答，否则交互 */
        return 0;
    }

    if (strcmp(mode, "sample") == 0) {
        /* sample <corpus> [weights.bin] ["prompt"] */
        const char *wpath = NULL, *prompt = "The ";  /* 默认参数 */
        for (int i = 3; i < argc; i++) {           /* 参数顺序灵活：自动识别哪个是权重文件 */
            if (strstr(argv[i], ".bin")) wpath = argv[i];  /* 带 .bin 的当权重 */
            else prompt = argv[i];                 /* 其余当提示词 */
        }
        if (wpath) { if (load_weights(wpath) != 0) return 1; }  /* 有权重就加载 */
        else printf("[提示] 未给权重文件，用随机初始化的权重生成（必然是乱码）\n");  /* 明确提示后果 */
        char *pu = to_utf8(prompt);          /* 命令行中文是 GBK，转 UTF-8 */
        generate(pu, 600);                     /* 生成 600 个字符 */
        free(pu);                              /* 释放转换结果 */
        return 0;
    }

    if (strcmp(mode, "resume") == 0) {
        /* resume <corpus> <weights.bin> <steps> [out.bin] */
        if (argc < 5) {                            /* 需要步数 */
            fprintf(stderr, "用法: nanogpt resume <corpus.txt> <权重.bin> <步数> [输出.bin]\n");
            return 1;
        }
        if (load_weights(argv[3]) != 0) return 1;  /* 断点续训必须能加载 */
        train(atoi(argv[4]));                      /* 继续训练指定步数 */
        generate("\nThe ", 400);                   /* 训练后立刻生成一段，检查效果 */
        if (argc > 5) save_weights(argv[5]);       /* 给了路径就保存 */
        return 0;
    }

    /* train <corpus> [steps] [out.bin] */
    int steps = argc > 3 ? atoi(argv[3]) : 2000;   /* 默认 2000 步 */
    train(steps);                                  /* 训练 */
    generate("\nThe ", 400);                       /* 生成样例，直观检查训练效果 */
    if (argc > 4) save_weights(argv[4]);           /* 给了路径就保存权重 */
    else printf("[提示] 未给保存路径，权重没落盘。用法: nanogpt train <corpus> <步数> <权重.bin>\n");  /* 提醒用户 */
    return 0;                                      /* 成功 */
}
