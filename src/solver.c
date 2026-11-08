/* ============================================================================
 * solver.c -- 中小学作业助手（纯 C 实现，不依赖 Python/PyTorch）
 *
 * 三种能力：
 *   1. 精确算术      : calc  "12+15*3"           -> 57
 *   2. 一元一次方程  : solve "2x+3=7"            -> x = 2
 *   3. 相似题检索    : ask   "一件衣服打八折..."  -> 从 19.5 万道中文应用题里
 *                      找出最相似的题目，给出它的标准答案和列式
 *
 * 检索原理：把每题转成"字符三元组"集合，用 TF-IDF 余弦相似度匹配。
 * 不支持模糊推理，只是"找到同一类题并给出标准解法"，属于检索而非计算。
 *
 * 编译: gcc -O2 -o solver.exe solver.c -lm
 * 用法: solver.exe calc "1+2*3"
 *       solver.exe solve "2x+3=7"
 *       solver.exe ask "一道题..."
 *       solver.exe            (交互模式)
 * ==========================================================================*/
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <ctype.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif

/* ------------------------- 控制台编码（Windows）-------------------------
 * 命令行参数和 stdin 在中文 Windows 上是 GBK/ANSI 编码，而题库文件是 UTF-8。
 * 这里统一转成 UTF-8，否则中文查询一个字节都对不上。 */
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

/* ============================ 精确算术 =================================== */
static const char *EP;

static double p_expr(void);

static void skipsp(void) { while (*EP == ' ' || *EP == '\t') EP++; }

static double p_primary(void) {
    skipsp();
    if (*EP == '(') { EP++; double v = p_expr(); skipsp(); if (*EP == ')') EP++; return v; }
    if (*EP == '-') { EP++; return -p_primary(); }
    if (*EP == '+') { EP++; return p_primary(); }
    char *end;
    double v = strtod(EP, &end);
    if (end == EP) { EP++; return 0.0; }
    EP = end;
    return v;
}
static double p_power(void) {
    double base = p_primary();
    for (;;) {
        skipsp();
        if (*EP == '^') { EP++; base = pow(base, p_power()); }
        else if (*EP == '%') { EP++; base = base / 100.0; }   /* 百分号是后缀：80% = 0.8 */
        else break;
    }
    return base;
}
static double p_term(void) {
    double v = p_power();
    for (;;) {
        skipsp();
        char c = *EP;
        if (c == '*' || c == '/') {
            EP++;
            double r = p_power();
            if (c == '*') v *= r;
            else v = (r == 0.0) ? NAN : v / r;
        } else if (c == 'x' || c == 'X') {
            break;                             /* 交给方程解析器 */
        } else break;
    }
    return v;
}
static double p_expr(void) {
    double v = p_term();
    for (;;) {
        skipsp();
        char c = *EP;
        if (c == '+' || c == '-') { EP++; double r = p_term(); v = (c == '+') ? v + r : v - r; }
        else break;
    }
    return v;
}

static int is_arith(const char *s) {
    int digits = 0;
    for (; *s; s++) {
        if (isdigit((unsigned char)*s)) { digits = 1; continue; }
        if (strchr("+-*/^%(). \t", *s)) continue;
        return 0;
    }
    return digits;
}
static double eval_arith(const char *s) { EP = s; return p_expr(); }

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

/* ============================ 语料与检索 ================================= */
static char *qbuf, *abuf;          /* 题库文本、答案文本 */
static long  qlen, alen;
static int  *qoff, *alen_off, *qline_len;
static long  nq;                   /* 题目数量 */

#define TMAP (1 << 22)             /* 三元组哈希表桶数 */
static unsigned *g_key;            /* 桶里的三元组 */
static int      *g_df;             /* 文档频率 */
static int      *g_last;           /* 上次出现的文档号（用于每篇只计一次） */
static int      *qoff_arr, *qlen_arr;
static int      *aoff_arr, *alen_arr;

static unsigned tri(const unsigned char *p) {
    unsigned h = 2166136261u;
    for (int i = 0; i < 3; i++) {
        unsigned char c = p[i];
        if (c >= 'A' && c <= 'Z') c = (unsigned char)(c - 'A' + 'a');
        h = (h ^ c) * 16777619u;
    }
    if (h == 0) h = 0x9e3779b9u;       /* 0 用作“空桶”哨兵，单独避开 */
    return h;
}

static int load_file(const char *path, char **buf_out, long *len_out) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "打不开文件: %s\n", path); return -1; }
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    char *buf = (char *)malloc((size_t)n + 1);
    if (fread(buf, 1, (size_t)n, f) != (size_t)n) { fclose(f); return -1; }
    buf[n] = 0; fclose(f);
    *buf_out = buf; *len_out = n;
    return 0;
}

static void index_lines(char *buf, long len, int **off_out, int **clen_out, long *count) {
    long n = 0;
    for (long i = 0; i < len; i++) if (buf[i] == '\n') n++;
    int *off = (int *)malloc(sizeof(int) * (size_t)(n + 2));
    int *cl  = (int *)malloc(sizeof(int) * (size_t)(n + 2));
    long k = 0, start = 0;
    for (long i = 0; i <= len; i++) {
        if (i == len || buf[i] == '\n') {
            off[k] = (int)start;
            cl[k]  = (int)(i - start);
            k++; start = i + 1;
        }
    }
    *off_out = off; *clen_out = cl; *count = k;
}

static void build_index(void) {
    g_key  = (unsigned *)calloc(TMAP, sizeof(unsigned));
    g_df   = (int *)calloc(TMAP, sizeof(int));
    g_last = (int *)malloc(sizeof(int) * TMAP);
    for (int i = 0; i < TMAP; i++) g_last[i] = -1;
    fprintf(stderr, "正在建立索引（%ld 道题）...\n", nq);
    for (long d = 0; d < nq; d++) {
        const unsigned char *s = (const unsigned char *)qbuf + qoff_arr[d];
        int L = qlen_arr[d];
        for (int i = 0; i + 2 < L; i++) {
            unsigned h = tri(s + i);
            unsigned b = (h * 2654435761u) & (TMAP - 1);
            while (g_key[b] && g_key[b] != h) b = (b + 1) & (TMAP - 1);
            if (!g_key[b]) g_key[b] = h;
            if (g_last[b] != (int)d) { g_last[b] = (int)d; g_df[b]++; }
        }
    }
    fprintf(stderr, "索引完成。\n");
}

/* 查一个三元组的 idf，找不到返回 0 */
static double gram_idf(unsigned h) {
    unsigned b = (h * 2654435761u) & (TMAP - 1);
    while (g_key[b]) {
        if (g_key[b] == h) {
            int df = g_df[b] ? g_df[b] : 1;
            return log((double)nq / (double)df);
        }
        b = (b + 1) & (TMAP - 1);
    }
    return 0.0;
}

/* 查询用的三元组集合（小哈希表） */
#define QMAP 512
static unsigned q_key[QMAP];
static double   q_w[QMAP];

static void query_body(const char *query, int topk) {
    memset(q_key, 0, sizeof q_key);
    unsigned char q[4096];
    int L = 0;
    for (const char *p = query; *p && L < 4095; p++) q[L++] = (unsigned char)((*p >= 'A' && *p <= 'Z') ? *p - 'A' + 'a' : *p);

    int nq_gram = 0;
    for (int i = 0; i + 2 < L; i++) {
        unsigned h = tri(q + i);
        unsigned b = (h * 2654435761u) & (QMAP - 1);
        while (q_key[b] && q_key[b] != h) b = (b + 1) & (QMAP - 1);
        if (!q_key[b]) { q_key[b] = h; q_w[b] = gram_idf(h); nq_gram++; }
    }
    if (nq_gram == 0) { printf("（输入太短，无法检索）\n"); return; }

    /* 逐题计算 TF-IDF 余弦相似度 */
    double best[8]; long bestd[8];
    for (int i = 0; i < topk; i++) { best[i] = -1; bestd[i] = -1; }

    for (long d = 0; d < nq; d++) {
        const unsigned char *s = (const unsigned char *)qbuf + qoff_arr[d];
        int DL = qlen_arr[d];
        double dot = 0.0;
        for (int i = 0; i + 2 < DL; i++) {
            unsigned h = tri(s + i);
            unsigned b = (h * 2654435761u) & (QMAP - 1);
            while (q_key[b]) {
                if (q_key[b] == h) { dot += q_w[b] * q_w[b]; break; }
                b = (b + 1) & (QMAP - 1);
            }
        }
        if (dot <= 0) continue;
        double sim = dot / sqrt((double)DL + 1.0);        /* 用长度做归一化 */
        for (int k = 0; k < topk; k++) {
            if (sim > best[k]) {
                for (int m = topk - 1; m > k; m--) { best[m] = best[m-1]; bestd[m] = bestd[m-1]; }
                best[k] = sim; bestd[k] = d;
                break;
            }
        }
    }
    printf("\n找到 %d 道最相似题：\n", topk);
    for (int k = 0; k < topk; k++) {
        if (bestd[k] < 0) continue;
        printf("\n【相似度 %.3f】题目：%.*s\n", best[k], qlen_arr[bestd[k]], qbuf + qoff_arr[bestd[k]]);
        if (bestd[k] < nq)
            printf("              答案：%.*s\n", alen_arr[bestd[k]], abuf + aoff_arr[bestd[k]]);
    }
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
    double v = eval_arith(expr);
    if (isnan(v)) return 0;
    printf("【题型】%s\n", kind);
    printf("【列式】%s = %.10g\n", expr, v);
    printf("【答案】%.10g\n", v);
    if (note && *note) printf("【依据】%s\n", note);
    printf("【核对】这一步是精确计算，你可以自己按计算器验证列式。\n");
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
        { printf("%s\n", pick_reply(greet, 4)); return 1; }
    if (has(buf, "你是谁") || has(buf, "你叫什么") || has(buf, "介绍一下"))
        { printf("%s\n", pick_reply(intro, 2)); return 1; }
    if (has(buf, "你会什么") || has(buf, "能干什么") || has(buf, "帮助") || has(buf, "怎么用") || has(buf, "help"))
        { printf("%s\n", can[0]); return 1; }
    if (has(buf, "谢谢") || has(buf, "感谢") || has(buf, "辛苦了"))
        { printf("%s\n", pick_reply(thanks, 2)); return 1; }
    if (has(buf, "再见") || has(buf, "拜拜") || has(buf, "晚安") || has(buf, "下次"))
        { printf("%s\n", pick_reply(bye, 3)); return 1; }
    if (has(buf, "时间") || has(buf, "几点")) {
        time_t t = time(NULL);
        struct tm *tm = localtime(&t);
        printf("现在是 %04d-%02d-%02d %02d:%02d。\n", tm->tm_year + 1900, tm->tm_mon + 1,
               tm->tm_mday, tm->tm_hour, tm->tm_min);
        return 1;
    }
    if (has(buf, "名字")) { printf("你可以叫我小助手。\n"); return 1; }
    if (has(buf, "开心") || has(buf, "高兴") || has(buf, "兴奋") || has(buf, "太棒"))
        { printf("%s\n", pick_reply(happy, 3)); return 1; }
    if (has(buf, "难过") || has(buf, "伤心") || has(buf, "哭") || has(buf, "委屈") || has(buf, "心情不好"))
        { printf("%s\n", pick_reply(sad, 3)); return 1; }
    if (has(buf, "累") || has(buf, "困") || has(buf, "疲惫"))
        { printf("%s\n", pick_reply(tired, 3)); return 1; }
    if (has(buf, "无聊") || has(buf, "没意思"))
        { printf("%s\n", pick_reply(bored, 3)); return 1; }
    if (has(buf, "烦") || has(buf, "生气") || has(buf, "气死") || has(buf, "讨厌"))
        { printf("%s\n", pick_reply(angry, 3)); return 1; }
    if (has(buf, "害怕") || has(buf, "紧张") || has(buf, "担心"))
        { printf("%s\n", pick_reply(scared, 3)); return 1; }
    if (has(buf, "天气") || has(buf, "下雨") || has(buf, "晴天") || has(buf, "热") || has(buf, "冷"))
        { printf("%s\n", pick_reply(weather, 3)); return 1; }
    if (has(buf, "吃饭") || has(buf, "饿") || has(buf, "吃什么"))
        { printf("%s\n", pick_reply(food, 3)); return 1; }
    if (has(buf, "作业") || has(buf, "考试") || has(buf, "学习") || has(buf, "数学") || has(buf, "考"))
        { printf("%s\n", pick_reply(study, 4)); return 1; }
    if (has(buf, "爱好") || has(buf, "喜欢") || has(buf, "唱歌") || has(buf, "画画") || has(buf, "运动") || has(buf, "游戏"))
        { printf("%s\n", pick_reply(hobby, 3)); return 1; }
    if (has(buf, "梦想") || has(buf, "未来") || has(buf, "长大"))
        { printf("%s\n", pick_reply(dream, 3)); return 1; }
    if (has(buf, "妈妈") || has(buf, "爸爸") || has(buf, "家人") || has(buf, "家庭"))
        { printf("%s\n", pick_reply(family, 2)); return 1; }
    if (has(buf, "朋友") || has(buf, "同学"))
        { printf("%s\n", pick_reply(friend_, 2)); return 1; }
    if (has(buf, "加油") || has(buf, "放弃") || has(buf, "撑不住") || has(buf, "坚持"))
        { printf("%s\n", pick_reply(cheer, 3)); return 1; }
    if (has(buf, "意义") || has(buf, "人生") || has(buf, "为什么活着"))
        { printf("%s\n", pick_reply(phil, 2)); return 1; }
    if (has(buf, "哈哈") || has(buf, "好笑") || has(buf, "逗"))
        { printf("%s\n", pick_reply(laugh, 2)); return 1; }
    if (has(buf, "厉害") || has(buf, "聪明") || has(buf, "棒"))
        { printf("谢谢夸奖！我只是把计算交给精确计算器、把题目交给题库，不装懂。\n"); return 1; }
    if (strlen(buf) <= 6) { printf("%s\n", pick_reply(shortq, 3)); return 1; }
    return 0;
}

/* ============================ 交互与入口 ================================ */
static void handle(const char *line, int topk) {
    char buf[4096];
    snprintf(buf, sizeof buf, "%s", line);
    if (!buf[0]) return;

    /* 先当闲聊处理 */
    if (chat_reply(buf)) return;

    int has_eq = strchr(buf, '=') != NULL;
    int has_x  = strchr(buf, 'x') != NULL || strchr(buf, 'X') != NULL;

    if (has_eq && has_x) {
        double x; char why[512];
        if (solve_linear(buf, &x, why, sizeof why)) {
            printf("【一元一次方程】%s\n", why);
            return;
        }
    }
    if (is_arith(buf)) {
        double v = eval_arith(buf);
        if (!isnan(v)) {
            printf("【计算】%s = %.10g\n", buf, v);
            return;
        }
        printf("【计算】除零或表达式有误\n");
        return;
    }
    /* 先让规则引擎试着直接算（精确、可核对） */
    if (try_rules(buf)) return;
    /* 规则认不出来，退回相似题检索 */
    printf("【说明】没有匹配到已知题型，下面是题库里最相似的题，仅供参考。\n");
    query_body(buf, topk);
}

int main(int argc, char **argv) {
#ifdef _WIN32
    SetConsoleOutputCP(65001);        /* 控制台按 UTF-8 输出，中文不乱码 */
#endif
    const char *qpath = "db_questions.txt";
    const char *apath = "db_answers.txt";
    const char *mode = argc > 1 ? argv[1] : "ask";

    if (load_file(qpath, &qbuf, &qlen) != 0) return 1;
    if (load_file(apath, &abuf, &alen) != 0) return 1;
    index_lines(qbuf, qlen, &qoff_arr, &qlen_arr, &nq);
    long na = 0;
    index_lines(abuf, alen, &aoff_arr, &alen_arr, &na);
    if (na < nq) nq = na;
    printf("题库: %ld 道中文数学应用题（答案 %ld 条）\n", nq, na);

    if (strcmp(mode, "calc") == 0 && argc > 2) {
        printf("%s = %.10g\n", argv[2], eval_arith(argv[2]));
        return 0;
    }
    if (strcmp(mode, "solve") == 0 && argc > 2) {
        double x; char why[512];
        if (solve_linear(argv[2], &x, why, sizeof why)) printf("【一元一次方程】%s\n", why);
        else printf("求解失败: %s\n", why);
        return 0;
    }

    build_index();

    if (argc > 2 && strcmp(mode, "ask") == 0) {
        char *q = to_utf8(argv[2]);     /* GBK -> UTF-8，否则中文对不上题库 */
        handle(q, 3);
        free(q);
        return 0;
    }

    printf("\n==============================================\n");
    printf("  AI 助手（纯 C 实现，离线运行）\n");
    printf("  直接在下面打字和我聊天，比如：\n");
    printf("    你好 / 12+15*3 / 2x+3=7 / 应用题题目\n");
    printf("  输入 quit 退出。\n");
    printf("==============================================\n");
    char line[4096];
    for (;;) {
        printf("\n> "); fflush(stdout);
        if (!fgets(line, sizeof line, stdin)) break;
        line[strcspn(line, "\r\n")] = 0;
        if (!strcmp(line, "quit") || !strcmp(line, "exit")) break;
        char *u = to_utf8(line);
        handle(u, 3);
        free(u);
    }
    return 0;
}
