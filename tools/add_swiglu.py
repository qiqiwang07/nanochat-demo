# -*- coding: utf-8 -*-
"""第一步：把 ReLU 前馈网络换成 SwiGLU（DeepSeek/LLaMA 用的门控激活）。

原理：
    ReLU 版：  h = W2 · ReLU(W1·x + b1) + b2
    SwiGLU 版：u = W1·x + b1          （内容支路）
              g = W3·x + b3          （门控支路）
              h = W2 · (SiLU(u) ⊙ g) + b2

SiLU(x) = x * sigmoid(x)，导数 = sigmoid(x) * (1 + x*(1 - sigmoid(x)))

反向推导（设 a = SiLU(u)⊙g，上游梯度 dh）：
    du = dh * g * SiLU'(u)
    dg = dh * SiLU(u)
    dW2 += aᵀ·dh          （在 mm_tn 里完成）
    dW1 += xᵀ·du,  db1 += Σdu
    dW3 += xᵀ·dg,  db3 += Σdg
"""
import ast
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\src\nanogpt.c'
t = io.open(P, encoding='utf-8').read()

FIXES = []

# ---------- 1) 新增参数 W3 / b3 ----------
FIXES.append((
    'static Param *W1[NLAYER], *b_1[NLAYER], *W2[NLAYER], *b_2[NLAYER];      /* 每层前馈网络的两层 */',
    'static Param *W1[NLAYER], *b_1[NLAYER], *W2[NLAYER], *b_2[NLAYER];      /* 每层前馈网络：升维、降维 */\n'
    'static Param *W3[NLAYER], *b_3[NLAYER];                                 /* SwiGLU 的门控支路（DeepSeek/LLaMA 同款） */'
))

# ---------- 2) 新增激活缓冲 h_gate / 梯度 g_gate ----------
FIXES.append((
    'static float *h_pre[NLAYER], *h_act[NLAYER], *h_h2[NLAYER], *h_x2[NLAYER];     /* FFN 中间量、激活值、FFN 输出、残差2 */',
    'static float *h_pre[NLAYER], *h_act[NLAYER], *h_h2[NLAYER], *h_x2[NLAYER];     /* FFN 中间量、激活值、FFN 输出、残差2 */\n'
    'static float *h_gate[NLAYER];   /* SwiGLU 门控支路的输出（前向要留着算反向） */'
))
FIXES.append((
    'static float *g_ln2[NLAYER], *g_pre[NLAYER], *g_act[NLAYER], *g_xout[NLAYER];  /* 同上，供 FFN 与残差使用 */',
    'static float *g_ln2[NLAYER], *g_pre[NLAYER], *g_act[NLAYER], *g_xout[NLAYER];  /* 同上，供 FFN 与残差使用 */\n'
    'static float *g_gate[NLAYER];   /* 门控支路的梯度 */'
))

# ---------- 3) 分配缓冲 ----------
FIXES.append((
    '        h_act[l]  = falloc(BTMLP);h_h2[l]  = falloc(BTC);  h_x2[l]  = falloc(BTC);    /* FFN 激活与输出 */',
    '        h_act[l]  = falloc(BTMLP);h_h2[l]  = falloc(BTC);  h_x2[l]  = falloc(BTC);    /* FFN 激活与输出 */\n'
    '        h_gate[l] = falloc(BTMLP);                                                   /* 门控支路输出 */'
))
FIXES.append((
    '        g_act[l]  = falloc(BTMLP);g_xout[l]= falloc(BTC);                            /* FFN 激活、出口 */',
    '        g_act[l]  = falloc(BTMLP);g_xout[l]= falloc(BTC);                            /* FFN 激活、出口 */\n'
    '        g_gate[l] = falloc(BTMLP);                                                   /* 门控支路梯度 */'
))

# ---------- 4) 注册参数 ----------
FIXES.append((
    '        snprintf(buf, sizeof buf, "L%d.b2",   l); b_2[l]  = add_param(buf, NEMBD);              /* FFN 第二层偏置 */',
    '        snprintf(buf, sizeof buf, "L%d.b2",   l); b_2[l]  = add_param(buf, NEMBD);              /* FFN 第二层偏置 */\n'
    '        snprintf(buf, sizeof buf, "L%d.W3",   l); W3[l]   = add_param(buf, NEMBD * MLP);        /* SwiGLU 门控投影 */\n'
    '        snprintf(buf, sizeof buf, "L%d.b3",   l); b_3[l]  = add_param(buf, MLP);                /* 门控偏置 */'
))

# ---------- 5) 前向：SwiGLU ----------
FIXES.append((
    '''        for (int i = 0; i < BT; i++) {                              /* 加偏置并做 ReLU */
            float *pr = h_pre[l] + (size_t)i * MLP;                 /* 升维后的值 */
            float *ac = h_act[l] + (size_t)i * MLP;                 /* 激活后的值 */
            for (int j = 0; j < MLP; j++) {
                float v = pr[j] + b_1[l]->p[j];                     /* 先加偏置 */
                pr[j] = v;                                          /* 反向传播要用加偏置后的值判断 ReLU 是否激活 */
                ac[j] = v > 0.0f ? v : 0.0f;          /* ReLU */
            }
        }''',
    '''        memset(h_gate[l], 0, (size_t)BT * MLP * sizeof(float));     /* 门控支路清零 */
        mm_nn(h_ln2[l], W3[l]->p, h_gate[l], BT, NEMBD, MLP);       /* SwiGLU 的门控投影 W3·x */
        for (int i = 0; i < BT; i++) {                              /* 加偏置，算 SiLU(u) ⊙ g */
            float *pr = h_pre[l] + (size_t)i * MLP;                 /* 内容支路 u */
            float *ga = h_gate[l] + (size_t)i * MLP;                /* 门控支路 g */
            float *ac = h_act[l] + (size_t)i * MLP;                 /* 激活后的值 */
            for (int j = 0; j < MLP; j++) {
                float u = pr[j] + b_1[l]->p[j];                     /* 内容支路加偏置 */
                float g = ga[j] + b_3[l]->p[j];                     /* 门控支路加偏置 */
                pr[j] = u;                                          /* 存下来，反向算 SiLU' 要用 */
                ga[j] = g;                                          /* 存下来，反向算 dg 要用 */
                float sig = 1.0f / (1.0f + expf(-u));               /* sigmoid(u) */
                float silu = u * sig;                               /* SiLU(u) = u·σ(u) */
                ac[j] = silu * g;                                   /* 门控相乘：内容被门控调节 */
            }
        }'''
))

# ---------- 6) 反向：SwiGLU ----------
FIXES.append((
    '''        for (int i = 0; i < BT; i++) {                                 /* 穿过 ReLU */
            const float *pr = h_pre[l] + (size_t)i * MLP;              /* 加偏置后的值 */
            const float *ga = g_act[l] + (size_t)i * MLP;              /* 激活后的梯度 */
            float *gp = g_pre[l] + (size_t)i * MLP;                    /* 激活前的梯度 */
            for (int j = 0; j < MLP; j++) gp[j] = pr[j] > 0.0f ? ga[j] : 0.0f;  /* ReLU'：>0 才传梯度 */
        }''',
    '''        for (int i = 0; i < BT; i++) {                                 /* 穿过 SwiGLU 的两个支路 */
            const float *pr = h_pre[l] + (size_t)i * MLP;              /* 内容支路 u */
            const float *gg = h_gate[l] + (size_t)i * MLP;             /* 门控支路 g */
            const float *gd = g_act[l] + (size_t)i * MLP;              /* 对 (SiLU(u)⊙g) 的梯度 */
            float *gp = g_pre[l] + (size_t)i * MLP;                    /* 对 u 的梯度 */
            float *ggr = g_gate[l] + (size_t)i * MLP;                  /* 对 g 的梯度 */
            for (int j = 0; j < MLP; j++) {
                float u = pr[j], g = gg[j], d = gd[j];                 /* 取出前向的值与上游梯度 */
                float sig = 1.0f / (1.0f + expf(-u));                  /* σ(u) */
                float silu = u * sig;                                  /* SiLU(u) */
                float dsilu = sig * (1.0f + u * (1.0f - sig));         /* SiLU'(u) = σ(u)(1 + u(1-σ(u))) */
                gp[j] = d * g * dsilu;                                 /* du = d · g · SiLU'(u) */
                ggr[j] = d * silu;                                     /* dg = d · SiLU(u) */
            }
        }'''
))

# ---------- 7) 反向：W3/b3 的梯度 ----------
FIXES.append((
    '''        for (int i = 0; i < BT; i++)                                    /* FFN 第一层偏置梯度 */
            for (int j = 0; j < MLP; j++) b_1[l]->g[j] += g_pre[l][(size_t)i * MLP + j];  /* 求和 */''',
    '''        memset(g_ln2[l], 0, (size_t)BT * NEMBD * sizeof(float));       /* 复用缓冲：先算门控支路对输入的梯度 */
        mm_nt(g_gate[l], W3[l]->p, g_ln2[l], BT, MLP, NEMBD);          /* d x（来自门控支路） */
        mm_tn(h_ln2[l], g_gate[l], W3[l]->g, BT, NEMBD, MLP);          /* dW3 */
        for (int i = 0; i < BT; i++)                                    /* 门控偏置梯度 */
            for (int j = 0; j < MLP; j++) b_3[l]->g[j] += g_gate[l][(size_t)i * MLP + j];  /* 求和 */

        for (int i = 0; i < BT; i++)                                    /* FFN 第一层偏置梯度 */
            for (int j = 0; j < MLP; j++) b_1[l]->g[j] += g_pre[l][(size_t)i * MLP + j];  /* 求和 */'''
))

# ---------- 8) 反向：两条支路的 dx 要相加（原来 g_ln2 被覆盖，改为累加） ----------
FIXES.append((
    '''        memset(g_ln2[l], 0, (size_t)BT * NEMBD * sizeof(float));       /* 清零 */
        mm_nt(g_pre[l], W1[l]->p, g_ln2[l], BT, MLP, NEMBD);           /* d ln2 */
        mm_tn(h_ln2[l], g_pre[l], W1[l]->g, BT, NEMBD, MLP);           /* dW1   */''',
    '''        mm_nt(g_pre[l], W1[l]->p, g_ln2[l], BT, MLP, NEMBD);           /* d x（来自内容支路），累加到门控支路的梯度上 */
        mm_tn(h_ln2[l], g_pre[l], W1[l]->g, BT, NEMBD, MLP);           /* dW1   */'''
))

applied = 0
for old, new in FIXES:
    if old in t:
        t = t.replace(old, new, 1)
        applied += 1
    else:
        print('✘ 未匹配:', old.split('\n')[0][:70])

ast.parse  # 占位，C 文件不用 ast
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('SwiGLU 补丁应用 %d / %d 处' % (applied, len(FIXES)))
