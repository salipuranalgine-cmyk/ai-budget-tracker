"""
user_manager.py
Handles multi-user profiles. Each user gets their own SQLite budget database.
A shared users.db stores the profile list and lightweight app state.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

USERS_DB = "users.db"
DEFAULT_EMOJI = "🧑"
LAST_ACTIVE_USER_KEY = "last_active_user_id"


@dataclass
class UserProfile:
    id: int
    name: str
    emoji: str
    created_at: str


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_users_db() -> None:
    conn = _connect()
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            emoji       TEXT    NOT NULL DEFAULT '{DEFAULT_EMOJI}',
            created_at  TEXT    DEFAULT (date('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_state (
            key     TEXT PRIMARY KEY,
            value   TEXT NOT NULL
        )
        """
    )
    try:
        conn.execute(
            f"ALTER TABLE users ADD COLUMN emoji TEXT NOT NULL DEFAULT '{DEFAULT_EMOJI}'"
        )
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def _row_to_profile(row: sqlite3.Row | None) -> UserProfile | None:
    if row is None:
        return None
    return UserProfile(
        id=row["id"],
        name=row["name"],
        emoji=row["emoji"] or DEFAULT_EMOJI,
        created_at=row["created_at"],
    )


def get_users() -> list[UserProfile]:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, name, emoji, created_at FROM users ORDER BY name ASC"
    ).fetchall()
    conn.close()
    return [profile for row in rows if (profile := _row_to_profile(row)) is not None]


def get_user_by_id(user_id: int) -> UserProfile | None:
    conn = _connect()
    row = conn.execute(
        "SELECT id, name, emoji, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return _row_to_profile(row)


def add_user(name: str, emoji: str = DEFAULT_EMOJI) -> UserProfile:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, emoji) VALUES (?, ?)",
        (name.strip(), emoji or DEFAULT_EMOJI),
    )
    conn.commit()
    uid = cur.lastrowid
    row = conn.execute(
        "SELECT id, name, emoji, created_at FROM users WHERE id = ?",
        (uid,),
    ).fetchone()
    conn.close()
    profile = _row_to_profile(row)
    if profile is None:
        raise RuntimeError("Failed to create user profile.")
    return profile


def _get_app_state(key: str) -> str | None:
    conn = _connect()
    row = conn.execute(
        "SELECT value FROM app_state WHERE key = ?",
        (key,),
    ).fetchone()
    conn.close()
    return row["value"] if row else None


def _set_app_state(key: str, value: str | None) -> None:
    conn = _connect()
    if value is None:
        conn.execute("DELETE FROM app_state WHERE key = ?", (key,))
    else:
        conn.execute(
            """
            INSERT INTO app_state(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
    conn.commit()
    conn.close()


def get_last_active_user_id() -> int | None:
    value = _get_app_state(LAST_ACTIVE_USER_KEY)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def set_last_active_user(user_id: int | None) -> None:
    _set_app_state(LAST_ACTIVE_USER_KEY, None if user_id is None else str(user_id))


def get_last_active_user() -> UserProfile | None:
    user_id = get_last_active_user_id()
    if user_id is None:
        return None
    user = get_user_by_id(user_id)
    if user is None:
        set_last_active_user(None)
    return user


def delete_user(user_id: int) -> None:
    """Delete a user profile and their budget database file."""
    if get_last_active_user_id() == user_id:
        set_last_active_user(None)

    conn = _connect()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    db_path = get_db_path(user_id)
    Path(db_path).unlink(missing_ok=True)


def get_db_path(user_id: int) -> str:
    return f"budget_user_{user_id}.db"


def user_name_exists(name: str) -> bool:
    conn = _connect()
    row = conn.execute(
        "SELECT 1 FROM users WHERE name = ? COLLATE NOCASE",
        (name.strip(),),
    ).fetchone()
    conn.close()
    return row is not None
