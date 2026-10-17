"""Synthetic company realism (company-analytics compliance): varied industries,
firmographics, multi-respondent companies, in-place legacy enrichment, and
account codes generated for every insert path."""

from __future__ import annotations

import uuid

import psycopg

from playbook_shared.analytics.synthetic import (
    INDUSTRIES,
    PLACEHOLDER_INDUSTRY,
    enrich_synthetic_companies,
    rename_synthetic_companies,
    seed_synthetic_respondents,
)
from playbook_shared.migrate import run_migrations
from playbook_shared.question_bank import reseed_questions


def _setup(fresh_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db_url)
    run_migrations(fresh_db_url)
    reseed_questions(fresh_db_url)


def test_generator_creates_varied_multi_respondent_companies(fresh_db_url, monkeypatch):
    _setup(fresh_db_url, monkeypatch)
    seed_synthetic_respondents(count=20, seed=321, use_llm=False)

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(DISTINCT r.id), count(DISTINCT r.company_id) "
            "FROM respondents r WHERE r.source = 'synthetic'"
        )
        respondents, companies = cur.fetchone()
        assert respondents == 20
        assert companies == 15  # every 4th respondent joined the previous company

        cur.execute(
            """
            SELECT DISTINCT c.industry, c.headcount_band, c.revenue_band, c.years_in_business,
                   c.account_code
            FROM companies c JOIN respondents r ON r.company_id = c.id
            WHERE r.source = 'synthetic'
            """
        )
        rows = cur.fetchall()
        industries = {row[0] for row in rows}
        assert industries <= set(INDUSTRIES)  # no placeholder industry
        assert len(industries) >= 3  # visibly varied
        for industry, headcount, revenue, years, account_code in rows:
            assert headcount and revenue and years and account_code
            assert account_code.startswith("C-")

        # Multi-respondent companies exist and share coherent company facts.
        cur.execute(
            """
            SELECT c.id FROM companies c JOIN respondents r ON r.company_id = c.id
            WHERE r.source = 'synthetic'
            GROUP BY c.id HAVING count(r.id) > 1 LIMIT 1
            """
        )
        shared_company = cur.fetchone()
        assert shared_company is not None
        cur.execute(
            "SELECT count(DISTINCT role) FROM respondents WHERE company_id = %s",
            (shared_company[0],),
        )
        assert cur.fetchone()[0] == 2  # two voices, different roles


def _seed_legacy_style(url: str, count: int) -> None:
    """Reproduce the pre-enrichment prod shape: 1 company per respondent,
    placeholder industry, no firmographics."""
    sizes = ["1-50", "51-200", "201-1000", "1000+"]
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        for n in range(count):
            cur.execute(
                "INSERT INTO companies (name, industry, size_bucket) VALUES (%s, %s, %s) RETURNING id",
                (f"Legacy Synth Co {n:03d}", PLACEHOLDER_INDUSTRY, sizes[n % 4]),
            )
            company_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO respondents (company_id, name, role, email, source) "
                "VALUES (%s, %s, 'Controller', %s, 'synthetic') RETURNING id",
                (company_id, f"Legacy respondent {n}", f"legacy{n}@playbook.local"),
            )
            respondent_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO sessions (company_id, respondent_id, status, script_version) "
                "VALUES (%s, %s, 'complete', 'test') RETURNING id",
                (company_id, respondent_id),
            )
            session_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO answers (session_id, slot_key, raw_text, structured_json, confidence, source) "
                "VALUES (%s, 'close.days', '10 days', '{\"value\": \"10 days\"}', 0.9, 'chat')",
                (session_id,),
            )
        conn.commit()


def test_enrichment_upgrades_legacy_companies_in_place_and_is_idempotent(fresh_db_url, monkeypatch):
    _setup(fresh_db_url, monkeypatch)
    _seed_legacy_style(fresh_db_url, 24)

    # consolidate_every=2 makes merging order-independent: the 2-industry size
    # bands hold 6 companies each, so some (industry, size) group always has >=3
    # members regardless of how the rng splits them.
    first = enrich_synthetic_companies(fresh_db_url, seed=99, consolidate_every=2)
    second = enrich_synthetic_companies(fresh_db_url, seed=99, consolidate_every=2)

    assert first.enriched == 24
    assert first.merged >= 1  # some companies consolidated into multi-respondent ones
    assert second.enriched == 0 and second.merged == 0  # idempotent

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM companies WHERE industry = %s", (PLACEHOLDER_INDUSTRY,))
        assert cur.fetchone()[0] == 0
        cur.execute(
            "SELECT count(*) FROM companies WHERE name LIKE 'Legacy Synth Co%' "
            "AND (headcount_band IS NULL OR revenue_band IS NULL OR years_in_business IS NULL)"
        )
        assert cur.fetchone()[0] == 0  # firmographics filled everywhere

        # Merged companies moved BOTH respondents and sessions; answers intact.
        cur.execute(
            """
            SELECT c.id FROM companies c JOIN respondents r ON r.company_id = c.id
            GROUP BY c.id HAVING count(r.id) > 1 LIMIT 1
            """
        )
        merged_company = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM sessions WHERE company_id = %s",
            (merged_company,),
        )
        assert cur.fetchone()[0] >= 2
        cur.execute("SELECT count(*) FROM answers")
        assert cur.fetchone()[0] == 24  # nothing lost

        # Orphaned shells have no sessions left -> hidden from the directory.
        cur.execute(
            """
            SELECT count(*) FROM companies c
            WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.company_id = c.id)
              AND c.name LIKE 'Legacy Synth Co%'
            """
        )
        assert cur.fetchone()[0] == first.merged


def test_generator_names_sound_industry_appropriate(fresh_db_url, monkeypatch):
    _setup(fresh_db_url, monkeypatch)
    seed_synthetic_respondents(count=20, seed=321, use_llm=False)

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT c.name FROM companies c JOIN respondents r ON r.company_id = c.id "
            "WHERE r.source = 'synthetic'"
        )
        names = [row[0] for row in cur.fetchall()]
    assert names
    assert not any(name.startswith("Synthetic Demo Co") for name in names)
    assert len(set(names)) == len(names)  # unique


def test_rename_gives_placeholder_companies_industry_names_idempotently(fresh_db_url, monkeypatch):
    _setup(fresh_db_url, monkeypatch)
    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO companies (name, industry) VALUES "
            "('Synthetic Demo Co 1-001', 'Manufacturing'), "
            "('Synthetic Demo Co 1-002', 'Manufacturing'), "
            "('Synthetic Demo Co 1-003', 'Healthcare'), "
            "('Acme Real Co', 'Manufacturing')"
        )
        conn.commit()

    first = rename_synthetic_companies(fresh_db_url)
    second = rename_synthetic_companies(fresh_db_url)

    assert first == 3
    assert second == 0  # idempotent: renamed rows no longer match the pattern

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT name, industry FROM companies WHERE name != 'Acme Real Co' ORDER BY name")
        rows = cur.fetchall()
    names = [name for name, _ in rows]
    assert len(set(names)) == 3  # unique within run
    assert not any(name.startswith("Synthetic Demo Co") for name in names)
    # Industry-flavored: manufacturing names come from the manufacturing pool.
    manufacturing_names = [name for name, industry in rows if industry == "Manufacturing"]
    manufacturing_stems = ("Ridgeline", "Vulcan", "Granite", "Apex", "Ironbridge", "Summit", "Bluepeak", "Cascade")
    assert all(name.startswith(manufacturing_stems) for name in manufacturing_names)


def test_account_codes_generated_unique_and_backfilled(fresh_db_url, monkeypatch):
    _setup(fresh_db_url, monkeypatch)
    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        # Any insert path gets a code from the DB default.
        cur.execute("INSERT INTO companies (name) VALUES ('Plain Insert Co') RETURNING account_code")
        code = cur.fetchone()[0]
        assert code and code.startswith("C-")
        cur.execute("INSERT INTO companies (name) VALUES ('Second Co') RETURNING account_code")
        assert cur.fetchone()[0] != code
        conn.commit()


def test_company_by_code_roundtrip(fresh_db_url, monkeypatch):
    _setup(fresh_db_url, monkeypatch)
    from api import report_repo  # noqa: PLC0415 - exercised against this DB

    session_id = uuid.uuid4()
    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO companies (name, industry) VALUES ('Acme', 'Manufacturing') RETURNING id, account_code")
        company_id, code = cur.fetchone()
        cur.execute(
            "INSERT INTO sessions (id, company_id, script_version) VALUES (%s, %s, 'test')",
            (session_id, company_id),
        )
        conn.commit()

    assert report_repo.company_id_by_account_code(code) == company_id
    assert report_repo.company_id_by_account_code(code.lower()) == company_id  # case-insensitive
    assert report_repo.company_id_by_account_code("C-99999") is None