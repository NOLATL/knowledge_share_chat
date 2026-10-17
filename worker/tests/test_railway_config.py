import json
from pathlib import Path


def test_worker_has_no_frequent_cron_schedule():
    config = json.loads((Path(__file__).resolve().parents[1] / "railway.json").read_text())
    deploy = config["deploy"]
    assert deploy.get("cronSchedule") not in {"*/30 * * * *", "*/5 * * * *"}
