"""Company directory + the external per-company deliverable (Task 8.3)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from api import report_generation, report_repo

router = APIRouter()


class CompanyReportOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    type: str
    content_json: dict[str, Any]
    rendered_md: str
    created_at: str


@router.get("/companies")
async def list_companies(include_synthetic: bool = False) -> list[dict[str, Any]]:
    return await run_in_threadpool(report_repo.list_companies, include_synthetic=include_synthetic)


@router.get("/companies/by-code/{account_code}")
async def get_company_by_code(account_code: str) -> dict[str, Any]:
    """Resolve a human-friendly account code (e.g. C-00042) to the company record."""
    company_id = await run_in_threadpool(report_repo.company_id_by_account_code, account_code)
    if company_id is None:
        raise HTTPException(status_code=404, detail="company not found")
    context = await run_in_threadpool(report_repo.load_company_report_context, company_id)
    return {
        "company": context["company"],
        "respondents": context["respondents"],
        "company_benchmark": context["company_benchmark"],
        "benchmark_history": context["benchmark_history"],
    }


@router.get("/companies/{company_id}/overview")
async def get_company_overview(company_id: uuid.UUID) -> dict[str, Any]:
    """Everything the external destination renders: company profile, exec-rollup
    answers, per-function breakdown (attributed answers + benchmarks + personas),
    company benchmark, and history."""
    context = await run_in_threadpool(report_repo.load_company_report_context, company_id)
    if context is None:
        raise HTTPException(status_code=404, detail="company not found")
    # Anonymized per-entity points for the evaluation charts (no member names).
    context["map_points"] = await run_in_threadpool(report_repo.cohort_map_points, company_id)
    return context


@router.post("/companies/{company_id}/reports/function", response_model=CompanyReportOut)
async def post_function_report(company_id: uuid.UUID, function_key: str) -> CompanyReportOut:
    try:
        report = await report_generation.generate_function_report(company_id, function_key)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if report is None:
        raise HTTPException(status_code=404, detail="company or function not found")
    return _out(report)


@router.get("/companies/{company_id}/reports/function/latest", response_model=CompanyReportOut)
async def get_latest_function_report(company_id: uuid.UUID, function_key: str) -> CompanyReportOut:
    report = await run_in_threadpool(report_repo.latest_function_report, company_id, function_key)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return _out(report)


@router.post("/companies/{company_id}/reports/external", response_model=CompanyReportOut)
async def post_company_report(company_id: uuid.UUID) -> CompanyReportOut:
    try:
        report = await report_generation.generate_company_report(company_id)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if report is None:
        raise HTTPException(status_code=404, detail="company not found")
    return _out(report)


@router.get("/companies/{company_id}/reports/external/latest", response_model=CompanyReportOut)
async def get_latest_company_report(company_id: uuid.UUID) -> CompanyReportOut:
    report = await run_in_threadpool(report_repo.latest_company_report, company_id, "company_external")
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return _out(report)


def _out(report: dict[str, Any]) -> CompanyReportOut:
    return CompanyReportOut(
        id=report["id"],
        company_id=report["company_id"],
        type=report["type"],
        content_json=report["content_json"],
        rendered_md=report["rendered_md"],
        created_at=report["created_at"].isoformat(),
    )
