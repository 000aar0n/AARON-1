"""AARON-1 Planner: tasks, timed events, deadlines and explainable priorities.

All data is kept in the existing local SQLite database. Schema upgrades
are additive: previous tasks, notes and imported schoolwork survive.
"""
from __future__ import annotations

import math
import sqlite3
import uuid
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Optional

from assistant_core import connect, score_task, learn_priority

PRIORITY_NAMES = {1: "Low", 2: "Normal", 3: "High", 4: "Urgent"}
KINDS = ("task", "event")

# Consistent high-contrast colors for readable calendar event labels.
EVENT_COLORS = {
    "Auto": None, "Blue": "#215AAB", "Purple": "#6246AE",
    "Teal": "#126B71", "Green": "#396D35", "Orange": "#965013",
    "Pink": "#9B356C", "Red": "#9C3545", "Slate": "#425269",
}
AUTO_PRIORITY_COLORS = {1: "Slate", 2: "Purple", 3: "Orange", 4: "Red"}



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
            "event_end": "TEXT",
            "color_name": "TEXT NOT NULL DEFAULT 'Auto'",
            "repeat_weekly": "INTEGER NOT NULL DEFAULT 0",
            "repeat_until": "TEXT",
            "linked_event_id": "TEXT",
            # A school-wide Google export is NOT proof of enrollment.
            "personal_status": "TEXT NOT NULL DEFAULT 'unverified'",
        }
        for name, decl in upgrades.items():
            if name not in existing:
                db.execute(f"ALTER TABLE tasks ADD COLUMN {name} {decl}")
        db.execute("CREATE INDEX IF NOT EXISTS idx_planner_due ON tasks(due, due_time)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_linked_assignments ON tasks(linked_event_id)")
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
                    duration_min, estimated_min, color_name="Auto",
                    repeat_weekly=False, repeat_until=None, linked_event_id=None):
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
    color_name = str(color_name or "Auto")
    if color_name not in EVENT_COLORS:
        raise ValueError("Choose a color from the available palette")
    if repeat_weekly and item_type != "event":
        raise ValueError("Only calendar events can repeat weekly")
    repeat_weekly = bool(repeat_weekly)
    repeat_until = normalize_date(repeat_until) if repeat_weekly else None
    if repeat_weekly:
        if repeat_until is None:
            raise ValueError("Choose an end date for the weekly series")
        days = (date.fromisoformat(repeat_until) - date.fromisoformat(due)).days
        if days < 0 or days > 1095:
            raise ValueError("Weekly events must end within three years of the first event")
    linked_event_id = str(linked_event_id or "").strip() or None
    if linked_event_id and item_type != "task":
        raise ValueError("Only tasks can be attached to a calendar event")
    return dict(title=title, due=due, due_time=due_time,
                notes=str(description).strip(), item_type=item_type,
                priority_level=priority, duration_min=duration_min,
                estimated_min=estimated_min, color_name=color_name,
                repeat_weekly=int(repeat_weekly), repeat_until=repeat_until,
                linked_event_id=linked_event_id)


def _validate_link(db, fields, *, updating_id=None):
    linked = fields["linked_event_id"]
    if linked and linked == updating_id:
        raise ValueError("An event cannot be attached to itself")
    if linked:
        record = db.execute(
            "SELECT id FROM tasks WHERE id=? AND item_type='event'", (linked,)
        ).fetchone()
        if record is None:
            raise ValueError("Choose an existing calendar event to link the assignment")


def create_item(*, title, due=None, due_time=None, description="",
                item_type="task", priority=2, duration_min=60, estimated_min=30,
                color_name="Auto", repeat_weekly=False, repeat_until=None,
                linked_event_id=None):
    """Create user-authorized local calendar entry or task."""
    fields = validate_fields(
        title=title, due=due, due_time=due_time, description=description,
        item_type=item_type, priority=priority,
        duration_min=duration_min, estimated_min=estimated_min,
        color_name=color_name, repeat_weekly=repeat_weekly,
        repeat_until=repeat_until, linked_event_id=linked_event_id,
    )
    ensure_schema()
    uid = str(uuid.uuid4())
    with connect() as db:
        _validate_link(db, fields)
        db.execute(
            """INSERT INTO tasks
              (id,title,due,due_time,notes,item_type,priority_level,duration_min,
               estimated_min,color_name,repeat_weekly,repeat_until,
               linked_event_id,source,created_at)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uid, fields["title"], fields["due"], fields["due_time"], fields["notes"],
             fields["item_type"], fields["priority_level"], fields["duration_min"],
             fields["estimated_min"], fields["color_name"], fields["repeat_weekly"],
             fields["repeat_until"], fields["linked_event_id"],
             "manual", datetime.now().isoformat()),
        )
        db.commit()
    return uid


def is_verified_personal(item):
    """Only explicitly accepted Google events can be called *your* classes.

    Locally entered work, Winter Arc sessions, and other direct user-authorized
    items keep working. Unverified / rejected imported Google events never
    appear in personal schedule answers or language-model context.
    """
    if str(item.get("personal_status") or "") == "not_mine":
        return False
    if item.get("source") == "google_calendar":
        return item.get("personal_status") == "mine"
    return True


def imported_series_key(external_id):
    """Exact calendar-source+UID prefix, regardless of ISO time colons.

    Google importer keys look like source:uid:T:2026-10-12T14:00:00+00:00
    or source:uid:D:2026-10-12; rsplit(':', 1) would erroneously group by
    timezone seconds rather than the event UID.
    """
    raw = str(external_id or "")
    for marker in (":T:", ":D:"):
        if marker in raw:
            return raw.rsplit(marker, 1)[0]
    return raw.rsplit(":", 1)[0]


def review_imported_groups(*, search="", limit=75):
    """Group incoming Google events by source calendar + iCal UID.

    Each recurrence usually expands into many instance rows sharing a UID.
    Group by UID rather than by titles so distinct sections / teachers remain
    separate; no personal calendar data leaves the local database.
    """
    ensure_schema()
    with connect() as db:
        imported = [
            dict(r) for r in db.execute(
                "SELECT id, title, due, due_time, notes, external_id, "
                "personal_status FROM tasks "
                "WHERE source='google_calendar' AND item_type='event' "
                "ORDER BY due, due_time, title"
            ).fetchall()
        ]
    groups = {}
    needle = " ".join(str(search).casefold().split())
    for item in imported:
        text_value = (item["title"] + " " + (item.get("notes") or "")).casefold()
        if needle and needle not in text_value:
            continue
        key = imported_series_key(item.get("external_id") or item["id"])
        group = groups.get(key)
        if group is None:
            groups[key] = {
                "id": item["id"],
                "title": item["title"],
                "first_date": item["due"],
                "time": item.get("due_time"),
                "notes": item.get("notes") or "",
                "status": item.get("personal_status") or "unverified",
                "occurrences": 1,
            }
        else:
            group["occurrences"] += 1
    # Prefer upcoming series, then recently finished classes, rather than
    # forcing users to scroll through years of old school-calendar exports.
    today = date.today().isoformat()
    ordered = sorted(
        groups.values(),
        key=lambda group: (
            group["first_date"] < today,
            group["first_date"] if group["first_date"] >= today
            else "".join(chr(255 - ord(c)) for c in group["first_date"]),
            group["title"].casefold(),
        ),
    )
    return ordered[:max(1, min(limit, 1000))]


def set_imported_personal_status(item_id, status):
    """Mark a school calendar event and all instances with the same UID.

    Explicit action only. Does not affect external Google, source records,
    manual tasks, or unrelated class sections with different UIDs.
    """
    if status not in ("mine", "not_mine", "unverified"):
        raise ValueError("Unknown confirmation status")
    ensure_schema()
    with connect() as db:
        row = db.execute(
            "SELECT external_id FROM tasks WHERE id=? "
            "AND source='google_calendar' AND item_type='event'", (item_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Choose an imported calendar event")
        identifier = str(row["external_id"] or "")
        if not identifier:
            ids = [item_id]
        else:
            series = imported_series_key(identifier)
            ids = [
                current["id"] for current in db.execute(
                    "SELECT id, external_id FROM tasks "
                    "WHERE source='google_calendar' AND item_type='event'"
                ).fetchall()
                if imported_series_key(current["external_id"]) == series
            ]
        db.executemany(
            "UPDATE tasks SET personal_status=? WHERE id=?",
            [(status, value) for value in ids],
        )
        db.commit()
    return len(ids)


def imported_review_counts():
    ensure_schema()
    with connect() as db:
        return {
            status: int(db.execute(
                "SELECT COUNT(*) FROM tasks WHERE source='google_calendar' "
                "AND item_type='event' AND personal_status=?", (status,)
            ).fetchone()[0])
            for status in ("unverified", "mine", "not_mine")
        }


def get_item(item_id):
    ensure_schema()
    with connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id=?", (item_id,)).fetchone()
    return dict(row) if row else None


def update_item(item_id, *, title, due=None, due_time=None, description="",
                item_type="task", priority=2, duration_min=60, estimated_min=30,
                color_name="Auto", repeat_weekly=False, repeat_until=None,
                linked_event_id=None):
    fields = validate_fields(
        title=title, due=due, due_time=due_time, description=description,
        item_type=item_type, priority=priority,
        duration_min=duration_min, estimated_min=estimated_min,
        color_name=color_name, repeat_weekly=repeat_weekly,
        repeat_until=repeat_until, linked_event_id=linked_event_id,
    )
    ensure_schema()
    with connect() as db:
        _validate_link(db, fields, updating_id=item_id)
        # Converting an event into a task detaches its assignment relationships.
        if item_type != "event":
            db.execute("UPDATE tasks SET linked_event_id=NULL WHERE linked_event_id=?", (item_id,))
        result = db.execute(
            """UPDATE tasks SET title=?,due=?,due_time=?,notes=?,item_type=?,
              priority_level=?,duration_min=?,estimated_min=?,event_end=NULL,
              color_name=?,repeat_weekly=?,repeat_until=?,linked_event_id=?
              WHERE id=?""",
            (fields["title"], fields["due"], fields["due_time"], fields["notes"],
             fields["item_type"], fields["priority_level"], fields["duration_min"],
             fields["estimated_min"], fields["color_name"], fields["repeat_weekly"],
             fields["repeat_until"], fields["linked_event_id"], item_id),
        )
        db.commit()
    return bool(result.rowcount)


def delete_item(item_id):
    """Delete only after an explicit UI click/confirmation."""
    ensure_schema()
    with connect() as db:
        db.execute("UPDATE tasks SET linked_event_id=NULL WHERE linked_event_id=?", (item_id,))
        result = db.execute("DELETE FROM tasks WHERE id=?", (item_id,))
        db.commit()
    return bool(result.rowcount)




def all_tasks(*, include_completed=True, limit=3000):
    """Task-only list; includes completed items so users can delete old work."""
    ensure_schema()
    clauses = ["item_type='task'"]
    if not include_completed:
        clauses.append("completed=0")
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM tasks WHERE " + " AND ".join(clauses) +
            " ORDER BY completed, due IS NULL, due, due_time, created_at DESC "
            "LIMIT ?",
            (min(max(int(limit), 1), 10000),),
        ).fetchall()
    return [dict(row) for row in rows]


def manually_added_task_count():
    """Count tasks user created in AARON-1, including completed tasks.

    Imported Blackbaud/calendar tasks, Gmail-sourced tasks, and all events are
    *never* included in this bulk-deletion scope.
    """
    ensure_schema()
    with connect() as db:
        return int(db.execute(
            "SELECT COUNT(*) FROM tasks WHERE source='manual' AND item_type='task'"
        ).fetchone()[0])


def clear_manually_added_tasks(*, expected_count):
    """Back up the SQLite database and clear only user-authored tasks.

    Must be called after a dedicated confirmed UI action, never at startup.
    expected_count is checked under a write lock to avoid deleting an
    unexpectedly changed set of tasks from a stale dashboard.
    Returns (deleted_count, local_backup_path_or_None).
    """
    ensure_schema()
    if isinstance(expected_count, bool) or not isinstance(expected_count, int):
        raise ValueError("Expected task count must be a nonnegative integer")
    if expected_count < 0:
        raise ValueError("Expected task count must be a nonnegative integer")
    with connect() as db:
        sql = "source='manual' AND item_type='task'"
        count = int(db.execute(
            "SELECT COUNT(*) FROM tasks WHERE " + sql
        ).fetchone()[0])
        if count != expected_count:
            raise ValueError(
                "Your task list changed since you opened this confirmation. "
                "Refresh and review the count before deleting."
            )
        if count == 0:
            return 0, None

        # SQLite's backup API produces a consistent, restorable snapshot,
        # including memory, Gmail-derived tasks, completed tasks and chat.
        original = next(row["file"] for row in db.execute("PRAGMA database_list")
                        if row["name"] == "main")
        backup_dir = Path(original).resolve().parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        filename = (
            "aaron_personal-before-manual-task-clear-" +
            datetime.now().strftime("%Y%m%d-%H%M%S") + "-" +
            uuid.uuid4().hex[:8] + ".sqlite3"
        )
        backup_path = backup_dir / filename
        with sqlite3.connect(backup_path) as backup_db:
            db.backup(backup_db)

        # Serialize the final check and DELETE in one local transaction.
        db.execute("BEGIN IMMEDIATE")
        rechecked = int(db.execute(
            "SELECT COUNT(*) FROM tasks WHERE " + sql
        ).fetchone()[0])
        if rechecked != expected_count:
            db.rollback()
            raise ValueError(
                "Your task list changed during deletion. No tasks were removed."
            )
        deleted = db.execute(
            "DELETE FROM tasks WHERE " + sql
        ).rowcount
        db.commit()
    return deleted, str(backup_path)


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
    """Return calendar records, including series overlapping the requested range.

    Weekly series is stored once and expanded into displayed occurrences by
    calendar_events(). Legacy/imported single-instance rows stay unchanged.
    """
    ensure_schema()
    filters = ["due IS NOT NULL"]
    params = []
    if start:
        day = normalize_date(start)
        filters.append("(due >= ? OR (item_type='event' AND repeat_weekly=1 "
                       "AND repeat_until >= ?))")
        params.extend((day, day))
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


def linkable_events(limit=5000):
    """Searchable dropdown choices, including imported appointments."""
    ensure_schema()
    with connect() as db:
        rows = db.execute(
            "SELECT id,title,due,due_time,repeat_weekly,repeat_until,color_name "
            "FROM tasks WHERE item_type='event' ORDER BY due DESC, title LIMIT ?",
            (max(1, min(int(limit), 10000)),),
        ).fetchall()
    return [dict(row) for row in rows]


def related_assignments(event_id):
    """Tasks explicitly linked to an event or its entire weekly series."""
    ensure_schema()
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM tasks WHERE item_type='task' AND linked_event_id=? "
            "ORDER BY completed,due IS NULL,due,title",
            (event_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def effective_color_name(item, event_colors=None):
    picked = str(item.get("color_name") or "Auto")
    if picked in EVENT_COLORS and picked != "Auto":
        return picked
    if (item.get("item_type") or "task") == "event":
        if item.get("source") == "winter_arc":
            return "Green"
        if item.get("source") == "google_calendar":
            return "Blue"
        return "Teal"
    linked = item.get("linked_event_id")
    if linked:
        parent = (event_colors or {}).get(linked)
        if parent:
            return parent
        row = get_item(linked)
        if row and row.get("item_type") == "event":
            return effective_color_name(row)
    return AUTO_PRIORITY_COLORS.get(int(item.get("priority_level") or 2), "Purple")


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
            "SELECT * FROM tasks WHERE due=? OR "
            "(item_type='event' AND repeat_weekly=1 AND due<=? AND repeat_until>=?) "
            "ORDER BY COALESCE(due_time, '00:00'), completed, title",
            (day, day, day),
        ).fetchall()
    answer = []
    on_day = date.fromisoformat(day)
    for row in rows:
        task = dict(row)
        if task.get("repeat_weekly") and task["due"] != day:
            if date.fromisoformat(task["due"]).weekday() != on_day.weekday():
                continue
            task["due"] = day
            task["occurrence_date"] = day
        answer.append(task)
    return answer


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


def _occurrence_days(item, start=None, end=None):
    """Iterate a single weekly series (at most 157 instances), bounded by dates."""
    first = date.fromisoformat(item["due"])
    if not item.get("repeat_weekly") or item.get("item_type") != "event":
        if (start is None or first >= normalize_as_date(start)) and (
            end is None or first < normalize_as_date(end)
        ):
            yield first
        return
    last = date.fromisoformat(item["repeat_until"])
    if start is not None:
        first_visible = normalize_as_date(start)
        if first_visible > first:
            first += timedelta(days=7 * (((first_visible - first).days + 6) // 7))
    if end is not None:
        last = min(last, normalize_as_date(end) - timedelta(days=1))
    # A three-year max series bound is enforced by validate_fields().
    for count in range(158):
        day = first + timedelta(days=7 * count)
        if day > last:
            break
        yield day


def normalize_as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(normalize_date(value))


def calendar_events(items, *, start=None, end=None):
    """Materialize weekly occurrences while keeping one editable parent event."""
    items = list(items)
    output = []
    event_colors = {
        item["id"]: effective_color_name(item)
        for item in items if item.get("item_type") == "event"
    }
    for item in items:
        if not item.get("due"):
            continue
        kind = item.get("item_type") or "task"
        is_done = bool(item.get("completed"))
        color_name = effective_color_name(item, event_colors)
        bg = EVENT_COLORS[color_name]
        fg = "#FFFFFF"
        if is_done:
            bg, fg = "#303C49", "#D2DBE6"
        hm = item.get("due_time")
        for occurrence in _occurrence_days(item, start=start, end=end):
            day = occurrence.isoformat()
            calendar_id = (
                item["id"] + "::" + day if item.get("repeat_weekly") else item["id"]
            )
            title_prefix = (
                "✓ " if is_done else "↻ " if item.get("repeat_weekly")
                else "📎 " if item.get("linked_event_id") else ""
            )
            start_at = f"{day}T{hm}:00" if hm else day
            record = {
                "id": calendar_id, "title": title_prefix + item["title"],
                "start": start_at, "allDay": not bool(hm),
                "backgroundColor": bg, "borderColor": bg,
                "textColor": fg,
                "extendedProps": {
                    "kind": kind, "description": item.get("notes", ""),
                    "priority": int(item.get("priority_level") or 2),
                    "completed": is_done, "color": color_name,
                    "linkedEventId": item.get("linked_event_id"),
                    "seriesId": item["id"],
                    "occurrenceDate": day,
                },
            }
            if item.get("event_end") and kind == "event" and not item.get("repeat_weekly"):
                record["end"] = item["event_end"]
            elif hm:
                minutes = (int(item.get("duration_min") or 60)
                           if kind == "event" else 15)
                record["end"] = (
                    datetime.fromisoformat(start_at) + timedelta(minutes=minutes)
                ).isoformat(timespec="seconds")
            output.append(record)
    return output
