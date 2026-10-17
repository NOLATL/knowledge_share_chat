"""Deterministic resume recap built from filled-slot state (Task 1.5)."""

from __future__ import annotations

import uuid

from api import repo


def build_recap(session_id: uuid.UUID | str) -> str:
    """A greeting that names what's already covered and what's next."""
    questions = repo.load_active_questions()
    by_key = {q["slot_key"]: q for q in questions}
    state = repo.compute_slot_state(session_id)

    covered = [by_key[k]["text"] for k in state["filled"] if k in by_key]
    next_keys = state["unfilled_must_fill"]
    next_text = by_key[next_keys[0]]["text"] if next_keys and next_keys[0] in by_key else None

    parts = ["Welcome back."]
    if covered:
        parts.append("So far we've covered: " + "; ".join(covered) + ".")
    else:
        parts.append("We're just getting started.")
    if next_text:
        parts.append(f"Next, I'd like to understand: {next_text}")
    else:
        parts.append("We've covered all the must-have topics — we can wrap up whenever you're ready.")
    return " ".join(parts)
