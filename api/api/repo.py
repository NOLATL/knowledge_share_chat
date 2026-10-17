"""Database access for the chat engine (authoritative server-side state, GR3).

Synchronous psycopg via the shared helper; the async routes call these through a
threadpool. Questions are always read from the DB at runtime (GR9) so a reseed
takes effect on the next session with no redeploy.
"""

from __future__ import annotations

import uuid
from typing import Any

from playbook_shared.db import connect

from api.answers_repo import PROVISIONAL_SOURCES


def _conn():
    return connect(register_vector_types=False)


def get_session(session_id: uuid.UUID | str) -> dict[str, Any] | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, status, resume_token, current_slot, script_version "
            "FROM sessions WHERE id = %s",
            (str(session_id),),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "status": row[1],
        "resume_token": row[2],
        "current_slot": row[3],
        "script_version": row[4],
    }


def get_session_by_token(resume_token: uuid.UUID | str) -> dict[str, Any] | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, status, resume_token, current_slot, script_version "
            "FROM sessions WHERE resume_token = %s",
            (str(resume_token),),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "status": row[1],
        "resume_token": row[2],
        "current_slot": row[3],
        "script_version": row[4],
    }


def set_status(session_id: uuid.UUID | str, status: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE sessions SET status = %s WHERE id = %s",
            (status, str(session_id)),
        )
        conn.commit()


def save_message(session_id: uuid.UUID | str, role: str, content: str) -> None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (%s, %s, %s)",
            (str(session_id), role, content),
        )
        conn.commit()


def load_messages(session_id: uuid.UUID | str) -> list[dict[str, str]]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at, id",
            (str(session_id),),
        )
        return [{"role": r[0], "content": r[1]} for r in cur.fetchall()]


def load_active_questions() -> list[dict[str, Any]]:
    """Active question backbone in priority order — read fresh from the DB."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT slot_key, category, text, framework_tag, tier, order_hint "
            "FROM questions WHERE active = true ORDER BY order_hint, slot_key"
        )
        cols = ("slot_key", "category", "text", "framework_tag", "tier", "order_hint")
        return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def compute_slot_state(session_id: uuid.UUID | str) -> dict[str, Any]:
    """Filled vs. unfilled slots for the session (authoritative, from the DB)."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT current_slot FROM sessions WHERE id = %s", (str(session_id),))
        row = cur.fetchone()
        current_slot = row[0] if row else None

        cur.execute(
            "SELECT DISTINCT slot_key, source FROM answers WHERE session_id = %s",
            (str(session_id),),
        )
        answer_rows = cur.fetchall()
        filled = {slot for (slot, _) in answer_rows}
        # Confirmed = the respondent (or a delegated colleague) actually said it;
        # slots filled only from the intake form / an uploaded document are
        # provisional — the agent confirms them in passing instead of re-asking.
        confirmed = {slot for (slot, source) in answer_rows if source not in PROVISIONAL_SOURCES}

        # Slots with a pending (unexpired, unanswered) email relay: a colleague
        # is answering them, so the agent must not re-ask the respondent.
        cur.execute(
            """
            SELECT DISTINCT slot_key FROM email_relays
            WHERE session_id = %s AND status = 'sent' AND expires_at > now()
            """,
            (str(session_id),),
        )
        delegated = {r[0] for r in cur.fetchall()} - filled

        cur.execute(
            "SELECT slot_key, tier FROM questions WHERE active = true ORDER BY order_hint, slot_key"
        )
        active = cur.fetchall()

    skip = filled | delegated
    unfilled_must_fill = [s for (s, tier) in active if tier == "must_fill" and s not in skip]
    unfilled_nice = [s for (s, tier) in active if tier == "nice_to_have" and s not in skip]
    return {
        "filled": sorted(filled),
        "provisional": sorted(filled - confirmed),
        "delegated": sorted(delegated),
        "unfilled_must_fill": unfilled_must_fill,
        "unfilled_nice_to_have": unfilled_nice,
        "current_slot": current_slot,
    }


def get_session_company_context(session_id: uuid.UUID | str) -> dict[str, Any] | None:
    """Company + respondent firmographics for the known-context prompt block."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.name, c.industry, c.headcount_band, c.revenue_band, c.years_in_business,
                   r.name, r.role
            FROM sessions s
            JOIN companies c ON c.id = s.company_id
            LEFT JOIN respondents r ON r.id = s.respondent_id
            WHERE s.id = %s
            """,
            (str(session_id),),
        )
        row = cur.fetchone()
    if row is None:
        return None
    keys = (
        "company_name",
        "industry",
        "headcount_band",
        "revenue_band",
        "years_in_business",
        "respondent_name",
        "respondent_role",
    )
    return dict(zip(keys, row, strict=True))
