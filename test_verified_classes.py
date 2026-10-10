"""Regression tests: all personal imported events visible; NO invented classes.

The assistant must get every claimed class/time/teacher/room from SQLite.
No private user calendar, network, or real school data is used here.
"""
from __future__ import annotations

from datetime import date, datetime
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import assistant_core as core
import assistant_conversation as conv
import calendar_context as cc
import planner
import planner_ui


class GroundedCalendarTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [
            patch.object(core, "DATA", root),
            patch.object(core, "DB", root / "mydata.sqlite3"),
            patch.object(core, "WEIGHTS", root / "weights.json"),
            patch.object(core, "LEGACY_MEMORY", root / "legacy.sqlite3"),
        ]
        for p in self.patches:
            p.start()
        planner.ensure_schema()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def import_fixture(self):
        """Mock the user's own calendar; none of the alleged fake classes exist."""
        rows = [
            ("g1", "Chinese Class", "personal:chinese:20261012T1105",
             "2026-10-12", "11:05",
             "Location: 410 Teacher: Mei Lin", "unverified"),
            ("g2", "Chemistry Class", "personal:chem:20261014T0910",
             "2026-10-14", "09:10",
             "Location: 226 Teacher: Dr. Chen", "not_mine"),
            ("g3", "Chinese Class", "personal:chinese:20261016T1105",
             "2026-10-16", "11:05",
             "Location: 410 Teacher: Mei Lin", "mine"),
        ]
        with core.connect() as db:
            db.executemany(
                """INSERT INTO tasks
                 (id,title,external_id,due,due_time,notes,item_type,
                  source,created_at,personal_status)
                  VALUES (?,?,?,?,?,?,?,?,?,?)""",
                [
                    (uid, title, external_id, due, when, notes,
                     "event", "google_calendar", "2026-10-10T09:00:00", status)
                    for uid, title, external_id, due, when, notes, status in rows
                ],
            )
            db.commit()
        return [r[0] for r in rows]

    def test_all_imported_events_display_without_any_manual_confirmation(self):
        ids = self.import_fixture()
        for uid in ids:
            self.assertTrue(planner.is_verified_personal(planner.get_item(uid)))
        events = cc.schedule_for_range(date(2026, 10, 12), date(2026, 10, 17))
        self.assertEqual([x["title"] for x in events], [
            "Chinese Class", "Chemistry Class", "Chinese Class"
        ])

    def test_direct_calendar_answer_never_invents_unsaved_classes(self):
        self.import_fixture()
        invented = "Advanced Architecture: Digital Domains"
        with patch.object(
            conv, "_local_model_reply",
            return_value="You have " + invented + " with Teacher: Atlas"
        ) as model:
            reply, acted = conv.respond(
                "Which classes do I have on Friday?",
                now=datetime(2026, 10, 10, 9),
                model="qwen2.5:3b",
                previous=[{
                    "role": "assistant",
                    "message": "You have " + invented + " this week."
                }],
            )
            self.assertFalse(acted)
            self.assertIn("Chinese Class", reply)
            self.assertNotIn(invented, reply)
            self.assertNotIn("Teacher: Atlas", reply)
            model.assert_not_called()

    def test_lookups_never_invent_unknown_course_teacher_or_time(self):
        self.import_fixture()
        with patch.object(conv, "_local_model_reply") as model:
            for question in (
                "When is my next Advanced Architecture class?",
                "Who is my Advanced Architecture teacher?",
                "Where is my Advanced Architecture class?",
            ):
                reply, acted = conv.respond(
                    question, now=datetime(2026, 10, 10),
                    model="__aaron_base__",
                )
                self.assertFalse(acted)
                self.assertIn("can't find", reply.lower())
                self.assertNotIn("Teacher: Atlas", reply)
            model.assert_not_called()

    def test_saved_teacher_and_room_are_quoted_verbatim_from_notes(self):
        self.import_fixture()
        teacher, acted = conv.respond(
            "Who is my Chinese teacher?", now=datetime(2026, 10, 10),
        )
        self.assertFalse(acted)
        self.assertIn("Mei Lin", teacher)
        self.assertIn("saved calendar notes", teacher)
        room, acted = conv.respond(
            "Where is my Chemistry class?", now=datetime(2026, 10, 10),
        )
        self.assertFalse(acted)
        self.assertIn("226", room)
        self.assertNotIn("1003", room)

    def test_class_list_contains_distinct_saved_titles_only(self):
        self.import_fixture()
        roster, acted = conv.respond(
            "What classes am I taking?", now=datetime(2026, 10, 10),
            model="qwen2.5:3b",
        )
        self.assertFalse(acted)
        self.assertEqual(roster.count("**Chinese Class**"), 1)
        self.assertEqual(roster.count("**Chemistry Class**"), 1)
        for absent in ("Advanced Architecture", "Advanced Engineering",
                       "Physical Education", "High School Math"):
            self.assertNotIn(absent, roster)
        self.assertIn("exact saved event titles", roster.lower())

    def test_notes_and_model_snapshot_include_actual_imported_events(self):
        self.import_fixture()
        context = cc.calendar_model_context(
            today=date(2026, 10, 10), days=14,
        )
        self.assertIn("Chinese Class", context)
        self.assertIn("Chemistry Class", context)
        self.assertIn("Teacher: Mei Lin", context)
        self.assertNotIn("Advanced Architecture", context)
        self.assertIn("UNTRUSTED DATA", context)

    def test_ui_keeps_all_imported_classes_and_no_verification_gate(self):
        self.import_fixture()
        seen = []

        def fake_calendar(*, events, options, **kwargs):
            seen.extend(events)
            return {"callback": ""}

        with patch.object(planner_ui, "calendar", side_effect=fake_calendar):
            at = AppTest.from_file(
                str(Path(__file__).resolve().parent / "app.py"),
                default_timeout=40,
            ).run()
        self.assertEqual(
            len(at.exception), 0,
            repr([x.message for x in at.exception]),
        )
        titles = [event["title"] for event in seen]
        self.assertEqual(titles.count("Chinese Class"), 2)
        self.assertIn("Chemistry Class", titles)
        self.assertNotIn("UNVERIFIED", " ".join(titles))
        self.assertNotIn(
            "planner_show_unverified_imports",
            [x.key for x in at.checkbox],
        )

    def test_no_data_is_deleted_or_rewritten_by_new_calendar_behavior(self):
        ids = self.import_fixture()
        before = [planner.get_item(uid) for uid in ids]
        cc.schedule_for_range(date(2026, 10, 12), date(2026, 10, 18))
        after = [planner.get_item(uid) for uid in ids]
        self.assertEqual(before, after)

    def test_academic_class_questions_still_use_the_language_model(self):
        self.import_fixture()
        with patch.object(
            conv, "_local_model_reply",
            return_value="Python classes define reusable objects.",
        ) as model:
            reply, modified = conv.respond(
                "What is a class in Python?",
                now=datetime(2026, 10, 10),
                model="test-model",
            )
        self.assertFalse(modified)
        self.assertIn("Python classes", reply)
        model.assert_called_once()

    def test_add_task_with_class_name_is_not_blocked_by_calendar_lookup(self):
        self.import_fixture()
        reply, modified = conv.respond(
            "add task study for my chemistry class due tomorrow",
            now=datetime(2026, 10, 10),
        )
        self.assertTrue(modified)
        self.assertIn("Added", reply)
        created = [task for task in planner.all_tasks()
                   if task["title"] == "study for my chemistry class"]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["due"], "2026-10-11")

    def test_generic_schedule_questions_are_grounded_not_generated(self):
        self.import_fixture()
        with patch.object(
            conv, "_local_model_reply",
            return_value="You have Advanced Engineering with Mr. Atlas.",
        ) as model:
            reply, acted = conv.respond(
                "What do I have next week?",
                now=datetime(2026, 10, 10),
                model="not-loaded",
            )
            self.assertFalse(acted)
            self.assertIn("Chinese Class", reply)
            self.assertIn("Chemistry Class", reply)
            self.assertNotIn("Advanced Engineering", reply)
            model.assert_not_called()

    def test_unknown_subject_returns_missing_not_model_output(self):
        self.import_fixture()
        output, acted = conv.respond(
            "When is my next advanced engineering class?",
            now=datetime(2026, 10, 10),
            model="__aaron_trained__",
        )
        self.assertFalse(acted)
        self.assertIn("can't find", output.lower())
        self.assertNotIn("10:05", output)

    def test_one_clock_aligned_week_replaces_second_scrollable_week(self):
        from inspect import getsource
        source = getsource(planner_ui.calendar_page)
        self.assertIn('"initialView": "timeGridWeek"', source)
        self.assertIn('"allDayText": "TASKS"', source)
        self.assertNotIn("_readable_week_agenda(", source)
        self.assertNotIn("dayGridWeek", source)
        self.assertIn("aaron_planner_aligned_week_v10", source)


if __name__ == "__main__":
    unittest.main()
