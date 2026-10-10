"""AARON-1 Unicode and persistence regression tests.

Runs without live Turso credentials. A SQLite-backed DB-API fake exercises the
remote connection factory, row mapping and transactional context manager.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import assistant_core
from assistant_core import _MappingRow, connect
from data_backup import export_personal_data, restore_personal_data

SAMPLES = [
    "中文课：城市交通 / 你好世界",
    "日本語・한글・العَرَبِيَّة",
    "á café naïve — “quotes” • © ™",
    "数学: ∑ ∫ √∞ ≤ ≥ ≠ → ↔ ± π λ",
    "Emoji: 😀 📅 🧠 🎹 ✨ 👩🏽‍💻 🏳️‍🌈",
    "𠀀𪛖 (CJK extension B)",
]


class UnicodePersistenceTest(unittest.TestCase):
    def test_local_sqlite_preserves_unicode(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(assistant_core, "DB", Path(tmp) / "local.db"):
                with patch.object(assistant_core, "_configuration_value", return_value=""):
                    with connect() as db:
                        for idx, title in enumerate(SAMPLES):
                            db.execute(
                                "INSERT INTO tasks (id,title,source,created_at) "
                                "VALUES (?,?,?,?)",
                                (str(idx), title, "manual", "2026-10-10"),
                            )
                        db.commit()
                    with connect() as db:
                        results = [row["title"] for row in db.execute(
                            "SELECT title FROM tasks ORDER BY id"
                        ).fetchall()]
                    self.assertEqual(results, SAMPLES)

    def test_backup_restores_symbols_after_simulated_reboot(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            with patch.object(assistant_core, "_configuration_value", return_value=""):
                with patch.object(assistant_core, "DB", temp / "before.db"):
                    with connect() as db:
                        db.execute(
                            "INSERT INTO tasks (id,title,source,created_at) "
                            "VALUES (?,?,?,?)",
                            ("a", SAMPLES[4], "manual", "2026-10-10"),
                        )
                        db.commit()
                    backup = export_personal_data()
                self.assertIn("🧠".encode("utf-8"), backup)
                self.assertEqual(json.loads(backup)["format"],
                                 "AARON-1-personal-data-v1")
                with patch.object(assistant_core, "DB", temp / "after.db"):
                    restored = restore_personal_data(backup)
                    self.assertGreater(restored, 0)
                    with connect() as db:
                        row = db.execute(
                            "SELECT title FROM tasks WHERE id=?", ("a",)
                        ).fetchone()
                        self.assertEqual(row["title"], SAMPLES[4])
                    # Merge-only recovery: replaying backup never duplicates.
                    self.assertEqual(restore_personal_data(backup), 0)

    def test_remote_backend_persists_on_new_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            location = str(Path(tmp) / "remote.db")
            fake_driver = types.SimpleNamespace(
                connect=lambda url, auth_token: sqlite3.connect(location)
            )
            def fake_secret(key):
                return {
                    "TURSO_DATABASE_URL": "https://db.example.test",
                    "TURSO_AUTH_TOKEN": "test-secret",
                }.get(key, "")
            with patch.dict(sys.modules, {"turso_serverless": fake_driver}):
                with patch.object(assistant_core, "_configuration_value", side_effect=fake_secret):
                    with connect() as db:
                        db.execute(
                            "INSERT INTO tasks (id,title,source,created_at) "
                            "VALUES (?,?,?,?)",
                            ("u1", SAMPLES[0], "manual", "2026-10-10"),
                        )
                        db.commit()
                    with connect() as db:
                        row = db.execute(
                            "SELECT * FROM tasks WHERE id=?", ("u1",)
                        ).fetchone()
                        self.assertEqual(row["title"], SAMPLES[0])
                        self.assertEqual(row[1], SAMPLES[0])
                        self.assertEqual(dict(row)["title"], SAMPLES[0])

    def test_libsql_database_url_uses_matching_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            location = str(Path(tmp) / "legacy_libsql.db")
            calls = []
            def fake_connect(database, auth_token):
                calls.append((database, auth_token))
                return sqlite3.connect(location)
            fake_driver = types.SimpleNamespace(connect=fake_connect)
            values = {
                "TURSO_DATABASE_URL": "libsql://sample.turso.io",
                "TURSO_AUTH_TOKEN": "private-test-token",
            }
            with patch.dict(sys.modules, {"libsql": fake_driver}):
                with patch.object(assistant_core, "_configuration_value",
                                  side_effect=lambda name: values.get(name, "")):
                    with connect() as db:
                        db.execute(
                            "INSERT INTO tasks (id,title,source,created_at) "
                            "VALUES (?,?,?,?)",
                            ("legacy", SAMPLES[3], "manual", "2026-10-10"),
                        )
                        db.commit()
                    with connect() as db:
                        saved = db.execute(
                            "SELECT * FROM tasks WHERE id=?", ("legacy",)
                        ).fetchone()
                        self.assertEqual(saved["title"], SAMPLES[3])
                    self.assertEqual(calls[0], (
                        "libsql://sample.turso.io", "private-test-token"
                    ))

    def test_engine_override_selects_turso_on_libsql_scheme(self):
        with tempfile.TemporaryDirectory() as tmp:
            location = str(Path(tmp) / "new_engine.db")
            calls = []
            def fake_connect(url, auth_token):
                calls.append(url)
                return sqlite3.connect(location)
            fake_driver = types.SimpleNamespace(connect=fake_connect)
            values = {
                "TURSO_DATABASE_URL": "libsql://sample.turso.io",
                "TURSO_AUTH_TOKEN": "private-test-token",
                "TURSO_DATABASE_ENGINE": "turso",
            }
            with patch.dict(sys.modules, {"turso_serverless": fake_driver}):
                with patch.object(assistant_core, "_configuration_value",
                                  side_effect=lambda name: values.get(name, "")):
                    with connect() as db:
                        self.assertIsNotNone(db.execute("SELECT 1").fetchone())
            self.assertEqual(calls, ["libsql://sample.turso.io"])

    def test_recovery_does_not_echo_database_secret(self):
        app_source = (
            Path(__file__).resolve().parents[1] / "app.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _database_startup_help(exc)", app_source)
        self.assertIn("st.stop()", app_source)
        self.assertNotIn("st.error(str(exc))", app_source)

    def test_half_configured_remote_fails_closed(self):
        def secret(key):
            return {"TURSO_DATABASE_URL": "https://db.example.test"}.get(key, "")
        with patch.object(assistant_core, "_configuration_value", side_effect=secret):
            with self.assertRaisesRegex(RuntimeError, "BOTH"):
                connect()

    def test_no_password_gate_and_turso_credentials_preserved(self):
        root = Path(__file__).resolve().parents[1]
        app = (root / "app.py").read_text(encoding="utf-8")
        readme = (root / "README.md").read_text(encoding="utf-8")
        core = (root / "assistant_core.py").read_text(encoding="utf-8")
        self.assertNotIn("APP_PASSWORD", app)
        self.assertNotIn("_require_password_if_configured", app)
        self.assertNotIn("aaron_password_gate", app)
        self.assertNotIn("APP_PASSWORD", readme)
        self.assertIn("TURSO_DATABASE_URL", core)
        self.assertIn("TURSO_AUTH_TOKEN", core)
        self.assertIn("private app visibility", readme)

    def test_unicode_fonts_and_safe_explicit_composer_present(self):
        root = Path(__file__).resolve().parents[1]
        theme = (root / "ui_theme.py").read_text(encoding="utf-8")
        calendar = (root / "planner_ui.py").read_text(encoding="utf-8")
        app = (root / "app.py").read_text(encoding="utf-8")
        for font in ("Noto Sans Symbols 2", "Noto Color Emoji",
                     "PingFang SC", "Microsoft YaHei"):
            self.assertIn(font, theme)
        self.assertIn("Noto Color Emoji", calendar)
        self.assertIn('st.form_submit_button("Send"', app)


if __name__ == "__main__":
    unittest.main()
