"""Demo-company cleanup removes shells + all dependents; real companies survive."""

from __future__ import annotations

import psycopg

from playbook_shared.demo_cleanup import delete_demo_companies
from playbook_shared.migrate import run_migrations
from playbook_shared.question_bank import reseed_questions
from playbook_shared.sessions import CompanyIntake, create_session


def _count(url, table):
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {table}")  # noqa: S608 - test-only, fixed names
        return cur.fetchone()[0]


def test_deletes_demo_shells_and_history_but_not_real_companies(fresh_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db_url)
    run_migrations(fresh_db_url)
    reseed_questions(fresh_db_url)

    # A demo shell via the no-intake path, with an answer + benchmark history.
    demo_session = create_session(fresh_db_url)
    # A real company via the intake path, with an answer.
    real_session = create_session(
        fresh_db_url,
        company=CompanyIntake(name="Acme Manufacturing", industry="Manufacturing"),
    )
    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        for session_id in (demo_session, real_session):
            cur.execute(
                "INSERT INTO answers (session_id, slot_key, raw_text, structured_json, confidence, source) "
                "VALUES (%s, 'close.days', '9 days', '{\"value\": \"9 days\"}', 0.9, 'chat')",
                (session_id,),
            )
            cur.execute("INSERT INTO messages (session_id, role, content) VALUES (%s, 'user', 'hi')", (session_id,))
        # Benchmark history rows hanging off the demo respondent/company.
        cur.execute("SELECT respondent_id, company_id FROM sessions WHERE id = %s", (demo_session,))
        demo_respondent, demo_company = cur.fetchone()
        cur.execute(
            "INSERT INTO cluster_runs (algorithm, params, n_clusters, silhouette_score) "
            "VALUES ('test', '{}', 1, 0.3) RETURNING id"
        )
        run_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO benchmarks (respondent_id, run_id, maturity_score, percentile_cohort, "
            "percentile_cluster, nearest_neighbor_ids) VALUES (%s, %s, 2.5, 50, 50, '[]')",
            (demo_respondent, run_id),
        )
        cur.execute(
            "INSERT INTO company_benchmarks (company_id, run_id, respondent_count, avg_maturity, "
            "percentile_cohort, percentile_peer, peer_group, cluster_exposure, common_pain_points, "
            "common_tech_stack) VALUES (%s, %s, 1, 2.5, 50, 50, '{}', '{}', '[]', '[]')",
            (demo_company, run_id),
        )
        vector = "[" + ",".join(["0.01"] * 1536) + "]"
        cur.execute(
            "INSERT INTO respondent_embeddings (respondent_id, embedding, feature_vector, model) "
            "VALUES (%s, %s::vector, '{}', 'test')",
            (demo_respondent, vector),
        )
        cur.execute(
            "INSERT INTO reports (session_id, type, content_json, rendered_md) VALUES (%s, 'prospect', '{}', 'md')",
            (demo_session,),
        )
        conn.commit()

    result = delete_demo_companies(fresh_db_url)

    assert result.companies == 1
    assert result.respondents == 1
    assert result.sessions == 1
    assert result.answers == 1

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM companies WHERE name = 'Demo discovery company'")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM companies WHERE name = 'Acme Manufacturing'")
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM sessions WHERE id = %s", (real_session,))
        assert cur.fetchone()[0] == 1  # real session intact, with its answer
        cur.execute("SELECT count(*) FROM answers")
        assert cur.fetchone()[0] == 1
    assert _count(fresh_db_url, "benchmarks") == 0
    assert _count(fresh_db_url, "company_benchmarks") == 0
    assert _count(fresh_db_url, "respondent_embeddings") == 0
    assert _count(fresh_db_url, "reports") == 0
    assert _count(fresh_db_url, "cluster_runs") == 1  # run rows are cohort history, kept

    # Idempotent: nothing left to delete.
    second = delete_demo_companies(fresh_db_url)
    assert second.companies == 0