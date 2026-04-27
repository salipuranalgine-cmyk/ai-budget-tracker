from __future__ import annotations

from typing import Sequence


def init_notifications_table() -> None:
    import database as db

    conn = db._connect()
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
    import database as db

    conn = db._connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO notifications (notif_type, title, message) VALUES (?, ?, ?)",
        (notif_type, title, message),
    )
    conn.commit()
    notif_id = cur.lastrowid
    conn.close()
    return int(notif_id)


def get_notifications() -> list[dict]:
    import database as db

    conn = db._connect()
    rows = conn.execute(
        """
        SELECT id, notif_type, title, message, is_read, created_at
        FROM notifications
        ORDER BY id DESC
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_unread_notifications_count() -> int:
    import database as db

    conn = db._connect()
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM notifications WHERE is_read = 0"
    ).fetchone()
    conn.close()
    return int(row["cnt"])


def mark_notification_read(notif_id: int) -> None:
    import database as db

    conn = db._connect()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()


def mark_all_notifications_read() -> None:
    import database as db

    conn = db._connect()
    conn.execute("UPDATE notifications SET is_read = 1")
    conn.commit()
    conn.close()


def delete_notification(notif_id: int) -> None:
    import database as db

    conn = db._connect()
    conn.execute("DELETE FROM notifications WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()


def delete_notifications(notif_ids: Sequence[int]) -> None:
    import database as db

    ids = [int(notif_id) for notif_id in notif_ids if notif_id is not None]
    if not ids:
        return

    placeholders = ",".join("?" for _ in ids)
    conn = db._connect()
    conn.execute(
        f"DELETE FROM notifications WHERE id IN ({placeholders})",
        tuple(ids),
    )
    conn.commit()
    conn.close()


def delete_notifications_by_type(notif_type: str) -> None:
    import database as db

    conn = db._connect()
    conn.execute("DELETE FROM notifications WHERE notif_type = ?", (notif_type,))
    conn.commit()
    conn.close()


def clear_all_notifications() -> None:
    import database as db

    conn = db._connect()
    conn.execute("DELETE FROM notifications")
    conn.commit()
    conn.close()


def is_first_run() -> bool:
    import database as db

    conn = db._connect()
    row = conn.execute("SELECT value FROM app_meta WHERE key = 'first_run_done'").fetchone()
    conn.close()
    return row is None


def mark_first_run_seen() -> None:
    import database as db

    conn = db._connect()
    conn.execute(
        """
        INSERT INTO app_meta(key, value)
        VALUES('first_run_done', '1')
        ON CONFLICT(key) DO UPDATE SET value = '1'
        """
    )
    conn.commit()
    conn.close()
