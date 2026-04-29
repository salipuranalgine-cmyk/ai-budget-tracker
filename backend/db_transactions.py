from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from models import BudgetLimit, Transaction


def add_transaction(
    txn_type: str,
    amount: float,
    category: str,
    description: str = "",
    txn_date: Optional[str] = None,
) -> int:
    from . import database as db

    txn_date = txn_date or datetime.now().strftime("%Y-%m-%d")
    logged_date = datetime.now().strftime("%Y-%m-%d")
    return db.insert_and_get_id(
        """
        INSERT INTO transactions (txn_type, amount, category, description, txn_date, logged_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (txn_type, amount, category, description.strip(), txn_date, logged_date),
    )


def update_transaction(
    txn_id: int,
    txn_type: str,
    amount: float,
    category: str,
    description: str,
    txn_date: str,
) -> None:
    from . import database as db

    conn = db._connect()
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
    from . import database as db

    conn = db._connect()
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
    from . import database as db

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
    conn = db._connect()
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


def get_starting_balance() -> float:
    from . import database as db

    conn = db._connect()
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'starting_balance'"
    ).fetchone()
    conn.close()
    return float(row["value"]) if row else 0.0


def set_starting_balance(amount: float) -> None:
    from . import database as db

    conn = db._connect()
    conn.execute(
        """
        INSERT INTO app_meta(key, value) VALUES('starting_balance', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(amount),),
    )
    conn.commit()
    conn.close()


def get_app_meta(key: str, default: Optional[str] = None) -> Optional[str]:
    from . import database as db

    conn = db._connect()
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = ?",
        (key,),
    ).fetchone()
    conn.close()
    return row["value"] if row else default


def set_app_meta(key: str, value: str) -> None:
    from . import database as db

    conn = db._connect()
    conn.execute(
        """
        INSERT INTO app_meta(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )
    conn.commit()
    conn.close()


def get_balance() -> float:
    from . import database as db

    today = datetime.now().strftime("%Y-%m-%d")
    conn = db._connect()
    income = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions "
        "WHERE txn_type = 'income' AND txn_date <= ?",
        (today,),
    ).fetchone()["total"]
    expense = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions "
        "WHERE txn_type = 'expense' AND txn_date <= ?",
        (today,),
    ).fetchone()["total"]
    conn.close()
    starting = get_starting_balance()
    return round(starting + float(income) - float(expense), 2)


def get_month_income_total(month: str) -> float:
    from . import database as db

    conn = db._connect()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM transactions "
        "WHERE txn_type = 'income' AND substr(txn_date, 1, 7) = ?",
        (month,),
    ).fetchone()
    conn.close()
    return float(row["total"])


def get_month_expense_summary(month: str) -> dict[str, float]:
    from . import database as db

    conn = db._connect()
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
    from . import database as db

    conn = db._connect()
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
    from . import database as db

    cutoff = (datetime.now().date() - timedelta(days=days)).isoformat()
    conn = db._connect()
    rows = conn.execute(
        """
        SELECT txn_date, COALESCE(SUM(amount), 0) AS total
        FROM transactions
        WHERE txn_type = 'expense' AND txn_date >= ?
        GROUP BY txn_date
        ORDER BY txn_date ASC
        """,
        (cutoff,),
    ).fetchall()
    conn.close()
    return [(row["txn_date"], float(row["total"])) for row in rows]


def set_budget_limit(
    category: str,
    monthly_limit: float,
    duration_type: str = "month",
    duration_days: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> None:
    from . import database as db

    start_date = start_date or datetime.now().strftime("%Y-%m-%d")
    conn = db._connect()
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
    from . import database as db

    conn = db._connect()
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
    from . import database as db

    conn = db._connect()
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
    from . import database as db

    conn = db._connect()
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


def export_transactions_csv(path: str) -> str:
    txns = get_transactions()
    export_path = Path(path)
    export_path.parent.mkdir(parents=True, exist_ok=True)
    with export_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "type", "amount", "category", "description", "date"])
        for txn in txns:
            writer.writerow(
                [txn.id, txn.txn_type, f"{txn.amount:.2f}", txn.category, txn.description, txn.txn_date]
            )
    return str(export_path)


def get_currency() -> str:
    conn = _meta_connection()
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'currency'"
    ).fetchone()
    conn.close()
    return row["value"] if row else "PHP"


def set_currency(code: str) -> None:
    conn = _meta_connection()
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
    conn = _meta_connection()
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'anthropic_api_key'"
    ).fetchone()
    conn.close()
    return row["value"] if row else ""


def set_anthropic_api_key(key: str) -> None:
    conn = _meta_connection()
    conn.execute(
        """
        INSERT INTO app_meta(key, value) VALUES('anthropic_api_key', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key.strip(),),
    )
    conn.commit()
    conn.close()


def get_ai_provider_mode() -> str:
    conn = _meta_connection()
    row = conn.execute(
        "SELECT value FROM app_meta WHERE key = 'ai_provider_mode'"
    ).fetchone()
    conn.close()
    value = row["value"] if row else "smart"
    return value if value in {"smart", "offline_first", "online_first"} else "smart"


def set_ai_provider_mode(mode: str) -> None:
    normalized = (mode or "smart").strip() or "smart"
    if normalized not in {"smart", "offline_first", "online_first"}:
        normalized = "smart"

    conn = _meta_connection()
    conn.execute(
        """
        INSERT INTO app_meta(key, value) VALUES('ai_provider_mode', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (normalized,),
    )
    conn.commit()
    conn.close()


def _meta_connection():
    from . import database as db

    return db._connect()
