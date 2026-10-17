"""Handbook RAG: guidance reaches call A's prompt, clearly labeled, and never
leaks into call B (extraction) — the structural guard that keeps handbook text
out of `answers`."""

from __future__ import annotations

import psycopg
from fastapi.testclient import TestClient

from api import document_rag, openai_client
from api.main import app
from playbook_shared.extraction_schemas import TurnExtraction

client = TestClient(app)

HANDBOOK_MARKER = "intercompany elimination is the biggest consolidation challenge"


def _vector(value: float = 0.01) -> list[float]:
    return [value] * 1536


def _seed_handbook_chunk(db_url: str, text: str) -> None:
    vec = "[" + ",".join(str(v) for v in _vector()) + "]"
    with psycopg.connect(db_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO handbook_chunks (chunk_key, source_file, section, chunk_text, embedding, metadata)
            VALUES ('V2_R2R.md#0', 'V2_R2R.md', 'Consolidation', %s, %s::vector, '{}'::jsonb)
            """,
            (text, vec),
        )
        conn.commit()


def _capture_calls(monkeypatch) -> dict:
    captured: dict = {}

    async def fake_parse(messages):
        captured["extraction_messages"] = messages
        return TurnExtraction(extractions=[])

    async def fake_stream(messages):
        captured["chat_messages"] = messages
        yield "ok"

    monkeypatch.setattr(openai_client, "parse_extraction", fake_parse)
    monkeypatch.setattr(openai_client, "stream_chat", fake_stream)
    return captured


def test_handbook_context_injected_and_labeled(chat_db, monkeypatch):
    _seed_handbook_chunk(chat_db, HANDBOOK_MARKER)
    monkeypatch.setattr(document_rag, "embed_texts", lambda texts: [_vector()])
    captured = _capture_calls(monkeypatch)

    session_id = client.post("/sessions").json()["id"]
    resp = client.post(f"/sessions/{session_id}/messages", json={"message": "Our close is painful."})

    assert resp.status_code == 200
    system = captured["chat_messages"][0]["content"]
    assert "Internal handbook guidance" in system
    assert "NOT facts about this prospect" in system
    assert HANDBOOK_MARKER in system
    assert "V2_R2R.md — Consolidation" in system


def test_handbook_block_absent_when_corpus_empty(chat_db, monkeypatch):
    captured = _capture_calls(monkeypatch)

    session_id = client.post("/sessions").json()["id"]
    resp = client.post(f"/sessions/{session_id}/messages", json={"message": "Hello."})

    assert resp.status_code == 200
    assert "Internal handbook guidance" not in captured["chat_messages"][0]["content"]


def test_handbook_text_never_reaches_extraction_call(chat_db, monkeypatch):
    _seed_handbook_chunk(chat_db, HANDBOOK_MARKER)
    monkeypatch.setattr(document_rag, "embed_texts", lambda texts: [_vector()])
    captured = _capture_calls(monkeypatch)

    session_id = client.post("/sessions").json()["id"]
    client.post(f"/sessions/{session_id}/messages", json={"message": "Our close is painful."})

    extraction_text = " ".join(m["content"] for m in captured["extraction_messages"])
    assert HANDBOOK_MARKER not in extraction_text
