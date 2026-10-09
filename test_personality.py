"""Tests for user-directed, fully local personality learning."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import individual
from personality import (
    get_profile, save_profile, teach_reply, learned_response,
    forget_example, learned_examples,
)


class PersonalityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(individual, "DB", Path(self.tmp.name) / "individual.sqlite3")
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.tmp.cleanup()

    def test_profile_persists(self):
        save_profile(3, 3, 2, "gang, lowk")
        self.assertEqual(get_profile()["energy"], "3")
        self.assertEqual(get_profile()["favorite_phrases"], "gang, lowk")

    def test_reply_example_is_used(self):
        self.assertTrue(teach_reply("What's good?", "yoooo gang 😭"))
        self.assertEqual(individual.respond("whats good"), "yoooo gang 😭")
        self.assertEqual(learned_response("what's good?"), "yoooo gang 😭")

    def test_personality_keeps_facts_and_memory(self):
        save_profile(3, 2, 1, "bro")
        individual.respond("my favorite snack is chips")
        self.assertEqual(individual.recall_fact("user", "favorite snack"), "chips")
        self.assertIn("chips", individual.respond("what is my favorite snack"))
        self.assertGreater(len(individual.history()), 0)

    def test_can_forget_a_taught_response(self):
        teach_reply("hey gang", "yooo")
        self.assertEqual(len(learned_examples()), 1)
        forget_example("hey gang")
        self.assertIsNone(learned_response("hey gang"))


if __name__ == "__main__":
    unittest.main()
