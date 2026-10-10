"""Supervised LoRA fine-tuning of AARON-1's conversational base model.

Usage:
    python train_aaron.py --job-id <id-created-by-train-tab>

This performs REAL gradient updates to LoRA matrices via PyTorch/PEFT.
It never trains on Gmail or private chats without explicit example approval.
It downloads the open-weight base model on the first run.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

from training_data import (
    ALLOWED_BASE_MODELS, BASE_MODEL, JOB_HOME, MODEL_HOME, atomic_json,
    job_file, read_job, training_root, update_job, validate_job_id,
)

SYSTEM = (
    "You are AARON-1, a friendly, clear personal assistant. Be helpful, "
    "curious, and conversational. Never claim to have taken calendar, "
    "email, or computer actions unless the application actually did so."
)
MAX_TOKENS = 384


def encode_example(tokenizer, prompt, response, max_tokens=MAX_TOKENS):
    """Mask ALL user/system input: supervised loss is ONLY on assistant tokens.

    Kept pure for unit tests; tokenizer/model dependencies aren't imported until
    a real training run starts.
    """
    if max_tokens < 64:
        raise ValueError("max_tokens too low")
    context = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": str(prompt)},
    ]
    prefix = tokenizer.apply_chat_template(
        context, tokenize=True, add_generation_prompt=True
    )
    if not isinstance(prefix, list):
        raise ValueError("Expected tokenizer IDs for chat prefix")
    end = tokenizer.eos_token or ""
    answer = tokenizer.encode(str(response) + end, add_special_tokens=False)
    if not answer:
        raise ValueError("Example has no answer tokens")

    # Retain assistant target and the most recent prompt tokens if examples
    # overflow context. At least half the context is reserved for the answer.
    answer = answer[:max_tokens // 2]
    prefix = prefix[-(max_tokens - len(answer)):]
    ids = prefix + answer
    labels = [-100] * len(prefix) + answer
    return {"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels}


def collate_batch(items, pad_token_id, torch_module):
    """Pad labels with -100 so pad and prompt tokens never contribute to loss."""
    longest = max(len(item["input_ids"]) for item in items)
    def padding(values, pad):
        return [v + [pad] * (longest - len(v)) for v in values]
    return {
        "input_ids": torch_module.tensor(
            padding([x["input_ids"] for x in items], pad_token_id),
            dtype=torch_module.long),
        "attention_mask": torch_module.tensor(
            padding([x["attention_mask"] for x in items], 0),
            dtype=torch_module.long),
        "labels": torch_module.tensor(
            padding([x["labels"] for x in items], -100),
            dtype=torch_module.long),
    }


def train(job_id):
    """Train adapter from an explicit, frozen snapshot and save locally."""
    job_id = validate_job_id(job_id)
    job = read_job(job_id)
    if not job:
        raise ValueError("Unknown training job")
    base = job["base_model"]
    if base not in ALLOWED_BASE_MODELS:
        raise ValueError("Unsupported base model")
    snapshot = JOB_HOME / (job_id + ".dataset.json")
    if not snapshot.exists():
        raise ValueError("Approved example snapshot missing")
    dataset = json.loads(snapshot.read_text(encoding="utf-8"))
    if len(dataset["train"]) < 6 or len(dataset["eval"]) < 2:
        raise ValueError("Not enough approved training and validation examples")

    # Hardware-specific PyTorch should already be installed before this call.
    import torch
    from torch.utils.data import Dataset
    from transformers import (
        AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments,
        set_seed,
    )
    from peft import LoraConfig, TaskType, get_peft_model

    set_seed(42)
    cuda = bool(torch.cuda.is_available())  # Also true for ROCm PyTorch.
    mps = bool(hasattr(torch.backends, "mps")
               and torch.backends.mps.is_available())
    accelerator = "CUDA / ROCm" if cuda else "Apple MPS" if mps else "CPU"
    print(f"AARON-1 | Base: {base} | Compute: {accelerator}", flush=True)
    update_job(job_id, status="running", device=accelerator)
    training_root()

    tokenizer = AutoTokenizer.from_pretrained(base, trust_remote_code=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    dtype = (torch.float16 if cuda else torch.float32)
    model = AutoModelForCausalLM.from_pretrained(
        base, torch_dtype=dtype, trust_remote_code=False,
    )
    model.config.use_cache = False
    config = LoraConfig(
        r=8, lora_alpha=16, lora_dropout=0.05, bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    model = get_peft_model(model, config)
    model.print_trainable_parameters()

    class Samples(Dataset):
        def __init__(self, pairs):
            self.items = [
                encode_example(tokenizer, row["prompt"], row["response"])
                for row in pairs
            ]

        def __getitem__(self, index):
            return self.items[index]

        def __len__(self):
            return len(self.items)

    train_ds = Samples(dataset["train"])
    eval_ds = Samples(dataset["eval"])
    folder = MODEL_HOME / job_id
    folder.mkdir(parents=True, exist_ok=True)

    args = TrainingArguments(
        output_dir=str(folder / "trainer_state"),
        num_train_epochs=int(job["epochs"]),
        learning_rate=1.5e-4,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=4,
        warmup_ratio=0.05,
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        eval_strategy="epoch",
        save_strategy="no",
        logging_steps=1,
        report_to="none",
        fp16=cuda,
        bf16=False,
        dataloader_pin_memory=False,
        remove_unused_columns=False,
        disable_tqdm=True,
        seed=42,
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=lambda batch: collate_batch(
            batch, tokenizer.pad_token_id, torch
        ),
    )
    print(f"Fine-tuning {len(train_ds)} approved examples; "
          f"{len(eval_ds)} held-out evaluations.", flush=True)
    baseline = trainer.evaluate()
    print("Held-out baseline loss:",
          round(float(baseline.get("eval_loss", float("nan"))), 4), flush=True)
    result = trainer.train()
    metrics = trainer.evaluate()
    adapter_dir = folder / "adapter"
    # Adapter contains only lightweight LoRA weights + tokenizer; NOT the
    # original pretrained model (which is downloaded separately).
    model.save_pretrained(adapter_dir, safe_serialization=True)
    tokenizer.save_pretrained(adapter_dir)

    report = {
        "base_model": base, "device": accelerator,
        "train_loss": float(result.training_loss),
        "baseline_eval_loss": float(baseline.get("eval_loss", float("nan"))),
        "eval_loss": float(metrics.get("eval_loss", float("nan"))),
        "train_examples": len(train_ds), "eval_examples": len(eval_ds),
        "epochs": int(job["epochs"]),
        "note": "Evaluation loss is measured on held-out approved examples; "
                "it is not an intelligence score or guarantee of improvement.",
    }
    # Avoid nonstandard NaN in JSON metadata.
    import math
    for key in ("eval_loss", "baseline_eval_loss", "train_loss"):
        if not math.isfinite(report[key]):
            report[key] = None
    atomic_json(folder / "metrics.json", report)
    update_job(job_id, status="completed", metrics=report)
    print("TRAINING COMPLETE. Adapter saved to:", adapter_dir, flush=True)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    try:
        train(args.job_id)
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        print("TRAINING FAILED:", message, file=sys.stderr)
        traceback.print_exc()
        try:
            update_job(args.job_id, status="failed", error=message[:1000])
        except (OSError, ValueError):
            pass
        raise SystemExit(1)


if __name__ == "__main__":
    main()
