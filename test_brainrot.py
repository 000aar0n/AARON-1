"""Regression tests for the opt-in-by-request max brainrot preset."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import individual
from personality import (
    ensure_brainrot_training, get_profile, teach_reply,
    learned_response, save_profile, forget_example, training_stats,
)
from brainrot_corpus import BRAINROT_EXAMPLES


class BrainrotTrainingTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.patch = patch.object(individual, "DB", Path(self.tempdir.name) / "brain.sqlite3")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tempdir.cleanup()

    def test_first_run_installs_corpus_and_maxes_style(self):
        self.assertGreater(len(BRAINROT_EXAMPLES), 100)
        added = ensure_brainrot_training()
        self.assertGreater(added, 100)
        self.assertEqual(get_profile()["slang"], "3")
        self.assertEqual(get_profile()["energy"], "3")
        self.assertEqual(get_profile()["humor"], "3")
        self.assertEqual(individual.respond("what is rizz"),
                         learned_response("what is rizz"))
        self.assertTrue(training_stats()["brainrot_installed"])

    def test_one_time_install_does_not_reset_personal_style(self):
        ensure_brainrot_training()
        save_profile(0, 0, 0, "plain")
        self.assertEqual(ensure_brainrot_training(), 0)
        self.assertEqual(get_profile()["slang"], "0")
        self.assertEqual(get_profile()["favorite_phrases"], "plain")

    def test_existing_user_taught_replies_win(self):
        teach_reply("hello", "my own reply")
        ensure_brainrot_training()
        self.assertEqual(individual.respond("hello"), "my own reply")

    def test_user_can_correct_seeded_reply(self):
        ensure_brainrot_training()
        teach_reply("hello", "actually, yo")
        self.assertEqual(individual.respond("HELLO!"), "actually, yo")
        ensure_brainrot_training(force=True)
        self.assertEqual(individual.respond("hello"), "actually, yo")

    def test_removing_examples_remains_removed_until_reapply(self):
        ensure_brainrot_training()
        forget_example("skibidi")
        ensure_brainrot_training()
        self.assertIsNone(learned_response("skibidi"))
        ensure_brainrot_training(force=True)
        self.assertIsNotNone(learned_response("skibidi"))

    def test_facts_and_training_state_survive_brainrot(self):
        individual.learn_fact("user", "favorite snack", "chips")
        ensure_brainrot_training(force=True)
        self.assertEqual(individual.recall_fact("user", "favorite snack"), "chips")
        self.assertIn("chips", individual.respond("what is my favorite snack"))


if __name__ == "__main__":
    unittest.main()
