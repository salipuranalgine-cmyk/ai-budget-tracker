from __future__ import annotations


def init_chat_tables() -> None:
    import database as db

    conn = db._connect()
    if db.using_postgres():
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'Chat',
                created_at TEXT DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS')
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id BIGSERIAL PRIMARY KEY,
                session_id BIGINT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content TEXT NOT NULL,
                created_at TEXT DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS')
            )
            """
        )
    else:
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
    import database as db

    return db.insert_and_get_id(
        "INSERT INTO chat_sessions (title) VALUES (?)",
        (title,),
    )


def save_chat_message(session_id: int, role: str, content: str) -> None:
    import database as db

    conn = db._connect()
    conn.execute(
        "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content),
    )
    conn.commit()
    conn.close()


def update_chat_session_title(session_id: int, title: str) -> None:
    import database as db

    conn = db._connect()
    conn.execute("UPDATE chat_sessions SET title = ? WHERE id = ?", (title[:60], session_id))
    conn.commit()
    conn.close()


def get_chat_sessions() -> list[dict]:
    import database as db

    conn = db._connect()
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
    import database as db

    conn = db._connect()
    rows = conn.execute(
        "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def delete_chat_session(session_id: int) -> None:
    import database as db

    conn = db._connect()
    conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


def get_chat_storage_kb() -> float:
    import database as db

    conn = db._connect()
    row = conn.execute(
        "SELECT COALESCE(SUM(LENGTH(content)), 0) AS total FROM chat_messages"
    ).fetchone()
    conn.close()
    return round(float(row["total"]) / 1024, 1)


def delete_all_chat_sessions() -> None:
    import database as db

    conn = db._connect()
    conn.execute("DELETE FROM chat_messages")
    conn.execute("DELETE FROM chat_sessions")
    conn.commit()
    conn.close()


def truncate_chat_messages_after_index(session_id: int, keep_count: int) -> None:
    import database as db

    conn = db._connect()
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
    conn.commit()
    conn.close()
