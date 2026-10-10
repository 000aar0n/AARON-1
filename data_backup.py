"""Portable personal-data backups for AARON-1.

Exports only SQLite tables used for calendar, tasks, chat and training pairs;
never includes OAuth tokens, API keys, or downloaded model checkpoints.
An import *adds missing rows* but never overwrites existing data.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from assistant_core import connect

BACKUP_FORMAT = "AARON-1-personal-data-v1"
TABLES = (
    "tasks", "memories", "migrations", "learning",
    "chat_history", "training_examples",
)
MAX_BACKUP_BYTES = 16 * 1024 * 1024
MAX_TABLE_ROWS = 30000


def _present_tables(db):
    return {
        row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def export_personal_data():
    tables = {}
    with connect() as db:
        present = _present_tables(db)
        for table in TABLES:
            if table not in present:
                continue
            records = db.execute("SELECT * FROM " + table).fetchall()
            if len(records) > MAX_TABLE_ROWS:
                raise ValueError("AARON-1 data exceeds the backup row limit")
            tables[table] = [dict(record) for record in records]
    data = {
        "format": BACKUP_FORMAT,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
    }
    content = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(content) > MAX_BACKUP_BYTES:
        raise ValueError("AARON-1 backup exceeds 16 MB")
    return content


def restore_personal_data(payload):
    """Only import missing entries; never delete/overwrite existing rows.

    Requires the app to have initialized the core tables first.
    """
    if not isinstance(payload, bytes) or len(payload) > MAX_BACKUP_BYTES:
        raise ValueError("Invalid or oversized backup")
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Backup must be valid UTF-8 JSON") from exc
    if not isinstance(data, dict) or data.get("format") != BACKUP_FORMAT:
        raise ValueError("Not an AARON-1 personal data backup")
    tables = data.get("tables")
    if not isinstance(tables, dict) or any(t not in TABLES for t in tables):
        raise ValueError("Unsupported backup content")
    added = 0
    # Training examples aren't initialized unless Model Lab has been opened;
    # ensure their table exists before restoring.
    from training_data import examples
    examples()
    with connect() as db:
        present = _present_tables(db)
        for table in TABLES:
            records = tables.get(table, [])
            if not isinstance(records, list) or len(records) > MAX_TABLE_ROWS:
                raise ValueError("Invalid backup table")
            if table not in present:
                if records:
                    raise ValueError("Destination is missing table " + table)
                continue
            columns = {
                row[1] for row in db.execute("PRAGMA table_info(" + table + ")")
            }
            for record in records:
                if (not isinstance(record, dict)
                        or not record
                        or not set(record).issubset(columns)):
                    raise ValueError("Invalid backup row for " + table)
                names = list(record)
                query = (
                    "INSERT OR IGNORE INTO " + table +
                    " (" + ",".join(names) + ") VALUES (" +
                    ",".join("?" for _ in names) + ")"
                )
                result = db.execute(query, tuple(record[n] for n in names))
                added += max(0, result.rowcount)
        db.commit()
    return added
