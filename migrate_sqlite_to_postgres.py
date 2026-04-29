from __future__ import annotations

import sqlite3
from pathlib import Path

from backend import database as db
import user_manager as um

SQLITE_USERS_DB = Path("users.db")
SQLITE_USER_DIR = Path("user_data")


def _sqlite_connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _copy_table(sqlite_conn: sqlite3.Connection, pg_conn, table: str, columns: list[str]) -> None:
    try:
        rows = sqlite_conn.execute(
            f"SELECT {', '.join(columns)} FROM {table}"
        ).fetchall()
    except sqlite3.OperationalError:
        return
    if not rows:
        return

    placeholders = ", ".join("?" for _ in columns)
    pg_conn.execute(f"DELETE FROM {table}")
    for row in rows:
        values = []
        for col in columns:
            value = row[col]
            if table in {"notifications", "recurring_transactions"} and col in {"is_read", "active"}:
                value = bool(value)
            values.append(value)
        pg_conn.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(values),
        )


def migrate() -> None:
    if not db.using_postgres():
        raise RuntimeError("Set DATABASE_URL to your PostgreSQL DSN before running this migration.")

    if not SQLITE_USERS_DB.exists():
        raise FileNotFoundError("users.db not found. Nothing to migrate.")

    print("Migrating shared users/app_state...")
    sqlite_users = _sqlite_connect(SQLITE_USERS_DB)
    um.init_users_db()
    public_conn = db._connect_public()

    public_conn.execute("DELETE FROM app_state")
    public_conn.execute("DELETE FROM users")
    public_conn.commit()

    for row in sqlite_users.execute("SELECT id, name, emoji, created_at FROM users ORDER BY id ASC"):
        public_conn.execute(
            """
            INSERT INTO users (id, name, emoji, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (row["id"], row["name"], row["emoji"], row["created_at"]),
        )
    for row in sqlite_users.execute("SELECT key, value FROM app_state"):
        public_conn.execute(
            "INSERT INTO app_state (key, value) VALUES (?, ?)",
            (row["key"], row["value"]),
        )
    public_conn.commit()
    public_conn.close()
    sqlite_users.close()
    db.reset_public_identity_sequences()

    for user in um.get_users():
        sqlite_path = SQLITE_USER_DIR / f"budget_user_{user.id}.db"
        if not sqlite_path.exists():
            print(f"Skipping user {user.id} ({user.name}): {sqlite_path} missing")
            continue

        print(f"Migrating user {user.id} ({user.name})...")
        sqlite_user = _sqlite_connect(sqlite_path)
        db.set_user_db(um.get_db_path(user.id))
        db.init_db()
        db.init_notifications_table()
        db.init_chat_tables()
        pg_conn = db._connect()

        _copy_table(
            sqlite_user,
            pg_conn,
            "transactions",
            ["id", "txn_type", "amount", "category", "description", "txn_date", "logged_date"],
        )
        _copy_table(
            sqlite_user,
            pg_conn,
            "budget_limits",
            ["id", "category", "monthly_limit", "duration_type", "duration_days", "start_date", "end_date"],
        )
        _copy_table(
            sqlite_user,
            pg_conn,
            "app_meta",
            ["key", "value"],
        )
        _copy_table(
            sqlite_user,
            pg_conn,
            "recurring_transactions",
            ["id", "txn_type", "amount", "category", "description", "frequency", "frequency_days", "start_date", "next_date", "active"],
        )
        _copy_table(
            sqlite_user,
            pg_conn,
            "notifications",
            ["id", "notif_type", "title", "message", "is_read", "created_at"],
        )
        _copy_table(
            sqlite_user,
            pg_conn,
            "chat_sessions",
            ["id", "title", "created_at"],
        )
        _copy_table(
            sqlite_user,
            pg_conn,
            "chat_messages",
            ["id", "session_id", "role", "content", "created_at"],
        )

        pg_conn.commit()
        pg_conn.close()
        sqlite_user.close()
        db.reset_identity_sequences()

    print("Migration complete.")


if __name__ == "__main__":
    migrate()
