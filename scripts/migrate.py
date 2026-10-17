"""CLI entrypoint for database migrations.

Run locally or as a Railway pre-deploy command:

    uv run python scripts/migrate.py

Reads DATABASE_URL from the environment; applies migrations from ../migrations.
"""

from __future__ import annotations

import sys
from pathlib import Path

from playbook_shared.migrate import run_migrations

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def main() -> int:
    applied = run_migrations(migrations_dir=MIGRATIONS_DIR)
    if applied:
        print(f"Applied {len(applied)} migration(s):")
        for name in applied:
            print(f"  + {name}")
    else:
        print("No pending migrations; database is up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
