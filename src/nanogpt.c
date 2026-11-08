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
#endif

/* ------------------------------ 超参数 ----------------------------------
 * 四个尺寸参数可在编译时用 -D 覆盖，例如大模型：
 *   gcc -DNLAYER=6 -DNEMBD=192 -DNHEAD=6 -DMLP=768 ...
 * 权重文件里记录了架构，加载时会校验，不匹配会拒绝加载。 */
#ifndef NLAYER
#define NLAYER   4
#endif
#ifndef NEMBD
#define NEMBD    128
#endif
#ifndef NHEAD
#define NHEAD    4
#endif
#ifndef MLP
#define MLP      512
#endif
#ifdef CHARLEVEL
#define VOCAB    1200        /* 字符级词表：最多 1200 个不同字符（汉字/字母/符号） */
#else
#define VOCAB    256         /* 字节级词表：覆盖全部字节 */
#endif
#define HD       (NEMBD / NHEAD)
#define RMS_EPS  1e-5f

static int B = 8;            /* batch */
static int T = 256;          /* 上下文：字符级时 256 个字符 */
static int BT;               /* B*T */

/* ------------------------------ 参数表 ---------------------------------- */
typedef struct {
    const char *name;
    int n;
    float *p, *g, *m, *v;    /* 数值 / 梯度 / AdamW 一阶、二阶动量 */
} Param;

static Param params[160];
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

#ifdef CHARLEVEL
/* ===== 字符级：一个汉字就是一个 token，模型只能吐出完整字符，不会出乱码 ===== */
static int  vocab_cp[VOCAB];          /* id -> Unicode 码点 */
#define CMAP 8192
static int  cmap_cp[CMAP];
static int  cmap_id[CMAP];
static void cmap_init(void) { for (int i = 0; i < CMAP; i++) cmap_cp[i] = -1; }
static int char_id(int cp) {
    unsigned h = (unsigned)cp * 2654435761u;
    int b = (int)(h & (CMAP - 1));
    while (cmap_cp[b] != -1) {
        if (cmap_cp[b] == cp) return cmap_id[b];
        b = (b + 1) & (CMAP - 1);
    }
    return 0;
}
static void cmap_put(int cp, int id) {
    unsigned h = (unsigned)cp * 2654435761u;
    int b = (int)(h & (CMAP - 1));
    while (cmap_cp[b] != -1 && cmap_cp[b] != cp) b = (b + 1) & (CMAP - 1);
    cmap_cp[b] = cp; cmap_id[b] = id;
}
static int u8_get(const unsigned char *p, int *len) {
    if (p[0] < 0x80) { *len = 1; return p[0]; }
    if ((p[0] & 0xE0) == 0xC0) { *len = 2; return ((p[0] & 0x1F) << 6) | (p[1] & 0x3F); }
    if ((p[0] & 0xF0) == 0xE0) { *len = 3; return ((p[0] & 0x0F) << 12) | ((p[1] & 0x3F) << 6) | (p[2] & 0x3F); }
    *len = 4; return ((p[0] & 0x07) << 18) | ((p[1] & 0x3F) << 12) | ((p[2] & 0x3F) << 6) | (p[3] & 0x3F);
}
static int u8_put(int cp, char *buf) {
    if (cp < 0x80) { buf[0] = (char)cp; return 1; }
    if (cp < 0x800) { buf[0] = (char)(0xC0 | (cp >> 6)); buf[1] = (char)(0x80 | (cp & 0x3F)); return 2; }
    if (cp < 0x10000) { buf[0] = (char)(0xE0 | (cp >> 12)); buf[1] = (char)(0x80 | ((cp >> 6) & 0x3F)); buf[2] = (char)(0x80 | (cp & 0x3F)); return 3; }
    buf[0] = (char)(0xF0 | (cp >> 18)); buf[1] = (char)(0x80 | ((cp >> 12) & 0x3F));
    buf[2] = (char)(0x80 | ((cp >> 6) & 0x3F)); buf[3] = (char)(0x80 | (cp & 0x3F));
    return 4;
}
#else
static unsigned char vocab[VOCAB];
static int   byte2id[256];
#endif

/* UTF-8 字符串 -> id 序列 */
static int str_to_ids(const char *s, int *out, int maxn) {
    int n = 0;
#ifdef CHARLEVEL
    const unsigned char *p = (const unsigned char *)s;
    while (*p && n < maxn) { int len; int cp = u8_get(p, &len); out[n++] = char_id(cp); p += len; }
#else
    while (s[n] && n < maxn) { out[n] = byte2id[(unsigned char)s[n]]; n++; }
#endif
    return n;
}
/* id -> 文本字节，返回字节数 */
static int id_to_out(int id, char *out) {
#ifdef CHARLEVEL
    return u8_put(vocab_cp[id], out);
#else
    out[0] = (char)vocab[id];
    return 1;
#endif
}

static int load_corpus(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "打不开语料: %s\n", path); return -1; }
    fseek(f, 0, SEEK_END); ncorpus = ftell(f); fseek(f, 0, SEEK_SET);
    corpus = (unsigned char *)malloc((size_t)ncorpus);
    if (fread(corpus, 1, (size_t)ncorpus, f) != (size_t)ncorpus) { fclose(f); return -1; }
    fclose(f);

    if (ncorpus < 1000) {
        fprintf(stderr, "语料太小（%ld 字节），至少需要 1000 字节\n", ncorpus);
        return -1;
    }
#ifdef CHARLEVEL
    {
        static int freq[0x10000];
        memset(freq, 0, sizeof freq);
        long ncp = 0;
        for (long i = 0; i < ncorpus; ) {
            int len; int cp = u8_get(corpus + i, &len);
            if (cp > 0 && cp < 0x10000) freq[cp]++;
            i += len; ncp++;
        }
        cmap_init();
        int k = 0;
        for (; k < VOCAB; k++) {
            int best = -1; long bestc = 0;
            for (int c = 1; c < 0x10000; c++)
                if (freq[c] > bestc) { bestc = freq[c]; best = c; }
            if (best < 0) break;
            freq[best] = 0;
            vocab_cp[k] = best;
            cmap_put(best, k);
        }
        for (; k < VOCAB; k++) { vocab_cp[k] = 0xFFFD; }   /* 剩余槽位占位 */
        int *tok = (int *)malloc(sizeof(int) * (size_t)(ncp + 1));
        long nt = 0;
        for (long i = 0; i < ncorpus; ) {
            int len; int cp = u8_get(corpus + i, &len);
            tok[nt++] = char_id(cp);
            i += len;
        }
        tokens = tok;
        ncorpus = nt;                       /* 这里是"字符数" */
        ntrain = (long)(ncorpus * 0.98);
        nval = ncorpus - ntrain;
        printf("语料 %ld 个字符 | 训练 %ld | 验证 %ld | 字表 %d 个字符\n", ncorpus, ntrain, nval, k);
        return 0;
    }
#else
    {
        long freq[256];
        memset(freq, 0, sizeof freq);
        for (long i = 0; i < ncorpus; i++) freq[corpus[i]]++;
        for (int k = 0; k < VOCAB; k++) {
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
#endif
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
    int n = str_to_ids(prompt, ctx, 8000);
    if (n == 0) { ctx[n++] = str_to_ids("\n", ctx + n, 1); }

    int savedB = B;
    B = 1;                                    /* 生成只用一条序列 */
    printf("--- 生成 %d 字符 | 提示: \"%s\" ---\n", nchars, prompt);
    for (int i = 0; i < n; i++) { char ob[8]; int k = id_to_out(ctx[i], ob); fwrite(ob, 1, (size_t)k, stdout); }
    for (int s = 0; s < nchars; s++) {
        int len = n < T ? n : T;
        BT = len;
        for (int t = 0; t < len; t++) { xs[t] = ctx[n - len + t]; ys[t] = 0; }
        forward();
        float *lg = h_logits + (size_t)(len - 1) * VOCAB;
        /* top-40 + 稳定 softmax + 温度 0.7：小模型这样吐字才连贯 */
        float kth = -1e30f;
        for (int v = 0; v < VOCAB; v++) if (lg[v] > kth) kth = lg[v];
        for (int r = 0; r < 39; r++) {
            float best = -1e30f;
            for (int v = 0; v < VOCAB; v++) if (lg[v] < kth && lg[v] > best) best = lg[v];
            kth = best;
        }
        float probs[VOCAB], sum = 0.0f, temp = 0.7f;
        for (int v = 0; v < VOCAB; v++) {
            if (lg[v] < kth) { probs[v] = 0.0f; continue; }
            float e = (lg[v] - kth) / temp;
            if (e > 60.0f) e = 60.0f;
            probs[v] = expf(e);
            sum += probs[v];
        }
        float r = frand() * sum, acc = 0.0f;
        int pick = VOCAB - 1;
        for (int v = 0; v < VOCAB; v++) { acc += probs[v]; if (r <= acc) { pick = v; break; } }
        ctx[n++] = pick;
        { char ob[8]; int k = id_to_out(pick, ob); fwrite(ob, 1, (size_t)k, stdout); }
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
#ifdef CHARLEVEL
    bytes += (long)fwrite(vocab_cp, sizeof(int), VOCAB, f);
#else
    bytes += (long)fwrite(vocab, 1, VOCAB, f);
#endif
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
#ifdef CHARLEVEL
    if (fread(vocab_cp, sizeof(int), VOCAB, f) != VOCAB) { fclose(f); return -1; }
    cmap_init();
    for (int k = 0; k < VOCAB; k++) cmap_put(vocab_cp[k], k);
#else
    if (fread(vocab, 1, VOCAB, f) != VOCAB) { fclose(f); return -1; }
    for (int b = 0; b < 256; b++) byte2id[b] = 0;
    for (int k = 0; k < VOCAB; k++) byte2id[vocab[k]] = k;
#endif

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
    return n + str_to_ids(s, ctx + n, 8190 - n);
}

/* 从 ctx 继续采样，边生成边打印；遇到停止串就停下并把它从 ctx 里去掉。
   返回新增字符数。 */
static int chat_generate(int *ctx, int *n, int maxchars, const char *stop) {
    int savedB = B;
    int stop_ids[16];
    int stoplen = str_to_ids(stop, stop_ids, 16);      /* 停止串也变成 id 序列比较 */
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
        { char ob[8]; int k = id_to_out(pick, ob); fwrite(ob, 1, (size_t)k, stdout); }
        fflush(stdout);
        if (*n - start >= stoplen) {                 /* 命中停止串？ */
            int match = 1;
            for (int k = 0; k < stoplen; k++)
                if (ctx[*n - stoplen + k] != stop_ids[k]) { match = 0; break; }
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
    int n = str_to_ids(prompt, ctx, 8000);
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
        if (m + 8 < maxch) {
            int k = id_to_out(pick, out + m);
            m += k;
        }
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

/* ------------------------------ 入口 ------------------------------------ */
int main(int argc, char **argv) {
#ifdef _WIN32
    SetConsoleOutputCP(65001);       /* 控制台按 UTF-8 输出，中文不乱码 */
#endif
    const char *mode = argc > 1 ? argv[1] : "train";
    const char *path = argc > 2 ? argv[2] : "corpus.txt";

    if (load_corpus(path) != 0) return 1;
    BT = B * T;
    init_params();

    if (strcmp(mode, "check") == 0) return gradcheck();

    alloc_activations();

    if (strcmp(mode, "ask") == 0) {
        /* ask <corpus> <weights.bin> "题目" */
        const char *wpath = argc > 3 ? argv[3] : NULL;
        if (!wpath || argc < 5) {
            fprintf(stderr, "用法: nanogpt ask <corpus.txt> <权重.bin> \"题目\"\n");
            return 1;
        }
        if (load_weights(wpath) != 0) return 1;
        ask_mode(argv[4]);
        return 0;
    }

    if (strcmp(mode, "arith_eval") == 0) {
        /* arith_eval <corpus> <weights.bin> <testfile> */
        if (argc < 5) {
            fprintf(stderr, "用法: nanogpt arith_eval <corpus.txt> <权重.bin> <测试集.txt>\n");
            return 1;
        }
        if (load_weights(argv[3]) != 0) return 1;
        arith_eval(argv[4]);
        return 0;
    }

    if (strcmp(mode, "think") == 0) {
        /* think <corpus> <weights.bin> "题目" [样本数] */
        const char *wpath = argc > 3 ? argv[3] : NULL;
        if (!wpath || argc < 5) {
            fprintf(stderr, "用法: nanogpt think <corpus.txt> <权重.bin> \"题目\" [样本数=8]\n");
            return 1;
        }
        if (load_weights(wpath) != 0) return 1;
        char *q = to_utf8(argv[4]);
        think_mode(q, argc > 5 ? atoi(argv[5]) : 8);
        free(q);
        return 0;
    }

    if (strcmp(mode, "chat") == 0) {
        /* chat <corpus> <weights.bin> ["单个问题"] */
        const char *wpath = argc > 3 ? argv[3] : NULL;
        if (!wpath) {
            fprintf(stderr, "用法: nanogpt chat <corpus.txt> <权重.bin> [\"问题\"]\n");
            return 1;
        }
        if (load_weights(wpath) != 0) return 1;
        chat_mode(argc > 4 ? argv[4] : NULL);
        return 0;
    }

    if (strcmp(mode, "sample") == 0) {
        /* sample <corpus> [weights.bin] ["prompt"] */
        const char *wpath = NULL, *prompt = "The ";
        for (int i = 3; i < argc; i++) {
            if (strstr(argv[i], ".bin")) wpath = argv[i];
            else prompt = argv[i];
        }
        if (wpath) { if (load_weights(wpath) != 0) return 1; }
        else printf("[提示] 未给权重文件，用随机初始化的权重生成（必然是乱码）\n");
        char *pu = to_utf8(prompt);          /* 命令行中文是 GBK，转 UTF-8 */
        generate(pu, 600);
        free(pu);
        return 0;
    }

    if (strcmp(mode, "resume") == 0) {
        /* resume <corpus> <weights.bin> <steps> [out.bin] */
        if (argc < 5) {
            fprintf(stderr, "用法: nanogpt resume <corpus.txt> <权重.bin> <步数> [输出.bin]\n");
            return 1;
        }
        if (load_weights(argv[3]) != 0) return 1;
        train(atoi(argv[4]));
        generate("\nThe ", 400);
        if (argc > 5) save_weights(argv[5]);
        return 0;
    }

    /* train <corpus> [steps] [out.bin] */
    int steps = argc > 3 ? atoi(argv[3]) : 2000;
    train(steps);
    generate("\nThe ", 400);
    if (argc > 4) save_weights(argv[4]);
    else printf("[提示] 未给保存路径，权重没落盘。用法: nanogpt train <corpus> <步数> <权重.bin>\n");
    return 0;
}
