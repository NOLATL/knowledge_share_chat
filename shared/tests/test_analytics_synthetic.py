import psycopg

from playbook_shared.analytics import openai_ops
from playbook_shared.analytics.synthetic import (
    backfill_session_functions,
    function_for_role,
    seed_synthetic_respondents,
)
from playbook_shared.migrate import run_migrations
from playbook_shared.question_bank import reseed_questions


def test_synthetic_seed_creates_real_shaped_rows(fresh_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db_url)
    run_migrations(fresh_db_url)
    reseed_questions(fresh_db_url)

    first = seed_synthetic_respondents(count=20, seed=123, use_llm=False)
    second = seed_synthetic_respondents(count=20, seed=123, use_llm=False)

    assert first.created == 20
    assert second.created == 0
    assert second.skipped_existing == 20

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM respondents WHERE source = 'synthetic'")
        assert cur.fetchone()[0] == 20
        cur.execute(
            """
            SELECT count(DISTINCT s.id), count(a.id)
            FROM sessions s
            JOIN respondents r ON r.id = s.respondent_id
            JOIN answers a ON a.session_id = s.id
            WHERE r.source = 'synthetic'
            """
        )
        sessions, answers = cur.fetchone()
        assert sessions == 20
        assert answers >= 20 * 13


def test_synthetic_seed_reports_progress(fresh_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db_url)
    run_migrations(fresh_db_url)
    reseed_questions(fresh_db_url)
    events = []

    summary = seed_synthetic_respondents(
        count=2,
        seed=789,
        use_llm=False,
        progress_callback=events.append,
    )

    assert summary.created == 2
    assert [event.status for event in events] == ["started", "created", "started", "created"]
    assert all(event.total == 2 for event in events)


def test_synthetic_seed_falls_back_for_shallow_primary(fresh_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db_url)
    run_migrations(fresh_db_url)
    reseed_questions(fresh_db_url)
    events = []
    calls = []

    def generate_answers(_prompt, slot_keys, model=None):
        calls.append(model)
        if model == openai_ops.synthetic_model():
            return {slot_key: "" for slot_key in slot_keys}
        return {slot_key: f"fallback answer for {slot_key}" for slot_key in slot_keys}

    monkeypatch.setattr(openai_ops, "generate_answers", generate_answers)

    summary = seed_synthetic_respondents(
        count=1,
        seed=790,
        use_llm=True,
        progress_callback=events.append,
    )

    assert summary.created == 1
    assert calls == [openai_ops.synthetic_model(), openai_ops.fallback_synthetic_model()]
    assert [event.status for event in events] == ["started", "fallback", "created"]


def test_synthetic_seed_stamps_function_key_from_role(fresh_db_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db_url)
    run_migrations(fresh_db_url)
    reseed_questions(fresh_db_url)

    seed_synthetic_respondents(count=10, seed=321, use_llm=False)

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM sessions WHERE function_key IS NULL")
        assert cur.fetchone()[0] == 0  # every synthetic session got a function
        cur.execute(
            "SELECT DISTINCT function_key FROM sessions s "
            "JOIN respondents r ON r.id = s.respondent_id WHERE r.role = 'Controller'"
        )
        assert [r[0] for r in cur.fetchall()] == ["Accounting / Controllership"]


def test_backfill_session_functions_fills_nulls(fresh_db_url):
    run_migrations(fresh_db_url)
    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO companies (name) VALUES ('Legacy Co') RETURNING id")
        company_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO respondents (company_id, name, role, source) "
            "VALUES (%s, 'Pat', 'VP of FP&A', 'real') RETURNING id",
            (company_id,),
        )
        respondent_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO sessions (company_id, respondent_id, script_version) VALUES (%s, %s, 'legacy') RETURNING id",
            (company_id, respondent_id),
        )
        session_id = cur.fetchone()[0]
        conn.commit()

    assert function_for_role("VP of FP&A") == "Financial Planning & Analysis (FP&A)"
    filled = backfill_session_functions(fresh_db_url)
    assert filled == 1
    assert backfill_session_functions(fresh_db_url) == 0  # idempotent

    with psycopg.connect(fresh_db_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT function_key FROM sessions WHERE id = %s", (session_id,))
        assert cur.fetchone()[0] == "Financial Planning & Analysis (FP&A)"


def test_openai_request_timeout_defaults_and_env(monkeypatch):
    monkeypatch.delenv("OPENAI_REQUEST_TIMEOUT_SECONDS", raising=False)
    assert openai_ops.request_timeout_seconds() == 45.0

    monkeypatch.setenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "12.5")
    assert openai_ops.request_timeout_seconds() == 12.5
