"""Database access for Epic 2 analytics."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from psycopg.types.json import Jsonb

from playbook_shared.analytics.models import EntityProfile, RespondentProfile
from playbook_shared.db import connect


def _vec(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


def active_questions() -> list[dict[str, Any]]:
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT slot_key, category, text, tier, order_hint "
            "FROM questions WHERE active = true ORDER BY order_hint, slot_key"
        )
        cols = ("slot_key", "category", "text", "tier", "order_hint")
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def synthetic_email(seed: int, index: int) -> str:
    return f"synthetic+{seed}-{index}@playbook.local"


def synthetic_exists(seed: int, index: int) -> bool:
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM respondents WHERE email = %s LIMIT 1", (synthetic_email(seed, index),))
        return cur.fetchone() is not None


def synthetic_company_id(seed: int, index: int) -> uuid.UUID | None:
    """The company a previously seeded synthetic respondent belongs to."""
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT company_id FROM respondents WHERE email = %s LIMIT 1",
            (synthetic_email(seed, index),),
        )
        row = cur.fetchone()
    return row[0] if row else None


def insert_synthetic_respondent(
    *,
    seed: int,
    index: int,
    company_name: str,
    size_bucket: str,
    role: str,
    answers: dict[str, str],
    script_version: str,
    industry: str | None = None,
    headcount_band: str | None = None,
    revenue_band: str | None = None,
    years_in_business: int | None = None,
    existing_company_id: uuid.UUID | None = None,
    function_key: str | None = None,
) -> uuid.UUID:
    """Insert a synthetic respondent, session, and answer rows.

    When `existing_company_id` is given the respondent joins that company
    (multi-respondent companies for the company-level rollup) instead of
    creating a new one.
    """
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        if existing_company_id is not None:
            company_id = existing_company_id
        else:
            cur.execute(
                """
                INSERT INTO companies
                    (name, industry, size_bucket, headcount_band, revenue_band, years_in_business)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (
                    company_name,
                    industry or "Finance/accounting demo cohort",
                    size_bucket,
                    headcount_band,
                    revenue_band,
                    years_in_business,
                ),
            )
            company_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO respondents (company_id, name, role, email, source)
            VALUES (%s, %s, %s, %s, 'synthetic') RETURNING id
            """,
            (company_id, f"Synthetic respondent {seed}-{index}", role, synthetic_email(seed, index)),
        )
        respondent_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO sessions (company_id, respondent_id, function_key, status, script_version, completed_at)
            VALUES (%s, %s, %s, 'complete', %s, now()) RETURNING id
            """,
            (company_id, respondent_id, function_key, script_version),
        )
        session_id = cur.fetchone()[0]
        for slot_key, value in answers.items():
            cur.execute(
                """
                INSERT INTO answers
                    (session_id, slot_key, raw_text, structured_json, confidence, source)
                VALUES (%s, %s, %s, %s, 0.86, 'chat')
                ON CONFLICT (session_id, slot_key, source) DO NOTHING
                """,
                (session_id, slot_key, value, Jsonb({"value": value})),
            )
        conn.commit()
        return respondent_id


def load_profiles() -> list[RespondentProfile]:
    backfill_real_respondents_for_answered_sessions()
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.id, r.source, r.role, r.company_id,
                   c.industry, COALESCE(c.headcount_band, c.size_bucket),
                   a.slot_key, a.structured_json
            FROM respondents r
            LEFT JOIN companies c ON c.id = r.company_id
            JOIN sessions s ON s.respondent_id = r.id
            JOIN answers a ON a.session_id = s.id
            ORDER BY r.created_at, r.id, a.slot_key
            """
        )
        grouped: dict[str, dict[str, Any]] = {}
        answers: dict[str, dict[str, str]] = defaultdict(dict)
        for respondent_id, source, role, company_id, industry, size_band, slot_key, structured in cur.fetchall():
            rid = str(respondent_id)
            grouped.setdefault(
                rid,
                {
                    "source": source,
                    "role": role,
                    "company_id": str(company_id) if company_id else None,
                    "company_industry": industry,
                    "company_size_band": size_band,
                },
            )
            value = structured.get("value") if isinstance(structured, dict) else None
            if value is not None:
                answers[rid][slot_key] = str(value)
    return [
        RespondentProfile(
            respondent_id=rid,
            source=meta["source"],
            role=meta["role"],
            answers=answers[rid],
            company_id=meta["company_id"],
            company_industry=meta["company_industry"],
            company_size_band=meta["company_size_band"],
        )
        for rid, meta in grouped.items()
    ]


def load_entity_profiles(grain: str) -> list[EntityProfile]:
    """Aggregate answers into function- or company-grain entities (Fork B).

    grain='function' groups by (company_id, function_key) over sessions that carry
    a function_key; grain='company' groups by company_id over all answered sessions.
    Latest answer per slot wins within the entity.
    """
    if grain not in ("function", "company"):
        raise ValueError(f"unknown grain: {grain}")
    backfill_real_respondents_for_answered_sessions()
    is_function = grain == "function"
    function_select = "s.function_key" if is_function else "NULL"
    where = "WHERE s.function_key IS NOT NULL" if is_function else ""
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT s.company_id, {function_select} AS function_key, s.respondent_id, r.source,
                   c.industry, COALESCE(c.headcount_band, c.size_bucket) AS size_band,
                   a.slot_key, a.structured_json
            FROM sessions s
            JOIN companies c ON c.id = s.company_id
            LEFT JOIN respondents r ON r.id = s.respondent_id
            JOIN answers a ON a.session_id = s.id
            {where}
            ORDER BY s.company_id, function_key, a.slot_key, a.created_at DESC, a.id DESC
            """
        )
        entities: dict[str, dict[str, Any]] = {}
        for company_id, function_key, respondent_id, source, industry, size_band, slot_key, structured in cur.fetchall():
            key = f"{company_id}:{function_key}" if is_function else str(company_id)
            entity = entities.setdefault(
                key,
                {
                    "company_id": str(company_id) if company_id else None,
                    "function_key": function_key,
                    "industry": industry,
                    "size_band": size_band,
                    "answers": {},
                    "respondents": set(),
                    "sources": set(),
                },
            )
            if respondent_id is not None:
                entity["respondents"].add(str(respondent_id))
            if source:
                entity["sources"].add(source)
            if slot_key not in entity["answers"]:  # first seen = latest (created_at DESC)
                value = structured.get("value") if isinstance(structured, dict) else None
                if value is not None:
                    entity["answers"][slot_key] = str(value)
    profiles: list[EntityProfile] = []
    for key, e in entities.items():
        source = "real" if "real" in e["sources"] else ("synthetic" if e["sources"] else "real")
        profiles.append(
            EntityProfile(
                key=key,
                grain=grain,
                company_id=e["company_id"],
                function_key=e["function_key"],
                industry=e["industry"],
                size_band=e["size_band"],
                member_count=max(len(e["respondents"]), 1),
                profile=RespondentProfile(
                    respondent_id=key,
                    source=source,
                    role=None,
                    answers=e["answers"],
                    company_id=e["company_id"],
                    company_industry=e["industry"],
                    company_size_band=e["size_band"],
                ),
            )
        )
    return profiles


def insert_entity_embedding(
    *, grain: str, entity_key: str, run_id: uuid.UUID, embedding: list[float],
    feature_vector: dict[str, Any], model: str,
) -> uuid.UUID:
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO entity_embeddings (grain, entity_key, run_id, embedding, feature_vector, model)
            VALUES (%s, %s, %s, %s::vector, %s, %s) RETURNING id
            """,
            (grain, entity_key, run_id, _vec(embedding), Jsonb(feature_vector), model),
        )
        eid = cur.fetchone()[0]
        conn.commit()
        return eid


def update_entity_umap(embedding_id: uuid.UUID, x: float, y: float) -> None:
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE entity_embeddings SET umap_x = %s, umap_y = %s WHERE id = %s",
            (x, y, embedding_id),
        )
        conn.commit()


def insert_function_benchmark(
    *, company_id: str, function_key: str, run_id: uuid.UUID, respondent_count: int,
    avg_maturity: float, percentile_cohort: float, percentile_peer: float,
    peer_group: dict[str, Any], cluster_id: uuid.UUID | str | None,
    common_pain_points: list[dict[str, Any]], common_tech_stack: list[str],
) -> None:
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO function_benchmarks
              (company_id, function_key, run_id, respondent_count, avg_maturity,
               percentile_cohort, percentile_peer, peer_group, cluster_id,
               common_pain_points, common_tech_stack)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                company_id, function_key, run_id, respondent_count, avg_maturity,
                percentile_cohort, percentile_peer, Jsonb(peer_group), cluster_id,
                Jsonb(common_pain_points), Jsonb(common_tech_stack),
            ),
        )
        conn.commit()


def set_company_cluster(company_id: str, run_id: uuid.UUID, cluster_id: uuid.UUID | str | None) -> None:
    """Stamp the company-grain persona onto the company_benchmarks row for this run."""
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE company_benchmarks SET company_cluster_id = %s WHERE company_id = %s AND run_id = %s",
            (cluster_id, company_id, run_id),
        )
        conn.commit()


def backfill_real_respondents_for_answered_sessions() -> int:
    """Attach legacy answered sessions to real respondent rows for analytics."""
    written = 0
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id
            FROM sessions s
            WHERE s.respondent_id IS NULL
              AND EXISTS (SELECT 1 FROM answers a WHERE a.session_id = s.id)
            ORDER BY s.started_at, s.id
            """
        )
        session_ids = [row[0] for row in cur.fetchall()]
        for session_id in session_ids:
            cur.execute(
                """
                INSERT INTO companies (name, industry)
                VALUES (%s, %s)
                RETURNING id
                """,
                ("Demo discovery company", "Finance/accounting discovery"),
            )
            company_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO respondents (company_id, name, email, source)
                VALUES (%s, %s, %s, 'real')
                RETURNING id
                """,
                (company_id, "Discovery respondent", f"real+{session_id}@playbook.local"),
            )
            respondent_id = cur.fetchone()[0]
            cur.execute(
                """
                UPDATE sessions
                SET company_id = %s, respondent_id = %s
                WHERE id = %s AND respondent_id IS NULL
                """,
                (company_id, respondent_id, session_id),
            )
            written += cur.rowcount
        conn.commit()
    return written


def create_cluster_run(algorithm: str, params: dict[str, Any], n_clusters: int, silhouette: float) -> uuid.UUID:
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO cluster_runs (algorithm, params, n_clusters, silhouette_score)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (algorithm, Jsonb(params), n_clusters, silhouette),
        )
        run_id = cur.fetchone()[0]
        conn.commit()
        return run_id


def insert_cluster(
    *,
    run_id: uuid.UUID,
    centroid: list[float],
    label: str,
    size: int,
    avg_maturity: float,
    common_pain_points: list[dict[str, Any]],
    common_tech_stack: list[str],
    summary: str,
    community_id: int | None,
    buying_persona: str | None = None,
    grain: str = "function",
) -> uuid.UUID:
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO clusters
              (run_id, centroid, label, size, avg_maturity, common_pain_points,
               common_tech_stack, summary, community_id, buying_persona, grain)
            VALUES (%s, %s::vector, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                run_id,
                _vec(centroid),
                label,
                size,
                avg_maturity,
                Jsonb(common_pain_points),
                Jsonb(common_tech_stack),
                summary,
                community_id,
                buying_persona,
                grain,
            ),
        )
        cluster_id = cur.fetchone()[0]
        conn.commit()
        return cluster_id


def insert_company_benchmark(
    *,
    company_id: str,
    run_id: uuid.UUID,
    respondent_count: int,
    avg_maturity: float,
    percentile_cohort: float,
    percentile_peer: float,
    peer_group: dict[str, Any],
    primary_cluster_id: uuid.UUID | str | None,
    cluster_exposure: dict[str, int],
    common_pain_points: list[dict[str, Any]],
    common_tech_stack: list[str],
) -> None:
    with connect(register_vector_types=False) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO company_benchmarks
              (company_id, run_id, respondent_count, avg_maturity, percentile_cohort,
               percentile_peer, peer_group, primary_cluster_id, cluster_exposure,
               common_pain_points, common_tech_stack)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                company_id,
                run_id,
                respondent_count,
                avg_maturity,
                percentile_cohort,
                percentile_peer,
                Jsonb(peer_group),
                primary_cluster_id,
                Jsonb(cluster_exposure),
                Jsonb(common_pain_points),
                Jsonb(common_tech_stack),
            ),
        )
        conn.commit()


