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
        content = b"Assignment,Due Date\\nRead chapter 3,10/20/2026\\nMath sheet,2026-10-21\\n"
        self.assertEqual(core.parse_csv(content), 2)
        self.assertEqual(core.parse_csv(content), 0)
        self.assertEqual(len(core.list_tasks()), 2)

    def test_ics_import_is_repeatable(self):
        ics = (b"BEGIN:VCALENDAR\\r\\nVERSION:2.0\\r\\n"
               b"BEGIN:VEVENT\\r\\nUID:hw123\\r\\n"
               b"DTSTART;VALUE=DATE:20261021\\r\\n"
               b"SUMMARY:Practice geometry\\r\\nEND:VEVENT\\r\\nEND:VCALENDAR\\r\\n")
        self.assertEqual(core.parse_ics(ics), 1)
        self.assertEqual(core.parse_ics(ics), 0)

    def test_facts_can_be_saved(self):
        core.concise_reply("my favorite subject is chemistry")
        self.assertEqual(core.recall("favorite subject"), "chemistry")
        self.assertIn("chemistry", core.concise_reply("what is my favorite subject"))

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
