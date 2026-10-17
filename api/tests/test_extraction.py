"""Extraction (call B): a user turn -> typed answers rows; coverage gating."""

from __future__ import annotations

import psycopg
from fastapi.testclient import TestClient

from api import coverage, openai_client
from api.answers_repo import save_answer
from api.main import app
from playbook_shared.extraction_schemas import ExtractedSlot, TurnExtraction
from playbook_shared.question_bank import load_bank

client = TestClient(app)


def _answers(url: str, session_id: str) -> dict[str, dict]:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT slot_key, structured_json, confidence, source FROM answers WHERE session_id = %s",
            (str(session_id),),
        )
        return {
            r[0]: {"structured_json": r[1], "confidence": r[2], "source": r[3]}
            for r in cur.fetchall()
        }


def _mock_openai(monkeypatch, extractions):
    async def fake_parse(messages):
        return TurnExtraction(extractions=extractions)

    async def fake_stream(messages):
        yield "ok"

    monkeypatch.setattr(openai_client, "parse_extraction", fake_parse)
    monkeypatch.setattr(openai_client, "stream_chat", fake_stream)


def test_extraction_writes_typed_answers(chat_db, monkeypatch):
    _mock_openai(
        monkeypatch,
        [
            ExtractedSlot(slot_key="ctx.role", value="Controller", confidence=0.92),
            ExtractedSlot(slot_key="close.days", value="12 days", confidence=0.8),
        ],
    )
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"message": "I'm the controller; close takes 12 days"})

    answers = _answers(chat_db, session_id)
    assert answers["ctx.role"]["structured_json"] == {"value": "Controller"}
    assert answers["ctx.role"]["source"] == "chat"
    assert answers["close.days"]["structured_json"] == {"value": "12 days"}


def test_low_confidence_is_flagged(chat_db, monkeypatch):
    _mock_openai(monkeypatch, [ExtractedSlot(slot_key="ctx.role", value="maybe a controller", confidence=0.25)])
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"message": "kind of run finance I guess"})
    assert _answers(chat_db, session_id)["ctx.role"]["confidence"] == 0.25


def test_reextraction_upserts_no_duplicates(chat_db, monkeypatch):
    session_id = client.post("/sessions").json()["id"]
    _mock_openai(monkeypatch, [ExtractedSlot(slot_key="ctx.role", value="Controller", confidence=0.5)])
    client.post(f"/sessions/{session_id}/messages", json={"message": "I'm the controller"})
    _mock_openai(monkeypatch, [ExtractedSlot(slot_key="ctx.role", value="FP&A Director", confidence=0.9)])
    client.post(f"/sessions/{session_id}/messages", json={"message": "actually FP&A Director"})

    answers = _answers(chat_db, session_id)
    assert answers["ctx.role"]["structured_json"] == {"value": "FP&A Director"}  # updated in place
    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM answers WHERE session_id = %s AND slot_key = 'ctx.role'", (session_id,))
        assert cur.fetchone()[0] == 1


def test_hallucinated_slot_keys_are_ignored(chat_db, monkeypatch):
    _mock_openai(monkeypatch, [ExtractedSlot(slot_key="not.a.real.slot", value="x", confidence=0.9)])
    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"message": "hi"})
    assert "not.a.real.slot" not in _answers(chat_db, session_id)


def test_provisional_fills_count_but_do_not_complete(chat_db):
    """Intake/document fills advance the progress bar but can't complete a session."""
    session_id = client.post("/sessions").json()["id"]
    must_fill = [q.slot_key for q in load_bank().must_fill]

    for slot_key in must_fill:
        save_answer(session_id, slot_key, "x", {"value": "x"}, 0.9, "intake")
    cov = coverage.coverage(session_id)
    assert cov["filled_must_fill"] == cov["total_must_fill"]
    assert cov["complete_ready"] is False
    assert coverage.try_complete(session_id) is False

    # The respondent confirms each in chat -> now completable.
    for slot_key in must_fill:
        save_answer(session_id, slot_key, "x", {"value": "x"}, 0.9, "chat")
    assert coverage.try_complete(session_id) is True


def test_chat_answer_confirms_provisional_slot(chat_db):
    from api import repo

    session_id = client.post("/sessions").json()["id"]
    save_answer(session_id, "ctx.role", "Controller", {"value": "Controller"}, 1.0, "intake")
    assert repo.compute_slot_state(session_id)["provisional"] == ["ctx.role"]

    save_answer(session_id, "ctx.role", "Controller", {"value": "Controller"}, 0.9, "chat")
    state = repo.compute_slot_state(session_id)
    assert state["provisional"] == []
    assert "ctx.role" in state["filled"]


def test_coverage_gate_blocks_complete_until_all_must_fill(chat_db):
    session_id = client.post("/sessions").json()["id"]
    must_fill = [q.slot_key for q in load_bank().must_fill]

    # Fill all but one must_fill slot.
    for slot_key in must_fill[:-1]:
        save_answer(session_id, slot_key, "x", {"value": "x"}, 0.9)
    assert coverage.try_complete(session_id) is False

    # Fill the last one -> now completable.
    save_answer(session_id, must_fill[-1], "x", {"value": "x"}, 0.9)
    assert coverage.try_complete(session_id) is True

    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM sessions WHERE id = %s", (session_id,))
        assert cur.fetchone()[0] == "complete"
