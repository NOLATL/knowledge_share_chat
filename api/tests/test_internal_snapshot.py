"""Internal destination snapshot (redesign Phase 4): grain-scoped personas with
named members for the persona -> member drill-down."""

from __future__ import annotations

import uuid

import psycopg
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

FPA_KEY = "Financial Planning & Analysis (FP&A)"


def _seed(chat_db) -> dict:
    ids = {
        "company": uuid.uuid4(),
        "fn_cluster": None,
        "co_cluster": None,
    }
    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO companies (id, name, industry) VALUES (%s, 'Acme', 'Manufacturing')",
            (ids["company"],),
        )
        cur.execute(
            "INSERT INTO cluster_runs (algorithm, params, n_clusters, silhouette_score) "
            "VALUES ('test', '{}', 2, 0.4) RETURNING id"
        )
        run_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO clusters (run_id, label, grain, size, avg_maturity,
                                  common_pain_points, common_tech_stack, summary, buying_persona)
            VALUES
              (%s, 'CFOs Navigating Compliance Challenges', 'function', 3, 2.8,
               '[{"slot_key": "pain.audit_burden", "count": 3, "score": 12.5}]', '["excel"]',
               'fn persona', 'Compliance-first buyers'),
              (%s, 'Manual-heavy manufacturers', 'company', 2, 2.5,
               '[{"slot_key": "pain.manual_hours", "count": 2, "score": 9.0}]', '["excel"]',
               'co persona', 'Ops-led buying')
            RETURNING id
            """,
            (run_id, run_id),
        )
        rows = cur.fetchall()
        # RETURNING with multi-VALUES yields both ids in order.
        ids["fn_cluster"], ids["co_cluster"] = rows[0][0], rows[1][0]
        cur.execute(
            """
            INSERT INTO function_benchmarks
              (company_id, function_key, run_id, respondent_count, avg_maturity,
               percentile_cohort, percentile_peer, peer_group, cluster_id,
               common_pain_points, common_tech_stack)
            VALUES (%s, %s, %s, 2, 2.8, 60.0, 55.0, '{"function_key": "FP&A"}', %s, '[]', '[]')
            """,
            (ids["company"], FPA_KEY, run_id, ids["fn_cluster"]),
        )
        cur.execute(
            """
            INSERT INTO company_benchmarks
              (company_id, run_id, respondent_count, avg_maturity, percentile_cohort,
               percentile_peer, peer_group, cluster_exposure, common_pain_points,
               common_tech_stack, company_cluster_id)
            VALUES (%s, %s, 2, 2.5, 50.0, 45.0, '{}', '{}', '[]', '[]', %s)
            """,
            (ids["company"], run_id, ids["co_cluster"]),
        )
        cur.execute(
            "INSERT INTO entity_embeddings (grain, entity_key, run_id, umap_x, umap_y, model) "
            "VALUES ('function', %s, %s, 1.5, 2.5, 'test')",
            (f"{ids['company']}:{FPA_KEY}", run_id),
        )
        conn.commit()
    return ids


def test_internal_snapshot_requires_admin(chat_db, monkeypatch):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")
    assert client.get("/admin/internal").status_code == 401


def test_internal_snapshot_groups_members_by_grain_persona(chat_db, monkeypatch):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")
    ids = _seed(chat_db)

    body = client.get("/admin/internal", headers={"Authorization": "Bearer secret"}).json()

    assert body["run"]["n_clusters"] == 2

    fn_scope = body["scopes"]["function"]
    assert len(fn_scope["clusters"]) == 1
    persona = fn_scope["clusters"][0]
    assert persona["label"] == "CFOs Navigating Compliance Challenges"
    assert persona["buying_persona"] == "Compliance-first buyers"
    member = persona["members"][0]
    assert member["company_id"] == str(ids["company"])
    assert member["company_name"] == "Acme"
    assert member["function_key"] == FPA_KEY
    assert member["percentile_peer"] == 55.0
    assert member["umap_x"] == 1.5  # entity coords ride along for the map viz

    co_scope = body["scopes"]["company"]
    assert len(co_scope["clusters"]) == 1
    co_member = co_scope["clusters"][0]["members"][0]
    assert co_member["company_name"] == "Acme"
    assert co_member["function_key"] is None

    # Pressure ranking per grain, from persona pain scores.
    assert fn_scope["pressure"][0] == {"slot_key": "pain.audit_burden", "score": 12.5}
    assert co_scope["pressure"][0] == {"slot_key": "pain.manual_hours", "score": 9.0}


def test_internal_snapshot_empty_without_runs(chat_db, monkeypatch):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")
    body = client.get("/admin/internal", headers={"Authorization": "Bearer secret"}).json()
    assert body["run"] is None
    assert body["scopes"]["function"]["clusters"] == []
