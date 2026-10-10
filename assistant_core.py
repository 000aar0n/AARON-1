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
PRETRAINED = ROOT / "models" / "priority_seed.json"
LEGACY_MEMORY = DATA / "aaron_individual.sqlite3"
BASE_WEIGHTS = [0.1, 2.3, 1.5, 0.6, 0.7, 0.4, 1.1]
FEATURES = ("bias", "overdue", "due_today", "due_week", "school", "inbox", "starred")


def _configuration_value(name):
    """Read DB credentials without ever logging or checking them into Git."""
    value = os.environ.get(name, "").strip()
    if value:
        return value
    try:
        import streamlit as st
        return str(st.secrets.get(name, "") or "").strip()
    except (ImportError, FileNotFoundError, KeyError, OSError):
        return ""


def persistent_database_configured():
    """Cloud-backed SQLite is opt-in; local SQLite stays the dev default."""
    return bool(_configuration_value("TURSO_DATABASE_URL")
                and _configuration_value("TURSO_AUTH_TOKEN"))


class _MappingRow:
    """Remote DB-API row supporting both row[0] and row['title'] / dict(row)."""
    __slots__ = ("_fields", "_values")

    def __init__(self, cursor, values):
        self._fields = tuple(col[0] for col in cursor.description)
        self._values = tuple(values)

    def keys(self):
        return list(self._fields)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._fields.index(key)]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


class _RemoteClosingConnection:
    """Ensure remote transactions are committed/rolled back and then closed."""
    def __init__(self, connection):
        self._connection = connection

    def __getattr__(self, attribute):
        return getattr(self._connection, attribute)

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception, traceback):
        try:
            if exception_type:
                self._connection.rollback()
            else:
                self._connection.commit()
        finally:
            self._connection.close()
        return False


def _open_app_db():
    url = _configuration_value("TURSO_DATABASE_URL")
    token = _configuration_value("TURSO_AUTH_TOKEN")
    if bool(url) != bool(token):
        raise RuntimeError(
            "Persistent database configuration is incomplete: set BOTH "
            "TURSO_DATABASE_URL and TURSO_AUTH_TOKEN in Streamlit Secrets."
        )
    if url:
        # Choose the official Python driver for the Turso engine in use.
        # Older dashboards and CLI defaults create libSQL databases, while
        # `turso db create ... --tursodb` creates the newer Turso engine.
        # A libsql:// URL normally identifies the older engine.
        engine = _configuration_value("TURSO_DATABASE_ENGINE").lower()
        if engine not in ("", "libsql", "turso"):
            raise ValueError(
                "TURSO_DATABASE_ENGINE must be either 'turso' or 'libsql'"
            )
        if engine == "libsql" or (not engine and url.startswith("libsql://")):
            import libsql
            raw = libsql.connect(database=url, auth_token=token)
        else:
            import turso_serverless
            raw = turso_serverless.connect(url, auth_token=token)
        # Never silently use temporary SQLite on a remote connection failure.
        raw.row_factory = _MappingRow
        return _RemoteClosingConnection(raw)
    DATA.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(DB, timeout=10, factory=ClosingConnection)
    raw.row_factory = sqlite3.Row
    return raw


class ClosingConnection(sqlite3.Connection):
    """Close SQLite handles when leaving with-connect(), on every platform.

    sqlite3.Connection.__exit__ commits/rolls back but does NOT close by
    default. Windows locks still-open DB files, causing temp DB cleanup
    failures and preventing reliable backup/moves. This subclass preserves
    transaction behavior while always closing the handle after the block.
    """

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect():
    db = _open_app_db()
    db.execute("""CREATE TABLE IF NOT EXISTS tasks (
      id TEXT PRIMARY KEY, title TEXT NOT NULL, due TEXT, notes TEXT,
      source TEXT NOT NULL DEFAULT 'manual', external_id TEXT,
      completed INTEGER NOT NULL DEFAULT 0,
      starred INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL)""")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS imported_task ON tasks(source,external_id) WHERE external_id IS NOT NULL")
    db.execute("""CREATE TABLE IF NOT EXISTS memories (
      name TEXT PRIMARY KEY, value TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS migrations (
      name TEXT PRIMARY KEY, completed INTEGER NOT NULL DEFAULT 1)""")
    db.execute("""CREATE TABLE IF NOT EXISTS learning (
      id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT,
      label INTEGER NOT NULL, created_at TEXT NOT NULL)""")
    db.commit()
    return db


def migrate_legacy_facts():
    """Import only user-taught personal facts from the old database, once.

    Leaves the original chat and agent-network checkpoints untouched.
    """
    if not LEGACY_MEMORY.is_file():
        return 0
    with connect() as db:
        if db.execute("SELECT 1 FROM migrations WHERE name='legacy_facts_v1'").fetchone():
            return 0
        try:
            old = sqlite3.connect(f"file:{LEGACY_MEMORY.resolve()}?mode=ro", uri=True)
            with old:
                facts = old.execute(
                    "SELECT attribute,value FROM facts WHERE subject='user'"
                ).fetchall()
            old.close()
        except (sqlite3.DatabaseError, OSError):
            return 0
        db.executemany(
            "INSERT OR IGNORE INTO memories(name,value) VALUES (?,?)",
            [(name, value) for name, value in facts]
        )
        db.execute("INSERT INTO migrations(name) VALUES ('legacy_facts_v1')")
        db.commit()
        return len(facts)


def remember(name, value):
    key = str(name).strip().lower()[:120]
    value = str(value).strip()[:1000]
    if not key or not value:
        raise ValueError("Memory needs a name and value")
    with connect() as db:
        db.execute("INSERT OR REPLACE INTO memories(name,value) VALUES (?,?)",
                   (key, value))
        db.commit()


def recall(name):
    with connect() as db:
        result = db.execute("SELECT value FROM memories WHERE name=?",
                            (str(name).strip().lower(),)).fetchone()
    return result["value"] if result else None


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
    # Local feedback always wins; bundled pretrained baseline is loaded only
    # when the user has not trained their own policy yet.
    for path in (WEIGHTS, PRETRAINED):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
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
    return sorted(list_tasks(), key=lambda t: (-score_task(t), t.get("due") or "9999-12-31"))


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



def month_bounds(year, month):
    """Inclusive first day and exclusive next-month day (supports December)."""
    first = date(int(year), int(month), 1)
    next_month = (date(first.year + 1, 1, 1)
                  if first.month == 12 else date(first.year, first.month + 1, 1))
    return first, next_month


def change_month(first, offset):
    """Shift calendar navigation by whole months, including across years."""
    index = first.year * 12 + (first.month - 1) + int(offset)
    year, month_zero = divmod(index, 12)
    return date(year, month_zero + 1, 1)


def tasks_due_in_month(year, month, include_completed=True):
    """Get EVERY dated task for a displayed month, without the task-list cap."""
    first, after = month_bounds(year, month)
    where = "due >= ? AND due < ?"
    if not include_completed:
        where += " AND completed=0"
    with connect() as db:
        records = db.execute(
            f"SELECT * FROM tasks WHERE {where} "
            "ORDER BY due ASC, completed ASC, title COLLATE NOCASE ASC",
            (first.isoformat(), after.isoformat()),
        ).fetchall()
    return [dict(row) for row in records]


def tasks_without_due_date(limit=100):
    """Open tasks that cannot be plotted on a calendar yet."""
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM tasks WHERE due IS NULL AND completed=0 "
            "ORDER BY created_at DESC LIMIT ?", (max(1, min(int(limit), 500)),)
        ).fetchall()
    return [dict(row) for row in rows]


def set_task_due_date(task_id, due):
    """Reschedule a local task; NEVER updates an external school account."""
    normalized = validate_date(due)
    if normalized is None:
        raise ValueError("Choose a date to put this task on the calendar")
    with connect() as db:
        cursor = db.execute(
            "UPDATE tasks SET due=? WHERE id=?", (normalized, task_id)
        )
        db.commit()
    return cursor.rowcount > 0

def concise_reply(message):
    """Small transparent command parser, without pretending to know English."""
    message = (message or "").strip()
    lower = message.lower().strip(" !?.")
    if not message:
        return "Tell me what you want to organize."
    if lower in ("hi", "hey", "hello", "yo"):
        return "Hey! What homework or to-dos should I help you organize?"

    # Mutating commands must run before querying tasks; e.g. "add task math homework"
    # must never accidentally trigger the "show homework" intent.
    add = re.fullmatch(
        r"(?:add|create) (?:task |todo )?(.+?)(?: due (\d{4}-\d\d-\d\d))?",
        lower, re.IGNORECASE
    )
    if add:
        title, due = add.groups()
        try:
            add_task(title, due=due)
        except ValueError as exc:
            return str(exc)
        return f"Added: {title}" + (f", due {due}" if due else "") + "."

    fact = re.fullmatch(r"my ([\w ]{2,80}) is (.{1,250})", lower)
    question = re.fullmatch(r"what is my ([\w ]{2,80})", lower)
    if fact:
        remember(fact.group(1), fact.group(2))
        return f"I'll remember: your {fact.group(1)} is {fact.group(2)}."
    if question:
        value = recall(question.group(1))
        return (f"Your {question.group(1)} is {value}." if value
                else f"I don't know your {question.group(1)} yet.")

    if re.search(r"\b(assignments|homework|due|tasks|todo|to do)\b", lower):
        tasks = ranked_tasks()[:5]
        if not tasks:
            return ("No assignments added yet. Create a task under Tasks or "
                    "import an assignment file under Connect.")
        return "Here's what I'd prioritize:\n" + "\n".join(
            f"{idx}. {t['title']}" + (f" — due {t['due']}" if t.get("due") else "")
            for idx, t in enumerate(tasks, 1)
        )

    if any(term in lower for term in ("email", "inbox", "gmail", "mail")):
        return ("Gmail needs your permission under Connect before I can read "
                "its latest messages. I'll never send or delete mail.")
    if "learn" in lower or "train" in lower:
        return ("Mark tasks as Important or Not urgent under Tasks. "
                "My priority model learns from each decision.")
    if lower in ("who are you", "what can you do"):
        return ("I'm AARON-1, your small local assistant. I organize tasks, "
                "learn which deadlines matter to you, and read your Gmail "
                "after you authorize access.")
    return ("I can't understand every request yet. Try 'what homework is due', "
            "'add task finish chemistry', or 'check my email'.")
