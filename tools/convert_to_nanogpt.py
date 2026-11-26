#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Colab 训出来的 model.pt 转成 nanogpt（C 版）能读的权重文件。

C 端格式（nanogpt.c 的 save_weights）：
    8 字节魔法 "NANOGPT1"
    6 个 int32：version, NLAYER, NEMBD, NHEAD, MLP, T
    VOCAB 个 int32：每个 token id 对应的 Unicode 码点
    1 个 int32：参数张量个数 np
    然后 np 组：(名字 32 字节) + (元素数 int32) + (float32 权重) + (m) + (v)
    m/v 是 AdamW 一阶/二阶动量，推理时用不到，补零即可。

参数顺序（必须与 C 的 init_params 完全一致）：
    tok_emb
    每层：Wqkv, bqkv, Wo, bo, W1, b1, W2, b2, W3, b3
    最后：lm_head, lm_bias

用法：
    python convert_to_nanogpt.py model.pt out.bin --transpose
"""
import argparse
import struct

import numpy as np
import torch

MAGIC = b"NANOGPT1"


def flat(t, transpose=False):
    """把张量摊平成一维 float32；transpose 用于匹配 C 端的矩阵方向。"""
    a = t.detach().cpu().float()
    if transpose and a.dim() == 2:
        a = a.t().contiguous()          # C 端若是 y = x @ W 而不是 x @ W^T，就要转置
    return a.reshape(-1).numpy().astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ckpt")
    ap.add_argument("out")
    ap.add_argument("--transpose", action="store_true", help="矩阵方向不对时加这个参数")
    ap.add_argument("--ctx", type=int, default=0, help="覆盖上下文长度（默认用训练时的）")
    args = ap.parse_args()

    ck = torch.load(args.ckpt, map_location="cpu")
    sd = ck["model"]
    vocab = ck["vocab"]
    tr = ck["args"]
    nlayer, nembd, nhead, mlp = tr["nlayer"], tr["nembd"], tr["nhead"], tr["mlp"]
    ctx = args.ctx or tr["ctx"]
    V = len(vocab)

    # 按 C 端顺序收集 (名字, 一维数组)
    params = [("tok_emb", flat(sd["tok.weight"]))]
    for l in range(nlayer):
        pre = "blocks.%d." % l
        params += [
            ("L%d.Wqkv" % l, flat(sd[pre + "wqkv.weight"], args.transpose)),
            ("L%d.bqkv" % l, flat(sd[pre + "wqkv.bias"])),
            ("L%d.Wo" % l, flat(sd[pre + "wo.weight"], args.transpose)),
            ("L%d.bo" % l, flat(sd[pre + "wo.bias"])),
            ("L%d.W1" % l, flat(sd[pre + "w1.weight"], args.transpose)),
            ("L%d.b1" % l, flat(sd[pre + "w1.bias"])),
            ("L%d.W2" % l, flat(sd[pre + "w2.weight"], args.transpose)),
            ("L%d.b2" % l, flat(sd[pre + "w2.bias"])),
            ("L%d.W3" % l, flat(sd[pre + "w3.weight"], args.transpose)),
            ("L%d.b3" % l, flat(sd[pre + "w3.bias"])),
        ]
    params += [("lm_head", flat(sd["head.weight"], args.transpose)),
               ("lm_bias", flat(sd["head.bias"]))]

    # 词表码点（C 端用它把 id 还原成字符）
    cps = np.array([ord(c) for c in vocab], dtype=np.int32)

    with open(args.out, "wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<6i", 1, nlayer, nembd, nhead, mlp, ctx))
        f.write(cps.tobytes())
        f.write(struct.pack("<i", len(params)))
        for name, arr in params:
            nm = name.encode("ascii")[:31]
            nm = nm + b"\x00" * (32 - len(nm))
            f.write(nm)
            f.write(struct.pack("<i", arr.size))
            f.write(arr.tobytes())
            f.write(np.zeros(arr.size, dtype=np.float32).tobytes())   # m
            f.write(np.zeros(arr.size, dtype=np.float32).tobytes())   # v

    print("已写出:", args.out)
    print("  层数 %d | 宽度 %d | 头 %d | MLP %d | 上下文 %d | 词表 %d"
          % (nlayer, nembd, nhead, mlp, ctx, V))
    print("  参数张量 %d 个，总计 %.1fM" % (len(params), sum(a.size for _, a in params) / 1e6))
    print("\n下一步：把 %s 和语料一起放到服务器，用" % args.out)
    print('  ./nanogpt sample <语料.txt> %s "问：你的问题"' % args.out)
    print("验证能否正确生成。若输出是乱码，重跑本脚本并加上 --transpose。")


if __name__ == "__main__":
    main()
