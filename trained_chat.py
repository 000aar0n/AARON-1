"""Run the pretrained or fine-tuned AARON-1 conversational model locally.

No Ollama daemon or API key is needed. On first run, Transformers downloads the
open-weight Qwen2.5 base model from Hugging Face, then caches it locally.
After explicitly approved LoRA training, the same base can load your adapter.
"""
from __future__ import annotations

from training_data import BASE_MODEL, ALLOWED_BASE_MODELS, trained_model


def inference_dependencies_ready(*, adapter=False):
    """Only inspect package availability here; avoid loading torch during UI render."""
    from importlib.util import find_spec

    modules = ("torch", "transformers", "peft") if adapter else (
        "torch", "transformers"
    )
    return all(find_spec(name) is not None for name in modules)


def _inference_device(torch):
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load_model(base, adapter=None):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM

    if base not in ALLOWED_BASE_MODELS:
        raise ValueError("Unsupported local AARON-1 base model")
    device = _inference_device(torch)
    # On Apple MPS, float32 is the most conservative default for compatibility.
    dtype = torch.float16 if device == "cuda" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(base, trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        base, torch_dtype=dtype, trust_remote_code=False,
    )
    if adapter is not None:
        from peft import PeftModel
        model = PeftModel.from_pretrained(
            model, adapter, is_trainable=False
        )
    model.eval()
    model.to(device)
    return model, tokenizer, device


try:
    import streamlit as st

    @st.cache_resource(show_spinner="Loading AARON-1's local language model…", max_entries=2)
    def _cached_model(base, adapter, generation):
        return _load_model(base, adapter)

except ImportError:
    def _cached_model(base, adapter, generation):
        return _load_model(base, adapter)


def _generate(messages, *, base, adapter=None, generation="base",
              max_new_tokens=240):
    if not inference_dependencies_ready(adapter=bool(adapter)):
        raise RuntimeError(
            "Install the optional training dependencies first: "
            "python3 -m pip install -r requirements-training.txt"
        )

    import torch
    model, tokenizer, device = _cached_model(base, adapter, generation)
    allowed = [
        {"role": msg["role"], "content": str(msg.get("content", ""))[:4000]}
        for msg in messages[-13:]
        if msg.get("role") in ("system", "user", "assistant")
    ]
    if not allowed or allowed[-1]["role"] != "user":
        raise ValueError("Conversation must end with a user message")
    prompt = tokenizer.apply_chat_template(
        allowed, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(
        prompt, return_tensors="pt", truncation=True, max_length=1280
    )
    inputs = {name: tensor.to(device) for name, tensor in inputs.items()}
    with torch.inference_mode():
        output = model.generate(
            **inputs, max_new_tokens=max(1, min(int(max_new_tokens), 512)),
            do_sample=True, temperature=0.65, top_p=0.92,
            pad_token_id=tokenizer.pad_token_id,
        )
    answer_ids = output[0][inputs["input_ids"].shape[-1]:]
    response = tokenizer.decode(answer_ids, skip_special_tokens=True).strip()
    if not response:
        return "I couldn't produce a response. Try rephrasing your question."
    return response


def generate_base(messages, base_model=BASE_MODEL, max_new_tokens=240):
    """Chat with the already-pretrained model, even before LoRA training."""
    if base_model not in ALLOWED_BASE_MODELS:
        raise ValueError("Unsupported base model")
    return _generate(
        messages, base=base_model, adapter=None,
        generation="pretrained", max_new_tokens=max_new_tokens,
    )


def generate(messages, max_new_tokens=240):
    """Chat with the active fine-tuned model (base + user-trained LoRA)."""
    active = trained_model()
    if active is None:
        raise RuntimeError("No trained AARON-1 adapter is active")
    return _generate(
        messages, base=active["base_model"],
        adapter=active["adapter"], generation=active["job_id"],
        max_new_tokens=max_new_tokens,
    )
