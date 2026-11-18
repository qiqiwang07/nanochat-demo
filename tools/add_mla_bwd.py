# -*- coding: utf-8 -*-
"""MLA 第三步：改反向传播（Q/K/V 独立缓冲 + 潜变量链式回传）。"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\src\nanogpt.c'
t = io.open(P, encoding='utf-8').read()

OLD = '''        const float *dao = g_ln1[l];                                    /* 注意力的上游梯度 */
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

#if USE_ROPE
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
        memset(g_ln1[l], 0, (size_t)BT * NEMBD * sizeof(float));        /* 复用缓冲存 d(ln1) */
        mm_nt(g_qkv[l], Wqkv[l]->p, g_ln1[l], BT, 3 * NEMBD, NEMBD);    /* d ln1  */
        mm_tn(h_ln1[l], g_qkv[l], Wqkv[l]->g, BT, NEMBD, 3 * NEMBD);    /* dWqkv  */
        for (int i = 0; i < BT; i++)                                     /* QKV 偏置梯度 */
            for (int c = 0; c < 3 * NEMBD; c++) b_qkv[l]->g[c] += g_qkv[l][(size_t)i * 3 * NEMBD + c];  /* 求和 */'''

NEW = '''        const float *dao = g_ln1[l];                                    /* 注意力的上游梯度 */
        memset(g_q[l], 0, (size_t)BT * NEMBD * sizeof(float));          /* Q 梯度清零 */
        memset(g_k[l], 0, (size_t)BT * NEMBD * sizeof(float));          /* K 梯度清零 */
        memset(g_v[l], 0, (size_t)BT * NEMBD * sizeof(float));          /* V 梯度清零 */
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
                    float *dq = g_q[l] + (size_t)(b * T + t) * NEMBD + hoff;              /* Q 的梯度 */
                    float dsum = 0.0f;                                  /* softmax 反向需要的点积和 */
                    for (int u = 0; u <= t; u++) {                      /* 先算 dL/datt */
                        const float *v = h_v[l] + (size_t)(b * T + u) * NEMBD + hoff;     /* 前向 V */
                        float s = 0.0f;                                 /* 点积 */
                        for (int d = 0; d < HD; d++) s += do_[d] * v[d];  /* do · v */
                        datt[u] = s;                                    /* 暂存 */
                        dsum += s * att[u];                             /* 累加 softmax 修正项 */
                    }
                    for (int d = 0; d < HD; d++) dq[d] = 0.0f;          /* Q 梯度先清零 */
                    for (int u = 0; u <= t; u++) {                      /* 对每个可见位置回传 */
                        float ds = att[u] * (datt[u] - dsum);          /* softmax 反向 */
                        const float *v  = h_v[l] + (size_t)(b * T + u) * NEMBD + hoff;   /* 前向 V */
                        float *dv = g_v[l] + (size_t)(b * T + u) * NEMBD + hoff;         /* V 梯度 */
                        for (int d = 0; d < HD; d++) dv[d] += att[u] * do_[d];  /* dV += att * do */
                        const float *q = h_q[l] + (size_t)(b * T + t) * NEMBD + hoff;    /* 前向 Q */
                        const float *k = h_k[l] + (size_t)(b * T + u) * NEMBD + hoff;    /* 前向 K */
                        float *dk = g_k[l] + (size_t)(b * T + u) * NEMBD + hoff;         /* K 梯度 */
                        for (int d = 0; d < HD; d++) {                  /* Q、K 的梯度 */
                            dq[d] += ds * k[d] * scale;                 /* dQ += ds * K * scale */
                            dk[d] += ds * q[d] * scale;                 /* dK += ds * Q * scale */
                        }
                    }
                }
            }
        }

#if USE_ROPE
        for (int b = 0; b < B; b++) {                   /* 与 forward 完全相同的遍历顺序 */
            for (int t = 0; t < T; t++) {
                for (int h = 0; h < NHEAD; h++) {
                    float *dq = g_q[l] + (size_t)(b * T + t) * NEMBD + h * HD;  /* 旋转坐标系下的 dQ */
                    float *dk = g_k[l] + (size_t)(b * T + t) * NEMBD + h * HD;  /* 旋转坐标系下的 dK */
                    rope_apply_bwd(dq, t, HD);          /* 反向旋转，转回原来的坐标系 */
                    rope_apply_bwd(dk, t, HD);
                }
            }
        }
#endif

        /* ---- MLA 反向：Q 支路 ---- */
        memset(g_ln1[l], 0, (size_t)BT * NEMBD * sizeof(float));        /* 清零，下面三条支路都累加到这 */
        mm_nt(g_q[l], Wq[l]->p, g_ln1[l], BT, NEMBD, NEMBD);            /* Q 支路对输入的梯度 */
        mm_tn(h_ln1[l], g_q[l], Wq[l]->g, BT, NEMBD, NEMBD);            /* dWq */
        for (int i = 0; i < BT; i++)                                     /* Q 偏置梯度 */
            for (int c = 0; c < NEMBD; c++) b_q[l]->g[c] += g_q[l][(size_t)i * NEMBD + c];

        /* ---- MLA 反向：K、V 先回传到潜变量 c ---- */
        memset(g_c[l], 0, (size_t)BT * DKV * sizeof(float));            /* 清零，K 与 V 两条支路累加 */
        mm_nt(g_k[l], W_uk[l]->p, g_c[l], BT, NEMBD, DKV);              /* K 支路 → dc */
        mm_tn(h_c[l], g_k[l], W_uk[l]->g, BT, DKV, NEMBD);              /* dW_uk */
        mm_nt(g_v[l], W_uv[l]->p, g_c[l], BT, NEMBD, DKV);              /* V 支路 → dc（累加） */
        mm_tn(h_c[l], g_v[l], W_uv[l]->g, BT, DKV, NEMBD);              /* dW_uv */
        for (int i = 0; i < BT; i++) {                                   /* K/V 偏置梯度 */
            for (int c = 0; c < NEMBD; c++) {
                b_uk[l]->g[c] += g_k[l][(size_t)i * NEMBD + c];
                b_uv[l]->g[c] += g_v[l][(size_t)i * NEMBD + c];
            }
        }

        /* ---- MLA 反向：潜变量再回传到输入 ---- */
        mm_nt(g_c[l], W_dkv[l]->p, g_ln1[l], BT, DKV, NEMBD);           /* 潜变量支路对输入的梯度（累加） */
        mm_tn(h_ln1[l], g_c[l], W_dkv[l]->g, BT, NEMBD, DKV);           /* dW_dkv */
        for (int i = 0; i < BT; i++)                                     /* 潜变量偏置梯度 */
            for (int j = 0; j < DKV; j++) b_dkv[l]->g[j] += g_c[l][(size_t)i * DKV + j];'''

assert OLD in t, '反向注意力段未匹配'
t = t.replace(OLD, NEW, 1)
io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('MLA 反向部分已替换')
