"""Chinese input and rule-based reply regression tests."""
import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from assistant_conversation import respond


class ChineseSupportTest(unittest.TestCase):
    def test_chinese_greeting(self):
        answer, changed = respond("你好", now=datetime(2026, 10, 10, 12, 0))
        self.assertFalse(changed)
        self.assertIn("你好", answer)

    def test_chinese_calendar_title_keeps_unicode(self):
        record = {"title": "中文课：城市交通", "due_time": "13:10"}
        with patch("assistant_conversation.schedule_for_range", return_value=[record]):
            answer, changed = respond(
                "明天有什么课？", now=datetime(2026, 10, 10, 12, 0)
            )
        self.assertFalse(changed)
        self.assertIn("明天", answer)
        self.assertIn(record["title"], answer)

    def test_no_model_does_not_claim_to_be_fluid_llm(self):
        answer, changed = respond(
            "我想练习中文", now=datetime(2026, 10, 10, 12, 0)
        )
        self.assertFalse(changed)
        self.assertIn("规则式助手", answer)

    def test_sqlite_roundtrip_keeps_hanzi(self):
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE chat(message TEXT)")
            original = "你好！中文课：城市交通 🚇"
            db.execute("INSERT INTO chat(message) VALUES (?)", (original,))
            self.assertEqual(db.execute("SELECT message FROM chat").fetchone()[0],
                             original)

    def test_ui_avoids_ime_enter_to_send(self):
        root = Path(__file__).resolve().parents[1]
        app = (root / "app.py").read_text(encoding="utf-8")
        self.assertIn('with st.form("aaron_chat_compose_form"', app)
        self.assertIn('st.form_submit_button("Send"', app)
        self.assertNotIn('st.chat_input(', app)
        theme = (root / "ui_theme.py").read_text(encoding="utf-8")
        calendar = (root / "planner_ui.py").read_text(encoding="utf-8")
        self.assertIn("PingFang SC", theme)
        self.assertIn("Microsoft YaHei", calendar)


if __name__ == "__main__":
    unittest.main()
