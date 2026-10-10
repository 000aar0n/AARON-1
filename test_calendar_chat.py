"""Calendar-aware AI chat and event-selection highlighting regression tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import assistant_core as core
import assistant_conversation as conv
import planner
import planner_ui
from calendar_context import calendar_model_context, schedule_for_range


class CalendarAssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            patch.object(core, "DATA", root),
            patch.object(core, "DB", root / "state.sqlite3"),
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

    def seed(self):
        chemistry = planner.create_item(
            title="Chemistry Class", due="2026-10-12", due_time="10:30",
            item_type="event", repeat_weekly=True,
            repeat_until="2026-11-02", color_name="Blue",
        )
        homework = planner.create_item(
            title="Chemistry lab report", due="2026-10-15",
            item_type="task", linked_event_id=chemistry,
        )
        return chemistry, homework

    def test_weekly_calendar_answers_include_classes_and_assignments(self):
        self.seed()
        now = datetime(2026, 10, 10, 8, 19)
        reply, modified = conv.respond(
            "what do I have on my calendar next week?", now=now
        )
        self.assertFalse(modified)
        self.assertIn("Chemistry Class", reply)
        self.assertIn("Chemistry lab report", reply)
        self.assertIn("for Chemistry Class", reply)
        self.assertIn("Monday, Oct 12", reply)

    def test_when_is_my_next_class_returns_real_local_time(self):
        self.seed()
        reply, acted = conv.respond(
            "When is my next chemistry class?", now=datetime(2026, 10, 10),
        )
        self.assertFalse(acted)
        self.assertIn("Chemistry Class", reply)
        self.assertIn("10:30 AM", reply)
        self.assertIn("Monday, Oct 12", reply)

    def test_today_and_following_week_include_virtual_recurring_occurrences(self):
        self.seed()
        rows = schedule_for_range(
            datetime(2026, 10, 19).date(), datetime(2026, 10, 26).date()
        )
        self.assertTrue(any(
            item["title"] == "Chemistry Class" and
            item["due"] == "2026-10-19"
            for item in rows
        ))
        context = calendar_model_context(
            today=datetime(2026, 10, 10).date(),
            days=14,
        )
        self.assertIn("Chemistry lab report", context)
        self.assertIn("assignment for Chemistry Class", context)
        self.assertIn("UNTRUSTED DATA", context)

    def test_local_ollama_model_receives_read_only_calendar_snapshot(self):
        self.seed()
        sent = {}

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *_):
                return False
            def read(self):
                return b'{"message":{"content":"You have Chemistry Class Monday."}}'

        def fake_open(request, timeout=75):
            sent["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        with patch.object(conv, "urlopen", side_effect=fake_open):
            reply, acted = conv.respond(
                "Can you help me study for the next two weeks?",
                model="qwen2.5:3b",
                now=datetime(2026, 10, 10),
            )
        self.assertFalse(acted)
        self.assertIn("Chemistry", reply)
        prompt = sent["payload"]["messages"][0]["content"]
        self.assertIn("Chemistry Class", prompt)
        self.assertIn("Chemistry lab report", prompt)
        self.assertIn("read-only", prompt)
        self.assertIn("UNTRUSTED DATA", prompt)

    def test_chat_history_is_scrollable_without_hiding_input(self):
        import app
        from inspect import getsource
        src = getsource(app.render_chat)
        self.assertIn("height=550", src)
        self.assertIn("aaron_chat_scroll_window", src)
        self.assertIn('st.chat_input("Talk to AARON-1…"', src)
        from app import APP_BUILD
        self.assertIn("calendar-chat-v7", APP_BUILD)
        at = AppTest.from_file(
            str(Path(__file__).resolve().parent / "app.py"),
            default_timeout=40,
        ).run()
        self.assertEqual(len(at.exception), 0,
                         repr([x.message for x in at.exception]))

    def test_clicked_event_has_persistent_selection_style(self):
        event_id = planner.create_item(
            title="Classical Music Club",
            due="2026-10-14", due_time="15:45",
            item_type="event", color_name="Blue",
        )
        received = []
        calls = {"n": 0}

        def mock_calendar(*, events, options, **kwargs):
            calls["n"] += 1
            selected = next(event for event in events if event["id"] == event_id)
            received.append(selected)
            if calls["n"] == 1:
                return {
                    "callback": "eventClick",
                    "eventClick": {"event": {"id": event_id}},
                }
            return {"callback": ""}

        with patch.object(planner_ui, "calendar", side_effect=mock_calendar):
            at = AppTest.from_file(
                str(Path(__file__).resolve().parent / "app.py"),
                default_timeout=40,
            ).run()
        self.assertEqual(len(at.exception), 0,
                         repr([x.message for x in at.exception]))
        self.assertEqual(at.session_state["planner_highlight_id"], event_id)
        self.assertIn("aaron-event-selected", received[-1].get("classNames", []))
        self.assertIn("aaron-event-selected", planner_ui.CALENDAR_CSS)
        self.assertIn(".fc .fc-event:hover", planner_ui.CALENDAR_CSS)


if __name__ == "__main__":
    unittest.main()
