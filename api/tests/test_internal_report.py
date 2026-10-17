"""Internal macro intelligence (Task 8.4): admin-gated, grounded in the vendor
capability doc, product-fit categories enforced."""

from __future__ import annotations

import psycopg
from fastapi.testclient import TestClient

from api import openai_client, report_generation
from api.main import app

client = TestClient(app)

INTERNAL_MD = """## Cohort Overview
150 companies, average maturity 2.9/5 across 6 clusters.

## Ranked Pain Themes
1. Manual reconciliation hours (largest weighted theme)
2. Slow multi-entity consolidation

## Product Fit Mapping
- Manual reconciliation hours — Current product: automated reconciliation via the matching engine.
- Slow multi-entity consolidation — Current product: multi-ERP consolidation engine.
- Bespoke board reporting narratives — Roadmap candidate: no narrative-generation capability in the document.
- Payroll processing — Third-party: out of platform scope.

## Buying Personas
Controller-led buying committees; ROI-first evaluation with IT sign-off.

## Market Scoping
Manual-heavy mid-market controllers are the largest underserved segment.

## Investor Narrative
A growing cohort with concentrated, recurring pain the current product already covers.
"""


def _seed_cohort(chat_db) -> None:
    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO cluster_runs (algorithm, params, n_clusters, silhouette_score) "
            "VALUES ('test', '{}', 2, 0.35) RETURNING id"
        )
        run_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO clusters (run_id, label, buying_persona, size, avg_maturity,
                                  common_pain_points, common_tech_stack, summary)
            VALUES
              (%s, 'Manual-heavy controllers', 'Controller-led committee', 90, 2.4,
               '[{"slot_key": "pain.manual_hours", "count": 50, "score": 180}]', '["excel"]', 's1'),
              (%s, 'Automation-forward FP&A', 'FP&A-led evaluation', 60, 3.6,
               '[{"slot_key": "pain.error_cost", "count": 20, "score": 60}]', '["sql"]', 's2')
            """,
            (run_id, run_id),
        )
        conn.commit()


def test_internal_report_requires_admin_token(chat_db, monkeypatch):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")
    assert client.post("/reports/internal").status_code == 401
    assert client.get("/reports/internal/latest").status_code == 401


def test_internal_report_grounded_in_capability_doc(chat_db, monkeypatch):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")
    _seed_cohort(chat_db)

    captured: dict = {}

    async def fake_complete(messages):
        captured["messages"] = messages
        return INTERNAL_MD

    monkeypatch.setattr(openai_client, "complete_report", fake_complete)
    resp = client.post("/reports/internal", headers={"Authorization": "Bearer secret"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "internal_macro"
    assert "## Product Fit Mapping" in body["rendered_md"]
    assert body["content_json"]["clusters"][0]["buying_persona"] == "Controller-led committee"
    # Cohort-growth trend rides along (Task 8.5), oldest run first.
    assert len(body["content_json"]["run_history"]) == 1
    assert body["content_json"]["run_history"][0]["n_clusters"] == 2

    system = captured["messages"][0]["content"]
    # The real capability doc is injected into the prompt (grounding).
    assert "VENDOR CAPABILITY DOCUMENT" in system
    assert "Reconciliation and matching" in system
    assert "Current product" in system and "Roadmap candidate" in system and "Third-party" in system

    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute("SELECT session_id, company_id FROM reports WHERE type = 'internal_macro'")
        assert cur.fetchone() == (None, None)  # cohort-wide, not session/company scoped

    latest = client.get("/reports/internal/latest", headers={"Authorization": "Bearer secret"})
    assert latest.status_code == 200
    assert latest.json()["id"] == body["id"]


def test_internal_report_rejects_missing_fit_categories(chat_db, monkeypatch):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")
    _seed_cohort(chat_db)
    bad_md = INTERNAL_MD.replace("Current product", "covered").replace("Roadmap candidate", "gap").replace(
        "Third-party", "elsewhere"
    )

    async def fake_complete(messages):
        return bad_md

    monkeypatch.setattr(openai_client, "complete_report", fake_complete)
    resp = client.post("/reports/internal", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 502
    assert "fit categories" in resp.json()["detail"]


def test_internal_report_fails_clearly_without_capability_doc(chat_db, monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")
    monkeypatch.setattr(report_generation, "CAPABILITIES_PATH", tmp_path / "missing.md")
    resp = client.post("/reports/internal", headers={"Authorization": "Bearer secret"})
    assert resp.status_code == 502
    assert "capability document not found" in resp.json()["detail"]