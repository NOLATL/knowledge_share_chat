"""Ingest the internal handbook corpus into `handbook_chunks` for RAG.

`knowledge/Playbook_RAG_MDs/*.md` is product/domain knowledge (finance and
accounting process handbooks), NOT session uploads. ``seed_handbook`` chunks the
markdown by section, embeds with the shared embedding model, and syncs the
`handbook_chunks` table: upsert by chunk_key, skip re-embedding unchanged text,
delete chunks whose key vanished from the corpus. Unlike the question bank this
is plain product config, not respondent history — hard delete is correct here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from psycopg.types.json import Jsonb

from playbook_shared.db import connect

CORPUS_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "Playbook_RAG_MDs"

CHUNK_WORDS = 500
CHUNK_OVERLAP_WORDS = 75
MIN_SECTION_WORDS = 40  # sections smaller than this merge into the previous chunk
EMBED_BATCH_SIZE = 100


@dataclass(frozen=True)
class HandbookChunk:
    chunk_key: str
    source_file: str
    section: str
    chunk_text: str
    content_sha: str


@dataclass
class HandbookSeedResult:
    embedded: list[str]  # chunk_keys inserted or re-embedded
    skipped: list[str]  # chunk_keys with unchanged content
    deleted: list[str]  # chunk_keys no longer in the corpus


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_words(text: str, *, chunk_words: int = CHUNK_WORDS, overlap_words: int = CHUNK_OVERLAP_WORDS) -> list[str]:
    # Same sliding window as api document chunking (kept here so shared/ has no api dependency).
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    step = max(1, chunk_words - overlap_words)
    while start < len(words):
        chunks.append(" ".join(words[start : start + chunk_words]))
        start += step
    return chunks


def split_markdown_sections(text: str) -> list[tuple[str, str]]:
    """Split on `##` headings → [(section_heading, section_text)].

    Content before the first `##` is grouped under the document's `#` title (or
    "intro"). Sections under MIN_SECTION_WORDS merge into the previous section so
    tiny fragments don't become their own retrieval units.
    """
    sections: list[tuple[str, list[str]]] = []
    heading = "intro"
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            sections.append((heading, lines))
            heading, lines = stripped.removeprefix("## ").strip(), []
        elif stripped.startswith("# ") and not sections and not lines:
            heading = stripped.removeprefix("# ").strip()
        elif stripped == "---":
            continue
        else:
            lines.append(line)
    sections.append((heading, lines))

    merged: list[tuple[str, str]] = []
    for section_heading, section_lines in sections:
        body = "\n".join(section_lines).strip()
        if not body:
            continue
        if merged and len(body.split()) < MIN_SECTION_WORDS:
            prev_heading, prev_body = merged[-1]
            merged[-1] = (prev_heading, f"{prev_body}\n\n{section_heading}\n{body}")
        else:
            merged.append((section_heading, body))
    return merged


def load_corpus(corpus_dir: Path | str | None = None) -> list[HandbookChunk]:
    corpus_dir = Path(corpus_dir) if corpus_dir else CORPUS_DIR
    if not corpus_dir.is_dir():
        raise FileNotFoundError(f"handbook corpus dir not found: {corpus_dir}")

    chunks: list[HandbookChunk] = []
    for path in sorted(corpus_dir.glob("*.md")):
        index = 0
        for section, body in split_markdown_sections(path.read_text(encoding="utf-8")):
            for piece in _split_words(body):
                text = f"{section}\n{piece}" if section else piece
                chunks.append(
                    HandbookChunk(
                        chunk_key=f"{path.name}#{index}",
                        source_file=path.name,
                        section=section,
                        chunk_text=text,
                        content_sha=_sha(text),
                    )
                )
                index += 1
    return chunks


def seed_handbook(
    database_url: str | None = None,
    corpus_dir: Path | str | None = None,
) -> HandbookSeedResult:
    """Sync the markdown corpus into `handbook_chunks`. Idempotent.

    Only chunks whose content changed (or that are new) are embedded, so a
    no-op reseed costs zero OpenAI calls.
    """
    # Lazy import: keeps `playbook_shared.handbook` importable without the openai extra.
    from playbook_shared.analytics.openai_ops import embed_texts, embedding_model

    corpus = load_corpus(corpus_dir)
    corpus_keys = {c.chunk_key for c in corpus}

    conn = connect(database_url, register_vector_types=False)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT chunk_key, metadata->>'content_sha' FROM handbook_chunks")
            existing = dict(cur.fetchall())

            to_embed = [c for c in corpus if existing.get(c.chunk_key) != c.content_sha]
            embed_keys = {c.chunk_key for c in to_embed}
            skipped = [c.chunk_key for c in corpus if c.chunk_key not in embed_keys]

            model = embedding_model()
            for start in range(0, len(to_embed), EMBED_BATCH_SIZE):
                batch = to_embed[start : start + EMBED_BATCH_SIZE]
                vectors = embed_texts([c.chunk_text for c in batch])
                for chunk, vector in zip(batch, vectors, strict=True):
                    cur.execute(
                        """
                        INSERT INTO handbook_chunks
                            (chunk_key, source_file, section, chunk_text, embedding, metadata)
                        VALUES (%s, %s, %s, %s, %s::vector, %s)
                        ON CONFLICT (chunk_key) DO UPDATE SET
                            source_file = EXCLUDED.source_file,
                            section     = EXCLUDED.section,
                            chunk_text  = EXCLUDED.chunk_text,
                            embedding   = EXCLUDED.embedding,
                            metadata    = EXCLUDED.metadata
                        """,
                        (
                            chunk.chunk_key,
                            chunk.source_file,
                            chunk.section,
                            chunk.chunk_text,
                            "[" + ",".join(f"{v:.8f}" for v in vector) + "]",
                            Jsonb({"content_sha": chunk.content_sha, "embedding_model": model}),
                        ),
                    )

            stale = sorted(set(existing) - corpus_keys)
            if stale:
                cur.execute("DELETE FROM handbook_chunks WHERE chunk_key = ANY(%s)", (stale,))
    finally:
        conn.close()

    return HandbookSeedResult(
        embedded=[c.chunk_key for c in to_embed],
        skipped=skipped,
        deleted=stale,
    )
