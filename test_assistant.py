"""Offline regression tests for the simplified AARON-1 assistant."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import assistant_core as core
import gmail_access as gmail


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            patch.object(core, "DATA", root),
            patch.object(core, "DB", root / "tasks.sqlite3"),
            patch.object(core, "WEIGHTS", root / "weights.json"),
            patch.object(core, "LEGACY_MEMORY", root / "nothing.sqlite3"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_tasks_can_be_added_ranked_and_completed(self):
        one, added = core.add_task("Finish chemistry", "2026-10-10")
        self.assertTrue(added)
        self.assertEqual(len(core.list_tasks()), 1)
        self.assertEqual(core.list_tasks()[0]["due"], "2026-10-10")
        self.assertTrue(core.update_task(one, completed=True))
        self.assertEqual(len(core.list_tasks()), 0)

    def test_chat_adds_task_before_listing_homework(self):
        reply = core.concise_reply("add task geometry homework")
        self.assertIn("Added:", reply)
        self.assertEqual(len(core.list_tasks()), 1)
        self.assertEqual(core.list_tasks()[0]["title"], "geometry homework")
        response = core.concise_reply("what homework is due")
        self.assertIn("geometry homework", response)

    def test_task_priority_updates_the_same_personal_policy(self):
        task_id, _ = core.add_task("Read notes")
        before = core.score_task(core.list_tasks()[0])
        self.assertTrue(core.learn_priority(task_id, important=True))
        after = core.score_task(core.list_tasks()[0])
        self.assertGreater(after, before)
        _, feedback_count = core.load_weights()
        self.assertEqual(feedback_count, 1)

    def test_priority_prefers_deadlines(self):
        overdue = {"due": "2026-10-01", "source": "blackbaud", "starred": 0}
        optional = {"due": None, "source": "manual", "starred": 0}
        self.assertGreater(core.score_task(overdue, today=date(2026, 10, 9)),
                           core.score_task(optional, today=date(2026, 10, 9)))

    def test_csv_import_is_repeatable(self):
        content = b"Assignment,Due Date\nRead chapter 3,10/20/2026\nMath sheet,2026-10-21\n"
        self.assertEqual(core.parse_csv(content), 2)
        self.assertEqual(core.parse_csv(content), 0)
        self.assertEqual(len(core.list_tasks()), 2)

    def test_ics_import_is_repeatable(self):
        ics = (b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
               b"BEGIN:VEVENT\r\nUID:hw123\r\n"
               b"DTSTART;VALUE=DATE:20261021\r\n"
               b"SUMMARY:Practice geometry\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        self.assertEqual(core.parse_ics(ics), 1)
        self.assertEqual(core.parse_ics(ics), 0)

    def test_facts_can_be_saved(self):
        core.concise_reply("my favorite subject is chemistry")
        self.assertEqual(core.recall("favorite subject"), "chemistry")
        self.assertIn("chemistry", core.concise_reply("what is my favorite subject"))


    def test_calendar_month_bounds_and_year_navigation(self):
        self.assertEqual(core.change_month(date(2026, 1, 1), -1),
                         date(2025, 12, 1))
        self.assertEqual(core.change_month(date(2026, 12, 1), 1),
                         date(2027, 1, 1))
        self.assertEqual(core.month_bounds(2028, 2),
                         (date(2028, 2, 1), date(2028, 3, 1)))

    def test_calendar_queries_only_selected_month(self):
        core.add_task("October chemistry", "2026-10-09")
        core.add_task("End of October", "2026-10-31")
        core.add_task("November geometry", "2026-11-01")
        core.add_task("September reading", "2026-09-30")
        core.add_task("Unscheduled")

        october = core.tasks_due_in_month(2026, 10)
        self.assertEqual({task["title"] for task in october},
                         {"October chemistry", "End of October"})
        self.assertEqual(len(core.tasks_due_in_month(2026, 11)), 1)
        self.assertEqual(len(core.tasks_without_due_date()), 1)

    def test_calendar_done_reopen_and_schedule(self):
        task_id, _ = core.add_task("Algebra practice", "2026-10-22")
        self.assertTrue(core.update_task(task_id, completed=True))
        self.assertEqual(len(core.tasks_due_in_month(2026, 10)), 1)
        self.assertEqual(len(core.tasks_due_in_month(2026, 10, include_completed=False)), 0)
        self.assertTrue(core.update_task(task_id, completed=False))
        self.assertEqual(len(core.tasks_due_in_month(2026, 10, include_completed=False)), 1)
        self.assertTrue(core.set_task_due_date(task_id, "2026-11-04"))
        self.assertEqual(len(core.tasks_due_in_month(2026, 10)), 0)
        self.assertEqual(core.tasks_due_in_month(2026, 11)[0]["due"], "2026-11-04")
        with self.assertRaises(ValueError):
            core.set_task_due_date(task_id, "tomorrow")

    def test_calendar_displays_imported_school_assignments(self):
        ics = (b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
               b"BEGIN:VEVENT\r\nUID:science-test\r\n"
               b"DTSTART;VALUE=DATE:20261020\r\n"
               b"SUMMARY:Science test\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        self.assertEqual(core.parse_ics(ics), 1)
        october = core.tasks_due_in_month(2026, 10)
        self.assertEqual(len(october), 1)
        self.assertEqual(october[0]["source"], "blackbaud")
        self.assertEqual(october[0]["due"], "2026-10-20")

    def test_seed_is_available(self):
        self.assertEqual(len(core.load_weights()[0]), len(core.FEATURES))


class GmailSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [
            patch.object(gmail, "DATA", root),
            patch.object(gmail, "CLIENT_FILE", root / "client.json"),
            patch.object(gmail, "TOKEN_FILE", root / "token.json"),
            patch.object(gmail, "PENDING_FILE", root / "pending.json"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def test_gmail_not_connected_without_authorization(self):
        self.assertFalse(gmail.connected())
        self.assertFalse(gmail.client_ready())

    def test_rejects_wrong_client_or_redirect(self):
        with self.assertRaises(ValueError):
            gmail.store_client_upload(b'{"installed": {"client_id": "x"}}')
        bad = {"web": {"client_id": "x", "client_secret": "y",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "redirect_uris": ["http://localhost:9000"]}}
        with self.assertRaises(ValueError):
            gmail.store_client_upload(json.dumps(bad).encode())
        self.assertFalse(gmail.connected())

    def test_disconnection_removes_local_token(self):
        gmail.secure_save(gmail.TOKEN_FILE, "{}")
        self.assertTrue(gmail.connected())
        gmail.disconnect()
        self.assertFalse(gmail.connected())


if __name__ == "__main__":
    unittest.main()
