"""LoRA 微调 DeepSeek-R1-Distill-Qwen-1.5B（CPU，小步试点）

用法：
    python train_lora.py --corpus <语料.txt> --steps 100 [--seq 256] [--lr 2e-4]

产物：
    适配器目录（默认 lora_adapter/），之后可合并回主权重并转 GGUF。
"""
import argparse
import os
import random
import time

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_DIR = r"C:\Users\Lenovo\ai\models\r1-distill-1.5b"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--steps", type=int, default=100)
    ap.add_argument("--seq", type=int, default=128)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--out", default="lora_adapter")
    ap.add_argument("--dtype", default="bf16", choices=["bf16", "fp32"])
    args = ap.parse_args()

    torch.set_num_threads(20)
    print(f"torch {torch.__version__} | threads {torch.get_num_threads()}", flush=True)

    text = open(args.corpus, encoding="utf-8", errors="ignore").read()
    print(f"语料 {len(text)} 字符", flush=True)

    tok = AutoTokenizer.from_pretrained(MODEL_DIR)
    print("加载模型...", flush=True)
    t0 = time.time()
    dtype = torch.bfloat16 if args.dtype == "bf16" else torch.float32
    try:                                   # transformers 5.x 用 dtype=
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_DIR, dtype=dtype, low_cpu_mem_usage=True
        )
    except TypeError:                      # 旧版本用 torch_dtype=
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_DIR, torch_dtype=dtype, low_cpu_mem_usage=True
        )
    print(f"模型加载完成 {time.time() - t0:.0f}s", flush=True)

    cfg = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, cfg)
    model.print_trainable_parameters()
    # 梯度检查点：用速度换内存（这台机器只剩 1.8GB 可用）
    try:
        model.gradient_checkpointing_enable()
        print("已启用梯度检查点（省内存）", flush=True)
    except Exception as e:
        print("梯度检查点不可用:", e, flush=True)
    model.train()

    ids = tok(text, return_tensors="pt").input_ids[0]
    print(f"语料 token 数 {len(ids)}", flush=True)
    if len(ids) < args.seq + 2:
        print("语料太短")
        return 1

    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=args.lr, betas=(0.9, 0.95))

    t1 = time.time()
    step = 0
    losses = []
    while step < args.steps:
        start = random.randrange(0, len(ids) - args.seq - 1)
        chunk = ids[start : start + args.seq + 1].unsqueeze(0)
        inputs, labels = chunk[:, :-1], chunk[:, 1:]
        out = model(input_ids=inputs, labels=labels)
        loss = out.loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
        opt.zero_grad(set_to_none=True)
        step += 1
        losses.append(loss.item())
        if step == 1 or step % 5 == 0:
            avg = sum(losses[-10:]) / len(losses[-10:])
            print(f"step {step}/{args.steps} | loss {loss.item():.4f} (近10步均值 {avg:.4f}) "
                  f"| 已用 {time.time() - t1:.0f}s | {1000 * (time.time() - t1) / step:.0f} ms/step",
                  flush=True)

    os.makedirs(args.out, exist_ok=True)
    model.save_pretrained(args.out)
    print("适配器已保存:", os.path.abspath(args.out), flush=True)
    print("最终 loss: %.4f" % (sum(losses[-20:]) / len(losses[-20:])), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
