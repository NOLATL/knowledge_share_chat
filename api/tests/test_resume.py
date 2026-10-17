"""Save / resume: magic-link restore, recap, and status transitions (Task 1.5)."""

from __future__ import annotations

import uuid

import psycopg
from fastapi.testclient import TestClient

from api.answers_repo import save_answer
from api.main import app

client = TestClient(app)


def _status(url: str, session_id: str) -> str:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM sessions WHERE id = %s", (str(session_id),))
        return cur.fetchone()[0]


def test_resume_restores_state_recap_and_status_transitions(chat_db):
    created = client.post("/sessions").json()
    session_id, token = created["id"], created["resume_token"]
    assert _status(chat_db, session_id) == "in_progress"

    # Some history + a filled slot.
    save_answer(session_id, "ctx.role", "Controller", {"value": "Controller"}, 0.9)

    # in_progress -> paused
    assert client.post(f"/sessions/{session_id}/pause").json()["status"] == "paused"
    assert _status(chat_db, session_id) == "paused"

    # paused -> in_progress, with a recap + restored conversation
    resumed = client.get(f"/sessions/by-token/{token}").json()
    resumed_again = client.get(f"/sessions/by-token/{token}").json()
    assert resumed["status"] == "in_progress"
    assert resumed["resume_token"] == token
    assert _status(chat_db, session_id) == "in_progress"

    assert "Your role" in resumed["recap"]  # covered slot named
    assert "Company size" in resumed["recap"]  # next must_fill named
    assert resumed_again["recap"] == resumed["recap"]
    assert resumed_again["messages"] == resumed["messages"]
    assert resumed["coverage"]["filled_must_fill"] >= 1


def test_resume_unknown_token_404(chat_db):
    assert client.get(f"/sessions/by-token/{uuid.uuid4()}").status_code == 404
