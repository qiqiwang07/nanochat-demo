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
typedef double real;
#define EXP exp
#define SQRT sqrt
#define LOG log
#define COS cos


/* ------------------------------ 超参数 ---------------------------------- */
#define NLAYER   2
#define NEMBD    64
#define NHEAD    4
#define MLP      256
#define VOCAB    96          /* 字符级词表：语料中最高频的 96 种字节 */
#define HD       (NEMBD / NHEAD)
#define RMS_EPS  1e-5f

static int B = 32;           /* batch */
static int T = 64;           /* 上下文长度 */
static int BT;               /* B*T */

/* ------------------------------ 参数表 ---------------------------------- */
typedef struct {
    const char *name;
    int n;
    real *p, *g, *m, *v;    /* 数值 / 梯度 / AdamW 一阶、二阶动量 */
} Param;

static Param params[40];
static int   nparams = 0;

static real *falloc(int n) {
    real *p = (real *)calloc((size_t)n, sizeof(real));
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
static real frand(void) { return (real)(xrand() >> 8) * (1.0f / 16777216.0f); }
static real nrand(void) {
    real u1 = frand() + 1e-7f, u2 = frand();
    return SQRT(-2.0f * LOG(u1)) * COS(6.28318530718f * u2);
}

/* ------------------------------ 矩阵乘法（累加语义）--------------------
 * 权重统一按 [in][out] 行主序存放。
 *   mm_nn: C[M,N] += A[M,K] @ B[K,N]            (B 为 [in][out])
 *   mm_nt: C[M,N] += A[M,K] @ B[N,K]^T          (反传 dx)
 *   mm_tn: C[K,N] += A[M,K]^T @ B[M,N]          (反传 dW)                     */
#define PARFOR _Pragma("omp parallel for")
static void mm_nn(const real *A, const real *Bm, real *C, int M, int K, int N) {
#ifdef _OPENMP
#pragma omp parallel for
#endif
    for (int i = 0; i < M; i++) {
        real *crow = C + (size_t)i * N;
        for (int k = 0; k < K; k++) {
            real a = A[(size_t)i * K + k];
            if (a == 0.0f) continue;
            const real *brow = Bm + (size_t)k * N;
            for (int j = 0; j < N; j++) crow[j] += a * brow[j];
        }
    }
}
static void mm_nt(const real *A, const real *Bm, real *C, int M, int K, int N) {
#ifdef _OPENMP
#pragma omp parallel for
#endif
    for (int i = 0; i < M; i++) {
        const real *arow = A + (size_t)i * K;
        real *crow = C + (size_t)i * N;
        for (int n = 0; n < N; n++) {
            const real *brow = Bm + (size_t)n * K;
            real s = 0.0f;
            for (int k = 0; k < K; k++) s += arow[k] * brow[k];
            crow[n] += s;
        }
    }
}
static void mm_tn(const real *A, const real *Bm, real *C, int M, int K, int N) {
    for (int i = 0; i < M; i++) {
        const real *arow = A + (size_t)i * K;
        const real *brow = Bm + (size_t)i * N;
        for (int k = 0; k < K; k++) {
            real a = arow[k];
            real *crow = C + (size_t)k * N;
            for (int j = 0; j < N; j++) crow[j] += a * brow[j];
        }
    }
}

/* ------------------------------ 参数 ------------------------------------ */
static Param *p_tok, *p_pos, *p_lm, *b_lm;
static Param *Wqkv[NLAYER], *b_qkv[NLAYER], *Wo[NLAYER], *b_o[NLAYER];
static Param *W1[NLAYER], *b_1[NLAYER], *W2[NLAYER], *b_2[NLAYER];

/* ------------------------------ 激活缓存（每层独立！）------------------- */
static real *h_emb;                    /* 嵌入，即第 0 层输入 */
static real *h_inv1[NLAYER], *h_ln1[NLAYER], *h_qkv[NLAYER], *h_att[NLAYER];
static real *h_ao[NLAYER], *h_x1[NLAYER], *h_inv2[NLAYER], *h_ln2[NLAYER];
static real *h_pre[NLAYER], *h_act[NLAYER], *h_h2[NLAYER], *h_x2[NLAYER];
static real *h_invf, *h_xf, *h_logits;

static real *g_xin[NLAYER], *g_ln1[NLAYER], *g_qkv[NLAYER], *g_ao[NLAYER];
static real *g_ln2[NLAYER], *g_pre[NLAYER], *g_act[NLAYER], *g_xout[NLAYER];
static real *g_xf, *g_logits, *g_scratch;

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
        memset(params[i].g, 0, (size_t)params[i].n * sizeof(real));
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
        if (is_bias(q->name)) { memset(q->p, 0, (size_t)q->n * sizeof(real)); continue; }
        real scale = strcmp(q->name, "lm_head") == 0 ? 0.001f : 0.02f;
        for (int j = 0; j < q->n; j++) q->p[j] = scale * nrand();
    }
    printf("参数张量 %d 个，参数总量 %ld (%.3fM)\n", nparams, total, total / 1e6);
}

/* ------------------------------ RMSNorm -------------------------------- */
static void rmsnorm_fwd(const real *x, real *out, real *inv_out, int rows) {
    for (int r = 0; r < rows; r++) {
        const real *xr = x + (size_t)r * NEMBD;
        real ss = 0.0f;
        for (int c = 0; c < NEMBD; c++) ss += xr[c] * xr[c];
        real inv = 1.0f / SQRT(ss / NEMBD + RMS_EPS);
        inv_out[r] = inv;
        real *orow = out + (size_t)r * NEMBD;
        for (int c = 0; c < NEMBD; c++) orow[c] = xr[c] * inv;
    }
}
static void rmsnorm_bwd(const real *x, const real *inv, const real *dy,
                        real *dx, int rows) {
    for (int r = 0; r < rows; r++) {
        const real *xr = x + (size_t)r * NEMBD;
        const real *dr = dy + (size_t)r * NEMBD;
        real *dxr = dx + (size_t)r * NEMBD;
        real g = inv[r], s = 0.0f;
        for (int c = 0; c < NEMBD; c++) s += dr[c] * xr[c];
        real k = g * g * g * s / NEMBD;
        for (int c = 0; c < NEMBD; c++) dxr[c] += g * dr[c] - k * xr[c];
    }
}

/* ------------------------------ 前向传播 -------------------------------- */
static void forward(void) {
    /* 嵌入 */
    for (int i = 0; i < BT; i++) {
        int tok = xs[i], t = i % T;
        const real *te = p_tok->p + (size_t)tok * NEMBD;
        const real *pe = p_pos->p + (size_t)t * NEMBD;
        real *o = h_emb + (size_t)i * NEMBD;
        for (int c = 0; c < NEMBD; c++) o[c] = te[c] + pe[c];
    }

    const real *x_in = h_emb;
    for (int l = 0; l < NLAYER; l++) {
        /* ---- 注意力子层 ---- */
        rmsnorm_fwd(x_in, h_ln1[l], h_inv1[l], BT);
        memset(h_qkv[l], 0, (size_t)BT * 3 * NEMBD * sizeof(real));
        mm_nn(h_ln1[l], Wqkv[l]->p, h_qkv[l], BT, NEMBD, 3 * NEMBD);
        for (int i = 0; i < BT; i++) {
            real *q = h_qkv[l] + (size_t)i * 3 * NEMBD;
            for (int c = 0; c < 3 * NEMBD; c++) q[c] += b_qkv[l]->p[c];
        }

        real scale = 1.0f / SQRT((real)HD);
#ifdef _OPENMP
#pragma omp parallel for collapse(2)
#endif
        for (int b = 0; b < B; b++) {
            for (int h = 0; h < NHEAD; h++) {
                int hoff = h * HD;
                for (int t = 0; t < T; t++) {
                    const real *q = h_qkv[l] + ((size_t)(b * T + t) * 3 * NEMBD) + hoff;
                    real *att = h_att[l] + (((size_t)b * NHEAD + h) * T + t) * T;
                    real maxs = -1e30f;
                    for (int u = 0; u <= t; u++) {
                        const real *k = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + NEMBD + hoff;
                        real s = 0.0f;
                        for (int d = 0; d < HD; d++) s += q[d] * k[d];
                        s *= scale;
                        att[u] = s;
                        if (s > maxs) maxs = s;
                    }
                    real sum = 0.0f;
                    for (int u = 0; u <= t; u++) { att[u] = EXP(att[u] - maxs); sum += att[u]; }
                    real inv = 1.0f / sum;
                    for (int u = 0; u <= t; u++) att[u] *= inv;

                    real *ao = h_ao[l] + (size_t)(b * T + t) * NEMBD + hoff;
                    for (int d = 0; d < HD; d++) ao[d] = 0.0f;
                    for (int u = 0; u <= t; u++) {
                        const real *v = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + 2 * NEMBD + hoff;
                        real a = att[u];
                        for (int d = 0; d < HD; d++) ao[d] += a * v[d];
                    }
                }
            }
        }

        memset(g_scratch, 0, (size_t)BT * NEMBD * sizeof(real));   /* 复用为投影输出 */
        mm_nn(h_ao[l], Wo[l]->p, g_scratch, BT, NEMBD, NEMBD);
        for (int i = 0; i < BT; i++) {
            const real *xi = x_in + (size_t)i * NEMBD;
            const real *ao = g_scratch + (size_t)i * NEMBD;
            real *x1 = h_x1[l] + (size_t)i * NEMBD;
            for (int c = 0; c < NEMBD; c++) x1[c] = xi[c] + ao[c] + b_o[l]->p[c];
        }

        /* ---- 前馈子层 ---- */
        rmsnorm_fwd(h_x1[l], h_ln2[l], h_inv2[l], BT);
        memset(h_pre[l], 0, (size_t)BT * MLP * sizeof(real));
        mm_nn(h_ln2[l], W1[l]->p, h_pre[l], BT, NEMBD, MLP);
        for (int i = 0; i < BT; i++) {
            real *pr = h_pre[l] + (size_t)i * MLP;
            real *ac = h_act[l] + (size_t)i * MLP;
            for (int j = 0; j < MLP; j++) {
                real v = pr[j] + b_1[l]->p[j];
                pr[j] = v;
                ac[j] = v > 0.0f ? v : 0.0f;          /* ReLU */
            }
        }
        memset(h_h2[l], 0, (size_t)BT * NEMBD * sizeof(real));
        mm_nn(h_act[l], W2[l]->p, h_h2[l], BT, MLP, NEMBD);
        for (int i = 0; i < BT; i++) {
            const real *x1 = h_x1[l] + (size_t)i * NEMBD;
            const real *hh = h_h2[l] + (size_t)i * NEMBD;
            real *x2 = h_x2[l] + (size_t)i * NEMBD;
            for (int c = 0; c < NEMBD; c++) x2[c] = x1[c] + hh[c] + b_2[l]->p[c];
        }
        x_in = h_x2[l];                                /* 本层输出 = 下一层输入 */
    }

    /* ---- 输出层 ---- */
    rmsnorm_fwd(x_in, h_xf, h_invf, BT);
    memset(h_logits, 0, (size_t)BT * VOCAB * sizeof(real));
    mm_nn(h_xf, p_lm->p, h_logits, BT, NEMBD, VOCAB);
    for (int i = 0; i < BT; i++)
        for (int v = 0; v < VOCAB; v++) h_logits[(size_t)i * VOCAB + v] += b_lm->p[v];
}

/* softmax + 交叉熵，并把 dL/dlogits 写进 g_logits */
static real loss_and_grad(void) {
    real loss = 0.0f, scale = 1.0f / (real)BT;
    for (int i = 0; i < BT; i++) {
        real *lg = h_logits + (size_t)i * VOCAB;
        real maxl = lg[0];
        for (int v = 1; v < VOCAB; v++) if (lg[v] > maxl) maxl = lg[v];
        real sum = 0.0f;
        for (int v = 0; v < VOCAB; v++) { lg[v] = EXP(lg[v] - maxl); sum += lg[v]; }
        real inv = 1.0f / sum;
        for (int v = 0; v < VOCAB; v++) lg[v] *= inv;
        int target = ys[i];
        loss += -LOG(lg[target] + 1e-9f);
        real *dl = g_logits + (size_t)i * VOCAB;
        for (int v = 0; v < VOCAB; v++) dl[v] = (lg[v] - (v == target ? 1.0f : 0.0f)) * scale;
    }
    return loss * scale;
}

/* ------------------------------ 反向传播 -------------------------------- */
static void backward(void) {
    memset(g_xf, 0, (size_t)BT * NEMBD * sizeof(real));
    mm_nt(g_logits, p_lm->p, g_xf, BT, VOCAB, NEMBD);              /* dxf   */
    mm_tn(h_xf, g_logits, p_lm->g, BT, NEMBD, VOCAB);              /* dW_lm */
    for (int i = 0; i < BT; i++)
        for (int v = 0; v < VOCAB; v++) b_lm->g[v] += g_logits[(size_t)i * VOCAB + v];

    real *d_out = g_scratch;                                       /* 上一层输出梯度 */
    memset(g_xout[NLAYER - 1], 0, (size_t)BT * NEMBD * sizeof(real));
    rmsnorm_bwd(h_x2[NLAYER - 1], h_invf, g_xf, g_xout[NLAYER - 1], BT);
    memcpy(d_out, g_xout[NLAYER - 1], (size_t)BT * NEMBD * sizeof(real));

    for (int l = NLAYER - 1; l >= 0; l--) {
        const real *x_in = (l == 0) ? h_emb : h_x2[l - 1];

        /* ---- 前馈子层反向 ---- */
        memset(g_xin[l], 0, (size_t)BT * NEMBD * sizeof(real));
        memcpy(g_xin[l], d_out, (size_t)BT * NEMBD * sizeof(real));   /* 恒等支路 → x1 */
        for (int i = 0; i < BT; i++)
            for (int c = 0; c < NEMBD; c++) b_2[l]->g[c] += d_out[(size_t)i * NEMBD + c];

        memset(g_act[l], 0, (size_t)BT * MLP * sizeof(real));
        mm_nt(d_out, W2[l]->p, g_act[l], BT, NEMBD, MLP);              /* d act */
        mm_tn(h_act[l], d_out, W2[l]->g, BT, MLP, NEMBD);              /* dW2   */

        for (int i = 0; i < BT; i++) {
            const real *pr = h_pre[l] + (size_t)i * MLP;
            const real *ga = g_act[l] + (size_t)i * MLP;
            real *gp = g_pre[l] + (size_t)i * MLP;
            for (int j = 0; j < MLP; j++) gp[j] = pr[j] > 0.0f ? ga[j] : 0.0f;  /* ReLU' */
        }
        memset(g_ln2[l], 0, (size_t)BT * NEMBD * sizeof(real));
        mm_nt(g_pre[l], W1[l]->p, g_ln2[l], BT, MLP, NEMBD);           /* d ln2 */
        mm_tn(h_ln2[l], g_pre[l], W1[l]->g, BT, NEMBD, MLP);           /* dW1   */
        for (int i = 0; i < BT; i++)
            for (int j = 0; j < MLP; j++) b_1[l]->g[j] += g_pre[l][(size_t)i * MLP + j];
        rmsnorm_bwd(h_x1[l], h_inv2[l], g_ln2[l], g_xin[l], BT);       /* → x1 */

        /* ---- 注意力子层反向 ---- */
        memset(g_ao[l], 0, (size_t)BT * NEMBD * sizeof(real));
        memcpy(g_ao[l], g_xin[l], (size_t)BT * NEMBD * sizeof(real)); /* 恒等支路 → x_in */
        for (int i = 0; i < BT; i++)
            for (int c = 0; c < NEMBD; c++) b_o[l]->g[c] += g_ao[l][(size_t)i * NEMBD + c];

        memset(g_ln1[l], 0, (size_t)BT * NEMBD * sizeof(real));       /* 暂存 d(ao投影前) */
        mm_nt(g_ao[l], Wo[l]->p, g_ln1[l], BT, NEMBD, NEMBD);          /* d ao  */
        mm_tn(h_ao[l], g_ao[l], Wo[l]->g, BT, NEMBD, NEMBD);           /* dWo   */

        const real *dao = g_ln1[l];
        memset(g_qkv[l], 0, (size_t)BT * 3 * NEMBD * sizeof(real));
        real scale = 1.0f / SQRT((real)HD);
#ifdef _OPENMP
#pragma omp parallel for collapse(2)
#endif
        for (int b = 0; b < B; b++) {
            for (int h = 0; h < NHEAD; h++) {
                int hoff = h * HD;
                real datt[8192];
                for (int t = 0; t < T; t++) {
                    const real *att = h_att[l] + (((size_t)b * NHEAD + h) * T + t) * T;
                    const real *do_ = dao + (size_t)(b * T + t) * NEMBD + hoff;
                    real *dq = g_qkv[l] + ((size_t)(b * T + t) * 3 * NEMBD) + hoff;
                    real dsum = 0.0f;
                    for (int u = 0; u <= t; u++) {
                        const real *v = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + 2 * NEMBD + hoff;
                        real s = 0.0f;
                        for (int d = 0; d < HD; d++) s += do_[d] * v[d];
                        datt[u] = s;
                        dsum += s * att[u];
                    }
                    for (int d = 0; d < HD; d++) dq[d] = 0.0f;
                    for (int u = 0; u <= t; u++) {
                        real ds = att[u] * (datt[u] - dsum);          /* softmax 反向 */
                        const real *v  = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + 2 * NEMBD + hoff;
                        real *dv = g_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + 2 * NEMBD + hoff;
                        for (int d = 0; d < HD; d++) dv[d] += att[u] * do_[d];
                        const real *q = h_qkv[l] + ((size_t)(b * T + t) * 3 * NEMBD) + hoff;
                        const real *k = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + NEMBD + hoff;
                        real *dk = g_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + NEMBD + hoff;
                        for (int d = 0; d < HD; d++) {
                            dq[d] += ds * k[d] * scale;
                            dk[d] += ds * q[d] * scale;
                        }
                    }
                }
            }
        }

        memset(g_ln1[l], 0, (size_t)BT * NEMBD * sizeof(real));
        mm_nt(g_qkv[l], Wqkv[l]->p, g_ln1[l], BT, 3 * NEMBD, NEMBD);    /* d ln1  */
        mm_tn(h_ln1[l], g_qkv[l], Wqkv[l]->g, BT, NEMBD, 3 * NEMBD);    /* dWqkv  */
        for (int i = 0; i < BT; i++)
            for (int c = 0; c < 3 * NEMBD; c++) b_qkv[l]->g[c] += g_qkv[l][(size_t)i * 3 * NEMBD + c];

        /* g_xin[l] 此刻已经是完整的 dL/dx1(= dL/d attn投影 也等于恒等支路对 x_in 的贡献)，
           再补上经过 RMSNorm1 的那条支路，就得到 dL/d(x_in) */
        rmsnorm_bwd(x_in, h_inv1[l], g_ln1[l], g_xin[l], BT);

        memcpy(d_out, g_xin[l], (size_t)BT * NEMBD * sizeof(real));
    }

    /* 嵌入梯度 */
    for (int i = 0; i < BT; i++) {
        int tok = xs[i], t = i % T;
        const real *d = d_out + (size_t)i * NEMBD;
        for (int c = 0; c < NEMBD; c++) {
            p_tok->g[(size_t)tok * NEMBD + c] += d[c];
            p_pos->g[(size_t)t * NEMBD + c]   += d[c];
        }
    }
}

/* ------------------------------ AdamW ---------------------------------- */
static real grad_norm(void) {
    double s = 0.0;
    for (int i = 0; i < nparams; i++)
        for (int j = 0; j < params[i].n; j++)
            s += (double)params[i].g[j] * params[i].g[j];
    return (real)sqrt(s);
}
static void adamw_step(real lr, int step) {
    real b1 = 0.9f, b2 = 0.95f, eps = 1e-8f, wd = 0.01f;
    real bc1 = 1.0f - powf(b1, (real)step);
    real bc2 = 1.0f - powf(b2, (real)step);
    real gn = grad_norm();
    real clip = gn > 1.0f ? 1.0f / gn : 1.0f;      /* 全局梯度裁剪 */
    for (int i = 0; i < nparams; i++) {
        Param *q = &params[i];
        for (int j = 0; j < q->n; j++) {
            real g = q->g[j] * clip;
            q->m[j] = b1 * q->m[j] + (1 - b1) * g;
            q->v[j] = b2 * q->v[j] + (1 - b2) * g * g;
            real mh = q->m[j] / bc1, vh = q->v[j] / bc2;
            q->p[j] -= lr * (mh / (SQRT(vh) + eps) + wd * q->p[j]);
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
static real eval_loss(int batches) {
    real tot = 0.0f;
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
        real *lg = h_logits + (size_t)(len - 1) * VOCAB;
        real temp = 0.8f, sum = 0.0f, probs[VOCAB];
        for (int v = 0; v < VOCAB; v++) { probs[v] = EXP(lg[v] / temp); sum += probs[v]; }
        real r = frand() * sum, acc = 0.0f;
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
    real eps = 1e-3;
    real noise_floor = 1e-4f;      /* 方向导数低于此值即视为噪声不可分辨 */
    real worst_dir = 0.0f;
    int bad = 0;

    /* 1) 方向导数：每个参数张量一次 */
    printf("\n--- [1] 方向导数（覆盖每个张量的全部元素）---\n");
    for (int pi = 0; pi < nparams; pi++) {
        Param *q = &params[pi];
        real *dir = (real *)malloc((size_t)q->n * sizeof(real));
        double norm = 0.0;
        for (int j = 0; j < q->n; j++) { dir[j] = frand() * 2.0f - 1.0f; norm += (double)dir[j] * dir[j]; }
        norm = sqrt(norm) + 1e-12;
        for (int j = 0; j < q->n; j++) dir[j] = (real)(dir[j] / norm);

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
    real worst_el = 0.0f;
    int checked = 0, skipped = 0;
    for (int pi = 0; pi < nparams; pi++) {
        Param *q = &params[pi];
        for (int k = 0; k < 2; k++) {
            int idx = (int)(xrand() % (unsigned)q->n);
            real ana = q->g[idx];
            if (fabsf(ana) < 1e-3f) { skipped++; continue; }
            real orig = q->p[idx];
            q->p[idx] = orig + eps; forward(); real lp = loss_and_grad();
            q->p[idx] = orig - eps; forward(); real lm = loss_and_grad();
            q->p[idx] = orig;
            real num = (lp - lm) / (2 * eps);
            real rel = fabsf(num - ana) / (fabsf(num) + fabsf(ana) + 1e-6f);
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
    real best_val = 1e9f;
    int warm = steps / 10 + 1;
    for (int step = 1; step <= steps; step++) {
        real lr;
        if (step <= warm) lr = 3e-3f * step / (real)warm;
        else {
            real prog = (real)(step - warm) / (real)(steps - warm);
            lr = 3e-3f * 0.5f * (1.0f + COS(3.14159265f * prog));
        }
        sample_batch(0);
        forward();
        real loss = loss_and_grad();
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
            real vl = eval_loss(10);
            printf("             验证 loss %.4f%s\n", vl, vl < best_val ? "  (新低)" : "");
            if (vl < best_val) best_val = vl;
        }
    }
    printf("\n训练完成，用时 %.1f 秒，最终验证 loss %.4f\n",
           (double)clock() / CLOCKS_PER_SEC, eval_loss(20));
}

/* ------------------------------ 入口 ------------------------------------ */
int main(int argc, char **argv) {
    const char *mode = argc > 1 ? argv[1] : "train";
    const char *path = argc > 2 ? argv[2] : "corpus.txt";

    if (load_corpus(path) != 0) return 1;
    BT = B * T;
    init_params();

    if (strcmp(mode, "check") == 0) return gradcheck();

    alloc_activations();
    if (strcmp(mode, "sample") == 0) {
        generate(argc > 3 ? argv[3] : "The ", 400);
        return 0;
    }
    int steps = argc > 3 ? atoi(argv[3]) : 2000;
    train(steps);
    generate("\nThe ", 400);
    return 0;
}
