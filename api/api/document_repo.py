"""Database access for uploaded documents and RAG chunks."""

from __future__ import annotations

import uuid
from typing import Any

from psycopg.types.json import Jsonb

from playbook_shared.db import connect


def _conn():
    return connect(register_vector_types=False)


def _vec(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


def get_session_company_id(session_id: uuid.UUID | str) -> uuid.UUID | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT company_id FROM sessions WHERE id = %s", (str(session_id),))
        row = cur.fetchone()
    if row is None:
        return None
    return row[0]


def ensure_session_company(session_id: uuid.UUID | str) -> uuid.UUID | None:
    """Return the session company, creating one for ad hoc demo sessions if needed."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT company_id FROM sessions WHERE id = %s", (str(session_id),))
        row = cur.fetchone()
        if row is None:
            return None
        if row[0] is not None:
            return row[0]

        cur.execute(
            "INSERT INTO companies (name, industry) VALUES (%s, %s) RETURNING id",
            ("Document demo company", "Finance/accounting discovery"),
        )
        company_id = cur.fetchone()[0]
        cur.execute("UPDATE sessions SET company_id = %s WHERE id = %s", (company_id, str(session_id)))
        conn.commit()
        return company_id


def insert_document(
    *,
    document_id: uuid.UUID,
    company_id: uuid.UUID,
    session_id: uuid.UUID | str,
    filename: str,
    doc_type: str,
    storage_url: str,
) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO documents
                (id, company_id, session_id, filename, doc_type, storage_url, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
            """,
            (str(document_id), str(company_id), str(session_id), filename, doc_type, storage_url),
        )
        conn.commit()


def update_document_status(
    document_id: uuid.UUID | str,
    *,
    status: str,
    parsed_text: str | None = None,
) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE documents SET status = %s, parsed_text = %s WHERE id = %s",
            (status, parsed_text, str(document_id)),
        )
        conn.commit()


def list_session_documents(session_id: uuid.UUID | str) -> list[dict[str, Any]]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.filename, d.doc_type, d.status, d.created_at, count(c.id) AS chunk_count
            FROM documents d
            LEFT JOIN document_chunks c ON c.document_id = d.id
            WHERE d.session_id = %s
            GROUP BY d.id
            ORDER BY d.created_at DESC, d.id
            """,
            (str(session_id),),
        )
        cols = ("id", "filename", "doc_type", "status", "created_at", "chunk_count")
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def delete_document_chunks(document_id: uuid.UUID | str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM document_chunks WHERE document_id = %s", (str(document_id),))
        conn.commit()


def insert_document_chunk(
    *,
    document_id: uuid.UUID | str,
    chunk_text: str,
    embedding: list[float],
    metadata: dict[str, Any],
) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO document_chunks (document_id, chunk_text, embedding, metadata)
            VALUES (%s, %s, %s::vector, %s)
            """,
            (str(document_id), chunk_text, _vec(embedding), Jsonb(metadata)),
        )
        conn.commit()


def session_has_document_chunks(session_id: uuid.UUID | str) -> bool:
    company_id = get_session_company_id(session_id)
    if company_id is None:
        return False
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.company_id = %s
            LIMIT 1
            """,
            (str(company_id),),
        )
        return cur.fetchone() is not None


def has_handbook_chunks() -> bool:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM handbook_chunks LIMIT 1")
        return cur.fetchone() is not None


def retrieve_handbook_chunks(
    *,
    query_embedding: list[float],
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Global (unscoped) retrieval over the internal handbook corpus."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT chunk_text, source_file, section, embedding <=> %s::vector AS distance
            FROM handbook_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (_vec(query_embedding), _vec(query_embedding), limit),
        )
        cols = ("chunk_text", "source_file", "section", "distance")
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def retrieve_chunks(
    *,
    company_id: uuid.UUID | str,
    query_embedding: list[float],
    limit: int = 4,
) -> list[dict[str, Any]]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.chunk_text, c.metadata, d.filename, c.embedding <=> %s::vector AS distance
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE d.company_id = %s
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
            """,
            (_vec(query_embedding), str(company_id), _vec(query_embedding), limit),
        )
        cols = ("chunk_text", "metadata", "filename", "distance")
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
