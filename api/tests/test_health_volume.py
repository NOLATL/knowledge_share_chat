from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_volume_health_ok_when_writable(tmp_path, monkeypatch):
    target = tmp_path / "uploads"
    monkeypatch.setenv("UPLOAD_VOLUME_PATH", str(target))

    resp = client.get("/health/volume")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["writable"] is True
    assert Path(body["volume"]) == target
    assert target.is_dir()


def test_volume_health_503_when_unset(monkeypatch):
    monkeypatch.delenv("UPLOAD_VOLUME_PATH", raising=False)

    resp = client.get("/health/volume")

    assert resp.status_code == 503
