# Railway deployment (Task 0.3)

One Railway **project** holds four services: `Postgres` (pgvector), `api`,
`worker`, `web`. The app services build from this repo via per-service
Dockerfiles; each has a `railway.json` capturing its build/deploy config
(Dockerfile path, watch patterns, pre-deploy, health check).

## Prerequisites (you do these in the Railway dashboard)

1. **Create the project** and connect the GitHub repo `NOLATL/knowledge_share_chat`.
2. **Add Postgres (pgvector):** `+ New → Database → Add PostgreSQL` (current
   Railway images bundle pgvector). Migration `0001` runs `CREATE EXTENSION
   IF NOT EXISTS vector;`, so no manual enabling is needed.

## Create the three app services

For **each** of `api`, `worker`, `web`, do `+ New → GitHub Repo → NOLATL/knowledge_share_chat`,
then in the service settings:

| Setting | api | worker | web |
| --- | --- | --- | --- |
| Config-as-code path | `api/railway.json` | `worker/railway.json` | `web/railway.json` |
| Root directory | repo root (`/`) | `/` | `/` |
| Builder | Dockerfile (from config) | Dockerfile | Dockerfile |

> The Dockerfiles expect the **repo root** as build context (api/worker depend on
> the `shared` workspace member), so leave Root Directory at `/`. Watch patterns
> in each `railway.json` make unchanged services skip redeploy.

## Environment variables (per service)

Set these in each service's **Variables** tab. Use Railway **reference variables**
for the DB so it stays in sync:

- **api:** `DATABASE_URL = ${{Postgres.DATABASE_URL}}`, `OPENAI_API_KEY = <secret>`,
  `UPLOAD_VOLUME_PATH = /data/uploads`
- **worker:** `DATABASE_URL = ${{Postgres.DATABASE_URL}}`, `OPENAI_API_KEY = <secret>`
- **web:** `API_BASE_URL = ${{api.RAILWAY_PRIVATE_DOMAIN}}` (added/used in Task 1.4;
  set when the BFF needs it)

`PORT` is injected by Railway automatically; the Dockerfiles bind to it.

## Volume (api only)

Add a **Volume** to the `api` service mounted at **`/data/uploads`** (matches
`UPLOAD_VOLUME_PATH`). Verify after deploy: `GET https://<api-domain>/health/volume`
returns `{"status":"ok","writable":true}`.

## Migrations

The `api` service's `railway.json` sets a **pre-deploy command** that applies
migrations before the new version goes live:

```
uv run --no-dev --package playbook-api python scripts/migrate.py
```

It reads `DATABASE_URL` from the env and is idempotent.

## CI gate (Wait-for-CI)

GitHub Actions (`.github/workflows/ci.yml`) runs lint + tests on every push/PR.
In **each** service: Settings → enable **"Wait for CI"** (a.k.a. Check Suites)
so a deploy only proceeds after CI passes, and a failing CI **skips** the deploy.

## Acceptance checks (verify in the dashboard)

- [ ] A push to `main` deploys all three services **only after CI passes**.
- [ ] A failing CI run **blocks/skips** the deploy.
- [ ] `GET https://<api-domain>/health` returns `200 {"status":"ok"}`.
- [ ] `GET https://<api-domain>/health/volume` returns `writable: true`.

## Optional: Railway CLI (for Claude to assist)

Install: `pnpm add -g @railway/cli` (or `npm i -g @railway/cli`). Authenticate
non-interactively with a token from **Account Settings → Tokens**, exposed as an
env var:

- `RAILWAY_API_TOKEN` (account-scoped) — broad: link projects, set vars, logs.
- `RAILWAY_TOKEN` (project-scoped) — limited to one project/environment.

With the token set, `railway status`, `railway variables`, `railway logs`,
`railway redeploy`, and `railway run` work without a browser login.
