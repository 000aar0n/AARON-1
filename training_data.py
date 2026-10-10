"""Explicit, local training examples for AARON-1.

These are *not* harvested automatically from email, schoolwork, or chat.
Only user-approved prompt/answer pairs are eligible for fine-tuning.
All persistent files live under the already-ignored data/ directory.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from assistant_core import connect, DATA

MIN_EXAMPLES = 8
MAX_EXAMPLES = 5000
BASE_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
ALLOWED_BASE_MODELS = (
    BASE_MODEL,
    "Qwen/Qwen2.5-1.5B-Instruct",
)
MODEL_HOME = DATA / "trained_models"
JOB_HOME = DATA / "training_jobs"
ACTIVE_MODEL = DATA / "active_finetune.json"


def _init(db):
    db.execute("""
      CREATE TABLE IF NOT EXISTS training_examples (
        id TEXT PRIMARY KEY,
        prompt TEXT NOT NULL,
        response TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'manual',
        created_at TEXT NOT NULL
      )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_training_created "
               "ON training_examples(created_at)")


def _validate(prompt, response):
    prompt, response = str(prompt).strip(), str(response).strip()
    if not (2 <= len(prompt) <= 2000):
        raise ValueError("Example prompt must contain 2–2,000 characters")
    if not (2 <= len(response) <= 4000):
        raise ValueError("Example response must contain 2–4,000 characters")
    return prompt, response


def add_example(prompt, response, source="manual"):
    """Only called after the user deliberately approves an example."""
    prompt, response = _validate(prompt, response)
    if source not in ("manual", "approved_chat"):
        raise ValueError("Unknown source for training example")
    identifier = str(uuid.uuid4())
    with connect() as db:
        _init(db)
        count = db.execute("SELECT count(*) FROM training_examples").fetchone()[0]
        if count >= MAX_EXAMPLES:
            raise ValueError("Training example limit reached")
        db.execute(
            "INSERT INTO training_examples(id,prompt,response,source,created_at) "
            "VALUES (?,?,?,?,?)",
            (identifier, prompt, response, source,
             datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
    return identifier


def examples():
    with connect() as db:
        _init(db)
        return [dict(row) for row in db.execute(
            "SELECT * FROM training_examples ORDER BY created_at, id"
        ).fetchall()]


def delete_example(example_id):
    with connect() as db:
        _init(db)
        result = db.execute("DELETE FROM training_examples WHERE id=?",
                            (str(example_id),))
        db.commit()
        return bool(result.rowcount)


def training_split(rows):
    """Deterministic, nonoverlapping train/eval split; never silently train on 1 pair."""
    if len(rows) < MIN_EXAMPLES:
        raise ValueError(
            f"Add at least {MIN_EXAMPLES} approved examples before fine-tuning. "
            "30–100 varied examples are more useful."
        )
    # Stable SHA-256 ordering ensures reproducible holdout with no randomness.
    import hashlib
    ranked = sorted(rows, key=lambda item: hashlib.sha256(
        (item["prompt"] + "\x00" + item["response"]).encode("utf-8")
    ).hexdigest())
    eval_count = max(2, min(30, round(len(ranked) * 0.20)))
    return ranked[eval_count:], ranked[:eval_count]


def training_root():
    MODEL_HOME.mkdir(parents=True, exist_ok=True)
    JOB_HOME.mkdir(parents=True, exist_ok=True)
    return MODEL_HOME


def validate_job_id(job_id):
    if not re.fullmatch(r"[0-9a-f]{32}", str(job_id)):
        raise ValueError("Invalid training job ID")
    return str(job_id)


def job_file(job_id):
    return JOB_HOME / (validate_job_id(job_id) + ".json")


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def create_job(model=BASE_MODEL, epochs=3):
    if model not in ALLOWED_BASE_MODELS:
        raise ValueError("Choose a supported model")
    if not isinstance(epochs, int) or not 1 <= epochs <= 5:
        raise ValueError("Epochs must be between 1 and 5")
    approved = examples()
    training, evaluation = training_split(approved)
    training_root()
    job_id = uuid.uuid4().hex
    # Freeze approved snapshot: deleting/correcting examples mid-training cannot
    # subtly change the dataset or cause cross-process database inconsistencies.
    snapshot = JOB_HOME / (job_id + ".dataset.json")
    atomic_json(snapshot, {"train": training, "eval": evaluation})
    job = {
        "id": job_id, "status": "queued", "base_model": model, "epochs": epochs,
        "train_count": len(training), "eval_count": len(evaluation),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "output": str(MODEL_HOME / job_id), "error": None,
    }
    atomic_json(job_file(job_id), job)
    return job


def update_job(job_id, *, status=None, **changes):
    path = job_file(job_id)
    if not path.is_file():
        raise ValueError("Unknown training job")
    current = json.loads(path.read_text(encoding="utf-8"))
    if status:
        if status not in ("queued", "running", "completed", "failed"):
            raise ValueError("Invalid job status")
        current["status"] = status
    current.update(changes)
    atomic_json(path, current)
    return current


def read_job(job_id):
    path = job_file(job_id)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def recent_jobs(limit=10):
    JOB_HOME.mkdir(parents=True, exist_ok=True)
    jobs = []
    for path in sorted(JOB_HOME.glob("*.json"), reverse=True):
        if len(jobs) >= limit:
            break
        if not re.fullmatch(r"[a-f0-9]{32}\.json", path.name):
            continue
        try:
            jobs.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return jobs


def trained_model():
    """Only models trained and explicitly activated here are eligible."""
    try:
        entry = json.loads(ACTIVE_MODEL.read_text(encoding="utf-8"))
        base = entry.get("base_model")
        adapter = (MODEL_HOME / validate_job_id(entry["job_id"]) / "adapter").resolve()
        if base in ALLOWED_BASE_MODELS and adapter.is_dir() and (
            adapter / "adapter_config.json"
        ).is_file() and adapter.is_relative_to(MODEL_HOME.resolve()):
            return {"base_model": base, "adapter": str(adapter),
                    "job_id": entry["job_id"]}
    except (OSError, KeyError, ValueError, TypeError):
        pass
    return None


def activate_trained(job_id):
    job = read_job(job_id)
    if not job or job.get("status") != "completed":
        raise ValueError("Only completed fine-tunings can be activated")
    directory = (MODEL_HOME / validate_job_id(job_id) / "adapter").resolve()
    if not (directory / "adapter_config.json").is_file():
        raise ValueError("Adapter weights are missing")
    atomic_json(ACTIVE_MODEL, {
        "job_id": job_id, "base_model": job["base_model"],
        "activated_at": datetime.now(timezone.utc).isoformat()
    })


def deactivate_trained():
    ACTIVE_MODEL.unlink(missing_ok=True)
