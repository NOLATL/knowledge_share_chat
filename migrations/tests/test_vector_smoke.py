"""Smoke test: pgvector is enabled and cosine search orders correctly."""

from __future__ import annotations

from pathlib import Path

import psycopg

from playbook_shared.migrate import run_migrations

MIGRATIONS_DIR = Path(__file__).resolve().parents[1]


def _vec(literal: list[str]) -> str:
    return "[" + ",".join(literal) + "]"


def test_vector_insert_and_cosine_search(fresh_db_url: str):
    run_migrations(fresh_db_url, MIGRATIONS_DIR)

    near = _vec(["1"] + ["0"] * 1535)
    far = _vec(["0"] * 1535 + ["1"])

    with psycopg.connect(fresh_db_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("INSERT INTO respondents (source) VALUES ('synthetic') RETURNING id")
            respondent_id = cur.fetchone()[0]

            cur.executemany(
                "INSERT INTO respondent_embeddings (respondent_id, embedding, model) "
                "VALUES (%s, %s::vector, %s)",
                [(respondent_id, near, "near"), (respondent_id, far, "far")],
            )

            # The nearest row to `near` (by cosine distance) must be 'near'.
            cur.execute(
                "SELECT model FROM respondent_embeddings "
                "ORDER BY embedding <=> %s::vector LIMIT 1",
                (near,),
            )
            assert cur.fetchone()[0] == "near"
