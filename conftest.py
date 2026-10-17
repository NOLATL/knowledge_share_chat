"""Repo-wide pytest fixtures: a real pgvector Postgres in a throwaway container.

Requires Docker (Docker Desktop locally; a Docker-enabled runner in CI). The
container is session-scoped; `fresh_db_url` resets the public schema per test so
each test starts from an empty database. Used by the migration tests and the
question-bank reseed tests.
"""

from __future__ import annotations

import os
import time

import psycopg
import pytest

# Ryuk (the testcontainers reaper) is flaky on Windows and unnecessary here —
# we stop the container explicitly in the fixture teardown.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

from testcontainers.core.container import DockerContainer  # noqa: E402

PGVECTOR_IMAGE = "pgvector/pgvector:pg16"
DB_USER = "playbook"
DB_PASSWORD = "playbook"
DB_NAME = "playbook"


def _wait_ready(url: str, timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with psycopg.connect(url):
                return
        except Exception as err:  # noqa: BLE001 — retry until ready or timeout
            last_err = err
            time.sleep(1)
    raise RuntimeError(f"Postgres did not become ready in {timeout}s: {last_err}")


@pytest.fixture(scope="session")
def pg_url() -> str:
    container = (
        DockerContainer(PGVECTOR_IMAGE)
        .with_env("POSTGRES_USER", DB_USER)
        .with_env("POSTGRES_PASSWORD", DB_PASSWORD)
        .with_env("POSTGRES_DB", DB_NAME)
        .with_exposed_ports(5432)
    )
    container.start()
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{host}:{port}/{DB_NAME}"
        _wait_ready(url)
        yield url
    finally:
        container.stop()


@pytest.fixture
def fresh_db_url(pg_url: str) -> str:
    """Reset to an empty public schema before handing the URL to a test."""
    with psycopg.connect(pg_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    return pg_url
