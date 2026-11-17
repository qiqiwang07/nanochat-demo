# -*- coding: utf-8 -*-
"""第二步：加 RoPE（旋转位置编码），并去掉可学习的位置嵌入。

RoPE 原理：
    把 Q、K 的每两个维度看作复平面上的一对数，按位置 t 旋转一个角度：
        q' = R(t·θ_i) · q
    两个向量的点积只依赖它们的相对位置 (t-u)，所以模型天然获得相对位置信息，
    也不需要 pos_emb 参数了（DeepSeek、LLaMA 都这么做）。

    旋转公式（i 与 i+HD/2 成对）：
        x' = x·cos - y·sin
        y' = x·sin + y·cos
    角度 θ_i = base^(-2i/HD)，base = 10000。

反向传播：
    旋转是正交变换，梯度回传就是乘以转置，即用 -θ 再旋转一次。
"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\src\nanogpt.c'
t = io.open(P, encoding='utf-8').read()

FIXES = []

# ---------- 1) 加 RoPE 开关与两个工具函数 ----------
FIXES.append((
    '''/* ------------------------------ RMSNorm --------------------------------''',
    '''/* ------------------------------ RoPE 旋转位置编码 -----------------------
 * 为什么需要：位置嵌入是"学出来的绝对位置"，换长度就不适配；
 * RoPE 把位置编码成旋转角度，注意力分数只和相对距离有关，外推更好。 */
#ifndef NO_ROPE
#define USE_ROPE 1          /* 默认启用，可用 -DNO_ROPE 编译对比消融实验 */
#else
#define USE_ROPE 0
#endif

static inline void rope_apply(float *x, int pos, int hd) {
    /* 对 hd 维向量做一次旋转：前一半 i 与后一半 i+hd/2 配对 */
    for (int i = 0; i < hd / 2; i++) {
        float freq = powf(10000.0f, -2.0f * (float)i / (float)hd);  /* 频率随维度指数衰减 */
        float ang = (float)pos * freq;                              /* 当前维度上的旋转角 */
        float c = cosf(ang), s = sinf(ang);                         /* 预计算三角函数 */
        float a = x[i], b = x[i + hd / 2];                          /* 取出一对分量 */
        x[i]           = a * c - b * s;                             /* 旋转后的前一半 */
        x[i + hd / 2]   = a * s + b * c;                            /* 旋转后的后一半 */
    }
}

static inline void rope_apply_bwd(float *g, int pos, int hd) {
    /* 旋转矩阵的转置 = 反向旋转，用于把梯度转回未旋转的坐标系 */
    for (int i = 0; i < hd / 2; i++) {
        float freq = powf(10000.0f, -2.0f * (float)i / (float)hd);  /* 与前向完全一致的频率 */
        float ang = (float)pos * freq;                              /* 同一个角度 */
        float c = cosf(ang), s = sinf(ang);                         /* 同样的三角函数 */
        float a = g[i], b = g[i + hd / 2];                          /* 旋转坐标系下的梯度 */
        g[i]           = a * c + b * s;                             /* 转置旋转，符号相反 */
        g[i + hd / 2]   = -a * s + b * c;                           /* 保持正交性 */
    }
}

/* ------------------------------ RMSNorm --------------------------------'''
))

# ---------- 2) 删除可学习位置嵌入的参数注册 ----------
FIXES.append((
    '''    p_pos = add_param("pos_emb", T * NEMBD);       /* 位置嵌入：学出来的绝对位置编码 */''',
    '''    /* 位置信息由 RoPE 提供，不再需要可学习的位置嵌入（省 T*NEMBD 个参数） */'''
))

# ---------- 3) 前向嵌入：只加词嵌入 ----------
FIXES.append((
    '''        const float *pe = p_pos->p + (size_t)t * NEMBD;    /* 该位置的位置嵌入行 */
        float *o = h_emb + (size_t)i * NEMBD;         /* 输出行 */
        for (int c = 0; c < NEMBD; c++) o[c] = te[c] + pe[c];  /* 直接相加，最经典的做法 */''',
    '''        float *o = h_emb + (size_t)i * NEMBD;         /* 输出行 */
        for (int c = 0; c < NEMBD; c++) o[c] = te[c];  /* 只有词嵌入，位置信息交给 RoPE */
        (void)t;                                      /* t 在这里不用了，加 (void) 避免告警 */'''
))

# ---------- 4) 前向：QKV 加完偏置后应用 RoPE ----------
FIXES.append((
    '''        float scale = 1.0f / sqrtf((float)HD);        /* 缩放因子 1/sqrt(d_k)，防止点积随维度爆炸 */''',
    '''#if USE_ROPE
        for (int b = 0; b < B; b++) {                  /* 逐条序列 */
            for (int t = 0; t < T; t++) {              /* 逐位置：位置 t 决定旋转角度 */
                for (int h = 0; h < NHEAD; h++) {      /* 逐头独立旋转 */
                    float *q = h_qkv[l] + ((size_t)(b * T + t) * 3 * NEMBD) + h * HD;  /* 该头的 Q */
                    float *k = q + NEMBD;              /* 紧随其后的是 K */
                    rope_apply(q, t, HD);              /* Q 施加旋转 */
                    rope_apply(k, t, HD);              /* K 施加同样的旋转，点积才只依赖相对位置 */
                }
            }
        }
#endif
        float scale = 1.0f / sqrtf((float)HD);        /* 缩放因子 1/sqrt(d_k)，防止点积随维度爆炸 */'''
))

# ---------- 5) 反向：attention 算出 dq/dk 之后，先把梯度转回未旋转坐标系 ----------
FIXES.append((
    '''        memset(g_ln1[l], 0, (size_t)BT * NEMBD * sizeof(float));        /* 复用缓冲存 d(ln1) */''',
    '''#if USE_ROPE
        for (int b = 0; b < B; b++) {                   /* 与 forward 完全相同的遍历顺序 */
            for (int t = 0; t < T; t++) {
                for (int h = 0; h < NHEAD; h++) {
                    float *dq = g_qkv[l] + ((size_t)(b * T + t) * 3 * NEMBD) + h * HD;  /* 旋转坐标系下的 dQ */
                    float *dk = dq + NEMBD;             /* 旋转坐标系下的 dK */
                    rope_apply_bwd(dq, t, HD);          /* 反向旋转，转回原来的坐标系 */
                    rope_apply_bwd(dk, t, HD);
                }
            }
        }
#endif
        memset(g_ln1[l], 0, (size_t)BT * NEMBD * sizeof(float));        /* 复用缓冲存 d(ln1) */'''
))

# ---------- 6) 参数说明同步 ----------
FIXES.append((
    '''static Param *p_tok, *p_pos, *p_lm, *b_lm;   /* token 嵌入、位置嵌入、输出投影、输出偏置 */''',
    '''static Param *p_tok, *p_lm, *b_lm;           /* token 嵌入、输出投影、输出偏置（位置由 RoPE 负责） */'''
))

applied = 0
for old, new in FIXES:
    if old in t:
        t = t.replace(old, new, 1)
        applied += 1
    else:
        print('✘ 未匹配:', old.split('\n')[0][:70])

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('RoPE 补丁应用 %d / %d 处' % (applied, len(FIXES)))
