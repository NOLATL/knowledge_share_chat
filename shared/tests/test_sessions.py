"""A new session records the current question-bank version (Task 1.1)."""

from __future__ import annotations

from pathlib import Path

import psycopg

from playbook_shared.migrate import run_migrations
from playbook_shared.question_bank import get_active_version
from playbook_shared.sessions import CompanyIntake, create_session

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def test_create_session_stamps_script_version(fresh_db_url):
    run_migrations(fresh_db_url, MIGRATIONS_DIR)

    session_id = create_session(fresh_db_url)

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.script_version, s.company_id, s.respondent_id, r.source
            FROM sessions s
            JOIN respondents r ON r.id = s.respondent_id
            WHERE s.id = %s
            """,
            (session_id,),
        )
        script_version, company_id, respondent_id, source = cur.fetchone()
        assert script_version == get_active_version()
        assert company_id is not None
        assert respondent_id is not None
        assert source == "real"


def _company_row(url, company_id):
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT name, industry, headcount_band, revenue_band, years_in_business FROM companies WHERE id = %s",
            (company_id,),
        )
        return cur.fetchone()


def test_intake_upserts_firmographics_and_links_real_company(fresh_db_url):
    run_migrations(fresh_db_url, MIGRATIONS_DIR)
    intake = CompanyIntake(
        name="Acme Manufacturing",
        industry="Manufacturing",
        headcount_band="201-1000",
        revenue_band="$50-250M",
        years_in_business=22,
        respondent_name="Jo Controller",
        respondent_role="Controller",
        respondent_email="jo@acme.example",
    )

    session_id = create_session(fresh_db_url, company=intake)

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT company_id, respondent_id FROM sessions WHERE id = %s", (session_id,))
        company_id, respondent_id = cur.fetchone()
    assert _company_row(fresh_db_url, company_id) == (
        "Acme Manufacturing", "Manufacturing", "201-1000", "$50-250M", 22,
    )

    # Same company name on a second session reuses the row and reuses the respondent by email.
    session_2 = create_session(fresh_db_url, company=intake)
    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT company_id, respondent_id FROM sessions WHERE id = %s", (session_2,))
        company_2, respondent_2 = cur.fetchone()
        cur.execute("SELECT count(*) FROM companies WHERE name = 'Acme Manufacturing'")
        assert cur.fetchone()[0] == 1  # upserted, not duplicated
    assert company_2 == company_id
    assert respondent_2 == respondent_id  # deduped by email


def test_intake_stamps_function_key_on_session(fresh_db_url):
    run_migrations(fresh_db_url, MIGRATIONS_DIR)
    intake = CompanyIntake(name="Acme Manufacturing", function_key="Treasury")

    session_id = create_session(fresh_db_url, company=intake)

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT function_key FROM sessions WHERE id = %s", (session_id,))
        assert cur.fetchone()[0] == "Treasury"


def test_no_intake_still_backfills_demo_company(fresh_db_url):
    run_migrations(fresh_db_url, MIGRATIONS_DIR)
    session_id = create_session(fresh_db_url)
    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT c.name FROM sessions s JOIN companies c ON c.id = s.company_id WHERE s.id = %s",
            (session_id,),
        )
        assert cur.fetchone()[0] == "Demo discovery company"
