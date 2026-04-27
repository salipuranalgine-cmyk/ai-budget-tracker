from __future__ import annotations

import sqlite3

from db_chat import (
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
from db_notifications import (
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
from db_recurring import (
    add_recurring_transaction,
    apply_due_recurring,
    delete_recurring,
    get_recurring_transactions,
    get_upcoming_recurring,
    toggle_recurring,
    update_recurring_transaction,
)
from db_transactions import (
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


def set_user_db(path: str) -> None:
    global DB_FILE
    DB_FILE = path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
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
