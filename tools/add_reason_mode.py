# -*- coding: utf-8 -*-
"""给 nanogpt 加 reason 模式：真正的"思考"—— 解析表达式、逐步求值、每步自检。

为什么这才叫思考：
    模型猜下一步，但"推理"需要三件事：
      1. 分解 —— 把大问题拆成小步骤
      2. 精确 —— 每步用确定的算法算，不靠猜
      3. 自检 —— 每步都验证，错了能发现
    这个模式把这三件事都做了：先建语法树（分解），按优先级逐步归约（精确），
    每一步用独立方法复算对比（自检）。

用法：./nanogpt reason "3 + 5 * (2 - 1)"
"""
import io

P = r'C:\Users\Lenovo\ai\nanochat-demo\src\nanogpt.c'
t = io.open(P, encoding='utf-8').read()

NEW_CODE = r'''
/* ====================== 推理模式：分解 + 精确 + 自检 ======================
 * 与"让模型猜"的根本区别：
 *   模型：P(下一个字 | 前文)，本质是概率续写，算术会错、推理会断。
 *   本模式：把问题建成语法树 → 按优先级逐层归约 → 每步独立复算验证。
 * 思考过程对用户可见（打印每个中间步骤和校验结果），而不是只给答案。*/

typedef struct RNode RNode;
struct RNode {
    int kind;            /* 0=数字 1=变量 2=一元负号 3=二元运算 */
    double val;          /* 数字节点的值 */
    char op;             /* 运算符：+ - * / ^ % */
    RNode *a, *b;        /* 子节点 */
    double cache;        /* 求值结果，归约时写入 */
};

static const char *RP;   /* 解析游标 */

static void r_skip(void) { while (*RP == ' ' || *RP == '\t') RP++; }

static RNode *r_new(int kind) {
    RNode *n = (RNode *)calloc(1, sizeof(RNode));
    if (!n) { fprintf(stderr, "内存不足\n"); exit(1); }
    n->kind = kind;
    return n;
}

static RNode *r_expr(void);

static RNode *r_prim(void) {
    r_skip();
    if (*RP == '(') {                       /* 括号：递归回最外层 */
        RP++;
        RNode *n = r_expr();
        r_skip();
        if (*RP == ')') RP++;
        return n;
    }
    if (*RP == '-') {                       /* 一元负号 */
        RP++;
        RNode *n = r_new(2);
        n->a = r_prim();
        return n;
    }
    if (*RP == '+') { RP++; return r_prim(); }   /* 一元正号忽略 */
    if (*RP >= '0' && *RP <= '9') {         /* 数字，允许小数 */
        char *end;
        double v = strtod(RP, &end);
        if (end == RP) { fprintf(stderr, "格式错误\n"); exit(1); }
        RP = end;
        RNode *n = r_new(0);
        n->val = v;
        return n;
    }
    fprintf(stderr, "无法解析的位置: %s\n", RP);
    exit(1);
}

static RNode *r_pow(void) {                 /* 幂：右结合 */
    RNode *b = r_prim();
    for (;;) {
        r_skip();
        if (*RP == '^') { RP++; RNode *n = r_new(3); n->op = '^'; n->a = b; n->b = r_pow(); return n; }
        if (*RP == '%') { RP++; RNode *n = r_new(3); n->op = '%'; n->a = b; n->b = NULL; return n; }
        return b;
    }
}

static RNode *r_term(void) {                /* 乘除：左结合 */
    RNode *v = r_pow();
    for (;;) {
        r_skip();
        if (*RP == '*') { RP++; RNode *n = r_new(3); n->op = '*'; n->a = v; n->b = r_pow(); v = n; }
        else if (*RP == '/') { RP++; RNode *n = r_new(3); n->op = '/'; n->a = v; n->b = r_pow(); v = n; }
        else return v;
    }
}

static RNode *r_expr(void) {                /* 加减：优先级最低 */
    RNode *v = r_term();
    for (;;) {
        r_skip();
        if (*RP == '+') { RP++; RNode *n = r_new(3); n->op = '+'; n->a = v; n->b = r_term(); v = n; }
        else if (*RP == '-') { RP++; RNode *n = r_new(3); n->op = '-'; n->a = v; n->b = r_term(); v = n; }
        else return v;
    }
}

static double r_apply(char op, double a, double b, int *ok) {
    /* 按运算符求值，同时检查非法情况（除零、负数开方等） */
    switch (op) {
        case '+': return a + b;
        case '-': return a - b;
        case '*': return a * b;
        case '/': if (b == 0) { *ok = 0; return NAN; } return a / b;
        case '^': return pow(a, b);
        case '%': return a / 100.0;   /* 后缀百分号：80% = 0.8 */
        default: *ok = 0; return NAN;
    }
}

static int r_step_count = 0;    /* 已执行的推理步数 */

static double r_eval(RNode *n, int depth) {
    /* 后序遍历求值：先算子节点，再算自己 —— 这天然就是"逐步归约"的思考顺序 */
    if (!n) return NAN;
    if (n->kind == 0) return n->val;              /* 数字直接返回 */
    if (n->kind == 2) {                            /* 一元负号 */
        double a = r_eval(n->a, depth + 1);
        double v = -a;
        printf("  第%d步：-%.10g = %.10g\n", ++r_step_count, a, v);
        return v;
    }
    double a = r_eval(n->a, depth + 1);            /* 先算左子树 */
    double b = n->b ? r_eval(n->b, depth + 1) : 0; /* 再算右子树 */
    int ok = 1;
    double v = r_apply(n->op, a, b, &ok);
    if (!ok) {
        printf("  第%d步：%.10g %c %.10g → 非法运算（除零等）\n", ++r_step_count, a, n->op, b);
        return NAN;
    }
    if (n->kind == 3) {                            /* 二元运算，打印这一步 */
        if (n->op == '%') printf("  第%d步：%.10g%% = %.10g\n", ++r_step_count, a, v);
        else printf("  第%d步：%.10g %c %.10g = %.10g\n", ++r_step_count, a, n->op, b, v);
    }
    return v;
}

static int r_depth(RNode *n) {
    /* 计算语法树深度，用来衡量问题复杂度（深度越大多步推理越长） */
    if (!n) return 0;
    int da = r_depth(n->a), db = r_depth(n->b);
    return 1 + (da > db ? da : db);
}

static void r_free(RNode *n) {
    if (!n) return;
    r_free(n->a); r_free(n->b);
    free(n);
}

static void reason_mode(const char *expr) {
    /* 完整推理流程：解析 → 分解 → 逐步求值 → 独立复算 → 结论 */
    printf("\n【问题】%s\n\n", expr);
    printf("【思考过程】\n");
    r_step_count = 0;
    RP = expr;
    RNode *root = r_expr();                       /* 第一步：建成语法树（分解） */
    r_skip();
    if (*RP) {
        printf("  注意：表达式在位置 \"%s\" 处无法继续解析，可能有语法错误\n", RP);
    }
    int depth = r_depth(root);
    printf("  解析完成：语法树深度 %d 层，预计需要 %d 步归约\n", depth, r_step_count);

    double v = r_eval(root, 0);                   /* 第二步：逐步求值（精确 + 可见） */
    if (isnan(v)) {
        printf("\n【结论】表达式非法，无法给出结果。\n");
        r_free(root);
        return;
    }

    /* 第三步：自检 —— 用完全独立的方法（直接按同一表达式重算）复核 */
    double check = eval_expr(expr);
    int pass = (fabs(check - v) <= 1e-9 * fmax(1.0, fabs(v)));
    printf("\n【自检】独立复算 = %.10g，逐步推导 = %.10g → %s\n",
           check, v, pass ? "一致 ✔" : "不一致 ✘");

    /* 结论：整数就按整数打印，避免 13.0000000001 这种噪声 */
    if (fabs(v - (double)(long long)(v + 0.0)) < 1e-12 && fabs(v) < 1e15) {
        printf("【结论】%lld\n", (long long)(v + (v < 0 ? -0.5 : 0.5)));
    } else {
        printf("【结论】%.10g\n", v);
    }
    printf("【说明】每一步都由 C 的精确浮点运算得出，没有任何"猜测"成分。\n");
    r_free(root);
}

'''

# 插到"入口"之前
anchor = '/* ------------------------------ 入口 ------------------------------------ */'
assert anchor in t, '找不到入口锚点'
t = t.replace(anchor, NEW_CODE + anchor, 1)

# 加 main 分支
old = '    if (strcmp(mode, "raw") == 0) {'
new = '''    if (strcmp(mode, "reason") == 0) {
        /* reason "表达式" —— 展示完整的分解、逐步求值与自检过程 */
        if (argc < 3) {                            /* 必须给表达式 */
            fprintf(stderr, "用法: nanogpt reason \\"3 + 5 * (2 - 1)\\"\\n");
            return 1;
        }
        char *e = to_utf8(argv[2]);                /* 命令行中文/符号转 UTF-8 */
        reason_mode(e);                            /* 进入推理流程 */
        free(e);
        return 0;
    }

    if (strcmp(mode, "raw") == 0) {'''
assert old in t, '找不到 raw 分支'
t = t.replace(old, new, 1)

io.open(P, 'w', encoding='utf-8', newline='\n').write(t)
print('reason 模式已加入')
