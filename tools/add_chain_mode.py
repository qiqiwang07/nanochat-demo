# -*- coding: utf-8 -*-
"""给 nanogpt 加 chain 模式：逐步验证模型给出的推理链。

用途：
    模型（或人）给出形如 "3+5=8; 8*2=16; 16-2=14" 的推理链，
    本模式逐个算式复算，指出哪一步错、正确值是多少，并给出最终可信答案。

为什么这比"让模型直接回答"可靠：
    模型可以编造中间步骤，但每个算式都会被独立重算一遍；
    只要有一步对不上，立刻能定位到具体位置。
"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\src\nanogpt.c'
t = io.open(P, encoding='utf-8').read()

NEW = r'''
/* ====================== 推理链验证 ======================
 * 输入：形如 "3+5=8; 8*2=16; 16-2=14" 的步骤串（分号或换行分隔）
 * 输出：每步的判定（对/错/无法解析）+ 最终可信答案
 * 判定标准：左边表达式由本程序的精确解析器重算，与右边声明值比较（相对误差 1e-9）。
 */
static int chain_verify(const char *chain) {
    char buf[4096];                                /* 拷贝一份，避免改动入参 */
    snprintf(buf, sizeof buf, "%s", chain);
    printf("\n【推理链验证】\n");
    int step = 0, good = 0, bad = 0;               /* 统计：步数、通过、失败 */
    double last = NAN;                              /* 最后一个通过验算的值 */
    char *save = buf;                               /* 手工切分游标 */
    while (*save) {
        /* 取出一段：以 ';' 或换行分隔 */
        char *sep = save;
        while (*sep && *sep != ';' && *sep != '\n') sep++;
        char hold = *sep;                           /* 记住分隔符，稍后恢复 */
        *sep = '\0';
        char *s = save;
        while (*s == ' ' || *s == '\t') s++;         /* 跳前导空白 */
        if (*s) {                                    /* 非空段才处理 */
            step++;
            char *eq = strrchr(s, '=');              /* 找最后一个等号 */
            if (!eq) {                               /* 没有等号，说明不是算式步骤 */
                printf("  第%d步：\"%s\" → 不是算式，跳过\n", step, s);
            } else {
                *eq = '\0';                          /* 左边：表达式 */
                char *rhs = eq + 1;                  /* 右边：声称的结果 */
                while (*rhs == ' ') rhs++;
                double claimed = atof(rhs);          /* 模型声明的值 */
                double got = eval_expr(s);           /* 用精确解析器重算 */
                if (isnan(got)) {                    /* 表达式非法 */
                    printf("  第%d步：\"%s\" → 无法解析 ✘\n", step, s);
                    bad++;
                } else if (fabs(got - claimed) <= 1e-9 * fmax(1.0, fabs(got))) {
                    printf("  第%d步：%s = %.10g ✔\n", step, s, got);
                    good++;
                    last = got;                      /* 通过验算的值才能作为可信结果 */
                } else {
                    printf("  第%d步：%s = %.10g ✘（声称 %.10g，实际 %.10g）\n",
                           step, s, claimed, claimed, got);
                    bad++;
                }
            }
        }
        if (!hold) break;                            /* 到末尾了 */
        *sep = hold;                                 /* 恢复分隔符 */
        save = sep + 1;                              /* 前进到下一段 */
    }
    printf("\n【汇总】共 %d 步：通过 %d，失败 %d\n", step, good, bad);
    if (step == 0) {
        printf("【结论】没有可验证的步骤。\n");
        return 2;
    }
    if (bad == 0) {
        if (!isnan(last)) printf("【可信答案】%.10g（全部步骤通过验算）\n", last);
        else printf("【可信答案】无（步骤里没有可计算的值）\n");
        return 0;
    }
    printf("【可信答案】无（存在错误步骤，整条推理链不可信）\n");
    return 1;
}

'''

anchor = '/* ------------------------------ 入口 ------------------------------------ */'
assert anchor in t, '找不到入口'
t = t.replace(anchor, NEW + anchor, 1)

# main 分支：放在 reason 之后
old = '''    if (load_corpus(path) != 0) return 1;          /* 语料是必需的，失败就退出 */'''
new = '''    /* chain 模式用于验证推理链，同样不需要语料 */
    if (strcmp(mode, "chain") == 0) {
        if (argc < 3) {                            /* 必须给推理链 */
            fprintf(stderr, "用法: nanogpt chain \\\\\"3+5=8; 8*2=16; 16-2=14\\\\\"\\n");
            return 1;
        }
        char *c = to_utf8(argv[2]);                /* 命令行编码兼容 */
        int rc = chain_verify(c);                  /* 逐步验算 */
        free(c);
        return rc;                                 /* 0 全对，1 有错，2 无步骤 */
    }

    if (load_corpus(path) != 0) return 1;          /* 语料是必需的，失败就退出 */'''
assert old in t, '找不到 load_corpus'
t = t.replace(old, new, 1)

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('chain 验证模式已加入')
