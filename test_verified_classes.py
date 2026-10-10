"""Regression tests: school-wide calendar entries are NOT evidence of enrollment.

All data is invented in isolated SQLite fixtures. Imported events are visible
for review, but may never be presented as the user's verified classes until
the user explicitly marks a matching iCalendar UID as theirs.
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


class VerifiedCalendarTests(unittest.TestCase):
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
        """School-wide export with repeated classes for another student."""
        rows = [
            ("g1", "Advanced Architecture: Digital Domains",
             "school:other-architect:20261016T1005", "2026-10-16",
             "Location: 1003 Teacher: Atlas"),
            ("g2", "Advanced Architecture: Digital Domains",
             "school:other-architect:20261023T1005", "2026-10-23",
             "Location: 1003 Teacher: Atlas"),
            ("g3", "High School Math",
             "school:other-math:20261017T0810", "2026-10-17",
             "Location: 421 Teacher: Kellam"),
        ]
        with core.connect() as db:
            db.executemany(
                """INSERT INTO tasks
                 (id,title,external_id,due,due_time,notes,item_type,
                  source,created_at)
                  VALUES (?,?,?,?,?,?,?,?,?)""",
                [
                    (item_id, title, external_id, due, "10:05", notes,
                     "event", "google_calendar", "2026-10-10T09:00:00")
                    for item_id, title, external_id, due, notes in rows
                ]
            )
            db.commit()
        return [r[0] for r in rows]

    def test_existing_school_import_defaults_to_unverified(self):
        ids = self.import_fixture()
        for item_id in ids:
            entry = planner.get_item(item_id)
            self.assertEqual(entry["personal_status"], "unverified")
            self.assertFalse(planner.is_verified_personal(entry))
        counts = planner.imported_review_counts()
        self.assertEqual(counts["unverified"], 3)

    def test_assistant_omits_other_students_imported_events(self):
        self.import_fixture()
        reply, action = conv.respond(
            "What is on my calendar next week?",
            now=datetime(2026, 10, 10, 9, 0),
        )
        self.assertFalse(action)
        self.assertNotIn("Advanced Architecture", reply)
        self.assertNotIn("High School Math", reply)
        self.assertIn("unverified", reply.lower())
        self.assertIn("won't guess", reply.lower())

        query, action = conv.respond(
            "When is my next advanced architecture class?",
            now=datetime(2026, 10, 10),
        )
        self.assertFalse(action)
        self.assertNotIn("Oct 16", query)
        self.assertIn("no verified", query)

        classes, action = conv.respond(
            "What classes am I taking?",
            now=datetime(2026, 10, 10),
        )
        self.assertFalse(action)
        self.assertNotIn("Advanced Architecture", classes)

    def test_teacher_room_and_general_class_questions_never_hallucinate(self):
        self.import_fixture()
        for question in (
            "Who is my teacher for Advanced Architecture?",
            "What is my classroom?",
            "Which classes do I have on Friday?",
            "Show me my full class timetable",
        ):
            reply, modified = conv.respond(
                question, now=datetime(2026, 10, 10), model="not-installed",
            )
            self.assertFalse(modified)
            self.assertNotIn(
                "Teacher: Atlas", reply,
                "The assistant disclosed an unverified teacher for: " + question,
            )
            self.assertNotIn(
                "Advanced Architecture", reply,
                "The assistant attributed another student's course for: " + question,
            )
            self.assertTrue(
                any(term in reply.lower() for term in (
                    "verify", "verified", "unverified", "confirm"
                )),
                repr(reply),
            )

    def test_local_model_context_never_receives_unverified_classes(self):
        self.import_fixture()
        ctx = cc.calendar_model_context(
            today=date(2026, 10, 10), days=14
        )
        self.assertNotIn("Advanced Architecture", ctx)
        self.assertNotIn("High School Math", ctx)
        self.assertIn("Only events manually added", ctx)

    def test_confirming_class_updates_repeats_only_not_other_majors(self):
        ids = self.import_fixture()
        changed = planner.set_imported_personal_status(ids[0], "mine")
        self.assertEqual(changed, 2)
        self.assertEqual(planner.get_item(ids[1])["personal_status"], "mine")
        self.assertEqual(planner.get_item(ids[2])["personal_status"], "unverified")
        self.assertEqual(
            len(cc.schedule_for_range(
                date(2026, 10, 16), date(2026, 10, 24)
            )),
            2,
        )
        answer, acted = conv.respond(
            "What's on my calendar next week?",
            now=datetime(2026, 10, 10),
        )
        self.assertFalse(acted)
        self.assertIn("Advanced Architecture", answer)
        self.assertNotIn("High School Math", answer)
        self.assertIn("unverified", answer.lower())

    def test_rejecting_class_hides_all_repeated_instances(self):
        ids = self.import_fixture()
        n = planner.set_imported_personal_status(ids[0], "not_mine")
        self.assertEqual(n, 2)
        self.assertFalse(planner.is_verified_personal(planner.get_item(ids[0])))
        self.assertFalse(planner.is_verified_personal(planner.get_item(ids[1])))
        self.assertEqual(planner.get_item(ids[2])["personal_status"], "unverified")

    def test_manual_events_remain_trusted_without_import_confirmation(self):
        self.import_fixture()
        manual = planner.create_item(
            title="My actual Geometry class", due="2026-10-16",
            item_type="event", due_time="12:10",
        )
        self.assertTrue(planner.is_verified_personal(planner.get_item(manual)))
        schedule = cc.schedule_for_range(
            date(2026, 10, 16), date(2026, 10, 17)
        )
        self.assertEqual([x["title"] for x in schedule],
                         ["My actual Geometry class"])

    def test_review_ui_does_not_show_unverified_classes_in_default_calendar(self):
        self.import_fixture()
        seen = []

        def fake_calendar(*, events, options, **kwargs):
            seen.extend(events)
            return {"callback": ""}

        with patch.object(planner_ui, "calendar", side_effect=fake_calendar):
            app = AppTest.from_file(
                str(Path(__file__).resolve().parent / "app.py"),
                default_timeout=40,
            ).run()
        self.assertEqual(
            len(app.exception), 0,
            repr([error.message for error in app.exception]),
        )
        self.assertFalse(any(
            "Architecture" in event["title"] for event in seen
        ))
        self.assertTrue(any(
            "Review imported classes" in md.value
            for md in app.get("markdown")
        ) or any(
            "Review imported classes" in str(exp.label)
            for exp in app.get("expander")
        ))

    def test_existing_source_rows_not_deleted_by_verification(self):
        ids = self.import_fixture()
        planner.set_imported_personal_status(ids[0], "mine")
        planner.set_imported_personal_status(ids[2], "not_mine")
        for item_id in ids:
            self.assertIsNotNone(planner.get_item(item_id))

    def test_reimport_preserves_confirmation_for_new_recurrence(self):
        from google_calendar_import import import_google_calendar

        def calendar_export(count):
            lines = [
                "BEGIN:VCALENDAR", "VERSION:2.0",
                "BEGIN:VEVENT", "UID:verified-class@example.edu",
                "DTSTART;TZID=America/New_York:20261012T100000",
                "DTEND;TZID=America/New_York:20261012T110000",
                f"RRULE:FREQ=WEEKLY;COUNT={count}",
                "SUMMARY:My actual Physics Class", "END:VEVENT",
                "END:VCALENDAR", "",
            ]
            return "\r\n".join(lines).encode("utf-8")

        import_google_calendar(
            calendar_export(2), "school.ics",
            from_date=date(2026, 10, 1), months=2,
        )
        first_import = [
            r for r in planner.items_for_calendar()
            if r.get("source") == "google_calendar"
        ]
        self.assertEqual(len(first_import), 2)
        planner.set_imported_personal_status(first_import[0]["id"], "mine")
        import_google_calendar(
            calendar_export(3), "school.ics",
            from_date=date(2026, 10, 1), months=2,
        )
        rows = [
            r for r in planner.items_for_calendar()
            if r.get("source") == "google_calendar"
        ]
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["personal_status"] == "mine" for r in rows))

    def test_full_title_mode_is_stacked_week_and_scrollable(self):
        from planner_ui import CALENDAR_CSS, _readable_week_agenda
        from inspect import getsource
        src = getsource(planner_ui.calendar_page)
        self.assertIn('"initialView": "dayGridWeek"', src)
        self.assertIn('height=390', getsource(_readable_week_agenda))
        self.assertIn('planner_read_full_', getsource(_readable_week_agenda))
        self.assertIn('font-size:14px', CALENDAR_CSS)

if __name__ == "__main__":
    unittest.main()
