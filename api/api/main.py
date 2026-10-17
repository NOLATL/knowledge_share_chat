"""FastAPI entrypoint. Task 0.1 provides a health check; later tasks add routers."""

import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException

from api import admin, chat, companies, documents, relays, reports, sessions

app = FastAPI(title="Playbook API")
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(admin.router)
app.include_router(companies.router)
app.include_router(documents.router)
app.include_router(reports.router)
app.include_router(relays.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe used by Railway and CI."""
    return {"status": "ok"}


@app.get("/health/volume")
def health_volume() -> dict[str, object]:
    """Prove the Railway Volume is mounted and writable at runtime (Task 0.3).

    Reads the mount path from ``UPLOAD_VOLUME_PATH``, writes+reads+deletes a
    throwaway file, and reports the result. 503 if the var is unset.
    """
    base = os.environ.get("UPLOAD_VOLUME_PATH")
    if not base:
        raise HTTPException(status_code=503, detail="UPLOAD_VOLUME_PATH not set")
    path = Path(base)
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".healthcheck-{uuid.uuid4().hex}"
        probe.write_text("ok", encoding="utf-8")
        ok = probe.read_text(encoding="utf-8") == "ok"
        probe.unlink()
    except OSError as err:
        raise HTTPException(status_code=503, detail=f"volume not writable: {err}") from err
    return {"status": "ok", "volume": str(path), "writable": ok}
