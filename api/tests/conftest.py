"""API test fixtures: a migrated + seeded DB wired to the app via DATABASE_URL."""

from __future__ import annotations

from pathlib import Path

import pytest

from playbook_shared.migrate import run_migrations
from playbook_shared.question_bank import reseed_questions

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


@pytest.fixture
def chat_db(fresh_db_url, monkeypatch):
    """Point the app at a fresh, migrated, seeded DB (uses the root `fresh_db_url`)."""
    monkeypatch.setenv("DATABASE_URL", fresh_db_url)
    run_migrations(fresh_db_url, MIGRATIONS_DIR)
    reseed_questions(fresh_db_url)  # the real shipped question bank
    return fresh_db_url
