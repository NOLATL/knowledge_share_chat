"""Recompute clusters + benchmarks at the function and company grain (Fork B);
there is no respondent-grain clustering."""

import math
import uuid

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


def _labeling_unavailable(prompt, model=None):
    raise RuntimeError("no LLM in tests — heuristic fallback expected")


def test_recompute_writes_grain_clusters_and_append_only_benchmarks(fresh_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db_url)
    monkeypatch.setattr("playbook_shared.analytics.openai_ops.label_cluster", _labeling_unavailable)
    run_migrations(fresh_db_url)
    reseed_questions(fresh_db_url)
    seed_synthetic_respondents(count=24, seed=456, use_llm=False)

    first = recompute(embedding_fn=_embedding_fn, enforce_gate=False)
    second = recompute(embedding_fn=_embedding_fn, enforce_gate=False)

    assert first.respondents_processed == 24
    # 24 synthetic respondents form 18 companies (every 4th joins the previous
    # respondent's company); functions = distinct (company, function_key).
    assert first.company_entities == 18
    assert first.function_entities >= 18
    assert first.function_benchmarks_written == first.function_entities
    assert first.function_clusters >= 2
    assert math.isfinite(first.function_silhouette)
    assert second.function_benchmarks_written == first.function_benchmarks_written

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM cluster_runs")
        assert cur.fetchone()[0] == 2
        # Append-only: both runs retained at both grains.
        cur.execute("SELECT count(*) FROM function_benchmarks")
        assert cur.fetchone()[0] == 2 * first.function_benchmarks_written
        cur.execute(
            "SELECT count(*) FROM entity_embeddings WHERE grain = 'function' AND umap_x IS NOT NULL"
        )
        assert cur.fetchone()[0] == 2 * first.function_entities
        cur.execute("SELECT count(*) FROM clusters WHERE grain = 'company' AND run_id = %s", (first.run_id,))
        assert cur.fetchone()[0] == first.company_clusters

        # Heuristic (no-LLM) cluster names/summaries at the function grain.
        cur.execute(
            "SELECT label, summary FROM clusters WHERE run_id = %s AND grain = 'function'",
            (first.run_id,),
        )
        cluster_rows = cur.fetchall()
        assert cluster_rows
        for label, summary in cluster_rows:
            assert " group " in label
            # No numeric maturity in prose — it gets misread as a member's own score.
            assert "operations" in summary
            assert "/5" not in summary
            assert "Common pressure areas" in summary
        cur.execute(
            "SELECT common_pain_points FROM clusters WHERE run_id = %s AND grain = 'function' LIMIT 1",
            (first.run_id,),
        )
        pain_points = cur.fetchone()[0]
        assert pain_points
        assert {"slot_key", "count", "score", "avg_score"} <= pain_points[0].keys()


def test_recompute_backfills_legacy_answered_session_into_company_grain(fresh_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db_url)
    monkeypatch.setattr("playbook_shared.analytics.openai_ops.label_cluster", _labeling_unavailable)
    run_migrations(fresh_db_url)
    reseed_questions(fresh_db_url)
    session_id = uuid.uuid4()
    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO sessions (id, script_version) VALUES (%s, 'legacy')", (session_id,))
        cur.execute(
            """
            INSERT INTO answers (session_id, slot_key, raw_text, structured_json, confidence, source)
            VALUES
              (%s, 'ctx.role', 'Controller', '{"value": "Controller"}', 0.9, 'chat'),
              (%s, 'close.days', 'Close takes 11 days', '{"value": "11 days"}', 0.9, 'chat'),
              (%s, 'pain.manual_hours', '90 manual hours', '{"value": "90 manual hours"}', 0.9, 'chat')
            """,
            (session_id, session_id, session_id),
        )
        conn.commit()

    summary = recompute(embedding_fn=_embedding_fn, enforce_gate=False)

    # No function_key on the legacy session: company grain only.
    assert summary.respondents_processed == 1
    assert summary.function_entities == 0
    assert summary.company_entities == 1
    assert summary.company_benchmarks_written == 1
    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.source, s.company_id, cb.company_cluster_id
            FROM sessions s
            JOIN respondents r ON r.id = s.respondent_id
            JOIN company_benchmarks cb ON cb.company_id = s.company_id
            WHERE s.id = %s
            """,
            (session_id,),
        )
        source, company_id, company_cluster_id = cur.fetchone()
        assert source == "real"  # backfill attached a real respondent
        assert company_id is not None
        assert company_cluster_id is not None  # company-grain persona stamped
