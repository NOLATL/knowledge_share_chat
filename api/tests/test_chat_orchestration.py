"""Chat orchestration: session creation, DB-driven questions, streaming, persistence."""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest
import yaml
from fastapi.testclient import TestClient

from api import openai_client
from api.main import app
from playbook_shared.question_bank import get_active_version, reseed_questions

client = TestClient(app)


def _db_messages(url: str, session_id: str) -> list[tuple[str, str]]:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at, id",
            (str(session_id),),
        )
        return cur.fetchall()


def _fake_stream(captured: dict, deltas: list[str]):
    async def fake(messages):
        captured["messages"] = messages
        for d in deltas:
            yield d

    return fake


INTAKE = {
    "name": "Northwind Foods",
    "industry": "CPG",
    "headcount_band": "201-1000",
    "revenue_band": "$50-250M",
    "years_in_business": 15,
    "respondent_name": "Jane Doe",
    "respondent_role": "Controller",
}


def _mock_intro(monkeypatch, reply="Hi Jane, welcome!"):
    """Stub the non-streamed intro call; captures the messages it was sent."""
    captured: dict = {}

    async def fake(messages):
        captured["messages"] = messages
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(openai_client, "complete_chat", fake)
    return captured


def test_post_session_returns_id_and_records_version(chat_db):
    resp = client.post("/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] and body["resume_token"]
    assert body["script_version"] == get_active_version()


def test_post_session_with_company_intake_links_real_company(chat_db, monkeypatch):
    _mock_intro(monkeypatch)
    resp = client.post("/sessions", json={"company": INTAKE})
    assert resp.status_code == 200
    session_id = resp.json()["id"]
    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT c.name, c.industry, c.headcount_band, c.revenue_band, c.years_in_business "
            "FROM sessions s JOIN companies c ON c.id = s.company_id WHERE s.id = %s",
            (session_id,),
        )
        assert cur.fetchone() == ("Northwind Foods", "CPG", "201-1000", "$50-250M", 15)


def test_intake_seeds_provisional_slot_answers(chat_db, monkeypatch):
    _mock_intro(monkeypatch)
    session_id = client.post("/sessions", json={"company": INTAKE}).json()["id"]

    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT slot_key, raw_text, source FROM answers WHERE session_id = %s ORDER BY slot_key",
            (session_id,),
        )
        rows = cur.fetchall()
    assert ("ctx.role", "Controller", "intake") in rows
    profile = next(r for r in rows if r[0] == "ctx.company_profile")
    assert profile[2] == "intake"
    assert "industry: CPG" in profile[1] and "years in business: 15" in profile[1]

    # Progress counts intake fills, but they can't complete a session.
    cov = client.get(f"/sessions/{session_id}/coverage").json()
    assert cov["filled_must_fill"] == 2
    assert cov["complete_ready"] is False


def test_intake_intro_is_generated_and_saved(chat_db, monkeypatch):
    captured = _mock_intro(monkeypatch, reply="Hi Jane! Northwind intro.")
    resp = client.post("/sessions", json={"company": INTAKE})
    assert resp.json()["initial_message"] == "Hi Jane! Northwind intro."

    # The intro prompt carries the intake summary and the first open question.
    user_content = captured["messages"][1]["content"]
    assert "Northwind Foods" in user_content
    assert "Jane Doe (Controller)" in user_content
    # ctx.role and ctx.company_profile are pre-filled, so the first open
    # question is the next must_fill: month-end close.
    assert "month-end close" in user_content

    rows = _db_messages(chat_db, resp.json()["id"])
    assert rows[0] == ("assistant", "Hi Jane! Northwind intro.")


def test_intro_failure_falls_back_to_static_welcome(chat_db, monkeypatch):
    from api.sessions import WELCOME_MESSAGE

    _mock_intro(monkeypatch, reply=RuntimeError("api down"))
    resp = client.post("/sessions", json={"company": INTAKE})
    assert resp.status_code == 200
    assert resp.json()["initial_message"] == WELCOME_MESSAGE


def test_no_intake_session_uses_static_welcome_without_llm(chat_db, monkeypatch):
    from api.sessions import WELCOME_MESSAGE

    async def boom(messages):  # pragma: no cover - must not be called
        raise AssertionError("no-intake session must not call the LLM")

    monkeypatch.setattr(openai_client, "complete_chat", boom)
    resp = client.post("/sessions")
    assert resp.json()["initial_message"] == WELCOME_MESSAGE


def test_system_prompt_carries_known_context_and_provisional(chat_db, monkeypatch):
    _mock_intro(monkeypatch)
    captured: dict = {}
    monkeypatch.setattr(openai_client, "stream_chat", _fake_stream(captured, ["ok"]))

    session_id = client.post("/sessions", json={"company": INTAKE}).json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"message": "hello"})

    system = captured["messages"][0]["content"]
    assert "Known context from the intake form" in system
    assert "Company: Northwind Foods" in system
    assert "Respondent: Jane Doe (Controller)" in system
    # Intake-seeded slots surface as provisional in the slot state.
    assert '"provisional"' in system
    from api import repo

    state = repo.compute_slot_state(session_id)
    assert state["provisional"] == ["ctx.company_profile", "ctx.role"]


def test_message_streams_and_persists(chat_db, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(openai_client, "stream_chat", _fake_stream(captured, ["Hello", " there"]))

    session_id = client.post("/sessions").json()["id"]
    resp = client.post(f"/sessions/{session_id}/messages", json={"message": "Hi, I run finance"})

    assert resp.status_code == 200
    assert "text-delta" in resp.text and "Hello" in resp.text and '"done"' in resp.text

    rows = _db_messages(chat_db, session_id)
    assert ("user", "Hi, I run finance") in rows
    assert ("assistant", "Hello there") in rows


def test_system_prompt_has_vendor_rule_and_db_questions(chat_db, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(openai_client, "stream_chat", _fake_stream(captured, ["ok"]))

    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"message": "hello"})

    system = captured["messages"][0]
    assert system["role"] == "system"
    assert "vendor-agnostic" in system["content"].lower()
    assert "close.days" in system["content"]  # backbone read from the DB


def test_questions_change_from_db_without_redeploy(chat_db, monkeypatch, tmp_path):
    # Reseed a different bank; the next session's prompt must reflect the DB.
    bank = tmp_path / "b.yaml"
    bank.write_text(
        yaml.safe_dump(
            {
                "version": "x.1",
                "questions": [
                    {
                        "slot_key": "custom.only",
                        "category": "A",
                        "text": "a custom question",
                        "framework_tag": "SPIN-Situation",
                        "tier": "must_fill",
                        "order_hint": 10,
                        "active": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    reseed_questions(chat_db, bank)

    captured: dict = {}
    monkeypatch.setattr(openai_client, "stream_chat", _fake_stream(captured, ["ok"]))
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"message": "hello"})

    system = captured["messages"][0]["content"]
    assert "custom.only" in system  # new bank picked up at runtime
    assert "close.days" not in system  # retired slot no longer offered


def test_one_question_at_a_time_rule_present(chat_db, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(openai_client, "stream_chat", _fake_stream(captured, ["ok"]))
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"message": "hi"})
    assert "one question at a time" in captured["messages"][0]["content"].lower()


def test_message_to_unknown_session_404(chat_db):
    resp = client.post(f"/sessions/{uuid.uuid4()}/messages", json={"message": "hi"})
    assert resp.status_code == 404


def test_coverage_endpoint(chat_db):
    session_id = client.post("/sessions").json()["id"]
    resp = client.get(f"/sessions/{session_id}/coverage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_must_fill"] >= 12
    assert body["filled_must_fill"] == 0
    assert body["complete_ready"] is False


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OPENAI") != "1",
    reason="opt-in live OpenAI behavioral check (needs OPENAI_API_KEY + valid model)",
)
def test_spin_implication_followup_live(chat_db):
    """Scripted transcript against the real model: a pain mention -> a follow-up question."""
    session_id = client.post("/sessions").json()["id"]
    resp = client.post(
        f"/sessions/{session_id}/messages",
        json={
            "message": (
                "Our month-end close takes 12 days and reconciliations are painful — "
                "tons of manual spreadsheet work and frequent errors."
            )
        },
    )
    assert resp.status_code == 200
    rows = _db_messages(chat_db, session_id)
    # Last assistant row: the first is now the canned session welcome message.
    assistant = [c for (r, c) in rows if r == "assistant"][-1]
    assert "?" in assistant  # it asks a follow-up
