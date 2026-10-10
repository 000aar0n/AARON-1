"""Calendar v3: high-contrast colors, weekly series, and attached assignments.

Every test uses an isolated SQLite database. No personal calendars or accounts.
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


class CalendarFeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            patch.object(core, "DATA", root),
            patch.object(core, "DB", root / "state.sqlite3"),
            patch.object(core, "WEIGHTS", root / "weights.json"),
            patch.object(core, "LEGACY_MEMORY", root / "legacy.sqlite3"),
        ]
        for item in self.patches:
            item.start()
        planner.ensure_schema()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.tmp.cleanup()

    def create_weekly(self, **overrides):
        settings = dict(
            title="Chinese class", due="2026-10-12", due_time="11:15",
            duration_min=75, item_type="event", color_name="Blue",
            repeat_weekly=True, repeat_until="2026-11-02",
        )
        settings.update(overrides)
        return planner.create_item(**settings)

    def test_color_choices_migrate_and_survive_edits(self):
        original = planner.create_item(
            title="Lab", item_type="event", due="2026-10-14",
            color_name="Pink",
        )
        planner.ensure_schema()  # repeat migration should never destroy colors
        self.assertEqual(planner.get_item(original)["color_name"], "Pink")
        planner.update_item(
            original, title="New lab", item_type="event",
            due="2026-10-14", color_name="Orange",
        )
        record = planner.calendar_events(planner.items_for_calendar())[0]
        self.assertEqual(record["backgroundColor"], planner.EVENT_COLORS["Orange"])
        self.assertEqual(record["textColor"], "#FFFFFF")
        self.assertEqual(planner.get_item(original)["color_name"], "Orange")

    def test_priority_source_colors_and_assignment_inheritance(self):
        event_id = self.create_weekly(color_name="Teal")
        task = planner.create_item(
            title="Chinese writing homework", due="2026-10-19",
            linked_event_id=event_id,
        )
        output = planner.calendar_events(planner.items_for_calendar())
        task_result = next(entry for entry in output if entry["id"] == task)
        self.assertEqual(task_result["backgroundColor"], planner.EVENT_COLORS["Teal"])
        self.assertEqual(task_result["extendedProps"]["linkedEventId"], event_id)
        # A task can override its parent's color.
        planner.update_item(
            task, title="Chinese writing homework", due="2026-10-19",
            linked_event_id=event_id, color_name="Red",
        )
        output = planner.calendar_events(planner.items_for_calendar())
        task_result = next(entry for entry in output if entry["id"] == task)
        self.assertEqual(task_result["backgroundColor"], planner.EVENT_COLORS["Red"])

    def test_weekly_recurrence_expansion_end_is_inclusive(self):
        series = self.create_weekly()
        events = planner.calendar_events(planner.items_for_calendar())
        dates = [entry["start"] for entry in events if entry["id"].startswith(series + "::")]
        self.assertEqual(dates, [
            "2026-10-12T11:15:00", "2026-10-19T11:15:00",
            "2026-10-26T11:15:00", "2026-11-02T11:15:00",
        ])
        self.assertEqual(len(planner.items_for_calendar()), 1)
        self.assertEqual(events[0]["end"], "2026-10-12T12:30:00")
        self.assertEqual(events[0]["extendedProps"]["seriesId"], series)

    def test_weekly_series_renders_when_start_is_before_visible_range(self):
        series = self.create_weekly()
        items = planner.items_for_calendar(start="2026-10-16", end="2026-11-01")
        self.assertEqual(len(items), 1)
        events = planner.calendar_events(items, start="2026-10-16", end="2026-11-01")
        self.assertEqual(
            [e["start"][:10] for e in events],
            ["2026-10-19", "2026-10-26"],
        )
        self.assertTrue(all(e["id"].startswith(series) for e in events))

    def test_daily_view_shows_virtual_weekly_occurrences(self):
        series = self.create_weekly()
        tuesday = planner.daily_items("2026-10-20")
        self.assertFalse(any(task["id"] == series for task in tuesday))
        monday = planner.daily_items("2026-10-26")
        self.assertEqual(len(monday), 1)
        self.assertEqual(monday[0]["id"], series)
        self.assertEqual(monday[0]["due"], "2026-10-26")

    def test_update_entire_weekly_series_and_stop_early(self):
        series = self.create_weekly()
        planner.update_item(
            series, title="Chinese conversation", due="2026-10-12",
            due_time="10:00", item_type="event", duration_min=45,
            repeat_weekly=True, repeat_until="2026-10-19",
            color_name="Pink",
        )
        events = planner.calendar_events(planner.items_for_calendar())
        self.assertEqual(len(events), 2)
        self.assertEqual(events[-1]["start"], "2026-10-19T10:00:00")
        self.assertTrue(all("Chinese conversation" in e["title"] for e in events))

    def test_rejects_invalid_links_dates_and_colors(self):
        task = planner.create_item(title="Individual homework")
        with self.assertRaisesRegex(ValueError, "calendar event"):
            planner.create_item(
                title="Invalid link", linked_event_id=task,
            )
        with self.assertRaisesRegex(ValueError, "weekly"):
            planner.create_item(
                title="Repeating task", item_type="task",
                due="2026-10-12", repeat_weekly=True,
                repeat_until="2026-10-19",
            )
        with self.assertRaisesRegex(ValueError, "three years"):
            self.create_weekly(repeat_until="2035-10-12")
        with self.assertRaisesRegex(ValueError, "color"):
            self.create_weekly(color_name="not a real hex code")
        with self.assertRaisesRegex(ValueError, "end date"):
            self.create_weekly(repeat_until=None)

    def test_delete_parent_unlinks_assignments_but_keeps_them(self):
        series = self.create_weekly()
        first = planner.create_item(
            title="Assignment one", linked_event_id=series, due="2026-10-19"
        )
        second = planner.create_item(
            title="Assignment two", linked_event_id=series, due="2026-10-26"
        )
        self.assertEqual(len(planner.related_assignments(series)), 2)
        self.assertTrue(planner.delete_item(series))
        self.assertIsNone(planner.get_item(series))
        for assignment in (first, second):
            self.assertIsNotNone(planner.get_item(assignment))
            self.assertIsNone(planner.get_item(assignment)["linked_event_id"])

    def test_google_cancellation_preserves_linked_homework(self):
        from google_calendar_import import import_google_calendar
        head = "BEGIN:VCALENDAR\\r\\nVERSION:2.0\\r\\n"
        master = (
            "BEGIN:VEVENT\\r\\nUID:chem-class@calendar\\r\\n"
            "DTSTART;TZID=America/New_York:20261012T140000\\r\\n"
            "DTEND;TZID=America/New_York:20261012T150000\\r\\n"
            "RRULE:FREQ=WEEKLY;COUNT=2\\r\\n"
            "SUMMARY:Chemistry\\r\\nEND:VEVENT\\r\\n"
        )
        cancelled = (
            "BEGIN:VEVENT\\r\\nUID:chem-class@calendar\\r\\n"
            "RECURRENCE-ID;TZID=America/New_York:20261012T140000\\r\\n"
            "DTSTART;TZID=America/New_York:20261012T140000\\r\\n"
            "DTEND;TZID=America/New_York:20261012T150000\\r\\n"
            "STATUS:CANCELLED\\r\\n"
            "SUMMARY:Chemistry\\r\\nEND:VEVENT\\r\\n"
        )
        initial = (head + master + "END:VCALENDAR\\r\\n").encode()
        import_google_calendar(
            initial, "mycalendar.ics", from_date=date(2026, 10, 1), months=2,
        )
        parent = next(
            item for item in planner.items_for_calendar()
            if item["due"] == "2026-10-12"
        )
        homework = planner.create_item(
            title="Practice equations", due="2026-10-14",
            linked_event_id=parent["id"],
        )
        altered = (head + master + cancelled + "END:VCALENDAR\\r\\n").encode()
        result = import_google_calendar(
            altered, "mycalendar.ics", from_date=date(2026, 10, 1), months=2,
        )
        self.assertEqual(result["cancelled_removed"], 1)
        self.assertIsNone(planner.get_item(parent["id"]))
        self.assertIsNotNone(planner.get_item(homework))
        self.assertIsNone(planner.get_item(homework)["linked_event_id"])

    def test_create_assignment_from_event_keeps_preselected_parent(self):
        from planner_ui import _render_editor
        parent = self.create_weekly()
        script = (
            "import streamlit as st\\n"
            "from planner_ui import _render_editor\\n"
            f"st.session_state.setdefault('planner_editor_id', {parent!r})\\n"
            "_render_editor(scope='calendar')\\n"
        )
        app = AppTest.from_string(script, default_timeout=30).run()
        self.assertEqual(len(app.exception), 0, repr([e.message for e in app.exception]))
        app.button(key="calendar_planner_0_create_attached").click().run()
        self.assertEqual(len(app.exception), 0, repr([e.message for e in app.exception]))
        self.assertEqual(
            app.selectbox(key="calendar_planner_1_linked_event").value, parent,
        )

    def test_full_app_has_color_weekly_and_assignment_controls(self):
        from app import APP_BUILD
        self.assertIn("calendar-v5", APP_BUILD)
        series = self.create_weekly()
        planner.create_item(title="Class assignment", linked_event_id=series)
        app = AppTest.from_file(
            str(Path(__file__).resolve().parent / "app.py"),
            default_timeout=40,
        ).run()
        self.assertEqual(
            len(app.exception), 0,
            repr([x.message for x in app.exception]),
        )
        self.assertIn("calendar_planner_0_color", [x.key for x in app.selectbox])
        self.assertIn("priorities_planner_0_color", [x.key for x in app.selectbox])
        # Both editors are constructed simultaneously by st.tabs.
        self.assertIn("calendar_planner_0_type", [x.key for x in app.get("segmented_control")])

    def test_form_select_weekly_and_attached_assignment(self):
        script = """
import streamlit as st
from planner_ui import _render_editor, _choose_item
st.session_state["planner_editor_id"] = None
st.session_state["planner_new_kind"] = "event"
_render_editor(scope="calendar")
"""
        app = AppTest.from_string(script, default_timeout=30).run()
        self.assertEqual(len(app.exception), 0, repr([e.message for e in app.exception]))
        self.assertIn("calendar_planner_0_weekly", [x.key for x in app.checkbox])
        app.checkbox(key="calendar_planner_0_weekly").set_value(True).run()
        self.assertEqual(len(app.exception), 0, repr([e.message for e in app.exception]))
        self.assertIn("calendar_planner_0_weekly_until", [x.key for x in app.get("date_input")])


if __name__ == "__main__":
    unittest.main()
