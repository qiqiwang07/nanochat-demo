"""从 LAwPY / elements of math 两个文件夹抽取文本，生成语料。

来源：
  *.ipynb      → markdown 单元 + 代码单元
  *.py         → 源码
  *.md         → 正文
  *.pdf        → PDF 文本层（跳过纯图片页）

输出：data\book_corpus.txt（带来源标注）
"""
import json
import os
import re
import sys

from pypdf import PdfReader

ROOT = r"C:\Users\Lenovo\ai\nanochat-demo"
DIRS = [os.path.join(ROOT, "LAwPY"), os.path.join(ROOT, "elements of math")]
OUT = os.path.join(ROOT, "data", "book_corpus.txt")

MAX_PDF_MB = 60          # 跳过超大 PDF（多是图集）
skip_names = (".ipynb_checkpoints", "checkpoint")


def clean(t: str) -> str:
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def from_ipynb(path: str) -> str:
    try:
        nb = json.load(open(path, encoding="utf-8", errors="ignore"))
    except Exception:
        return ""
    parts = []
    for cell in nb.get("cells", []):
        src = cell.get("source", [])
        text = "".join(src) if isinstance(src, list) else str(src)
        if not text.strip():
            continue
        if cell.get("cell_type") == "markdown":
            parts.append(clean(text))
        elif cell.get("cell_type") == "code":
            parts.append("```python\n" + text.strip() + "\n```")
    return "\n\n".join(parts)


def from_pdf(path: str) -> str:
    try:
        if os.path.getsize(path) > MAX_PDF_MB * 1024 * 1024:
            return ""
        r = PdfReader(path)
        pages = []
        for p in r.pages[:120]:
            try:
                t = p.extract_text() or ""
            except Exception:
                continue
            t = clean(t)
            if len(t) > 40:                    # 过滤只有图/页眉的页
                pages.append(t)
        return "\n\n".join(pages)
    except Exception:
        return ""


def main() -> int:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    total = 0
    stats = {}
    with open(OUT, "w", encoding="utf-8") as f:
        for d in DIRS:
            book = os.path.basename(d)
            for dirpath, _, files in os.walk(d):
                if any(s in dirpath for s in skip_names):
                    continue
                for fn in sorted(files):
                    if any(s in fn for s in skip_names):
                        continue
                    p = os.path.join(dirpath, fn)
                    low = fn.lower()
                    if low.endswith(".ipynb"):
                        txt = from_ipynb(p)
                    elif low.endswith(".py"):
                        txt = clean(open(p, encoding="utf-8", errors="ignore").read())
                    elif low.endswith(".md"):
                        txt = clean(open(p, encoding="utf-8", errors="ignore").read())
                    elif low.endswith(".pdf"):
                        txt = from_pdf(p)
                    else:
                        continue
                    if len(txt) < 200:
                        continue
                    rel = os.path.relpath(p, ROOT)
                    f.write(f"\n\n===== 来源: {rel} =====\n\n")
                    f.write(txt)
                    total += len(txt)
                    ext = os.path.splitext(low)[1]
                    stats[ext] = stats.get(ext, 0) + len(txt)
                    print(f"  {rel}: {len(txt)} 字", flush=True)
    print(f"\n合计 {total} 字符 ≈ {total/1e6:.2f} M", flush=True)
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v/1e6:.2f} M", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
