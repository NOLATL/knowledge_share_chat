from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi.testclient import TestClient

from api import email_sender, openai_client, repo
from api.main import app

client = TestClient(app)


def _session_id() -> str:
    return client.post("/sessions").json()["id"]


def test_relay_options_reject_unknown_session(chat_db):
    resp = client.get(f"/sessions/{uuid.uuid4()}/relays/options")
    assert resp.status_code == 404


def test_create_relay_writes_row_and_sends_link(chat_db, monkeypatch):
    session_id = _session_id()
    sent = {}

    def fake_send(*, to_email, relay_url, question_text, context_text=""):
        sent.update({"to": to_email, "url": relay_url, "question": question_text, "context": context_text})
        return email_sender.EmailResult(delivered=True, provider="test", message="sent")

    monkeypatch.setenv("PUBLIC_WEB_BASE_URL", "https://web.example")
    monkeypatch.setattr(email_sender, "send_relay_email", fake_send)

    resp = client.post(
        f"/sessions/{session_id}/relays",
        json={"slot_key": "close.days", "sent_to_email": "peer@example.com"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["email_delivered"] is True
    assert body["relay_url"].startswith("https://web.example/relay/")
    assert sent["to"] == "peer@example.com"
    assert "month-end close" in sent["question"]

    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute("SELECT slot_key, sent_to_email, status FROM email_relays WHERE token = %s", (body["token"],))
        row = cur.fetchone()
    assert row == ("close.days", "peer@example.com", "sent")


def test_submit_relay_answer_writes_email_source_and_closes_token(chat_db, monkeypatch):
    session_id = _session_id()
    monkeypatch.setattr(
        email_sender,
        "send_relay_email",
        lambda **_: email_sender.EmailResult(delivered=True, provider="test", message="ok"),
    )
    token = client.post(
        f"/sessions/{session_id}/relays",
        json={"slot_key": "pain.manual_hours", "sent_to_email": "peer@example.com"},
    ).json()["token"]

    resp = client.post(f"/relays/{token}/answer", json={"reply_text": "We spend 80 hours per month."})
    assert resp.status_code == 200
    assert resp.json()["status"] == "answered"

    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT structured_json, source
            FROM answers
            WHERE session_id = %s AND slot_key = 'pain.manual_hours'
            """,
            (session_id,),
        )
        answer = cur.fetchone()
        cur.execute("SELECT status, reply_text FROM email_relays WHERE token = %s", (token,))
        relay = cur.fetchone()

    assert answer == ({"value": "We spend 80 hours per month."}, "email")
    assert relay == ("answered", "We spend 80 hours per month.")

    second = client.post(f"/relays/{token}/answer", json={"reply_text": "second answer"})
    assert second.status_code == 409


def test_relay_without_slot_key_uses_current_question(chat_db, monkeypatch):
    """Omitting slot_key resolves the session's current question server-side."""
    session_id = _session_id()
    monkeypatch.setattr(
        email_sender,
        "send_relay_email",
        lambda **_: email_sender.EmailResult(delivered=True, provider="test", message="ok"),
    )

    resp = client.post(f"/sessions/{session_id}/relays", json={"sent_to_email": "peer@example.com"})
    assert resp.status_code == 200

    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT slot_key FROM questions WHERE active = true AND tier = 'must_fill' "
            "ORDER BY order_hint, slot_key LIMIT 1"
        )
        expected_slot = cur.fetchone()[0]
    assert resp.json()["slot_key"] == expected_slot


def test_relay_context_generated_and_emailed(chat_db, monkeypatch):
    session_id = _session_id()
    sent = {}

    def fake_send(*, to_email, relay_url, question_text, context_text=""):
        sent["context"] = context_text
        return email_sender.EmailResult(delivered=True, provider="test", message="sent")

    async def fake_complete(messages):
        return "Include how many business days the close takes and the long pole."

    monkeypatch.setattr(email_sender, "send_relay_email", fake_send)
    monkeypatch.setattr(openai_client, "complete_report", fake_complete)

    resp = client.post(
        f"/sessions/{session_id}/relays",
        json={"slot_key": "close.days", "sent_to_email": "peer@example.com"},
    )
    assert resp.status_code == 200
    assert "business days" in sent["context"]

    token = resp.json()["token"]
    relay = client.get(f"/relays/{token}").json()
    assert "business days" in relay["context_text"]


def test_relay_uses_agents_actual_question(chat_db, monkeypatch):
    """asked_question -> the email + landing page show the real chat question
    (cleaned to stand alone), not the scripted template."""
    session_id = _session_id()
    sent = {}

    def fake_send(*, to_email, relay_url, question_text, context_text=""):
        sent["question"] = question_text
        return email_sender.EmailResult(delivered=True, provider="test", message="ok")

    async def fake_complete(messages):
        if "standalone question" in messages[0]["content"]:
            return "How many business days does your month-end close take, end to end?"
        return "Context: include the number of business days and the biggest bottleneck."

    monkeypatch.setattr(email_sender, "send_relay_email", fake_send)
    monkeypatch.setattr(openai_client, "complete_report", fake_complete)

    resp = client.post(
        f"/sessions/{session_id}/relays",
        json={
            "slot_key": "close.days",
            "sent_to_email": "peer@example.com",
            "asked_question": "Great, thanks! So roughly how long does closing the books take you each month?",
        },
    )
    assert resp.status_code == 200
    # The email carries the cleaned real question, not the scripted template.
    assert sent["question"] == "How many business days does your month-end close take, end to end?"

    token = resp.json()["token"]
    relay = client.get(f"/relays/{token}").json()
    assert relay["question_text"] == "How many business days does your month-end close take, end to end?"


def test_pending_relay_marks_slot_delegated(chat_db, monkeypatch):
    """A slot awaiting a colleague's reply leaves the unfilled list so the agent moves on."""
    session_id = _session_id()
    monkeypatch.setattr(
        email_sender,
        "send_relay_email",
        lambda **_: email_sender.EmailResult(delivered=True, provider="test", message="ok"),
    )
    client.post(
        f"/sessions/{session_id}/relays",
        json={"slot_key": "close.days", "sent_to_email": "peer@example.com"},
    )

    state = repo.compute_slot_state(session_id)
    assert "close.days" in state["delegated"]
    assert "close.days" not in state["unfilled_must_fill"]


def test_relay_answer_is_woven_into_chat_history(chat_db, monkeypatch):
    session_id = _session_id()
    monkeypatch.setattr(
        email_sender,
        "send_relay_email",
        lambda **_: email_sender.EmailResult(delivered=True, provider="test", message="ok"),
    )
    token = client.post(
        f"/sessions/{session_id}/relays",
        json={"slot_key": "close.days", "sent_to_email": "peer@example.com"},
    ).json()["token"]

    client.post(f"/relays/{token}/answer", json={"reply_text": "Close takes 9 business days."})

    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT content FROM messages WHERE session_id = %s AND role = 'user'",
            (session_id,),
        )
        contents = [r[0] for r in cur.fetchall()]
    woven = [c for c in contents if "peer@example.com" in c]
    assert woven and "Close takes 9 business days." in woven[0]

    # And the slot is no longer delegated once answered — it is filled.
    state = repo.compute_slot_state(session_id)
    assert "close.days" in state["filled"]
    assert "close.days" not in state["delegated"]


def test_failed_delivery_returns_502_and_removes_relay(chat_db, monkeypatch):
    """A real provider refusing the email must not silently delegate the slot."""
    session_id = _session_id()
    monkeypatch.setattr(
        email_sender,
        "send_relay_email",
        lambda **_: email_sender.EmailResult(
            delivered=False,
            provider="resend",
            message="HTTP 403: You can only send testing emails to your own email address",
        ),
    )

    resp = client.post(
        f"/sessions/{session_id}/relays",
        json={"slot_key": "close.days", "sent_to_email": "someone.else@example.com"},
    )
    assert resp.status_code == 502
    assert "only send testing emails" in resp.json()["detail"]

    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM email_relays WHERE session_id = %s", (session_id,))
        assert cur.fetchone()[0] == 0
    state = repo.compute_slot_state(session_id)
    assert "close.days" not in state["delegated"]


def test_expired_relay_cannot_be_answered(chat_db):
    session_id = _session_id()
    token = uuid.uuid4()
    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO email_relays (session_id, slot_key, token, sent_to_email, expires_at)
            VALUES (%s, 'close.days', %s, 'peer@example.com', %s)
            """,
            (session_id, token, datetime.now(timezone.utc) - timedelta(minutes=1)),
        )
        conn.commit()

    resp = client.post(f"/relays/{token}/answer", json={"reply_text": "late"})
    assert resp.status_code == 410

    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM email_relays WHERE token = %s", (token,))
        status = cur.fetchone()[0]
    assert status == "expired"
