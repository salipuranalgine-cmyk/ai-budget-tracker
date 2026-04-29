"""
notifications.py
Central notification hub for Budget Guardian.

Types: budget_exceeded, budget_warning, bill_due, ai_insight
"""
from __future__ import annotations
from dataclasses import dataclass
from backend import database as db

# ── Type constants ────────────────────────────────────────────────────────────
TYPE_BUDGET_EXCEEDED = "budget_exceeded"
TYPE_BUDGET_WARNING  = "budget_warning"
TYPE_BILL_DUE        = "bill_due"
TYPE_AI_INSIGHT      = "ai_insight"


def _normalize_type(notif_type: str) -> str:
    """Keep backwards compatibility with older AI notification aliases."""
    if notif_type == "ai":
        return TYPE_AI_INSIGHT
    return notif_type

# ── Notification dataclass (used by UI) ───────────────────────────────────────
@dataclass
class Notification:
    id:         int
    notif_type: str
    title:      str
    body:       str       # maps from db "message"
    read:       bool      # maps from db "is_read"
    timestamp:  str       # maps from db "created_at"

    @staticmethod
    def from_row(row: dict) -> "Notification":
        return Notification(
            id=row["id"],
            notif_type=_normalize_type(row["notif_type"]),
            title=row["title"],
            body=row["message"],
            read=bool(row["is_read"]),
            timestamp=row["created_at"],
        )

# ── Subscriber registry ───────────────────────────────────────────────────────
_subscribers: list = []


def subscribe(fn) -> None:
    """Register a zero-arg callback that fires on any notification change."""
    if fn not in _subscribers:
        _subscribers.append(fn)


def unsubscribe(fn) -> None:
    """Remove a previously registered callback."""
    try:
        _subscribers.remove(fn)
    except ValueError:
        pass


def _fire() -> None:
    for fn in list(_subscribers):
        try:
            fn()
        except Exception:
            pass


# ── Session management ────────────────────────────────────────────────────────

def reset() -> None:
    """
    Called when switching users. Initialises the notifications table for the
    newly selected user DB and clears stale subscriber callbacks.
    """
    _subscribers.clear()
    db.init_notifications_table()


# ── Read API ──────────────────────────────────────────────────────────────────

def get_all() -> list[Notification]:
    return [Notification.from_row(r) for r in db.get_notifications()]


def unread_count() -> int:
    return db.get_unread_notifications_count()


# ── Write API ─────────────────────────────────────────────────────────────────

def add(notif_type: str, title: str, message: str) -> int:
    nid = db.add_notification(_normalize_type(notif_type), title, message)
    _fire()
    return nid


def mark_read(notif_id: int) -> None:
    db.mark_notification_read(notif_id)
    _fire()


def mark_all_read() -> None:
    db.mark_all_notifications_read()
    _fire()


def delete(notif_id: int) -> None:
    db.delete_notification(notif_id)
    _fire()


def delete_selected(notif_ids: list[int]) -> None:
    db.delete_notifications(notif_ids)
    _fire()


def clear_all() -> None:
    db.clear_all_notifications()
    _fire()


# ── Auto-generation ───────────────────────────────────────────────────────────

def generate_budget_notifications(budget_limits: list, expense_map: dict) -> None:
    """
    Refresh budget_warning / budget_exceeded notifications.
    Called on login and whenever budget/transaction data changes.
    """
    db.delete_notifications_by_type(TYPE_BUDGET_WARNING)
    db.delete_notifications_by_type(TYPE_BUDGET_EXCEEDED)

    for b in budget_limits:
        if b.monthly_limit <= 0:
            continue
        spent = expense_map.get(b.category, 0.0)
        pct = spent / b.monthly_limit * 100

        if pct >= 100:
            db.add_notification(
                TYPE_BUDGET_EXCEEDED,
                f"Budget Exceeded — {b.category}",
                f"You've used {pct:.0f}% of your limit "
                f"(spent {spent:,.0f} this month). Consider cutting back now.",
            )
        elif pct >= 80:
            db.add_notification(
                TYPE_BUDGET_WARNING,
                f"Budget Warning — {b.category}",
                f"You're at {pct:.0f}% of your limit "
                f"(spent {spent:,.0f}). Slow down before you go over.",
            )

    _fire()


def generate_bill_notifications(upcoming: list) -> None:
    """
    Refresh bill_due notifications.
    Only flags overdue, due today, and due within 3 days.
    """
    db.delete_notifications_by_type(TYPE_BILL_DUE)

    for u in upcoming:
        days = u["days_away"]
        name = (u.get("description") or "").strip() or u["category"]

        if days < 0:
            db.add_notification(
                TYPE_BILL_DUE,
                f"Overdue — {u['category']}",
                f'"{name}" was due {abs(days)} day(s) ago and hasn\'t been logged.',
            )
        elif days == 0:
            db.add_notification(
                TYPE_BILL_DUE,
                f"Due Today — {u['category']}",
                f'"{name}" is due today! Make sure to log it.',
            )
        elif days <= 3:
            db.add_notification(
                TYPE_BILL_DUE,
                f"Due in {days} Day(s) — {u['category']}",
                f'"{name}" is coming up in {days} day(s). Plan ahead.',
            )

    _fire()


def add_ai_insight(title: str, message: str) -> None:
    """Add an AI-generated insight notification (persists across sessions)."""
    add(TYPE_AI_INSIGHT, title, message)


def scan_ai_reply(reply: str) -> None:
    """
    Fallback keyword scanner for urgent AI advice when the structured
    [NOTIFY: ...] tag was not included in the reply.
    """
    compact = " ".join((reply or "").split())
    if not compact:
        return

    lower = compact.lower()
    rules = [
        (("budget exceeded", "over budget", "exceeded your budget"), "AI Budget Alert"),
        (("low balance", "dangerously low", "cash is running out"), "AI Low Balance Warning"),
        (("overdue", "past due", "bill is due today", "due today"), "AI Bill Warning"),
    ]

    for keywords, title in rules:
        if any(keyword in lower for keyword in keywords):
            message = compact[:180]
            if len(compact) > 180:
                message += "..."
            add_ai_insight(title, message)
            return
