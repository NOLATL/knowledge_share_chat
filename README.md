# Playbook

AI-driven, vendor-agnostic discovery POC for finance/accounting prospects.

> **About the demo vendor.** The internal (presales) side of Playbook is written
> for **Corbel Analytics**, a fictional analytics-automation vendor. Its product
> is described in [`knowledge/vendor_capabilities.md`](./knowledge/vendor_capabilities.md),
> which grounds the product-fit mapping (Current product / Roadmap candidate /
> Third-party). Swap that file and `VENDOR_NAME` to point Playbook at any real
> product. The cohort data is synthetic.
See [`BUILD_PLAN.md`](./BUILD_PLAN.md) — the single source of truth for scope,
ground rules, and the sequenced backlog.

## Monorepo layout

| Path          | What it is                                                        |
| ------------- | ----------------------------------------------------------------- |
| `web/`        | Next.js 15 (App Router) frontend + thin BFF                       |
| `api/`        | FastAPI: chat orchestration, extraction, RAG, reports, relay      |
| `worker/`     | Python analytics pipeline (cron + manual trigger)                 |
| `shared/`     | Shared Python package (`playbook_shared`): models, question bank  |
| `migrations/` | Forward-only SQL migrations (pgvector + tables)                   |
| `scripts/`    | Reseed, synthetic data, eval scripts                              |

## Toolchain

- **Node** 20+ with **pnpm** (`web`).
- **Python** 3.12 with **uv** (`api`, `worker`, `shared`) — a uv workspace.
- **Postgres + pgvector** (Railway plugin in prod; a local container for tests).

## Local quickstart

```bash
# Python services (from repo root — uv workspace)
uv sync
uv run --package playbook-api uvicorn api.main:app --reload   # http://localhost:8000/health
uv run --package playbook-worker python -m worker.main        # runs and exits 0

# Web
cd web && pnpm install && pnpm dev                            # http://localhost:3000
```

## Database & migrations

Forward-only SQL migrations live in [`migrations/`](./migrations) and are applied
by a small runner (records applied files in a `schema_migrations` table; re-runs
are a no-op). Files named `*.notx.sql` run outside a transaction (for future
`CREATE INDEX CONCURRENTLY`).

```bash
# Set DATABASE_URL (pgvector-enabled Postgres), then:
uv run python scripts/migrate.py            # also the Railway pre-deploy command
```

## Question bank (the editable "script")

The discovery questionnaire lives in one human-editable file,
[`shared/question_bank.yaml`](./shared/question_bank.yaml) (the single source of
truth), and is synced to the `questions` table by an upsert reseed. `slot_key`s
are an **immutable contract** — reword/retier/reorder/retire freely, but never
rename or reuse a key (retire it and add a new one). Editing rules are documented
at the top of the YAML.

```bash
uv run python scripts/reseed_questions.py   # upsert by slot_key; retires missing
```

The conversation engine (Task 1.2) reads the **active** set from the DB at
runtime, so a reseed takes effect on the next session with no redeploy.

## Tests

```bash
uv run pytest                               # all Python services + migrations
cd web && pnpm test                         # web
```

> The migration/vector tests spin up a throwaway `pgvector/pgvector:pg16`
> container via testcontainers, so **Docker must be running** for them (locally:
> Docker Desktop; in CI: a Docker-enabled runner).

## CI / Deployment

CI (lint + tests for every service) runs via GitHub Actions
([`.github/workflows/ci.yml`](./.github/workflows/ci.yml)) and gates Railway
deploys (Wait-for-CI). Each service builds from its Dockerfile; per-service
`railway.json` files carry the build/deploy config. Full Railway setup steps are
in [`docs/deploy-railway.md`](./docs/deploy-railway.md).

Environment variables are documented in [`.env.example`](./.env.example).

## Analytics

Epic 2 analytics are on-demand for the POC/demo stage: synthetic seeding is an
explicit script, and recompute is triggered through `POST /admin/recompute` or a
manual worker run. The internal review dashboard is served by the web app at
`/admin/analytics` and is protected by the admin token. See
[`docs/analytics-epic2.md`](./docs/analytics-epic2.md).

## Demo

The live POC demo path is documented in [`docs/demo.md`](./docs/demo.md). Use the
admin demo cockpit at `/admin/demo` to track session readiness, reports,
document parsing, relay status, recompute, and selected-respondent analytics.
