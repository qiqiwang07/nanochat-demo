#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用本地语料训练词向量（共现矩阵 + SVD），让程序具备"近义"能力。

为什么这样做：
    纯关键词匹配的死穴是"换个说法就认不出"：
    "把重复的删掉" 和 "去重" 一个字都不一样，规则匹配不上。
    有了词向量，就能算出两者的语义距离，从而识别同义说法。

训练方式（不需要任何外部模型，也不联网）：
    1. 用中文字符二元组当"词"（中文不需要分词器）
    2. 统计窗口内的共现次数
    3. 对共现矩阵做 SVD 降维，得到每个"词"的 128 维向量

输出：wordvec.npz（词表 + 向量矩阵），供 serve_r1 加载。
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus.txt")          # 主语料（教材+文学）
OUT = os.path.join(HERE, "wordvec.npz")

DIM = 128          # 向量维度
MIN_COUNT = 8      # 出现次数低于此的二元组丢掉
MAX_VOCAB = 4000   # 词表上限
WINDOW = 5         # 共现窗口


def main():
    if not os.path.exists(CORPUS):
        print("找不到语料:", CORPUS)
        return 1
    text = open(CORPUS, encoding="utf-8", errors="ignore").read()
    print("语料 %d 字符" % len(text))

    # 1) 字符级词表：中文不需要分词，字本身就是最小语义单位
    counts = {}
    for ch in text:
        if ch in "\n\r\t ":
            continue
        counts[ch] = counts.get(ch, 0) + 1

    vocab = [w for w, c in sorted(counts.items(), key=lambda x: -x[1]) if c >= MIN_COUNT][:MAX_VOCAB]
    index = {w: i for i, w in enumerate(vocab)}
    V = len(vocab)
    print("词表 %d 个字符（出现 >= %d 次）" % (V, MIN_COUNT))

    # 2) 统计共现（窗口内）
    co = np.zeros((V, V), dtype=np.float32)
    toks = [ch for ch in text if ch not in "\n\r\t "]
    for i, t in enumerate(toks):
        a = index.get(t)
        if a is None:
            continue
        for j in range(max(0, i - WINDOW), min(len(toks), i + WINDOW + 1)):
            if j == i:
                continue
            b = index.get(toks[j])
            if b is not None:
                co[a, b] += 1.0
    print("共现矩阵 %dx%d，非零 %.2f%%" % (V, V, 100.0 * np.count_nonzero(co) / (V * V)))

    # 3) 标准 PPMI：log(观测/期望)，负值截零
    total = co.sum()
    rs = co.sum(axis=1, keepdims=True)          # 行和
    cs = co.sum(axis=0, keepdims=True)          # 列和
    expected = rs @ cs / (total + 1e-9)         # 独立假设下的期望共现
    with np.errstate(divide="ignore", invalid="ignore"):
        pmi = np.log((co + 1e-9) / (expected + 1e-9))
    pmi = np.maximum(pmi, 0.0)                  # PPMI
    pmi[~np.isfinite(pmi)] = 0.0
    print("做 SVD 降维到 %d 维…" % DIM)
    u, s, _vt = np.linalg.svd(pmi, full_matrices=False)
    vecs = (u[:, :DIM] * s[:DIM]).astype(np.float32)

    # 4) 去掉第一主成分（它代表全局平均，会让所有词都像）+ 归一化
    if DIM > 1:
        u1 = vecs[:, 0:1] / (np.linalg.norm(vecs[:, 0]) + 1e-9)   # 第一主方向
        vecs = vecs - u1 @ (u1.T @ vecs)                          # 把该方向上的分量减掉
    vecs = vecs - vecs.mean(axis=0, keepdims=True)
    norm = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-6
    vecs = vecs / norm
    np.savez_compressed(OUT, vocab=np.array(vocab), vecs=vecs)
    print("已保存:", OUT, "(%.1f MB)" % (os.path.getsize(OUT) / 1e6))

    # 5) 抽查：词向量 = 各字向量的平均
    def word_vec(w):
        ids = [index[c] for c in w if c in index]
        if not ids:
            return None
        v = vecs[ids].mean(axis=0)
        return v / (np.linalg.norm(v) + 1e-6)

    for probe in ("重复", "偶数", "排序", "理想", "李白"):
        v = word_vec(probe)
        if v is None:
            print("  %s: 字都不在词表" % probe)
            continue
        sim = vecs @ v
        top = np.argsort(-sim)[:6]
        print("  %s 相近的字 → %s" % (probe, "、".join(vocab[j] for j in top)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
