from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from typing import Any

_EMBED_DIMENSIONS = 384


def init_rag_tables() -> None:
    from . import database as db

    pgvector_enabled = _pgvector_enabled()
    conn = db._connect()

    if db.using_postgres():
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_documents (
                id BIGSERIAL PRIMARY KEY,
                source_group TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(source_group, source_type, source_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id BIGSERIAL PRIMARY KEY,
                document_id BIGINT NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                chunk_tokens INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(document_id, chunk_index)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rag_documents_group ON rag_documents(source_group)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rag_chunks_document_id ON rag_chunks(document_id)"
        )

        if pgvector_enabled:
            try:
                conn.execute(
                    f"ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS embedding vector({_EMBED_DIMENSIONS})"
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_hnsw
                    ON rag_chunks USING hnsw (embedding vector_cosine_ops)
                    """
                )
                conn.execute(
                    "UPDATE rag_chunks SET embedding = vector_json::vector WHERE embedding IS NULL"
                )
            except Exception:
                pass
    else:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_group TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(source_group, source_type, source_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                chunk_tokens INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(document_id, chunk_index)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rag_documents_group ON rag_documents(source_group)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_rag_chunks_document_id ON rag_chunks(document_id)"
        )

    conn.commit()
    conn.close()


def _pgvector_enabled() -> bool:
    from . import database as db

    if not db.using_postgres():
        return False

    public = db._connect_public()
    try:
        row = public.execute(
            "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        if row:
            return True
        try:
            public.execute("CREATE EXTENSION IF NOT EXISTS vector")
            public.commit()
        except Exception:
            pass
        row = public.execute(
            "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        return bool(row)
    finally:
        public.close()


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _token_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9_]+", text or ""))


def _content_hash(title: str, content: str, metadata_json: str) -> str:
    payload = f"{title}\n{content}\n{metadata_json}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _chunk_text(text: str, *, chunk_size: int = 420, overlap: int = 80) -> list[str]:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        if end < len(cleaned):
            boundary = max(
                cleaned.rfind(". ", start, end),
                cleaned.rfind("; ", start, end),
                cleaned.rfind(", ", start, end),
                cleaned.rfind(" | ", start, end),
            )
            if boundary > start + int(chunk_size * 0.45):
                end = boundary + 1
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    try:
        from sklearn.feature_extraction.text import HashingVectorizer

        vectorizer = HashingVectorizer(
            n_features=_EMBED_DIMENSIONS,
            alternate_sign=False,
            norm="l2",
            stop_words="english",
        )
        matrix = vectorizer.transform(texts)
        return [row.toarray().ravel().astype(float).tolist() for row in matrix]
    except Exception:
        return [_fallback_embed_text(text) for text in texts]


def _fallback_embed_text(text: str, dims: int = _EMBED_DIMENSIONS) -> list[float]:
    tokens = re.findall(r"[A-Za-z0-9_]+", (text or "").lower())
    vec = [0.0] * dims
    for token in tokens:
        bucket = hash(token) % dims
        vec[bucket] += 1.0
    norm = math.sqrt(sum(value * value for value in vec)) or 1.0
    return [value / norm for value in vec]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return float(sum(a * b for a, b in zip(left, right)))


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"


def sync_rag_documents(source_group: str, documents: list[dict[str, Any]]) -> None:
    from . import database as db

    init_rag_tables()
    now_text = _now_text()
    pgvector_enabled = _pgvector_enabled()
    normalized_docs: list[dict[str, Any]] = []

    for doc in documents:
        source_type = str(doc.get("source_type", "")).strip()
        source_id = str(doc.get("source_id", "")).strip()
        title = str(doc.get("title", "")).strip()
        content = str(doc.get("content", "")).strip()
        metadata = doc.get("metadata", {})
        if not source_type or not source_id or not content:
            continue
        safe_title = title or f"{source_type}:{source_id}"
        metadata_json = json.dumps(metadata or {}, sort_keys=True)
        normalized_docs.append(
            {
                "source_type": source_type,
                "source_id": source_id,
                "title": safe_title,
                "content": content,
                "metadata_json": metadata_json,
                "content_hash": _content_hash(safe_title, content, metadata_json),
            }
        )

    conn = db._connect()
    existing_rows = conn.execute(
        """
        SELECT id, source_type, source_id, content_hash
        FROM rag_documents
        WHERE source_group = ?
        """,
        (source_group,),
    ).fetchall()
    existing = {
        (row["source_type"], row["source_id"]): {
            "id": row["id"],
            "content_hash": row["content_hash"],
        }
        for row in existing_rows
    }

    seen_keys: set[tuple[str, str]] = set()
    for doc in normalized_docs:
        key = (doc["source_type"], doc["source_id"])
        seen_keys.add(key)
        existing_doc = existing.get(key)
        if existing_doc and existing_doc["content_hash"] == doc["content_hash"]:
            continue

        if existing_doc:
            conn.execute(
                """
                UPDATE rag_documents
                SET title = ?, content = ?, metadata_json = ?, content_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    doc["title"],
                    doc["content"],
                    doc["metadata_json"],
                    doc["content_hash"],
                    now_text,
                    existing_doc["id"],
                ),
            )
            document_id = int(existing_doc["id"])
            conn.execute("DELETE FROM rag_chunks WHERE document_id = ?", (document_id,))
        else:
            document_id = db.insert_and_get_id(
                """
                INSERT INTO rag_documents (
                    source_group, source_type, source_id, title, content,
                    metadata_json, content_hash, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_group,
                    doc["source_type"],
                    doc["source_id"],
                    doc["title"],
                    doc["content"],
                    doc["metadata_json"],
                    doc["content_hash"],
                    now_text,
                    now_text,
                ),
            )
            conn = db._connect()

        chunks = _chunk_text(doc["content"])
        vectors = _embed_texts(chunks)
        for idx, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
            vector_json = json.dumps(vector)
            if db.using_postgres() and pgvector_enabled:
                conn.execute(
                    """
                    INSERT INTO rag_chunks (
                        document_id, chunk_index, chunk_text, vector_json, embedding, chunk_tokens, created_at
                    )
                    VALUES (?, ?, ?, ?, ?::vector, ?, ?)
                    """,
                    (
                        document_id,
                        idx,
                        chunk_text,
                        vector_json,
                        _vector_literal(vector),
                        _token_count(chunk_text),
                        now_text,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO rag_chunks (
                        document_id, chunk_index, chunk_text, vector_json, chunk_tokens, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        idx,
                        chunk_text,
                        vector_json,
                        _token_count(chunk_text),
                        now_text,
                    ),
                )
        conn.commit()

    stale_keys = [key for key in existing.keys() if key not in seen_keys]
    for source_type, source_id in stale_keys:
        conn.execute(
            """
            DELETE FROM rag_documents
            WHERE source_group = ? AND source_type = ? AND source_id = ?
            """,
            (source_group, source_type, source_id),
        )
    conn.commit()
    conn.close()


def search_rag_chunks(
    query: str,
    *,
    source_group: str,
    limit: int = 6,
) -> list[dict[str, Any]]:
    from . import database as db

    init_rag_tables()
    query = (query or "").strip()
    if not query:
        return []

    query_vector_list = _embed_texts([query])
    if not query_vector_list:
        return []
    query_vector = query_vector_list[0]

    if db.using_postgres() and _pgvector_enabled():
        conn = db._connect()
        try:
            rows = conn.execute(
                """
                SELECT
                    c.chunk_text,
                    d.title,
                    d.source_type,
                    d.source_id,
                    d.metadata_json,
                    1 - (c.embedding <=> ?::vector) AS score
                FROM rag_chunks c
                JOIN rag_documents d ON d.id = c.document_id
                WHERE d.source_group = ? AND c.embedding IS NOT NULL
                ORDER BY c.embedding <=> ?::vector
                LIMIT ?
                """,
                (_vector_literal(query_vector), source_group, _vector_literal(query_vector), limit),
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "score": float(row["score"] or 0.0),
                "text": row["chunk_text"],
                "title": row["title"],
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
            }
            for row in rows
        ]

    conn = db._connect()
    rows = conn.execute(
        """
        SELECT
            c.chunk_text,
            c.vector_json,
            d.title,
            d.source_type,
            d.source_id,
            d.metadata_json
        FROM rag_chunks c
        JOIN rag_documents d ON d.id = c.document_id
        WHERE d.source_group = ?
        """,
        (source_group,),
    ).fetchall()
    conn.close()

    scored: list[dict[str, Any]] = []
    for row in rows:
        try:
            vector = json.loads(row["vector_json"])
        except Exception:
            continue
        score = _cosine_similarity(query_vector, vector)
        if score <= 0:
            continue
        scored.append(
            {
                "score": score,
                "text": row["chunk_text"],
                "title": row["title"],
                "source_type": row["source_type"],
                "source_id": row["source_id"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]
