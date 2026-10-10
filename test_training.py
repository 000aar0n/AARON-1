"""Offline tests for AARON-1's opt-in, genuinely trainable LoRA architecture."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import assistant_core as core
import assistant_conversation as conversation
import training_data as data
import train_aaron
import trained_chat


class FakeTokenizer:
    eos_token = "<eos>"

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
        assert tokenize and add_generation_prompt
        return [11, 12, 13, 14]

    def encode(self, value, add_special_tokens=False):
        assert add_special_tokens is False
        return [30, 31, 32]


class TrainingDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        folder = Path(self.temp.name)
        self.patches = [
            patch.object(core, "DATA", folder),
            patch.object(core, "DB", folder / "state.db"),
            patch.object(core, "WEIGHTS", folder / "weights.json"),
            patch.object(data, "DATA", folder),
            patch.object(data, "MODEL_HOME", folder / "trained_models"),
            patch.object(data, "JOB_HOME", folder / "training_jobs"),
            patch.object(data, "ACTIVE_MODEL", folder / "active_finetune.json"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_no_automatic_training_on_gmail_or_regular_chat(self):
        core.add_task("Chemistry assignment", source="email",
                      external_id="mail001", notes="Personal snippet")
        core.remember("favorite drink", "tea")
        conversation.respond("hello")
        self.assertEqual(data.examples(), [])

    def test_only_explicitly_approved_examples_are_stored(self):
        example_id = data.add_example("How was school?", "Pretty good, gang.")
        rows = data.examples()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["prompt"], "How was school?")
        self.assertTrue(data.delete_example(example_id))
        self.assertFalse(data.delete_example(example_id))
        self.assertEqual(data.examples(), [])

    def test_reapproval_replaces_old_answer_instead_of_contradicting(self):
        first = data.add_example("What's up?", "Hello!")
        second = data.add_example("what's up?", "YOOO gang!")
        self.assertEqual(first, second)
        self.assertEqual(len(data.examples()), 1)
        self.assertEqual(data.examples()[0]["response"], "YOOO gang!")

    def test_validation_and_source_restrictions(self):
        with self.assertRaises(ValueError):
            data.add_example("", "yes")
        with self.assertRaises(ValueError):
            data.add_example("question", "reply", source="gmail")
        with self.assertRaises(ValueError):
            data.create_job()
        with self.assertRaises(ValueError):
            data.create_job(model="unknown/model")
        with self.assertRaises(ValueError):
            data.create_job(epochs=8)

    def _populate(self, count=16):
        for i in range(count):
            data.add_example(f"Message {i}?", f"Preferred answer {i}.")

    def test_dataset_split_is_stable_and_does_not_overlap(self):
        self._populate()
        rows = data.examples()
        first, evaluation = data.training_split(rows)
        second, second_eval = data.training_split(list(reversed(rows)))
        self.assertEqual(first, second)
        self.assertEqual(evaluation, second_eval)
        self.assertEqual(len(first) + len(evaluation), 16)
        self.assertFalse({x["id"] for x in first} & {x["id"] for x in evaluation})

    def test_job_snapshots_are_local_and_activate_only_when_complete(self):
        self._populate(12)
        job = data.create_job(epochs=2)
        self.assertEqual(job["status"], "queued")
        snapshot = json.loads(
            (data.JOB_HOME / (job["id"] + ".dataset.json")).read_text()
        )
        self.assertEqual(len(snapshot["train"]) + len(snapshot["eval"]), 12)
        with self.assertRaises(ValueError):
            data.activate_trained(job["id"])
        folder = data.MODEL_HOME / job["id"] / "adapter"
        folder.mkdir(parents=True)
        (folder / "adapter_config.json").write_text('{"peft_type":"LORA"}')
        (folder / "adapter_model.safetensors").write_bytes(b"mock safetensors file")
        data.update_job(job["id"], status="completed")
        data.activate_trained(job["id"])
        self.assertEqual(data.trained_model()["job_id"], job["id"])
        data.deactivate_trained()
        self.assertIsNone(data.trained_model())

    def test_continued_training_retains_previous_adapter_link(self):
        self._populate(10)
        old = data.create_job()
        directory = data.MODEL_HOME / old["id"] / "adapter"
        directory.mkdir(parents=True)
        (directory / "adapter_config.json").write_text("{}")
        (directory / "adapter_model.safetensors").write_bytes(b"weights")
        data.update_job(old["id"], status="completed")
        data.activate_trained(old["id"])
        new = data.create_job(model=data.BASE_MODEL)
        self.assertEqual(new["parent_job_id"], old["id"])
        restarted = data.create_job(
            model=data.BASE_MODEL, continue_from_active=False
        )
        self.assertIsNone(restarted["parent_job_id"])
        different = data.create_job(
            model=data.ALLOWED_BASE_MODELS[1]
        )
        self.assertIsNone(different["parent_job_id"])

    def test_export_import_uses_only_approved_pairs(self):
        self._populate(8)
        original = data.export_jsonl()
        self.assertEqual(original.count("\n"), 8)
        self.assertEqual(data.import_jsonl(original), 0)
        data.delete_example(data.examples()[0]["id"])
        self.assertEqual(data.import_jsonl(original), 1)
        with self.assertRaises(ValueError):
            data.import_jsonl('{"email_password": "secret"}')
        self.assertEqual(len(data.examples()), 8)

    def test_no_absolute_external_paths_can_be_activated(self):
        self._populate(8)
        job = data.create_job()
        data.update_job(job["id"], status="completed")
        (data.MODEL_HOME / job["id"]).mkdir(exist_ok=True)
        # No adapter files => refusal instead of arbitrary path loading.
        with self.assertRaises(ValueError):
            data.activate_trained(job["id"])

    def test_pretrained_mode_dispatches_without_ollama(self):
        self._populate(8)
        with (patch("trained_chat.generate_base",
                    return_value="Hello, this is my pretrained model") as native,
              patch.object(conversation, "urlopen",
                           side_effect=AssertionError("Ollama must not be called"))):
            result, acted = conversation.respond(
                "Tell me about the solar system",
                previous=[{"role": "user", "message": "We are studying space"}],
                model="__aaron_base__",
            )
        self.assertEqual(result, "Hello, this is my pretrained model")
        self.assertFalse(acted)
        self.assertTrue(native.called)

    def test_base_inference_uses_supported_local_model_only(self):
        with patch("trained_chat._generate", return_value="test") as inference:
            result = trained_chat.generate_base([
                {"role": "user", "content": "Hello"}
            ])
        self.assertEqual(result, "test")
        kwargs = inference.call_args.kwargs
        self.assertEqual(kwargs["base"], data.BASE_MODEL)
        self.assertIsNone(kwargs["adapter"])
        with self.assertRaises(ValueError):
            trained_chat.generate_base(
                [{"role": "user", "content": "Hello"}],
                base_model="random/untrusted-model"
            )

    def test_trained_mode_dispatches_without_ollama_call(self):
        self._populate(8)
        with patch("trained_chat.generate", return_value="Yep, that's my trained reply") as mock:
            result, acted = conversation.respond(
                "tell me something interesting",
                previous=[{"role": "user", "message": "Hey"}],
                model="__aaron_trained__",
            )
            self.assertEqual(result, "Yep, that's my trained reply")
            self.assertFalse(acted)
            self.assertTrue(mock.called)


class LoRATests(unittest.TestCase):
    def test_training_labels_mask_prompt_and_not_answer(self):
        sample = train_aaron.encode_example(
            FakeTokenizer(), "How are you?", "Good!", max_tokens=64
        )
        self.assertEqual(sample["input_ids"], [11, 12, 13, 14, 30, 31, 32])
        self.assertEqual(sample["labels"], [-100, -100, -100, -100, 30, 31, 32])
        self.assertEqual(sample["attention_mask"], [1]*7)

    def test_overlong_prefix_never_drops_assistant_targets(self):
        class LongTokenizer(FakeTokenizer):
            def apply_chat_template(self, *args, **kwargs):
                return list(range(400))
            def encode(self, *args, **kwargs):
                return list(range(20))
        sample = train_aaron.encode_example(
            LongTokenizer(), "hi", "test", max_tokens=64
        )
        self.assertEqual(len(sample["input_ids"]), 64)
        self.assertEqual(sample["labels"].count(-100), 44)
        self.assertEqual(sample["labels"][-20:], list(range(20)))

    def test_padding_keeps_loss_masked(self):
        class FakeTorch:
            long = "int64"
            def tensor(self, value, dtype=None):
                return value
        one = {"input_ids": [3, 4], "attention_mask": [1, 1],
               "labels": [-100, 4]}
        two = {"input_ids": [5], "attention_mask": [1],
               "labels": [5]}
        batch = train_aaron.collate_batch([one, two], 0, FakeTorch())
        self.assertEqual(batch["input_ids"], [[3, 4], [5, 0]])
        self.assertEqual(batch["labels"], [[-100, 4], [5, -100]])
        self.assertEqual(batch["attention_mask"], [[1, 1], [1, 0]])


if __name__ == "__main__":
    unittest.main()
