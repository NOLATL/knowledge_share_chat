"""Database access for tokenized colleague answer relays."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from playbook_shared.db import connect


def _conn():
    return connect(register_vector_types=False)


def active_questions_for_session(session_id: uuid.UUID | str) -> list[dict[str, Any]] | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM sessions WHERE id = %s", (str(session_id),))
        if cur.fetchone() is None:
            return None
        cur.execute(
            """
            SELECT q.slot_key, q.category, q.text, q.tier, q.order_hint,
                   EXISTS (
                     SELECT 1 FROM answers a
                     WHERE a.session_id = %s AND a.slot_key = q.slot_key
                   ) AS filled
            FROM questions q
            WHERE q.active = true
            ORDER BY q.order_hint, q.slot_key
            """,
            (str(session_id),),
        )
        cols = ("slot_key", "category", "text", "tier", "order_hint", "filled")
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def resolve_relay_slot(session_id: uuid.UUID | str, slot_key: str | None) -> dict[str, str] | None:
    """Resolve the slot to relay: explicit slot_key, else the session's current
    question (current_slot if still unfilled, else earliest unfilled must_fill).

    Returns {slot_key, question_text}; None if the session is unknown; raises
    ValueError when no shareable question exists.
    """
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT current_slot FROM sessions WHERE id = %s", (str(session_id),))
        row = cur.fetchone()
        if row is None:
            return None

        if slot_key is None:
            cur.execute(
                """
                SELECT q.slot_key FROM questions q
                WHERE q.active = true
                  AND (q.slot_key = %s OR q.tier = 'must_fill')
                  AND NOT EXISTS (
                    SELECT 1 FROM answers a
                    WHERE a.session_id = %s AND a.slot_key = q.slot_key
                  )
                ORDER BY (q.slot_key = %s) DESC, q.order_hint, q.slot_key
                LIMIT 1
                """,
                (row[0], str(session_id), row[0]),
            )
            resolved = cur.fetchone()
            if resolved is None:
                raise ValueError("no unfilled question available to share")
            slot_key = resolved[0]

        cur.execute("SELECT text FROM questions WHERE slot_key = %s AND active = true", (slot_key,))
        question = cur.fetchone()
        if question is None:
            raise ValueError("slot_key is not active")
        return {"slot_key": slot_key, "question_text": question[0]}


def create_relay(
    *,
    session_id: uuid.UUID | str,
    slot_key: str,
    sent_to_email: str,
    expires_in_hours: int,
    context_text: str = "",
    asked_question_text: str | None = None,
) -> dict[str, Any] | None:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM sessions WHERE id = %s", (str(session_id),))
        if cur.fetchone() is None:
            return None
        cur.execute(
            "SELECT text FROM questions WHERE slot_key = %s AND active = true",
            (slot_key,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError("slot_key is not active")
        token = uuid.uuid4()
        cur.execute(
            """
            INSERT INTO email_relays
              (session_id, slot_key, token, sent_to_email, expires_at, context_text, asked_question_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, session_id, slot_key, token, sent_to_email, status, reply_text, expires_at, created_at, context_text
            """,
            (str(session_id), slot_key, str(token), sent_to_email, expires_at, context_text or None, asked_question_text),
        )
        relay = _row(cur.fetchone(), question_text=asked_question_text or row[0])
        conn.commit()
        return relay


def get_relay_by_token(token: uuid.UUID | str) -> dict[str, Any] | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT er.id, er.session_id, er.slot_key, er.token, er.sent_to_email,
                   er.status, er.reply_text, er.expires_at, er.created_at, er.context_text,
                   COALESCE(er.asked_question_text, q.text)
            FROM email_relays er
            JOIN questions q ON q.slot_key = er.slot_key
            WHERE er.token = %s
            """,
            (str(token),),
        )
        row = cur.fetchone()
    return _row(row, question_text=row[10]) if row is not None else None


def delete_relay(token: uuid.UUID | str) -> None:
    """Remove a relay whose email could not be delivered (keeps the slot undelegated)."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM email_relays WHERE token = %s", (str(token),))
        conn.commit()


def mark_answered(token: uuid.UUID | str, reply_text: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE email_relays
            SET status = 'answered', reply_text = %s
            WHERE token = %s
            """,
            (reply_text, str(token)),
        )
        conn.commit()


def mark_expired(token: uuid.UUID | str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE email_relays SET status = 'expired' WHERE token = %s AND status = 'sent'",
            (str(token),),
        )
        conn.commit()


def is_usable(relay: dict[str, Any]) -> bool:
    expires_at = relay["expires_at"]
    return relay["status"] == "sent" and expires_at is not None and expires_at > datetime.now(timezone.utc)


def _row(row, *, question_text: str) -> dict[str, Any]:
    return {
        "id": row[0],
        "session_id": row[1],
        "slot_key": row[2],
        "token": row[3],
        "sent_to_email": row[4],
        "status": row[5],
        "reply_text": row[6],
        "expires_at": row[7],
        "created_at": row[8],
        "context_text": row[9] or "",
        "question_text": question_text,
    }
