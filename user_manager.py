"""
user_manager.py
Handles multi-user profiles. Each user gets their own SQLite budget database.
A shared 'users.db' stores the user list only.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

USERS_DB = "users.db"


@dataclass
class UserProfile:
    id: int
    name: str
    emoji: str          # chosen avatar emoji
    created_at: str


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_users_db() -> None:
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            emoji       TEXT    NOT NULL DEFAULT '🧑',
            created_at  TEXT    DEFAULT (date('now'))
        )
        """
    )
    # Safe migration: add emoji column if older db lacks it
    try:
        conn.execute("ALTER TABLE users ADD COLUMN emoji TEXT NOT NULL DEFAULT '🧑'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def get_users() -> list[UserProfile]:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, name, emoji, created_at FROM users ORDER BY name ASC"
    ).fetchall()
    conn.close()
    return [
        UserProfile(
            id=row["id"],
            name=row["name"],
            emoji=row["emoji"] or "🧑",
            created_at=row["created_at"],
        )
        for row in rows
    ]


def add_user(name: str, emoji: str = "🧑") -> UserProfile:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, emoji) VALUES (?, ?)",
        (name.strip(), emoji),
    )
    conn.commit()
    uid = cur.lastrowid
    row = conn.execute(
        "SELECT id, name, emoji, created_at FROM users WHERE id = ?", (uid,)
    ).fetchone()
    conn.close()
    return UserProfile(
        id=row["id"],
        name=row["name"],
        emoji=row["emoji"],
        created_at=row["created_at"],
    )


def delete_user(user_id: int) -> None:
    """Delete user profile and their budget data file."""
    conn = _connect()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    db_path = get_db_path(user_id)
    Path(db_path).unlink(missing_ok=True)


def get_db_path(user_id: int) -> str:
    """Returns the SQLite file path for a specific user's budget data."""
    return f"budget_user_{user_id}.db"


def user_name_exists(name: str) -> bool:
    conn = _connect()
    row = conn.execute(
        "SELECT 1 FROM users WHERE name = ? COLLATE NOCASE", (name.strip(),)
    ).fetchone()
    conn.close()
    return row is not None