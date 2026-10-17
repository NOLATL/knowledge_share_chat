"""On-demand report generation for Epic 4 outputs."""

from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import playbook_shared
from playbook_shared.branding import VENDOR_NAME

from api import openai_client, report_repo

# Internal vendor product knowledge grounding the product-fit mapping.
# ponytail: single-doc inject; promote to the handbook-RAG pattern if it grows past a few pages
CAPABILITIES_PATH = (
    Path(playbook_shared.__file__).resolve().parents[2] / "knowledge" / "vendor_capabilities.md"
)

PRODUCT_FIT_CATEGORIES = ("Current product", "Roadmap candidate", "Third-party")

INTERNAL_SECTIONS = (
    "Cohort Overview",
    "Ranked Pain Themes",
    "Product Fit Mapping",
    "Buying Personas",
    "Market Scoping",
    # Moved here from the vendor prompt (redesign): the cohort/market story is
    # the natural home for the fundraising narrative, not a single account.
    "Investor Narrative",
)

COMPANY_SECTIONS = (
    "Company Profile",
    "Cohort Benchmark",
    "Advisory - Technical Improvements",
    "Advisory - People And Product Gaps",
    "Advisory - Current To Future Risks",
    "Quick Wins",
    "Roadmap",
)

# The function-level roadmap (evolved from the retired prospect report).
FUNCTION_SECTIONS = (
    "Current State",
    "Maturity Assessment",
    "Benchmark Comparison",
    "Prioritized Pains",
    "Category-Level Recommendations",
    "Quick Wins",
    "Roadmap",
)

# Structured phase grid rendered on the external view (brutalist redesign).
ROADMAP_PHASES = ("Now", "Next", "Later")

_ROADMAP_INSTRUCTIONS = (
    "The final section is '## Roadmap' and MUST contain exactly three H3 "
    "subsections '### Now', '### Next', '### Later' (near-term, mid-term, "
    "long-term). Each phase lists 2-3 items formatted exactly as "
    "'- **Title** — one-line description' (bold short title, em dash, one "
    "sentence). Roadmap items are vendor-agnostic, category-level actions."
)

# Account intel (redesign Phase 4): the former session-scoped vendor report,
# re-grained to the company and extended with capability-doc-grounded product
# fit. Internal-only; surfaces on the internal dashboard's account drill-down.
ACCOUNT_SECTIONS = (
    "Opportunity Sizing",
    "Benchmark And Cluster Placement",
    "Ideal Customer Profile Signals",
    "Product Fit",
)

_FORBIDDEN_RECOMMENDATION_VENDORS = (
    "blackline",
    "floqast",
    "netsuite",
    "sap",
    "oracle",
    "anaplan",
    "pigment",
    "workday adaptive",
    "quickbooks",
    "sage",
)


def _recommends_foreign_vendor(text: str, payload: dict[str, Any]) -> bool:
    """True if a blocklisted vendor is named that is NOT part of the company's
    own context. Mirrors the prompt rule: mentioning the current stack is fine,
    recommending a new named vendor as the answer is not."""
    context = json.dumps(payload).lower()
    return any(
        vendor not in context
        and re.search(rf"\b{re.escape(vendor)}\b", text, flags=re.IGNORECASE)
        for vendor in _FORBIDDEN_RECOMMENDATION_VENDORS
    )


async def generate_internal_intelligence() -> dict[str, Any]:
    """Cohort-wide internal (vendor presales) view: ranked pain themes with
    product-fit mapping grounded in the capability doc, plus buying personas."""
    if not CAPABILITIES_PATH.is_file():
        raise ValueError(f"capability document not found: {CAPABILITIES_PATH}")
    capabilities = CAPABILITIES_PATH.read_text(encoding="utf-8")

    context = report_repo.load_internal_context()
    payload = _jsonable({"report_type": "internal_macro", **context})
    markdown = await openai_client.complete_report(_internal_messages(payload, capabilities))
    markdown = _normalize_markdown(markdown)
    _validate_internal_report(markdown)
    return report_repo.insert_report(
        session_id=None,
        company_id=None,
        report_type="internal_macro",
        content_json=payload,
        rendered_md=markdown,
    )


def _internal_messages(payload: dict[str, Any], capabilities: str) -> list[dict[str, str]]:
    required_sections = "\n".join(f"- {section}" for section in INTERNAL_SECTIONS)
    fit = " | ".join(PRODUCT_FIT_CATEGORIES)
    return [
        {
            "role": "system",
            "content": (
                f"You write the INTERNAL market-intelligence view for {VENDOR_NAME} presales. "
                "It is never shown to prospects. Use only the supplied cohort context and the "
                "vendor capability document. Return Markdown only, with exactly these H2 "
                "sections:\n"
                f"{required_sections}\n"
                "Cohort Overview: include how the cohort has grown across runs (run_history) "
                "when more than one run exists — growth is the re-engagement signal. "
                "Ranked Pain Themes: rank the cohort's common pain themes by weight/size. "
                f"Product Fit Mapping: classify EVERY ranked theme as exactly one of [{fit}] — "
                "grounded strictly in the capability document (cite the specific capability for "
                "'Current product'; name the gap for 'Roadmap candidate'; say why it is out of "
                "scope for 'Third-party'). Never invent capabilities not in the document. "
                "Buying Personas: use the per-cluster buying personas to describe who buys and "
                "how to tailor market fit. Market Scoping: rank clusters by size and "
                "underserved pain. Investor Narrative: the fundraising story this cohort "
                "supports — market size signals, recurring pain themes, product-fit coverage, "
                "and the growth/re-engagement trend across runs.\n"
                "Formatting rules: numbered lists ONLY inside Ranked Pain Themes (it is a "
                "ranking); every other list uses '-' bullets. Keep each item's narrative inside "
                "the same bullet after a bold lead (e.g. '- **Audit burden — Current product:** "
                "explanation…'), never as a separate paragraph after the list. Use '### ' H3 "
                "lines for sub-headers inside a section. Start gap assessments with 'Gap:' and "
                "the investor net takeaway with 'Net:' (they are highlighted in the UI).\n\n"
                "VENDOR CAPABILITY DOCUMENT:\n"
                f"{capabilities}"
            ),
        },
        {
            "role": "user",
            "content": (
                "Generate the internal intelligence view from this JSON cohort context.\n\n"
                f"{json.dumps(payload, indent=2)}"
            ),
        },
    ]


def _validate_internal_report(markdown: str) -> None:
    lowered = markdown.lower()
    missing = [section for section in INTERNAL_SECTIONS if f"## {section.lower()}" not in lowered]
    if missing:
        raise ValueError(f"internal report missing sections: {', '.join(missing)}")
    fit_text = _section(markdown, "Product Fit Mapping").lower()
    if not any(category.lower() in fit_text for category in PRODUCT_FIT_CATEGORIES):
        raise ValueError("internal report product-fit mapping missing fit categories")


async def generate_company_report(company_id: uuid.UUID | str) -> dict[str, Any] | None:
    """The external per-company deliverable (Task 8.3): baseball-card profile,
    peer benchmark, and the advisory layer, aggregated across all sessions."""
    context = report_repo.load_company_report_context(company_id)
    if context is None:
        return None

    payload = _jsonable(
        {
            "report_type": "company_external",
            "company": context["company"],
            "respondents": context["respondents"],
            "answers": [_answer_summary(answer) for answer in context["answers"]],
            # Per-function breakdown (multi-grain redesign): who covers the
            # function, their attributed answers, and the function's benchmark
            # + cross-company function persona.
            "functions": [
                {
                    "function_key": fn["function_key"],
                    "respondents": fn["respondents"],
                    "answers": [
                        {
                            **_answer_summary(answer),
                            "respondent_name": answer.get("respondent_name"),
                            "respondent_role": answer.get("respondent_role"),
                        }
                        for answer in fn["answers"]
                    ],
                    "benchmark": fn["benchmark"],
                }
                for fn in context.get("functions", [])
            ],
            "uploaded_documents": context["documents"],
            "company_benchmark": context["company_benchmark"],
            "benchmark_history": context["benchmark_history"],
        }
    )
    markdown = await openai_client.complete_report(_company_messages(payload))
    markdown = _normalize_markdown(markdown)
    _validate_company_report(markdown, payload)
    roadmap = _parse_roadmap(markdown)
    _validate_roadmap(roadmap)
    return report_repo.insert_report(
        session_id=None,
        company_id=company_id,
        report_type="company_external",
        content_json={**payload, "roadmap": roadmap},
        rendered_md=markdown,
    )


async def generate_function_report(
    company_id: uuid.UUID | str, function_key: str
) -> dict[str, Any] | None:
    """The function-level external deliverable (redesign Phase 3): one function's
    roadmap, benchmarked against the same function across the cohort. Header
    reads 'Company / Function'."""
    context = report_repo.load_company_report_context(company_id)
    if context is None:
        return None
    function = next(
        (fn for fn in context["functions"] if fn["function_key"] == function_key), None
    )
    if function is None:
        return None

    payload = _jsonable(
        {
            "report_type": "function_external",
            "company": context["company"],
            "function_key": function_key,
            "respondents": function["respondents"],
            "answers": [
                {
                    **_answer_summary(answer),
                    "respondent_name": answer.get("respondent_name"),
                    "respondent_role": answer.get("respondent_role"),
                }
                for answer in function["answers"]
            ],
            "function_benchmark": function["benchmark"],
            "company_benchmark": context["company_benchmark"],
            "uploaded_documents": context["documents"],
        }
    )
    markdown = await openai_client.complete_report(_function_messages(payload))
    markdown = _normalize_markdown(markdown)
    _validate_function_report(markdown, context["company"]["name"], function_key, payload)
    roadmap = _parse_roadmap(markdown)
    _validate_roadmap(roadmap)
    return report_repo.insert_report(
        session_id=None,
        company_id=company_id,
        function_key=function_key,
        report_type="function_external",
        content_json={**payload, "roadmap": roadmap},
        rendered_md=markdown,
    )


def _function_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    required_sections = "\n".join(f"- {section}" for section in FUNCTION_SECTIONS)
    company = payload["company"]["name"]
    function_key = payload["function_key"]
    return [
        {
            "role": "system",
            "content": (
                "You write a concise finance transformation roadmap for ONE business "
                "function at a prospect company. Use only the supplied context. Be "
                "vendor-agnostic: never recommend a named vendor as the answer; "
                "recommendations are category-level and job-to-be-done framed. Mention a "
                "named tool only if it appears in the function's own current-state facts. "
                f"Start with exactly this H1 title line: '# {company} / {function_key}'. "
                "Then return exactly these H2 sections:\n"
                f"{required_sections}\n"
                "Benchmark Comparison uses function_benchmark: how this function compares "
                "to the SAME function at other companies (percentile_peer), falling back "
                "to the whole cohort when peers are sparse; name its cross-company persona "
                "when present. Keep it specific and easy for the function's leader to scan. "
                f"{_ROADMAP_INSTRUCTIONS}"
            ),
        },
        {
            "role": "user",
            "content": (
                "Generate the function roadmap from this JSON context. "
                "If function_benchmark is null, say function benchmarking will appear "
                "after the next analytics recompute.\n\n"
                f"{json.dumps(payload, indent=2)}"
            ),
        },
    ]


def _validate_function_report(
    markdown: str, company_name: str, function_key: str, payload: dict[str, Any]
) -> None:
    first_line = markdown.splitlines()[0].strip()
    if not (
        first_line.startswith("# ")
        and company_name.lower() in first_line.lower()
        and function_key.lower() in first_line.lower()
    ):
        raise ValueError("function report must open with the '# Company / Function' title")
    lowered = markdown.lower()
    missing = [section for section in FUNCTION_SECTIONS if f"## {section.lower()}" not in lowered]
    if missing:
        raise ValueError(f"function report missing sections: {', '.join(missing)}")
    recommendation_text = _section(markdown, "Category-Level Recommendations")
    if _recommends_foreign_vendor(recommendation_text, payload):
        raise ValueError("function report recommendations must be vendor-agnostic")


async def generate_account_report(company_id: uuid.UUID | str) -> dict[str, Any] | None:
    """Internal account intel for one company: opportunity sizing, ideal
    customer profile signals, benchmark/cluster placement, and capability-doc-
    grounded product fit at the company AND function grain. Never shown to
    prospects."""
    if not CAPABILITIES_PATH.is_file():
        raise ValueError(f"capability document not found: {CAPABILITIES_PATH}")
    capabilities = CAPABILITIES_PATH.read_text(encoding="utf-8")

    context = report_repo.load_company_report_context(company_id)
    if context is None:
        return None

    payload = _jsonable(
        {
            "report_type": "account_internal",
            "company": context["company"],
            "respondents": context["respondents"],
            "answers": [_answer_summary(answer) for answer in context["answers"]],
            "functions": [
                {
                    "function_key": fn["function_key"],
                    "respondents": fn["respondents"],
                    "answers": [_answer_summary(answer) for answer in fn["answers"]],
                    "benchmark": fn["benchmark"],
                }
                for fn in context.get("functions", [])
            ],
            "company_benchmark": context["company_benchmark"],
            "benchmark_history": context["benchmark_history"],
            "uploaded_documents": context["documents"],
        }
    )
    markdown = await openai_client.complete_report(_account_messages(payload, capabilities))
    markdown = _normalize_markdown(markdown)
    _validate_account_report(markdown)
    return report_repo.insert_report(
        session_id=None,
        company_id=company_id,
        report_type="account_internal",
        content_json=payload,
        rendered_md=markdown,
    )


def _account_messages(payload: dict[str, Any], capabilities: str) -> list[dict[str, str]]:
    required_sections = "\n".join(f"- {section}" for section in ACCOUNT_SECTIONS)
    fit = " | ".join(PRODUCT_FIT_CATEGORIES)
    return [
        {
            "role": "system",
            "content": (
                f"You write INTERNAL account intelligence for {VENDOR_NAME} presales about one "
                "prospect company. It is never shown to the prospect. Use only the supplied "
                "account context and the vendor capability document. Return Markdown only, "
                "with exactly these H2 sections:\n"
                f"{required_sections}\n"
                "Opportunity Sizing: use the account's own numbers (hours, volumes, team "
                "size) when available. Benchmark And Cluster Placement: where the company "
                "and each function sit vs peers, and their personas. Ideal Customer Profile "
                "Signals: how well this account matches the ideal customer profile and the "
                "follow-up hooks; spell out 'Ideal Customer Profile', never the acronym ICP. "
                f"Product Fit: classify the account's top pains as exactly one of [{fit}] — "
                "at the company level AND per function — grounded strictly in the capability "
                "document (cite the capability for 'Current product'; name the gap for "
                "'Roadmap candidate'; say why it is out of scope for 'Third-party'). Never "
                "invent capabilities not in the document.\n"
                "Formatting rules: all lists use '-' bullets, never numbered lists (nothing "
                "here is a ranking). Keep each item's narrative inside the same bullet after "
                "a bold lead (e.g. '- **Audit burden — Current product:** explanation…'), "
                "never as a separate paragraph after the list. Use '### ' H3 lines for "
                "sub-headers inside a section. Start gap assessments with 'Gap:' (they are "
                "highlighted in the UI).\n\n"
                "VENDOR CAPABILITY DOCUMENT:\n"
                f"{capabilities}"
            ),
        },
        {
            "role": "user",
            "content": (
                "Generate the account intel view from this JSON context. If benchmarks are "
                "null, note that placement appears after the next analytics recompute.\n\n"
                f"{json.dumps(payload, indent=2)}"
            ),
        },
    ]


def _validate_account_report(markdown: str) -> None:
    lowered = markdown.lower()
    missing = [section for section in ACCOUNT_SECTIONS if f"## {section.lower()}" not in lowered]
    if missing:
        raise ValueError(f"account report missing sections: {', '.join(missing)}")
    fit_text = _section(markdown, "Product Fit").lower()
    if not any(category.lower() in fit_text for category in PRODUCT_FIT_CATEGORIES):
        raise ValueError("account report product fit missing fit categories")


def _company_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    required_sections = "\n".join(f"- {section}" for section in COMPANY_SECTIONS)
    return [
        {
            "role": "system",
            "content": (
                "You write a concise, company-centric finance discovery deliverable for the "
                "prospect company itself. Use only the supplied context. Be vendor-agnostic: "
                "never recommend a named vendor as the answer; recommendations are category-level "
                "and job-to-be-done framed. Mention a named tool only if it appears in the "
                "company's own current-state facts. Return Markdown only, with exactly these H2 "
                "sections:\n"
                f"{required_sections}\n"
                "Company Profile is a scannable 'baseball card': maturity score, peer percentile, "
                "firmographics, cataloged systems/processes/team, and other key stats from the "
                "answers. Cohort Benchmark states how the company compares to its industry/size "
                "peers (or all companies when the peer group fell back) and what that means; "
                "when benchmark_history has two or more entries, also state the movement since "
                "the prior run (percentile and maturity delta) — benchmarks shift as the cohort "
                "grows, so note that this comparison refreshes over time. "
                "The three Advisory sections cover: technical areas to improve; gaps in people "
                "skills and product/tooling coverage; and the risks between current state and "
                "the company's stated future goals. Keep it specific and easy to scan. "
                f"{_ROADMAP_INSTRUCTIONS}"
            ),
        },
        {
            "role": "user",
            "content": (
                "Generate the company deliverable from this JSON context. "
                "If company_benchmark is null, say peer comparison will appear after the next "
                "analytics recompute.\n\n"
                f"{json.dumps(payload, indent=2)}"
            ),
        },
    ]


def _validate_company_report(markdown: str, payload: dict[str, Any]) -> None:
    lowered = markdown.lower()
    missing = [section for section in COMPANY_SECTIONS if f"## {section.lower()}" not in lowered]
    if missing:
        raise ValueError(f"company report missing sections: {', '.join(missing)}")

    advisory_text = " ".join(
        _section(markdown, heading)
        for heading in ("Advisory - Technical Improvements", "Advisory - People And Product Gaps", "Quick Wins")
    )
    if _recommends_foreign_vendor(advisory_text, payload):
        raise ValueError("company report advisory must be vendor-agnostic")


def _parse_roadmap(markdown: str) -> list[dict[str, Any]]:
    """Parse the '## Roadmap' section's '### Now/Next/Later' phases into
    [{phase, items: [{title, desc}]}] for the external view's phase grid."""
    text = _section(markdown, "Roadmap")
    phases: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        header = re.match(r"^###\s+(Now|Next|Later)\b", stripped, flags=re.IGNORECASE)
        if header:
            current = {"phase": header.group(1).capitalize(), "items": []}
            phases.append(current)
            continue
        item = re.match(r"^[-*]\s+\*\*(.+?)\*\*\s*[—–:-]?\s*(.*)$", stripped)
        if item and current is not None:
            current["items"].append({"title": item.group(1).strip(), "desc": item.group(2).strip()})
    return phases


def _validate_roadmap(phases: list[dict[str, Any]]) -> None:
    found = {phase["phase"] for phase in phases if phase["items"]}
    missing = [phase for phase in ROADMAP_PHASES if phase not in found]
    if missing:
        raise ValueError(f"roadmap missing populated phases: {', '.join(missing)}")


def _answer_summary(answer: dict[str, Any]) -> dict[str, Any]:
    structured = answer.get("structured_json") or {}
    value = structured.get("value") if isinstance(structured, dict) else None
    return {
        "slot_key": answer["slot_key"],
        "category": answer["category"],
        "question": answer["question"],
        "tier": answer["tier"],
        "value": value if value is not None else answer.get("raw_text"),
        "confidence": answer["confidence"],
        "source": answer["source"],
    }


def _normalize_markdown(markdown: str) -> str:
    text = markdown.strip()
    if not text:
        raise ValueError("report generation returned empty content")
    return text


def _section(markdown: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$"
    lines = markdown.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.match(pattern, line, flags=re.IGNORECASE):
            start = index + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return "\n".join(lines[start:end])


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value
