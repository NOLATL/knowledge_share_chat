-- Multi-grain analytics (redesign Phase 2, Fork B): cluster SEPARATELY at each
-- grain — respondent (existing), function, company — so each grain has its own
-- personas and benchmark rollup. A "function" is the (company_id, function_key)
-- pair; multiple sessions roll into a function, multiple functions into a company.

-- Tag every cluster with the grain it was clustered at. Existing rows are
-- respondent-grain personas.
ALTER TABLE clusters ADD COLUMN grain text NOT NULL DEFAULT 'respondent';

-- The company's own (company-grain) persona, distinct from the respondent-persona
-- mix already captured by company_benchmarks.primary_cluster_id / cluster_exposure.
ALTER TABLE company_benchmarks ADD COLUMN company_cluster_id uuid REFERENCES clusters(id);

-- Per-function rollup — mirrors company_benchmarks. percentile_peer compares a
-- function against the SAME function_key across companies (FP&A vs all FP&A);
-- percentile_cohort is vs every function in the run.
CREATE TABLE function_benchmarks (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id         uuid NOT NULL REFERENCES companies(id),
  function_key       text NOT NULL,
  run_id             uuid NOT NULL REFERENCES cluster_runs(id),
  respondent_count   int  NOT NULL,
  avg_maturity       real,
  percentile_cohort  real,
  percentile_peer    real,
  peer_group         jsonb,
  cluster_id         uuid REFERENCES clusters(id),  -- this function's persona (grain='function')
  common_pain_points jsonb,
  common_tech_stack  jsonb,
  computed_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX function_benchmarks_lookup_idx
  ON function_benchmarks (company_id, function_key, computed_at DESC);

-- Embeddings + UMAP for function/company entities. The respondent grain keeps its
-- own respondent_embeddings table. entity_key = company_id for company grain,
-- 'company_id:function_key' for function grain.
CREATE TABLE entity_embeddings (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  grain          text NOT NULL,               -- 'function' | 'company'
  entity_key     text NOT NULL,
  run_id         uuid REFERENCES cluster_runs(id),
  embedding      vector(1536),
  feature_vector jsonb,
  umap_x         double precision,
  umap_y         double precision,
  model          text,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX entity_embeddings_lookup_idx
  ON entity_embeddings (grain, entity_key, created_at DESC);
