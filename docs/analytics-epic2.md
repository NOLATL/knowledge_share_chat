# Epic 2 analytics

## Closeout status

Epic 2 is functionally complete for the current solo/demo stage. Production has
the full analytics loop live:

- 150 synthetic respondents, 150 completed sessions, and 3,750 answer rows.
- Synthetic respondents are clearly tagged with `respondents.source = 'synthetic'`.
- On-demand recompute writes feature vectors, 1536-dimension embeddings, UMAP
  coordinates, append-only cluster runs, clusters, and benchmark rows.
- Latest production gate after content-weighted pain scoring: 150 respondents,
  6 clusters, silhouette 0.376, and 150 benchmarks.
- `/admin/analytics` is live on the Railway web service as the internal review
  dashboard, with manual recompute controls.

Deferred from Epic 2:

- Real-world survey calibration of the synthetic cohort. Hold synthetic data
  quality refinements until actual survey/reference data is selected.
- Benchmark drill-down UI for individual respondent history and nearest-neighbor
  excerpts.
- Deeper network graph visualization and central-node reporting.
- LLM-generated narrative summaries. Current cluster labels and summaries are
  deterministic/cost-controlled.

Analytics recompute is on demand by default for the POC/demo stage. The worker
Railway cron is disabled in `worker/railway.json`; use the admin endpoint or a
manual worker run when you want to refresh clusters and benchmarks.

## Synthetic cohort

Start with a small deterministic or live quality gate before seeding the full
cohort:

```bash
uv run python scripts/seed_synthetic.py --count 20 --deterministic
uv run python scripts/seed_synthetic.py --count 20
uv run python scripts/seed_synthetic.py --count 150
```

Synthetic respondents are tagged with `respondents.source = 'synthetic'` and
stable `synthetic+<seed>-<index>@playbook.local` emails so repeated runs skip
existing rows instead of flooding the database.

## Recompute

Manual API trigger:

```bash
curl -X POST "$API_BASE_URL/admin/recompute" \
  -H "Authorization: Bearer $ADMIN_RECOMPUTE_TOKEN"
```

Internal dashboard:

```text
/admin/analytics
```

The dashboard is token-gated and includes latest run metrics, cluster cards,
UMAP scatter, pressure rankings, benchmark samples, and a manual recompute
button. Keep the admin token private and rotate it if it is shared outside the
operator context.

Manual worker run:

```bash
uv run --package playbook-worker python -m worker.main
```

## Cost controls

Synthetic generation defaults to `gpt-4o-mini` and falls back to
`gpt-4.1-mini` only if the first model fails. Embeddings use
`text-embedding-3-small`, matching the existing `vector(1536)` schema.
