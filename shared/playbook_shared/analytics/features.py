"""Normalize answer text into structured analytics features."""

from __future__ import annotations

import re

from playbook_shared.analytics.models import FeatureProfile, RespondentProfile

TOOLS = ("excel", "power query", "alteryx", "power bi", "sql", "python")
ERPS = ("netsuite", "sap", "oracle", "dynamics", "quickbooks", "sage")
PAIN_SLOTS = ("pain.error_cost", "pain.manual_hours", "pain.bus_factor", "pain.audit_burden")
PAIN_SIGNAL_WORDS = {
    "pain.error_cost": (
        "misstatement",
        "compliance",
        "reputational",
        "risk",
        "rework",
        "correction",
        "delay",
        "reporting",
        "error",
        "errors",
        "cost",
        "costly",
        "audit",
    ),
    "pain.manual_hours": (
        "manual",
        "spreadsheet",
        "prep",
        "preparation",
        "reconciliation",
        "reconciliations",
        "copy",
        "paste",
    ),
    "pain.bus_factor": (
        "key analyst",
        "single point",
        "out",
        "vacation",
        "delay",
        "delays",
        "tribal",
        "knowledge",
    ),
    "pain.audit_burden": (
        "audit",
        "evidence",
        "emails",
        "email",
        "spreadsheet",
        "spreadsheets",
        "support",
        "manual",
    ),
}


def _text(profile: RespondentProfile, key: str) -> str:
    return profile.answers.get(key, "").lower()


def _num(text: str, default: float) -> float:
    match = re.search(r"\d+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group(0)) if match else default


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def build_feature_profile(profile: RespondentProfile) -> FeatureProfile:
    all_text = " ".join(profile.answers.values()).lower()
    close_days = min(_num(_text(profile, "close.days"), 10.0), 30.0)
    manual_hours = min(_num(_text(profile, "pain.manual_hours"), 80.0), 400.0)
    company_text = _text(profile, "ctx.company_profile")
    role_text = (profile.role or _text(profile, "ctx.role")).lower()

    automation_score = 1.0 if _has_any(all_text, ("automated", "automation", "workflow")) else 0.0
    sql_score = 1.0 if _has_any(all_text, ("sql", "python", "warehouse")) else 0.0
    maturity = (
        2.8
        + automation_score * 0.7
        + sql_score * 0.5
        - max(close_days - 5, 0) * 0.08
        - max(manual_hours - 40, 0) * 0.006
    )
    maturity = max(1.0, min(5.0, maturity))

    feature_vector: dict[str, float | int | str | list[str]] = {
        "close_days": close_days,
        "manual_hours": manual_hours,
        "maturity_score": maturity,
        "company_size_rank": _size_rank(company_text),
        "role_controller": int("controller" in role_text),
        "role_fpa": int("fp&a" in role_text or "finance planning" in role_text),
        "role_cfo": int("cfo" in role_text),
        "source": profile.source,
    }
    for tool in TOOLS:
        feature_vector[f"tool_{tool.replace(' ', '_')}"] = int(tool in all_text)
    for erp in ERPS:
        feature_vector[f"erp_{erp}"] = int(erp in all_text)
    for slot in PAIN_SLOTS:
        feature_vector[f"has_{slot.replace('.', '_')}"] = int(bool(profile.answers.get(slot)))
        feature_vector[f"score_{slot.replace('.', '_')}"] = pain_score(profile, slot)

    profile_text = _profile_text(profile, maturity)
    return FeatureProfile(
        respondent_id=profile.respondent_id,
        source=profile.source,
        feature_vector=feature_vector,
        profile_text=profile_text,
        maturity_score=maturity,
    )


def pain_scores(profile: RespondentProfile) -> dict[str, float]:
    return {slot: pain_score(profile, slot) for slot in PAIN_SLOTS}


def pain_score(profile: RespondentProfile, slot: str) -> float:
    text = _text(profile, slot)
    if not text:
        return 0.0

    score = 1.0
    score += _signal_score(text, PAIN_SIGNAL_WORDS.get(slot, ()))

    if slot == "pain.manual_hours":
        hours = _num(text, 0.0)
        if hours:
            score += min(hours / 40.0, 6.0)
    elif slot == "pain.error_cost":
        amount = _num(text, 0.0)
        if amount:
            score += min(amount / 10_000.0, 4.0)
    elif slot == "pain.bus_factor" and _has_any(text, ("only", "single", "key", "one person")):
        score += 1.5
    elif slot == "pain.audit_burden" and _has_any(text, ("audit", "evidence", "support")):
        score += 1.5

    return round(score, 3)


def _signal_score(text: str, words: tuple[str, ...]) -> float:
    return sum(0.45 for word in words if word in text)


def numeric_matrix(profiles: list[FeatureProfile]) -> list[list[float]]:
    keys = sorted(
        key
        for profile in profiles
        for key, value in profile.feature_vector.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )
    return [[float(profile.feature_vector.get(key, 0.0)) for key in keys] for profile in profiles]


def _size_rank(text: str) -> int:
    if "1000" in text or "enterprise" in text:
        return 4
    if "201" in text or "mid-market" in text:
        return 3
    if "51" in text or "growth" in text:
        return 2
    return 1


def _profile_text(profile: RespondentProfile, maturity: float) -> str:
    ordered = [f"{key}: {value}" for key, value in sorted(profile.answers.items())]
    return (
        f"Role: {profile.role or profile.answers.get('ctx.role', 'finance leader')}. "
        f"Source: {profile.source}. Estimated maturity: {maturity:.1f}/5. "
        + " ".join(ordered)
    )
