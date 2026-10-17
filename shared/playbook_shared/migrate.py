"""Forward-only SQL migration runner.

- Applies numbered ``*.sql`` files in a migrations directory in filename order.
- Records applied files in a ``schema_migrations`` table; re-running is a no-op.
- Each file runs inside a transaction, EXCEPT files whose name contains
  ``.notx.`` (e.g. ``0007_hnsw_concurrently.notx.sql``), which run in autocommit
  so statements like ``CREATE INDEX CONCURRENTLY`` are allowed (per BUILD_PLAN
  conventions). No ``.notx.`` files exist yet; the hook is here for later tasks.

The logic lives here (importable + testable); ``scripts/migrate.py`` is the CLI.
"""

from __future__ import annotations

from pathlib import Path

import psycopg

from playbook_shared.db import connect

_SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def _discover(migrations_dir: Path) -> list[Path]:
    return sorted(migrations_dir.glob("*.sql"), key=lambda p: p.name)


def _applied_versions(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def _record(cur: psycopg.Cursor, name: str) -> None:
    cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (name,))


def _apply_file(conn: psycopg.Connection, path: Path) -> None:
    # Connection is in autocommit mode. Normal files apply atomically inside an
    # explicit transaction; ``.notx.`` files (e.g. CREATE INDEX CONCURRENTLY)
    # run statement-by-statement with no surrounding transaction.
    sql = path.read_text(encoding="utf-8")
    if ".notx." in path.name:
        with conn.cursor() as cur:
            cur.execute(sql)
            _record(cur, path.name)
    else:
        with conn.transaction(), conn.cursor() as cur:
            cur.execute(sql)
            _record(cur, path.name)


def run_migrations(
    database_url: str | None = None,
    migrations_dir: Path | str | None = None,
) -> list[str]:
    """Apply all pending migrations. Returns the list of versions applied now."""
    migrations_dir = Path(migrations_dir) if migrations_dir else _default_dir()
    if not migrations_dir.is_dir():
        raise FileNotFoundError(f"migrations dir not found: {migrations_dir}")

    applied_now: list[str] = []
    conn = connect(database_url, register_vector_types=False)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA_MIGRATIONS)
        already = _applied_versions(conn)
        for path in _discover(migrations_dir):
            if path.name in already:
                continue
            _apply_file(conn, path)
            applied_now.append(path.name)
    finally:
        conn.close()
    return applied_now


def _default_dir() -> Path:
    # repo_root/migrations — this file is shared/playbook_shared/migrate.py
    return Path(__file__).resolve().parents[2] / "migrations"
