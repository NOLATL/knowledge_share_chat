"""Multi-grain analytics (redesign Phase 2, Fork B): recompute clusters and
benchmarks separately at the function and company grain."""

from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb

from playbook_shared.analytics.pipeline import recompute
from playbook_shared.migrate import run_migrations
from playbook_shared.question_bank import reseed_questions

# Two companies, each with an Accounting and an FP&A function (one session each).
FUNCTIONS = [("Acme", "Accounting"), ("Acme", "FP&A"), ("Beta", "Accounting"), ("Beta", "FP&A")]
ANSWERS = [
    ("ctx.role", "Controller"),
    ("close.days", "Close takes 10 days"),
    ("sys.erp", "NetSuite"),
    ("pain.manual_hours", "100 manual hours"),
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


def _no_llm(prompt, model=None):
    raise RuntimeError("no LLM in tests — heuristic fallback expected")


def _seed_functions(url: str) -> None:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        company_ids: dict[str, str] = {}
        for name in ("Acme", "Beta"):
            cur.execute(
                "INSERT INTO companies (name, industry, headcount_band) "
                "VALUES (%s, 'Manufacturing', '201-1000') RETURNING id",
                (name,),
            )
            company_ids[name] = cur.fetchone()[0]
        for name, function_key in FUNCTIONS:
            company_id = company_ids[name]
            cur.execute(
                "INSERT INTO respondents (company_id, name, role, email, source) "
                "VALUES (%s, %s, 'Controller', %s, 'real') RETURNING id",
                (company_id, f"{name} {function_key}", f"{name}.{function_key}@x.example"),
            )
            respondent_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO sessions (company_id, respondent_id, function_key, status, script_version) "
                "VALUES (%s, %s, %s, 'complete', 'test') RETURNING id",
                (company_id, respondent_id, function_key),
            )
            session_id = cur.fetchone()[0]
            for slot_key, value in ANSWERS:
                cur.execute(
                    "INSERT INTO answers (session_id, slot_key, raw_text, structured_json, confidence, source) "
                    "VALUES (%s, %s, %s, %s, 0.9, 'chat')",
                    (session_id, slot_key, value, Jsonb({"value": value})),
                )
        conn.commit()


def test_recompute_writes_function_and_company_grain(fresh_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db_url)
    monkeypatch.setattr("playbook_shared.analytics.openai_ops.label_cluster", _no_llm)
    run_migrations(fresh_db_url)
    reseed_questions(fresh_db_url)
    _seed_functions(fresh_db_url)

    summary = recompute(embedding_fn=_embedding_fn, enforce_gate=False)

    assert summary.function_entities == 4
    assert summary.company_entities == 2
    assert summary.function_benchmarks_written == 4

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        # One function_benchmarks row per (company, function), each with a persona.
        cur.execute("SELECT count(*) FROM function_benchmarks")
        assert cur.fetchone()[0] == 4
        cur.execute("SELECT count(*) FROM function_benchmarks WHERE cluster_id IS NOT NULL")
        assert cur.fetchone()[0] == 4

        # Grain-tagged personas exist at both new grains.
        cur.execute("SELECT count(*) FROM clusters WHERE grain = 'function'")
        assert cur.fetchone()[0] >= 1
        cur.execute("SELECT count(*) FROM clusters WHERE grain = 'company'")
        assert cur.fetchone()[0] >= 1

        # Every company got a company-grain persona stamped on its rollup row.
        cur.execute("SELECT count(*) FROM company_benchmarks WHERE company_cluster_id IS NOT NULL")
        assert cur.fetchone()[0] == 2

        # Function entities have embeddings + UMAP coords.
        cur.execute("SELECT count(*) FROM entity_embeddings WHERE grain = 'function' AND umap_x IS NOT NULL")
        assert cur.fetchone()[0] == 4

        # Peer grouping is by same function_key across companies.
        cur.execute("SELECT DISTINCT peer_group->>'function_key' FROM function_benchmarks ORDER BY 1")
        assert [r[0] for r in cur.fetchall()] == ["Accounting", "FP&A"]
