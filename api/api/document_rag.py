"""Retrieval helpers for document-grounded chat context."""

from __future__ import annotations

import uuid

from api import document_repo
from playbook_shared.analytics.openai_ops import embed_texts


def retrieve_document_context(session_id: uuid.UUID | str, query: str, *, limit: int = 4) -> str:
    company_id = document_repo.get_session_company_id(session_id)
    if company_id is None:
        return ""
    if not query.strip() or not document_repo.session_has_document_chunks(session_id):
        return ""

    query_embedding = embed_texts([query])[0]
    chunks = document_repo.retrieve_chunks(company_id=company_id, query_embedding=query_embedding, limit=limit)
    if not chunks:
        return ""

    parts = []
    for index, chunk in enumerate(chunks, start=1):
        text = " ".join(str(chunk["chunk_text"]).split())[:1200]
        filename = chunk["filename"]
        parts.append(f"[{index}] {filename}: {text}")
    return "\n".join(parts)


def retrieve_handbook_context(query: str, *, limit: int = 3) -> str:
    """Internal handbook guidance (global corpus — domain knowledge, not respondent facts)."""
    if not query.strip() or not document_repo.has_handbook_chunks():
        return ""

    query_embedding = embed_texts([query])[0]
    chunks = document_repo.retrieve_handbook_chunks(query_embedding=query_embedding, limit=limit)

    parts = []
    for index, chunk in enumerate(chunks, start=1):
        text = " ".join(str(chunk["chunk_text"]).split())[:1200]
        parts.append(f"[{index}] {chunk['source_file']} — {chunk['section']}: {text}")
    return "\n".join(parts)
