#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""colab_train.py —— 在 Colab/Kaggle 的免费 GPU 上训练自研模型。

架构与本地 C 版 nanogpt 完全一致：
  RMSNorm + RoPE + SwiGLU + 多头注意力 + 字符级词表
训练完导出 model.pt 与 vocab.json，再用 convert_to_nanogpt.py 转成 C 程序能读的格式。

用法（Colab 笔记本里）：
    !python colab_train.py --data corpus.txt --steps 12000
"""
import argparse
import json
import math
import os
import time

import torch
import torch.nn as nn
import torch.nn.functional as F


# ---------------------------------------------------------------- 模型
class RMSNorm(nn.Module):
    def __init__(self, d):
        super().__init__()
        self.w = nn.Parameter(torch.ones(d))

    def forward(self, x):
        return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + 1e-6) * self.w


def rope(x, base=10000.0):
    """RoPE：对 (B, H, T, D) 的 Q/K 施加旋转位置编码。"""
    B, H, T, D = x.shape
    half = D // 2
    pos = torch.arange(T, device=x.device, dtype=torch.float32).unsqueeze(1)
    freqs = torch.exp(-math.log(base) * torch.arange(half, device=x.device, dtype=torch.float32) / half)
    ang = pos * freqs                                   # (T, half)
    cos, sin = ang.cos()[None, None], ang.sin()[None, None]
    x1, x2 = x[..., :half], x[..., half:]
    return torch.cat([x1 * cos - x2 * sin, x1 * sin + x2 * cos], dim=-1)


class Block(nn.Module):
    def __init__(self, nembd, nhead, mlp):
        super().__init__()
        self.nh = nhead
        self.dh = nembd // nhead
        self.ln1 = RMSNorm(nembd)
        self.wqkv = nn.Linear(nembd, 3 * nembd, bias=True)
        self.wo = nn.Linear(nembd, nembd, bias=True)
        self.ln2 = RMSNorm(nembd)
        self.w1 = nn.Linear(nembd, mlp, bias=True)      # 内容支路
        self.w3 = nn.Linear(nembd, mlp, bias=True)      # 门控支路
        self.w2 = nn.Linear(mlp, nembd, bias=True)

    def forward(self, x):
        B, T, C = x.shape
        h = self.ln1(x)
        qkv = self.wqkv(h).view(B, T, 3, self.nh, self.dh).permute(2, 0, 3, 1, 4)
        q, k, v = qkv[0], qkv[1], qkv[2]               # (B, H, T, dh)
        q, k = rope(q), rope(k)
        att = (q @ k.transpose(-2, -1)) / math.sqrt(self.dh)
        mask = torch.triu(torch.ones(T, T, device=x.device, dtype=torch.bool), diagonal=1)
        att = att.masked_fill(mask, float("-inf"))
        y = (att.softmax(-1) @ v).transpose(1, 2).contiguous().view(B, T, C)
        x = x + self.wo(y)
        h = self.ln2(x)
        x = x + self.w2(F.silu(self.w1(h)) * self.w3(h))   # SwiGLU
        return x


class GPT(nn.Module):
    def __init__(self, vocab, nlayer, nembd, nhead, mlp, ctx):
        super().__init__()
        self.ctx = ctx
        self.tok = nn.Embedding(vocab, nembd)
        self.blocks = nn.ModuleList([Block(nembd, nhead, mlp) for _ in range(nlayer)])
        self.ln_f = RMSNorm(nembd)
        self.head = nn.Linear(nembd, vocab, bias=True)

    def forward(self, idx, targets=None):
        x = self.tok(idx)
        for b in self.blocks:
            x = b(x)
        logits = self.head(self.ln_f(x))
        if targets is None:
            return logits, None
        loss = F.cross_entropy(logits.view(-1, logits.size(-1)), targets.reshape(-1))
        return logits, loss


# ---------------------------------------------------------------- 数据
def build_vocab(text, size=1200):
    """按字频取前 size 个字符做词表，返回 (vocab_list, encoder)。"""
    freq = {}
    for ch in text:
        freq[ch] = freq.get(ch, 0) + 1
    chars = [c for c, _ in sorted(freq.items(), key=lambda x: -x[1])][:size]
    return chars, {c: i for i, c in enumerate(chars)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="corpus.txt")
    ap.add_argument("--steps", type=int, default=12000)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--ctx", type=int, default=512)
    ap.add_argument("--nlayer", type=int, default=8)
    ap.add_argument("--nembd", type=int, default=512)
    ap.add_argument("--nhead", type=int, default=8)
    ap.add_argument("--mlp", type=int, default=1536)
    ap.add_argument("--lr", type=float, default=6e-4)
    ap.add_argument("--out", default="model.pt")
    args = ap.parse_args()

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print("设备:", dev, torch.cuda.get_device_name(0) if dev == "cuda" else "")

    text = open(args.data, encoding="utf-8", errors="ignore").read()
    print("语料 %d 字符" % len(text))
    vocab, enc = build_vocab(text, 1200)
    ids = torch.tensor([enc.get(c, 0) for c in text], dtype=torch.long)
    print("词表 %d，token %d" % (len(vocab), len(ids)))

    model = GPT(len(vocab), args.nlayer, args.nembd, args.nhead, args.mlp, args.ctx).to(dev)
    nparam = sum(p.numel() for p in model.parameters())
    print("参数量 %.1fM" % (nparam / 1e6))

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, betas=(0.9, 0.95), weight_decay=0.1)
    warm = max(1, args.steps // 20)
    t0 = time.time()
    for step in range(1, args.steps + 1):
        lr = args.lr * step / warm if step <= warm else \
            args.lr * 0.5 * (1 + math.cos(math.pi * (step - warm) / max(1, args.steps - warm)))
        for g in opt.param_groups:
            g["lr"] = lr
        ix = torch.randint(0, len(ids) - args.ctx - 1, (args.batch,))
        x = torch.stack([ids[i:i + args.ctx] for i in ix]).to(dev)
        y = torch.stack([ids[i + 1:i + 1 + args.ctx] for i in ix]).to(dev)
        _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if step % 50 == 0 or step == 1:
            el = time.time() - t0
            print("step %5d/%d  loss %.4f  lr %.2e  %.0fs  %.0f tok/s"
                  % (step, args.steps, loss.item(), lr, el,
                     step * args.batch * args.ctx / max(1, el)), flush=True)
        if step % 1000 == 0:                     # 定期存盘，断线可续
            torch.save({"model": model.state_dict(), "vocab": vocab, "args": vars(args)}, args.out)
            print("  已保存检查点", args.out, flush=True)

    torch.save({"model": model.state_dict(), "vocab": vocab, "args": vars(args)}, args.out)
    json.dump(vocab, open("vocab.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("完成，权重已保存:", args.out)


if __name__ == "__main__":
    main()
