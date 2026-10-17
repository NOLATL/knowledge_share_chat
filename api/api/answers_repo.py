"""Writes for extracted answers (UPSERT by the (session, slot, source) key)."""

from __future__ import annotations

import uuid
from typing import Any

from psycopg.types.json import Jsonb

from playbook_shared.db import connect


def _conn():
    return connect(register_vector_types=False)


# Sources that pre-fill a slot without the respondent having confirmed it in
# conversation. Slots filled only by these are "provisional" (GR: confirm, don't skip).
PROVISIONAL_SOURCES = ("intake", "document")


def save_answer(
    session_id: uuid.UUID | str,
    slot_key: str,
    raw_text: str,
    structured_json: dict[str, Any],
    confidence: float | None,
    source: str = "chat",
) -> None:
    """Insert or update the answer for (session, slot, source). Re-extraction is
    idempotent rather than a duplicate-key crash (Appendix A UNIQUE constraint)."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO answers
                (session_id, slot_key, raw_text, structured_json, confidence, source)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_id, slot_key, source) DO UPDATE SET
                raw_text        = EXCLUDED.raw_text,
                structured_json = EXCLUDED.structured_json,
                confidence      = EXCLUDED.confidence,
                created_at      = now()
            """,
            (str(session_id), slot_key, raw_text, Jsonb(structured_json), confidence, source),
        )
        conn.commit()


def set_current_slot(session_id: uuid.UUID | str, slot_key: str | None) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE sessions SET current_slot = %s WHERE id = %s",
            (slot_key, str(session_id)),
        )
        conn.commit()
