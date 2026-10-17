-- Internal handbook RAG corpus (product/domain knowledge, NOT session uploads).
-- Global — deliberately no company/session scoping; retrieval must never present
-- handbook text as respondent facts (enforced at the prompt layer).
-- Seeded/synced by scripts/seed_handbook.py from knowledge/Playbook_RAG_MDs/.

CREATE TABLE handbook_chunks (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chunk_key    text NOT NULL UNIQUE,   -- "V2_R2R.md#3" (source file + chunk index)
  source_file  text NOT NULL,
  section      text,                   -- markdown section heading the chunk came from
  chunk_text   text NOT NULL,
  embedding    vector(1536),
  metadata     jsonb NOT NULL DEFAULT '{}'::jsonb,  -- {content_sha, embedding_model}
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON handbook_chunks USING hnsw (embedding vector_cosine_ops);
