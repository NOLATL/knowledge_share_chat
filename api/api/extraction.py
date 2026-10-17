"""Structured extraction (GR2 call B): a user turn -> typed `answers` rows.

Runs a separate, non-streamed Structured Outputs call after each user message,
writes the addressed slots to `answers` (source='chat'), and advances
`sessions.current_slot` to the next unfilled must_fill slot.
"""

from __future__ import annotations

import uuid

from fastapi.concurrency import run_in_threadpool

from api import answers_repo, openai_client, repo

_EXTRACTION_INSTRUCTIONS = (
    "You extract structured facts from a finance discovery conversation. "
    "Given the user's latest message, return values ONLY for slots it actually "
    "addresses, using the exact slot_key from the list below. Do not invent "
    "slots or values. If the message addresses no slots, return an empty list. "
    "Set confidence in [0,1] reflecting how clearly the value was stated."
)


def _next_must_fill(session_id: uuid.UUID | str) -> str | None:
    state = repo.compute_slot_state(session_id)
    unfilled = state["unfilled_must_fill"]
    return unfilled[0] if unfilled else None


async def extract_and_save(session_id: uuid.UUID | str, user_message: str) -> list[str]:
    """Extract + persist answers for the user's message. Returns saved slot_keys."""
    questions = await run_in_threadpool(repo.load_active_questions)
    active_keys = {q["slot_key"] for q in questions}
    slot_list = "\n".join(f"- {q['slot_key']}: {q['text']}" for q in questions)

    messages = [
        {"role": "system", "content": f"{_EXTRACTION_INSTRUCTIONS}\n\nSlots:\n{slot_list}"},
        {"role": "user", "content": user_message},
    ]
    result = await openai_client.parse_extraction(messages)

    saved: list[str] = []
    for ex in result.extractions:
        if ex.slot_key not in active_keys:
            continue  # defensive: ignore hallucinated slot_keys
        await run_in_threadpool(
            answers_repo.save_answer,
            session_id,
            ex.slot_key,
            user_message,
            {"value": ex.value},
            ex.confidence,
            "chat",
        )
        saved.append(ex.slot_key)

    next_slot = await run_in_threadpool(_next_must_fill, session_id)
    await run_in_threadpool(answers_repo.set_current_slot, session_id, next_slot)
    return saved
