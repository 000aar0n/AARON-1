"""Private Google Calendar ZIP integration and 48 Winter Arc reminder tests."""
from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

import assistant_core as core
from google_calendar_import import import_google_calendar, _extract_ics_files
from planner import ensure_schema, items_for_calendar, calendar_events
from winter_arc import (
    END, START, PUSH, PULL, WORKOUTS,
    seed_winter_arc, workout_for_day, upcoming_workout,
)

ICS_HEAD = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Tests//EN\r\n"
ICS_TAIL = "END:VCALENDAR\r\n"


def ics(*events):
    return (ICS_HEAD + "".join(events) + ICS_TAIL).encode("utf-8")


def one_event(uid, start, end, name="Google calendar appointment", details=""):
    return (
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\nDTSTART;TZID=America/New_York:{start}\r\n"
        f"DTEND;TZID=America/New_York:{end}\r\n"
        f"SUMMARY:{name}\r\n" + details + "END:VEVENT\r\n"
    )


def zip_calendar(data, file_name="my-school-calendar.ics"):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(file_name, data)
    return out.getvalue()


class CalendarAndWinterArcTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [
            patch.object(core, "DATA", root),
            patch.object(core, "DB", root / "personal.sqlite3"),
            patch.object(core, "WEIGHTS", root / "weights.json"),
            patch.object(core, "LEGACY_MEMORY", root / "old.sqlite3"),
        ]
        for p in self.patches:
            p.start()
        ensure_schema()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_winter_arc_exact_four_day_split_and_end_date(self):
        self.assertEqual(workout_for_day(date(2026, 10, 8)), PUSH)
        self.assertEqual(workout_for_day(date(2026, 10, 9)), PULL)
        self.assertEqual(workout_for_day(date(2026, 10, 10)), None)
        self.assertEqual(workout_for_day(date(2026, 10, 12)), PUSH)
        self.assertEqual(workout_for_day(date(2026, 10, 13)), PULL)
        self.assertEqual(workout_for_day(date(2026, 10, 14)), None)
        self.assertEqual(workout_for_day(date(2026, 12, 29)), PULL)
        self.assertEqual(workout_for_day(date(2026, 12, 30)), None)
        self.assertIsNone(workout_for_day(date(2026, 12, 31)))
        self.assertIn("dumbbell triceps kickbacks", WORKOUTS[PUSH])
        self.assertNotIn("Band triceps extension", WORKOUTS[PUSH])

    def test_seed_winter_arc_creates_48_workouts_only_once(self):
        self.assertEqual(seed_winter_arc(), 48)
        self.assertEqual(seed_winter_arc(), 0)
        with core.connect() as db:
            rows = db.execute(
                "SELECT id,due,title,item_type,source,notes FROM tasks "
                "WHERE source='winter_arc' ORDER BY due"
            ).fetchall()
        self.assertEqual(len(rows), 48)
        self.assertEqual(rows[0]["due"], "2026-10-08")
        self.assertEqual(rows[-1]["due"], "2026-12-29")
        self.assertTrue(all(r["item_type"] == "event" for r in rows))
        self.assertEqual(upcoming_workout(date(2026, 10, 10)),
                         (date(2026, 10, 12), PUSH))
        # User can delete a workout without startup recreating it.
        from planner import delete_item
        delete_item(rows[0]["id"])
        self.assertEqual(seed_winter_arc(), 0)
        with core.connect() as db:
            n = db.execute("SELECT COUNT(*) FROM tasks WHERE source='winter_arc'").fetchone()[0]
        self.assertEqual(n, 47)

    def test_google_zip_import_preserves_local_start_end_and_location(self):
        content = ics(one_event(
            "meeting-1@google.com", "20261012T143000", "20261012T160000",
            "Music rehearsal",
            "LOCATION:School hall\r\nDESCRIPTION:Bring music\r\n"
        ))
        result = import_google_calendar(
            zip_calendar(content), "google-export.zip",
            from_date=date(2026, 10, 1), months=3
        )
        self.assertEqual(result["added"], 1)
        self.assertEqual(result["updated"], 0)
        events = items_for_calendar()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "google_calendar")
        self.assertEqual(events[0]["due_time"], "14:30")
        self.assertEqual(events[0]["duration_min"], 90)
        self.assertIn("School hall", events[0]["notes"])
        cal = calendar_events(events)
        self.assertEqual(cal[0]["start"], "2026-10-12T14:30:00")
        self.assertEqual(cal[0]["end"], "2026-10-12T16:00:00")
        # Repeat import should refresh, never duplicate.
        again = import_google_calendar(
            zip_calendar(content), "google-export.zip",
            from_date=date(2026, 10, 1), months=3
        )
        self.assertEqual(again["added"], 0)
        self.assertEqual(again["updated"], 1)
        self.assertEqual(len(items_for_calendar()), 1)

    def test_utc_event_is_converted_to_eastern(self):
        content = ics(
            "BEGIN:VEVENT\r\nUID:utc@calendar\r\n"
            "DTSTART:20261012T190000Z\r\n"
            "DTEND:20261012T201500Z\r\n"
            "SUMMARY:Remote meeting\r\nEND:VEVENT\r\n"
        )
        import_google_calendar(content, "calendar.ics",
                               from_date=date(2026, 10, 1), months=2)
        row = items_for_calendar()[0]
        self.assertEqual(row["due_time"], "15:00")
        self.assertEqual(row["event_end"], "2026-10-12T16:15:00")

    def test_all_day_multi_day_event_keeps_exclusive_end(self):
        content = ics(
            "BEGIN:VEVENT\r\nUID:vacation@calendar\r\n"
            "DTSTART;VALUE=DATE:20261019\r\n"
            "DTEND;VALUE=DATE:20261023\r\n"
            "SUMMARY:School break\r\nEND:VEVENT\r\n"
        )
        import_google_calendar(content, "calendar.ics",
                               from_date=date(2026, 10, 1), months=2)
        event = calendar_events(items_for_calendar())[0]
        self.assertTrue(event["allDay"])
        self.assertEqual(event["start"], "2026-10-19")
        self.assertEqual(event["end"], "2026-10-23")

    def test_rrule_exdates_modified_and_cancelled_instances(self):
        content = ics(
            "BEGIN:VEVENT\r\nUID:recurring@calendar\r\n"
            "DTSTART;TZID=America/New_York:20261012T150000\r\n"
            "DTEND;TZID=America/New_York:20261012T160000\r\n"
            "RRULE:FREQ=WEEKLY;COUNT=8;BYDAY=MO,TH\r\n"
            "EXDATE;TZID=America/New_York:20261022T150000\r\n"
            "SUMMARY:Class workout\r\nEND:VEVENT\r\n",
            "BEGIN:VEVENT\r\nUID:recurring@calendar\r\n"
            "RECURRENCE-ID;TZID=America/New_York:20261015T150000\r\n"
            "DTSTART;TZID=America/New_York:20261016T153000\r\n"
            "DTEND;TZID=America/New_York:20261016T163000\r\n"
            "SUMMARY:Moved class\r\nEND:VEVENT\r\n",
            "BEGIN:VEVENT\r\nUID:recurring@calendar\r\n"
            "RECURRENCE-ID;TZID=America/New_York:20261029T150000\r\n"
            "DTSTART;TZID=America/New_York:20261029T150000\r\n"
            "DTEND;TZID=America/New_York:20261029T160000\r\n"
            "STATUS:CANCELLED\r\nSUMMARY:Cancelled class\r\nEND:VEVENT\r\n",
        )
        result = import_google_calendar(content, "calendar.ics",
                                        from_date=date(2026, 10, 1), months=2)
        self.assertEqual(result["added"], 6)  # 8 - 1 EXDATE - 1 cancelled
        rows = items_for_calendar()
        self.assertTrue(any(t["title"] == "Moved class" and
                            t["due"] == "2026-10-16" for t in rows))
        self.assertFalse(any(t["due"] == "2026-10-22" for t in rows))
        self.assertFalse(any(t["due"] == "2026-10-29" for t in rows))

    def test_16mb_uncompressed_zip_is_accepted(self):
        # Similar to the user's real Google export: compressed ZIP, large .ics.
        giant_description = "A" * 16_000_000
        raw = ics(one_event(
            "large-calendar@google.com", "20261012T143000",
            "20261012T153000", details="DESCRIPTION:" + giant_description + "\r\n"
        ))
        zipped = zip_calendar(raw)
        self.assertGreater(len(raw), 15_000_000)
        extracted = _extract_ics_files(zipped, "google-export.zip")
        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0][1], raw)

    def test_import_window_excludes_old_history(self):
        content = ics(
            one_event("old@calendar", "20220801T100000", "20220801T103000"),
            one_event("now@calendar", "20261012T100000", "20261012T103000"),
        )
        result = import_google_calendar(content, "calendar.ics",
                                        from_date=date(2026, 9, 1), months=18)
        self.assertEqual(result["source_events"], 2)
        self.assertEqual(result["added"], 1)

    def test_calendar_import_does_not_delete_manually_created_tasks_or_events(self):
        from planner import create_item
        created = create_item(title="Hand-added schoolwork", due="2026-10-17")
        seed_winter_arc()
        original_winter_count = len([
            r for r in items_for_calendar() if r["source"] == "winter_arc"
        ])
        import_google_calendar(ics(one_event(
            "m@calendar", "20261012T140000", "20261012T150000",
        )), "calendar.ics", from_date=date(2026, 9, 1), months=18)
        self.assertIsNotNone(__import__("planner").get_item(created))
        self.assertEqual(len([
            r for r in items_for_calendar() if r["source"] == "winter_arc"
        ]), original_winter_count)

    def test_rejects_zip_bomb_and_unrelated_extensions(self):
        with self.assertRaisesRegex(ValueError, "must be"):
            _extract_ics_files(b"hi", "calendar.pdf")
        too_big = zip_calendar(b"A" * 40_000_001)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            _extract_ics_files(too_big, "calendar.zip")


if __name__ == "__main__":
    unittest.main()
