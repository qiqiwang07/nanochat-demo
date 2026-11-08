"""Build server.c = nanogpt.c (neural engine) + solver.c tools + HTTP server."""
from pathlib import Path

DST = Path(r"C:\Users\Lenovo\ai\nanochat-demo")
WS = Path(r"C:\其它\OneDrive\文档\deepseek-harness\default-workspace")
nano = (DST / "src" / "nanogpt.c").read_text(encoding="utf-8")
solver = (DST / "src" / "solver.c").read_text(encoding="utf-8")
server_part = (WS / "server_part.c").read_text(encoding="utf-8")


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

# 工具函数里的输出改成写进回复缓冲（先保护 snprintf，再替换 printf）
def to_rep(region: str) -> str:
    region = region.replace("snprintf(", "SNPRINTF_TMP(")
    region = region.replace("printf(", "repf(")
    region = region.replace("SNPRINTF_TMP(", "snprintf(")
    region = region.replace("eval_arith(", "eval_expr(")
    return region

B = to_rep(B)
C = to_rep(C)

# winsock2 必须排在 windows.h 之前
old_inc = "#ifdef _WIN32\n#include <windows.h>\n#endif"
new_inc = ("#ifdef _WIN32\n#include <winsock2.h>\n#include <windows.h>\n"
           "#include <shellapi.h>\n"
           "static void repf(const char *fmt, ...);\nstatic void rep(const char *s);\n#endif")
assert nano.count(old_inc) == 1
nano = nano.replace(old_inc, new_inc, 1)

# 裁掉 nanogpt.c 自己的 main（从“入口”到文件尾）
idx = nano.index("/* ------------------------------ 入口")
nano = nano[:idx]

server_c = nano + A + B + C + "\n" + server_part + "\n"
(DST / "src" / "server.c").write_text(server_c, encoding="utf-8")
print("已生成 server.c，共", server_c.count(chr(10)), "行")
