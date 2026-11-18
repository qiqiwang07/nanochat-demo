# -*- coding: utf-8 -*-
"""第三步：实现 MLA（多头潜在注意力）—— DeepSeek 的核心算法。

思路：
    普通注意力要把 K、V 完整存下来（每个 token 2×NEMBD 个数）。
    MLA 先把输入压成一个低维潜变量 c（维度 DKV），缓存时只需要存 c；
    用的时候再用 W_uk、W_uv 把 c 升维回 K、V。

        c = W_dkv · x            （NEMBD → DKV，压缩）
        K = W_uk  · c            （DKV → NEMBD，还原）
        V = W_uv  · c            （DKV → NEMBD，还原）
        Q = W_q   · x            （Q 不压缩，保持表达力）

    DKV = NEMBD/2 时，K/V 缓存从 2×NEMBD 降到 NEMBD/2，省 4 倍。

改造要点：
    1. Q/K/V 从交错的 h_qkv（每行 3×NEMBD）拆成三个独立缓冲，才能直接喂给 mm_nt/mm_tn
    2. 新增 4 组参数：Wq/bq、W_dkv/b_dkv、W_uk/b_uk、W_uv/b_uv
    3. 前向多两次升维，反向多两次链式回传
"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\src\nanogpt.c'
t = io.open(P, encoding='utf-8').read()

FIXES = []

# ---------- 1) 新增 DKV 宏 ----------
FIXES.append((
    '#define HD       (NEMBD / NHEAD)  /* 每个头的维度，必须整除，否则注意力无法拆分 */',
    '#define HD       (NEMBD / NHEAD)  /* 每个头的维度，必须整除，否则注意力无法拆分 */\n'
    '#define DKV      (NEMBD / 2)      /* MLA 潜变量维度：K/V 压缩到这个宽度，缓存省 4 倍 */'
))

# ---------- 2) 参数声明 ----------
FIXES.append((
    'static Param *Wqkv[NLAYER], *b_qkv[NLAYER], *Wo[NLAYER], *b_o[NLAYER];  /* 每层的注意力量重与偏置 */',
    'static Param *Wq[NLAYER], *b_q[NLAYER];                                 /* MLA：Q 的投影（不压缩） */\n'
    'static Param *W_dkv[NLAYER], *b_dkv[NLAYER];                            /* MLA：把输入压成潜变量 c */\n'
    'static Param *W_uk[NLAYER], *b_uk[NLAYER];                              /* MLA：潜变量 c 还原成 K */\n'
    'static Param *W_uv[NLAYER], *b_uv[NLAYER];                              /* MLA：潜变量 c 还原成 V */\n'
    'static Param *Wo[NLAYER], *b_o[NLAYER];                                 /* 注意力输出投影 */'
))

# ---------- 3) 激活缓冲声明 ----------
FIXES.append((
    'static float *h_inv1[NLAYER], *h_ln1[NLAYER], *h_qkv[NLAYER], *h_att[NLAYER];  /* 归一化系数、归一化输出、QKV、注意力分数 */',
    'static float *h_inv1[NLAYER], *h_ln1[NLAYER], *h_att[NLAYER];                  /* 归一化系数、归一化输出、注意力分数 */\n'
    'static float *h_q[NLAYER], *h_k[NLAYER], *h_v[NLAYER], *h_c[NLAYER];           /* MLA：Q、K、V 与潜变量 c（各自独立连续存放） */'
))
FIXES.append((
    'static float *g_xin[NLAYER], *g_ln1[NLAYER], *g_qkv[NLAYER], *g_ao[NLAYER];    /* 反向传播中逐层的梯度缓冲 */',
    'static float *g_xin[NLAYER], *g_ln1[NLAYER], *g_ao[NLAYER];                    /* 反向传播中逐层的梯度缓冲 */\n'
    'static float *g_q[NLAYER], *g_k[NLAYER], *g_v[NLAYER], *g_c[NLAYER];           /* MLA：Q/K/V 与潜变量的梯度 */'
))

# ---------- 4) 分配缓冲 ----------
FIXES.append((
    '        h_inv1[l] = falloc(BT);   h_ln1[l] = falloc(BTC);  h_qkv[l] = falloc(BT3C);   /* 归一化与 QKV */',
    '        h_inv1[l] = falloc(BT);   h_ln1[l] = falloc(BTC);                              /* 归一化 */\n'
    '        h_q[l] = falloc(BTC);     h_k[l] = falloc(BTC);  h_v[l] = falloc(BTC);        /* MLA 的 Q/K/V */\n'
    '        h_c[l] = falloc((size_t)BT * DKV);                                             /* MLA 潜变量 c */'
))
FIXES.append((
    '        g_xin[l]  = falloc(BTC);  g_ln1[l] = falloc(BTC);  g_qkv[l] = falloc(BT3C);   /* 反向梯度：入口、归一化1、QKV */',
    '        g_xin[l]  = falloc(BTC);  g_ln1[l] = falloc(BTC);                              /* 反向梯度 */\n'
    '        g_q[l] = falloc(BTC);     g_k[l] = falloc(BTC);  g_v[l] = falloc(BTC);        /* MLA 的 Q/K/V 梯度 */\n'
    '        g_c[l] = falloc((size_t)BT * DKV);                                             /* 潜变量梯度 */'
))

# ---------- 5) 注册参数 ----------
FIXES.append((
    '        snprintf(buf, sizeof buf, "L%d.Wqkv", l); Wqkv[l] = add_param(buf, 3 * NEMBD * NEMBD);  /* Q/K/V 合并成一个矩阵，省一次乘法 */\n'
    '        snprintf(buf, sizeof buf, "L%d.bqkv", l); b_qkv[l] = add_param(buf, 3 * NEMBD);         /* 对应的偏置 */',
    '        snprintf(buf, sizeof buf, "L%d.Wq",   l); Wq[l]   = add_param(buf, NEMBD * NEMBD);        /* MLA：Q 投影 */\n'
    '        snprintf(buf, sizeof buf, "L%d.bq",   l); b_q[l]  = add_param(buf, NEMBD);                /* Q 偏置 */\n'
    '        snprintf(buf, sizeof buf, "L%d.Wdkv", l); W_dkv[l]= add_param(buf, NEMBD * DKV);          /* MLA：压缩到潜变量 */\n'
    '        snprintf(buf, sizeof buf, "L%d.bdkv", l); b_dkv[l]= add_param(buf, DKV);                  /* 潜变量偏置 */\n'
    '        snprintf(buf, sizeof buf, "L%d.Wuk",  l); W_uk[l] = add_param(buf, DKV * NEMBD);          /* MLA：还原 K */\n'
    '        snprintf(buf, sizeof buf, "L%d.buk",  l); b_uk[l] = add_param(buf, NEMBD);                /* K 偏置 */\n'
    '        snprintf(buf, sizeof buf, "L%d.Wuv",  l); W_uv[l] = add_param(buf, DKV * NEMBD);          /* MLA：还原 V */\n'
    '        snprintf(buf, sizeof buf, "L%d.buv",  l); b_uv[l] = add_param(buf, NEMBD);                /* V 偏置 */'
))

# ---------- 6) 前向：MLA ----------
old_f = '''        /* ---- 注意力子层 ---- */
        rmsnorm_fwd(x_in, h_ln1[l], h_inv1[l], BT);   /* 先归一化，稳定数值 */
        memset(h_qkv[l], 0, (size_t)BT * 3 * NEMBD * sizeof(float));  /* mm_nn 是累加语义，必须先清零 */
        mm_nn(h_ln1[l], Wqkv[l]->p, h_qkv[l], BT, NEMBD, 3 * NEMBD);  /* 一次算出 Q、K、V */
        for (int i = 0; i < BT; i++) {                /* 加上 QKV 偏置 */
            float *q = h_qkv[l] + (size_t)i * 3 * NEMBD;  /* 当前行的 QKV 起点 */
            for (int c = 0; c < 3 * NEMBD; c++) q[c] += b_qkv[l]->p[c];  /* 偏置对 Q/K/V 三段共用同一组下标 */
        }

#if USE_ROPE
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
#endif'''

new_f = '''        /* ---- 注意力子层（MLA：先压缩再还原 K/V）---- */
        rmsnorm_fwd(x_in, h_ln1[l], h_inv1[l], BT);   /* 先归一化，稳定数值 */

        /* 第一步：把输入压成低维潜变量 c，这是 MLA 省缓存的关键 */
        memset(h_c[l], 0, (size_t)BT * DKV * sizeof(float));          /* mm_nn 是累加语义，先清零 */
        mm_nn(h_ln1[l], W_dkv[l]->p, h_c[l], BT, NEMBD, DKV);         /* c = W_dkv · x */
        for (int i = 0; i < BT; i++) {                                /* 加潜变量偏置 */
            float *cc = h_c[l] + (size_t)i * DKV;
            for (int j = 0; j < DKV; j++) cc[j] += b_dkv[l]->p[j];
        }

        /* 第二步：用潜变量还原出完整的 K、V */
        memset(h_k[l], 0, (size_t)BT * NEMBD * sizeof(float));        /* 清零 */
        mm_nn(h_c[l], W_uk[l]->p, h_k[l], BT, DKV, NEMBD);            /* K = W_uk · c */
        memset(h_v[l], 0, (size_t)BT * NEMBD * sizeof(float));        /* 清零 */
        mm_nn(h_c[l], W_uv[l]->p, h_v[l], BT, DKV, NEMBD);            /* V = W_uv · c */
        for (int i = 0; i < BT; i++) {                                /* 加 K/V 偏置 */
            float *kk = h_k[l] + (size_t)i * NEMBD;
            float *vv = h_v[l] + (size_t)i * NEMBD;
            for (int j = 0; j < NEMBD; j++) { kk[j] += b_uk[l]->p[j]; vv[j] += b_uv[l]->p[j]; }
        }

        /* 第三步：Q 不压缩，直接从输入投影 */
        memset(h_q[l], 0, (size_t)BT * NEMBD * sizeof(float));        /* 清零 */
        mm_nn(h_ln1[l], Wq[l]->p, h_q[l], BT, NEMBD, NEMBD);          /* Q = Wq · x */
        for (int i = 0; i < BT; i++) {                                /* 加 Q 偏置 */
            float *qq = h_q[l] + (size_t)i * NEMBD;
            for (int j = 0; j < NEMBD; j++) qq[j] += b_q[l]->p[j];
        }

#if USE_ROPE
        for (int b = 0; b < B; b++) {                  /* 逐条序列 */
            for (int t = 0; t < T; t++) {              /* 逐位置：位置 t 决定旋转角度 */
                for (int h = 0; h < NHEAD; h++) {      /* 逐头独立旋转 */
                    float *q = h_q[l] + (size_t)(b * T + t) * NEMBD + h * HD;  /* 该头的 Q */
                    float *k = h_k[l] + (size_t)(b * T + t) * NEMBD + h * HD;  /* 该头的 K */
                    rope_apply(q, t, HD);              /* Q 施加旋转 */
                    rope_apply(k, t, HD);              /* K 施加同样的旋转，点积才只依赖相对位置 */
                }
            }
        }
#endif'''

assert old_f in t, '前向注意力段未匹配'
t = t.replace(old_f, new_f, 1)

# ---------- 7) 前向注意力循环里的索引 ----------
FIXES.append((
    '                    const float *q = h_qkv[l] + ((size_t)(b * T + t) * 3 * NEMBD) + hoff;  /* 当前 token 的 Q */',
    '                    const float *q = h_q[l] + (size_t)(b * T + t) * NEMBD + hoff;  /* 当前 token 的 Q */'
))
FIXES.append((
    '                        const float *k = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + NEMBD + hoff;  /* K 在第二段 */',
    '                        const float *k = h_k[l] + (size_t)(b * T + u) * NEMBD + hoff;  /* 该位置的 K */'
))
FIXES.append((
    '                        const float *v = h_qkv[l] + ((size_t)(b * T + u) * 3 * NEMBD) + 2 * NEMBD + hoff;  /* V 在第三段 */',
    '                        const float *v = h_v[l] + (size_t)(b * T + u) * NEMBD + hoff;  /* 该位置的 V */'
))

applied = 0
for old, new in FIXES:
    if old in t:
        t = t.replace(old, new, 1)
        applied += 1
    else:
        print('✘ 未匹配:', old.split('\n')[0][:70])

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('MLA 前向部分应用 %d / %d 处' % (applied, len(FIXES)))
