"""Navigation regression tests that do not require installing Streamlit.

Execute with: python -m unittest discover -s tests
"""
import ast
import unittest
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "planner_ui.py"


def _load_calendar_helpers():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    required = {"_move_calendar_date", "_calendar_period_heading"}
    nodes = [node for node in tree.body
             if isinstance(node, ast.FunctionDef) and node.name in required]
    if len(nodes) != len(required):
        raise AssertionError("Navigation helpers missing")
    env = {"date": date, "timedelta": timedelta, "monthrange": monthrange}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), env)
    return env


class CalendarNavigationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = _load_calendar_helpers()

    def test_week_navigation(self):
        move = self.helpers["_move_calendar_date"]
        anchor = date(2026, 10, 10)
        self.assertEqual(move(anchor, "Week", 1), date(2026, 10, 17))
        self.assertEqual(move(anchor, "Week", -1), date(2026, 10, 3))
        self.assertEqual(move(anchor, "Agenda", 1), date(2026, 10, 17))

    def test_day_navigation(self):
        move = self.helpers["_move_calendar_date"]
        self.assertEqual(move(date(2026, 10, 10), "Day", 1),
                         date(2026, 10, 11))

    def test_month_navigation_at_year_boundary(self):
        move = self.helpers["_move_calendar_date"]
        self.assertEqual(move(date(2026, 12, 31), "Month", 1),
                         date(2027, 1, 31))
        self.assertEqual(move(date(2027, 1, 31), "Month", 1),
                         date(2027, 2, 28))
        self.assertEqual(move(date(2028, 3, 31), "Month", -1),
                         date(2028, 2, 29))

    def test_period_titles(self):
        title = self.helpers["_calendar_period_heading"]
        self.assertEqual(title(date(2026, 10, 10), "Month"), "October 2026")
        self.assertEqual(title(date(2026, 10, 10), "Week"), "Oct 05 – 11, 2026")


if __name__ == "__main__":
    unittest.main()
