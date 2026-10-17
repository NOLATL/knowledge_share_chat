"""Tokenized colleague answer relay endpoints."""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, field_validator

from api import answers_repo, email_sender, openai_client, relay_repo, repo

logger = logging.getLogger(__name__)
router = APIRouter()

_CONTEXT_INSTRUCTIONS = (
    "A respondent in a finance/accounting discovery interview is forwarding one "
    "question to a colleague by email. Write 2-3 short sentences of context for "
    "the colleague: what the question is trying to learn and what a complete "
    "answer includes (numbers, time spans, tool names, owners — whatever fits "
    "this question). Plain text only; no greeting, no signature, no markdown."
)

_QUESTION_INSTRUCTIONS = (
    "An interviewer in a finance/accounting discovery chat is forwarding the "
    "question they just asked to a colleague by email. Rewrite it as ONE clear, "
    "standalone question the colleague can answer without seeing the chat. Keep "
    "the interviewer's intent and any specifics; drop greetings, acknowledgements, "
    "and filler. Plain text, a single question, no preamble or quotes."
)


async def _recent_history(session_id: uuid.UUID) -> str:
    history = await run_in_threadpool(repo.load_messages, session_id)
    return "\n".join(
        f"{m['role']}: {m['content']}" for m in history[-6:] if m["role"] in ("user", "assistant")
    )


async def _standalone_question(session_id: uuid.UUID, canned_text: str, asked_text: str) -> str:
    """Clean the interviewer's actual last question into a self-contained one for
    the email. Falls back to the raw asked text on any failure."""
    try:
        recent = await _recent_history(session_id)
        messages = [
            {"role": "system", "content": _QUESTION_INSTRUCTIONS},
            {
                "role": "user",
                "content": (
                    f"Question just asked:\n{asked_text}\n\n"
                    f"Scripted version of this question (for reference): {canned_text}\n\n"
                    f"Recent conversation:\n{recent}"
                ),
            },
        ]
        cleaned = (await openai_client.complete_report(messages)).strip()
        return cleaned or asked_text
    except Exception:  # noqa: BLE001 - cleaning is best-effort, never block the relay
        logger.exception("relay question cleaning failed for session %s", session_id)
        return asked_text


async def _generate_context(session_id: uuid.UUID, question_text: str) -> str:
    """Best-effort slot context for the relay email; empty string on any failure."""
    try:
        recent = await _recent_history(session_id)
        messages = [
            {"role": "system", "content": _CONTEXT_INSTRUCTIONS},
            {"role": "user", "content": f"Question:\n{question_text}\n\nRecent conversation:\n{recent}"},
        ]
        return (await openai_client.complete_report(messages)).strip()
    except Exception:  # noqa: BLE001 - context is a nice-to-have, never block the relay
        logger.exception("relay context generation failed for session %s", session_id)
        return ""


class RelayQuestion(BaseModel):
    slot_key: str
    category: str
    text: str
    tier: str
    order_hint: int
    filled: bool


class RelayCreateIn(BaseModel):
    slot_key: str | None = None  # omitted -> the session's current question
    sent_to_email: str
    # The interviewer's actual last question in the chat; when present the email
    # reflects what was really asked instead of the scripted template.
    asked_question: str | None = None
    expires_in_hours: int | None = Field(default=None, ge=1, le=24 * 30)

    @field_validator("sent_to_email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        stripped = value.strip()
        if "@" not in stripped or stripped.startswith("@") or stripped.endswith("@"):
            raise ValueError("valid email is required")
        return stripped


class RelayCreateOut(BaseModel):
    id: uuid.UUID
    token: uuid.UUID
    session_id: uuid.UUID
    slot_key: str
    sent_to_email: str
    status: str
    relay_url: str
    email_provider: str
    email_delivered: bool
    email_message: str
    expires_at: str


class RelayOut(BaseModel):
    token: uuid.UUID
    slot_key: str
    question_text: str
    context_text: str = ""
    sent_to_email: str
    status: str
    expires_at: str
    expired: bool


class RelayAnswerIn(BaseModel):
    reply_text: str = Field(min_length=1, max_length=5000)


@router.get("/sessions/{session_id}/relays/options", response_model=list[RelayQuestion])
async def get_relay_options(session_id: uuid.UUID) -> list[RelayQuestion]:
    rows = await run_in_threadpool(relay_repo.active_questions_for_session, session_id)
    if rows is None:
        raise HTTPException(status_code=404, detail="session not found")
    return [RelayQuestion(**row) for row in rows]


@router.post("/sessions/{session_id}/relays", response_model=RelayCreateOut)
async def post_relay(session_id: uuid.UUID, body: RelayCreateIn) -> RelayCreateOut:
    expires_in_hours = body.expires_in_hours or int(os.environ.get("RELAY_EXPIRES_HOURS", "168"))
    try:
        resolved = await run_in_threadpool(relay_repo.resolve_relay_slot, session_id, body.slot_key)
        if resolved is None:
            raise HTTPException(status_code=404, detail="session not found")
        asked = (body.asked_question or "").strip()
        if asked:
            question_text = await _standalone_question(session_id, resolved["question_text"], asked)
        else:
            question_text = resolved["question_text"]
        context_text = await _generate_context(session_id, question_text)
        relay = await run_in_threadpool(
            relay_repo.create_relay,
            session_id=session_id,
            slot_key=resolved["slot_key"],
            sent_to_email=str(body.sent_to_email),
            expires_in_hours=expires_in_hours,
            context_text=context_text,
            asked_question_text=question_text if asked else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if relay is None:
        raise HTTPException(status_code=404, detail="session not found")

    relay_url = f"{email_sender.relay_base_url()}/relay/{relay['token']}"
    email_result = await run_in_threadpool(
        email_sender.send_relay_email,
        to_email=str(body.sent_to_email),
        relay_url=relay_url,
        question_text=relay["question_text"],
        context_text=relay["context_text"],
    )
    # A real provider refusing delivery is a hard failure: drop the relay so the
    # slot is not silently delegated, and tell the caller why. (The "log"
    # provider is the dev dry-run and proceeds.)
    if email_result.provider != "log" and not email_result.delivered:
        await run_in_threadpool(relay_repo.delete_relay, relay["token"])
        raise HTTPException(status_code=502, detail=f"email not delivered: {email_result.message}")
    return RelayCreateOut(
        id=relay["id"],
        token=relay["token"],
        session_id=relay["session_id"],
        slot_key=relay["slot_key"],
        sent_to_email=relay["sent_to_email"],
        status=relay["status"],
        relay_url=relay_url,
        email_provider=email_result.provider,
        email_delivered=email_result.delivered,
        email_message=email_result.message,
        expires_at=relay["expires_at"].isoformat(),
    )


@router.get("/relays/{token}", response_model=RelayOut)
async def get_relay(token: uuid.UUID) -> RelayOut:
    relay = await run_in_threadpool(relay_repo.get_relay_by_token, token)
    if relay is None:
        raise HTTPException(status_code=404, detail="relay not found")
    expired = not relay_repo.is_usable(relay) and relay["status"] == "sent"
    if expired:
        await run_in_threadpool(relay_repo.mark_expired, token)
        relay["status"] = "expired"
    return RelayOut(
        token=relay["token"],
        slot_key=relay["slot_key"],
        question_text=relay["question_text"],
        context_text=relay["context_text"],
        sent_to_email=relay["sent_to_email"],
        status=relay["status"],
        expires_at=relay["expires_at"].isoformat(),
        expired=expired,
    )


@router.post("/relays/{token}/answer")
async def post_relay_answer(token: uuid.UUID, body: RelayAnswerIn) -> dict[str, str]:
    relay = await run_in_threadpool(relay_repo.get_relay_by_token, token)
    if relay is None:
        raise HTTPException(status_code=404, detail="relay not found")
    if not relay_repo.is_usable(relay):
        if relay["status"] == "sent":
            await run_in_threadpool(relay_repo.mark_expired, token)
            raise HTTPException(status_code=410, detail="relay expired")
        raise HTTPException(status_code=409, detail=f"relay already {relay['status']}")

    reply_text = body.reply_text.strip()
    await run_in_threadpool(
        answers_repo.save_answer,
        relay["session_id"],
        relay["slot_key"],
        reply_text,
        {"value": reply_text},
        0.82,
        "email",
    )
    await run_in_threadpool(relay_repo.mark_answered, token, reply_text)
    # Weave the colleague's reply into the conversation so the agent can
    # reference it on the respondent's next turn.
    await run_in_threadpool(
        repo.save_message,
        relay["session_id"],
        "user",
        (
            f"[Emailed reply from {relay['sent_to_email']} regarding "
            f"\"{relay['question_text']}\"]: {reply_text}"
        ),
    )
    return {"status": "answered"}
