"""AARON-1 Planner: tasks, timed events, deadlines and explainable priorities.

All data is kept in the existing local SQLite database. Schema upgrades
are additive: previous tasks, notes and imported schoolwork survive.
"""
from __future__ import annotations

import math
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from assistant_core import connect, score_task, learn_priority

PRIORITY_NAMES = {1: "Low", 2: "Normal", 3: "High", 4: "Urgent"}
KINDS = ("task", "event")


def ensure_schema():
    """Idempotent migration for existing users; never drops or resets data."""
    with connect() as db:
        existing = {row[1] for row in db.execute("PRAGMA table_info(tasks)")}
        upgrades = {
            "due_time": "TEXT",
            "duration_min": "INTEGER NOT NULL DEFAULT 60",
            "estimated_min": "INTEGER NOT NULL DEFAULT 30",
            "priority_level": "INTEGER NOT NULL DEFAULT 2",
            "item_type": "TEXT NOT NULL DEFAULT 'task'",
        }
        for name, decl in upgrades.items():
            if name not in existing:
                db.execute(f"ALTER TABLE tasks ADD COLUMN {name} {decl}")
        db.execute("CREATE INDEX IF NOT EXISTS idx_planner_due ON tasks(due, due_time)")
        db.commit()


def normalize_date(value):
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError as exc:
        raise ValueError("Use a valid date in YYYY-MM-DD format") from exc


def normalize_time(value):
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return f"{value.hour:02d}:{value.minute:02d}"
    try:
        return datetime.strptime(str(value).strip(), "%H:%M").strftime("%H:%M")
    except ValueError as exc:
        raise ValueError("Use a valid 24-hour time (HH:MM)") from exc


def validate_fields(*, title, due, due_time, description, item_type, priority,
                    duration_min, estimated_min):
    title = str(title).strip()
    if not title or len(title) > 250:
        raise ValueError("Title must contain 1–250 characters")
    due = normalize_date(due)
    due_time = normalize_time(due_time)
    if due_time and not due:
        raise ValueError("Choose a date before specifying a time")
    if item_type not in KINDS:
        raise ValueError("Choose either a task or calendar event")
    if item_type == "event" and not due:
        raise ValueError("Calendar events need a date")
    if len(str(description)) > 4000:
        raise ValueError("Description must be 4,000 characters or fewer")
    priority = int(priority)
    if priority not in PRIORITY_NAMES:
        raise ValueError("Priority must be between 1 and 4")
    duration_min = int(duration_min)
    estimated_min = int(estimated_min)
    if not 5 <= duration_min <= 1440:
        raise ValueError("Event duration must be between 5 and 1440 minutes")
    if not 5 <= estimated_min <= 1440:
        raise ValueError("Estimate must be between 5 and 1440 minutes")
    return dict(title=title, due=due, due_time=due_time,
                notes=str(description).strip(), item_type=item_type,
                priority_level=priority, duration_min=duration_min,
                estimated_min=estimated_min)


def create_item(*, title, due=None, due_time=None, description="",
                item_type="task", priority=2, duration_min=60, estimated_min=30):
    """Create user-authorized local calendar entry or task."""
    fields = validate_fields(
        title=title, due=due, due_time=due_time, description=description,
        item_type=item_type, priority=priority,
        duration_min=duration_min, estimated_min=estimated_min,
    )
    ensure_schema()
    uid = str(uuid.uuid4())
    with connect() as db:
        db.execute(
            """INSERT INTO tasks
              (id,title,due,due_time,notes,item_type,priority_level,duration_min,
               estimated_min,source,created_at)
              VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (uid, fields["title"], fields["due"], fields["due_time"], fields["notes"],
             fields["item_type"], fields["priority_level"], fields["duration_min"],
             fields["estimated_min"], "manual", datetime.now().isoformat()),
        )
        db.commit()
    return uid


def get_item(item_id):
    ensure_schema()
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id=?", (item_id,)).fetchone()
    return dict(row) if row else None


def update_item(item_id, *, title, due=None, due_time=None, description="",
                item_type="task", priority=2, duration_min=60, estimated_min=30):
    fields = validate_fields(
        title=title, due=due, due_time=due_time, description=description,
        item_type=item_type, priority=priority,
        duration_min=duration_min, estimated_min=estimated_min,
    )
    ensure_schema()
    with connect() as db:
        result = db.execute(
            """UPDATE tasks SET title=?,due=?,due_time=?,notes=?,item_type=?,
              priority_level=?,duration_min=?,estimated_min=? WHERE id=?""",
            (fields["title"], fields["due"], fields["due_time"], fields["notes"],
             fields["item_type"], fields["priority_level"], fields["duration_min"],
             fields["estimated_min"], item_id),
        )
        db.commit()
    return bool(result.rowcount)


def delete_item(item_id):
    """Delete only after an explicit UI click/confirmation."""
    ensure_schema()
    with connect() as db:
        result = db.execute("DELETE FROM tasks WHERE id=?", (item_id,))
        db.commit()
    return bool(result.rowcount)



def set_priority(item_id, level):
    """Explicit user feedback changes both priority and local learned preference."""
    level = int(level)
    if level not in PRIORITY_NAMES:
        raise ValueError("Priority must be 1–4")
    ensure_schema()
    with connect() as db:
        row = db.execute(
            "SELECT item_type FROM tasks WHERE id=?", (item_id,)
        ).fetchone()
        if row is None or row["item_type"] != "task":
            return False
        db.execute("UPDATE tasks SET priority_level=? WHERE id=?", (level, item_id))
        db.commit()
    learn_priority(item_id, level >= 3)
    return True


def toggle_complete(item_id, completed=True):
    ensure_schema()
    with connect() as db:
        result = db.execute("UPDATE tasks SET completed=? WHERE id=? AND item_type='task'",
                            (int(bool(completed)), item_id))
        db.commit()
    return bool(result.rowcount)


def items_for_calendar(start=None, end=None, *, include_completed=True):
    """Fetch full range, including legacy/imported tasks (not task-list limited)."""
    ensure_schema()
    filters = ["due IS NOT NULL"]
    params = []
    if start:
        filters.append("due >= ?")
        params.append(normalize_date(start))
    if end:
        filters.append("due < ?")
        params.append(normalize_date(end))
    if not include_completed:
        filters.append("completed=0")
    sql = ("SELECT * FROM tasks WHERE " + " AND ".join(filters)
           + " ORDER BY due, COALESCE(due_time, '00:00'), title")
    with connect() as db:
        rows = db.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def open_tasks(limit=1500):
    ensure_schema()
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM tasks WHERE completed=0 AND item_type='task' "
            "ORDER BY due IS NULL, due, due_time LIMIT ?",
            (min(max(int(limit), 1), 5000),),
        ).fetchall()
    return [dict(row) for row in rows]


def daily_items(day):
    ensure_schema()
    day = normalize_date(day)
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM tasks WHERE due=? ORDER BY "
            "COALESCE(due_time, '00:00'), completed, title", (day,)
        ).fetchall()
    return [dict(row) for row in rows]


def _due_datetime(item):
    if not item.get("due"):
        return None
    day = date.fromisoformat(item["due"])
    if item.get("due_time"):
        return datetime.combine(day, datetime.strptime(item["due_time"], "%H:%M").time())
    # All-day tasks are not overdue until the following day.
    return datetime.combine(day, datetime.max.time().replace(microsecond=0))


def explain_priority(task, now=None):
    """User-understandable recommendation, not a fake ML probability."""
    now = now or datetime.now()
    due = _due_datetime(task)
    priority = int(task.get("priority_level") or 2)
    score = {1: 0, 2: 19, 3: 43, 4: 72}.get(priority, 19)
    reasons = []
    if due is not None:
        seconds = (due - now).total_seconds()
        if seconds < 0:
            score += 110
            reasons.append("Overdue")
        elif seconds <= 4*3600:
            score += 104
            reasons.append("Due within 4 hours")
        elif seconds <= 24*3600:
            score += 87
            reasons.append("Due within 24 hours")
        elif seconds <= 48*3600:
            score += 63
            reasons.append("Due within 2 days")
        elif seconds <= 7*86400:
            score += 32
            reasons.append("Due this week")
        else:
            reasons.append("Scheduled ahead")
    else:
        reasons.append("No deadline set")
    if priority >= 3:
        reasons.append(PRIORITY_NAMES[priority] + " priority")
    # Include the personalized model, but don't let its synthetic training
    # outweigh real deadlines and explicit manual priority.
    try:
        score += min(16, max(0, 16*score_task(task, now.date())))
    except (ValueError, TypeError):
        pass
    estimate = int(task.get("estimated_min") or 30)
    if estimate <= 20 and score >= 60:
        score += 4
        reasons.append("Quick win")
    return round(score, 2), " · ".join(reasons)


def next_actions(limit=6, now=None):
    """Return sorted actionable tasks with transparent reasons and due labels."""
    now = now or datetime.now()
    annotated = []
    for task in open_tasks():
        score, reason = explain_priority(task, now=now)
        annotated.append({**task, "action_score": score, "why": reason})
    annotated.sort(
        key=lambda task: (-task["action_score"],
                          task.get("due") or "9999-12-31",
                          task.get("due_time") or "23:59",
                          task["title"].lower())
    )
    return annotated[:max(1, min(int(limit), 50))]


def calendar_events(items):
    """Convert tasks and events into FullCalendar's event JSON."""
    output = []
    colors = {
        1: ("#526178", "#f0f3fa"),
        2: ("#747acf", "#ffffff"),
        3: ("#edaa69", "#17151b"),
        4: ("#f07182", "#1b1118"),
    }
    for item in items:
        day = item.get("due")
        if not day:
            continue
        kind = item.get("item_type") or "task"
        is_done = bool(item.get("completed"))
        level = int(item.get("priority_level") or 2)
        bg, fg = colors.get(level, colors[2])
        if kind == "event":
            bg, fg = "#3a9c91", "#ffffff"
        if is_done:
            bg, fg = "#303c49", "#b4c1d1"
        hm = item.get("due_time")
        start = f"{day}T{hm}:00" if hm else day
        record = {
            "id": item["id"], "title": ("✓ " if is_done else "") + item["title"],
            "start": start, "allDay": not bool(hm),
            "backgroundColor": bg, "borderColor": bg, "textColor": fg,
            "extendedProps": {
                "kind": kind, "description": item.get("notes", ""),
                "priority": level, "completed": is_done,
            },
        }
        if hm:
            # A task is a deadline marker, not a one-hour meeting block.
            minutes = (int(item.get("duration_min") or 60)
                       if kind == "event" else 15)
            finish = datetime.fromisoformat(start) + timedelta(minutes=minutes)
            record["end"] = finish.isoformat(timespec="seconds")
        output.append(record)
    return output
