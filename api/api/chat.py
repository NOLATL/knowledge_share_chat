"""Streamed assistant turn — the two-call pattern's call A (GR2).

Persists the user message, assembles the system prompt from the editable template
+ authoritative DB state, streams the assistant reply (gpt-5.4-mini), and persists
the finalized assistant message when the stream completes. Structured extraction
(call B) is Task 1.3.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api import document_rag, extraction, openai_client, repo
from api.prompt import build_system_prompt, render_known_context

logger = logging.getLogger(__name__)
router = APIRouter()

_HISTORY_ROLES = ("user", "assistant")


class MessageIn(BaseModel):
    message: str


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _build_chat_messages(session_id: uuid.UUID, latest_user_message: str) -> list[dict[str, str]]:
    history = await run_in_threadpool(repo.load_messages, session_id)
    questions = await run_in_threadpool(repo.load_active_questions)
    slot_state = await run_in_threadpool(repo.compute_slot_state, session_id)

    # Use recent conversation thread for retrieval so handbook context stays
    # relevant to what was actually just said, not just the next slot to fill.
    recent_ctx = "\n".join(m["content"] for m in history[-4:] if m["role"] in _HISTORY_ROLES)
    rag_query = recent_ctx or latest_user_message

    document_context = await run_in_threadpool(
        document_rag.retrieve_document_context,
        session_id,
        rag_query,
    )
    handbook_context = await run_in_threadpool(document_rag.retrieve_handbook_context, rag_query)
    company_ctx = await run_in_threadpool(repo.get_session_company_context, session_id)
    system = build_system_prompt(
        slot_state,
        questions,
        known_context=render_known_context(company_ctx),
        document_context=document_context,
        handbook_context=handbook_context,
    )

    chat_messages = [{"role": "system", "content": system}]
    chat_messages += [m for m in history if m["role"] in _HISTORY_ROLES]
    return chat_messages


@router.post("/sessions/{session_id}/messages")
async def post_message(session_id: uuid.UUID, body: MessageIn) -> StreamingResponse:
    session = await run_in_threadpool(repo.get_session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    # Persist the user message immediately (so it survives a dropped stream).
    await run_in_threadpool(repo.save_message, session_id, "user", body.message)

    # Call B (separate, non-streamed): extract typed answers before replying so
    # slot state is fresh. Best-effort — a failed extraction must not break the
    # streamed reply.
    try:
        await extraction.extract_and_save(session_id, body.message)
    except Exception:  # noqa: BLE001 - extraction is best-effort
        logger.exception("extraction failed for session %s", session_id)

    chat_messages = await _build_chat_messages(session_id, body.message)

    async def generate() -> AsyncIterator[str]:
        parts: list[str] = []
        async for delta in openai_client.stream_chat(chat_messages):
            parts.append(delta)
            yield _sse({"type": "text-delta", "delta": delta})
        assistant_text = "".join(parts)
        await run_in_threadpool(repo.save_message, session_id, "assistant", assistant_text)
        yield _sse({"type": "done"})

    return StreamingResponse(generate(), media_type="text/event-stream")
