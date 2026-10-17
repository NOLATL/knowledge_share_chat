"""Company-level rollup (Task 8.2): one append-only row per company per run,
peer percentile with cohort fallback, cluster exposure across respondents."""

from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb

from playbook_shared.analytics.pipeline import recompute
from playbook_shared.analytics.synthetic import seed_synthetic_respondents
from playbook_shared.migrate import run_migrations
from playbook_shared.question_bank import reseed_questions

ACME_ANSWERS = [
    ("ctx.role", "Controller"),
    ("close.days", "Close takes 12 days"),
    ("sys.erp", "NetSuite"),
    ("pain.manual_hours", "120 manual hours"),
]


def _embedding_fn(texts):
    vectors = []
    for i, text in enumerate(texts):
        base = (sum(ord(c) for c in text) % 97) / 97
        vector = [0.0] * 1536
        vector[i % 16] = 1.0
        vector[(i // 5) % 16] += 0.5
        vector[32] = base
        vectors.append(vector)
    return vectors


def _seed_acme_with_three_respondents(url: str) -> str:
    """One real company, unique industry (forces peer fallback), 3 respondents."""
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO companies (name, industry, headcount_band) "
            "VALUES ('Acme Manufacturing', 'Manufacturing', '201-1000') RETURNING id"
        )
        company_id = cur.fetchone()[0]
        for n in range(3):
            cur.execute(
                "INSERT INTO respondents (company_id, name, role, email, source) "
                "VALUES (%s, %s, 'Controller', %s, 'real') RETURNING id",
                (company_id, f"Acme respondent {n}", f"acme{n}@acme.example"),
            )
            respondent_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO sessions (company_id, respondent_id, status, script_version) "
                "VALUES (%s, %s, 'complete', 'test') RETURNING id",
                (company_id, respondent_id),
            )
            session_id = cur.fetchone()[0]
            for slot_key, value in ACME_ANSWERS:
                cur.execute(
                    "INSERT INTO answers (session_id, slot_key, raw_text, structured_json, confidence, source) "
                    "VALUES (%s, %s, %s, %s, 0.9, 'chat')",
                    (session_id, slot_key, f"{value} (variant {n})", Jsonb({"value": f"{value} {n}"})),
                )
        conn.commit()
        return str(company_id)


def test_company_rollup_peer_fallback_and_append_only(fresh_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db_url)
    monkeypatch.setattr(
        "playbook_shared.analytics.openai_ops.label_cluster",
        lambda prompt, model=None: (_ for _ in ()).throw(RuntimeError("no LLM in tests")),
    )
    run_migrations(fresh_db_url)
    reseed_questions(fresh_db_url)
    # 24 synthetic one-respondent companies (shared industry, 5 size buckets)
    # + one real 3-respondent company with a unique industry.
    seed_synthetic_respondents(count=24, seed=456, use_llm=False)
    acme_id = _seed_acme_with_three_respondents(fresh_db_url)

    first = recompute(embedding_fn=_embedding_fn, enforce_gate=False)
    second = recompute(embedding_fn=_embedding_fn, enforce_gate=False)

    assert first.respondents_processed == 27
    # 24 synthetic respondents now form 18 companies (every 4th joins the
    # previous respondent's company) + Acme.
    assert first.company_benchmarks_written == 19
    assert second.company_benchmarks_written == 19

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        # Append-only: both runs retained.
        cur.execute("SELECT count(*) FROM company_benchmarks")
        assert cur.fetchone()[0] == 38
        cur.execute("SELECT count(*) FROM company_benchmarks WHERE company_id = %s", (acme_id,))
        assert cur.fetchone()[0] == 2

        # The 3-respondent company rolls up to ONE row per run.
        cur.execute(
            """
            SELECT respondent_count, avg_maturity, percentile_cohort, percentile_peer,
                   peer_group, primary_cluster_id, cluster_exposure, common_pain_points,
                   company_cluster_id
            FROM company_benchmarks
            WHERE company_id = %s AND run_id = %s
            """,
            (acme_id, first.run_id),
        )
        rows = cur.fetchall()
        assert len(rows) == 1
        (count, maturity, pct_cohort, pct_peer, peer_group, primary_cluster, exposure, pains, company_cluster) = rows[0]
        assert count == 3
        assert 1.0 <= maturity <= 5.0
        assert 0.0 < pct_cohort <= 100.0
        # Unique industry -> no peers -> cohort fallback, and then peer == cohort.
        assert peer_group["fell_back"] is True
        assert peer_group["industry"] == "Manufacturing"
        assert pct_peer == pct_cohort
        # No intracompany respondent-persona mix (redesign): the company's persona
        # is its company-grain cluster.
        assert primary_cluster is None
        assert exposure == {}
        assert company_cluster is not None
        assert pains and pains[0]["slot_key"].startswith("pain.")

        # Synthetic companies share an industry; the populous size bands get a
        # real peer group (no fallback) with n >= PEER_MIN.
        cur.execute(
            """
            SELECT count(*)
            FROM company_benchmarks
            WHERE run_id = %s AND (peer_group->>'fell_back')::boolean = false
              AND (peer_group->>'n')::int >= 3
            """,
            (first.run_id,),
        )
        assert cur.fetchone()[0] > 0