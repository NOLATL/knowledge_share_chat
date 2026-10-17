"""Session-scoped document upload and listing endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from api import document_processing, document_repo, repo

router = APIRouter()


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    doc_type: str | None
    status: str
    created_at: str
    chunk_count: int


@router.get("/sessions/{session_id}/documents", response_model=list[DocumentOut])
async def list_documents(session_id: uuid.UUID) -> list[DocumentOut]:
    session = await run_in_threadpool(repo.get_session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    rows = await run_in_threadpool(document_repo.list_session_documents, session_id)
    return [
        DocumentOut(
            id=row["id"],
            filename=row["filename"],
            doc_type=row["doc_type"],
            status=row["status"],
            created_at=row["created_at"].isoformat(),
            chunk_count=row["chunk_count"],
        )
        for row in rows
    ]


@router.post("/sessions/{session_id}/documents", response_model=DocumentOut)
async def upload_document(
    session_id: uuid.UUID,
    file: UploadFile = File(...),
    doc_type: str | None = Form(default=None),
) -> DocumentOut:
    session = await run_in_threadpool(repo.get_session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    filename = document_processing.safe_filename(file.filename or "")
    try:
        document_processing.validate_extension(filename)
        data = document_processing.read_limited_upload(await file.read())
    except document_processing.DocumentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        company_id = await run_in_threadpool(document_repo.ensure_session_company, session_id)
        if company_id is None:  # pragma: no cover - session was just checked
            raise HTTPException(status_code=404, detail="session not found")
        document_id = uuid.uuid4()
        resolved_type = document_processing.infer_doc_type(filename, doc_type)
        target_dir = document_processing.upload_root() / str(session_id) / str(document_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        target.write_bytes(data)

        await run_in_threadpool(
            document_repo.insert_document,
            document_id=document_id,
            company_id=company_id,
            session_id=session_id,
            filename=filename,
            doc_type=resolved_type,
            storage_url=str(target),
        )

        try:
            parsed_text = await run_in_threadpool(document_processing.parse_file, target)
            await run_in_threadpool(
                document_processing.write_chunks,
                document_id=document_id,
                company_id=company_id,
                session_id=session_id,
                doc_type=resolved_type,
                parsed_text=parsed_text,
            )
            await run_in_threadpool(
                document_repo.update_document_status,
                document_id,
                status="parsed",
                parsed_text=parsed_text,
            )
        except Exception as exc:  # noqa: BLE001 - upload should report a persisted error row
            await run_in_threadpool(document_repo.update_document_status, document_id, status="error")
            raise HTTPException(status_code=422, detail=f"document parse failed: {exc}") from exc

        try:
            await document_processing.extract_document_answers(session_id, parsed_text)
        except Exception:
            # Document extraction is best-effort; the parsed document and chunks are still useful.
            pass
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    rows = await run_in_threadpool(document_repo.list_session_documents, session_id)
    row = next(row for row in rows if row["id"] == document_id)
    return DocumentOut(
        id=row["id"],
        filename=row["filename"],
        doc_type=row["doc_type"],
        status=row["status"],
        created_at=row["created_at"].isoformat(),
        chunk_count=row["chunk_count"],
    )
