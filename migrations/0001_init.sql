-- Task 0.2 — base schema. Copied verbatim from BUILD_PLAN.md Appendix A
-- (the authoritative schema). The respondents.cluster_id -> clusters(id)
-- foreign key is intentionally deferred to 0002 to avoid a circular create-time
-- dependency (clusters does not exist yet when respondents is created).

CREATE EXTENSION IF NOT EXISTS vector;

-- Prospect organizations
CREATE TABLE companies (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  industry      text,
  size_bucket   text,                 -- e.g. '1-50','51-200','201-1000','1000+'
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Individual people who answer (drives the "Focus Controller" persona)
CREATE TABLE respondents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    uuid REFERENCES companies(id),
  name          text,
  role          text,                 -- Controller, FP&A Director, CFO, Analyst...
  email         text,
  source        text NOT NULL DEFAULT 'real',  -- 'real' | 'synthetic'
  persona_label text,                 -- set by clustering (Task 2.4)
  cluster_id    uuid,                 -- nullable FK to clusters(id), set post-run
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- A discovery conversation
CREATE TABLE sessions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    uuid REFERENCES companies(id),
  respondent_id uuid REFERENCES respondents(id),
  status        text NOT NULL DEFAULT 'in_progress', -- in_progress|paused|complete
  resume_token  uuid NOT NULL DEFAULT gen_random_uuid(),
  current_slot  text,                 -- slot_key the agent is working on
  script_version text,                 -- question-bank version this session used (Task 1.1)
  started_at    timestamptz NOT NULL DEFAULT now(),
  completed_at  timestamptz
);

-- The backbone question bank (seeded in Task 1.1)
CREATE TABLE questions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  category      text NOT NULL,        -- A..F (see Appendix B)
  slot_key      text NOT NULL UNIQUE, -- stable, immutable machine key, e.g. 'close.days'
  text          text NOT NULL,        -- editable wording (safe to change anytime)
  framework_tag text,                 -- 'SPIN' | 'MEDDIC' | 'JTBD'
  tier          text NOT NULL,        -- 'must_fill' | 'nice_to_have'
  order_hint    int  NOT NULL DEFAULT 100,
  active        boolean NOT NULL DEFAULT true, -- retire by setting false; never DELETE
  updated_at    timestamptz NOT NULL DEFAULT now()
);

-- Full transcript
CREATE TABLE messages (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id    uuid NOT NULL REFERENCES sessions(id),
  role          text NOT NULL,        -- user|assistant|system|tool
  content       text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Extracted, typed facts (the analytics feedstock)
CREATE TABLE answers (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id      uuid NOT NULL REFERENCES sessions(id),
  slot_key        text NOT NULL,
  raw_text        text,
  structured_json jsonb NOT NULL,     -- typed value(s) for the slot
  confidence      real,               -- 0..1 from extraction
  source          text NOT NULL DEFAULT 'chat', -- chat|email|document
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (session_id, slot_key, source)
);

-- Uploaded documents
CREATE TABLE documents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id    uuid REFERENCES companies(id),
  session_id    uuid REFERENCES sessions(id),
  filename      text NOT NULL,
  doc_type      text,                 -- financials|budget|forecast|schematic|deck|glossary|notes
  storage_url   text,                 -- path on the Railway Volume
  parsed_text   text,
  status        text NOT NULL DEFAULT 'pending', -- pending|parsed|error
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- RAG chunks
CREATE TABLE document_chunks (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id   uuid NOT NULL REFERENCES documents(id),
  chunk_text    text NOT NULL,
  embedding     vector(1536),
  metadata      jsonb,                -- {company_id, page, doc_type, ...}
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- One profile embedding + feature vector per respondent (clustering input)
CREATE TABLE respondent_embeddings (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  respondent_id  uuid NOT NULL REFERENCES respondents(id),
  embedding      vector(1536),
  feature_vector jsonb,               -- scaled numerics + one-hots
  umap_x         real,                -- stored 2D coords for the dashboard
  umap_y         real,
  model          text,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON respondent_embeddings USING hnsw (embedding vector_cosine_ops);

-- A clustering run (params + quality)
CREATE TABLE cluster_runs (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  algorithm        text NOT NULL,     -- 'hdbscan' | 'kmeans'
  params           jsonb NOT NULL,
  n_clusters       int,
  silhouette_score real,
  created_at       timestamptz NOT NULL DEFAULT now()
);

-- Discovered personas/clusters
CREATE TABLE clusters (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id             uuid NOT NULL REFERENCES cluster_runs(id),
  centroid           vector(1536),
  label              text,            -- LLM persona name (Task 2.4)
  size               int,
  avg_maturity       real,
  common_pain_points jsonb,           -- ranked slot_keys + counts
  common_tech_stack  jsonb,
  summary            text,
  community_id       int              -- from network analysis (Task 2.5)
);

-- A respondent's placement vs. the cohort
CREATE TABLE benchmarks (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  respondent_id      uuid NOT NULL REFERENCES respondents(id),
  run_id             uuid NOT NULL REFERENCES cluster_runs(id),
  cluster_id         uuid REFERENCES clusters(id),
  maturity_score     real,
  percentile_cohort  real,
  percentile_cluster real,
  nearest_neighbor_ids jsonb,
  computed_at        timestamptz NOT NULL DEFAULT now()
);

-- Tokenized colleague relay (Task 5.1)
CREATE TABLE email_relays (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id    uuid NOT NULL REFERENCES sessions(id),
  slot_key      text NOT NULL,
  token         uuid NOT NULL UNIQUE,
  sent_to_email text NOT NULL,
  status        text NOT NULL DEFAULT 'sent', -- sent|answered|expired
  reply_text    text,
  expires_at    timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Generated outputs
CREATE TABLE reports (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id   uuid NOT NULL REFERENCES sessions(id),
  type         text NOT NULL,         -- 'prospect' | 'vendor'
  content_json jsonb,
  rendered_md  text,
  created_at   timestamptz NOT NULL DEFAULT now()
);
