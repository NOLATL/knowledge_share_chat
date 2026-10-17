"""External per-company deliverable (Task 8.3): directory, generation, validation."""

from __future__ import annotations

import uuid

import psycopg
from fastapi.testclient import TestClient

from api import openai_client
from api.main import app

client = TestClient(app)

COMPANY_MD = """## Company Profile
Acme Manufacturing: maturity 3.1/5, 62nd peer percentile, 3 respondents, NetSuite + Excel close.

## Cohort Benchmark
Acme sits at the 62nd percentile of Manufacturing peers in the 201-1000 band.

## Advisory - Technical Improvements
- Automate bank and intercompany reconciliations.
- Move consolidation out of spreadsheets into a governed process.

## Advisory - People And Product Gaps
- No SQL/Python capability on the team; workflow building depends on IT.

## Advisory - Current To Future Risks
- The 12-day close blocks the stated goal of a 5-day close within a year.

## Quick Wins
- Assign a close-calendar owner and automate recurring evidence collection.

## Roadmap
### Now
- **Close-cycle automation** — Cut manual month-end reconciliation with rule-based matching.
### Next
- **Reporting accuracy layer** — Validation on top of exports.
### Later
- **System consolidation** — Reduce tool sprawl into an integrated stack.
"""


def _seed_company(chat_db, *, with_benchmark: bool = True) -> str:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    session_id = uuid.uuid4()
    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO companies (id, name, industry, headcount_band, revenue_band, years_in_business)
            VALUES (%s, 'Acme Manufacturing', 'Manufacturing', '201-1000', '$50-250M', 22)
            """,
            (company_id,),
        )
        cur.execute(
            "INSERT INTO respondents (id, company_id, name, role, email, source) "
            "VALUES (%s, %s, 'Jo', 'Controller', 'jo@acme.example', 'real')",
            (respondent_id, company_id),
        )
        cur.execute(
            "INSERT INTO sessions (id, company_id, respondent_id, status, script_version) "
            "VALUES (%s, %s, %s, 'complete', 'test')",
            (session_id, company_id, respondent_id),
        )
        cur.execute(
            """
            INSERT INTO answers (session_id, slot_key, raw_text, structured_json, confidence, source)
            VALUES
              (%s, 'close.days', 'Close takes 12 days', '{"value": "12 days"}', 0.9, 'chat'),
              (%s, 'sys.erp', 'NetSuite', '{"value": "NetSuite"}', 0.9, 'chat'),
              (%s, 'goal.future_state', '5-day close in a year', '{"value": "5-day close"}', 0.9, 'chat')
            """,
            (session_id, session_id, session_id),
        )
        if with_benchmark:
            cur.execute(
                "INSERT INTO cluster_runs (algorithm, params, n_clusters, silhouette_score) "
                "VALUES ('test', '{}', 3, 0.35) RETURNING id"
            )
            run_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO clusters (run_id, label, size, avg_maturity, common_pain_points,
                                      common_tech_stack, summary)
                VALUES (%s, 'Manual-heavy controllers', 12, 2.6, '[]', '["excel"]', 'summary')
                RETURNING id
                """,
                (run_id,),
            )
            cluster_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO company_benchmarks
                  (company_id, run_id, respondent_count, avg_maturity, percentile_cohort,
                   percentile_peer, peer_group, primary_cluster_id, cluster_exposure,
                   common_pain_points, common_tech_stack)
                VALUES (%s, %s, 1, 3.1, 58.0, 62.0,
                        '{"industry": "Manufacturing", "size_band": "201-1000", "n": 4, "fell_back": false}',
                        %s, '{}', '[]', '["netsuite", "excel"]')
                """,
                (company_id, run_id, cluster_id),
            )
        conn.commit()
    return str(company_id)


def _seed_synthetic_only_company(chat_db) -> str:
    company_id = uuid.uuid4()
    respondent_id = uuid.uuid4()
    session_id = uuid.uuid4()
    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO companies (id, name, industry, size_bucket) "
            "VALUES (%s, 'Synthetic Demo Co', 'Finance/accounting demo cohort', '51-200')",
            (company_id,),
        )
        cur.execute(
            "INSERT INTO respondents (id, company_id, name, role, email, source) "
            "VALUES (%s, %s, 'Synth', 'Controller', 'synth@playbook.local', 'synthetic')",
            (respondent_id, company_id),
        )
        cur.execute(
            "INSERT INTO sessions (id, company_id, respondent_id, status, script_version) "
            "VALUES (%s, %s, %s, 'complete', 'test')",
            (session_id, company_id, respondent_id),
        )
        cur.execute(
            "INSERT INTO answers (session_id, slot_key, raw_text, structured_json, confidence, source) "
            "VALUES (%s, 'close.days', '8 days', '{\"value\": \"8 days\"}', 0.9, 'chat')",
            (session_id,),
        )
        conn.commit()
    return str(company_id)


def _seed_empty_shell_company(chat_db) -> str:
    """A backfill-style company with a respondent but zero answers."""
    company_id = uuid.uuid4()
    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO companies (id, name, industry) "
            "VALUES (%s, 'Demo discovery company', 'Finance/accounting discovery')",
            (company_id,),
        )
        cur.execute(
            "INSERT INTO respondents (company_id, name, source) VALUES (%s, 'Discovery respondent', 'real')",
            (company_id,),
        )
        conn.commit()
    return str(company_id)


def test_companies_list_excludes_synthetic_and_unassessed_shells(chat_db):
    real_id = _seed_company(chat_db)
    synth_id = _seed_synthetic_only_company(chat_db)
    shell_id = _seed_empty_shell_company(chat_db)

    default = client.get("/companies").json()
    assert [c["id"] for c in default] == [real_id]  # no synthetic, no empty shell
    assert default[0]["percentile_peer"] == 62.0
    assert default[0]["has_real_respondents"] is True
    assert default[0]["created_at"]  # dropdowns dedupe repeated names by date

    everything = client.get("/companies?include_synthetic=true").json()
    ids = {c["id"] for c in everything}
    assert ids == {real_id, synth_id}  # shells with zero answers stay hidden
    assert shell_id not in ids


def test_company_report_generation_writes_company_scoped_report(chat_db, monkeypatch):
    company_id = _seed_company(chat_db)

    async def fake_complete(messages):
        assert "vendor-agnostic" in messages[0]["content"]
        assert "percentile_peer" in messages[1]["content"]
        assert "Acme Manufacturing" in messages[1]["content"]
        return COMPANY_MD

    monkeypatch.setattr(openai_client, "complete_report", fake_complete)
    resp = client.post(f"/companies/{company_id}/reports/external")

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "company_external"
    assert body["company_id"] == company_id
    assert "## Cohort Benchmark" in body["rendered_md"]

    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT session_id, company_id, type FROM reports WHERE company_id = %s",
            (company_id,),
        )
        session_id, db_company_id, report_type = cur.fetchone()
    assert session_id is None  # company-scoped, not session-scoped
    assert str(db_company_id) == company_id
    assert report_type == "company_external"

    latest = client.get(f"/companies/{company_id}/reports/external/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == body["id"]


def test_company_report_carries_time_ordered_history_and_regenerates_append_only(chat_db, monkeypatch):
    company_id = _seed_company(chat_db)
    # A second, later run for the same company (higher peer percentile).
    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO cluster_runs (algorithm, params, n_clusters, silhouette_score) "
            "VALUES ('test', '{}', 3, 0.36) RETURNING id"
        )
        run_2 = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO company_benchmarks
              (company_id, run_id, respondent_count, avg_maturity, percentile_cohort,
               percentile_peer, peer_group, cluster_exposure, common_pain_points,
               common_tech_stack, computed_at)
            VALUES (%s, %s, 1, 3.3, 64.0, 71.0, '{}', '{}', '[]', '[]', now() + interval '1 hour')
            """,
            (company_id, run_2),
        )
        conn.commit()

    async def fake_complete(messages):
        assert "benchmark_history" in messages[1]["content"]
        return COMPANY_MD

    monkeypatch.setattr(openai_client, "complete_report", fake_complete)
    first = client.post(f"/companies/{company_id}/reports/external")
    second = client.post(f"/companies/{company_id}/reports/external")

    assert first.status_code == 200 and second.status_code == 200
    history = first.json()["content_json"]["benchmark_history"]
    assert len(history) == 2
    assert [h["percentile_peer"] for h in history] == [62.0, 71.0]  # oldest first

    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM reports WHERE company_id = %s AND type = 'company_external'",
            (company_id,),
        )
        assert cur.fetchone()[0] == 2  # regenerate appends, never mutates


def test_company_report_rejects_vendor_named_advisory(chat_db, monkeypatch):
    company_id = _seed_company(chat_db)
    bad_md = COMPANY_MD.replace(
        "- Automate bank and intercompany reconciliations.",
        "- Buy BlackLine to automate reconciliations.",
    )

    async def fake_complete(messages):
        return bad_md

    monkeypatch.setattr(openai_client, "complete_report", fake_complete)
    resp = client.post(f"/companies/{company_id}/reports/external")
    assert resp.status_code == 502
    assert "vendor-agnostic" in resp.json()["detail"]


def test_company_report_allows_current_stack_vendor(chat_db, monkeypatch):
    company_id = _seed_company(chat_db)  # seed's own ERP is NetSuite
    ok_md = COMPANY_MD.replace(
        "- Automate bank and intercompany reconciliations.",
        "- Extend NetSuite's native reconciliation automation.",
    )

    async def fake_complete(messages):
        return ok_md

    monkeypatch.setattr(openai_client, "complete_report", fake_complete)
    resp = client.post(f"/companies/{company_id}/reports/external")
    assert resp.status_code == 200


def test_company_report_rejects_missing_sections(chat_db, monkeypatch):
    company_id = _seed_company(chat_db)

    async def fake_complete(messages):
        return "## Company Profile\nJust a profile, nothing else."

    monkeypatch.setattr(openai_client, "complete_report", fake_complete)
    resp = client.post(f"/companies/{company_id}/reports/external")
    assert resp.status_code == 502
    assert "missing sections" in resp.json()["detail"]


def test_company_report_unknown_company_404(chat_db):
    resp = client.post(f"/companies/{uuid.uuid4()}/reports/external")
    assert resp.status_code == 404


FPA_KEY = "Financial Planning & Analysis (FP&A)"

FUNCTION_MD = f"""# Acme Manufacturing / {FPA_KEY}

## Current State
FP&A forecasts monthly in spreadsheets fed by ERP exports.

## Maturity Assessment
Maturity 3.0/5 for the function.

## Benchmark Comparison
This FP&A function sits at the 55th percentile of FP&A functions in the cohort.

## Prioritized Pains
- Manual forecast assembly.

## Category-Level Recommendations
- Adopt a governed planning process with automated actuals feeds.

## Quick Wins
- Automate the actuals load into the forecast model.

## Roadmap
### Now
- **Governed forecast inputs** — Automate the actuals load into the forecast model.
### Next
- **Driver-based planning** — Move the annual budget to rolling drivers.
### Later
- **Scenario modeling** — Add fast what-if capacity for leadership asks.
"""


def _add_fpa_function(chat_db, company_id: str) -> None:
    """Give the seeded company a second, FP&A-keyed session with its own answer."""
    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE sessions SET function_key = 'Accounting / Controllership' WHERE company_id = %s",
            (company_id,),
        )
        fpa_respondent, fpa_session = uuid.uuid4(), uuid.uuid4()
        cur.execute(
            "INSERT INTO respondents (id, company_id, name, role, email, source) "
            "VALUES (%s, %s, 'Pat', 'FP&A Director', 'pat@acme.example', 'real')",
            (fpa_respondent, company_id),
        )
        cur.execute(
            "INSERT INTO sessions (id, company_id, respondent_id, function_key, status, script_version) "
            f"VALUES (%s, %s, %s, '{FPA_KEY}', 'complete', 'test')",
            (fpa_session, company_id, fpa_respondent),
        )
        cur.execute(
            "INSERT INTO answers (session_id, slot_key, raw_text, structured_json, confidence, source, created_at) "
            """VALUES (%s, 'close.days', 'Close takes 6 days', '{"value": "6 days"}', 0.9, 'chat', now() + interval '1 minute')""",
            (fpa_session,),
        )
        conn.commit()


def test_function_report_generation_scoped_and_titled(chat_db, monkeypatch):
    company_id = _seed_company(chat_db)
    _add_fpa_function(chat_db, company_id)

    async def fake_complete(messages):
        assert "ONE business function" in messages[0]["content"]
        payload = messages[1]["content"]
        assert FPA_KEY in payload
        assert "function_benchmark" in payload
        assert '"6 days"' in payload  # the function's own answer
        assert '"12 days"' not in payload  # NOT the accounting function's
        return FUNCTION_MD

    monkeypatch.setattr(openai_client, "complete_report", fake_complete)
    resp = client.post(
        f"/companies/{company_id}/reports/function", params={"function_key": FPA_KEY}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "function_external"
    assert body["rendered_md"].startswith("# Acme Manufacturing /")

    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT function_key FROM reports WHERE company_id = %s AND type = 'function_external'",
            (company_id,),
        )
        assert cur.fetchone()[0] == FPA_KEY

    latest = client.get(
        f"/companies/{company_id}/reports/function/latest", params={"function_key": FPA_KEY}
    )
    assert latest.status_code == 200
    assert latest.json()["id"] == body["id"]


def test_function_report_parses_structured_roadmap(chat_db, monkeypatch):
    """The Roadmap section is parsed into content_json['roadmap'] phases."""
    company_id = _seed_company(chat_db)
    _add_fpa_function(chat_db, company_id)

    async def fake_complete(messages):
        return FUNCTION_MD

    monkeypatch.setattr(openai_client, "complete_report", fake_complete)
    resp = client.post(
        f"/companies/{company_id}/reports/function", params={"function_key": FPA_KEY}
    )

    assert resp.status_code == 200
    roadmap = resp.json()["content_json"]["roadmap"]
    assert [phase["phase"] for phase in roadmap] == ["Now", "Next", "Later"]
    assert roadmap[0]["items"] == [
        {"title": "Governed forecast inputs", "desc": "Automate the actuals load into the forecast model."}
    ]


def test_function_report_missing_roadmap_phase_502(chat_db, monkeypatch):
    company_id = _seed_company(chat_db)
    _add_fpa_function(chat_db, company_id)

    async def fake_complete(messages):
        return FUNCTION_MD.replace("### Later", "### Someday")

    monkeypatch.setattr(openai_client, "complete_report", fake_complete)
    resp = client.post(
        f"/companies/{company_id}/reports/function", params={"function_key": FPA_KEY}
    )
    assert resp.status_code == 502
    assert "roadmap" in resp.json()["detail"].lower()


def test_function_report_requires_title_line(chat_db, monkeypatch):
    company_id = _seed_company(chat_db)
    _add_fpa_function(chat_db, company_id)

    async def fake_complete(messages):
        return FUNCTION_MD.split("\n", 2)[2]  # drop the H1 title

    monkeypatch.setattr(openai_client, "complete_report", fake_complete)
    resp = client.post(
        f"/companies/{company_id}/reports/function", params={"function_key": FPA_KEY}
    )
    assert resp.status_code == 502
    assert "title" in resp.json()["detail"]


def test_function_report_unknown_function_404(chat_db):
    company_id = _seed_company(chat_db)
    resp = client.post(
        f"/companies/{company_id}/reports/function", params={"function_key": "Nonexistent"}
    )
    assert resp.status_code == 404


def test_company_overview_returns_functions(chat_db):
    company_id = _seed_company(chat_db)
    _add_fpa_function(chat_db, company_id)
    # A function-grain persona + benchmark in the latest run — external map data.
    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM cluster_runs ORDER BY created_at DESC LIMIT 1")
        run_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO clusters (run_id, label, grain, size, avg_maturity,
                                  common_pain_points, common_tech_stack, summary)
            VALUES (%s, 'Spreadsheet-bound FP&A teams', 'function', 5, 2.7,
                    '[{"slot_key": "pain.manual_hours", "count": 4, "score": 14.0}]',
                    '["excel"]', 'fn persona')
            RETURNING id
            """,
            (run_id,),
        )
        fn_cluster_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO function_benchmarks
              (company_id, function_key, run_id, respondent_count, avg_maturity,
               percentile_cohort, percentile_peer, peer_group, cluster_id,
               common_pain_points, common_tech_stack)
            VALUES (%s, %s, %s, 1, 2.7, 55.0, 55.0, '{}', %s,
                    '[{"slot_key": "pain.manual_hours", "count": 4, "score": 14.0}]', '["excel"]')
            """,
            (company_id, FPA_KEY, run_id, fn_cluster_id),
        )
        conn.commit()

    resp = client.get(f"/companies/{company_id}/overview")

    assert resp.status_code == 200
    body = resp.json()
    assert body["company"]["name"] == "Acme Manufacturing"
    keys = [fn["function_key"] for fn in body["functions"]]
    assert keys == ["Accounting / Controllership", FPA_KEY]
    assert body["company_benchmark"]["percentile_peer"] == 62.0
    # Per-entity map points ride along, anonymized (persona + stats, no names).
    points = body["map_points"]
    assert points["company"] == [
        {"maturity": 3.1, "pain_load": 0.0, "persona": None, "is_self": True}
    ]
    assert points["function"] == [
        {
            "maturity": 2.7,
            "pain_load": 14.0,
            "persona": "Spreadsheet-bound FP&A teams",
            "is_self": True,
            "function_key": FPA_KEY,
        }
    ]


ACCOUNT_MD = """## Opportunity Sizing
120 manual hours/month across accounting and FP&A; mid-market manufacturing account.

## Benchmark And Cluster Placement
Company sits at the 62nd peer percentile; FP&A function at the 55th percentile of FP&A peers.

## Ideal Customer Profile Signals
Strong fit: spreadsheet-heavy close, NetSuite ERP, controller-led buying committee.

## Product Fit
- Manual reconciliation (company + Accounting function) — Current product: automated reconciliation.
- Narrative board reporting — Roadmap candidate: not in the capability document.
- Payroll — Third-party: out of scope.
"""


def test_account_report_admin_gated_and_grounded(chat_db, monkeypatch):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")
    company_id = _seed_company(chat_db)
    _add_fpa_function(chat_db, company_id)

    assert client.post(f"/companies/{company_id}/reports/account").status_code == 401

    async def fake_complete(messages):
        system = messages[0]["content"]
        assert "VENDOR CAPABILITY DOCUMENT" in system
        assert "never shown to the prospect".lower() in system.lower()
        assert "functions" in messages[1]["content"]
        return ACCOUNT_MD

    monkeypatch.setattr(openai_client, "complete_report", fake_complete)
    resp = client.post(
        f"/companies/{company_id}/reports/account", headers={"Authorization": "Bearer secret"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "account_internal"
    assert "## Product Fit" in body["rendered_md"]

    latest = client.get(
        f"/companies/{company_id}/reports/account/latest", headers={"Authorization": "Bearer secret"}
    )
    assert latest.status_code == 200
    assert latest.json()["id"] == body["id"]


def test_account_report_rejects_missing_fit_categories(chat_db, monkeypatch):
    monkeypatch.setenv("ADMIN_RECOMPUTE_TOKEN", "secret")
    company_id = _seed_company(chat_db)

    async def fake_complete(messages):
        return ACCOUNT_MD.replace("Current product", "covered").replace(
            "Roadmap candidate", "gap"
        ).replace("Third-party", "elsewhere")

    monkeypatch.setattr(openai_client, "complete_report", fake_complete)
    resp = client.post(
        f"/companies/{company_id}/reports/account", headers={"Authorization": "Bearer secret"}
    )
    assert resp.status_code == 502
    assert "fit categories" in resp.json()["detail"]


def test_company_context_groups_answers_by_function_with_attribution(chat_db):
    """Multi-grain redesign: the same slot answered by two functions keeps BOTH
    answers (attributed), instead of the old company-wide latest-wins flatten."""
    from api import report_repo

    company_id = _seed_company(chat_db)
    with psycopg.connect(chat_db) as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE sessions SET function_key = 'Accounting / Controllership' WHERE company_id = %s",
            (company_id,),
        )
        fpa_respondent, fpa_session = uuid.uuid4(), uuid.uuid4()
        cur.execute(
            "INSERT INTO respondents (id, company_id, name, role, email, source) "
            "VALUES (%s, %s, 'Pat', 'FP&A Director', 'pat@acme.example', 'real')",
            (fpa_respondent, company_id),
        )
        cur.execute(
            "INSERT INTO sessions (id, company_id, respondent_id, function_key, status, script_version) "
            "VALUES (%s, %s, %s, 'Financial Planning & Analysis (FP&A)', 'complete', 'test')",
            (fpa_session, company_id, fpa_respondent),
        )
        cur.execute(
            "INSERT INTO answers (session_id, slot_key, raw_text, structured_json, confidence, source, created_at) "
            """VALUES (%s, 'close.days', 'Close takes 6 days', '{"value": "6 days"}', 0.9, 'chat', now() + interval '1 minute')""",
            (fpa_session,),
        )
        conn.commit()

    context = report_repo.load_company_report_context(company_id)

    keys = [fn["function_key"] for fn in context["functions"]]
    assert keys == ["Accounting / Controllership", "Financial Planning & Analysis (FP&A)"]
    acct, fpa = context["functions"]
    acct_close = next(a for a in acct["answers"] if a["slot_key"] == "close.days")
    fpa_close = next(a for a in fpa["answers"] if a["slot_key"] == "close.days")
    assert acct_close["raw_text"] == "Close takes 12 days"  # NOT overwritten by FP&A's newer answer
    assert fpa_close["raw_text"] == "Close takes 6 days"
    assert acct_close["respondent_name"] == "Jo"
    assert fpa_close["respondent_name"] == "Pat"
    assert acct["respondents"][0]["name"] == "Jo"
    # The exec rollup keeps latest-per-slot across the whole company.
    top_close = next(a for a in context["answers"] if a["slot_key"] == "close.days")
    assert top_close["raw_text"] == "Close takes 6 days"
