"""Private, bounded import of Google Calendar .ics or official .ics.zip exports.

Google data remains in the local SQLite database. Nothing from a calendar
export is checked into GitHub, uploaded to a model provider, or auto-synced.
"""
from __future__ import annotations

import hashlib
import io
import sqlite3
import uuid
import zipfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import PurePosixPath
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrulestr
from icalendar import Calendar

from assistant_core import connect
from planner import ensure_schema

CALENDAR_SOURCE = "google_calendar"
LOCAL_TZ = ZoneInfo("America/New_York")
MAX_ICS_SIZE = 40_000_000
MAX_ZIP_FILES = 12
MAX_COMPONENTS = 15_000
MAX_OCCURRENCES = 24_000


def _extract_ics_files(payload, filename):
    """Strict size limits reject ZIP bombs while supporting 16 MB ICS exports."""
    if not isinstance(payload, bytes) or not payload:
        raise ValueError("Select a Google Calendar .ics or .zip export")
    suffix = str(filename or "").lower()
    if suffix.endswith(".ics"):
        if len(payload) > MAX_ICS_SIZE:
            raise ValueError("Calendar file exceeds the 40 MB limit")
        return [(PurePosixPath(filename).name, payload)]
    if not suffix.endswith(".zip"):
        raise ValueError("Google Calendar export must be .ics or .zip")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = [item for item in archive.infolist()
                     if not item.is_dir() and item.filename.lower().endswith(".ics")
                     and not item.filename.startswith("__MACOSX/")]
            if not names:
                raise ValueError("ZIP does not contain any .ics calendars")
            if len(names) > MAX_ZIP_FILES:
                raise ValueError("ZIP contains too many calendars (maximum 12)")
            if sum(item.file_size for item in names) > MAX_ICS_SIZE:
                raise ValueError("Uncompressed calendar data exceeds 40 MB")
            files = []
            for item in names:
                if item.file_size > MAX_ICS_SIZE or item.flag_bits & 0x1:
                    raise ValueError("Encrypted or oversized calendar in ZIP")
                raw = archive.read(item)
                if len(raw) > MAX_ICS_SIZE:
                    raise ValueError("Uncompressed calendar is oversized")
                files.append((PurePosixPath(item.filename).name, raw))
            return files
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise ValueError("Invalid or unreadable Google Calendar ZIP") from exc


def _local(value):
    """Normalize aware UTC/TZID times into the displayed New York local time."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=LOCAL_TZ)
        return value.astimezone(LOCAL_TZ)
    return value


def _identity(value):
    """Match EXDATE / RECURRENCE-ID even if exported in a different timezone."""
    if isinstance(value, datetime):
        return "T:" + _local(value).astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return "D:" + value.isoformat()
    return str(value)


def _decoded(component, name):
    prop = component.get(name)
    return prop.dt if prop is not None and hasattr(prop, "dt") else None


def _duration(component):
    start = _decoded(component, "DTSTART")
    end = _decoded(component, "DTEND")
    if start is None:
        return timedelta(hours=1)
    if end is not None:
        a, b = _local(start), _local(end)
        if isinstance(a, datetime) and isinstance(b, datetime):
            difference = b - a
        elif isinstance(a, date) and not isinstance(a, datetime) and (
                isinstance(b, date) and not isinstance(b, datetime)):
            difference = b - a
        else:
            difference = timedelta(hours=1)
        return difference if difference.total_seconds() > 0 else timedelta(hours=1)
    explicit = component.get("DURATION")
    if explicit is not None:
        try:
            delta = component.decoded("DURATION")
            if isinstance(delta, timedelta) and delta.total_seconds() > 0:
                return delta
        except (ValueError, TypeError, AttributeError):
            pass
    return timedelta(days=1) if not isinstance(start, datetime) else timedelta(hours=1)


def _date_values(component, field):
    values = component.get(field)
    if not values:
        return []
    if not isinstance(values, list):
        values = [values]
    result = []
    for obj in values:
        result.extend(x.dt for x in getattr(obj, "dts", ()))
    return result


def _within_window(start, end, window_start, window_end):
    # Event times and Google's all-day DTEND are both exclusive at the end.
    # Don't pull in a vacation that finished before the chosen start date.
    if isinstance(start, datetime) and isinstance(end, datetime):
        lower = datetime.combine(window_start, time.min, tzinfo=LOCAL_TZ)
        upper = datetime.combine(window_end, time.min, tzinfo=LOCAL_TZ)
        return start < upper and end > lower
    return start < window_end and end > window_start


def _record(component, *, actual_start, span, calendar_id, uid, original_start,
            window_start, window_end):
    if str(component.get("STATUS", "")).upper() == "CANCELLED":
        return None
    title = str(component.get("SUMMARY", "")).strip()[:250]
    if not title:
        return None
    start = _local(actual_start)
    end = start + span
    if not _within_window(start, end, window_start, window_end):
        return None
    all_day = not isinstance(start, datetime)
    day = start.isoformat() if all_day else start.date().isoformat()
    clock = None if all_day else start.strftime("%H:%M")
    final_end = end.isoformat() if all_day else end.strftime("%Y-%m-%dT%H:%M:%S")
    minutes = max(5, min(1440, round(span.total_seconds() / 60)))
    note_parts = []
    location = str(component.get("LOCATION", "")).strip()
    description = str(component.get("DESCRIPTION", "")).strip()
    if location:
        note_parts.append("Location: " + location)
    if description:
        note_parts.append(description)
    notes = "\n\n".join(note_parts)[:4000]
    instance_id = _identity(original_start)
    identity = calendar_id + ":" + uid + ":" + instance_id
    return {
        "external_id": identity,
        "title": title,
        "due": day,
        "due_time": clock,
        "notes": notes,
        "event_end": final_end,
        "duration_min": minutes,
        "item_type": "event",
    }


def _calendar_records(raw, filename, window_start, window_end):
    """Expand bounded recurring series and apply changed/cancelled occurrences."""
    try:
        cal = Calendar.from_ical(raw)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Could not read this Google Calendar .ics file") from exc
    components = list(cal.walk("VEVENT"))
    if len(components) > MAX_COMPONENTS:
        raise ValueError("Calendar has more than 15,000 events")
    source_id = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:12]
    masters, exceptions = {}, {}
    for i, comp in enumerate(components):
        initial = _decoded(comp, "DTSTART")
        if initial is None:
            continue
        uid = str(comp.get("UID") or "").strip()
        if not uid:
            uid = hashlib.sha256(
                (str(comp.get("SUMMARY", "")) + _identity(initial)).encode()
            ).hexdigest()[:24]
        if comp.get("RECURRENCE-ID") is not None:
            revised = _decoded(comp, "RECURRENCE-ID")
            if revised is not None:
                exceptions[(uid, _identity(revised))] = comp
        else:
            masters.setdefault(uid, []).append(comp)
    records = {}
    cancelled = set()
    consumed = set()
    range_start = datetime.combine(window_start - timedelta(days=3),
                                   time.min, tzinfo=LOCAL_TZ)
    range_end = datetime.combine(window_end + timedelta(days=3),
                                 time.max, tzinfo=LOCAL_TZ)
    processed = 0

    def collect(master, occurrence, uid, length):
        nonlocal processed
        processed += 1
        if processed > MAX_OCCURRENCES:
            raise ValueError("Calendar has too many recurring instances in this range")
        instance_key = (uid, _identity(occurrence))
        override = exceptions.get(instance_key)
        if override is not None:
            consumed.add(instance_key)
            if str(override.get("STATUS", "")).upper() == "CANCELLED":
                cancelled.add(source_id + ":" + uid + ":" + instance_key[1])
                return
            override_start = _decoded(override, "DTSTART") or occurrence
            actual_start = override_start
            used_span = (_duration(override) if override.get("DTEND") is not None
                         or override.get("DURATION") is not None else length)
            component = override
        else:
            if _identity(occurrence) in master_exdates:
                return
            if str(master.get("STATUS", "")).upper() == "CANCELLED":
                return
            actual_start, used_span, component = occurrence, length, master
        item = _record(
            component, actual_start=actual_start, span=used_span,
            calendar_id=source_id, uid=uid, original_start=occurrence,
            window_start=window_start, window_end=window_end,
        )
        if item:
            records[item["external_id"]] = item

    for uid, instances in masters.items():
        for master in instances:
            initial = _decoded(master, "DTSTART")
            if initial is None:
                continue
            length = _duration(master)
            master_exdates = {_identity(x) for x in _date_values(master, "EXDATE")}
            recurrence = master.get("RRULE")
            if recurrence is None:
                collect(master, initial, uid, length)
                continue
            rule = recurrence.to_ical().decode("utf-8")
            start_dt = (_local(initial) if isinstance(initial, datetime)
                        else datetime.combine(initial, time.min, tzinfo=LOCAL_TZ))
            try:
                times = rrulestr(rule, dtstart=start_dt).between(
                    range_start, range_end, inc=True
                )
            except (ValueError, TypeError) as exc:
                raise ValueError("A recurring event contains an invalid RRULE") from exc
            for occurrence_dt in times:
                occurrence = (occurrence_dt if isinstance(initial, datetime)
                              else occurrence_dt.date())
                collect(master, occurrence, uid, length)
            for extra in _date_values(master, "RDATE"):
                collect(master, extra, uid, length)

    # Some changed instances have been moved inside the window while their
    # original occurrence falls outside it. Include those too.
    for (uid, original_key), override in exceptions.items():
        if (uid, original_key) in consumed:
            continue
        actual_start = _decoded(override, "DTSTART")
        origin = _decoded(override, "RECURRENCE-ID")
        if actual_start is None or origin is None:
            continue
        external_id = source_id + ":" + uid + ":" + original_key
        if str(override.get("STATUS", "")).upper() == "CANCELLED":
            cancelled.add(external_id)
            continue
        item = _record(
            override, actual_start=actual_start, span=_duration(override),
            calendar_id=source_id, uid=uid, original_start=origin,
            window_start=window_start, window_end=window_end,
        )
        if item:
            records[item["external_id"]] = item
    return records, cancelled, len(components)


def import_google_calendar(payload, filename, *, from_date=None, months=18):
    """Import upcoming events to the local DB; return counts, safe to rerun.

    Supports the official Google Calendar .ics.zip download directly (the
    user's example expands to 16 MB). Re-importing updates matching events.
    Does not send or alter events at Google.
    """
    if from_date is None:
        from_date = date.today() - timedelta(days=30)
    if not isinstance(from_date, date) or isinstance(from_date, datetime):
        raise ValueError("Import start must be a date")
    if not isinstance(months, int) or not 1 <= months <= 48:
        raise ValueError("Import range must be between 1 and 48 months")
    until = from_date + relativedelta(months=months)
    files = _extract_ics_files(payload, filename)
    all_records, removed, components = {}, set(), 0
    for name, raw in files:
        records, cancelled, count = _calendar_records(
            raw, name, from_date, until
        )
        all_records.update(records)
        removed.update(cancelled)
        components += count
    ensure_schema()
    created, refreshed, deleted = 0, 0, 0
    # One transaction: either the entire calendar import succeeds or none.
    with connect() as db:
        # A confirmed/rejected recurring class keeps its status when a
        # subsequent ICS import introduces new occurrences of the same UID.
        # This never infers enrollment from title/teacher similarities.
        known_status = {
            str(r["external_id"]).rsplit(":", 1)[0]: r["personal_status"]
            for r in db.execute(
                "SELECT external_id, personal_status FROM tasks "
                "WHERE source=? AND item_type='event' "
                "AND personal_status IN ('mine','not_mine') "
                "AND external_id IS NOT NULL",
                (CALENDAR_SOURCE,),
            ).fetchall()
        }
        for key in removed:
            # A cancelled imported event must not delete its attached homework.
            # Detach local assignments first, then remove only the event copy.
            db.execute(
                "UPDATE tasks SET linked_event_id=NULL WHERE linked_event_id IN "
                "(SELECT id FROM tasks WHERE source=? AND external_id=?)",
                (CALENDAR_SOURCE, key),
            )
            deleted += db.execute(
                "DELETE FROM tasks WHERE source=? AND external_id=?",
                (CALENDAR_SOURCE, key),
            ).rowcount
        for key, item in all_records.items():
            current = db.execute(
                "SELECT id FROM tasks WHERE source=? AND external_id=?",
                (CALENDAR_SOURCE, key),
            ).fetchone()
            if current:
                db.execute(
                    """UPDATE tasks
                       SET title=?, due=?, due_time=?, notes=?, event_end=?,
                           duration_min=?, item_type='event'
                       WHERE id=?""",
                    (item["title"], item["due"], item["due_time"], item["notes"],
                     item["event_end"], item["duration_min"], current["id"]),
                )
                refreshed += 1
            else:
                db.execute(
                    """INSERT INTO tasks
                      (id,title,due,due_time,notes,source,external_id,
                       created_at,item_type,duration_min,estimated_min,
                       priority_level,event_end,personal_status)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (str(uuid.uuid4()), item["title"], item["due"],
                     item["due_time"], item["notes"], CALENDAR_SOURCE, key,
                     datetime.now(timezone.utc).isoformat(), "event",
                     item["duration_min"], 30, 2, item["event_end"],
                     known_status.get(key.rsplit(":", 1)[0], "unverified")),
                )
                created += 1
        db.commit()
    return {
        "calendars": len(files),
        "source_events": components,
        "added": created,
        "updated": refreshed,
        "cancelled_removed": deleted,
        "range_start": from_date.isoformat(),
        "range_end": until.isoformat(),
    }
