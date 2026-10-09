"""AARON-1 personal task brain: local SQLite, learned task ranking and safe imports.

This replaces the multi-agent experiments in the primary experience.
The assistant only takes actions the user explicitly requests.
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DB = DATA / "aaron_personal.sqlite3"
WEIGHTS = DATA / "priority_weights.json"
BASE_WEIGHTS = [0.1, 2.3, 1.5, 0.6, 0.7, 0.4, 1.1]
FEATURES = ("bias", "overdue", "due_today", "due_week", "school", "inbox", "starred")


def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS tasks (
      id TEXT PRIMARY KEY, title TEXT NOT NULL, due TEXT, notes TEXT,
      source TEXT NOT NULL DEFAULT 'manual', external_id TEXT,
      completed INTEGER NOT NULL DEFAULT 0,
      starred INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL)""")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS imported_task ON tasks(source,external_id) WHERE external_id IS NOT NULL")
    db.execute("""CREATE TABLE IF NOT EXISTS learning (
      id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
      label INTEGER NOT NULL, created_at TEXT NOT NULL)""")
    db.commit()
    return db


def validate_date(value):
    if value is None or str(value).strip() == "":
        return None
    value = str(value).strip()
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError as exc:
        raise ValueError("Due date must be YYYY-MM-DD") from exc


def add_task(title, due=None, notes="", source="manual", external_id=None):
    title = str(title).strip()[:250]
    if not title:
        raise ValueError("Task needs a title")
    due = validate_date(due)
    if source not in ("manual", "blackbaud", "calendar", "email"):
        raise ValueError("Unknown task source")
    identifier = str(uuid.uuid4())
    with connect() as db:
        if external_id is not None:
            exists = db.execute("SELECT id FROM tasks WHERE source=? AND external_id=?",
                                (source, str(external_id))).fetchone()
            if exists:
                return exists["id"], False
        db.execute(
            "INSERT INTO tasks (id,title,due,notes,source,external_id,created_at) VALUES (?,?,?,?,?,?,?)",
            (identifier, title, due, str(notes)[:4000], source,
             str(external_id)[:300] if external_id is not None else None,
             datetime.now(timezone.utc).isoformat()),
        )
        db.commit()
    return identifier, True


def list_tasks(include_completed=False, limit=200):
    with connect() as db:
        query = ("SELECT * FROM tasks " +
                 ("" if include_completed else "WHERE completed=0 ") +
                 "ORDER BY created_at DESC LIMIT ?")
        return [dict(x) for x in db.execute(query, (min(500, max(1, limit)),))]


def update_task(task_id, *, completed=None, starred=None):
    if completed is None and starred is None:
        return False
    with connect() as db:
        row = db.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return False
        if completed is not None:
            db.execute("UPDATE tasks SET completed=? WHERE id=?", (int(bool(completed)), task_id))
        if starred is not None:
            db.execute("UPDATE tasks SET starred=? WHERE id=?", (int(bool(starred)), task_id))
        db.commit()
    return True


def features(task, today=None):
    today = today or date.today()
    due = date.fromisoformat(task["due"]) if task.get("due") else None
    distance = (due - today).days if due else None
    return [
        1.0,
        1.0 if distance is not None and distance < 0 else 0.0,
        1.0 if distance == 0 else 0.0,
        1.0 if distance is not None and 1 <= distance <= 7 else 0.0,
        1.0 if task.get("source") in ("blackbaud", "calendar") else 0.0,
        1.0 if task.get("source") == "email" else 0.0,
        float(bool(task.get("starred", False))),
    ]


def load_weights():
    try:
        obj = json.loads(WEIGHTS.read_text(encoding="utf-8"))
        weights = obj["weights"]
        if (len(weights) == len(FEATURES) and
                all(isinstance(x, (int, float)) and math.isfinite(x) for x in weights)):
            return [float(x) for x in weights], int(obj.get("feedback_count", 0))
    except (OSError, KeyError, ValueError, TypeError):
        pass
    return BASE_WEIGHTS[:], 0


def store_weights(weights, count):
    DATA.mkdir(exist_ok=True)
    tmp = WEIGHTS.with_suffix(".tmp")
    tmp.write_text(json.dumps({"identity": "AARON-1", "weights": weights,
                               "features": FEATURES, "feedback_count": count},
                              indent=2), encoding="utf-8")
    os.replace(tmp, WEIGHTS)


def score_task(task, today=None):
    w, _ = load_weights()
    values = features(task, today=today)
    linear = sum(a*b for a, b in zip(w, values))
    return 1.0 / (1.0 + math.exp(-max(-20., min(20., linear))))


def ranked_tasks():
    return sorted(list_tasks(), key=lambda t: (score_task(t), t.get("due") or "9999-12-31"),
                  reverse=True)


def learn_priority(task_id, important):
    """Real online-learning step from task feedback, not canned examples."""
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return False
        task = dict(row)
        weights, count = load_weights()
        vector = features(task)
        predicted = score_task(task)
        label = float(bool(important))
        for i in range(len(weights)):
            weights[i] = max(-6., min(6., weights[i] + 0.28 * (label - predicted) * vector[i]))
        store_weights(weights, count+1)
        db.execute("INSERT INTO learning(task_id,label,created_at) VALUES (?,?,?)",
                   (task_id, int(label), datetime.now(timezone.utc).isoformat()))
        db.commit()
    return True


def parse_ics(data, source="blackbaud", max_events=300):
    """Parse uploaded Blackbaud calendar data; nothing fetched automatically."""
    from icalendar import Calendar
    if len(data) > 2_000_000:
        raise ValueError("Calendar file is too large (2 MB max)")
    calendar = Calendar.from_ical(data)
    count = 0
    for comp in calendar.walk("VEVENT"):
        if count >= max_events:
            break
        title = str(comp.get("summary", "")).strip()
        if not title:
            continue
        raw_due = comp.get("dtstart") or comp.get("due")
        parsed = raw_due.dt if raw_due else None
        due = parsed.date().isoformat() if isinstance(parsed, datetime) else (
            parsed.isoformat() if isinstance(parsed, date) else None)
        uid = str(comp.get("uid", "")) or None
        desc = str(comp.get("description", ""))[:4000]
        _, added = add_task(title, due=due, notes=desc, source=source,
                            external_id=uid or (title + "|" + str(due)))
        count += int(added)
    return count


def parse_csv(data, source="blackbaud", max_rows=300):
    """Read a simple CSV export with Title/Assignment and Due Date columns."""
    if len(data) > 2_000_000:
        raise ValueError("CSV is too large (2 MB max)")
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    if not reader.fieldnames:
        raise ValueError("CSV needs a header row")
    created = 0
    for index, row in enumerate(reader):
        if index >= max_rows:
            break
        normalized = {str(k).strip().lower().replace("_", " "): v for k, v in row.items() if k}
        title = next((normalized.get(k) for k in ("title", "assignment", "name", "summary")
                      if normalized.get(k)), None)
        if not title:
            continue
        due_str = next((normalized.get(k) for k in ("due date", "due", "date", "deadline")
                        if normalized.get(k)), None)
        due = None
        if due_str:
            try:
                due = validate_date(due_str)
            except ValueError:
                for fmt in ("%m/%d/%Y", "%m/%d/%y", "%b %d, %Y", "%B %d, %Y"):
                    try:
                        due = datetime.strptime(due_str.strip(), fmt).date().isoformat()
                        break
                    except ValueError:
                        continue
        external_id = (normalized.get("id") or
                       f"{title}|{due or ''}")
        _, added = add_task(title, due, source=source, external_id=external_id)
        created += int(added)
    return created


def concise_reply(message):
    """Transparent small command interface; no LLM, no fake broad comprehension."""
    message = (message or "").strip()
    lower = message.lower().strip(" !?.")
    if not message:
        return "Tell me what you want to organize."
    if lower in ("hi", "hey", "hello", "yo"):
        return "Hey! I can organize your tasks and, once connected, check your inbox."
    if re.search(r"\b(assignments|homework|due|tasks|todo|to do)\b", lower):
        tasks = ranked_tasks()[:5]
        if not tasks:
            return ("I don't have any assignments yet. Add one below, or import your "
                    "Blackbaud assignment calendar under Connections.")
        lines = [f"{idx}. {x['title']}" + (f" — due {x['due']}" if x.get("due") else "")
                 for idx, x in enumerate(tasks, 1)]
        return "Here is what I'd work on first:\n" + "\n".join(lines)
    match = re.match(r"^(?:add|remember|create) (?:task |todo )?(.+?)(?: due (\d{4}-\d\d-\d\d))?$",
                     lower, re.IGNORECASE)
    if match:
        name, due = match.groups()
        try:
            add_task(name, due=due)
        except ValueError as error:
            return str(error)
        return f"Added to your tasks: {name}" + (f" (due {due})" if due else "") + "."
    if any(term in lower for term in ("email", "inbox", "mail")):
        return ("Your inbox only becomes available after you authorize a read-only "
                "email connection under Connections. I won't send or delete mail.")
    if "learn" in lower or "train" in lower:
        return ("Every time you mark a task important or not important, my priority "
                "model updates. That's how I'm learning your priorities.")
    if lower in ("who are you", "what can you do"):
        return ("I'm AARON-1, a small local assistant. I keep your task list, learn "
                "your priorities, and can read supported accounts after you connect them.")
    return ("I'm still a small task-focused AI, not a conversational LLM. Try "
            "'what homework is due', 'add task finish chemistry', or 'check my email'.")

