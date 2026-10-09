"""Tests for AARON-1's persistent goal-conditioned tool policy.

The evaluation only covers the two declared simulated environments.
"""
import json
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agency import (
    ACTIONS, AARONAgent, GOALS, IDENTITY, PRETRAINED_POLICY,
    PracticeWorkspace, atomic_json, read_json, preview_local_folder,
)


class AgencyTests(unittest.TestCase):
    def test_tool_inspection_reveals_hidden_category(self):
        env = PracticeWorkspace("sort_inbox", random.Random(42), count=3)
        before = env.observe()
        self.assertEqual(before["tag"], "not inspected")
        result, done, after = env.step("inspect")
        self.assertEqual(result, -0.04)
        self.assertFalse(done)
        self.assertIn(after["tag"], GOALS["sort_inbox"]["categories"])
        self.assertEqual(before["current_item"], after["current_item"])

    def test_known_action_completes_task(self):
        env = PracticeWorkspace("triage_tasks", random.Random(42), count=1)
        env.step("inspect")
        key = env.observe()["tag"]
        action = GOALS["triage_tasks"]["correct_actions"][key]
        reward, done, _ = env.step(action)
        self.assertTrue(done)
        self.assertEqual(reward, 2.0)
        self.assertEqual(env.summary()["correct"], 1)

    def test_training_updates_one_persistent_policy(self):
        agent = AARONAgent()
        agent.train(count=3000, seed=11)
        self.assertEqual(agent.identity, IDENTITY)
        self.assertEqual(agent.episodes, 3000)
        self.assertGreater(agent.steps, agent.episodes)
        self.assertGreaterEqual(agent.evaluate(50)["accuracy"], .90)

    def test_pretrained_policy_generalizes_to_new_sandbox_instances(self):
        source = read_json(PRETRAINED_POLICY)
        self.assertIsNotNone(source, "Pretrained policy must be checked into repo")
        agent = AARONAgent(source)
        result = agent.evaluate(trials_per_goal=100, seed=918172)
        self.assertGreaterEqual(result["accuracy"], .98)
        self.assertGreaterEqual(result["complete_rate"], .98)

    def test_run_goal_returns_auditable_tool_trace(self):
        agent = AARONAgent(read_json(PRETRAINED_POLICY))
        run = agent.do_goal("sort_inbox", count=5, seed=40)
        self.assertEqual(run["summary"]["correct"], 5)
        self.assertEqual(run["summary"]["items"], 5)
        self.assertTrue(run["trace"])
        self.assertEqual(run["trace"][0]["tool"], "Inspect item")

    def test_save_restore_preserves_identity_training_and_weights(self):
        agent = AARONAgent(read_json(PRETRAINED_POLICY))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "policy.json"
            agent.save(path)
            restored = AARONAgent(read_json(path))
            self.assertEqual(restored.identity, IDENTITY)
            self.assertEqual(restored.q, agent.q)
            self.assertEqual(restored.episodes, agent.episodes)


    def test_local_preview_only_reads_permitted_file_names(self):
        agent = AARONAgent(read_json(PRETRAINED_POLICY))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "permitted"
            root.mkdir()
            sample = root / "homework.pdf"
            sample.write_text("untouched content", encoding="utf-8")
            with patch.dict(os.environ, {"AARON_AGENCY_PREVIEW_ROOT": str(root)}):
                preview = preview_local_folder(root, agent)
                self.assertEqual(preview["files_changed"], 0)
                self.assertEqual(preview["items"][0]["decision"], "Would organize into Documents")
                self.assertEqual(sample.read_text(encoding="utf-8"), "untouched content")

    def test_unapproved_preview_directory_rejected(self):
        agent = AARONAgent(read_json(PRETRAINED_POLICY))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "allowed"
            other = Path(directory) / "private"
            root.mkdir()
            other.mkdir()
            with patch.dict(os.environ, {"AARON_AGENCY_PREVIEW_ROOT": str(root)}):
                with self.assertRaises(ValueError):
                    preview_local_folder(other, agent)


if __name__ == "__main__":
    unittest.main()
