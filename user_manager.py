"""
user_manager.py
Handles multi-user profiles for either local SQLite storage or a shared PostgreSQL backend.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import database as db

USERS_DB = "users.db"
USER_DATA_DIR = Path("user_data")
DEFAULT_EMOJI = "🙂"
LAST_ACTIVE_USER_KEY = "last_active_user_id"


@dataclass
class UserProfile:
    id: int
    name: str
    emoji: str
    avatar_image: str | None
    created_at: str


def _connect():
    if db.using_postgres():
        return db._connect_public()

    conn = sqlite3.connect(USERS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_users_db() -> None:
    USER_DATA_DIR.mkdir(exist_ok=True)
    conn = _connect()
    if db.using_postgres():
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                emoji TEXT NOT NULL DEFAULT '🙂',
                avatar_image TEXT,
                created_at TEXT DEFAULT to_char(CURRENT_DATE, 'YYYY-MM-DD')
            )
            """
        )
        conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_image TEXT")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS users_name_lower_idx
            ON users ((LOWER(name)))
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()
        return

    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
            emoji        TEXT    NOT NULL DEFAULT '{DEFAULT_EMOJI}',
            avatar_image TEXT,
            created_at   TEXT    DEFAULT (date('now'))
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
    try:
        conn.execute("ALTER TABLE users ADD COLUMN avatar_image TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def _row_to_profile(row) -> UserProfile | None:
    if row is None:
        return None
    return UserProfile(
        id=row["id"],
        name=row["name"],
        emoji=row["emoji"] or DEFAULT_EMOJI,
        avatar_image=row["avatar_image"],
        created_at=row["created_at"],
    )


def get_users() -> list[UserProfile]:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, name, emoji, avatar_image, created_at FROM users ORDER BY name ASC"
    ).fetchall()
    conn.close()
    return [profile for row in rows if (profile := _row_to_profile(row)) is not None]


def get_user_by_id(user_id: int) -> UserProfile | None:
    conn = _connect()
    row = conn.execute(
        "SELECT id, name, emoji, avatar_image, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return _row_to_profile(row)


def add_user(name: str, emoji: str = DEFAULT_EMOJI, avatar_image: str | None = None) -> UserProfile:
    clean_name = name.strip()
    conn = _connect()
    if db.using_postgres():
        row = conn.execute(
            """
            INSERT INTO users (name, emoji, avatar_image)
            VALUES (?, ?, ?)
            RETURNING id, name, emoji, avatar_image, created_at
            """,
            (clean_name, emoji or DEFAULT_EMOJI, avatar_image),
        ).fetchone()
        conn.commit()
        conn.close()
        profile = _row_to_profile(row)
        if profile is None:
            raise RuntimeError("Failed to create user profile.")
        return profile

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, emoji, avatar_image) VALUES (?, ?, ?)",
        (clean_name, emoji or DEFAULT_EMOJI, avatar_image),
    )
    conn.commit()
    uid = cur.lastrowid
    row = conn.execute(
        "SELECT id, name, emoji, avatar_image, created_at FROM users WHERE id = ?",
        (uid,),
    ).fetchone()
    conn.close()
    profile = _row_to_profile(row)
    if profile is None:
        raise RuntimeError("Failed to create user profile.")
    return profile


def update_user(
    user_id: int,
    *,
    name: str,
    emoji: str = DEFAULT_EMOJI,
    avatar_image: str | None = None,
) -> UserProfile:
    clean_name = name.strip()
    conn = _connect()
    conn.execute(
        "UPDATE users SET name = ?, emoji = ?, avatar_image = ? WHERE id = ?",
        (clean_name, emoji or DEFAULT_EMOJI, avatar_image, user_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, name, emoji, avatar_image, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    profile = _row_to_profile(row)
    if profile is None:
        raise RuntimeError("Failed to update user profile.")
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
    if get_last_active_user_id() == user_id:
        set_last_active_user(None)

    conn = _connect()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    db_path = get_db_path(user_id)
    if db.using_postgres():
        db.drop_user_scope(db_path)
    else:
        Path(db_path).unlink(missing_ok=True)


def get_db_path(user_id: int) -> str:
    if db.using_postgres():
        return db.user_schema_name(user_id)
    return str(USER_DATA_DIR / f"budget_user_{user_id}.db")


def user_name_exists(name: str, *, exclude_user_id: int | None = None) -> bool:
    conn = _connect()
    clean_name = name.strip()
    if db.using_postgres():
        if exclude_user_id is None:
            row = conn.execute(
                "SELECT 1 FROM users WHERE LOWER(name) = LOWER(?)",
                (clean_name,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM users WHERE LOWER(name) = LOWER(?) AND id <> ?",
                (clean_name, exclude_user_id),
            ).fetchone()
    else:
        if exclude_user_id is None:
            row = conn.execute(
                "SELECT 1 FROM users WHERE name = ? COLLATE NOCASE",
                (clean_name,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM users WHERE name = ? COLLATE NOCASE AND id <> ?",
                (clean_name, exclude_user_id),
            ).fetchone()
    conn.close()
    return row is not None
