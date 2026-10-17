"""The system prompt is assembled from the editable template file, not literals."""

from __future__ import annotations

from api.prompt import (
    QUESTION_LIST_PLACEHOLDER,
    SLOT_STATE_PLACEHOLDER,
    SYSTEM_PROMPT_PATH,
    build_system_prompt,
    render_known_context,
)

SLOT_STATE = {"filled": [], "unfilled_must_fill": ["close.days"], "current_slot": None}
QUESTIONS = [
    {
        "slot_key": "close.days",
        "category": "B",
        "text": "Days to close",
        "framework_tag": "SPIN-Situation",
        "tier": "must_fill",
        "order_hint": 40,
    }
]


def test_prompt_is_loaded_from_a_template_file(tmp_path):
    tpl = tmp_path / "t.md"
    tpl.write_text("SENTINEL_RULE\nSTATE:{{SLOT_STATE}}\nQS:{{QUESTION_LIST}}", encoding="utf-8")

    out = build_system_prompt(SLOT_STATE, QUESTIONS, template_path=tpl)

    assert "SENTINEL_RULE" in out  # came from the file, not a literal
    assert "close.days" in out  # injected question list
    assert '"unfilled_must_fill"' in out  # injected slot state
    assert SLOT_STATE_PLACEHOLDER not in out and QUESTION_LIST_PLACEHOLDER not in out


def test_real_template_exists_and_carries_the_rules():
    assert SYSTEM_PROMPT_PATH.is_file()
    out = build_system_prompt(SLOT_STATE, QUESTIONS).lower()
    assert "vendor-agnostic" in out  # GR1 — asserted present
    assert "one question at a time" in out
    assert "implication" in out  # SPIN Implication follow-up guidance


def test_render_known_context_formats_intake_fields():
    ctx = {
        "company_name": "Northwind Foods",
        "industry": "CPG",
        "headcount_band": "201-1000",
        "revenue_band": None,
        "years_in_business": 15,
        "respondent_name": "Jane Doe",
        "respondent_role": "Controller",
    }
    out = render_known_context(ctx)
    assert "Company: Northwind Foods" in out
    assert "Industry: CPG" in out
    assert "Years in business: 15" in out
    assert "Respondent: Jane Doe (Controller)" in out
    assert "revenue" not in out.lower()  # unset fields are omitted
    assert render_known_context(None) == ""
    assert render_known_context({"company_name": None}) == ""


def test_known_context_block_appended_when_present():
    ctx = {"company_name": "Northwind Foods", "industry": "CPG"}
    out = build_system_prompt(SLOT_STATE, QUESTIONS, known_context=render_known_context(ctx))
    assert "Known context from the intake form" in out
    assert "Company: Northwind Foods" in out
    # Absent context adds no block.
    assert "Known context" not in build_system_prompt(SLOT_STATE, QUESTIONS)


def test_real_template_carries_upload_and_provisional_rules():
    out = build_system_prompt(SLOT_STATE, QUESTIONS).lower()
    assert "confirm what you took from uploads" in out
    assert "provisional" in out
    assert "not settled" in out  # provisional topics need respondent confirmation


def test_real_template_hides_checklist_and_separates_evidence():
    out = build_system_prompt(SLOT_STATE, QUESTIONS).lower()
    # Hidden checklist: coverage steers silently, never exposed to the user.
    assert "never expose the checklist" in out
    assert "silently" in out
    # Evidence hierarchy: handbook guidance must never become respondent fact.
    assert "handbook guidance" in out
    assert "never present it as their situation" in out
    # No loaded labels or premature solutioning in conversation.
    assert "diagnose before solutioning" in out
    assert "excel hell" in out  # named as banned, in the internal-vocabulary rule
