"""Merge solver.c's tools (equation solver + rule engine + small talk) into
nanogpt.c's neural chat engine, producing ai.c: one program that can do both."""
from pathlib import Path

DST = Path(r"C:\Users\Lenovo\ai\nanochat-demo")
solver = (DST / "solver.c").read_text(encoding="utf-8")
nano = (DST / "nanogpt.c").read_text(encoding="utf-8")


def cut(src, start_marker, end_marker, name):
    i = src.index(start_marker)
    j = src.index(end_marker, i)
    print(f"  提取 {name}: 行 {src[:i].count(chr(10))} .. {src[:j].count(chr(10))}")
    return src[i:j]


A = cut(solver, "/* ============================ 一元一次方程",
        "/* ============================ 语料与检索", "一元一次方程")
B = cut(solver, "/* ======================= 中文数字与题型规则引擎",
        "/* ====================== 闲聊应答", "题型规则引擎")
C = cut(solver, "/* ====================== 闲聊应答",
        "/* ============================ 交互与入口", "闲聊应答")

AI_MODE = r'''
/* ====================== 统一聊天入口 ai_mode ============================= */
static int is_arith_s(const char *s) {
    int digits = 0;
    for (; *s; s++) {
        if (isdigit((unsigned char)*s)) { digits = 1; continue; }
        if (strchr("+-*/^%(). \t", *s)) continue;
        return 0;
    }
    return digits;
}

static void ai_mode(void) {
    static char line[2048];
    static int ctx[8192];
    int n = 0;
    printf("\n==============================================\n");
    printf("  AI 助手（纯 C，离线）：想聊什么直接打字\n");
    printf("  会聊天 / 会算数 / 会解方程 / 会应用题\n");
    printf("  输入 quit 退出。\n");
    printf("==============================================\n");
    for (;;) {
        printf("\n你："); fflush(stdout);
        if (!fgets(line, sizeof line, stdin)) { printf("再见！\n"); break; }
        line[strcspn(line, "\r\n")] = 0;
        if (!strcmp(line, "quit") || !strcmp(line, "exit")) { printf("再见！\n"); break; }
        if (!line[0]) continue;
        char *u = to_utf8(line);
        char buf[4096];
        snprintf(buf, sizeof buf, "%s", u);
        free(u);
        if (chat_reply(buf)) continue;
        if (is_arith_s(buf)) {
            double v = eval_expr(buf);
            if (!isnan(v)) { printf("AI：%s = %.10g\n", buf, v); continue; }
        }
        if (strchr(buf, '=') && (strchr(buf, 'x') || strchr(buf, 'X'))) {
            double x; char why[512];
            if (solve_linear(buf, &x, why, sizeof why)) { printf("AI：x = %.6g\n", x); continue; }
        }
        if (try_rules(buf)) continue;
        n = ctx_append(ctx, n, "### User: ");
        n = ctx_append(ctx, n, buf);
        n = ctx_append(ctx, n, "\n### Assistant:");
        if (n > 6000) { int keep = 3000; memmove(ctx, ctx + (n - keep), (size_t)keep * sizeof(int)); n = keep; }
        printf("AI：");
        chat_generate(ctx, &n, 300, "\n###");
        printf("\n");
        n = ctx_append(ctx, n, "\n");
    }
}
'''

# 1) insert the merged tool code before the 入口 marker
assert nano.count("/* ------------------------------ 入口") == 1
nano = nano.replace("/* ------------------------------ 入口", A + B + C + AI_MODE + "/* ------------------------------ 入口", 1)

# 2) add the `ai` mode dispatch before the chat branch
anchor = '    if (strcmp(mode, "chat") == 0) {'
assert nano.count(anchor) == 1
dispatch = (
    '    if (strcmp(mode, "ai") == 0) {\n'
    '        /* ai <corpus> <weights.bin> */\n'
    '        if (argc < 4) { fprintf(stderr, "用法: nanogpt ai <corpus.txt> <权重.bin>\\n"); return 1; }\n'
    '        if (load_weights(argv[3]) != 0) return 1;\n'
    '        ai_mode();\n'
    '        return 0;\n'
    '    }\n\n'
)
nano = nano.replace(anchor, dispatch + anchor, 1)

# 3) chattier sampling in chat_generate: temp 0.85 -> 0.9, top-20 -> top-50
nano = nano.replace('float temp = 0.85f', 'float temp = 0.9f', 1)
nano = nano.replace('for (int r = 0; r < 19; r++)', 'for (int r = 0; r < 49; r++)', 1)

(DST / "ai.c").write_text(nano, encoding="utf-8")
print("已生成 ai.c，共", nano.count(chr(10)), "行")
