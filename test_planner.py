"""Planner v2: migration, timed entries, recommendations and conversational commands."""
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import assistant_core as core
import planner
import assistant_conversation as conversation


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [
            patch.object(core, "DATA", root),
            patch.object(core, "DB", root / "state.sqlite3"),
            patch.object(core, "WEIGHTS", root / "priority.json"),
            patch.object(core, "LEGACY_MEMORY", root / "old.sqlite3"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_existing_assignments_are_preserved_by_additive_migration(self):
        old_id, created = core.add_task("Old imported chemistry work", "2026-10-15",
                                        notes="Bring lab notebook", source="blackbaud",
                                        external_id="class-123")
        self.assertTrue(created)
        planner.ensure_schema()
        planner.ensure_schema()
        old = planner.get_item(old_id)
        self.assertEqual(old["title"], "Old imported chemistry work")
        self.assertEqual(old["notes"], "Bring lab notebook")
        self.assertEqual(old["source"], "blackbaud")
        self.assertEqual(old["item_type"], "task")
        self.assertEqual(old["priority_level"], 2)
        self.assertIsNone(old["due_time"])

    def test_timed_task_creation_edit_and_notes_persist(self):
        item_id = planner.create_item(
            title="Geometry proof", due="2026-10-15", due_time="17:30",
            description="Bring textbook. Do exercises 1–5.", priority=4,
            item_type="task", estimated_min=75,
        )
        original = planner.get_item(item_id)
        self.assertEqual(original["due_time"], "17:30")
        self.assertEqual(original["estimated_min"], 75)
        self.assertIn("textbook", original["notes"])
        self.assertTrue(planner.update_item(
            item_id, title="Geometry review", due="2026-10-16",
            due_time="15:15", description="Finish the proof", item_type="task",
            priority=3, estimated_min=45,
        ))
        updated = planner.get_item(item_id)
        self.assertEqual(updated["due"], "2026-10-16")
        self.assertEqual(updated["due_time"], "15:15")
        self.assertEqual(updated["priority_level"], 3)
        self.assertEqual(updated["notes"], "Finish the proof")

    def test_real_event_duration_and_time_are_calendar_visible(self):
        uid = planner.create_item(title="Coding club", due=date(2026, 10, 10),
                                  due_time="16:00", duration_min=90,
                                  description="Meet in lab", item_type="event")
        events = planner.calendar_events(planner.items_for_calendar())
        e = next(e for e in events if e["id"] == uid)
        self.assertEqual(e["start"], "2026-10-10T16:00:00")
        self.assertEqual(e["end"], "2026-10-10T17:30:00")
        self.assertFalse(e["allDay"])
        self.assertEqual(e["extendedProps"]["description"], "Meet in lab")

    def test_all_day_task_and_mark_complete(self):
        uid = planner.create_item(title="History packet", due="2026-10-10",
                                  priority=3)
        event = next(e for e in planner.calendar_events(planner.items_for_calendar())
                     if e["id"] == uid)
        self.assertTrue(event["allDay"])
        self.assertEqual(event["start"], "2026-10-10")
        self.assertTrue(planner.toggle_complete(uid))
        self.assertEqual(planner.get_item(uid)["completed"], 1)
        self.assertNotIn(uid, [x["id"] for x in planner.open_tasks()])
        self.assertTrue(planner.toggle_complete(uid, False))
        self.assertEqual(planner.get_item(uid)["completed"], 0)

    def test_action_engine_ranks_overdue_urgent_above_distant(self):
        later = planner.create_item(
            title="Review optional reading", due="2026-11-30",
            priority=1, estimated_min=120)
        urgent = planner.create_item(
            title="Chemistry quiz", due="2026-10-10",
            due_time="09:00", priority=4, estimated_min=30)
        picks = planner.next_actions(
            now=datetime(2026, 10, 10, 8, 0), limit=3)
        self.assertEqual(picks[0]["id"], urgent)
        self.assertIn("Due within 4 hours", picks[0]["why"])
        self.assertEqual(picks[-1]["id"], later)
        self.assertNotIn("estimated", picks[0]["why"].lower())

    def test_existing_completed_items_not_recommended(self):
        uid = planner.create_item(title="Already finished", due="2026-10-10",
                                  priority=4)
        planner.toggle_complete(uid, True)
        self.assertFalse(any(x["id"] == uid for x in planner.next_actions()))

    def test_priority_setting_and_validation(self):
        with self.assertRaises(ValueError):
            planner.create_item(title="Bad time", due="2026-10-10",
                                due_time="26:00")
        with self.assertRaises(ValueError):
            planner.create_item(title="Bad date", due="2026-02-30")
        with self.assertRaises(ValueError):
            planner.create_item(title="No event date", item_type="event")
        with self.assertRaises(ValueError):
            planner.create_item(title="Bad priority", priority=9)

    def test_item_delete_does_not_touch_other_entries(self):
        keep = planner.create_item(title="Keep me", due="2026-10-10")
        gone = planner.create_item(title="Remove me", due="2026-10-11")
        self.assertTrue(planner.delete_item(gone))
        self.assertIsNone(planner.get_item(gone))
        self.assertIsNotNone(planner.get_item(keep))
        self.assertFalse(planner.delete_item("not-real"))

    def test_conversation_can_add_a_timed_task_then_recall_tomorrow(self):
        now = datetime(2026, 10, 9, 20, 0)
        result, acted = conversation.respond(
            "add task read chapter 5 due tomorrow at 5pm", now=now)
        self.assertTrue(acted)
        self.assertIn("read chapter 5", result)
        entries = planner.daily_items(date(2026, 10, 10))
        self.assertEqual(entries[0]["due_time"], "17:00")
        answer, acted = conversation.respond(
            "what homework do i have tomorrow", now=now)
        self.assertFalse(acted)
        self.assertIn("read chapter 5", answer)

    def test_conversation_next_step_has_reason(self):
        planner.create_item(title="Math prep", due="2026-10-10",
                            due_time="11:00", priority=4)
        answer, acted = conversation.respond(
            "what should i do next", now=datetime(2026, 10, 10, 8))
        self.assertFalse(acted)
        self.assertIn("Math prep", answer)
        self.assertIn("priority", answer.lower())

    def test_conversation_memory_survives(self):
        conversation.respond("my favorite subject is chemistry")
        value, _ = conversation.respond("what's my favorite subject")
        self.assertIn("chemistry", value)

    def test_local_model_receives_recent_chat_and_saved_facts(self):
        core.remember("favorite food", "sushi")
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, *_args):
                return b'{"message":{"content":"Yep, sushi is your favorite."}}'

        def fake_open(request, timeout=0):
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        # urlopen is the only networking method; it is patched during tests.
        with patch.object(conversation, "urlopen", side_effect=fake_open):
            reply, acted = conversation.respond(
                "what food do i like?",
                previous=[{"role": "user", "message": "Do you remember me?"}],
                model="qwen2.5:3b",
            )
        self.assertFalse(acted)
        self.assertIn("sushi", reply)
        self.assertEqual(captured["url"],
                         "http://127.0.0.1:11434/api/chat")
        self.assertIn("favorite food: sushi",
                      captured["payload"]["messages"][0]["content"])
        self.assertTrue(any("Do you remember me?" in entry["content"]
                            for entry in captured["payload"]["messages"]))

    def test_natural_language_calendar_questions(self):
        planner.create_item(title="Chinese quiz", due="2026-10-12", due_time="11:15")
        text, action = conversation.respond(
            "what do i have monday", now=datetime(2026, 10, 9, 18))
        self.assertFalse(action)
        self.assertIn("Chinese quiz", text)
        all_due, action = conversation.respond(
            "what homework is due", now=datetime(2026, 10, 9, 18))
        self.assertIn("Chinese quiz", all_due)

    def test_local_chat_does_not_require_external_credentials(self):
        answer, action = conversation.respond("how are you")
        self.assertFalse(action)
        self.assertIn("Doing good", answer)


if __name__ == "__main__":
    unittest.main()
