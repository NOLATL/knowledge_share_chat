"""Reseed upserts by slot_key: insert, update-in-place, retire (never delete).

Uses the shared `fresh_db_url` container fixture (repo-root conftest.py) and runs
the real migrations first to create the `questions`/`answers` tables.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
import yaml

from playbook_shared.migrate import run_migrations
from playbook_shared.question_bank import QuestionBankError, load_bank, reseed_questions

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def _row(slot_key, *, category="A", text="t", tag="SPIN-Situation", tier="must_fill", order=10):
    return {
        "slot_key": slot_key,
        "category": category,
        "text": text,
        "framework_tag": tag,
        "tier": tier,
        "order_hint": order,
        "active": True,
    }


def _write_bank(path: Path, rows: list[dict], version: str = "test.1") -> Path:
    path.write_text(
        yaml.safe_dump({"version": version, "questions": rows}, sort_keys=False),
        encoding="utf-8",
    )
    return path


def _migrate(url: str) -> None:
    run_migrations(url, MIGRATIONS_DIR)


def _questions(url: str) -> dict[str, dict]:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT slot_key, text, tier, order_hint, active FROM questions")
        return {
            r[0]: {"text": r[1], "tier": r[2], "order_hint": r[3], "active": r[4]}
            for r in cur.fetchall()
        }


def test_reseed_inserts_active_rows(fresh_db_url, tmp_path):
    _migrate(fresh_db_url)
    bank = _write_bank(tmp_path / "b.yaml", [_row("a.one"), _row("b.two", category="B")])

    result = reseed_questions(fresh_db_url, bank)

    assert set(result.inserted) == {"a.one", "b.two"}
    assert result.updated == []
    rows = _questions(fresh_db_url)
    assert set(rows) == {"a.one", "b.two"}
    assert all(r["active"] for r in rows.values())


def test_reseed_updates_in_place_no_duplicates(fresh_db_url, tmp_path):
    _migrate(fresh_db_url)
    path = tmp_path / "b.yaml"
    _write_bank(path, [_row("a.one", text="old", tier="must_fill", order=10)])
    reseed_questions(fresh_db_url, path)

    _write_bank(path, [_row("a.one", text="new wording", tier="nice_to_have", order=99)])
    result = reseed_questions(fresh_db_url, path)

    assert result.inserted == []
    assert result.updated == ["a.one"]
    rows = _questions(fresh_db_url)
    assert len(rows) == 1  # updated in place, not duplicated
    assert rows["a.one"] == {"text": "new wording", "tier": "nice_to_have", "order_hint": 99, "active": True}


def test_reseed_retires_missing_and_keeps_answers(fresh_db_url, tmp_path):
    _migrate(fresh_db_url)
    path = tmp_path / "b.yaml"
    _write_bank(path, [_row("a.one"), _row("b.two", category="B")])
    reseed_questions(fresh_db_url, path)

    # Attach an answer to b.two via a session.
    with psycopg.connect(fresh_db_url) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("INSERT INTO sessions DEFAULT VALUES RETURNING id")
            session_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO answers (session_id, slot_key, structured_json) VALUES (%s, %s, %s)",
                (session_id, "b.two", "{}"),
            )

    # Remove b.two from the file and reseed.
    _write_bank(path, [_row("a.one")])
    result = reseed_questions(fresh_db_url, path)

    assert "b.two" in result.retired
    assert "b.two" in result.retired_with_answers
    rows = _questions(fresh_db_url)
    assert rows["b.two"]["active"] is False  # retired, not deleted
    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM answers WHERE slot_key = 'b.two'")
        assert cur.fetchone()[0] == 1  # historical answer preserved


def test_reseed_inserts_new_slot(fresh_db_url, tmp_path):
    _migrate(fresh_db_url)
    path = tmp_path / "b.yaml"
    _write_bank(path, [_row("a.one")])
    reseed_questions(fresh_db_url, path)

    _write_bank(path, [_row("a.one"), _row("c.three", category="C")])
    result = reseed_questions(fresh_db_url, path)

    assert result.inserted == ["c.three"]
    assert _questions(fresh_db_url)["c.three"]["active"] is True


def test_reseed_reactivates_returning_slot(fresh_db_url, tmp_path):
    _migrate(fresh_db_url)
    path = tmp_path / "b.yaml"
    _write_bank(path, [_row("a.one"), _row("b.two", category="B")])
    reseed_questions(fresh_db_url, path)
    _write_bank(path, [_row("a.one")])  # retire b.two
    reseed_questions(fresh_db_url, path)
    _write_bank(path, [_row("a.one"), _row("b.two", category="B")])  # bring it back

    reseed_questions(fresh_db_url, path)

    assert _questions(fresh_db_url)["b.two"]["active"] is True


def test_reseed_ships_full_real_bank(fresh_db_url):
    _migrate(fresh_db_url)
    result = reseed_questions(fresh_db_url)  # default path = shared/question_bank.yaml
    bank = load_bank()

    assert len(result.inserted) == len(bank.questions)
    rows = _questions(fresh_db_url)
    assert len(rows) == len(bank.questions)
    must_fill_active = [k for k, v in rows.items() if v["tier"] == "must_fill" and v["active"]]
    assert len(must_fill_active) >= 12


def test_reseed_ships_company_strategic_plan_slots(fresh_db_url):
    _migrate(fresh_db_url)
    reseed_questions(fresh_db_url)  # the real shipped bank
    rows = _questions(fresh_db_url)
    for slot in ("company.strategic_plan_1yr", "company.strategic_plan_3yr", "company.strategic_plan_5yr"):
        assert rows[slot]["active"] is True


def test_reseed_refuses_duplicate_slot_key(fresh_db_url, tmp_path):
    _migrate(fresh_db_url)
    path = _write_bank(tmp_path / "b.yaml", [_row("dup"), _row("dup", category="B")])
    with pytest.raises(QuestionBankError, match="duplicate slot_key"):
        reseed_questions(fresh_db_url, path)
    assert _questions(fresh_db_url) == {}  # nothing written
