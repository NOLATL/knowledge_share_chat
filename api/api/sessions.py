"""Session lifecycle endpoints."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from playbook_shared.sessions import CompanyIntake, create_session

from api import answers_repo, openai_client
from api import coverage as coverage_mod
from api import recap as recap_mod
from api import repo
from api.prompt import render_known_context

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = (
    "Welcome! I look forward to learning more about your organization. "
    "We will be discussing the people, processes, and technology supporting "
    "your accounting and finance functions."
)

_INTRO_INSTRUCTIONS = (
    "You are a sharp, friendly discovery consultant opening a conversation with a "
    "finance/accounting leader. Using the intake details below, write a short opening "
    "message (4-6 sentences, no headings or lists) that:\n"
    "- greets the respondent by name if known and reflects back what the intake form "
    "told us about their company, tailored to them (not a canned line);\n"
    "- explains the goal: understanding the people, processes, and technology behind "
    "their accounting and finance functions so we can benchmark them against peers and "
    "build a tailored roadmap;\n"
    "- mentions you'll double-check the details they've already provided as they come up;\n"
    "- ends by asking ONLY the first question given below, phrased naturally.\n"
    "One question only. Never recommend specific vendors or products."
)

router = APIRouter()


def seed_intake_answers(session_id: uuid.UUID | str, intake: CompanyIntake) -> None:
    """Pre-fill slots the intake form already answered (source='intake', provisional)."""
    if intake.respondent_role:
        answers_repo.save_answer(
            session_id,
            "ctx.role",
            intake.respondent_role,
            {"value": intake.respondent_role},
            1.0,
            "intake",
        )
    profile_bits = [
        f"{label}: {value}"
        for label, value in (
            ("industry", intake.industry),
            ("headcount", intake.headcount_band),
            ("annual revenue", intake.revenue_band),
            ("years in business", intake.years_in_business),
        )
        if value is not None and value != ""
    ]
    if profile_bits:
        profile = "; ".join(profile_bits)
        answers_repo.save_answer(
            session_id,
            "ctx.company_profile",
            profile,
            {"value": profile},
            1.0,
            "intake",
        )


async def _generate_intro(session_id: uuid.UUID) -> str:
    """LLM-tailored opening: summarizes the intake, sets expectations, asks question 1."""
    company_ctx = await run_in_threadpool(repo.get_session_company_context, session_id)
    state = await run_in_threadpool(repo.compute_slot_state, session_id)
    questions = await run_in_threadpool(repo.load_active_questions)
    by_key = {q["slot_key"]: q for q in questions}
    next_keys = state["unfilled_must_fill"]
    first_question = (
        by_key[next_keys[0]]["text"]
        if next_keys and next_keys[0] in by_key
        else "An open-ended invitation to describe how their finance team works today."
    )
    user_content = (
        f"Intake details:\n{render_known_context(company_ctx) or '(none provided)'}\n\n"
        f"First question to ask: {first_question}"
    )
    intro = await openai_client.complete_chat(
        [
            {"role": "system", "content": _INTRO_INSTRUCTIONS},
            {"role": "user", "content": user_content},
        ]
    )
    return intro.strip() or WELCOME_MESSAGE


class CompanyIntakeIn(BaseModel):
    name: str
    industry: str | None = None
    size_bucket: str | None = None
    headcount_band: str | None = None
    revenue_band: str | None = None
    years_in_business: int | None = None
    respondent_name: str | None = None
    respondent_role: str | None = None
    respondent_email: str | None = None
    function_key: str | None = None


class SessionCreate(BaseModel):
    company_id: uuid.UUID | None = None
    respondent_id: uuid.UUID | None = None
    company: CompanyIntakeIn | None = None


class SessionOut(BaseModel):
    id: uuid.UUID
    resume_token: uuid.UUID
    script_version: str | None
    initial_message: str | None = None


@router.post("/sessions", response_model=SessionOut)
async def post_session(body: SessionCreate | None = None) -> SessionOut:
    body = body or SessionCreate()
    intake = CompanyIntake(**body.company.model_dump()) if body.company else None
    session_id = await run_in_threadpool(
        create_session,
        company_id=body.company_id,
        respondent_id=body.respondent_id,
        company=intake,
    )
    initial_message = WELCOME_MESSAGE
    if intake is not None:
        await run_in_threadpool(seed_intake_answers, session_id, intake)
        try:
            initial_message = await _generate_intro(session_id)
        except Exception:  # noqa: BLE001 - intro is best-effort; fall back to static
            logger.exception("intro generation failed for session %s", session_id)
    await run_in_threadpool(repo.save_message, session_id, "assistant", initial_message)
    session = await run_in_threadpool(repo.get_session, session_id)
    if session is None:  # pragma: no cover - just-created row must exist
        raise HTTPException(status_code=500, detail="session not found after create")
    return SessionOut(
        id=session["id"],
        resume_token=session["resume_token"],
        script_version=session["script_version"],
        initial_message=initial_message,
    )


@router.get("/sessions/{session_id}/coverage")
async def get_coverage(session_id: uuid.UUID) -> dict:
    session = await run_in_threadpool(repo.get_session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    return await run_in_threadpool(coverage_mod.coverage, session_id)


@router.post("/sessions/{session_id}/pause")
async def pause_session(session_id: uuid.UUID) -> dict:
    session = await run_in_threadpool(repo.get_session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    if session["status"] == "in_progress":
        await run_in_threadpool(repo.set_status, session_id, "paused")
    return {"status": "paused"}


@router.get("/sessions/by-token/{resume_token}")
async def resume_session(resume_token: uuid.UUID) -> dict:
    """Magic-link resume: restore conversation + slot state, open with a recap."""
    session = await run_in_threadpool(repo.get_session_by_token, resume_token)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    session_id = session["id"]
    if session["status"] == "paused":
        await run_in_threadpool(repo.set_status, session_id, "in_progress")

    recap = await run_in_threadpool(recap_mod.build_recap, session_id)
    messages = await run_in_threadpool(repo.load_messages, session_id)
    cov = await run_in_threadpool(coverage_mod.coverage, session_id)
    return {
        "id": session_id,
        "resume_token": session["resume_token"],
        "status": "in_progress",
        "recap": recap,
        "messages": messages,
        "coverage": cov,
    }
