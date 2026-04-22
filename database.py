import csv
import sqlite3
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from pathlib import Path
from typing import Optional

from models import BudgetLimit, Transaction, RecurringTransaction

DB_FILE = "budget.db"


def set_user_db(path: str) -> None:
    """Switch the active database to the given file path (called on user login)."""
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
    # Safe migration: add columns if they don't exist yet
    for col_sql in [
        "ALTER TABLE budget_limits ADD COLUMN duration_type TEXT DEFAULT 'month'",
        "ALTER TABLE budget_limits ADD COLUMN duration_days INTEGER DEFAULT 30",
        "ALTER TABLE budget_limits ADD COLUMN start_date TEXT",
        "ALTER TABLE budget_limits ADD COLUMN end_date TEXT",
    ]:
        try:
            cur.execute(col_sql)
        except sqlite3.OperationalError:
            pass  # column already exists

    # Add logged_date to transactions if missing (safe migration)
    try:
        cur.execute("ALTER TABLE transactions ADD COLUMN logged_date TEXT")
    except sqlite3.OperationalError:
        pass  # already exists

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
    # Safe migration for older recurring_transactions schema versions
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

    # Backfill next_date from known date fields when available
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


# ---------------------------------------------------------------------------
# Recurring transactions
# ---------------------------------------------------------------------------

def _next_occurrence(current: date, frequency: str, frequency_days: int) -> date:
    if frequency == "daily":
        return current + timedelta(days=1)
    elif frequency == "weekly":
        return current + timedelta(weeks=1)
    elif frequency == "biweekly":
        return current + timedelta(weeks=2)
    elif frequency == "monthly":
        return current + relativedelta(months=1)
    elif frequency == "yearly":
        return current + relativedelta(years=1)
    elif frequency == "custom":
        return current + timedelta(days=max(1, frequency_days))
    return current + timedelta(days=30)


def add_recurring_transaction(
    txn_type: str,
    amount: float,
    category: str,
    description: str,
    frequency: str,
    frequency_days: int,
    start_date: str,
) -> int:
    conn = _connect()
    cur = conn.cursor()
    rec_cols = {row["name"] for row in cur.execute("PRAGMA table_info(recurring_transactions)").fetchall()}
    has_next_due = "next_due_date" in rec_cols
    if has_next_due:
        cur.execute(
            """
            INSERT INTO recurring_transactions
                (
                    txn_type, amount, category, description, frequency, frequency_days,
                    start_date, next_date, next_due_date, active
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                txn_type,
                amount,
                category,
                description.strip(),
                frequency,
                frequency_days,
                start_date,
                start_date,
                start_date,
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO recurring_transactions
                (txn_type, amount, category, description, frequency, frequency_days, start_date, next_date, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (txn_type, amount, category, description.strip(), frequency, frequency_days, start_date, start_date),
        )
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return int(last_id)


def get_recurring_transactions() -> list[RecurringTransaction]:
    conn = _connect()
    rows = conn.execute(
        """
        SELECT id, txn_type, amount, category, description,
               frequency, frequency_days, start_date, next_date, active
        FROM recurring_transactions
        ORDER BY txn_type DESC, category ASC
        """
    ).fetchall()
    conn.close()
    return [
        RecurringTransaction(
            id=row["id"],
            txn_type=row["txn_type"],
            amount=float(row["amount"]),
            category=row["category"],
            description=row["description"],
            frequency=row["frequency"],
            frequency_days=int(row["frequency_days"] or 0),
            start_date=row["start_date"],
            next_date=row["next_date"],
            active=bool(row["active"]),
        )
        for row in rows
    ]


def toggle_recurring(rec_id: int, active: bool) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE recurring_transactions SET active = ? WHERE id = ?",
        (1 if active else 0, rec_id),
    )
    conn.commit()
    conn.close()


def delete_recurring(rec_id: int) -> None:
    conn = _connect()
    conn.execute("DELETE FROM recurring_transactions WHERE id = ?", (rec_id,))
    conn.commit()
    conn.close()


def update_recurring_transaction(
    rec_id: int,
    amount: float,
    category: str,
    description: str,
    frequency: str,
    frequency_days: int,
    next_date: str,
) -> None:
    """Update an existing recurring transaction's details and next due date."""
    conn = _connect()
    conn.execute(
        """
        UPDATE recurring_transactions
        SET amount = ?, category = ?, description = ?, frequency = ?,
            frequency_days = ?, next_date = ?
        WHERE id = ?
        """,
        (amount, category, description.strip(), frequency, frequency_days, next_date, rec_id),
    )
    conn.commit()
    conn.close()


def get_upcoming_recurring(days: int = 7) -> list[dict]:
    """Return active recurring transactions due within the next N days (for dashboard warning)."""
    from datetime import date, timedelta
    today = date.today()
    cutoff = (today + timedelta(days=days)).isoformat()
    conn = _connect()
    rows = conn.execute(
        """
        SELECT id, txn_type, amount, category, description, frequency, next_date
        FROM recurring_transactions
        WHERE active = 1 AND next_date <= ?
        ORDER BY next_date ASC
        """,
        (cutoff,),
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        nd = row["next_date"]
        try:
            from datetime import datetime as _dt
            due_date = _dt.strptime(nd, "%Y-%m-%d").date()
            days_away = (due_date - today).days
        except Exception:
            days_away = 0
        result.append({
            "id": row["id"],
            "txn_type": row["txn_type"],
            "amount": float(row["amount"]),
            "category": row["category"],
            "description": row["description"],
            "frequency": row["frequency"],
            "next_date": nd,
            "days_away": days_away,
        })
    return result


def apply_due_recurring() -> int:
    """Apply all recurring transactions that are due today or earlier. Returns count applied."""
    today = date.today()
    conn = _connect()
    rec_cols = {row["name"] for row in conn.execute("PRAGMA table_info(recurring_transactions)").fetchall()}
    has_next_due = "next_due_date" in rec_cols
    next_expr = "COALESCE(NULLIF(next_date, ''), next_due_date)" if has_next_due else "next_date"
    rows = conn.execute(
        f"SELECT *, {next_expr} AS due_date FROM recurring_transactions WHERE active = 1 AND {next_expr} <= ?",
        (today.isoformat(),),
    ).fetchall()
    count = 0
    for row in rows:
        cur_date = datetime.strptime(row["due_date"], "%Y-%m-%d").date()
        while cur_date <= today:
            conn.execute(
                """
                INSERT INTO transactions (txn_type, amount, category, description, txn_date)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["txn_type"],
                    float(row["amount"]),
                    row["category"],
                    f"[Auto] {row['description']}".strip(),
                    cur_date.isoformat(),
                ),
            )
            count += 1
            cur_date = _next_occurrence(cur_date, row["frequency"], int(row["frequency_days"] or 0))
        if has_next_due:
            conn.execute(
                "UPDATE recurring_transactions SET next_date = ?, next_due_date = ? WHERE id = ?",
                (cur_date.isoformat(), cur_date.isoformat(), row["id"]),
            )
        else:
            conn.execute(
                "UPDATE recurring_transactions SET next_date = ? WHERE id = ?",
                (cur_date.isoformat(), row["id"]),
            )
    conn.commit()
    conn.close()
    return count


# ---------------------------------------------------------------------------
# One-time transactions
# ---------------------------------------------------------------------------

def add_transaction(
    txn_type: str,
    amount: float,
    category: str,
    description: str = "",
    txn_date: Optional[str] = None,
) -> int:
    txn_date = txn_date or datetime.now().strftime("%Y-%m-%d")
    logged_date = datetime.now().strftime("%Y-%m-%d")
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO transactions (txn_type, amount, category, description, txn_date, logged_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (txn_type, amount, category, description.strip(), txn_date, logged_date),
    )
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return int(last_id)


def update_transaction(
    txn_id: int,
    txn_type: str,
    amount: float,
    category: str,
    description: str,
    txn_date: str,
) -> None:
    conn = _connect()
    conn.execute(
        """
        UPDATE transactions
        SET txn_type = ?, amount = ?, category = ?, description = ?, txn_date = ?
        WHERE id = ?
        """,
        (txn_type, amount, category, description.strip(), txn_date, txn_id),
    )
    conn.commit()
    conn.close()


def delete_transaction(txn_id: int) -> None:
    conn = _connect()
    conn.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
    conn.commit()
    conn.close()


def get_transactions(
    search: str = "",
    category: str = "All",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
) -> list[Transaction]:
    query = """
        SELECT id, txn_type, amount, category, description, txn_date,
               COALESCE(logged_date, txn_date) AS logged_date
        FROM transactions
        WHERE 1 = 1
    """
    params: list[object] = []
    if search:
        query += " AND (description LIKE ? OR category LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if date_from:
        query += " AND txn_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND txn_date <= ?"
        params.append(date_to)
    if min_amount is not None:
        query += " AND amount >= ?"
        params.append(min_amount)
    if max_amount is not None:
        query += " AND amount <= ?"
        params.append(max_amount)
    query += " ORDER BY txn_date DESC, id DESC"
    conn = _connect()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [
        Transaction(
            id=row["id"],
            txn_type=row["txn_type"],
            amount=float(row["amount"]),
            category=row["category"],
            description=row["description"],
            txn_date=row["txn_date"],
            logged_date=row["logged_date"],
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Starting balance helpers
# ---------------------------------------------------------------------------

def get_starting_balance() -> float:
    conn = _connect()
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'starting_balance'"
    ).fetchone()
    conn.close()
    return float(row["value"]) if row else 0.0


def set_starting_balance(amount: float) -> None:
    conn = _connect()
    conn.execute(
        """
        INSERT INTO app_meta(key, value) VALUES('starting_balance', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(amount),),
    )
    conn.commit()
    conn.close()


def get_balance() -> float:
    """
    Balance only counts transactions whose txn_date is on or before today.
    Future-dated transactions are recorded but do not affect the current balance
    until their date arrives.
    """
    conn = _connect()
    income = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions "
        "WHERE txn_type = 'income' AND txn_date <= date('now')"
    ).fetchone()["total"]
    expense = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions "
        "WHERE txn_type = 'expense' AND txn_date <= date('now')"
    ).fetchone()["total"]
    conn.close()
    starting = get_starting_balance()
    return round(starting + float(income) - float(expense), 2)



def get_month_income_total(month: str) -> float:
    """Total income recorded for the given month (YYYY-MM)."""
    conn = _connect()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions "
        "WHERE txn_type = 'income' AND substr(txn_date, 1, 7) = ?",
        (month,),
    ).fetchone()
    conn.close()
    return float(row["total"])

def get_month_expense_summary(month: str) -> dict[str, float]:
    conn = _connect()
    rows = conn.execute(
        """
        SELECT category, COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE txn_type = 'expense' AND substr(txn_date, 1, 7) = ?
        GROUP BY category
        ORDER BY total DESC
        """,
        (month,),
    ).fetchall()
    conn.close()
    return {row["category"]: float(row["total"]) for row in rows}


def get_expense_summary_range(start_date: str, end_date: str) -> dict[str, float]:
    """Get expense totals per category within a date range (inclusive)."""
    conn = _connect()
    rows = conn.execute(
        """
        SELECT category, COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE txn_type = 'expense' AND txn_date >= ? AND txn_date <= ?
        GROUP BY category
        ORDER BY total DESC
        """,
        (start_date, end_date),
    ).fetchall()
    conn.close()
    return {row["category"]: float(row["total"]) for row in rows}


def get_expenses_last_days(days: int = 30) -> list[tuple[str, float]]:
    conn = _connect()
    rows = conn.execute(
        """
        SELECT txn_date, COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE txn_type = 'expense' AND date(txn_date) >= date('now', ?)
        GROUP BY txn_date
        ORDER BY txn_date ASC
        """,
        (f"-{days} day",),
    ).fetchall()
    conn.close()
    return [(row["txn_date"], float(row["total"])) for row in rows]


# ---------------------------------------------------------------------------
# Budget limits with duration
# ---------------------------------------------------------------------------

def set_budget_limit(
    category: str,
    monthly_limit: float,
    duration_type: str = "month",
    duration_days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> None:
    start_date = start_date or datetime.now().strftime("%Y-%m-%d")
    conn = _connect()
    conn.execute(
        """
        INSERT INTO budget_limits (category, monthly_limit, duration_type, duration_days, start_date, end_date)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(category) DO UPDATE SET
            monthly_limit = excluded.monthly_limit,
            duration_type = excluded.duration_type,
            duration_days = excluded.duration_days,
            start_date = excluded.start_date,
            end_date = excluded.end_date
        """,
        (category, monthly_limit, duration_type, duration_days, start_date, end_date),
    )
    conn.commit()
    conn.close()


def get_budget_limits() -> list[BudgetLimit]:
    conn = _connect()
    rows = conn.execute(
        """
        SELECT id, category, monthly_limit,
               COALESCE(duration_type, 'month') AS duration_type,
               COALESCE(duration_days, 30) AS duration_days,
               start_date, end_date
        FROM budget_limits
        ORDER BY category ASC
        """
    ).fetchall()
    conn.close()
    return [
        BudgetLimit(
            id=row["id"],
            category=row["category"],
            monthly_limit=float(row["monthly_limit"]),
            duration_type=row["duration_type"],
            duration_days=int(row["duration_days"]),
            start_date=row["start_date"],
            end_date=row["end_date"],
        )
        for row in rows
    ]


def delete_budget_limit(budget_id: int) -> None:
    conn = _connect()
    conn.execute("DELETE FROM budget_limits WHERE id = ?", (budget_id,))
    conn.commit()
    conn.close()


def update_budget_limit(
    budget_id: int,
    monthly_limit: float,
    duration_type: str = "custom",
    duration_days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> None:
    conn = _connect()
    conn.execute(
        """
        UPDATE budget_limits
        SET monthly_limit = ?, duration_type = ?, duration_days = ?,
            start_date = ?, end_date = ?
        WHERE id = ?
        """,
        (monthly_limit, duration_type, duration_days, start_date, end_date, budget_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_transactions_csv(path: str) -> str:
    txns = get_transactions()
    export_path = Path(path)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    with export_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "type", "amount", "category", "description", "date"])
        for t in txns:
            writer.writerow(
                [t.id, t.txn_type, f"{t.amount:.2f}", t.category, t.description, t.txn_date]
            )
    return str(export_path)


# ---------------------------------------------------------------------------
# First-run helpers
# ---------------------------------------------------------------------------



def get_currency() -> str:
    """Return the stored currency code (e.g. 'PHP', 'USD'), default 'PHP'."""
    conn = _connect()
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'currency'"
    ).fetchone()
    conn.close()
    return row["value"] if row else "PHP"


def set_currency(code: str) -> None:
    conn = _connect()
    conn.execute(
        """
        INSERT INTO app_meta(key, value) VALUES('currency', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (code,),
    )
    conn.commit()
    conn.close()

def get_anthropic_api_key() -> str:
    """Return the stored Anthropic API key, or empty string if not set."""
    conn = _connect()
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'anthropic_api_key'"
    ).fetchone()
    conn.close()
    return row["value"] if row else ""


def set_anthropic_api_key(key: str) -> None:
    conn = _connect()
    conn.execute(
        """
        INSERT INTO app_meta(key, value) VALUES('anthropic_api_key', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key.strip(),),
    )
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def init_notifications_table() -> None:
    """Create notifications table if it doesn't exist (safe to call repeatedly)."""
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            notif_type  TEXT    NOT NULL,
            title       TEXT    NOT NULL,
            message     TEXT    NOT NULL,
            is_read     INTEGER DEFAULT 0,
            created_at  TEXT    DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.commit()
    conn.close()


def add_notification(notif_type: str, title: str, message: str) -> int:
    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO notifications (notif_type, title, message) VALUES (?, ?, ?)",
        (notif_type, title, message),
    )
    conn.commit()
    nid = cur.lastrowid
    conn.close()
    return int(nid)


def get_notifications() -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        """
        SELECT id, notif_type, title, message, is_read, created_at
        FROM notifications
        ORDER BY id DESC
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unread_notifications_count() -> int:
    conn = _connect()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM notifications WHERE is_read = 0"
    ).fetchone()
    conn.close()
    return int(row["cnt"])


def mark_notification_read(notif_id: int) -> None:
    conn = _connect()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()


def mark_all_notifications_read() -> None:
    conn = _connect()
    conn.execute("UPDATE notifications SET is_read = 1")
    conn.commit()
    conn.close()


def delete_notifications_by_type(notif_type: str) -> None:
    """Remove all notifications of a specific type (used to refresh auto-generated ones)."""
    conn = _connect()
    conn.execute("DELETE FROM notifications WHERE notif_type = ?", (notif_type,))
    conn.commit()
    conn.close()


def clear_all_notifications() -> None:
    conn = _connect()
    conn.execute("DELETE FROM notifications")
    conn.commit()
    conn.close()


def is_first_run() -> bool:
    conn = _connect()
    row = conn.execute("SELECT value FROM app_meta WHERE key = 'first_run_done'").fetchone()
    conn.close()
    return row is None


def mark_first_run_seen() -> None:
    conn = _connect()
    conn.execute(
        """
        INSERT INTO app_meta(key, value)
        VALUES('first_run_done', '1')
        ON CONFLICT(key) DO UPDATE SET value = '1'
        """
    )
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# AI Chat history
# ---------------------------------------------------------------------------
# Storage is very lightweight: ~200 bytes per message avg.
# 50 sessions × 30 messages = ~300 KB total. Users can delete any session.

def init_chat_tables() -> None:
    """Create chat history tables if they don't exist (safe to call on every startup)."""
    conn = _connect()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL DEFAULT 'Chat',
            created_at  TEXT    DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
            role        TEXT    NOT NULL CHECK(role IN ('user','assistant')),
            content     TEXT    NOT NULL,
            created_at  TEXT    DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.commit()
    conn.close()


def create_chat_session(title: str = "New Chat") -> int:
    """Create a new chat session and return its id."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO chat_sessions (title) VALUES (?)", (title,))
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return int(sid)


def save_chat_message(session_id: int, role: str, content: str) -> None:
    """Append a single message to a session."""
    conn = _connect()
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content),
    )
    conn.commit()
    conn.close()


def update_chat_session_title(session_id: int, title: str) -> None:
    conn = _connect()
    conn.execute("UPDATE chat_sessions SET title = ? WHERE id = ?", (title[:60], session_id))
    conn.commit()
    conn.close()


def get_chat_sessions() -> list[dict]:
    """Return all sessions newest-first, with message count and preview."""
    conn = _connect()
    rows = conn.execute(
        """
        SELECT s.id, s.title, s.created_at,
               COUNT(m.id) AS msg_count,
               (SELECT content FROM chat_messages
                WHERE session_id = s.id AND role = 'assistant'
                ORDER BY id ASC LIMIT 1) AS preview
        FROM chat_sessions s
        LEFT JOIN chat_messages m ON m.session_id = s.id
        GROUP BY s.id
        ORDER BY s.id DESC
        """
    ).fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "msg_count": row["msg_count"],
            "preview": (row["preview"] or "")[:100],
        }
        for row in rows
    ]


def get_chat_messages(session_id: int) -> list[dict]:
    """Return all messages for a session in order."""
    conn = _connect()
    rows = conn.execute(
        "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def delete_chat_session(session_id: int) -> None:
    """Delete a session and all its messages (CASCADE handles messages)."""
    conn = _connect()
    # Manually delete messages first in case PRAGMA foreign_keys is off
    conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


def get_chat_storage_kb() -> float:
    """Rough estimate of chat history size in KB."""
    conn = _connect()
    row = conn.execute(
        "SELECT COALESCE(SUM(LENGTH(content)), 0) AS total FROM chat_messages"
    ).fetchone()
    conn.close()
    return round(float(row["total"]) / 1024, 1)

def delete_all_chat_sessions() -> None:
    """Wipe every chat session and message."""
    conn = _connect()
    conn.execute("DELETE FROM chat_messages")
    conn.execute("DELETE FROM chat_sessions")
    conn.commit()
    conn.close()


def truncate_chat_messages_after_index(session_id: int, keep_count: int) -> None:
    """Keep only the first keep_count messages for a session; delete the rest.

    Used when the user edits a message mid-conversation so that everything
    after the edited point is removed from persistent storage.
    """
    conn = _connect()
    if keep_count <= 0:
        conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    else:
        rows = conn.execute(
            "SELECT id FROM chat_messages WHERE session_id = ? ORDER BY id ASC LIMIT ?",
            (session_id, keep_count),
        ).fetchall()
        if rows:
            last_keep_id = rows[-1]["id"]
            conn.execute(
                "DELETE FROM chat_messages WHERE session_id = ? AND id > ?",
                (session_id, last_keep_id),
            )
        # If the session has fewer messages than keep_count, nothing to delete.
    conn.commit()
    conn.close()