"""Postgres connection helpers (psycopg3, sync).

Task 0.2 only needs synchronous access (migrations + a vector smoke test). The
async helper the FastAPI app will use lands when the chat engine needs the DB
(Task 1.2). `register_vector_types` is opt-in and lazily imports `pgvector`,
since nothing reads/writes vectors from Python until the analytics work (Epic 2);
the migrator must NOT enable it (the `vector` extension may not exist yet on a
fresh DB).
"""

from __future__ import annotations

import os

import psycopg


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def connect(
    database_url: str | None = None,
    *,
    register_vector_types: bool = False,
) -> psycopg.Connection:
    """Open a synchronous connection. Caller is responsible for closing it."""
    conn = psycopg.connect(database_url or get_database_url())
    if register_vector_types:
        from pgvector.psycopg import register_vector  # lazy: optional dep

        register_vector(conn)
    return conn
