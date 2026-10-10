"""Run AARON-1's locally trained LoRA adapter for real conversations.

Uses the exact base model that the adapter was trained on. The application
does not need Ollama for this path; no cloud inference calls are made, though
the base weights may need downloading from Hugging Face on first use.
"""
from __future__ import annotations

from training_data import trained_model


def inference_dependencies_ready():
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        import peft  # noqa: F401
    except (ImportError, OSError):
        return False
    return True


def _inference_device(torch):
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load_model(base, adapter):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel

    device = _inference_device(torch)
    dtype = torch.float16 if device == "cuda" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(base, trust_remote_code=False)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        base, torch_dtype=dtype, trust_remote_code=False,
    )
    model = PeftModel.from_pretrained(model, adapter, is_trainable=False)
    model.eval()
    model.to(device)
    return model, tokenizer, device


try:
    import streamlit as st

    @st.cache_resource(show_spinner="Loading locally trained AARON-1…", max_entries=2)
    def _cached_model(base, adapter, generation):
        return _load_model(base, adapter)

except ImportError:
    def _cached_model(base, adapter, generation):
        return _load_model(base, adapter)


def generate(messages, max_new_tokens=240):
    active = trained_model()
    if active is None:
        raise RuntimeError("No trained AARON-1 adapter is active")
    if not inference_dependencies_ready():
        raise RuntimeError(
            "Install the optional fine-tuning dependencies to use the trained adapter"
        )

    import torch
    model, tokenizer, device = _cached_model(
        active["base_model"], active["adapter"], active["job_id"]
    )
    allowed = [
        {"role": msg["role"], "content": str(msg.get("content", ""))[:4000]}
        for msg in messages[-13:]
        if msg.get("role") in ("system", "user", "assistant")
    ]
    prompt = tokenizer.apply_chat_template(
        allowed, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(
        prompt, return_tensors="pt", truncation=True, max_length=1280
    )
    inputs = {name: tensor.to(device) for name, tensor in inputs.items()}
    with torch.inference_mode():
        output = model.generate(
            **inputs, max_new_tokens=int(max_new_tokens),
            do_sample=True, temperature=0.65, top_p=0.92,
            pad_token_id=tokenizer.pad_token_id,
        )
    answer_ids = output[0][inputs["input_ids"].shape[-1]:]
    response = tokenizer.decode(answer_ids, skip_special_tokens=True).strip()
    if not response:
        return "I couldn't produce a response. Try rephrasing your question."
    return response
