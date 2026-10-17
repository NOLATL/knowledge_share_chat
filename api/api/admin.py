"""Admin-only analytics controls."""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.concurrency import run_in_threadpool

from playbook_shared.analytics import recompute
from playbook_shared.db import connect

router = APIRouter(prefix="/admin")


def _require_admin(authorization: str | None) -> None:
    token = os.environ.get("ADMIN_RECOMPUTE_TOKEN")
    if not token:
        raise HTTPException(status_code=503, detail="ADMIN_RECOMPUTE_TOKEN is not set")
    if authorization != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="invalid admin token")


@router.post("/recompute")
async def post_recompute(authorization: str | None = Header(default=None)) -> dict:
    _require_admin(authorization)
    summary = await run_in_threadpool(recompute)
    return {
        "respondents_processed": summary.respondents_processed,
        "run_id": summary.run_id,
        "company_benchmarks_written": summary.company_benchmarks_written,
        "function_entities": summary.function_entities,
        "function_clusters": summary.function_clusters,
        "function_silhouette": summary.function_silhouette,
        "function_benchmarks_written": summary.function_benchmarks_written,
        "company_entities": summary.company_entities,
        "company_clusters": summary.company_clusters,
        "company_silhouette": summary.company_silhouette,
    }


@router.get("/internal")
async def get_internal(authorization: str | None = Header(default=None)) -> dict:
    _require_admin(authorization)
    return await run_in_threadpool(_internal_snapshot)


def _internal_snapshot() -> dict:
    """The internal destination's cohort view (redesign Phase 4): grain-tagged
    personas with their named members (persona -> member drill-down), plus a
    per-grain pressure ranking. Grains: 'function' and 'company'."""
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, n_clusters, silhouette_score, created_at FROM cluster_runs "
            "ORDER BY created_at DESC LIMIT 1"
        )
        run = cur.fetchone()
        if run is None:
            return {"run": None, "scopes": {"function": _empty_scope(), "company": _empty_scope()}}
        run_id = run[0]

        scopes = {}
        for grain in ("function", "company"):
            cur.execute(
                """
                SELECT id, label, size, avg_maturity, common_pain_points,
                       common_tech_stack, summary, buying_persona
                FROM clusters
                WHERE run_id = %s AND grain = %s
                ORDER BY size DESC
                """,
                (run_id, grain),
            )
            clusters = {
                str(r[0]): {
                    "id": str(r[0]),
                    "label": r[1],
                    "size": r[2],
                    "avg_maturity": _num(r[3]),
                    "common_pain_points": r[4],
                    "common_tech_stack": r[5],
                    "summary": r[6],
                    "buying_persona": r[7],
                    "members": [],
                }
                for r in cur.fetchall()
            }

            if grain == "function":
                cur.execute(
                    """
                    SELECT fb.cluster_id, fb.company_id, c.name, c.account_code,
                           fb.function_key, fb.avg_maturity, fb.percentile_cohort,
                           fb.percentile_peer, ee.umap_x, ee.umap_y
                    FROM function_benchmarks fb
                    JOIN companies c ON c.id = fb.company_id
                    LEFT JOIN entity_embeddings ee
                      ON ee.grain = 'function' AND ee.run_id = fb.run_id
                     AND ee.entity_key = fb.company_id::text || ':' || fb.function_key
                    WHERE fb.run_id = %s
                    """,
                    (run_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT cb.company_cluster_id, cb.company_id, c.name, c.account_code,
                           NULL, cb.avg_maturity, cb.percentile_cohort,
                           cb.percentile_peer, ee.umap_x, ee.umap_y
                    FROM company_benchmarks cb
                    JOIN companies c ON c.id = cb.company_id
                    LEFT JOIN entity_embeddings ee
                      ON ee.grain = 'company' AND ee.run_id = cb.run_id
                     AND ee.entity_key = cb.company_id::text
                    WHERE cb.run_id = %s AND cb.company_cluster_id IS NOT NULL
                    """,
                    (run_id,),
                )
            for r in cur.fetchall():
                cluster = clusters.get(str(r[0]))
                if cluster is None:
                    continue
                cluster["members"].append(
                    {
                        "company_id": str(r[1]),
                        "company_name": r[2],
                        "account_code": r[3],
                        "function_key": r[4],
                        "avg_maturity": _num(r[5]),
                        "percentile_cohort": _num(r[6]),
                        "percentile_peer": _num(r[7]),
                        "umap_x": _num(r[8]),
                        "umap_y": _num(r[9]),
                    }
                )

            # Cohort pressure ranking at this grain: pain scores summed across personas.
            totals: dict[str, float] = {}
            for cluster in clusters.values():
                for pain in cluster["common_pain_points"] or []:
                    key = str(pain.get("slot_key"))
                    totals[key] = totals.get(key, 0.0) + float(pain.get("score") or pain.get("count") or 0)
            pressure = [
                {"slot_key": key, "score": round(score, 3)}
                for key, score in sorted(totals.items(), key=lambda item: -item[1])
            ]
            scopes[grain] = {"clusters": list(clusters.values()), "pressure": pressure}

    return {
        "run": {
            "id": str(run[0]),
            "n_clusters": run[1],
            "silhouette_score": _num(run[2]),
            "created_at": run[3].isoformat(),
        },
        "scopes": scopes,
    }


def _empty_scope() -> dict:
    return {"clusters": [], "pressure": []}


def _num(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


@router.get("/demo/status")
async def get_demo_status(
    authorization: str | None = Header(default=None),
    session_id: UUID | None = Query(default=None),
) -> dict:
    _require_admin(authorization)
    if session_id is None:
        raise HTTPException(status_code=400, detail="session_id is required")
    status = await run_in_threadpool(_demo_status, session_id)
    if status is None:
        raise HTTPException(status_code=404, detail="session not found")
    return status


def _demo_status(session_id: UUID) -> dict | None:
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, s.status, s.resume_token, s.current_slot, s.respondent_id,
                   r.name, r.role, r.email, r.source, c.name, s.company_id
            FROM sessions s
            LEFT JOIN respondents r ON r.id = s.respondent_id
            LEFT JOIN companies c ON c.id = s.company_id
            WHERE s.id = %s
            """,
            (session_id,),
        )
        session = cur.fetchone()
        if session is None:
            return None

        cur.execute("SELECT slot_key FROM questions WHERE active = true AND tier = 'must_fill'")
        must_fill = {row[0] for row in cur.fetchall()}
        cur.execute("SELECT DISTINCT slot_key FROM answers WHERE session_id = %s", (session_id,))
        filled = {row[0] for row in cur.fetchall()}
        filled_must = must_fill & filled

        cur.execute(
            """
            SELECT status, count(*)
            FROM documents
            WHERE session_id = %s
            GROUP BY status
            """,
            (session_id,),
        )
        documents = {status: count for status, count in cur.fetchall()}

        cur.execute(
            """
            SELECT status, count(*)
            FROM email_relays
            WHERE session_id = %s
            GROUP BY status
            """,
            (session_id,),
        )
        relays = {status: count for status, count in cur.fetchall()}

        cur.execute(
            """
            SELECT type, id, created_at
            FROM reports
            WHERE session_id = %s
            ORDER BY created_at DESC
            """,
            (session_id,),
        )
        reports = {}
        for report_type, report_id, created_at in cur.fetchall():
            reports.setdefault(report_type, {"id": report_id, "created_at": created_at})

        cur.execute(
            """
            SELECT id, n_clusters, silhouette_score, created_at
            FROM cluster_runs
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        run = cur.fetchone()

        benchmark = None
        if session[4] is not None and run is not None:
            cur.execute(
                """
                SELECT b.id, c.label, b.maturity_score, b.percentile_cohort,
                       b.percentile_cluster, b.computed_at
                FROM benchmarks b
                LEFT JOIN clusters c ON c.id = b.cluster_id
                WHERE b.respondent_id = %s AND b.run_id = %s
                ORDER BY b.computed_at DESC
                LIMIT 1
                """,
                (session[4], run[0]),
            )
            row = cur.fetchone()
            if row is not None:
                benchmark = {
                    "id": row[0],
                    "cluster_label": row[1],
                    "maturity_score": row[2],
                    "percentile_cohort": row[3],
                    "percentile_cluster": row[4],
                    "computed_at": row[5],
                }

    return _jsonable(
        {
            "session": {
                "id": session[0],
                "status": session[1],
                "resume_token": session[2],
                "current_slot": session[3],
                "respondent_id": session[4],
                "respondent_name": session[5],
                "role": session[6],
                "email": session[7],
                "source": session[8],
                "company_name": session[9],
                "company_id": session[10],
            },
            "coverage": {
                "filled_must_fill": len(filled_must),
                "total_must_fill": len(must_fill),
                "complete_ready": bool(must_fill and must_fill <= filled),
            },
            "documents": {
                "total": sum(documents.values()),
                "parsed": documents.get("parsed", 0),
                "pending": documents.get("pending", 0),
                "error": documents.get("error", 0),
            },
            "relays": {
                "total": sum(relays.values()),
                "sent": relays.get("sent", 0),
                "answered": relays.get("answered", 0),
                "expired": relays.get("expired", 0),
            },
            "reports": {
                "prospect": reports.get("prospect"),
                "vendor": reports.get("vendor"),
            },
            "analytics": {
                "latest_run": None
                if run is None
                else {
                    "id": run[0],
                    "n_clusters": run[1],
                    "silhouette_score": run[2],
                    "created_at": run[3],
                },
                "benchmark": benchmark,
            },
        }
    )


def _jsonable(value):
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value
