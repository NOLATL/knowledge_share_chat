"""Synthetic respondent generation for Epic 2."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from typing import Callable

from playbook_shared.analytics import openai_ops, repo
from playbook_shared.question_bank import get_active_version


@dataclass(frozen=True)
class SyntheticSummary:
    requested: int
    created: int
    skipped_existing: int
    model: str


@dataclass(frozen=True)
class SyntheticProgress:
    index: int
    total: int
    status: str
    model: str
    message: str = ""


ProgressCallback = Callable[[SyntheticProgress], None]


ARCHETYPES = [
    ("Controller", "51-200", "spreadsheet-heavy", "NetSuite", "Excel and Power Query"),
    ("FP&A Director", "201-1000", "planning-mature", "Oracle", "Power BI, SQL, Python"),
    ("CFO", "1-50", "lean-team", "QuickBooks", "Excel"),
    ("Accounting Manager", "1000+", "shared-services", "SAP", "BlackLine, Alteryx"),
    ("Finance Systems Lead", "201-1000", "automation-forward", "Dynamics", "SQL, Power BI"),
]

# Maps a respondent role to the business FUNCTION its session belongs to (the
# user-facing analytics grain). Values mirror CompanyIntakeForm's FUNCTION
# suggestions so synthetic and real data land in the same function peer pools.
DEFAULT_FUNCTION = "Accounting / Controllership"
FUNCTION_BY_ROLE = (
    ("finance systems", "Financial Systems / IT"),
    ("fp&a", "Financial Planning & Analysis (FP&A)"),
    ("planning", "Financial Planning & Analysis (FP&A)"),
    ("cfo", "Office of the CFO"),
    ("treasur", "Treasury"),
    ("tax", "Tax"),
    ("controller", "Accounting / Controllership"),
    ("accounting", "Accounting / Controllership"),
)


def function_for_role(role: str | None) -> str:
    lowered = (role or "").lower()
    for needle, function_key in FUNCTION_BY_ROLE:
        if needle in lowered:
            return function_key
    return DEFAULT_FUNCTION

# Canonical industry names — mirrored as suggestions in the pre-chat intake form
# so real companies land in the same peer pools. Two industries per archetype
# keeps (industry, size) peer groups dense enough for real peer percentiles.
INDUSTRIES = (
    "Manufacturing",
    "Software & SaaS",
    "Retail & E-commerce",
    "Healthcare",
    "Logistics & Transportation",
    "Financial Services",
    "Business Services",
)

_ARCHETYPE_INDUSTRIES = (
    ("Manufacturing", "Business Services"),
    ("Software & SaaS", "Healthcare"),
    ("Software & SaaS", "Business Services"),
    ("Manufacturing", "Retail & E-commerce"),
    ("Logistics & Transportation", "Financial Services"),
)

# Plausible, clearly fictional company name stems per industry. Combined with
# suffixes this gives 40 unique names per industry — plenty for the cohort.
_NAME_STEMS = {
    "Manufacturing": (
        "Ridgeline Fabrication", "Vulcan Components", "Granite Forge", "Apex Tooling",
        "Ironbridge Industrial", "Summit Diecast", "Bluepeak Plastics", "Cascade Machining",
    ),
    "Software & SaaS": (
        "Nimbusworks", "Brightstack Software", "Cloudvane", "Pixelforge Labs",
        "Quantifi Systems", "Loopwave", "Datalyra", "Kitehill Software",
    ),
    "Retail & E-commerce": (
        "Maple & Main Retail", "Cartwheel Commerce", "Urban Thread", "Shopline Collective",
        "Bluebird Goods", "Harborline Retail", "Evercart", "Willow Market",
    ),
    "Healthcare": (
        "Clearpath Health", "Meridian Care", "Lakeside Clinics", "Vitalis Health",
        "Brightwell Health", "Cedarpoint Medical", "Northstar Care", "Foxhollow Diagnostics",
    ),
    "Logistics & Transportation": (
        "Swiftroute Logistics", "Bluewater Freight", "Crossdock Carriers", "Meridian Haulage",
        "Portside Shipping", "Ridgeway Transport", "Lattice Freight", "Northhaul Logistics",
    ),
    "Financial Services": (
        "Sterling Row Capital", "Harborstone Financial", "Oakgate Advisors", "Crestline Lending",
        "Meridian Trust", "Bluechip Payments", "Foxglove Insurance", "Northbridge Capital",
    ),
    "Business Services": (
        "Beaconpoint Consulting", "Claritywork Partners", "Stonebriar Services", "Elmrock Advisory",
        "Brightside Staffing", "Keystone Facilities", "Northwind Outsourcing", "Cobalt Business Group",
    ),
}

_NAME_SUFFIXES = ("", " Group", " Holdings", " Partners", " Inc")


def _company_name(industry: str, ordinal: int) -> str:
    stems = _NAME_STEMS.get(industry, _NAME_STEMS["Business Services"])
    stem = stems[ordinal % len(stems)]
    suffix = _NAME_SUFFIXES[(ordinal // len(stems)) % len(_NAME_SUFFIXES)]
    return f"{stem}{suffix}"


_REVENUE_BY_SIZE = {
    "1-50": "<$10M",
    "51-200": "$10-50M",
    "201-1000": "$50-250M",
    "1000+": "$250M-1B",
}

_YEARS_BY_SIZE = {
    "1-50": (3, 15),
    "51-200": (5, 25),
    "201-1000": (10, 40),
    "1000+": (20, 80),
}

# Every Nth synthetic respondent joins the previous respondent's company, so
# the cohort contains multi-respondent companies for the company-level rollup.
SHARE_COMPANY_EVERY = 4


def _industry_for(index: int) -> str:
    pool = _ARCHETYPE_INDUSTRIES[index % len(ARCHETYPES)]
    return pool[(index // len(ARCHETYPES)) % len(pool)]


def _firmographics(size_bucket: str, rng: random.Random) -> tuple[str, str, int]:
    low, high = _YEARS_BY_SIZE.get(size_bucket, (5, 30))
    return size_bucket, _REVENUE_BY_SIZE.get(size_bucket, "$10-50M"), rng.randint(low, high)


def seed_synthetic_respondents(
    *,
    count: int | None = None,
    seed: int | None = None,
    use_llm: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> SyntheticSummary:
    target = count if count is not None else int(os.environ.get("SYNTHETIC_TARGET_COUNT", "150"))
    seed_value = seed if seed is not None else int(os.environ.get("SYNTHETIC_SEED", "20260628"))
    rng = random.Random(seed_value)
    questions = repo.active_questions()
    slot_keys = [q["slot_key"] for q in questions]
    script_version = get_active_version()
    model = openai_ops.synthetic_model()

    created = 0
    skipped = 0
    for index in range(target):
        if repo.synthetic_exists(seed_value, index):
            skipped += 1
            _notify_progress(progress_callback, index, target, "skipped", model, "already exists")
            continue
        archetype = ARCHETYPES[index % len(ARCHETYPES)]
        # Every SHARE_COMPANY_EVERYth respondent joins the previous respondent's
        # company: a second voice from the same company, with a different role
        # but the previous archetype's company facts so the story stays coherent.
        existing_company_id = None
        if index % SHARE_COMPANY_EVERY == SHARE_COMPANY_EVERY - 1 and index > 0:
            existing_company_id = repo.synthetic_company_id(seed_value, index - 1)
            if existing_company_id is not None:
                previous = ARCHETYPES[(index - 1) % len(ARCHETYPES)]
                archetype = (archetype[0], *previous[1:])
        _notify_progress(progress_callback, index, target, "started", model, archetype[0])
        answers = (
            _llm_answers(
                archetype,
                questions,
                slot_keys,
                rng,
                model,
                index=index,
                total=target,
                progress_callback=progress_callback,
            )
            if use_llm
            else _deterministic_answers(archetype, slot_keys, index)
        )
        headcount_band, revenue_band, years = _firmographics(archetype[1], rng)
        repo.insert_synthetic_respondent(
            seed=seed_value,
            index=index,
            company_name=_company_name(_industry_for(index), index),
            size_bucket=archetype[1],
            role=archetype[0],
            answers=answers,
            script_version=script_version,
            industry=_industry_for(index),
            headcount_band=headcount_band,
            revenue_band=revenue_band,
            years_in_business=years,
            existing_company_id=existing_company_id,
            function_key=function_for_role(archetype[0]),
        )
        created += 1
        _notify_progress(progress_callback, index, target, "created", model, "inserted")
    return SyntheticSummary(requested=target, created=created, skipped_existing=skipped, model=model)


def _llm_answers(
    archetype,
    questions,
    slot_keys,
    rng: random.Random,
    model: str,
    *,
    index: int,
    total: int,
    progress_callback: ProgressCallback | None,
) -> dict[str, str]:
    role, size, maturity, erp, tools = archetype
    prompt = (
        f"Role: {role}\nCompany size: {size}\nMaturity profile: {maturity}\n"
        f"ERP: {erp}\nTools: {tools}\nVariation seed: {rng.randint(1, 1_000_000)}\n\n"
        "Questions:\n"
        + "\n".join(f"- {q['slot_key']}: {q['text']}" for q in questions)
    )
    fallback_model = openai_ops.fallback_synthetic_model()
    try:
        answers = openai_ops.generate_answers(prompt, slot_keys, model=model)
        if _has_enough_answers(answers, slot_keys):
            return answers
        _notify_progress(
            progress_callback,
            index,
            total,
            "fallback",
            fallback_model,
            "primary returned too few answers",
        )
    except Exception as exc:
        _notify_progress(progress_callback, index, total, "fallback", fallback_model, type(exc).__name__)
    answers = openai_ops.generate_answers(prompt, slot_keys, model=fallback_model)
    if not _has_enough_answers(answers, slot_keys):
        raise ValueError("synthetic model returned too few answers")
    return answers


def _has_enough_answers(answers: dict[str, str], slot_keys: list[str]) -> bool:
    return sum(bool(v) for v in answers.values()) >= max(6, len(slot_keys) // 2)


def _notify_progress(
    progress_callback: ProgressCallback | None,
    index: int,
    total: int,
    status: str,
    model: str,
    message: str = "",
) -> None:
    if progress_callback is not None:
        progress_callback(
            SyntheticProgress(index=index, total=total, status=status, model=model, message=message)
        )


PLACEHOLDER_INDUSTRY = "Finance/accounting demo cohort"

_SIZE_INDUSTRIES = {
    "1-50": ("Software & SaaS", "Business Services"),
    "51-200": ("Manufacturing", "Business Services"),
    "201-1000": ("Software & SaaS", "Healthcare", "Logistics & Transportation", "Financial Services"),
    "1000+": ("Manufacturing", "Retail & E-commerce"),
}


@dataclass(frozen=True)
class EnrichmentSummary:
    enriched: int
    merged: int


def enrich_synthetic_companies(
    database_url: str | None = None,
    *,
    seed: int | None = None,
    consolidate_every: int = SHARE_COMPANY_EVERY,
) -> EnrichmentSummary:
    """One-off, in-place upgrade of legacy synthetic companies (Task: company analytics).

    Legacy seeding gave every synthetic respondent its own company with the
    placeholder industry and no firmographics — which makes peer groups
    degenerate and the company rollup trivially 1:1. This assigns realistic
    industries + firmographics (deterministic from the seed) and merges every
    Nth company within an (industry, size) group into a multi-respondent
    company. Answers, respondents, and append-only analytics history are
    preserved; orphaned company rows keep their history but drop out of the
    directory (no sessions). Idempotent: only placeholder-industry companies
    are touched, so a re-run is a no-op.
    """
    from playbook_shared.db import connect  # local import keeps module deps flat

    seed_value = seed if seed is not None else int(os.environ.get("SYNTHETIC_SEED", "20260628"))
    rng = random.Random(seed_value)
    conn = connect(database_url, register_vector_types=False)
    conn.autocommit = True
    enriched = 0
    merged = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.size_bucket
                FROM companies c
                WHERE c.industry = %s
                  AND EXISTS (
                    SELECT 1 FROM respondents r
                    WHERE r.company_id = c.id AND r.source = 'synthetic'
                  )
                ORDER BY c.created_at, c.id
                """,
                (PLACEHOLDER_INDUSTRY,),
            )
            targets = cur.fetchall()

            groups: dict[tuple[str, str], list] = {}
            for company_id, size_bucket in targets:
                size = size_bucket or "51-200"
                pool = _SIZE_INDUSTRIES.get(size, INDUSTRIES)
                industry = pool[rng.randrange(len(pool))]
                _, revenue_band, years = _firmographics(size, rng)
                cur.execute(
                    """
                    UPDATE companies SET
                        industry = %s, headcount_band = %s, revenue_band = %s,
                        years_in_business = %s, updated_at = now()
                    WHERE id = %s
                    """,
                    (industry, size, revenue_band, years, company_id),
                )
                enriched += 1
                groups.setdefault((industry, size), []).append(company_id)

            # Merge every Nth company of a peer group into the group's first, so
            # the cohort contains multi-respondent companies.
            for members in groups.values():
                head = members[0]
                for position, company_id in enumerate(members[1:], start=1):
                    if position % consolidate_every != 0:
                        continue
                    cur.execute(
                        "UPDATE respondents SET company_id = %s WHERE company_id = %s",
                        (head, company_id),
                    )
                    cur.execute(
                        "UPDATE sessions SET company_id = %s WHERE company_id = %s",
                        (head, company_id),
                    )
                    merged += 1
    finally:
        conn.close()
    return EnrichmentSummary(enriched=enriched, merged=merged)


def rename_synthetic_companies(database_url: str | None = None) -> int:
    """One-off: replace 'Synthetic Demo Co …' placeholders with plausible,
    industry-appropriate fictional names. Deterministic (ordered by creation),
    unique per industry within the run, idempotent (renamed rows no longer match
    the placeholder pattern). Account codes remain the stable identifier."""
    from playbook_shared.db import connect  # local import keeps module deps flat

    conn = connect(database_url, register_vector_types=False)
    conn.autocommit = True
    renamed = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, industry FROM companies
                WHERE name LIKE 'Synthetic Demo Co %'
                ORDER BY created_at, id
                """
            )
            ordinals: dict[str, int] = {}
            for company_id, industry in cur.fetchall():
                key = industry or "Business Services"
                ordinal = ordinals.get(key, 0)
                ordinals[key] = ordinal + 1
                cur.execute(
                    "UPDATE companies SET name = %s, updated_at = now() WHERE id = %s",
                    (_company_name(key, ordinal), company_id),
                )
                renamed += 1
    finally:
        conn.close()
    return renamed


def backfill_session_functions(database_url: str | None = None) -> int:
    """One-off: set sessions.function_key from the respondent's role for sessions
    that predate the intake function selector. Idempotent — only fills NULLs, so
    a re-run (or sessions created after the selector shipped) is a no-op."""
    from playbook_shared.db import connect  # local import keeps module deps flat

    conn = connect(database_url, register_vector_types=False)
    conn.autocommit = True
    updated = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id, r.role
                FROM sessions s
                LEFT JOIN respondents r ON r.id = s.respondent_id
                WHERE s.function_key IS NULL
                """
            )
            for session_id, role in cur.fetchall():
                cur.execute(
                    "UPDATE sessions SET function_key = %s WHERE id = %s AND function_key IS NULL",
                    (function_for_role(role), session_id),
                )
                updated += cur.rowcount
    finally:
        conn.close()
    return updated


def _deterministic_answers(archetype, slot_keys: list[str], index: int) -> dict[str, str]:
    role, size, maturity, erp, tools = archetype
    close_days = {"spreadsheet-heavy": 12, "planning-mature": 5, "lean-team": 8}.get(maturity, 7)
    manual_hours = {"spreadsheet-heavy": 140, "planning-mature": 35, "lean-team": 80}.get(maturity, 55)
    values = {
        "ctx.role": f"I am the {role} and own finance operations.",
        "ctx.company_profile": f"We are a {size} {maturity} company.",
        "ctx.team_structure": "Small finance team with shared accounting and FP&A coverage.",
        "close.days": f"Month-end close takes about {close_days + index % 3} days.",
        "recon.manual_vs_auto": "Bank and balance sheet reconciliations are partly manual.",
        "apar.volume": "We process roughly 900 invoices and payments per month.",
        "consolidation.method": f"We consolidate entities from {erp} and spreadsheets.",
        "reporting.process": "Board reporting is built in spreadsheets and reviewed manually.",
        "fpa.cadence": "Forecasts are monthly, with scenario planning mostly spreadsheet based.",
        "tax.process": "Tax reconciliations are prepared manually with outside advisor review.",
        "sys.erp": erp,
        "sys.dataprep_tools": tools,
        "sys.data_location": "Data lives across ERP exports, SharePoint, and spreadsheets.",
        "sys.epm_close_tools": "Some close checklist tooling, but no unified automation.",
        "skill.builders": "Finance analysts build most workflows with light IT support.",
        "skill.sql_python": "A few analysts know SQL or Python; most are Excel-first.",
        "skill.onboarding_time": "New analysts need four to six weeks to learn the tooling.",
        "pain.error_cost": "Errors cause rework, late reporting, and audit risk.",
        "pain.manual_hours": f"We spend about {manual_hours + index % 20} hours per month on manual prep.",
        "pain.bus_factor": "A key analyst being out delays reporting and reconciliations.",
        "pain.audit_burden": "Audit evidence is collected from emails and spreadsheets.",
        "goal.future_state": "Great means close is faster, reporting is trusted, and analysis gets more time.",
        "goal.trigger": "Growth and reporting pressure are forcing a better process now.",
        "goal.decision_process": "The CFO funds it, finance owns evaluation, IT reviews security.",
        "goal.blockers": "Budget, bandwidth, and change management blocked progress.",
    }
    return {slot: values.get(slot, f"Synthetic answer for {slot}.") for slot in slot_keys}
