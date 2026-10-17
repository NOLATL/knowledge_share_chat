"""Internal report endpoints: cohort macro intelligence + account intel."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from api import admin, report_generation, report_repo

router = APIRouter()


class InternalReportOut(BaseModel):
    id: uuid.UUID
    type: str
    content_json: dict[str, Any]
    rendered_md: str
    created_at: str


@router.post("/reports/internal", response_model=InternalReportOut)
async def post_internal_report(authorization: str | None = Header(default=None)) -> InternalReportOut:
    admin._require_admin(authorization)
    try:
        report = await report_generation.generate_internal_intelligence()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _internal_out(report)


@router.get("/reports/internal/latest", response_model=InternalReportOut)
async def get_latest_internal_report(authorization: str | None = Header(default=None)) -> InternalReportOut:
    admin._require_admin(authorization)
    report = await run_in_threadpool(report_repo.latest_internal_report)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return _internal_out(report)


class AccountReportOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    type: str
    content_json: dict[str, Any]
    rendered_md: str
    created_at: str


@router.post("/companies/{company_id}/reports/account", response_model=AccountReportOut)
async def post_account_report(
    company_id: uuid.UUID,
    authorization: str | None = Header(default=None),
) -> AccountReportOut:
    admin._require_admin(authorization)
    try:
        report = await report_generation.generate_account_report(company_id)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if report is None:
        raise HTTPException(status_code=404, detail="company not found")
    return _account_out(report)


@router.get("/companies/{company_id}/reports/account/latest", response_model=AccountReportOut)
async def get_latest_account_report(
    company_id: uuid.UUID,
    authorization: str | None = Header(default=None),
) -> AccountReportOut:
    admin._require_admin(authorization)
    report = await run_in_threadpool(report_repo.latest_company_report, company_id, "account_internal")
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return _account_out(report)


def _account_out(report: dict[str, Any]) -> AccountReportOut:
    return AccountReportOut(
        id=report["id"],
        company_id=report["company_id"],
        type=report["type"],
        content_json=report["content_json"],
        rendered_md=report["rendered_md"],
        created_at=report["created_at"].isoformat(),
    )


def _internal_out(report: dict[str, Any]) -> InternalReportOut:
    return InternalReportOut(
        id=report["id"],
        type=report["type"],
        content_json=report["content_json"],
        rendered_md=report["rendered_md"],
        created_at=report["created_at"].isoformat(),
    )
