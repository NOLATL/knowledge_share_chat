"""Migration runner applies cleanly on a fresh DB and is idempotent."""

from __future__ import annotations

from pathlib import Path

import psycopg

from playbook_shared.migrate import run_migrations

MIGRATIONS_DIR = Path(__file__).resolve().parents[1]

# Every table named in BUILD_PLAN.md Appendix A.
EXPECTED_TABLES = {
    "companies",
    "respondents",
    "sessions",
    "questions",
    "messages",
    "answers",
    "documents",
    "document_chunks",
    "handbook_chunks",
    "respondent_embeddings",
    "cluster_runs",
    "clusters",
    "benchmarks",
    "company_benchmarks",
    "email_relays",
    "reports",
    "function_benchmarks",
    "entity_embeddings",
}


def _public_tables(url: str) -> set[str]:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )
        return {row[0] for row in cur.fetchall()}


def test_migration_applies_on_fresh_db(fresh_db_url: str):
    applied = run_migrations(fresh_db_url, MIGRATIONS_DIR)
    assert applied == [
        "0001_init.sql",
        "0002_respondents_cluster_fk.sql",
        "0003_handbook_chunks.sql",
        "0004_company_firmographics.sql",
        "0005_company_benchmarks.sql",
        "0006_reports_company_id.sql",
        "0007_cluster_buying_persona.sql",
        "0008_company_account_code.sql",
        "0009_relay_context.sql",
        "0010_sessions_function.sql",
        "0011_multigrain_analytics.sql",
        "0012_reports_function_key.sql",
        "0013_relay_asked_question.sql",
    ]
    assert EXPECTED_TABLES <= _public_tables(fresh_db_url)


def test_migration_is_idempotent(fresh_db_url: str):
    run_migrations(fresh_db_url, MIGRATIONS_DIR)
    assert run_migrations(fresh_db_url, MIGRATIONS_DIR) == []


def test_cluster_fk_added(fresh_db_url: str):
    run_migrations(fresh_db_url, MIGRATIONS_DIR)
    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_name = 'respondents_cluster_id_fkey' "
            "AND constraint_type = 'FOREIGN KEY'"
        )
        assert cur.fetchone() is not None
