"""Session creation helper.

Task 1.1 owns one piece of session creation: stamping the active question-bank
`version` onto `sessions.script_version` so every session records which script it
was answered against. Task 1.2 builds the `POST /sessions` endpoint on top of this.

Task 8.1 adds company-centric intake: when the pre-chat form supplies real
company firmographics, upsert a real `companies` row (+ respondent) instead of
the generic "Demo discovery company" backfill, so analytics can roll up by
company. The no-info path keeps the backfill for quick demos.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from playbook_shared.db import connect
from playbook_shared.question_bank import get_active_version


@dataclass(frozen=True)
class CompanyIntake:
    """Firmographics from the pre-chat form. `name` is required to be treated as real."""

    name: str
    industry: str | None = None
    size_bucket: str | None = None
    headcount_band: str | None = None
    revenue_band: str | None = None
    years_in_business: int | None = None
    respondent_name: str | None = None
    respondent_role: str | None = None
    respondent_email: str | None = None
    # The business function this discovery covers (Accounting, FP&A, Treasury...);
    # the user-facing analytics grain. See migration 0010.
    function_key: str | None = None


def upsert_company(cur, intake: CompanyIntake) -> uuid.UUID:
    """Insert or update a company by name (POC natural key), returning its id.

    ponytail: dedup by name; add a real unique key if companies get created via
    more than the intake form.
    """
    cur.execute("SELECT id FROM companies WHERE name = %s ORDER BY created_at LIMIT 1", (intake.name,))
    row = cur.fetchone()
    if row is not None:
        cur.execute(
            """
            UPDATE companies SET
                industry          = COALESCE(%s, industry),
                size_bucket       = COALESCE(%s, size_bucket),
                headcount_band    = COALESCE(%s, headcount_band),
                revenue_band      = COALESCE(%s, revenue_band),
                years_in_business = COALESCE(%s, years_in_business),
                updated_at        = now()
            WHERE id = %s
            """,
            (
                intake.industry,
                intake.size_bucket,
                intake.headcount_band,
                intake.revenue_band,
                intake.years_in_business,
                row[0],
            ),
        )
        return row[0]
    cur.execute(
        """
        INSERT INTO companies
            (name, industry, size_bucket, headcount_band, revenue_band, years_in_business)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            intake.name,
            intake.industry,
            intake.size_bucket,
            intake.headcount_band,
            intake.revenue_band,
            intake.years_in_business,
        ),
    )
    return cur.fetchone()[0]


def _ensure_respondent(cur, company_id: uuid.UUID, intake: CompanyIntake) -> uuid.UUID:
    """Reuse a respondent by email within the company if given, else insert one."""
    if intake.respondent_email:
        cur.execute(
            "SELECT id FROM respondents WHERE company_id = %s AND email = %s LIMIT 1",
            (company_id, intake.respondent_email),
        )
        row = cur.fetchone()
        if row is not None:
            return row[0]
    cur.execute(
        "INSERT INTO respondents (company_id, name, role, email, source) "
        "VALUES (%s, %s, %s, %s, 'real') RETURNING id",
        (company_id, intake.respondent_name, intake.respondent_role, intake.respondent_email),
    )
    return cur.fetchone()[0]


def create_session(
    database_url: str | None = None,
    *,
    company_id: uuid.UUID | None = None,
    respondent_id: uuid.UUID | None = None,
    company: CompanyIntake | None = None,
    function_key: str | None = None,
    script_version: str | None = None,
) -> uuid.UUID:
    """Insert a session, stamping the current script version. Returns its id.

    If `company` (intake form) is provided, upsert a real company + respondent.
    If nothing is provided, fall back to the demo backfill row.
    """
    version = script_version if script_version is not None else get_active_version()
    if function_key is None and company is not None:
        function_key = company.function_key
    conn = connect(database_url, register_vector_types=False)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            if company is not None and company.name.strip():
                company_id = upsert_company(cur, company)
                respondent_id = _ensure_respondent(cur, company_id, company)
            elif company_id is None and respondent_id is None:
                cur.execute(
                    """
                    INSERT INTO companies (name, industry)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    ("Demo discovery company", "Finance/accounting discovery"),
                )
                company_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO respondents (company_id, name, source)
                    VALUES (%s, %s, 'real')
                    RETURNING id
                    """,
                    (company_id, "Discovery respondent"),
                )
                respondent_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO sessions (company_id, respondent_id, function_key, script_version) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (company_id, respondent_id, function_key, version),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()
