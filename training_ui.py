"""AARON-1's learn-and-fine-tune dashboard.

Examples are manually approved; the training subprocess executes ON the machine
hosting this Streamlit app. No mail or school data is auto-ingested for training.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st

from ui_theme import page_heading, metric
from training_data import (
    ACTIVE_MODEL, BASE_MODEL, ALLOWED_BASE_MODELS, MIN_EXAMPLES, JOB_HOME,
    add_example, delete_example, examples, create_job, read_job,
    recent_jobs, trained_model, activate_trained, deactivate_trained,
    update_job, export_jsonl, import_jsonl,
)

PROJECT = Path(__file__).resolve().parent


def training_packages_available():
    return all(importlib.util.find_spec(name) is not None for name in (
        "torch", "transformers", "peft", "accelerate"
    ))


def launch_job(job):
    """Start exactly one bounded local job; no shell or external commands."""
    script = PROJECT / "train_aaron.py"
    if not script.is_file():
        raise RuntimeError("Training script missing")
    log = JOB_HOME / (job["id"] + ".log")
    with log.open("a", encoding="utf-8") as output:
        proc = subprocess.Popen(
            [sys.executable, "-u", str(script), "--job-id", job["id"]],
            cwd=str(PROJECT), stdin=subprocess.DEVNULL,
            stdout=output, stderr=subprocess.STDOUT,
            start_new_session=(os.name != "nt"),
        )
    update_job(job["id"], pid=proc.pid, logfile=str(log))
    return proc.pid


def _recent_pairs(history):
    pairs = []
    last_user = None
    for turn in history:
        if turn.get("role") == "user":
            last_user = str(turn.get("message", "")).strip()
        elif turn.get("role") == "assistant" and last_user:
            response = str(turn.get("message", "")).strip()
            if last_user and response:
                pairs.append((last_user, response))
            last_user = None
    return pairs[-35:][::-1]


def training_page(history):
    page_heading(
        "Personalize the language model", "Train AARON-1",
        "Teach it your preferred replies, fine-tune a small pretrained model, "
        "and activate the improved version for conversations.",
    )
    approved = examples()
    recent = recent_jobs(12)
    active = trained_model()

    a, b, c = st.columns(3, gap="medium")
    with a:
        metric("Approved examples", len(approved),
               f"Minimum {MIN_EXAMPLES} to begin")
    with b:
        metric("Training runs", len(recent), "Stored only on this machine")
    with c:
        metric("Active conversational model",
               "Trained" if active else "Base",
               "Local fine-tuned adapter" if active else "Ollama / rules")

    if active:
        st.success(
            "Trained AARON-1 is active. Choose **AARON-1 (fine-tuned)** "
            "in Chat → Conversation settings."
        )
        if st.button("Use base model instead", key="training_disable"):
            deactivate_trained()
            st.session_state.pop("aaron_selected_chat_model", None)
            st.session_state.pop("aaron_model_picker", None)
            st.rerun()
    st.caption(
        "Your planner, tasks and memories are separate from language-model "
        "weights. Fine-tuning changes how the model responds; it does not "
        "automatically give it access to apps, or make it self-training."
    )

    example_col, run_col = st.columns([1.2, 1], gap="large")
    with example_col:
        with st.container(border=True, key="examples_manual_card"):
            st.markdown("### 1 · Teach an example")
            st.caption(
                "Write a message and the answer you WANT AARON-1 to give. "
                "Only clicking Save approves this example for training."
            )
            with st.form("training_manual", clear_on_submit=True):
                question = st.text_area(
                    "When I say…", placeholder="I'm stressed about tomorrow's test",
                    height=75,
                )
                target = st.text_area(
                    "AARON-1 should reply…",
                    placeholder="That sounds rough. Want to tackle one topic at a time?",
                    height=110,
                )
                if st.form_submit_button(
                    "Save approved example", type="primary", use_container_width=True
                ):
                    try:
                        add_example(question, target)
                        st.toast("Approved example saved locally")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

            candidate = _recent_pairs(history)
            if candidate:
                with st.expander("Correct a reply from your chat"):
                    st.caption("Chat history is NOT used for training unless "
                               "you explicitly approve the edited pair here.")
                    choices = list(range(len(candidate)))
                    chosen = st.selectbox(
                        "Conversation", choices,
                        format_func=lambda i: candidate[i][0][:100],
                        key="training_pair_choose",
                    )
                    phrase, last_reply = candidate[chosen]
                    with st.form(f"training_approve_chat_{chosen}"):
                        prompt = st.text_area("Your message", value=phrase, height=85)
                        preferred = st.text_area(
                            "Corrected / approved reply", value=last_reply,
                            height=100,
                        )
                        if st.form_submit_button("Approve this reply for training"):
                            try:
                                add_example(prompt, preferred, source="approved_chat")
                                st.toast("Example approved")
                                st.rerun()
                            except ValueError as exc:
                                st.error(str(exc))

            with st.expander(f"Manage approved examples ({len(approved)})"):
                for row in approved[-120:][::-1]:
                    col, delete = st.columns([6, 1])
                    col.markdown("**" + row["prompt"].replace("<", "&lt;")[:120] + "**")
                    col.caption(row["response"][:170])
                    if delete.button(
                        "✕", key=f"training_del_{row['id']}", help="Remove example"
                    ):
                        delete_example(row["id"])
                        st.rerun()
                if len(approved) > 120:
                    st.caption("Showing the most recent 120 examples.")

            with st.expander("Transfer approved examples to your gaming PC"):
                st.caption(
                    "Export a JSONL file, then import it on your other machine. "
                    "Only explicitly approved pairs are included. "
                    "This file may contain personal details, so keep it private."
                )
                st.download_button(
                    "Export training examples", data=export_jsonl(),
                    file_name="aaron1_approved_training.jsonl",
                    mime="application/x-ndjson",
                    disabled=not bool(approved),
                    key="training_export",
                )
                uploaded = st.file_uploader(
                    "Import an approved JSONL file", type=["jsonl"],
                    key="training_upload",
                )
                if uploaded and st.button("Import approved pairs"):
                    try:
                        n = import_jsonl(uploaded.getvalue())
                        st.success(f"Imported {n} new examples.")
                        st.rerun()
                    except (ValueError, UnicodeError) as exc:
                        st.error(str(exc))

    with run_col:
        with st.container(border=True, key="training_job_card"):
            st.markdown("### 2 · Fine-tune the model")
            st.caption(
                "Real LoRA gradient training on a small open-weight Qwen model. "
                "It will use your computer and download base weights if needed."
            )
            if not training_packages_available():
                st.warning(
                    "Optional training packages are not installed. "
                    "Run the command below in your AARON-1 environment first."
                )
                st.code(
                    "python3 -m pip install -r requirements-training.txt",
                    language="bash",
                )
            else:
                st.success("Training packages found (hardware not yet verified).")

            model = st.selectbox(
                "Model to fine-tune",
                options=ALLOWED_BASE_MODELS,
                index=0,
                format_func=lambda m: (
                    "Qwen2.5 0.5B · Recommended starter"
                    if m == BASE_MODEL else
                    "Qwen2.5 1.5B · More memory and compute"
                ),
            )
            epochs = st.slider("Training passes (epochs)", min_value=1,
                               max_value=5, value=3)
            st.caption(
                "Minimum eight approved examples; 30–100+ varied corrections "
                "usually give a more meaningful signal. A few examples can "
                "overfit, and improvement is never guaranteed."
            )
            busy = any(j.get("status") in ("queued", "running") for j in recent[:10])
            disabled = (
                len(approved) < MIN_EXAMPLES or busy or
                not training_packages_available()
            )
            if st.button(
                "🧠 Train AARON-1 on this computer",
                type="primary", use_container_width=True,
                disabled=disabled, key="start_finetune",
            ):
                try:
                    job = create_job(model=model, epochs=epochs)
                    launch_job(job)
                    st.success("Training started on this computer. "
                               "Refresh its status below.")
                    st.rerun()
                except (RuntimeError, OSError, ValueError) as exc:
                    st.error(f"Could not start training: {exc}")
            if busy:
                st.info("A training job is in progress. "
                        "Only one training job can run at a time.")
            st.markdown("### 3 · Review and activate")
            if st.button("Refresh training status", key="refresh_training",
                         use_container_width=True):
                st.rerun()
            if not recent:
                st.caption("No runs yet. Your first adapter will appear here.")
            for job in recent[:5]:
                with st.expander(
                    f"{job['status'].upper()} · {job['base_model'].split('/')[-1]} "
                    f"· {job['train_count']} examples",
                    expanded=(job == recent[0]),
                ):
                    st.caption("Job " + job["id"][:12])
                    st.write(
                        f"{job['train_count']} training / {job['eval_count']} "
                        f"validation examples · {job['epochs']} epochs"
                    )
                    if job.get("device"):
                        st.caption("Hardware: " + str(job["device"]))
                    if job.get("metrics"):
                        scores = job["metrics"]
                        train_loss = scores.get("train_loss")
                        if train_loss is not None:
                            st.write(f"Training loss: {train_loss:.3f}")
                        base_loss = scores.get("baseline_eval_loss")
                        val = scores.get("eval_loss")
                        if base_loss is not None and val is not None:
                            st.write(
                                f"Held-out validation loss: {base_loss:.3f} → {val:.3f}"
                            )
                            if val > base_loss:
                                st.warning("Validation loss increased: this "
                                           "training may have made the model worse.")
                            else:
                                st.success("Lower held-out loss after training. "
                                           "Test real prompts before relying on it.")
                        st.caption("Validation loss on a tiny private dataset "
                                   "is not a general intelligence score.")
                    if job.get("error"):
                        st.error(str(job["error"]))
                    logfile = JOB_HOME / (job["id"] + ".log")
                    if logfile.is_file():
                        with st.expander("Training log"):
                            tail = logfile.read_text(
                                encoding="utf-8", errors="replace"
                            )[-6000:]
                            st.code(tail, language="text")
                    if job.get("status") == "completed":
                        is_active = active and active["job_id"] == job["id"]
                        if st.button(
                            "Use this fine-tuned AARON-1" if not is_active
                            else "Currently active ✓",
                            disabled=bool(is_active),
                            key="activate_" + job["id"], use_container_width=True,
                        ):
                            try:
                                activate_trained(job["id"])
                                st.session_state["aaron_selected_chat_model"] = (
                                    "__aaron_trained__"
                                )
                                st.session_state.pop("aaron_model_picker", None)
                                st.toast("Trained AARON-1 activated for Chat")
                                st.rerun()
                            except ValueError as exc:
                                st.error(str(exc))
        st.caption("Training runs on the PC/Mac hosting this dashboard. "
                   "If your GPU isn't supported by the installed PyTorch, "
                   "training may run on CPU and take considerably longer.")
