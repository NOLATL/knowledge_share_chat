"""Coverage: a session may not be 'complete' until all must_fill slots are filled."""

from __future__ import annotations

import uuid
from typing import Any

from playbook_shared.db import connect

from api.answers_repo import PROVISIONAL_SOURCES


def _conn():
    return connect(register_vector_types=False)


def coverage(session_id: uuid.UUID | str) -> dict[str, Any]:
    """Filled vs. total active must_fill slots for the session.

    The progress count includes provisional (intake/document) fills so the bar
    feels responsive, but a session is only complete_ready once every must_fill
    slot has a respondent-confirmed (non-provisional) answer.
    """
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT slot_key FROM questions WHERE active = true AND tier = 'must_fill'")
        must = {r[0] for r in cur.fetchall()}
        cur.execute("SELECT DISTINCT slot_key, source FROM answers WHERE session_id = %s", (str(session_id),))
        rows = cur.fetchall()
    filled = {slot for (slot, _) in rows}
    confirmed = {slot for (slot, source) in rows if source not in PROVISIONAL_SOURCES}
    return {
        "filled_must_fill": len(must & filled),
        "total_must_fill": len(must),
        "complete_ready": len(must) > 0 and must <= confirmed,
    }


def try_complete(session_id: uuid.UUID | str) -> bool:
    """Transition to 'complete' ONLY if every must_fill slot is filled."""
    if not coverage(session_id)["complete_ready"]:
        return False
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE sessions SET status = 'complete', completed_at = now() WHERE id = %s",
            (str(session_id),),
        )
        conn.commit()
    return True
