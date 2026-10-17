"""Database access for generated reports."""

from __future__ import annotations

import uuid
from typing import Any

from psycopg.types.json import Jsonb

from playbook_shared.db import connect


def _conn():
    return connect(register_vector_types=False)


def list_companies(*, include_synthetic: bool = False) -> list[dict[str, Any]]:
    """Company directory for the external-deliverable picker, newest benchmark attached.

    Only companies that were actually assessed (have at least one answer) are
    listed — session backfill creates empty demo shells that are pure noise here.
    """
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.id, c.account_code, c.name, c.industry, c.size_bucket, c.headcount_band,
                   c.revenue_band, c.years_in_business, c.created_at,
                   bool_or(r.source = 'real') AS has_real,
                   count(DISTINCT r.id) AS respondent_count,
                   cb.avg_maturity, cb.percentile_cohort, cb.percentile_peer, cb.computed_at
            FROM companies c
            LEFT JOIN respondents r ON r.company_id = c.id
            LEFT JOIN LATERAL (
                SELECT avg_maturity, percentile_cohort, percentile_peer, computed_at
                FROM company_benchmarks
                WHERE company_id = c.id
                ORDER BY computed_at DESC, id DESC
                LIMIT 1
            ) cb ON true
            WHERE EXISTS (
                SELECT 1
                FROM sessions s
                JOIN answers a ON a.session_id = s.id
                WHERE s.company_id = c.id
            )
            GROUP BY c.id, c.account_code, c.name, c.industry, c.size_bucket, c.headcount_band,
                     c.revenue_band, c.years_in_business, c.created_at,
                     cb.avg_maturity, cb.percentile_cohort, cb.percentile_peer, cb.computed_at
            HAVING (%s OR bool_or(r.source = 'real'))
            ORDER BY c.created_at DESC, c.id
            LIMIT 200
            """,
            (include_synthetic,),
        )
        cols = (
            "id", "account_code", "name", "industry", "size_bucket", "headcount_band",
            "revenue_band", "years_in_business", "created_at", "has_real_respondents",
            "respondent_count", "avg_maturity", "percentile_cohort", "percentile_peer",
            "benchmark_computed_at",
        )
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def company_id_by_account_code(account_code: str) -> uuid.UUID | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM companies WHERE account_code = %s", (account_code.strip().upper(),))
        row = cur.fetchone()
    return row[0] if row else None


def load_company_report_context(company_id: uuid.UUID | str) -> dict[str, Any] | None:
    """Aggregate a company's sessions into one report context (Task 8.3).

    Latest answer per slot wins across all the company's sessions/respondents.
    """
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, account_code, name, industry, size_bucket, headcount_band,
                   revenue_band, years_in_business
            FROM companies WHERE id = %s
            """,
            (str(company_id),),
        )
        company = cur.fetchone()
        if company is None:
            return None

        cur.execute(
            "SELECT id, name, role, email, source FROM respondents WHERE company_id = %s ORDER BY created_at",
            (str(company_id),),
        )
        respondents = [
            {"id": r[0], "name": r[1], "role": r[2], "email": r[3], "source": r[4]}
            for r in cur.fetchall()
        ]

        # Latest answer per slot WITHIN each function (multi-grain redesign):
        # attribution (function + who said it) is preserved instead of flattening
        # the whole company into one anonymous voice.
        cur.execute(
            """
            SELECT DISTINCT ON (COALESCE(s.function_key, ''), a.slot_key)
                   COALESCE(s.function_key, '') AS function_key,
                   a.slot_key, q.category, q.text, q.tier, a.raw_text,
                   a.structured_json, a.confidence, a.source, a.created_at,
                   r.name, r.role
            FROM answers a
            JOIN sessions s ON s.id = a.session_id
            LEFT JOIN respondents r ON r.id = s.respondent_id
            LEFT JOIN questions q ON q.slot_key = a.slot_key
            WHERE s.company_id = %s
            ORDER BY COALESCE(s.function_key, ''), a.slot_key, a.created_at DESC, a.id DESC
            """,
            (str(company_id),),
        )
        answers_by_function: dict[str, list[dict[str, Any]]] = {}
        for r in cur.fetchall():
            answers_by_function.setdefault(r[0], []).append(
                {
                    "slot_key": r[1],
                    "category": r[2],
                    "question": r[3],
                    "tier": r[4],
                    "raw_text": r[5],
                    "structured_json": r[6],
                    "confidence": r[7],
                    "source": r[8],
                    "created_at": r[9],
                    "function_key": r[0] or None,
                    "respondent_name": r[10],
                    "respondent_role": r[11],
                }
            )
        # Company-level view: latest per slot across all functions (exec rollup).
        latest_by_slot: dict[str, dict[str, Any]] = {}
        for rows in answers_by_function.values():
            for answer in rows:
                current = latest_by_slot.get(answer["slot_key"])
                if current is None or answer["created_at"] > current["created_at"]:
                    latest_by_slot[answer["slot_key"]] = answer
        answers = sorted(latest_by_slot.values(), key=lambda a: a["slot_key"])

        # Latest function benchmark + function-grain persona per function.
        cur.execute(
            """
            SELECT DISTINCT ON (fb.function_key)
                   fb.function_key, fb.respondent_count, fb.avg_maturity,
                   fb.percentile_cohort, fb.percentile_peer, fb.peer_group,
                   fb.cluster_id, fb.common_pain_points, fb.common_tech_stack,
                   fb.computed_at, cl.label, cl.summary, cl.buying_persona
            FROM function_benchmarks fb
            LEFT JOIN clusters cl ON cl.id = fb.cluster_id
            WHERE fb.company_id = %s
            ORDER BY fb.function_key, fb.computed_at DESC, fb.id DESC
            """,
            (str(company_id),),
        )
        function_benchmarks = {
            r[0]: {
                "respondent_count": r[1],
                "avg_maturity": r[2],
                "percentile_cohort": r[3],
                "percentile_peer": r[4],
                "peer_group": r[5],
                "cluster_id": r[6],
                "common_pain_points": r[7],
                "common_tech_stack": r[8],
                "computed_at": r[9],
                "persona_label": r[10],
                "persona_summary": r[11],
                "buying_persona": r[12],
            }
            for r in cur.fetchall()
        }

        # Who contributed to each function.
        cur.execute(
            """
            SELECT DISTINCT COALESCE(s.function_key, ''), r.id, r.name, r.role, r.email, r.source
            FROM sessions s
            LEFT JOIN respondents r ON r.id = s.respondent_id
            WHERE s.company_id = %s AND r.id IS NOT NULL
            """,
            (str(company_id),),
        )
        respondents_by_function: dict[str, list[dict[str, Any]]] = {}
        for r in cur.fetchall():
            respondents_by_function.setdefault(r[0], []).append(
                {"id": r[1], "name": r[2], "role": r[3], "email": r[4], "source": r[5]}
            )

        function_keys = sorted(
            {k for k in (*answers_by_function, *function_benchmarks, *respondents_by_function) if k}
        )
        functions = [
            {
                "function_key": key,
                "respondents": respondents_by_function.get(key, []),
                "answers": answers_by_function.get(key, []),
                "benchmark": function_benchmarks.get(key),
            }
            for key in function_keys
        ]

        cur.execute(
            """
            SELECT filename, doc_type, status, left(coalesce(parsed_text, ''), 1600), created_at
            FROM documents
            WHERE company_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT 5
            """,
            (str(company_id),),
        )
        documents = [
            {"filename": r[0], "doc_type": r[1], "status": r[2], "excerpt": r[3], "created_at": r[4]}
            for r in cur.fetchall()
        ]

        cur.execute(
            """
            SELECT cb.run_id, cb.respondent_count, cb.avg_maturity, cb.percentile_cohort,
                   cb.percentile_peer, cb.peer_group, cb.primary_cluster_id, cb.cluster_exposure,
                   cb.common_pain_points, cb.common_tech_stack, cb.computed_at,
                   cl.label, cl.summary,
                   cc.label, cc.summary, cc.buying_persona
            FROM company_benchmarks cb
            LEFT JOIN clusters cl ON cl.id = cb.primary_cluster_id
            LEFT JOIN clusters cc ON cc.id = cb.company_cluster_id
            WHERE cb.company_id = %s
            ORDER BY cb.computed_at DESC, cb.id DESC
            LIMIT 1
            """,
            (str(company_id),),
        )
        b = cur.fetchone()
        benchmark = (
            {
                "run_id": b[0],
                "respondent_count": b[1],
                "avg_maturity": b[2],
                "percentile_cohort": b[3],
                "percentile_peer": b[4],
                "peer_group": b[5],
                "primary_cluster_id": b[6],
                "cluster_exposure": b[7],
                "common_pain_points": b[8],
                "common_tech_stack": b[9],
                "computed_at": b[10],
                "primary_cluster_label": b[11],
                "primary_cluster_summary": b[12],
                # Company-grain persona (multi-grain redesign).
                "company_persona_label": b[13],
                "company_persona_summary": b[14],
                "company_buying_persona": b[15],
            }
            if b is not None
            else None
        )

    return {
        "company": {
            "id": company[0],
            "account_code": company[1],
            "name": company[2],
            "industry": company[3],
            "size_bucket": company[4],
            "headcount_band": company[5],
            "revenue_band": company[6],
            "years_in_business": company[7],
        },
        "respondents": respondents,
        "answers": answers,
        "functions": functions,
        "documents": documents,
        "company_benchmark": benchmark,
        "benchmark_history": company_benchmark_history(company_id),
    }


def cohort_map_points(company_id: uuid.UUID | str) -> dict[str, list[dict[str, Any]]]:
    """Per-entity points for the external evaluation charts, latest run only,
    anonymized — persona label + stats per point, never another member's name.

    company: one point per company in the selected company's firmographic
    cohort (same industry + size band as the peer-percentile rule, whole
    cohort when there are too few peers), colored by company-grain persona.
    function: one point per (company, function) entity with its function-grain
    persona; the client filters to the selected function.
    """
    out: dict[str, list[dict[str, Any]]] = {"company": [], "function": []}
    cid = str(company_id)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM cluster_runs ORDER BY created_at DESC LIMIT 1")
        run = cur.fetchone()
        if run is None:
            return out

        cur.execute(
            """
            SELECT cb.company_id, cb.avg_maturity, cb.common_pain_points, cl.label,
                   lower(trim(coalesce(c.industry, ''))) AS industry_key,
                   lower(trim(coalesce(c.headcount_band, c.size_bucket, ''))) AS size_key
            FROM company_benchmarks cb
            JOIN companies c ON c.id = cb.company_id
            LEFT JOIN clusters cl ON cl.id = cb.company_cluster_id
            WHERE cb.run_id = %s
            """,
            (run[0],),
        )
        rows = cur.fetchall()
        me = next((r for r in rows if str(r[0]) == cid), None)
        peers = [r for r in rows if me is not None and (r[4], r[5]) == (me[4], me[5])]
        if len(peers) < 3:  # mirrors pipeline.PEER_MIN's whole-cohort fallback
            peers = rows
        out["company"] = [_map_point(r, is_self=str(r[0]) == cid) for r in peers]

        cur.execute(
            """
            SELECT fb.company_id, fb.avg_maturity, fb.common_pain_points, cl.label, fb.function_key
            FROM function_benchmarks fb
            LEFT JOIN clusters cl ON cl.id = fb.cluster_id
            WHERE fb.run_id = %s
            """,
            (run[0],),
        )
        out["function"] = [
            {**_map_point(r, is_self=str(r[0]) == cid), "function_key": r[4]} for r in cur.fetchall()
        ]
    return out


def _map_point(row: tuple, *, is_self: bool) -> dict[str, Any]:
    pain_load = sum(float(p.get("score") or p.get("count") or 0) for p in (row[2] or []))
    return {
        "maturity": float(row[1]) if row[1] is not None else None,
        "pain_load": round(pain_load, 3),
        "persona": row[3],
        "is_self": is_self,
    }


def company_benchmark_history(company_id: uuid.UUID | str) -> list[dict[str, Any]]:
    """A company's placement across all recompute runs, oldest first (Task 8.5).

    The append-only company_benchmarks history is what makes 'you moved from the
    40th to the 55th percentile as the cohort grew' computable — the recurring
    touch-point hook.
    """
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT cb.run_id, cb.respondent_count, cb.avg_maturity, cb.percentile_cohort,
                   cb.percentile_peer, cb.peer_group, cb.computed_at, cl.label
            FROM company_benchmarks cb
            LEFT JOIN clusters cl ON cl.id = cb.primary_cluster_id
            WHERE cb.company_id = %s
            ORDER BY cb.computed_at ASC, cb.id ASC
            """,
            (str(company_id),),
        )
        cols = (
            "run_id", "respondent_count", "avg_maturity", "percentile_cohort",
            "percentile_peer", "peer_group", "computed_at", "primary_cluster_label",
        )
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def load_internal_context() -> dict[str, Any]:
    """Cohort-wide inputs for the internal macro intelligence view (Task 8.4)."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, algorithm, n_clusters, silhouette_score, created_at "
            "FROM cluster_runs ORDER BY created_at DESC LIMIT 1"
        )
        run = cur.fetchone()
        clusters: list[dict[str, Any]] = []
        companies: dict[str, Any] = {}
        if run is not None:
            cur.execute(
                """
                SELECT id, label, buying_persona, size, avg_maturity,
                       common_pain_points, common_tech_stack, summary
                FROM clusters
                WHERE run_id = %s
                ORDER BY size DESC, label
                """,
                (run[0],),
            )
            rows = cur.fetchall()
            total = sum(row[3] or 0 for row in rows)
            clusters = [
                {
                    "id": row[0],
                    "label": row[1],
                    "buying_persona": row[2],
                    "size": row[3],
                    "share_of_cohort": round((row[3] or 0) / total * 100, 1) if total else 0.0,
                    "avg_maturity": row[4],
                    "common_pain_points": row[5],
                    "common_tech_stack": row[6],
                    "summary": row[7],
                }
                for row in rows
            ]
            cur.execute(
                """
                SELECT count(*), avg(avg_maturity),
                       count(*) FILTER (WHERE (peer_group->>'fell_back')::boolean = false)
                FROM company_benchmarks
                WHERE run_id = %s
                """,
                (run[0],),
            )
            c = cur.fetchone()
            companies = {
                "count": c[0],
                "avg_maturity": float(c[1]) if c[1] is not None else None,
                "with_real_peer_group": c[2],
            }

        # Cohort growth across runs (Task 8.5) — the trend/touch-point signal.
        cur.execute(
            """
            SELECT cr.id, cr.created_at, cr.n_clusters, cr.silhouette_score,
                   count(DISTINCT b.respondent_id) AS respondents,
                   count(DISTINCT cb.company_id) AS companies
            FROM cluster_runs cr
            LEFT JOIN benchmarks b ON b.run_id = cr.id
            LEFT JOIN company_benchmarks cb ON cb.run_id = cr.id
            GROUP BY cr.id, cr.created_at, cr.n_clusters, cr.silhouette_score
            ORDER BY cr.created_at ASC
            """
        )
        run_history = [
            {
                "run_id": row[0],
                "created_at": row[1],
                "n_clusters": row[2],
                "silhouette_score": row[3],
                "respondents": row[4],
                "companies": row[5],
            }
            for row in cur.fetchall()
        ]

    return {
        "run_history": run_history,
        "latest_run": {
            "id": run[0],
            "algorithm": run[1],
            "n_clusters": run[2],
            "silhouette_score": run[3],
            "created_at": run[4],
        }
        if run is not None
        else None,
        "clusters": clusters,
        "companies": companies,
    }


def latest_internal_report() -> dict[str, Any] | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, session_id, company_id, type, content_json, rendered_md, created_at
            FROM reports
            WHERE type = 'internal_macro'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
    return _report_row(row) if row is not None else None


def insert_report(
    *,
    session_id: uuid.UUID | str | None,
    report_type: str,
    content_json: dict[str, Any],
    rendered_md: str,
    company_id: uuid.UUID | str | None = None,
    function_key: str | None = None,
) -> dict[str, Any]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO reports (session_id, company_id, function_key, type, content_json, rendered_md)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, session_id, company_id, type, content_json, rendered_md, created_at
            """,
            (
                str(session_id) if session_id else None,
                str(company_id) if company_id else None,
                function_key,
                report_type,
                Jsonb(content_json),
                rendered_md,
            ),
        )
        row = cur.fetchone()
        conn.commit()
    return _report_row(row)


def latest_function_report(company_id: uuid.UUID | str, function_key: str) -> dict[str, Any] | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, session_id, company_id, type, content_json, rendered_md, created_at
            FROM reports
            WHERE company_id = %s AND function_key = %s AND type = 'function_external'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (str(company_id), function_key),
        )
        row = cur.fetchone()
    return _report_row(row) if row is not None else None


def latest_company_report(company_id: uuid.UUID | str, report_type: str) -> dict[str, Any] | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, session_id, company_id, type, content_json, rendered_md, created_at
            FROM reports
            WHERE company_id = %s AND type = %s
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (str(company_id), report_type),
        )
        row = cur.fetchone()
    return _report_row(row) if row is not None else None


def _report_row(row) -> dict[str, Any]:
    return {
        "id": row[0],
        "session_id": row[1],
        "company_id": row[2],
        "type": row[3],
        "content_json": row[4],
        "rendered_md": row[5],
        "created_at": row[6],
    }
