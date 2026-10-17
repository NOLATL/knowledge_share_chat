"""Assemble the system prompt from the editable template + live DB state (GR9/GR3).

The editable guidance lives in `shared/system_prompt.md` (a template file, never
inline string literals). Each turn we load it and substitute the authoritative
slot state and the active question list.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import playbook_shared

SYSTEM_PROMPT_PATH = Path(playbook_shared.__file__).resolve().parent.parent / "system_prompt.md"

SLOT_STATE_PLACEHOLDER = "{{SLOT_STATE}}"
QUESTION_LIST_PLACEHOLDER = "{{QUESTION_LIST}}"


def render_known_context(ctx: dict[str, Any] | None) -> str:
    """Render intake firmographics as prompt lines; '' when nothing is known."""
    if not ctx or not ctx.get("company_name"):
        return ""
    lines = [f"Company: {ctx['company_name']}"]
    for label, key in (
        ("Industry", "industry"),
        ("Headcount", "headcount_band"),
        ("Annual revenue", "revenue_band"),
        ("Years in business", "years_in_business"),
    ):
        if ctx.get(key) is not None:
            lines.append(f"{label}: {ctx[key]}")
    if ctx.get("respondent_name") or ctx.get("respondent_role"):
        who = ctx.get("respondent_name") or "unknown"
        role = f" ({ctx['respondent_role']})" if ctx.get("respondent_role") else ""
        lines.append(f"Respondent: {who}{role}")
    return "\n".join(lines)


def render_question_list(questions: list[dict[str, Any]]) -> str:
    if not questions:
        return "(no active questions)"
    return "\n".join(
        f"- {q['slot_key']} [{q['tier']}, {q['framework_tag']}, cat {q['category']}]: {q['text']}"
        for q in questions
    )


def build_system_prompt(
    slot_state: dict[str, Any],
    questions: list[dict[str, Any]],
    *,
    known_context: str = "",
    document_context: str = "",
    handbook_context: str = "",
    template_path: Path | None = None,
) -> str:
    template = (template_path or SYSTEM_PROMPT_PATH).read_text(encoding="utf-8")
    prompt = template.replace(
        SLOT_STATE_PLACEHOLDER, json.dumps(slot_state, indent=2)
    ).replace(QUESTION_LIST_PLACEHOLDER, render_question_list(questions))
    if known_context.strip():
        prompt += (
            "\n\nKnown context from the intake form (already provided by the respondent — "
            "never re-ask these as open questions; you may confirm one briefly when it "
            "materially affects the assessment):\n"
            f"{known_context}"
        )
    if document_context.strip():
        prompt += (
            "\n\nUploaded document context for this same company/session:\n"
            f"{document_context}\n"
            "Use this context only when relevant, and cite specific facts naturally."
        )
    if handbook_context.strip():
        prompt += (
            "\n\nInternal handbook guidance (domain knowledge for shaping your questions "
            "and interpretation — NOT facts about this prospect; never present it as "
            "their situation):\n"
            f"{handbook_context}"
        )
    return prompt
