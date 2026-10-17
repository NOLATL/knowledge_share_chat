-- Company-level rollup of respondent analytics, one row per company per
-- cluster run (append-only, GR8 — never update in place). Written by the
-- recompute pipeline right after respondent benchmarks.

CREATE TABLE company_benchmarks (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id         uuid NOT NULL REFERENCES companies(id),
  run_id             uuid NOT NULL REFERENCES cluster_runs(id),
  respondent_count   int NOT NULL,
  avg_maturity       real,
  percentile_cohort  real,           -- vs all companies this run
  percentile_peer    real,           -- vs industry+size peers (fallback: cohort)
  peer_group         jsonb,          -- {industry, size_band, n, fell_back}
  primary_cluster_id uuid REFERENCES clusters(id),
  cluster_exposure   jsonb,          -- {cluster_id: member_count}
  common_pain_points jsonb,
  common_tech_stack  jsonb,
  computed_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON company_benchmarks (company_id, computed_at);
CREATE INDEX ON company_benchmarks (run_id);
