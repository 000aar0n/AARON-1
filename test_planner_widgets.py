"""Regression test: Streamlit renders every tab, even when it's not selected.

Planner and Priorities both render the same editor and recommendation list.
The widgets must be assigned distinct keys for each tab, including when they
refer to the same task. AppTest catches StreamlitDuplicateElementKey errors.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import assistant_core as core
import planner


class StreamlitPlannerWidgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [
            patch.object(core, "DATA", root),
            patch.object(core, "DB", root / "state.sqlite3"),
            patch.object(core, "WEIGHTS", root / "priority.json"),
            patch.object(core, "LEGACY_MEMORY", root / "old.sqlite3"),
        ]
        for item in self.patches:
            item.start()
        planner.ensure_schema()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_calendar_and_priorities_editor_widget_keys_do_not_collide(self):
        # Same underlying tasks appear on both tabs simultaneously.
        planner.create_item(
            title="Geometry proof", due="2026-10-15", priority=4,
            description="Test the shared editor",
        )
        script = """
import streamlit as st
from planner_ui import _render_editor, _action_list

tab1, tab2 = st.tabs(["Planner", "Priorities"])
with tab1:
    _render_editor(scope="calendar")
    _action_list(limit=4, scope="calendar")
with tab2:
    _render_editor(scope="priorities")
    _action_list(limit=12, scope="priorities")
"""
        at = AppTest.from_string(script, default_timeout=25).run()
        self.assertEqual(
            len(at.exception), 0,
            "Both tabs should render together without duplicate widget keys: "
            + repr([e.message for e in at.exception]),
        )
        # The same two form fields must exist separately in each tab.
        keys = [item.key for item in at.get("text_input")]
        self.assertIn("calendar_planner_0_title", keys)
        self.assertIn("priorities_planner_0_title", keys)

    def test_scopes_cannot_be_omitted(self):
        # Required keyword-only scope protects against future duplicate calls.
        from planner_ui import _render_editor, _action_list
        with self.assertRaises(TypeError):
            _render_editor()
        with self.assertRaises(TypeError):
            _action_list()


if __name__ == "__main__":
    unittest.main()
