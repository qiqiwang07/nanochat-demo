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
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <stdint.h>
#ifdef _WIN32
#include <windows.h>
static void repf(const char *fmt, ...);
static void rep(const char *s);
#endif

/* ------------------------------ 超参数 ---------------------------------- */
#define NLAYER   4
#define NEMBD    128
#define NHEAD    4
#define MLP      512
#define VOCAB    256         /* 字节级词表：题目含 LaTeX 符号，必须覆盖全部字节 */
#define HD       (NEMBD / NHEAD)
#define RMS_EPS  1e-5f

static int B = 8;            /* batch */
static int T = 256;          /* 上下文长度：要能装下「问题+回答」一整轮对话 */
static int BT;               /* B*T */

/* ------------------------------ 参数表 ---------------------------------- */
typedef struct {
    const char *name;
    int n;
    float *p, *g, *m, *v;    /* 数值 / 梯度 / AdamW 一阶、二阶动量 */
} Param;

static Param params[40];
static int   nparams = 0;

static float *falloc(int n) {
    float *p = (float *)calloc((size_t)n, sizeof(float));
    if (!p) { fprintf(stderr, "out of memory\n"); exit(1); }
    return p;
}
static Param *add_param(const char *name, int n) {
    Param *q = &params[nparams++];
    q->name = strdup(name);          /* 必须复制：调用方复用了同一个栈缓冲 */
    q->n = n;
    q->p = falloc(n); q->g = falloc(n); q->m = falloc(n); q->v = falloc(n);
    return q;
}

/* ------------------------------ 随机数 ---------------------------------- */
static unsigned long long rng_state = 0x853c49e6748fea9bULL;
static unsigned int xrand(void) {
    rng_state ^= rng_state >> 12;
    rng_state ^= rng_state << 25;
    rng_state ^= rng_state >> 27;
    return (unsigned int)((rng_state * 0x2545F4914F6CDD1DULL) >> 32);
}
static float frand(void) { return (float)(xrand() >> 8) * (1.0f / 16777216.0f); }
static float nrand(void) {
    float u1 = frand() + 1e-7f, u2 = frand();
    return sqrtf(-2.0f * logf(u1)) * cosf(6.28318530718f * u2);
}

/* ------------------------------ 矩阵乘法（累加语义）--------------------
 * 权重统一按 [in][out] 行主序存放。
 *   mm_nn: C[M,N] += A[M,K] @ B[K,N]            (B 为 [in][out])
 *   mm_nt: C[M,N] += A[M,K] @ B[N,K]^T          (反传 dx)
 *   mm_tn: C[K,N] += A[M,K]^T @ B[M,N]          (反传 dW)                     */
#define PARFOR _Pragma("omp parallel for")
static void mm_nn(const float *A, const float *Bm, float *C, int M, int K, int N) {
#ifdef _OPENMP
#pragma omp parallel for
#endif
    for (int i = 0; i < M; i++) {
        float *crow = C + (size_t)i * N;
        for (int k = 0; k < K; k++) {
            float a = A[(size_t)i * K + k];
            if (a == 0.0f) continue;
            const float *brow = Bm + (size_t)k * N;
            for (int j = 0; j < N; j++) crow[j] += a * brow[j];
        }
    }
}
static void mm_nt(const float *A, const float *Bm, float *C, int M, int K, int N) {
#ifdef _OPENMP
#pragma omp parallel for
#endif
    for (int i = 0; i < M; i++) {
        const float *arow = A + (size_t)i * K;
        float *crow = C + (size_t)i * N;
        for (int n = 0; n < N; n++) {
            const float *brow = Bm + (size_t)n * K;
            float s = 0.0f;
            for (int k = 0; k < K; k++) s += arow[k] * brow[k];
            crow[n] += s;
        }
    }
}
static void mm_tn(const float *A, const float *Bm, float *C, int M, int K, int N) {
    for (int i = 0; i < M; i++) {
        const float *arow = A + (size_t)i * K;
        const float *brow = Bm + (size_t)i * N;
        for (int k = 0; k < K; k++) {
            float a = arow[k];
            float *crow = C + (size_t)k * N;
            for (int j = 0; j < N; j++) crow[j] += a * brow[j];
        }
    }
}

/* ------------------------------ 参数 ------------------------------------ */
static Param *p_tok, *p_pos, *p_lm, *b_lm;
static Param *Wqkv[NLAYER], *b_qkv[NLAYER], *Wo[NLAYER], *b_o[NLAYER];
static Param *W1[NLAYER], *b_1[NLAYER], *W2[NLAYER], *b_2[NLAYER];

/* ------------------------------ 激活缓存（每层独立！）------------------- */
static float *h_emb;                    /* 嵌入，即第 0 层输入 */
static float *h_inv1[NLAYER], *h_ln1[NLAYER], *h_qkv[NLAYER], *h_att[NLAYER];
static float *h_ao[NLAYER], *h_x1[NLAYER], *h_inv2[NLAYER], *h_ln2[NLAYER];
static float *h_pre[NLAYER], *h_act[NLAYER], *h_h2[NLAYER], *h_x2[NLAYER];
static float *h_invf, *h_xf, *h_logits;

static float *g_xin[NLAYER], *g_ln1[NLAYER], *g_qkv[NLAYER], *g_ao[NLAYER];
static float *g_ln2[NLAYER], *g_pre[NLAYER], *g_act[NLAYER], *g_xout[NLAYER];
static float *g_xf, *g_logits, *g_scratch;

static int *xs, *ys;

static void alloc_activations(void) {
    size_t BTC  = (size_t)BT * NEMBD;
    size_t BT3C = (size_t)BT * 3 * NEMBD;
    size_t BTMLP= (size_t)BT * MLP;
    size_t BTV  = (size_t)BT * VOCAB;
    size_t ATT  = (size_t)NHEAD * B * T * T;

    h_emb = falloc(BTC);
    h_invf = falloc(BT); h_xf = falloc(BTC); h_logits = falloc(BTV);
    g_xf = falloc(BTC); g_logits = falloc(BTV); g_scratch = falloc(BTC);
    for (int l = 0; l < NLAYER; l++) {
        h_inv1[l] = falloc(BT);   h_ln1[l] = falloc(BTC);  h_qkv[l] = falloc(BT3C);
        h_att[l]  = falloc(ATT);  h_ao[l]  = falloc(BTC);  h_x1[l]  = falloc(BTC);
        h_inv2[l] = falloc(BT);   h_ln2[l] = falloc(BTC);  h_pre[l] = falloc(BTMLP);
        h_act[l]  = falloc(BTMLP);h_h2[l]  = falloc(BTC);  h_x2[l]  = falloc(BTC);

        g_xin[l]  = falloc(BTC);  g_ln1[l] = falloc(BTC);  g_qkv[l] = falloc(BT3C);
        g_ao[l]   = falloc(BTC);  g_ln2[l] = falloc(BTC);  g_pre[l] = falloc(BTMLP);
        g_act[l]  = falloc(BTMLP);g_xout[l]= falloc(BTC);
    }
    xs = (int *)calloc(BT, sizeof(int));
    ys = (int *)calloc(BT, sizeof(int));
}

static void zero_grads(void) {
    for (int i = 0; i < nparams; i++)
        memset(params[i].g, 0, (size_t)params[i].n * sizeof(float));
}

/* ------------------------------ 初始化 ---------------------------------- */
static int is_bias(const char *name) {
    return strstr(name, ".b") != NULL || strstr(name, "bias") != NULL;
}
static void init_params(void) {
    p_tok = add_param("tok_emb", VOCAB * NEMBD);
    p_pos = add_param("pos_emb", T * NEMBD);
    for (int l = 0; l < NLAYER; l++) {
        char buf[64];
        snprintf(buf, sizeof buf, "L%d.Wqkv", l); Wqkv[l] = add_param(buf, 3 * NEMBD * NEMBD);
        snprintf(buf, sizeof buf, "L%d.bqkv", l); b_qkv[l] = add_param(buf, 3 * NEMBD);
        snprintf(buf, sizeof buf, "L%d.Wo",   l); Wo[l]   = add_param(buf, NEMBD * NEMBD);
        snprintf(buf, sizeof buf, "L%d.bo",   l); b_o[l]  = add_param(buf, NEMBD);
        snprintf(buf, sizeof buf, "L%d.W1",   l); W1[l]   = add_param(buf, NEMBD * MLP);
        snprintf(buf, sizeof buf, "L%d.b1",   l); b_1[l]  = add_param(buf, MLP);
        snprintf(buf, sizeof buf, "L%d.W2",   l); W2[l]   = add_param(buf, MLP * NEMBD);
        snprintf(buf, sizeof buf, "L%d.b2",   l); b_2[l]  = add_param(buf, NEMBD);
    }
    p_lm = add_param("lm_head", NEMBD * VOCAB);
    b_lm = add_param("lm_bias", VOCAB);

    long total = 0;
    for (int i = 0; i < nparams; i++) {
        Param *q = &params[i];
        total += q->n;
        if (is_bias(q->name)) { memset(q->p, 0, (size_t)q->n * sizeof(float)); continue; }
        float scale = strcmp(q->name, "lm_head") == 0 ? 0.001f : 0.02f;
        for (int j = 0; j < q->n; j++) q->p[j] = scale * nrand();
    }
    printf("参数张量 %d 个，参数总量 %ld (%.3fM)\n", nparams, total, total / 1e6);
}

/* ------------------------------ RMSNorm -------------------------------- */
static void rmsnorm_fwd(const float *x, float *out, float *inv_out, int rows) {
    for (int r = 0; r < rows; r++) {
        const float *xr = x + (size_t)r * NEMBD;
        float ss = 0.0f;
        for (int c = 0; c < NEMBD; c++) ss += xr[c] * xr[c];
        float inv = 1.0f / sqrtf(ss / NEMBD + RMS_EPS);
        inv_out[r] = inv;
        float *orow = out + (size_t)r * NEMBD;
        for (int c = 0; c < NEMBD; c++) orow[c] = xr[c] * inv;
    }
}
static void rmsnorm_bwd(const float *x, const float *inv, const float *dy,
                        float *dx, int rows) {
    for (int r = 0; r < rows; r++) {
        const float *xr = x + (size_t)r * NEMBD;
        const float *dr = dy + (size_t)r * NEMBD;
        float *dxr = dx + (size_t)r * NEMBD;
        float g = inv[r], s = 0.0f;
        for (int c = 0; c < NEMBD; c++) s += dr[c] * xr[c];
        float k = g * g * g * s / NEMBD;
        for (int c = 0; c < NEMBD; c++) dxr[c] += g * dr[c] - k * xr[c];
    }
}

/* ------------------------------ 前向传播 -------------------------------- */
static void forward(void) {
    /* 嵌入 */
    for (int i = 0; i < BT; i++) {
        int tok = xs[i], t = i % T;
        const float *te = p_tok->p + (size_t)tok * NEMBD;
        const float *pe = p_pos->p + (size_t)t * NEMBD;
        float *o = h_emb + (size_t)i * NEMBD;
        for (int c = 0; c < NEMBD; c++) o[c] = te[c] + pe[c];
    }

    const float *x_in = h_emb;
    for (int l = 0; l < NLAYER; l++) {
        /* ---- 注意力子层 ---- */
        rmsnorm_fwd(x_in, h_ln1[l], h_inv1[l], BT);
        memset(h_qkv[l], 0, (size_t)BT * 3 * NEMBD * sizeof(float));
        mm_nn(h_ln1[l], Wqkv[l]->p, h_qkv[l], BT, NEMBD, 3 * NEMBD);
        for (int i = 0; i < BT; i++) {
            float *q = h_qkv[l] + (size_t)i * 3 * NEMBD;
            for (int c = 0; c < 3 * NEMBD; c++) q[c] += b_qkv[l]->p[c];
        }

        float scale = 1.0f / sqrtf((float)HD);
#ifdef _OPENMP
#pragma omp parallel for collapse(2)
#endif
        for (int b = 0; b < B; b++) {
            for (int h = 0; h < NHEAD; h++) {
                int hoff = h * HD;
                for (int t = 0; t < T; t++) {
                    const float *q = h_qkv[l] + ((size_t)(b * T + t) * 3 * NEMBD) + hoff;
                    float *att = h_att[l] + (((size_t)b * NHEAD + h) * T + t) * T;
                    float maxs = -1e30f;
                    for (int u = 0; u <= t; u++) {
                        const float *k = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + NEMBD + hoff;
                        float s = 0.0f;
                        for (int d = 0; d < HD; d++) s += q[d] * k[d];
                        s *= scale;
                        att[u] = s;
                        if (s > maxs) maxs = s;
                    }
                    float sum = 0.0f;
                    for (int u = 0; u <= t; u++) { att[u] = expf(att[u] - maxs); sum += att[u]; }
                    float inv = 1.0f / sum;
                    for (int u = 0; u <= t; u++) att[u] *= inv;

                    float *ao = h_ao[l] + (size_t)(b * T + t) * NEMBD + hoff;
                    for (int d = 0; d < HD; d++) ao[d] = 0.0f;
                    for (int u = 0; u <= t; u++) {
                        const float *v = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + 2 * NEMBD + hoff;
                        float a = att[u];
                        for (int d = 0; d < HD; d++) ao[d] += a * v[d];
                    }
                }
            }
        }

        memset(g_scratch, 0, (size_t)BT * NEMBD * sizeof(float));   /* 复用为投影输出 */
        mm_nn(h_ao[l], Wo[l]->p, g_scratch, BT, NEMBD, NEMBD);
        for (int i = 0; i < BT; i++) {
            const float *xi = x_in + (size_t)i * NEMBD;
            const float *ao = g_scratch + (size_t)i * NEMBD;
            float *x1 = h_x1[l] + (size_t)i * NEMBD;
            for (int c = 0; c < NEMBD; c++) x1[c] = xi[c] + ao[c] + b_o[l]->p[c];
        }

        /* ---- 前馈子层 ---- */
        rmsnorm_fwd(h_x1[l], h_ln2[l], h_inv2[l], BT);
        memset(h_pre[l], 0, (size_t)BT * MLP * sizeof(float));
        mm_nn(h_ln2[l], W1[l]->p, h_pre[l], BT, NEMBD, MLP);
        for (int i = 0; i < BT; i++) {
            float *pr = h_pre[l] + (size_t)i * MLP;
            float *ac = h_act[l] + (size_t)i * MLP;
            for (int j = 0; j < MLP; j++) {
                float v = pr[j] + b_1[l]->p[j];
                pr[j] = v;
                ac[j] = v > 0.0f ? v : 0.0f;          /* ReLU */
            }
        }
        memset(h_h2[l], 0, (size_t)BT * NEMBD * sizeof(float));
        mm_nn(h_act[l], W2[l]->p, h_h2[l], BT, MLP, NEMBD);
        for (int i = 0; i < BT; i++) {
            const float *x1 = h_x1[l] + (size_t)i * NEMBD;
            const float *hh = h_h2[l] + (size_t)i * NEMBD;
            float *x2 = h_x2[l] + (size_t)i * NEMBD;
            for (int c = 0; c < NEMBD; c++) x2[c] = x1[c] + hh[c] + b_2[l]->p[c];
        }
        x_in = h_x2[l];                                /* 本层输出 = 下一层输入 */
    }

    /* ---- 输出层 ---- */
    rmsnorm_fwd(x_in, h_xf, h_invf, BT);
    memset(h_logits, 0, (size_t)BT * VOCAB * sizeof(float));
    mm_nn(h_xf, p_lm->p, h_logits, BT, NEMBD, VOCAB);
    for (int i = 0; i < BT; i++)
        for (int v = 0; v < VOCAB; v++) h_logits[(size_t)i * VOCAB + v] += b_lm->p[v];
}

/* softmax + 交叉熵，并把 dL/dlogits 写进 g_logits */
static float loss_and_grad(void) {
    float loss = 0.0f, scale = 1.0f / (float)BT;
    for (int i = 0; i < BT; i++) {
        float *lg = h_logits + (size_t)i * VOCAB;
        float maxl = lg[0];
        for (int v = 1; v < VOCAB; v++) if (lg[v] > maxl) maxl = lg[v];
        float sum = 0.0f;
        for (int v = 0; v < VOCAB; v++) { lg[v] = expf(lg[v] - maxl); sum += lg[v]; }
        float inv = 1.0f / sum;
        for (int v = 0; v < VOCAB; v++) lg[v] *= inv;
        int target = ys[i];
        loss += -logf(lg[target] + 1e-9f);
        float *dl = g_logits + (size_t)i * VOCAB;
        for (int v = 0; v < VOCAB; v++) dl[v] = (lg[v] - (v == target ? 1.0f : 0.0f)) * scale;
    }
    return loss * scale;
}

/* ------------------------------ 反向传播 -------------------------------- */
static void backward(void) {
    memset(g_xf, 0, (size_t)BT * NEMBD * sizeof(float));
    mm_nt(g_logits, p_lm->p, g_xf, BT, VOCAB, NEMBD);              /* dxf   */
    mm_tn(h_xf, g_logits, p_lm->g, BT, NEMBD, VOCAB);              /* dW_lm */
    for (int i = 0; i < BT; i++)
        for (int v = 0; v < VOCAB; v++) b_lm->g[v] += g_logits[(size_t)i * VOCAB + v];

    float *d_out = g_scratch;                                       /* 上一层输出梯度 */
    memset(g_xout[NLAYER - 1], 0, (size_t)BT * NEMBD * sizeof(float));
    rmsnorm_bwd(h_x2[NLAYER - 1], h_invf, g_xf, g_xout[NLAYER - 1], BT);
    memcpy(d_out, g_xout[NLAYER - 1], (size_t)BT * NEMBD * sizeof(float));

    for (int l = NLAYER - 1; l >= 0; l--) {
        const float *x_in = (l == 0) ? h_emb : h_x2[l - 1];

        /* ---- 前馈子层反向 ---- */
        memset(g_xin[l], 0, (size_t)BT * NEMBD * sizeof(float));
        memcpy(g_xin[l], d_out, (size_t)BT * NEMBD * sizeof(float));   /* 恒等支路 → x1 */
        for (int i = 0; i < BT; i++)
            for (int c = 0; c < NEMBD; c++) b_2[l]->g[c] += d_out[(size_t)i * NEMBD + c];

        memset(g_act[l], 0, (size_t)BT * MLP * sizeof(float));
        mm_nt(d_out, W2[l]->p, g_act[l], BT, NEMBD, MLP);              /* d act */
        mm_tn(h_act[l], d_out, W2[l]->g, BT, MLP, NEMBD);              /* dW2   */

        for (int i = 0; i < BT; i++) {
            const float *pr = h_pre[l] + (size_t)i * MLP;
            const float *ga = g_act[l] + (size_t)i * MLP;
            float *gp = g_pre[l] + (size_t)i * MLP;
            for (int j = 0; j < MLP; j++) gp[j] = pr[j] > 0.0f ? ga[j] : 0.0f;  /* ReLU' */
        }
        memset(g_ln2[l], 0, (size_t)BT * NEMBD * sizeof(float));
        mm_nt(g_pre[l], W1[l]->p, g_ln2[l], BT, MLP, NEMBD);           /* d ln2 */
        mm_tn(h_ln2[l], g_pre[l], W1[l]->g, BT, NEMBD, MLP);           /* dW1   */
        for (int i = 0; i < BT; i++)
            for (int j = 0; j < MLP; j++) b_1[l]->g[j] += g_pre[l][(size_t)i * MLP + j];
        rmsnorm_bwd(h_x1[l], h_inv2[l], g_ln2[l], g_xin[l], BT);       /* → x1 */

        /* ---- 注意力子层反向 ---- */
        memset(g_ao[l], 0, (size_t)BT * NEMBD * sizeof(float));
        memcpy(g_ao[l], g_xin[l], (size_t)BT * NEMBD * sizeof(float)); /* 恒等支路 → x_in */
        for (int i = 0; i < BT; i++)
            for (int c = 0; c < NEMBD; c++) b_o[l]->g[c] += g_ao[l][(size_t)i * NEMBD + c];

        memset(g_ln1[l], 0, (size_t)BT * NEMBD * sizeof(float));       /* 暂存 d(ao投影前) */
        mm_nt(g_ao[l], Wo[l]->p, g_ln1[l], BT, NEMBD, NEMBD);          /* d ao  */
        mm_tn(h_ao[l], g_ao[l], Wo[l]->g, BT, NEMBD, NEMBD);           /* dWo   */

        const float *dao = g_ln1[l];
        memset(g_qkv[l], 0, (size_t)BT * 3 * NEMBD * sizeof(float));
        float scale = 1.0f / sqrtf((float)HD);
#ifdef _OPENMP
#pragma omp parallel for collapse(2)
#endif
        for (int b = 0; b < B; b++) {
            for (int h = 0; h < NHEAD; h++) {
                int hoff = h * HD;
                float datt[8192];
                for (int t = 0; t < T; t++) {
                    const float *att = h_att[l] + (((size_t)b * NHEAD + h) * T + t) * T;
                    const float *do_ = dao + (size_t)(b * T + t) * NEMBD + hoff;
                    float *dq = g_qkv[l] + ((size_t)(b * T + t) * 3 * NEMBD) + hoff;
                    float dsum = 0.0f;
                    for (int u = 0; u <= t; u++) {
                        const float *v = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + 2 * NEMBD + hoff;
                        float s = 0.0f;
                        for (int d = 0; d < HD; d++) s += do_[d] * v[d];
                        datt[u] = s;
                        dsum += s * att[u];
                    }
                    for (int d = 0; d < HD; d++) dq[d] = 0.0f;
                    for (int u = 0; u <= t; u++) {
                        float ds = att[u] * (datt[u] - dsum);          /* softmax 反向 */
                        const float *v  = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + 2 * NEMBD + hoff;
                        float *dv = g_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + 2 * NEMBD + hoff;
                        for (int d = 0; d < HD; d++) dv[d] += att[u] * do_[d];
                        const float *q = h_qkv[l] + ((size_t)(b * T + t) * 3 * NEMBD) + hoff;
                        const float *k = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + NEMBD + hoff;
                        float *dk = g_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + NEMBD + hoff;
                        for (int d = 0; d < HD; d++) {
                            dq[d] += ds * k[d] * scale;
                            dk[d] += ds * q[d] * scale;
                        }
                    }
                }
            }
        }

        memset(g_ln1[l], 0, (size_t)BT * NEMBD * sizeof(float));
        mm_nt(g_qkv[l], Wqkv[l]->p, g_ln1[l], BT, 3 * NEMBD, NEMBD);    /* d ln1  */
        mm_tn(h_ln1[l], g_qkv[l], Wqkv[l]->g, BT, NEMBD, 3 * NEMBD);    /* dWqkv  */
        for (int i = 0; i < BT; i++)
            for (int c = 0; c < 3 * NEMBD; c++) b_qkv[l]->g[c] += g_qkv[l][(size_t)i * 3 * NEMBD + c];

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
    double s = 0.0;
    for (int i = 0; i < nparams; i++)
        for (int j = 0; j < params[i].n; j++)
            s += (double)params[i].g[j] * params[i].g[j];
    return (float)sqrt(s);
}
static void adamw_step(float lr, int step) {
    float b1 = 0.9f, b2 = 0.95f, eps = 1e-8f, wd = 0.01f;
    float bc1 = 1.0f - powf(b1, (float)step);
    float bc2 = 1.0f - powf(b2, (float)step);
    float gn = grad_norm();
    float clip = gn > 1.0f ? 1.0f / gn : 1.0f;      /* 全局梯度裁剪 */
    for (int i = 0; i < nparams; i++) {
        Param *q = &params[i];
        for (int j = 0; j < q->n; j++) {
            float g = q->g[j] * clip;
            q->m[j] = b1 * q->m[j] + (1 - b1) * g;
            q->v[j] = b2 * q->v[j] + (1 - b2) * g * g;
            float mh = q->m[j] / bc1, vh = q->v[j] / bc2;
            q->p[j] -= lr * (mh / (sqrtf(vh) + eps) + wd * q->p[j]);
        }
    }
}

/* ------------------------------ 语料与词表 ------------------------------ */
static unsigned char *corpus;
static int  *tokens;
static long  ncorpus, ntrain, nval;
static unsigned char vocab[VOCAB];
static int   byte2id[256];

static int load_corpus(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "打不开语料: %s\n", path); return -1; }
    fseek(f, 0, SEEK_END); ncorpus = ftell(f); fseek(f, 0, SEEK_SET);
    corpus = (unsigned char *)malloc((size_t)ncorpus);
    if (fread(corpus, 1, (size_t)ncorpus, f) != (size_t)ncorpus) { fclose(f); return -1; }
    fclose(f);

    long freq[256];
    memset(freq, 0, sizeof freq);
    for (long i = 0; i < ncorpus; i++) freq[corpus[i]]++;

    for (int k = 0; k < VOCAB; k++) {                 /* 取最高频字节 */
        int best = -1; long bestc = -1;
        for (int b = 0; b < 256; b++) {
            int used = 0;
            for (int j = 0; j < k; j++) if (vocab[j] == b) { used = 1; break; }
            if (!used && freq[b] > bestc) { bestc = freq[b]; best = b; }
        }
        vocab[k] = (unsigned char)best;
    }
    for (int b = 0; b < 256; b++) byte2id[b] = 0;
    for (int k = 0; k < VOCAB; k++) byte2id[vocab[k]] = k;

    if (ncorpus < 1000) {
        fprintf(stderr, "语料太小（%ld 字节），至少需要 1000 字节\n", ncorpus);
        return -1;
    }
    tokens = (int *)malloc((size_t)ncorpus * sizeof(int));
    for (long i = 0; i < ncorpus; i++) tokens[i] = byte2id[corpus[i]];
    ntrain = (long)(ncorpus * 0.98);
    nval   = ncorpus - ntrain;
    printf("语料 %ld 字节 | 训练 %ld | 验证 %ld | 字符表 %d 种\n", ncorpus, ntrain, nval, VOCAB);
    return 0;
}
static void sample_batch(int val_split) {
    long lo = val_split ? ntrain : 0;
    long hi = val_split ? ntrain + nval : ntrain;
    for (int b = 0; b < B; b++) {
        long start = lo + (long)(xrand() % (unsigned)(hi - lo - T - 1));
        for (int t = 0; t < T; t++) {
            xs[b * T + t] = tokens[start + t];
            ys[b * T + t] = tokens[start + t + 1];
        }
    }
}
static float eval_loss(int batches) {
    float tot = 0.0f;
    for (int i = 0; i < batches; i++) { sample_batch(1); forward(); tot += loss_and_grad(); }
    return tot / batches;
}

/* ------------------------------ 文本生成 -------------------------------- */
static void generate(const char *prompt, int nchars) {
    static int ctx[8192];
    int n = 0;
    for (const char *p = prompt; *p && n < 8000; p++) ctx[n++] = byte2id[(unsigned char)*p];
    if (n == 0) ctx[n++] = byte2id['\n'];

    int savedB = B;
    B = 1;                                    /* 生成只用一条序列 */
    printf("--- 生成 %d 字符 | 提示: \"%s\" ---\n", nchars, prompt);
    for (int i = 0; i < n; i++) putchar(vocab[ctx[i]]);
    for (int s = 0; s < nchars; s++) {
        int len = n < T ? n : T;
        BT = len;
        for (int t = 0; t < len; t++) { xs[t] = ctx[n - len + t]; ys[t] = 0; }
        forward();
        float *lg = h_logits + (size_t)(len - 1) * VOCAB;
        float temp = 0.8f, sum = 0.0f, probs[VOCAB];
        for (int v = 0; v < VOCAB; v++) { probs[v] = expf(lg[v] / temp); sum += probs[v]; }
        float r = frand() * sum, acc = 0.0f;
        int pick = VOCAB - 1;
        for (int v = 0; v < VOCAB; v++) { acc += probs[v]; if (r <= acc) { pick = v; break; } }
        ctx[n++] = pick;
        putchar(vocab[pick]);
        fflush(stdout);
    }
    printf("\n--- 结束 ---\n");
    BT = B * T; B = savedB;
}

/* ------------------------------ 梯度检查 --------------------------------
 * float32 下逐元素中心差分会被精度噪声淹没（真梯度 ~1e-4 时噪声 ~5e-4）。
 * 因此主要用“方向导数”检查：把整个参数张量沿随机单位方向 d 移动 ±eps，
 * 比较 (L(p+eps*d)-L(p-eps*d))/(2eps) 与 sum_j g_j*d_j。
 * 信号是整张量的梯度，远大于噪声，能同时覆盖该张量的所有元素。 */
static int gradcheck(void) {
    printf("\n=== 梯度检查 ===\n（逐张量方向导数 + 逐元素抽查，float32 精度）\n");
    int savedB = B;
    B = 2; BT = B * T;
    alloc_activations();
    sample_batch(0);
    zero_grads();
    forward();
    loss_and_grad();
    backward();

    /* 步长选择：float32 下 expf/logf 会给 loss 带来 ~1e-6 的绝对误差。
       数值差分 2*eps*|g| 必须远大于它，否则就是纯噪声。
       eps=0.2 时沿单位方向的每元素扰动约 0.2/sqrt(n)≈0.004，曲率误差仍很小。 */
    float eps = 0.2f;
    float noise_floor = 1e-4f;      /* 方向导数低于此值即视为噪声不可分辨 */
    float worst_dir = 0.0f;
    int bad = 0;

    /* 1) 方向导数：每个参数张量一次 */
    printf("\n--- [1] 方向导数（覆盖每个张量的全部元素）---\n");
    for (int pi = 0; pi < nparams; pi++) {
        Param *q = &params[pi];
        float *dir = (float *)malloc((size_t)q->n * sizeof(float));
        double norm = 0.0;
        for (int j = 0; j < q->n; j++) { dir[j] = frand() * 2.0f - 1.0f; norm += (double)dir[j] * dir[j]; }
        norm = sqrt(norm) + 1e-12;
        for (int j = 0; j < q->n; j++) dir[j] = (float)(dir[j] / norm);

        double ana = 0.0;
        for (int j = 0; j < q->n; j++) ana += (double)q->g[j] * dir[j];

        for (int j = 0; j < q->n; j++) q->p[j] += eps * dir[j];
        forward(); double lp = loss_and_grad();
        for (int j = 0; j < q->n; j++) q->p[j] -= 2.0f * eps * dir[j];
        forward(); double lm = loss_and_grad();
        for (int j = 0; j < q->n; j++) q->p[j] += eps * dir[j];

        double num = (lp - lm) / (2.0 * eps);
        double denom = fabs(num) + fabs(ana) + 1e-6;
        double rel = fabs(num - ana) / denom;
        int noisy = fabs(ana) < noise_floor;      /* 梯度太小，float32 分辨不了 */
        int ok = rel < 0.08;
        if (rel > worst_dir && !noisy) worst_dir = rel;
        if (!ok && !noisy) bad++;
        printf("  %s %-10s 数值=%+.6e 解析=%+.6e 相对误差=%.2e %s\n",
               ok ? "✔" : (noisy ? "~" : "✘"), q->name, num, ana, rel,
               noisy ? "(信号低于噪声门限，跳过)" : "");
        free(dir);
    }

    /* 2) 逐元素抽查：只覆盖梯度足够大的元素（小梯度在 float32 下必然被噪声主导） */
    printf("\n--- [2] 逐元素抽查（只比较 |梯度| > 1e-3 的位置）---\n");
    zero_grads(); forward(); loss_and_grad(); backward();
    float worst_el = 0.0f;
    int checked = 0, skipped = 0;
    for (int pi = 0; pi < nparams; pi++) {
        Param *q = &params[pi];
        for (int k = 0; k < 2; k++) {
            int idx = (int)(xrand() % (unsigned)q->n);
            float ana = q->g[idx];
            if (fabsf(ana) < 1e-3f) { skipped++; continue; }
            float orig = q->p[idx];
            q->p[idx] = orig + eps; forward(); float lp = loss_and_grad();
            q->p[idx] = orig - eps; forward(); float lm = loss_and_grad();
            q->p[idx] = orig;
            float num = (lp - lm) / (2 * eps);
            float rel = fabsf(num - ana) / (fabsf(num) + fabsf(ana) + 1e-6f);
            if (rel > worst_el) worst_el = rel;
            if (rel > 0.05f) {
                bad++;
                printf("  ✘ %-10s idx=%6d 数值=%+.6e 解析=%+.6e 相对误差=%.2e\n",
                       q->name, idx, num, ana, rel);
            }
            checked++;
        }
    }
    printf("  比较 %d 处（%d 处因梯度太小跳过），最大相对误差 %.3e\n", checked, skipped, worst_el);
    printf("\n方向导数最大相对误差 %.3e → %s\n", worst_dir,
           worst_dir < 0.05 ? "反向传播正确 ✔" : "反向传播有误 ✘");
    B = savedB; BT = B * T;
    return bad ? 1 : 0;
}

/* ------------------------------ 训练 ------------------------------------ */
static void train(int steps) {
    printf("\n=== 训练 %d 步 ===\n", steps);
    printf("配置: %d 层 | 宽度 %d | %d 头 | 上下文 %d | batch %d | 每步 %d token\n\n",
           NLAYER, NEMBD, NHEAD, T, B, B * T);
    clock_t t0 = clock();
    float best_val = 1e9f;
    int warm = steps / 10 + 1;
    for (int step = 1; step <= steps; step++) {
        float lr;
        if (step <= warm) lr = 3e-3f * step / (float)warm;
        else {
            float prog = (float)(step - warm) / (float)(steps - warm);
            lr = 3e-3f * 0.5f * (1.0f + cosf(3.14159265f * prog));
        }
        sample_batch(0);
        forward();
        float loss = loss_and_grad();
        zero_grads();
        backward();
        adamw_step(lr, step);

        if (step == 1 || step % 50 == 0) {
            double secs = (double)(clock() - t0) / CLOCKS_PER_SEC;
            printf("step %5d/%d | 训练 loss %.4f | lr %.2e | %6.1fs | %.0f ms/step\n",
                   step, steps, loss, lr, secs, secs * 1000.0 / step);
            fflush(stdout);
        }
        if (step % 500 == 0) {
            float vl = eval_loss(10);
            printf("             验证 loss %.4f%s\n", vl, vl < best_val ? "  (新低)" : "");
            if (vl < best_val) best_val = vl;
        }
    }
    printf("\n训练完成，用时 %.1f 秒，最终验证 loss %.4f\n",
           (double)clock() / CLOCKS_PER_SEC, eval_loss(20));
}

/* ------------------------------ 权重存取 --------------------------------
 * 自描述二进制格式，便于断点续训：
 *   magic "NANOGPT1" | 6×int32 (版本, NLAYER, NEMBD, NHEAD, MLP, T)
 *   VOCAB 字节字符表 | int32 张量个数
 *   每个张量: char name[32] | int32 n | float p[n] | float m[n] | float v[n]
 * 一并保存 AdamW 一阶/二阶动量，加载后可以无缝继续训练。 */
static const char SAVE_MAGIC[8] = {'N','A','N','O','G','P','T','1'};

static int save_weights(const char *path) {
    FILE *f = fopen(path, "wb");
    if (!f) { fprintf(stderr, "无法写入: %s\n", path); return -1; }
    int32_t hdr[6] = {1, NLAYER, NEMBD, NHEAD, MLP, T};
    long bytes = 0;
    bytes += (long)fwrite(SAVE_MAGIC, 1, 8, f);
    bytes += (long)fwrite(hdr, sizeof(int32_t), 6, f);
    bytes += (long)fwrite(vocab, 1, VOCAB, f);
    int32_t np = nparams;
    bytes += (long)fwrite(&np, sizeof(int32_t), 1, f);
    for (int i = 0; i < nparams; i++) {
        char name[32];
        memset(name, 0, sizeof name);
        strncpy(name, params[i].name, 31);
        int32_t n = params[i].n;
        bytes += (long)fwrite(name, 1, 32, f);
        bytes += (long)fwrite(&n, sizeof(int32_t), 1, f);
        bytes += (long)fwrite(params[i].p, sizeof(float), n, f);
        bytes += (long)fwrite(params[i].m, sizeof(float), n, f);
        bytes += (long)fwrite(params[i].v, sizeof(float), n, f);
    }
    fclose(f);
    printf("权重已保存: %s (%.2f MB，含 AdamW 动量)\n", path, bytes / 1e6);
    return 0;
}

static int load_weights(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "无法读取权重: %s\n", path); return -1; }
    char magic[8]; int32_t hdr[6];
    if (fread(magic, 1, 8, f) != 8 || memcmp(magic, SAVE_MAGIC, 8) != 0) {
        fprintf(stderr, "不是本程序保存的权重文件: %s\n", path);
        fclose(f); return -1;
    }
    if (fread(hdr, sizeof(int32_t), 6, f) != 6) { fclose(f); return -1; }
    if (hdr[1] != NLAYER || hdr[2] != NEMBD || hdr[3] != NHEAD ||
        hdr[4] != MLP || hdr[5] != T) {
        fprintf(stderr, "架构不匹配：文件是 %d层/%d宽/%d头/MLP%d/上下文%d，"
                        "本程序是 %d/%d/%d/%d/%d\n",
                hdr[1], hdr[2], hdr[3], hdr[4], hdr[5],
                NLAYER, NEMBD, NHEAD, MLP, T);
        fclose(f); return -1;
    }
    if (fread(vocab, 1, VOCAB, f) != VOCAB) { fclose(f); return -1; }
    for (int b = 0; b < 256; b++) byte2id[b] = 0;
    for (int k = 0; k < VOCAB; k++) byte2id[vocab[k]] = k;

    int32_t np = 0;
    if (fread(&np, sizeof(int32_t), 1, f) != 1 || np != nparams) {
        fprintf(stderr, "参数张量个数不匹配（文件 %d，程序 %d）\n", np, nparams);
        fclose(f); return -1;
    }
    for (int i = 0; i < nparams; i++) {
        char name[32]; int32_t n = 0;
        if (fread(name, 1, 32, f) != 32) { fclose(f); return -1; }
        if (fread(&n, sizeof(int32_t), 1, f) != 1 ||
            n != params[i].n || strncmp(name, params[i].name, 31) != 0) {
            fprintf(stderr, "张量 %d 不匹配（文件 %s / 程序 %s）\n", i, name, params[i].name);
            fclose(f); return -1;
        }
        if (fread(params[i].p, sizeof(float), n, f) != (size_t)n) { fclose(f); return -1; }
        if (fread(params[i].m, sizeof(float), n, f) != (size_t)n) { fclose(f); return -1; }
        if (fread(params[i].v, sizeof(float), n, f) != (size_t)n) { fclose(f); return -1; }
    }
    fclose(f);
    printf("已加载权重: %s\n", path);
    return 0;
}

/* ------------------------------ 对话模式 -------------------------------- */
static int ctx_append(int *ctx, int n, const char *s) {
    for (; *s; s++) if (n < 8190) ctx[n++] = byte2id[(unsigned char)*s];
    return n;
}

/* 从 ctx 继续采样，边生成边打印；遇到停止串就停下并把它从 ctx 里去掉。
   返回新增字符数。 */
static int chat_generate(int *ctx, int *n, int maxchars, const char *stop) {
    int savedB = B;
    int stoplen = (int)strlen(stop);
    int start = *n;
    B = 1;
    for (int s = 0; s < maxchars; s++) {
        int len = *n < T ? *n : T;
        BT = len;
        for (int t = 0; t < len; t++) { xs[t] = ctx[*n - len + t]; ys[t] = 0; }
        forward();
        float *lg = h_logits + (size_t)(len - 1) * VOCAB;
        float temp = 0.85f, sum = 0.0f, probs[VOCAB];
        /* top-k=20：把其余 logits 压成 0，避免反复吐同一句套话 */
        float kth = -1e30f;
        for (int v = 0; v < VOCAB; v++) if (lg[v] > kth) kth = lg[v];
        for (int r = 0; r < 19; r++) {              /* 迭代 19 次得到第 20 大的值 */
            float best = -1e30f;
            for (int v = 0; v < VOCAB; v++) if (lg[v] < kth && lg[v] > best) best = lg[v];
            kth = best;
        }
        for (int v = 0; v < VOCAB; v++) {
            if (lg[v] < kth) { probs[v] = 0.0f; continue; }
            probs[v] = expf((lg[v] - kth) / temp);
            sum += probs[v];
        }
        float r = frand() * sum, acc = 0.0f;
        int pick = VOCAB - 1;
        for (int v = 0; v < VOCAB; v++) { acc += probs[v]; if (r <= acc) { pick = v; break; } }
        if (*n >= 8190) break;
        ctx[(*n)++] = pick;
        putchar(vocab[pick]);
        fflush(stdout);
        if (*n - start >= stoplen) {                 /* 命中停止串？ */
            int match = 1;
            for (int k = 0; k < stoplen; k++)
                if (vocab[ctx[*n - stoplen + k]] != (unsigned char)stop[k]) { match = 0; break; }
            if (match) { *n -= stoplen; break; }
        }
    }
    B = savedB; BT = B * T;
    return *n - start;
}

/* chat_mode：不传 question 就是交互式；传了就是问一句答一句然后退出 */
static void chat_mode(const char *once) {
    static int ctx[8192];
    static char line[2048];
    int n = 0;
    printf("\n================ C 版迷你对话模型 ================\n");
    printf("直接输入问题回车；quit 退出；clear 重开对话。\n");
    printf("（0.8M 参数、纯 C 训练，回答会很幼稚，请见谅）\n");
    printf("==================================================\n");
    for (;;) {
        if (once) {
            strncpy(line, once, sizeof line - 1);
            line[sizeof line - 1] = 0;
        } else {
            printf("\n你: "); fflush(stdout);
            if (!fgets(line, sizeof line, stdin)) { printf("\n再见！\n"); break; }
            line[strcspn(line, "\r\n")] = 0;
            if (!strcmp(line, "quit") || !strcmp(line, "exit")) { printf("再见！\n"); break; }
            if (!strcmp(line, "clear")) { n = 0; printf("[对话已清空]\n"); continue; }
            if (!line[0]) continue;
        }
        n = ctx_append(ctx, n, "### User: ");
        n = ctx_append(ctx, n, line);
        n = ctx_append(ctx, n, "\n### Assistant:");
        if (n > 6000) {                              /* 太长了就只留最近一段 */
            int keep = 3000;
            memmove(ctx, ctx + (n - keep), (size_t)keep * sizeof(int));
            n = keep;
        }
        printf("AI:");
        chat_generate(ctx, &n, 300, "\n###");
        printf("\n");
        n = ctx_append(ctx, n, "\n");
        if (once) break;
    }
}

/* ------------------------------ 解题模式 -------------------------------- */
static void ask_mode(const char *question) {
    static int ctx[8192];
    int n = 0;
    n = ctx_append(ctx, n, "### Problem: ");
    n = ctx_append(ctx, n, question);
    n = ctx_append(ctx, n, "\n### Solution:");
    printf("### Problem: %s\n### Solution:", question);
    chat_generate(ctx, &n, 500, "\n###");
    printf("\n");
}

/* ====================== 命令行中文编码（GBK -> UTF-8）=================== */
static int looks_utf8(const char *s) {
    for (const unsigned char *p = (const unsigned char *)s; *p; ) {
        if (*p < 0x80) { p++; continue; }
        int n = (*p >= 0xF0) ? 4 : (*p >= 0xE0) ? 3 : (*p >= 0xC0) ? 2 : 0;
        if (!n) return 0;
        for (int i = 1; i < n; i++) if ((p[i] & 0xC0) != 0x80) return 0;
        p += n;
    }
    return 1;
}
static char *to_utf8(const char *s) {
#ifdef _WIN32
    if (!looks_utf8(s)) {
        int wlen = MultiByteToWideChar(CP_ACP, 0, s, -1, NULL, 0);
        if (wlen > 0) {
            wchar_t *w = (wchar_t *)malloc(sizeof(wchar_t) * (size_t)wlen);
            MultiByteToWideChar(CP_ACP, 0, s, -1, w, wlen);
            int ulen = WideCharToMultiByte(CP_UTF8, 0, w, -1, NULL, 0, NULL, NULL);
            char *u = (char *)malloc((size_t)ulen);
            WideCharToMultiByte(CP_UTF8, 0, w, -1, u, ulen, NULL, NULL);
            free(w);
            return u;
        }
    }
#endif
    char *u = (char *)malloc(strlen(s) + 1);
    strcpy(u, s);
    return u;
}

/* ====================== 算术考试（用精确计算器判分）===================== */
static int gen_text(const char *prompt, char *out, int maxch, float temp);

static void arith_eval(const char *testfile) {
    FILE *f = fopen(testfile, "r");
    if (!f) { printf("打不开测试集: %s\n", testfile); return; }
    char line[256];
    int total = 0, ok = 0;
    int ct[3] = {0, 0, 0}, co[3] = {0, 0, 0};      /* 0 一位数 1 两位数 2 乘法 */
    static char out[64];
    while (fgets(line, sizeof line, f)) {
        int a, b, expect;
        char op;
        if (sscanf(line, "%d%c%d\t%d", &a, &op, &b, &expect) != 4) continue;
        char prompt[160];
        snprintf(prompt, sizeof prompt, "%d%c%d=", a, op, b);
        gen_text(prompt, out, 12, 0.01f);          /* 接近贪婪解码 */
        int got = (int)strtol(out, NULL, 10);
        int cat = (op == '*') ? 2 : ((a > 9 || b > 9) ? 1 : 0);
        total++; ct[cat]++;
        if (got == expect) { ok++; co[cat]++; }
        if (total <= 6) {                       /* 前几题打印出来看模型到底输出了什么 */
            char shown[32];
            size_t k = 0;
            while (out[k] && out[k] != '\n' && k < sizeof shown - 1) { shown[k] = out[k]; k++; }
            shown[k] = 0;
            printf("  例 %d%c%d：期望 %d，模型 \"%s\" %s\n",
                   a, op, b, expect, shown, got == expect ? "✔" : "✘");
        }
    }
    fclose(f);
    printf("\n===== 算术准确率（共 %d 题，判分用精确计算器）=====\n", total);
    const char *names[3] = {"一位数加减", "两位数加减", "乘法表  "};
    for (int i = 0; i < 3; i++)
        printf("  %s : %4d/%-4d = %5.1f%%\n", names[i], co[i], ct[i],
               ct[i] ? 100.0 * co[i] / ct[i] : 0.0);
    printf("  ------------------------------ \n");
    printf("  总计        : %4d/%-4d = %5.1f%%\n", ok, total, total ? 100.0 * ok / total : 0.0);
}

/* ====================== 精确算术（独立于模型的验算器）==================== */
static const char *EP;
static double e_expr(void);
static void e_skip(void) { while (*EP == ' ' || *EP == '\t') EP++; }
static double e_prim(void) {
    e_skip();
    if (*EP == '(') { EP++; double v = e_expr(); e_skip(); if (*EP == ')') EP++; return v; }
    if (*EP == '-') { EP++; return -e_prim(); }
    if (*EP == '+') { EP++; return e_prim(); }
    char *end; double v = strtod(EP, &end);
    if (end == EP) return NAN;
    EP = end; return v;
}
static double e_pow(void) {
    double b = e_prim();
    for (;;) {
        e_skip();
        if (*EP == '^') { EP++; b = pow(b, e_pow()); }
        else if (*EP == '%') { EP++; b = b / 100.0; }   /* 百分号是后缀：80% = 0.8 */
        else break;
    }
    return b;
}
static double e_term(void) {
    double v = e_pow();
    for (;;) {
        e_skip();
        if (*EP == '*') { EP++; v *= e_pow(); }
        else if (*EP == '/') { EP++; double r = e_pow(); v = (r == 0) ? NAN : v / r; }
        else break;
    }
    return v;
}
static double e_expr(void) {
    double v = e_term();
    for (;;) {
        e_skip();
        if (*EP == '+') { EP++; v += e_term(); }
        else if (*EP == '-') { EP++; v -= e_term(); }
        else break;
    }
    return v;
}
static double eval_expr(const char *s) { EP = s; return e_expr(); }

/* ====================== 生成到缓冲区（不打印）=========================== */
static int gen_text(const char *prompt, char *out, int maxch, float temp) {
    static int ctx[8192];
    int n = 0;
    for (const char *p = prompt; *p && n < 8000; p++) ctx[n++] = byte2id[(unsigned char)*p];
    int savedB = B, m = 0;
    B = 1;
    for (int s = 0; s < maxch; s++) {
        int len = n < T ? n : T;
        BT = len;
        for (int t = 0; t < len; t++) { xs[t] = ctx[n - len + t]; ys[t] = 0; }
        forward();
        float *lg = h_logits + (size_t)(len - 1) * VOCAB;
        float kth = -1e30f;                     /* top-30 采样 */
        for (int v = 0; v < VOCAB; v++) if (lg[v] > kth) kth = lg[v];
        for (int r = 0; r < 29; r++) {
            float best = -1e30f;
            for (int v = 0; v < VOCAB; v++) if (lg[v] < kth && lg[v] > best) best = lg[v];
            kth = best;
        }
        float probs[VOCAB], sum = 0.0f;
        float mxl = -1e30f;                     /* 用最大 logit 做稳定归一化 */
        for (int v = 0; v < VOCAB; v++) if (lg[v] > mxl) mxl = lg[v];
        for (int v = 0; v < VOCAB; v++) {
            if (lg[v] < kth) { probs[v] = 0.0f; continue; }
            float e = (lg[v] - mxl) / temp;
            if (e > 60.0f) e = 60.0f;           /* 防 exp 溢出（temp 很小时尤其重要） */
            probs[v] = expf(e); sum += probs[v];
        }
        float r = frand() * sum, acc = 0.0f;
        int pick = VOCAB - 1;
        for (int v = 0; v < VOCAB; v++) { acc += probs[v]; if (r <= acc) { pick = v; break; } }
        ctx[n++] = pick;
        out[m++] = (char)vocab[pick];
        if (m >= 4 && out[m-1] == '#' && out[m-2] == '#' && out[m-3] == '#') break;
    }
    out[m] = 0;
    B = savedB; BT = B * T;
    return m;
}

/* ====================== 逐步验算 + 投票 ================================ */
typedef struct {
    char   steps[1024];
    char   answer[64];
    int    n_step, n_ok;
    double last_ok;
    int    has_answer;
} Chain;

static void verify_chain(const char *gen, Chain *c) {
    memset(c, 0, sizeof *c);
    c->last_ok = NAN;
    const char *th = strstr(gen, "### 思考:");
    if (!th) th = gen; else th += strlen("### 思考:");
    const char *ans = strstr(th, "### 答案:");
    size_t thlen = ans ? (size_t)(ans - th) : strlen(th);
    if (thlen >= sizeof c->steps) thlen = sizeof c->steps - 1;
    memcpy(c->steps, th, thlen);
    c->steps[thlen] = 0;
    if (ans) {
        ans += strlen("### 答案:");
        while (*ans == ' ') ans++;
        size_t k = 0;
        while (ans[k] && ans[k] != '\n' && ans[k] != '#' && k < sizeof c->answer - 1) {
            c->answer[k] = ans[k]; k++;
        }
        c->answer[k] = 0;
    }
    /* 按 ';' 切分步骤，逐步用精确计算器验算（不用 strtok_r，避免平台差异） */
    const char *p = c->steps;
    char tok[512];
    while (*p) {
        const char *semi = strchr(p, ';');
        size_t len = semi ? (size_t)(semi - p) : strlen(p);
        if (len >= sizeof tok) len = sizeof tok - 1;
        memcpy(tok, p, len); tok[len] = 0;
        p = semi ? semi + 1 : p + strlen(p);
        char *t = tok;
        while (*t == ' ') t++;
        char *eq = strrchr(t, '=');
        if (!eq) continue;
        *eq = 0;
        char *valstr = eq + 1;
        while (*valstr == ' ') valstr++;
        double claimed = atof(valstr);
        double got = eval_expr(t);
        c->n_step++;
        if (!isnan(got) && fabs(got - claimed) <= 1e-4 * fmax(1.0, fabs(claimed))) {
            c->n_ok++;
            c->last_ok = got;
        }
    }
    c->has_answer = (c->n_step > 0 && c->n_ok == c->n_step);
}

static void think_mode(const char *problem, int n_samples) {
    char prompt[1024], gen[2048];
    snprintf(prompt, sizeof prompt, "### 题目: %s\n### 思考:", problem);
    Chain best, cur;
    memset(&best, 0, sizeof best);
    best.n_ok = -1;
    printf("\n【题目】%s\n", problem);
    printf("【模型】我们自己用 C 训练的 nanogpt（%d 层 / 宽度 %d）\n\n", NLAYER, NEMBD);
    for (int k = 0; k < n_samples; k++) {
        gen_text(prompt, gen, 260, 0.75f);
        verify_chain(gen, &cur);
        printf("【思路 %d】%.*s\n", k + 1, (int)strcspn(cur.steps, "\n"), cur.steps);
        printf("         验算 %d/%d 步通过", cur.n_ok, cur.n_step);
        if (cur.has_answer) printf("  → 推出 %.10g\n", cur.last_ok);
        else printf("  → 有步骤不成立，不可信\n");
        if (cur.n_ok > best.n_ok) { best = cur; }
    }
    printf("\n【选定】思路 %d（%d/%d 步通过验算）\n", best.n_ok + 1, best.n_ok, best.n_step);
    if (best.has_answer) {
        printf("【答案】%.10g\n", best.last_ok);
        printf("【依据】答案由 C 写的精确计算器从最后一步算出，不是模型猜的数字。\n");
    } else {
        printf("【答案】给不出可信答案：所有思路都过不了验算。\n");
        printf("【说明】这超出 0.89M 参数模型的能力了。要么用 solver.exe 的规则题型，要么换更大的模型。\n");
    }
}

/* ============================ 一元一次方程 ===============================
 * 支持形如 2x+3=7、3*x-1=x/2+4 的线性方程，解析成 (系数, 常数) 形式。 */
typedef struct { double a, b; } Lin;

static const char *lin_term(const char *s, Lin *out) {
    Lin t = {0, 0};
    while (*s == ' ') s++;
    double sign = 1;
    if (*s == '+') s++;
    else if (*s == '-') { sign = -1; s++; }
    double coef = 1;
    int have_num = 0;
    char *end;
    double v = strtod(s, &end);
    if (end != s) { coef = v; have_num = 1; s = end; }
    while (*s == ' ' || *s == '*') s++;
    if (*s == 'x' || *s == 'X') {
        s++;
        t.a = sign * coef;
    } else if (have_num) {
        t.b = sign * coef;
    } else {
        return NULL;                       /* 不是合法的项 */
    }
    /* 处理 x/2 这种除法 */
    while (*s == ' ') s++;
    if (*s == '/') {
        s++;
        double d = strtod(s, &end);
        if (end != s && d != 0) { t.a /= d; t.b /= d; s = end; }
    }
    *out = t;
    return s;
}

static int solve_linear(const char *eq, double *x_out, char *why, size_t whysz) {
    const char *eqpos = strchr(eq, '=');
    if (!eqpos) { snprintf(why, whysz, "没有等号"); return 0; }
    Lin left = {0, 0}, right = {0, 0};
    const char *p = eq;
    while (p < eqpos) {
        Lin t;
        p = lin_term(p, &t);
        if (!p) { snprintf(why, whysz, "左边第 %ld 个字符处看不懂", (long)(p - eq) + 1); return 0; }
        left.a += t.a; left.b += t.b;
        while (*p == ' ') p++;
    }
    p = eqpos + 1;
    while (*p) {
        Lin t;
        p = lin_term(p, &t);
        if (!p) { snprintf(why, whysz, "右边看不懂"); return 0; }
        right.a += t.a; right.b += t.b;
        while (*p == ' ') p++;
    }
    double a = left.a - right.a, b = right.b - left.b;
    if (fabs(a) < 1e-12) { snprintf(why, whysz, "这不是一元一次方程（x 的系数抵消了）"); return 0; }
    *x_out = b / a;
    snprintf(why, whysz, "%s\n   左边 = %.6gx + %.6g，右边 = %.6gx + %.6g\n   =>  x = %.6g",
             eq, left.a, left.b, right.a, right.b, *x_out);
    return 1;
}

/* ======================= 中文数字与题型规则引擎 =========================
 * 设计原则：规则只负责「看懂题型 + 找出数字的角色」，所有算术一律交给
 * eval_arith 精确计算。所以输出里的每个数字都能被手工核对。 */
static int u8_next(const char *s, unsigned *cp) {
    const unsigned char *p = (const unsigned char *)s;
    if (*p < 0x80) { *cp = *p; return 1; }
    if ((*p & 0xE0) == 0xC0) { *cp = ((p[0] & 0x1Fu) << 6) | (p[1] & 0x3Fu); return 2; }
    if ((*p & 0xF0) == 0xE0) { *cp = ((p[0] & 0x0Fu) << 12) | ((p[1] & 0x3Fu) << 6) | (p[2] & 0x3Fu); return 3; }
    *cp = ((p[0] & 0x07u) << 18) | ((p[1] & 0x3Fu) << 12) | ((p[2] & 0x3Fu) << 6) | (p[3] & 0x3Fu);
    return 4;
}
static const char *u8_prev(const char *start, const char *pos) {
    if (pos <= start) return start;
    pos--;
    while (pos > start && ((unsigned char)*pos & 0xC0) == 0x80) pos--;
    return pos;
}
/* 返回汉字数字的数值，不是数字返回 -1 */
static int cn_digit(unsigned cp) {
    switch (cp) {
        case 0x96F6: return 0;  /* 零 */
        case 0x4E00: return 1;  /* 一 */
        case 0x4E8C: return 2;  /* 二 */
        case 0x4E09: return 3;  /* 三 */
        case 0x56DB: return 4;  /* 四 */
        case 0x4E94: return 5;  /* 五 */
        case 0x516D: return 6;  /* 六 */
        case 0x4E03: return 7;  /* 七 */
        case 0x516B: return 8;  /* 八 */
        case 0x4E5D: return 9;  /* 九 */
        case 0x4E24: return 2;  /* 两 */
        default: return -1;
    }
}
/* 解析「十二」「二十」「八十五」「一百零五」，返回消耗的字节数，0 表示不是数字 */
static int parse_cn(const char *s, double *out) {
    double total = 0, num = -1; int any = 0; const char *p = s;
    unsigned cp; int len;
    while ((len = u8_next(p, &cp)) > 0 && *p) {
        int d = cn_digit(cp);
        if (d >= 0) { num = d; any = 1; p += len; continue; }
        if (cp == 0x5341) { total += (num < 0 ? 1 : num) * 10;  num = -1; any = 1; p += len; continue; }  /* 十 */
        if (cp == 0x767E) { total += (num < 0 ? 1 : num) * 100; num = -1; any = 1; p += len; continue; }  /* 百 */
        if (cp == 0x5343) { total += (num < 0 ? 1 : num) * 1000;num = -1; any = 1; p += len; continue; }  /* 千 */
        break;
    }
    if (!any) return 0;
    *out = total + (num < 0 ? 0 : num);
    return (int)(p - s);
}

typedef struct { double v; int kind; } RNum;   /* 0 普通 1 钱 2 百分比 3 数量 */
#define MAXRN 24
static RNum g_nums[MAXRN];
static int  g_nnum;
static double g_disc; static int g_hasdisc;
static char   g_input[4096];

static void collect_numbers(const char *s) {
    g_nnum = 0; g_hasdisc = 0; g_disc = 0;
    const char *p = s;
    unsigned cp; int len;
    while (*p && g_nnum < MAXRN) {
        if (*p >= '0' && *p <= '9') {
            char *end; double v = strtod(p, &end);
            const char *q = end;
            int kind = 0;
            if (*q == '%') { kind = 2; q++; }
            else if (((unsigned char)q[0] == 0xE5 && (unsigned char)q[1] == 0x85 && (unsigned char)q[2] == 0x83) ||  /* 元 */
                     ((unsigned char)q[0] == 0xE5 && (unsigned char)q[1] == 0x9D && (unsigned char)q[2] == 0x97)) { /* 块 */
                kind = 1; q += 3;
            } else {
                unsigned c2; int l2 = u8_next(q, &c2);
                if (c2 == 0x4E2A || c2 == 0x672C || c2 == 0x4EF6 || c2 == 0x652F ||
                    c2 == 0x7BB1 || c2 == 0x5343 || c2 == 0x7C73 || c2 == 0x65A4 || c2 == 0x5C0F)
                    kind = 3;
                (void)l2;
            }
            g_nums[g_nnum].v = v; g_nums[g_nnum].kind = kind; g_nnum++;
            p = end;
            continue;
        }
        /* 百分之 X ：字节序列 百(E7 99 BE) 分(E5 88 86) 之(E4 B9 8B) */
        if ((unsigned char)p[0] == 0xE7 && (unsigned char)p[1] == 0x99 && (unsigned char)p[2] == 0xBE &&
            (unsigned char)p[3] == 0xE5 && (unsigned char)p[4] == 0x88 && (unsigned char)p[5] == 0x86 &&
            (unsigned char)p[6] == 0xE4 && (unsigned char)p[7] == 0xB9 && (unsigned char)p[8] == 0x8B) {
            const char *q = p + 9;
            double v; int n = parse_cn(q, &v);
            if (n == 0) { char *e; v = strtod(q, &e); n = (int)(e - q); }
            if (n > 0 && g_nnum < MAXRN) {
                g_nums[g_nnum].v = v; g_nums[g_nnum].kind = 2; g_nnum++;
                p = q + n;
                continue;
            }
        }
        /* 打折：形如 八折 / 七五折 / 8折 / 8.5折 */
        len = u8_next(p, &cp);
        if (cp == 0x6298) {                       /* 折 */
            const char *b = u8_prev(s, p);
            int digits[4], nd = 0; double arab = -1;
            while (b >= s && nd < 4) {
                unsigned c3; u8_next(b, &c3);
                int d = cn_digit(c3);
                if (d < 0) break;
                digits[nd++] = d;                 /* 注意：这里是倒序收集 */
                if (b == s) break;
                b = u8_prev(s, b);
            }
            if (nd > 0) {
                double v;
                if (nd == 1) v = digits[0] / 10.0;            /* 八折 -> 0.8 */
                else { v = digits[1] * 10.0 + digits[0];      /* 七五折 -> 75 -> 0.75 */
                       v /= 100.0; }
                g_disc = v; g_hasdisc = 1;
            } else {
                const char *q = p;
                while (q > s && (q[-1] >= '0' && q[-1] <= '9')) q--;
                if (q < p) { arab = strtod(q, NULL); g_disc = (arab > 10 ? arab / 100.0 : arab / 10.0); g_hasdisc = 1; }
            }
            p += len;
            continue;
        }
        /* 汉字数字（只在后面跟单位时计入，避免误判） */
        {
            double v; int n = parse_cn(p, &v);
            if (n > 0) {
                unsigned c2; int l2 = u8_next(p + n, &c2);
                int kind = 0;
                if (c2 == 0x4E2A || c2 == 0x672C || c2 == 0x4EF6 || c2 == 0x652F ||
                    c2 == 0x7BB1 || c2 == 0x5343 || c2 == 0x7C73) kind = 3;
                if (kind == 3 && g_nnum < MAXRN) {
                    g_nums[g_nnum].v = v; g_nums[g_nnum].kind = kind; g_nnum++;
                }
                (void)l2;
                p += n;
                continue;
            }
        }
        p += len;
    }
}
static int has(const char *s, const char *kw) { return strstr(s, kw) != NULL; }
static double first_of(int kind, int *ok) {
    for (int i = 0; i < g_nnum; i++) if (g_nums[i].kind == kind) { *ok = 1; return g_nums[i].v; }
    *ok = 0; return 0;
}
static double first_any(int skip, int *ok) {
    for (int i = 0; i < g_nnum; i++) { if (skip-- > 0) continue; *ok = 1; return g_nums[i].v; }
    *ok = 0; return 0;
}
/* 最大的那个数（金额识别失败时用它兜底，通常就是价格） */
static double max_num(int *ok) {
    double m = -1;
    for (int i = 0; i < g_nnum; i++) if (g_nums[i].v > m) m = g_nums[i].v;
    *ok = (m >= 0);
    return m < 0 ? 0 : m;
}
static int emit(const char *kind, const char *expr, const char *note) {
    double v = eval_expr(expr);
    if (isnan(v)) return 0;
    repf("【题型】%s\n", kind);
    repf("【列式】%s = %.10g\n", expr, v);
    repf("【答案】%.10g\n", v);
    if (note && *note) repf("【依据】%s\n", note);
    repf("【核对】这一步是精确计算，你可以自己按计算器验证列式。\n");
    return 1;
}

static int try_rules(const char *s) {
    char expr[512], note[512];
    collect_numbers(s);
    int ok;

    /* 折扣题 */
    if (g_hasdisc) {
        double money = first_of(1, &ok);
        if (!ok) money = max_num(&ok);        /* 没识别到“元”，取最大的数当价格 */
        if (ok) {
            /* 先判断问的是哪一个：句子里出现“原价”不代表求现价，
               要看它是不是被问的对象（原价是多少 / 求原价）。 */
            int asks_orig = has(s, "原价是多少") || has(s, "原价多少") || has(s, "求原价") ||
                            has(s, "原价是几") || has(s, "原来的价格") || has(s, "原价多少元");
            int has_orig  = has(s, "原价") || has(s, "成本") || has(s, "进价") || has(s, "标价");
            int has_after = has(s, "折后") || has(s, "售价") || has(s, "现价") || has(s, "花了");
            int want_orig;
            if (asks_orig && has_after)      want_orig = 1;
            else if (has_orig && !asks_orig) want_orig = 0;
            else if (has_after)              want_orig = 1;
            else                             want_orig = -1;   /* 信息不足，猜一个并标注 */

            if (want_orig == 0) {
                snprintf(expr, sizeof expr, "%.10g*%.10g%%", money, g_disc * 100);
                snprintf(note, sizeof note, "原价 %.10g 元，折扣 %.4g%%，现价 = 原价 × 折扣", money, g_disc * 100);
                return emit("折扣 · 求现价", expr, note);
            }
            if (want_orig == 1) {
                snprintf(expr, sizeof expr, "%.10g/%.10g%%", money, g_disc * 100);
                snprintf(note, sizeof note, "折后价 %.10g 元，折扣 %.4g%%，原价 = 折后价 ÷ 折扣", money, g_disc * 100);
                return emit("折扣 · 求原价", expr, note);
            }
            snprintf(expr, sizeof expr, "%.10g*%.10g%%", money, g_disc * 100);
            snprintf(note, sizeof note, "题面没说是求原价还是现价，按「现价 = 原价 × 折扣」算；若 %.10g 其实是折后价，请改用除法", money);
            return emit("折扣 · 方向不确定", expr, note);
        }
    }
    /* 百分比增减 */
    {
        int okp = 0, okm = 0;
        double pc = first_of(2, &okp), base = first_of(1, &okm);
        if (okp && okm) {
            int down = has(s, "降价") || has(s, "减少") || has(s, "便宜") || has(s, "优惠") || has(s, "下调") || has(s, "降低");
            int up   = has(s, "上涨") || has(s, "提高") || has(s, "增加") || has(s, "上调") || has(s, "涨");
            if (down || up) {
                snprintf(expr, sizeof expr, "%.10g*(1%s%.10g%%)", base, down ? "-" : "+", pc);
                snprintf(note, sizeof note, "基数 %.10g，%s %.4g%%", base, down ? "下调" : "上调", pc);
                return emit(down ? "百分比 · 降价后" : "百分比 · 涨价后", expr, note);
            }
        }
    }
    /* 行程 */
    if ((has(s, "速度") || has(s, "每小时") || has(s, "行驶") || has(s, "开了")) && g_nnum >= 2) {
        snprintf(expr, sizeof expr, "%.10g*%.10g", g_nums[0].v, g_nums[1].v);
        snprintf(note, sizeof note, "速度 %.10g × 时间 %.10g", g_nums[0].v, g_nums[1].v);
        return emit("行程 · 求路程", expr, note);
    }
    /* 平均 */
    if (has(s, "平均") && g_nnum >= 2) {
        int n = 0; double sum = 0;
        for (int i = 0; i < g_nnum; i++) { sum += g_nums[i].v; n++; }
        snprintf(expr, sizeof expr, "(%.10g", g_nums[0].v);
        for (int i = 1; i < g_nnum; i++) { char t[64]; snprintf(t, sizeof t, "+%.10g", g_nums[i].v); strncat(expr, t, sizeof expr - strlen(expr) - 1); }
        { char t[64]; snprintf(t, sizeof t, ")/%d", n); strncat(expr, t, sizeof expr - strlen(expr) - 1); }
        snprintf(note, sizeof note, "%d 个数的平均值", n);
        return emit("平均数", expr, note);
    }
    /* 求剩余 */
    if ((has(s, "还剩") || has(s, "剩下") || has(s, "剩余") || has(s, "吃了") || has(s, "用了") || has(s, "卖出")) && g_nnum >= 2) {
        snprintf(expr, sizeof expr, "%.10g", g_nums[0].v);
        for (int i = 1; i < g_nnum; i++) { char t[64]; snprintf(t, sizeof t, "-%.10g", g_nums[i].v); strncat(expr, t, sizeof expr - strlen(expr) - 1); }
        snprintf(note, sizeof note, "总数 %.10g 依次减去其余", g_nums[0].v);
        return emit("求剩余", expr, note);
    }
    /* 求和 */
    if ((has(s, "共") || has(s, "一共") || has(s, "总共") || has(s, "合计") || has(s, "总和")) && g_nnum >= 2) {
        snprintf(expr, sizeof expr, "%.10g", g_nums[0].v);
        for (int i = 1; i < g_nnum; i++) { char t[64]; snprintf(t, sizeof t, "+%.10g", g_nums[i].v); strncat(expr, t, sizeof expr - strlen(expr) - 1); }
        snprintf(note, sizeof note, "%d 个数相加", g_nnum);
        return emit("求和", expr, note);
    }
    /* 单价 × 数量 */
    {
        int okm = 0, okc = 0;
        double price = first_of(1, &okm), cnt = first_of(3, &okc);
        if (okm && okc && (has(s, "每") || has(s, "单价") || has(s, "买") || has(s, "一共"))) {
            snprintf(expr, sizeof expr, "%.10g*%.10g", price, cnt);
            snprintf(note, sizeof note, "单价 %.10g × 数量 %.10g", price, cnt);
            return emit("总价", expr, note);
        }
    }
    return 0;
}

/* ====================== 闲聊应答（中文寒暄，话多一点）===================== */
static unsigned g_rr = 0;
static const char *pick_reply(const char *choices[], int n) {
    g_rr = g_rr * 1103515245u + 12345u;     /* 简单伪随机，让每次回答不一样 */
    return choices[g_rr % n];
}

static int chat_reply(const char *buf) {
    static const char *greet[] = {
        "你好！今天过得怎么样？有什么想聊的都可以说，学习、生活、还是随便扯几句，我都陪你。",
        "嗨！很高兴见到你。想聊点什么？开心的、烦恼的，或者考我几道数学题都行。",
        "你好呀！我一直在。说说看，今天想聊什么？",
        "在的！随时都在。你今天心情怎么样？",
    };
    static const char *intro[] = {
        "我是你机器上的 AI 助手，代码全部用 C 语言写成，聊天模型是这台电脑自己训练出来的。你可以叫我小助手。",
        "我叫小助手。我会聊天、会算算术、会解方程、还会解应用题。想试试哪样？",
    };
    static const char *can[] = {
        "我会这些：①算算式，比如 12+15*3；②解方程，比如 2x+3=7；③应用题，比如“原价200元打八折多少钱”；④随便聊天。你试试？",
    };
    static const char *thanks[] = {
        "不客气！能帮上忙我就开心。还有别的想聊的吗？",
        "客气啦！有事随时喊我。",
    };
    static const char *bye[] = {
        "再见！早点休息，明天见。记得有题不会随时来找我。",
        "拜拜！和你聊天很开心，期待下次。",
        "晚安！祝你做个好梦，明天元气满满。",
    };
    static const char *happy[] = {
        "开心就好呀！是什么好事，说给我听听？快乐的事情分享出来会翻倍。",
        "看你开心我也跟着高兴！今天遇到什么好事了？",
        "真不错！好心情要记下来，以后难过的时候翻出来看看。",
    };
    static const char *sad[] = {
        "抱抱你。怎么了，愿意说说吗？说出来心里会好受一点，我听着。",
        "难过的时候别一个人憋着。跟我说说发生了什么事？",
        "每个人都会有低谷，这不代表你不好。深呼吸，我陪你聊一会儿。",
    };
    static const char *tired[] = {
        "累了就休息一下吧，别硬撑。喝口水、伸个懒腰，过一会儿就好了。",
        "辛苦啦！今天一定忙坏了吧。早点休息，身体要紧。",
        "累说明你在认真生活。休息不是偷懒，是充电。",
    };
    static const char *bored[] = {
        "无聊的话我们来玩个游戏：你出一道算术题考我，或者让我讲个笑话，选一个？",
        "无聊的时候最适合学点新东西了。要不要我出道题给你解解闷？",
        "那我讲个笑话吧：0见到8说，兄弟你这腰带不错啊！8说，最近瘦了。",
    };
    static const char *angry[] = {
        "消消气，生气伤身体。是什么事把你气着了？说来听听。",
        "先深呼吸三次。气头上别做决定，等心情平一点我们再聊。",
        "我理解你的不爽。要不把烦心事说给我，我帮你分析分析？",
    };
    static const char *scared[] = {
        "紧张的时候就做几次深呼吸：吸气四秒，呼气六秒，很管用。",
        "害怕是正常的，说明你在乎这件事。把大目标拆成小步骤，一小步一小步来。",
        "别怕，我陪你。先说说你在担心什么？",
    };
    static const char *weather[] = {
        "我在屋里看不见窗外，不过你可以拉开窗帘看看。晴天就出门走走，心情会很好。",
        "不管外面什么天气，记得照顾好自己：天冷加衣，天热喝水，下雨带伞。",
        "天气好不好，心情都可以好。今天打算出门吗？",
    };
    static const char *food[] = {
        "我不吃饭，我靠电活着哈哈。你饿了吗？去吃点热乎的吧，按时吃饭很重要。",
        "饿了就去吃！米饭配两个菜，再来点汤，吃饱了才有力气聊天和做题。",
        "说到吃的，你最喜欢吃什么菜？",
    };
    static const char *study[] = {
        "作业多就拆开来做，先做最难的，剩下就轻松了。哪一科最头疼？应用题可以问我。",
        "考试难是正常的。考完别光看分数，看看错在哪，那才是收获。",
        "一次考砸不算什么，把错题弄明白下次就上去了。哪道题不会？拿出来我看看。",
        "学习确实累，但每天进步一点点就很好。休息五分钟再继续，我陪着你。",
    };
    static const char *hobby[] = {
        "我喜欢和大家聊天，也喜欢帮忙解题。你的爱好是什么？运动、音乐还是别的？",
        "我最喜欢的运动是脑力劳动哈哈。你平时喜欢做什么？",
        "看书我擅长，特别是数学书。你最近在听什么歌、看什么书？",
    };
    static const char *dream[] = {
        "有梦想的人眼里有光。你的梦想是什么？说给我听听。",
        "梦想再大也要从今天的小事做起。先定一个小目标，明天就开始。",
        "未来是由今天的你决定的。别急，一步一步来。",
    };
    static const char *family[] = {
        "家人是最支持你的人。想他们了就打个电话，聊聊今天发生的事。",
        "妈妈的唠叨里藏着爱，爸爸的沉默里也有。多陪陪他们。",
    };
    static const char *friend_[] = {
        "好朋友是生活的充电宝。今天和谁一起玩了吗？",
        "和朋友闹别扭的话，主动说一句“我们聊聊”，很多误会就解开了。",
    };
    static const char *cheer[] = {
        "加油！你已经比昨天的自己更厉害了。撑不住就歇一会儿，我在。",
        "别放弃，再坚持一下下。把大目标切成小步，先走完今天这一小步。",
        "我相信你可以。需要帮忙算题、还是需要一句鼓励，我都给。",
    };
    static const char *phil[] = {
        "这个问题很深。我的看法是：意义不是找到的，是做出来的。你今天帮一个人、学会一件事，意义就多了一点。",
        "人生就像做题：过程比答案重要，方法比分数重要。",
    };
    static const char *laugh[] = {
        "哈哈，能逗你开心就好！要不要再来一个？",
        "嘿嘿，我肚子里笑话可多了，还听吗？",
    };
    static const char *shortq[] = {
        "嗯嗯，我在听。想聊什么继续说。",
        "是呀是呀。然后呢？我听着呢。",
        "哈哈。你还有别的想聊的吗？",
    };

    if (has(buf, "你好") || has(buf, "您好") || has(buf, "在吗") || has(buf, "hi") || has(buf, "hello") || has(buf, "嗨"))
        { repf("%s\n", pick_reply(greet, 4)); return 1; }
    if (has(buf, "你是谁") || has(buf, "你叫什么") || has(buf, "介绍一下"))
        { repf("%s\n", pick_reply(intro, 2)); return 1; }
    if (has(buf, "你会什么") || has(buf, "能干什么") || has(buf, "帮助") || has(buf, "怎么用") || has(buf, "help"))
        { repf("%s\n", can[0]); return 1; }
    if (has(buf, "谢谢") || has(buf, "感谢") || has(buf, "辛苦了"))
        { repf("%s\n", pick_reply(thanks, 2)); return 1; }
    if (has(buf, "再见") || has(buf, "拜拜") || has(buf, "晚安") || has(buf, "下次"))
        { repf("%s\n", pick_reply(bye, 3)); return 1; }
    if (has(buf, "时间") || has(buf, "几点")) {
        time_t t = time(NULL);
        struct tm *tm = localtime(&t);
        repf("现在是 %04d-%02d-%02d %02d:%02d。\n", tm->tm_year + 1900, tm->tm_mon + 1,
               tm->tm_mday, tm->tm_hour, tm->tm_min);
        return 1;
    }
    if (has(buf, "名字")) { repf("你可以叫我小助手。\n"); return 1; }
    if (has(buf, "开心") || has(buf, "高兴") || has(buf, "兴奋") || has(buf, "太棒"))
        { repf("%s\n", pick_reply(happy, 3)); return 1; }
    if (has(buf, "难过") || has(buf, "伤心") || has(buf, "哭") || has(buf, "委屈") || has(buf, "心情不好"))
        { repf("%s\n", pick_reply(sad, 3)); return 1; }
    if (has(buf, "累") || has(buf, "困") || has(buf, "疲惫"))
        { repf("%s\n", pick_reply(tired, 3)); return 1; }
    if (has(buf, "无聊") || has(buf, "没意思"))
        { repf("%s\n", pick_reply(bored, 3)); return 1; }
    if (has(buf, "烦") || has(buf, "生气") || has(buf, "气死") || has(buf, "讨厌"))
        { repf("%s\n", pick_reply(angry, 3)); return 1; }
    if (has(buf, "害怕") || has(buf, "紧张") || has(buf, "担心"))
        { repf("%s\n", pick_reply(scared, 3)); return 1; }
    if (has(buf, "天气") || has(buf, "下雨") || has(buf, "晴天") || has(buf, "热") || has(buf, "冷"))
        { repf("%s\n", pick_reply(weather, 3)); return 1; }
    if (has(buf, "吃饭") || has(buf, "饿") || has(buf, "吃什么"))
        { repf("%s\n", pick_reply(food, 3)); return 1; }
    if (has(buf, "作业") || has(buf, "考试") || has(buf, "学习") || has(buf, "数学") || has(buf, "考"))
        { repf("%s\n", pick_reply(study, 4)); return 1; }
    if (has(buf, "爱好") || has(buf, "喜欢") || has(buf, "唱歌") || has(buf, "画画") || has(buf, "运动") || has(buf, "游戏"))
        { repf("%s\n", pick_reply(hobby, 3)); return 1; }
    if (has(buf, "梦想") || has(buf, "未来") || has(buf, "长大"))
        { repf("%s\n", pick_reply(dream, 3)); return 1; }
    if (has(buf, "妈妈") || has(buf, "爸爸") || has(buf, "家人") || has(buf, "家庭"))
        { repf("%s\n", pick_reply(family, 2)); return 1; }
    if (has(buf, "朋友") || has(buf, "同学"))
        { repf("%s\n", pick_reply(friend_, 2)); return 1; }
    if (has(buf, "加油") || has(buf, "放弃") || has(buf, "撑不住") || has(buf, "坚持"))
        { repf("%s\n", pick_reply(cheer, 3)); return 1; }
    if (has(buf, "意义") || has(buf, "人生") || has(buf, "为什么活着"))
        { repf("%s\n", pick_reply(phil, 2)); return 1; }
    if (has(buf, "哈哈") || has(buf, "好笑") || has(buf, "逗"))
        { repf("%s\n", pick_reply(laugh, 2)); return 1; }
    if (has(buf, "厉害") || has(buf, "聪明") || has(buf, "棒"))
        { repf("谢谢夸奖！我只是把计算交给精确计算器、把题目交给题库，不装懂。\n"); return 1; }
    if (strlen(buf) <= 6) { repf("%s\n", pick_reply(shortq, 3)); return 1; }
    return 0;
}


/* ====================== 回复缓冲与统一应答 ================================ */
#include <stdarg.h>
static char RB[16384];
static size_t RL;

static void rep(const char *s) {
    size_t l = strlen(s);
    if (RL + l < sizeof RB - 1) { memcpy(RB + RL, s, l); RL += l; RB[RL] = 0; }
}
static void repf(const char *fmt, ...) {
    char tmp[2048];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(tmp, sizeof tmp, fmt, ap);
    va_end(ap);
    rep(tmp);
}

static int is_arith_s(const char *s) {
    int digits = 0;
    for (; *s; s++) {
        if (isdigit((unsigned char)*s)) { digits = 1; continue; }
        if (strchr("+-*/^%(). \t", *s)) continue;
        return 0;
    }
    return digits;
}

/* 会话记忆：只对神经网络部分生效 */
static char session[8192];
static size_t sess_len;

static void sess_append(const char *s) {
    size_t l = strlen(s);
    if (sess_len + l > sizeof session - 1) { sess_len = 0; }
    memcpy(session + sess_len, s, l);
    sess_len += l;
    session[sess_len] = 0;
}

static void answer_q(const char *q, char *out, size_t cap) {
    RL = 0; RB[0] = 0;
    if (chat_reply(q)) { snprintf(out, cap, "%s", RB); return; }
    if (is_arith_s(q)) {
        double v = eval_expr(q);
        if (!isnan(v)) {
            snprintf(out, cap, "%s = %.10g\n（精确计算结果，可自行验证。）", q, v);
            return;
        }
    }
    if (strchr(q, '=') && (strchr(q, 'x') || strchr(q, 'X'))) {
        double x; char why[512];
        if (solve_linear(q, &x, why, sizeof why)) {
            snprintf(out, cap, "x = %.6g\n%s", x, why);
            return;
        }
    }
    if (try_rules(q)) { snprintf(out, cap, "%s", RB); return; }

    sess_append("### User: ");
    sess_append(q);
    sess_append("\n### Assistant:");
    size_t keep = sess_len < 2000 ? sess_len : 2000;
    const char *ctx_start = session + (sess_len - keep);
    char tmp[4096];
    gen_text(ctx_start, tmp, 220, 0.5f);
    char *hash = strstr(tmp, "###");
    if (hash) *hash = 0;
    /* 输出质检：必须能读（合法 UTF-8 且含中文），否则退回固定话术 */
    int cn = 0;
    for (const char *p = tmp; *p; p++) if ((unsigned char)*p >= 0x80) cn++;
    if (!looks_utf8(tmp) || cn < 6 || tmp[0] == 0) {
        snprintf(out, cap, "这个话题我还在学。要不考我一道数学题，或者让我讲个笑话？");
        return;
    }
    sess_append(tmp);
    sess_append("\n");
    snprintf(out, cap, "%s", tmp);
}


#include <stdio.h>

int main(void) {
#ifdef _WIN32
    SetConsoleOutputCP(65001);
#endif
    if (load_corpus("zhchat_corpus.txt") != 0) return 1;
    BT = B * T;
    init_params();
    alloc_activations();
    if (load_weights("zhchat.bin") != 0) return 1;
    char out[8192];
    const char *qs[] = {"你好", "讲个笑话", "再见", "谢谢", "我有点难过",
                        "12+15*3", "一件衣服原价200元，打八折后需要多少钱？", "2x+3=7"};
    for (int i = 0; i < 8; i++) {
        printf("\nQ: %s\nA: ", qs[i]);
        fflush(stdout);
        answer_q(qs[i], out, sizeof out);
        printf("%s\n", out);
        fflush(stdout);
    }
    printf("\n全部完成\n");
    return 0;
}

