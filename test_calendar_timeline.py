"""End-to-end coverage for the single clock-aligned weekly calendar.

All events are synthetic and saved only in a temporary SQLite database.
Tasks use one canonical database record while the calendar can display two
visual occurrences: a top-row reminder and a precise timed deadline.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import assistant_core as core
import planner
import planner_ui


class AlignedCalendarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            patch.object(core, "DATA", root),
            patch.object(core, "DB", root / "personal.sqlite3"),
            patch.object(core, "WEIGHTS", root / "weights.json"),
            patch.object(core, "LEGACY_MEMORY", root / "legacy.sqlite3"),
        ]
        for p in self.patches:
            p.start()
        planner.ensure_schema()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_class_time_is_precise_not_rounded_to_slot(self):
        class_id = planner.create_item(
            title="High School Math", due="2026-10-12",
            due_time="08:10", duration_min=55, item_type="event"
        )
        class2 = planner.create_item(
            title="Chinese", due="2026-10-12",
            due_time="09:05", duration_min=50, item_type="event"
        )
        rendered = {
            e["id"]: e for e in planner.calendar_events(
                planner.items_for_calendar()
            )
        }
        self.assertEqual(rendered[class_id]["start"], "2026-10-12T08:10:00")
        self.assertEqual(rendered[class_id]["end"], "2026-10-12T09:05:00")
        self.assertEqual(rendered[class2]["start"], "2026-10-12T09:05:00")
        self.assertEqual(rendered[class2]["end"], "2026-10-12T09:55:00")
        self.assertFalse(rendered[class_id]["allDay"])
        self.assertFalse(rendered[class2]["allDay"])

    def test_timed_homework_pinned_top_and_at_deadline_same_record(self):
        task = planner.create_item(
            title="Chemistry lab report", due="2026-10-12",
            due_time="11:17", priority=3,
        )
        rows = planner.items_for_calendar()
        self.assertEqual(len(rows), 1)
        result = planner.calendar_events(rows)
        self.assertEqual(len(result), 2)
        entries = {e["id"]: e for e in result}
        marker = entries[task]
        top = entries[task + "::top"]
        self.assertEqual(marker["start"], "2026-10-12T11:17:00")
        self.assertEqual(marker["end"], "2026-10-12T11:32:00")
        self.assertFalse(marker["allDay"])
        self.assertIn("⏰ DUE", marker["title"])
        self.assertEqual(top["start"], "2026-10-12")
        self.assertTrue(top["allDay"])
        self.assertIn("11:17 AM", top["title"])
        self.assertIn("aaron-task-pin", top["classNames"])
        self.assertIn("aaron-task-due", marker["classNames"])
        self.assertEqual(
            top["extendedProps"]["canonicalId"], task,
        )
        self.assertEqual(marker["extendedProps"]["seriesId"], task)
        self.assertEqual(planner.get_item(task)["title"], "Chemistry lab report")

    def test_untimed_task_goes_only_to_all_day_top(self):
        task = planner.create_item(
            title="History reading", due="2026-10-13",
        )
        result = planner.calendar_events(planner.items_for_calendar())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], task)
        self.assertTrue(result[0]["allDay"])
        self.assertEqual(result[0]["start"], "2026-10-13")
        self.assertEqual(result[0]["extendedProps"]["taskCalendarRole"], "pin")

    def test_timed_task_is_linked_to_class_in_both_locations(self):
        cls = planner.create_item(
            title="Chemistry (L)", due="2026-10-12",
            due_time="09:35", duration_min=50, item_type="event",
            color_name="Blue",
        )
        task = planner.create_item(
            title="Balance equations", due="2026-10-12",
            due_time="15:40", linked_event_id=cls,
        )
        rendered = {
            e["id"]: e for e in planner.calendar_events(
                planner.items_for_calendar()
            )
        }
        self.assertEqual(
            rendered[task]["extendedProps"]["linkedEventId"], cls
        )
        self.assertIn("Chemistry (L)", rendered[task + "::top"]["title"])
        self.assertEqual(
            rendered[task]["backgroundColor"],
            rendered[cls]["backgroundColor"],
        )
        self.assertEqual(len(planner.related_assignments(cls)), 1)

    def test_weekly_classes_still_repeat_correctly_at_exact_time(self):
        series = planner.create_item(
            title="Music lesson", due="2026-10-12",
            due_time="16:05", duration_min=45, item_type="event",
            repeat_weekly=True, repeat_until="2026-10-26",
        )
        rendered = planner.calendar_events(
            planner.items_for_calendar(
                start="2026-10-14", end="2026-10-27"
            ),
            start="2026-10-14", end="2026-10-27",
        )
        self.assertEqual([e["id"] for e in rendered], [
            series + "::2026-10-19", series + "::2026-10-26"
        ])
        self.assertEqual(rendered[0]["start"], "2026-10-19T16:05:00")
        self.assertEqual(rendered[1]["end"], "2026-10-26T16:50:00")

    def test_untimed_imported_school_event_stays_all_day(self):
        with core.connect() as db:
            db.execute(
                "INSERT INTO tasks "
                "(id,title,due,item_type,source,created_at) "
                "VALUES (?,?,?,?,?,?)",
                (
                    "import1", "School holiday", "2026-10-13", "event",
                    "google_calendar", "2026-10-10T08:00:00",
                ),
            )
            db.commit()
        result = planner.calendar_events(planner.items_for_calendar())
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["allDay"])
        self.assertIn("School holiday", result[0]["title"])

    def test_ui_has_one_timegrid_week_no_secondary_week_page(self):
        captured = {}
        def fake_calendar(*, events, options, key, **kwargs):
            captured["events"] = events
            captured["options"] = options
            captured["key"] = key
            return {"callback": ""}
        with patch.object(planner_ui, "calendar", side_effect=fake_calendar):
            at = AppTest.from_file(
                str(Path(__file__).resolve().parent / "app.py"),
                default_timeout=45,
            ).run()
        self.assertEqual(
            len(at.exception), 0,
            repr([e.message for e in at.exception]),
        )
        opt = captured["options"]
        self.assertEqual(opt["initialView"], "timeGridWeek")
        self.assertEqual(opt["timeZone"], "local")
        self.assertEqual(opt["slotMinTime"], "00:00:00")
        self.assertEqual(opt["slotMaxTime"], "24:00:00")
        self.assertEqual(opt["slotDuration"], "00:30:00")
        self.assertTrue(opt["allDaySlot"])
        self.assertFalse(opt["slotEventOverlap"])
        self.assertFalse(opt["eventOverlap"])
        self.assertNotIn("dayGridWeek", opt["views"])
        self.assertNotIn("planner_readable_week_date", [
            d.key for d in at.get("date_input")
        ])
        self.assertIn("aligned_week", captured["key"])
        self.assertEqual(len(at.tabs), 5)

    def test_timed_task_popup_from_all_day_pin_uses_original_id(self):
        item = planner.create_item(
            title="Chinese presentation",
            due="2026-10-12", due_time="11:15",
        )
        click = {
            "callback": "eventClick",
            "eventClick": {"event": {"id": item + "::top"}},
        }
        with patch.object(planner_ui, "calendar", return_value=click):
            at = AppTest.from_file(
                str(Path(__file__).resolve().parent / "app.py"),
                default_timeout=45,
            ).run()
        self.assertEqual(len(at.exception), 0,
                         repr([e.message for e in at.exception]))
        self.assertEqual(at.session_state["planner_editor_id"], item)
        self.assertTrue(at.session_state["planner_popup_open"])


if __name__ == "__main__":
    unittest.main()
