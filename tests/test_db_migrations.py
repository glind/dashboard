"""Older dashboard databases (the family instances on hoth) predate some columns."""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from database import USER_PROFILE_EXTRA_COLUMNS, DatabaseManager  # noqa: E402


def test_old_user_profile_table_gets_new_columns(tmp_path):
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE user_profile (
        id INTEGER PRIMARY KEY CHECK (id = 1), full_name TEXT, preferred_name TEXT, occupation TEXT,
        company TEXT, role TEXT, work_focus TEXT, interests TEXT, communication_style TEXT,
        timezone TEXT, work_hours TEXT, priorities TEXT, bio TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("INSERT INTO user_profile (id, preferred_name) VALUES (1, 'Sam')")
    conn.commit()
    conn.close()

    db = DatabaseManager(str(db_path))  # migrates at init
    cols = {r[1] for r in sqlite3.connect(db_path).execute("PRAGMA table_info(user_profile)")}
    assert {c for c, _ in USER_PROFILE_EXTRA_COLUMNS} <= cols
    profile = db.get_user_profile()  # was "no such column: github_username" -> {}
    assert profile["preferred_name"] == "Sam" and profile["github_username"] == ""
    assert db.save_user_profile({"github_username": "octo"})
    assert db.get_user_profile()["github_username"] == "octo"
    DatabaseManager(str(db_path))  # idempotent
