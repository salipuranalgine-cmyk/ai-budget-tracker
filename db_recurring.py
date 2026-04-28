from __future__ import annotations

from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

from models import RecurringTransaction


def _next_occurrence(current: date, frequency: str, frequency_days: int) -> date:
    if frequency == "daily":
        return current + timedelta(days=1)
    if frequency == "weekly":
        return current + timedelta(weeks=1)
    if frequency == "biweekly":
        return current + timedelta(weeks=2)
    if frequency == "monthly":
        return current + relativedelta(months=1)
    if frequency == "yearly":
        return current + relativedelta(years=1)
    if frequency == "custom":
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
    import database as db

    if db.using_postgres():
        return db.insert_and_get_id(
            """
            INSERT INTO recurring_transactions
                (txn_type, amount, category, description, frequency, frequency_days, start_date, next_date, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, TRUE)
            """,
            (txn_type, amount, category, description.strip(), frequency, frequency_days, start_date, start_date),
        )

    conn = db._connect()
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
    import database as db

    conn = db._connect()
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
    import database as db

    conn = db._connect()
    conn.execute(
        "UPDATE recurring_transactions SET active = ? WHERE id = ?",
        ((bool(active) if db.using_postgres() else (1 if active else 0)), rec_id),
    )
    conn.commit()
    conn.close()


def delete_recurring(rec_id: int) -> None:
    import database as db

    conn = db._connect()
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
    import database as db

    conn = db._connect()
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
    import database as db

    today = date.today()
    cutoff = (today + timedelta(days=days)).isoformat()
    conn = db._connect()
    rows = conn.execute(
        """
        SELECT id, txn_type, amount, category, description, frequency, next_date
        FROM recurring_transactions
        WHERE active = ? AND next_date <= ?
        ORDER BY next_date ASC
        """,
        ((True if db.using_postgres() else 1), cutoff),
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        nd = row["next_date"]
        try:
            due_date = datetime.strptime(nd, "%Y-%m-%d").date()
            days_away = (due_date - today).days
        except Exception:
            days_away = 0
        result.append(
            {
                "id": row["id"],
                "txn_type": row["txn_type"],
                "amount": float(row["amount"]),
                "category": row["category"],
                "description": row["description"],
                "frequency": row["frequency"],
                "next_date": nd,
                "days_away": days_away,
            }
        )
    return result


def apply_due_recurring() -> int:
    import database as db

    today = date.today()
    conn = db._connect()
    rec_cols = set()
    has_next_due = False
    if not db.using_postgres():
        rec_cols = {row["name"] for row in conn.execute("PRAGMA table_info(recurring_transactions)").fetchall()}
        has_next_due = "next_due_date" in rec_cols
    next_expr = "COALESCE(NULLIF(next_date, ''), next_due_date)" if has_next_due else "next_date"
    rows = conn.execute(
        f"SELECT *, {next_expr} AS due_date FROM recurring_transactions WHERE active = ? AND {next_expr} <= ?",
        ((True if db.using_postgres() else 1), today.isoformat()),
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
