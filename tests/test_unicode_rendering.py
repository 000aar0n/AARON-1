"""Check actual Unicode font loading in Streamlit and embedded FullCalendar."""
from pathlib import Path
import unittest

from unicode_support import FONT_IMPORT, FONT_STACK, UNICODE_SAMPLES
from ui_theme import STYLE
from planner_ui import CALENDAR_CSS


class UnicodeRenderingTest(unittest.TestCase):
    def test_real_remote_font_loading_in_both_documents(self):
        for css in (STYLE, CALENDAR_CSS):
            self.assertIn("fonts.googleapis.com/css2?", css)
            self.assertIn("Noto+Sans+SC", css)
            self.assertIn("Noto+Sans+Math", css)
            self.assertIn("Noto+Sans+Symbols+2", css)
            self.assertIn("Noto+Emoji", css)
            self.assertNotIn("UNICODE_FONT_", css)
            # CSS @import must precede other style rules.
            self.assertTrue(css.lstrip().startswith("<style>") or
                            css.lstrip().startswith("@import url("))
        self.assertIn(FONT_IMPORT.strip(), STYLE)
        self.assertIn(FONT_IMPORT.strip(), CALENDAR_CSS)

    def test_main_input_and_calendar_event_styles_cover_fonts(self):
        self.assertIn("font-family:" + FONT_STACK + "!important;", STYLE)
        self.assertIn("font-family:" + FONT_STACK + "!important", CALENDAR_CSS)
        self.assertIn(".fc .fc-event-title", CALENDAR_CSS)
        self.assertNotIn(".fc .fc-icon {\n font-family:", CALENDAR_CSS)

    def test_probe_survives_independent_of_database(self):
        app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        self.assertIn('st.expander("Character and symbol display test")', app)
        self.assertIn('for label, sample in UNICODE_SAMPLES:', app)
        self.assertIn('st.markdown(', app)
        self.assertIn('**Character display check:** 中文 漢字', app)
        self.assertLess(app.index("def main():\n    install_theme()"),
                        app.index("init_chat()", app.index("def main():")))
        self.assertGreaterEqual(len(UNICODE_SAMPLES), 5)
        for _, text in UNICODE_SAMPLES:
            self.assertNotIn("\\u", text)
            self.assertTrue(text)

if __name__ == "__main__":
    unittest.main()
