"""Build gui.c = nanogpt.c (neural engine) + solver.c tools + Win32 chat window."""
from pathlib import Path

DST = Path(r"C:\Users\Lenovo\ai\nanochat-demo")
WS = Path(r"C:\其它\OneDrive\文档\deepseek-harness\default-workspace")
nano = (DST / "src" / "nanogpt.c").read_text(encoding="utf-8")
solver = (DST / "src" / "solver.c").read_text(encoding="utf-8")
gui_part = (WS / "gui_part.c").read_text(encoding="utf-8")


def cut(src, start_marker, end_marker, name):
    i = src.index(start_marker)
    j = src.index(end_marker, i)
    print(f"  提取 {name}: 行 {src[:i].count(chr(10))}..{src[:j].count(chr(10))}")
    return src[i:j]


A = cut(solver, "/* ============================ 一元一次方程",
        "/* ============================ 语料与检索", "一元一次方程")
B = cut(solver, "/* ======================= 中文数字与题型规则引擎",
        "/* ====================== 闲聊应答", "题型规则引擎")
C = cut(solver, "/* ====================== 闲聊应答",
        "/* ============================ 交互与入口", "闲聊应答")


def to_rep(region: str) -> str:
    region = region.replace("snprintf(", "SNPRINTF_TMP(")
    region = region.replace("printf(", "repf(")
    region = region.replace("SNPRINTF_TMP(", "snprintf(")
    region = region.replace("eval_arith(", "eval_expr(")
    return region


B = to_rep(B)
C = to_rep(C)

# 前置声明
old_inc = "#ifdef _WIN32\n#include <windows.h>\n#endif"
new_inc = ("#ifdef _WIN32\n#include <windows.h>\n"
           "static void repf(const char *fmt, ...);\nstatic void rep(const char *s);\n#endif")
assert nano.count(old_inc) == 1
nano = nano.replace(old_inc, new_inc, 1)

idx = nano.index("/* ------------------------------ 入口")
nano = nano[:idx]

gui_c = nano + A + B + C + "\n" + gui_part + "\n"
(DST / "src" / "gui.c").write_text(gui_c, encoding="utf-8")
print("已生成 gui.c，共", gui_c.count(chr(10)), "行")
