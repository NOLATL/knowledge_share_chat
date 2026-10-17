import pytest

from playbook_shared.analytics.pipeline import RecomputeSummary
from worker.main import main, run


def _summary() -> RecomputeSummary:
    return RecomputeSummary(
        respondents_processed=1,
        run_id="run-1",
        company_benchmarks_written=1,
        function_entities=1,
        function_clusters=1,
        function_silhouette=0.0,
        function_benchmarks_written=1,
        company_entities=1,
        company_clusters=1,
        company_silhouette=0.0,
    )


def test_run_returns_zero(monkeypatch):
    monkeypatch.setattr("worker.main.recompute", _summary)
    assert run() == 0


def test_main_exits_zero(monkeypatch):
    monkeypatch.setattr("worker.main.recompute", _summary)
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
