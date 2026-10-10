"""Integration coverage for safe task deletion and all five Streamlit tabs."""
from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import assistant_core as core
import planner
import training_data
import gmail_access


class TaskCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [
            patch.object(core, "DATA", root),
            patch.object(core, "DB", root / "state.sqlite3"),
            patch.object(core, "WEIGHTS", root / "priority.json"),
            patch.object(core, "LEGACY_MEMORY", root / "legacy.sqlite3"),
            patch.object(training_data, "DATA", root),
            patch.object(training_data, "MODEL_HOME", root / "trained_models"),
            patch.object(training_data, "JOB_HOME", root / "training_jobs"),
            patch.object(training_data, "ACTIVE_MODEL", root / "active_finetune.json"),
            patch.object(gmail_access, "DATA", root),
            patch.object(gmail_access, "CLIENT_FILE", root / "gmail_client.json"),
            patch.object(gmail_access, "TOKEN_FILE", root / "gmail_token.json"),
            patch.object(gmail_access, "PENDING_FILE", root / "gmail_auth_pending.json"),
        ]
        for p in self.patches:
            p.start()
        planner.ensure_schema()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def seed_data(self):
        manual_open = planner.create_item(
            title="My test homework", due="2026-10-16",
            description="Manually created work",
        )
        manual_completed = planner.create_item(
            title="My already finished task", due="2026-10-14"
        )
        planner.toggle_complete(manual_completed)
        old_manual, _ = core.add_task("Older manual task")
        imported, _ = core.add_task(
            "Imported school assignment", source="blackbaud",
            external_id="bb-44",
        )
        email, _ = core.add_task(
            "Email homework reminder", source="email",
            external_id="mail-22",
        )
        event = planner.create_item(
            title="Band rehearsal", due="2026-10-17",
            item_type="event", due_time="16:00",
        )
        core.remember("favorite color", "blue")
        training_data.add_example("Say hello", "Hello!")
        return manual_open, manual_completed, old_manual, imported, email, event

    def test_bulk_delete_only_clears_manually_added_tasks(self):
        manual_open, completed, old, imported, email, event = self.seed_data()
        self.assertEqual(planner.manually_added_task_count(), 3)
        count, backup = planner.clear_manually_added_tasks(expected_count=3)
        self.assertEqual(count, 3)
        self.assertTrue(Path(backup).exists())
        for task in (manual_open, completed, old):
            self.assertIsNone(planner.get_item(task))
        for task in (imported, email, event):
            self.assertIsNotNone(planner.get_item(task))
        self.assertEqual(core.recall("favorite color"), "blue")
        self.assertEqual(len(training_data.examples()), 1)
        self.assertNotIn("Band rehearsal", [
            task["title"] for task in planner.all_tasks()
        ])
        # Full database backup existed BEFORE deletion and can be restored.
        with sqlite3.connect(backup) as db:
            remaining = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        self.assertEqual(remaining, 6)

    def test_bulk_delete_rejects_stale_count_without_deleting(self):
        self.seed_data()
        with self.assertRaisesRegex(ValueError, "changed"):
            planner.clear_manually_added_tasks(expected_count=2)
        self.assertEqual(planner.manually_added_task_count(), 3)
        self.assertFalse((Path(core.DB).parent / "backups").exists())

    def test_zero_manual_tasks_noop(self):
        count, path = planner.clear_manually_added_tasks(expected_count=0)
        self.assertEqual(count, 0)
        self.assertIsNone(path)

    def test_single_task_deletion_leaves_other_tasks_alone(self):
        manual_open, completed, old, imported, email, event = self.seed_data()
        self.assertTrue(planner.delete_item(manual_open))
        self.assertIsNone(planner.get_item(manual_open))
        self.assertEqual(planner.manually_added_task_count(), 2)
        for kept in (completed, old, imported, email, event):
            self.assertIsNotNone(planner.get_item(kept))

    def test_cli_preview_and_confirmed_clear(self):
        self.seed_data()
        from clear_my_tasks import main
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([])
        self.assertEqual(code, 0)
        self.assertIn("Preview only", out.getvalue())
        self.assertEqual(planner.manually_added_task_count(), 3)
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--yes"])
        self.assertEqual(code, 0)
        self.assertEqual(planner.manually_added_task_count(), 0)
        self.assertIn("Backup saved", out.getvalue())

    def _run_app(self):
        path = str(Path(__file__).resolve().parent / "app.py")
        at = AppTest.from_file(path, default_timeout=45).run()
        self.assertEqual(
            len(at.exception), 0,
            "Full five-tab application raised a Streamlit exception: " +
            repr([e.message for e in at.exception]),
        )
        return at

    def test_full_app_renders_all_tabs_and_duplicate_task_widgets(self):
        self.seed_data()
        at = self._run_app()
        self.assertEqual(len(at.tabs), 5)
        self.assertIn("priorities_planner_0_title", [
            field.key for field in at.get("text_input")
        ])
        self.assertIn("calendar_planner_0_title", [
            field.key for field in at.get("text_input")
        ])
        self.assertTrue(any(
            button.key == "priorities_bulk_delete" for button in at.button
        ))

    def test_delete_task_via_buttons_then_clear_remaining_manual_tasks(self):
        first, completed, old, imported, email, event = self.seed_data()
        at = self._run_app()

        at.button(key=f"priorities_all_delete_{first}").click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertIsNotNone(planner.get_item(first))
        at.button(key="priorities_confirm_single_delete").click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertIsNone(planner.get_item(first))
        self.assertEqual(planner.manually_added_task_count(), 2)

        at.checkbox(key="priorities_confirm_bulk_delete").set_value(True).run()
        self.assertEqual(len(at.exception), 0)
        at.button(key="priorities_bulk_delete").click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(planner.manually_added_task_count(), 0)
        for task in (imported, email, event):
            self.assertIsNotNone(planner.get_item(task))


if __name__ == "__main__":
    unittest.main()
