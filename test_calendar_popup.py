"""Full-width Streamlit calendar and modal editor regression tests.

Exercises all tabs simultaneously against temporary SQLite data, so private
Google Calendar exports are never needed in CI.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import assistant_core as core
import planner


class FullWidthCalendarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            patch.object(core, "DATA", root),
            patch.object(core, "DB", root / "personal.sqlite3"),
            patch.object(core, "WEIGHTS", root / "priority.json"),
            patch.object(core, "LEGACY_MEMORY", root / "legacy.sqlite3"),
        ]
        for p in self.patches:
            p.start()
        planner.ensure_schema()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def _app(self):
        at = AppTest.from_file(
            str(Path(__file__).resolve().parent / "app.py"),
            default_timeout=45,
        ).run()
        self.assertEqual(
            len(at.exception), 0,
            repr([e.message for e in at.exception]),
        )
        return at

    def test_normal_page_uses_full_width_without_permanent_calendar_editor(self):
        from app import APP_BUILD
        self.assertIn("aligned-calendar-v10", APP_BUILD)
        from planner_ui import CALENDAR_CSS
        self.assertIn("min-height:125px", CALENDAR_CSS)
        self.assertIn("font-size:13px", CALENDAR_CSS)

        at = self._app()
        self.assertEqual(len(at.tabs), 5)
        title_keys = [widget.key for widget in at.get("text_input")]
        self.assertIn("priorities_planner_0_title", title_keys)
        self.assertNotIn("calendar_planner_0_title", title_keys)
        self.assertIn("planner_new_task", [b.key for b in at.button])
        self.assertIn("planner_new_event", [b.key for b in at.button])

    def test_open_and_close_new_event_popup_without_affecting_priorities(self):
        at = self._app()
        at.button(key="planner_new_event").click().run()
        self.assertEqual(len(at.exception), 0, repr([e.message for e in at.exception]))
        self.assertTrue(at.session_state["planner_popup_open"])
        self.assertIn("calendar_planner_1_title", [widget.key for widget in at.get("text_input")])
        self.assertIn("priorities_planner_1_title", [widget.key for widget in at.get("text_input")])
        self.assertIn("calendar_dialog_cancel", [b.key for b in at.button])

        at.button(key="calendar_dialog_cancel").click().run()
        self.assertEqual(len(at.exception), 0, repr([e.message for e in at.exception]))
        self.assertFalse(at.session_state["planner_popup_open"])
        self.assertNotIn(
            "calendar_planner_1_title", [widget.key for widget in at.get("text_input")]
        )

    def test_create_event_in_popup_saves_and_closes_without_sidebar(self):
        at = self._app()
        at.button(key="planner_new_event").click().run()
        self.assertEqual(len(at.exception), 0)
        # A Streamlit form submits all its input changes as one transaction.
        # Don't rerun between typing and clicking Submit in AppTest.
        at.text_input(key="calendar_planner_1_title").set_value(
            "Class: Advanced Geometry"
        )
        at.button(key="calendar_planner_1_save").click()
        at.run()
        self.assertEqual(len(at.exception), 0, repr([e.message for e in at.exception]))
        saved = [
            x["title"] for x in planner.items_for_calendar()
            if x["title"] == "Class: Advanced Geometry"
        ]
        self.assertTrue(
            saved,
            "Form submission did not save the event; popup state: "
            + repr(at.session_state.get("planner_popup_open"))
            + " and available fields: "
            + repr([x.key for x in at.get("text_input")]),
        )
        self.assertFalse(
            at.session_state.get("planner_popup_open"),
            "Saved event still leaves the popup open: " +
            repr([x.message for x in at.exception]),
        )
        self.assertNotIn(
            "calendar_planner_1_title", [x.key for x in at.get("text_input")]
        )

    def test_open_existing_event_from_calendar_callback_and_show_full_title(self):
        import planner_ui
        long_title = "Mathematics Class " + ("Very long event title " * 6)
        event_id = planner.create_item(
            title=long_title,
            item_type="event",
            due="2026-10-15",
            due_time="11:15",
            color_name="Blue",
        )
        clicked = {
            "callback": "eventClick",
            "eventClick": {"event": {"id": event_id}},
        }
        # FullCalendar runs in an iframe; simulate its genuine callback object.
        with patch.object(planner_ui, "calendar", return_value=clicked):
            at = self._app()
        self.assertEqual(len(at.exception), 0)
        self.assertTrue(at.session_state["planner_popup_open"])
        self.assertEqual(at.session_state["planner_editor_id"], event_id)
        self.assertIn(
            long_title,
            " ".join(x.value for x in at.get("markdown")),
        )

    def test_blue_legend_is_labeled_classes(self):
        import planner_ui
        from inspect import getsource
        source = getsource(planner_ui.calendar_page)
        self.assertIn('("Classes", "Blue")', source)
        self.assertNotIn('("Google", "Blue")', source)


if __name__ == "__main__":
    unittest.main()
