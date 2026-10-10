"""Portable Windows launchers and platform path sanity tests.

Windows CI also runs the full app test suite with Windows-style paths.
"""
from pathlib import Path
import ast
import re
import unittest

ROOT = Path(__file__).resolve().parent


class WindowsSupportTests(unittest.TestCase):
    def test_launchers_exist_and_use_venv_python(self):
        setup = (ROOT / "setup_windows.cmd").read_text(encoding="utf-8")
        start = (ROOT / "start_windows.cmd").read_text(encoding="utf-8")
        self.assertIn("py -3.12", setup)
        self.assertIn("py -3.11", setup)
        self.assertIn("-m venv", setup)
        self.assertIn(r".venv-win\Scripts\python.exe", setup)
        self.assertIn(r".venv-win\Scripts\python.exe", start)
        self.assertIn("-m streamlit run app.py", start)
        self.assertIn("127.0.0.1", start)
        self.assertIn("call", start.lower())

    def test_paths_are_relative_to_project_not_macos_home(self):
        for name in ("setup_windows.cmd", "start_windows.cmd"):
            data = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn(r'cd /d "%~dp0"', data)
            self.assertNotIn("/Users/", data)
            self.assertNotIn("sudo ", data)

    def test_imports_are_not_anchored_to_mac_user_paths(self):
        for path in ROOT.glob("*.py"):
            if path.name == "test_windows_support.py":
                continue  # This test necessarily contains its own regex literal.
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
            strings = [
                n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
            ]
            hardcoded_home = [
                v for v in strings
                if re.search(r"/Users/[^/\s]+/", v) and len(v) < 1000
            ]
            self.assertEqual(hardcoded_home, [], path.name)


if __name__ == "__main__":
    unittest.main()
