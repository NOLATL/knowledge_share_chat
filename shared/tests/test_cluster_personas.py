"""LLM cluster personas (Task 8.4): labels/personas applied to every grain's
clusters on success; the heuristic fallback is covered by test_analytics_pipeline
(labeling raises there)."""

from __future__ import annotations

import psycopg

from playbook_shared.analytics.pipeline import recompute
from playbook_shared.analytics.synthetic import seed_synthetic_respondents
from playbook_shared.migrate import run_migrations
from playbook_shared.question_bank import reseed_questions


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


def test_llm_personas_written_to_grain_clusters(fresh_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db_url)
    run_migrations(fresh_db_url)
    reseed_questions(fresh_db_url)
    seed_synthetic_respondents(count=24, seed=456, use_llm=False)

    calls: list[str] = []

    def fake_label(prompt, model=None):
        calls.append(prompt)
        n = len(calls)
        return {
            "label": f"Spreadsheet-bound controllers {n}",
            "buying_persona": f"Controller-led buying committee {n}: pragmatic, ROI-first.",
            "summary": f"Cluster {n}: manual-close teams ready for automation.",
        }

    monkeypatch.setattr("playbook_shared.analytics.openai_ops.label_cluster", fake_label)
    summary = recompute(embedding_fn=_embedding_fn, enforce_gate=False)

    assert summary.function_clusters >= 2
    # Every grain's clusters get an LLM persona pass.
    assert len(calls) == summary.function_clusters + summary.company_clusters
    assert "top pains" in calls[0]  # prompt carries the cluster facts

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM clusters WHERE run_id = %s AND buying_persona IS NULL",
            (summary.run_id,),
        )
        assert cur.fetchone()[0] == 0  # every cluster got a persona
        cur.execute(
            "SELECT label FROM clusters WHERE run_id = %s AND grain = 'function' LIMIT 1",
            (summary.run_id,),
        )
        assert "Spreadsheet-bound controllers" in cur.fetchone()[0]
        cur.execute(
            "SELECT DISTINCT grain FROM clusters WHERE run_id = %s ORDER BY grain",
            (summary.run_id,),
        )
        assert [row[0] for row in cur.fetchall()] == ["company", "function"]
