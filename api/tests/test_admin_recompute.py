import uuid

import psycopg
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from api import admin
from api.main import app
from playbook_shared.analytics.pipeline import RecomputeSummary

client = TestClient(app)


def test_admin_recompute_requires_configured_token(monkeypatch):
    monkeypatch.delenv("ADMIN_RECOMPUTE_TOKEN", raising=False)
    resp = client.post("/admin/recompute")
    assert resp.status_code == 503


def test_admin_recompute_rejects_invalid_token(monkeypatch):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")
    resp = client.post("/admin/recompute", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_admin_recompute_runs_with_valid_token(monkeypatch):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")

    def fake_recompute():
        return RecomputeSummary(
            respondents_processed=3,
            run_id="run-1",
            company_benchmarks_written=2,
            function_entities=3,
            function_clusters=2,
            function_silhouette=0.42,
            function_benchmarks_written=3,
            company_entities=2,
            company_clusters=2,
            company_silhouette=0.4,
        )

    monkeypatch.setattr(admin, "recompute", fake_recompute)
    resp = client.post("/admin/recompute", headers={"Authorization": "Bearer secret"})

    assert resp.status_code == 200
    assert resp.json()["run_id"] == "run-1"
    assert resp.json()["function_clusters"] == 2


def test_admin_demo_status_requires_session_id(monkeypatch):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")
    resp = client.get("/admin/demo/status", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 400


def test_admin_demo_status_returns_readiness(chat_db, monkeypatch):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")
    session_id, _respondent_id = _analytics_fixture(chat_db)

    resp = client.get(
        f"/admin/demo/status?session_id={session_id}",
        headers={"Authorization": "Bearer secret"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["session"]["id"] == str(session_id)
    assert body["coverage"]["filled_must_fill"] >= 1
    assert body["documents"]["parsed"] == 1
    assert body["relays"]["sent"] == 1
    assert body["reports"]["prospect"]["id"]
    assert body["analytics"]["benchmark"]["percentile_cohort"] == 73.0


def test_admin_demo_status_rejects_unknown_session(chat_db, monkeypatch):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")
    resp = client.get(
        f"/admin/demo/status?session_id={uuid.uuid4()}",
        headers={"Authorization": "Bearer secret"},
    )
    assert resp.status_code == 404


def _analytics_fixture(chat_db):
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    session_id = uuid.uuid4()
    neighbor_id = uuid.uuid4()
    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO companies (id, name, industry, size_bucket) VALUES (%s, %s, %s, %s)",
            (company_id, "Demo Co", "Software", "201-1000"),
        )
        cur.execute(
            """
            INSERT INTO respondents (id, company_id, name, role, email, source)
            VALUES
              (%s, %s, 'Jordan', 'Controller', 'jordan@example.com', 'real'),
              (%s, %s, 'Synthetic Neighbor', 'Controller', 'synthetic@example.com', 'synthetic')
            """,
            (respondent_id, company_id, neighbor_id, company_id),
        )
        cur.execute(
            """
            INSERT INTO sessions (id, company_id, respondent_id, status, script_version)
            VALUES (%s, %s, %s, 'in_progress', 'test')
            """,
            (session_id, company_id, respondent_id),
        )
        cur.execute(
            """
            INSERT INTO answers (session_id, slot_key, raw_text, structured_json, confidence, source)
            VALUES (%s, 'ctx.role', 'Controller', '{"value": "Controller"}', 0.9, 'chat')
            """,
            (session_id,),
        )
        cur.execute(
            """
            INSERT INTO documents (company_id, session_id, filename, doc_type, storage_url, parsed_text, status)
            VALUES (%s, %s, 'budget.csv', 'budget', '/tmp/budget.csv', 'budget rows', 'parsed')
            """,
            (company_id, session_id),
        )
        cur.execute(
            """
            INSERT INTO email_relays (session_id, slot_key, token, sent_to_email, status)
            VALUES (%s, 'pain.manual_hours', %s, 'colleague@example.com', 'sent')
            """,
            (session_id, uuid.uuid4()),
        )
        cur.execute(
            """
            INSERT INTO reports (session_id, type, content_json, rendered_md)
            VALUES (%s, 'prospect', '{}', 'roadmap')
            """,
            (session_id,),
        )
        cur.execute(
            """
            INSERT INTO cluster_runs (algorithm, params, n_clusters, silhouette_score)
            VALUES ('test', '{}', 1, 0.33)
            RETURNING id
            """
        )
        run_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO clusters
              (run_id, label, size, avg_maturity, common_pain_points, common_tech_stack, summary, community_id)
            VALUES (%s, 'Demo Controllers', 2, 3.4, '[]', '[]', 'Demo cluster', 1)
            RETURNING id
            """,
            (run_id,),
        )
        cluster_id = cur.fetchone()[0]
        vector = "[" + ",".join(["0.01"] * 1536) + "]"
        cur.execute(
            """
            INSERT INTO respondent_embeddings (respondent_id, embedding, feature_vector, umap_x, umap_y, model)
            VALUES
              (%s, %s::vector, '{}', 1.0, 2.0, 'test'),
              (%s, %s::vector, '{}', 1.5, 2.5, 'test')
            """,
            (respondent_id, vector, neighbor_id, vector),
        )
        cur.execute(
            """
            INSERT INTO benchmarks
              (respondent_id, run_id, cluster_id, maturity_score, percentile_cohort,
               percentile_cluster, nearest_neighbor_ids)
            VALUES
              (%s, %s, %s, 3.7, 73.0, 65.0, %s),
              (%s, %s, %s, 3.5, 60.0, 55.0, '[]')
            """,
            (respondent_id, run_id, cluster_id, Jsonb([str(neighbor_id)]), neighbor_id, run_id, cluster_id),
        )
        conn.commit()
    return session_id, respondent_id
