"""Download the DeepSeek-R1 distilled 1.5B GGUF (Q4_K_M) from hf-mirror."""
import os
import sys
import urllib.request

URL = ("https://hf-mirror.com/bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF/"
       "resolve/main/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf")
DST = r"C:\Users\Lenovo\ai\models\DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf"


def main() -> int:
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    if os.path.exists(DST) and os.path.getsize(DST) > 800_000_000:
        print("model already present:", round(os.path.getsize(DST) / 1e6, 1), "MB")
        return 0
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(DST, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        print(f"size: {total / 1e6:.0f} MB", flush=True)
        n = 0
        last = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            n += len(chunk)
            if n - last >= 100 << 20:
                last = n
                print(f"  {n / 1e6:.0f} / {total / 1e6:.0f} MB", flush=True)
    print("downloaded:", round(n / 1e6, 1), "MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
