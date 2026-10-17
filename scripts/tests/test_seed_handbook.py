"""Handbook corpus sync: section chunking, sha-skip idempotency, delete-on-removal.

Uses the shared `fresh_db_url` container fixture (repo-root conftest.py) with the
real migrations; embeddings are mocked (no OpenAI calls).
"""

from __future__ import annotations

from pathlib import Path

import psycopg

from playbook_shared.handbook import load_corpus, seed_handbook, split_markdown_sections
from playbook_shared.migrate import run_migrations

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

DOC_A = """# Volume T — Test Close Handbook

## What is this function?
{}

## The Close Journey
{}
""".format("Close words " * 60, "Journey words " * 60)

DOC_B = "# Volume U — Other\n\n## Reconciliation\n" + ("Recon words " * 60)


def _mock_embeddings(monkeypatch, calls: list[list[str]]):
    def fake_embed(texts, model=None):
        calls.append(list(texts))
        return [[0.01] * 1536 for _ in texts]

    monkeypatch.setattr("playbook_shared.analytics.openai_ops.embed_texts", fake_embed)


def _write_corpus(tmp_path: Path) -> Path:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "T_Close.md").write_text(DOC_A, encoding="utf-8")
    (corpus / "U_Other.md").write_text(DOC_B, encoding="utf-8")
    return corpus


def _rows(url: str) -> dict[str, dict]:
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT chunk_key, source_file, section, metadata->>'content_sha' FROM handbook_chunks")
        return {r[0]: {"source_file": r[1], "section": r[2], "sha": r[3]} for r in cur.fetchall()}


def test_split_markdown_sections_keeps_headings_and_merges_tiny():
    text = "# Title\n\nintro body here\n\n---\n\n## Big Section\n" + ("word " * 50) + "\n## Tiny\nshort"
    sections = split_markdown_sections(text)
    headings = [h for h, _ in sections]
    assert headings == ["Title", "Big Section"]  # Tiny merged into Big Section
    assert "short" in sections[1][1]


def test_load_real_corpus_has_unique_keys_and_sections():
    chunks = load_corpus()  # default: knowledge/Playbook_RAG_MDs
    assert len(chunks) > 50
    keys = [c.chunk_key for c in chunks]
    assert len(keys) == len(set(keys))
    assert all(c.section for c in chunks)


def test_seed_inserts_then_skips_unchanged(fresh_db_url, tmp_path, monkeypatch):
    run_migrations(fresh_db_url, MIGRATIONS_DIR)
    corpus = _write_corpus(tmp_path)
    calls: list[list[str]] = []
    _mock_embeddings(monkeypatch, calls)

    first = seed_handbook(fresh_db_url, corpus)
    assert len(first.embedded) >= 3  # two sections in A + one in B
    assert first.skipped == [] and first.deleted == []
    rows = _rows(fresh_db_url)
    assert rows["T_Close.md#0"]["section"] == "What is this function?"

    second = seed_handbook(fresh_db_url, corpus)
    assert second.embedded == []  # unchanged shas → zero embedding calls
    assert len(second.skipped) == len(first.embedded)
    assert len(calls) == 1  # only the first run embedded anything


def test_seed_reembeds_changed_and_deletes_removed(fresh_db_url, tmp_path, monkeypatch):
    run_migrations(fresh_db_url, MIGRATIONS_DIR)
    corpus = _write_corpus(tmp_path)
    calls: list[list[str]] = []
    _mock_embeddings(monkeypatch, calls)
    seed_handbook(fresh_db_url, corpus)
    before = _rows(fresh_db_url)

    (corpus / "T_Close.md").write_text(DOC_A.replace("Close words", "Edited words"), encoding="utf-8")
    (corpus / "U_Other.md").unlink()
    result = seed_handbook(fresh_db_url, corpus)

    assert "T_Close.md#0" in result.embedded
    assert result.deleted == ["U_Other.md#0"]
    after = _rows(fresh_db_url)
    assert "U_Other.md#0" not in after
    assert after["T_Close.md#0"]["sha"] != before["T_Close.md#0"]["sha"]
