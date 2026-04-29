from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from .db_chat import (
    create_chat_session,
    delete_all_chat_sessions,
    delete_chat_session,
    get_chat_messages,
    get_chat_sessions,
    get_chat_storage_kb,
    init_chat_tables,
    save_chat_message,
    truncate_chat_messages_after_index,
    update_chat_session_title,
)
from .db_notifications import (
    add_notification,
    clear_all_notifications,
    delete_notification,
    delete_notifications,
    delete_notifications_by_type,
    get_notifications,
    get_unread_notifications_count,
    init_notifications_table,
    is_first_run,
    mark_all_notifications_read,
    mark_first_run_seen,
    mark_notification_read,
)
from .db_recurring import (
    add_recurring_transaction,
    apply_due_recurring,
    delete_recurring,
    get_recurring_transactions,
    get_upcoming_recurring,
    toggle_recurring,
    update_recurring_transaction,
)
from .db_transactions import (
    add_transaction,
    delete_budget_limit,
    delete_transaction,
    export_transactions_csv,
    get_ai_provider_mode,
    get_anthropic_api_key,
    get_app_meta,
    get_balance,
    get_budget_limits,
    get_currency,
    get_expense_summary_range,
    get_expenses_last_days,
    get_month_expense_summary,
    get_month_income_total,
    get_starting_balance,
    get_transactions,
    set_ai_provider_mode,
    set_anthropic_api_key,
    set_app_meta,
    set_budget_limit,
    set_currency,
    set_starting_balance,
    update_budget_limit,
    update_transaction,
)

DB_FILE = "budget.db"
_POSTGRES_PREFIXES = ("postgres://", "postgresql://")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def get_backend() -> str:
    dsn = os.getenv("DATABASE_URL", "").strip()
    return "postgres" if dsn.startswith(_POSTGRES_PREFIXES) else "sqlite"


def using_postgres() -> bool:
    return get_backend() == "postgres"


def set_user_db(path: str) -> None:
    global DB_FILE
    DB_FILE = path


def user_schema_name(user_id: int) -> str:
    return f"budget_user_{int(user_id)}"


def get_active_scope_name() -> str:
    raw = DB_FILE
    if raw.endswith(".db") or "\\" in raw or "/" in raw:
        raw = Path(raw).stem
    raw = re.sub(r"[^A-Za-z0-9_]", "_", raw.strip().lower())
    if not raw:
        raw = "budget"
    if raw[0].isdigit():
        raw = f"user_{raw}"
    return raw


def get_storage_key() -> str:
    if using_postgres():
        return f"postgres:{get_active_scope_name()}"
    return str(Path(DB_FILE).resolve())


def _require_psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL mode requires `psycopg`. Install it with `pip install psycopg[binary]`."
        ) from exc
    return psycopg, dict_row


def _quote_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return f'"{name}"'


def _translate_placeholders(query: str) -> str:
    result: list[str] = []
    in_single = False
    in_double = False
    for char in query:
        if char == "'" and not in_double:
            in_single = not in_single
            result.append(char)
        elif char == '"' and not in_single:
            in_double = not in_double
            result.append(char)
        elif char == "?" and not in_single and not in_double:
            result.append("%s")
        else:
            result.append(char)
    return "".join(result)


class CursorWrapper:
    def __init__(self, cursor: Any, backend: str):
        self._cursor = cursor
        self._backend = backend

    def execute(self, query: str, params: Any = None):
        sql = _translate_placeholders(query) if self._backend == "postgres" else query
        if params is None:
            self._cursor.execute(sql)
        else:
            self._cursor.execute(sql, params)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)


class ConnectionWrapper:
    def __init__(self, conn: Any, backend: str):
        self._conn = conn
        self._backend = backend

    def cursor(self) -> CursorWrapper:
        return CursorWrapper(self._conn.cursor(), self._backend)

    def execute(self, query: str, params: Any = None) -> CursorWrapper:
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()


def _sqlite_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _postgres_connect(scope: str | None = None) -> ConnectionWrapper:
    psycopg, dict_row = _require_psycopg()
    conn = psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)
    wrapper = ConnectionWrapper(conn, "postgres")
    schema = scope or get_active_scope_name()
    wrapper.execute(f"SET search_path TO {_quote_identifier(schema)}, public")
    return wrapper


def _connect():
    if using_postgres():
        return _postgres_connect()
    return _sqlite_connect()


def _connect_public():
    if using_postgres():
        return _postgres_connect("public")
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def insert_and_get_id(query: str, params: tuple[Any, ...] | list[Any]) -> int:
    conn = _connect()
    try:
        cur = conn.cursor()
        if using_postgres():
            sql = query.strip().rstrip(";")
            if " returning " not in f" {sql.lower()} ":
                sql = f"{sql} RETURNING id"
            cur.execute(sql, params)
            row = cur.fetchone()
            conn.commit()
            return int(row["id"])
        cur.execute(query, params)
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def create_user_scope(scope_name: str) -> None:
    if using_postgres():
        public = _connect_public()
        public.execute(f"CREATE SCHEMA IF NOT EXISTS {_quote_identifier(scope_name)}")
        public.commit()
        public.close()
        return

    Path(scope_name).parent.mkdir(parents=True, exist_ok=True)


def drop_user_scope(scope_name: str) -> None:
    if using_postgres():
        public = _connect_public()
        public.execute(f"DROP SCHEMA IF EXISTS {_quote_identifier(scope_name)} CASCADE")
        public.commit()
        public.close()


def _reset_sqlite_sequences(conn: sqlite3.Connection) -> None:
    return None


def reset_identity_sequences(scope: str | None = None) -> None:
    if not using_postgres():
        return

    schema = scope or get_active_scope_name()
    conn = _postgres_connect(schema)
    try:
        for table in [
            "transactions",
            "budget_limits",
            "recurring_transactions",
            "notifications",
            "chat_sessions",
            "chat_messages",
        ]:
            conn.execute(
                f"""
                SELECT setval(
                    pg_get_serial_sequence('{table}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {table}), 1),
                    true
                )
                """
            )
        conn.commit()
    finally:
        conn.close()


def reset_public_identity_sequences() -> None:
    if not using_postgres():
        return

    conn = _connect_public()
    try:
        conn.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('users', 'id'),
                COALESCE((SELECT MAX(id) FROM users), 1),
                true
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    if using_postgres():
        scope = get_active_scope_name()
        create_user_scope(scope)
        conn = _connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id BIGSERIAL PRIMARY KEY,
                txn_type TEXT NOT NULL CHECK(txn_type IN ('income','expense')),
                amount DOUBLE PRECISION NOT NULL,
                category TEXT NOT NULL,
                description TEXT DEFAULT '',
                txn_date TEXT NOT NULL,
                logged_date TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS budget_limits (
                id BIGSERIAL PRIMARY KEY,
                category TEXT NOT NULL UNIQUE,
                monthly_limit DOUBLE PRECISION NOT NULL,
                duration_type TEXT DEFAULT 'month',
                duration_days INTEGER DEFAULT 30,
                start_date TEXT,
                end_date TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recurring_transactions (
                id BIGSERIAL PRIMARY KEY,
                txn_type TEXT NOT NULL CHECK(txn_type IN ('income','expense')),
                amount DOUBLE PRECISION NOT NULL,
                category TEXT NOT NULL,
                description TEXT DEFAULT '',
                frequency TEXT NOT NULL,
                frequency_days INTEGER DEFAULT 0,
                start_date TEXT NOT NULL,
                next_date TEXT NOT NULL,
                active BOOLEAN DEFAULT TRUE
            )
            """
        )
        conn.commit()
        conn.close()
        return

    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_type TEXT NOT NULL CHECK(txn_type IN ('income','expense')),
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT DEFAULT '',
            txn_date TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS budget_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL UNIQUE,
            monthly_limit REAL NOT NULL,
            duration_type TEXT DEFAULT 'month',
            duration_days INTEGER DEFAULT 30,
            start_date TEXT,
            end_date TEXT
        )
        """
    )
    for col_sql in [
        "ALTER TABLE budget_limits ADD COLUMN duration_type TEXT DEFAULT 'month'",
        "ALTER TABLE budget_limits ADD COLUMN duration_days INTEGER DEFAULT 30",
        "ALTER TABLE budget_limits ADD COLUMN start_date TEXT",
        "ALTER TABLE budget_limits ADD COLUMN end_date TEXT",
    ]:
        try:
            cur.execute(col_sql)
        except sqlite3.OperationalError:
            pass

    try:
        cur.execute("ALTER TABLE transactions ADD COLUMN logged_date TEXT")
    except sqlite3.OperationalError:
        pass

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS recurring_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_type TEXT NOT NULL CHECK(txn_type IN ('income','expense')),
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT DEFAULT '',
            frequency TEXT NOT NULL,
            frequency_days INTEGER DEFAULT 0,
            start_date TEXT NOT NULL,
            next_date TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )
        """
    )
    rec_cols = {row["name"] for row in cur.execute("PRAGMA table_info(recurring_transactions)").fetchall()}
    if "frequency" not in rec_cols:
        cur.execute("ALTER TABLE recurring_transactions ADD COLUMN frequency TEXT NOT NULL DEFAULT 'monthly'")
    if "frequency_days" not in rec_cols:
        cur.execute("ALTER TABLE recurring_transactions ADD COLUMN frequency_days INTEGER DEFAULT 0")
    if "start_date" not in rec_cols:
        cur.execute(
            "ALTER TABLE recurring_transactions ADD COLUMN start_date TEXT NOT NULL DEFAULT ''"
        )
    if "next_date" not in rec_cols:
        cur.execute(
            "ALTER TABLE recurring_transactions ADD COLUMN next_date TEXT NOT NULL DEFAULT ''"
        )
    if "active" not in rec_cols:
        cur.execute("ALTER TABLE recurring_transactions ADD COLUMN active INTEGER DEFAULT 1")

    if "next_date" not in rec_cols and "next_run_date" in rec_cols:
        cur.execute(
            """
            UPDATE recurring_transactions
            SET next_date = COALESCE(NULLIF(next_run_date, ''), NULLIF(start_date, ''), date('now'))
            """
        )
    elif "next_date" not in rec_cols and "next_due_date" in rec_cols:
        cur.execute(
            """
            UPDATE recurring_transactions
            SET next_date = COALESCE(NULLIF(next_due_date, ''), NULLIF(start_date, ''), date('now'))
            """
        )
    elif "next_date" not in rec_cols:
        cur.execute(
            """
            UPDATE recurring_transactions
            SET next_date = COALESCE(NULLIF(start_date, ''), date('now'))
            """
        )
    conn.commit()
    conn.close()
