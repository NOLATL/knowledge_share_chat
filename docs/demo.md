# Playbook Demo Runbook

The demo runs on the framework machine and is reachable only over the tailnet. All data is synthetic.
There is no app-level login: the tailnet is the access boundary, so never expose this stack publicly.

## URLs

- Web: `https://framework.taila4cc29.ts.net:9444` (also listed on the tailnet demo hub)
- Stack: `~/demos/playbook` (Docker Compose: `db`, `api`, `web`). Up: `docker compose up -d --build`.

| Page | What it is |
| --- | --- |
| `/` | Start a new discovery chat |
| `/session/{resume_token}` | Resume a chat (the page shows its own resume link) |
| `/hub` | Entry point to the External and Internal views |
| `/external`, `/external/{company_id}` | Company-facing deliverable: executive rollup plus per-function roadmaps |
| `/internal` | Cohort intelligence: personas, account intel, pressure rankings, macro write-up, recompute |
| `/admin/demo?sessionId={session_id}` | Demo cockpit: readiness status for one session |

## Required environment (`~/demos/playbook/.env`)

- `OPENAI_API_KEY` is required for chat, extraction, embeddings, and report generation.
- `POSTGRES_PASSWORD` for the stack's own Postgres (pgvector).
- `RESEND_API_KEY` and `EMAIL_FROM` are optional; without them relays stay in demo-link mode.
- Do not set variables to an empty value (for example `OPENAI_BASE_URL=`): an empty base URL breaks every OpenAI call.

## Demo flow

1. Open or resume a discovery chat at `/` or `/session/{resume_token}`. The page shows slot coverage.
2. Upload a supported document (PDF, DOCX, PPTX, XLSX, CSV) from the chat page; it should show as parsed.
3. Ask a question grounded in the uploaded file; the assistant answers from it and continues discovery.
4. Send a colleague relay from the chat page. In demo-link mode, open the returned link and answer it.
5. Open `/external` for the company-facing deliverable.
6. Open `/internal`, run a recompute if needed, and walk the personas, member drill-down and write-up.
7. Use `/admin/demo?sessionId={session_id}` to check a session's readiness at any point.

## Troubleshooting

- Chat shows no reply: check `docker compose logs api` for `APIConnectionError` (bad or empty OpenAI settings).
- Missing benchmark or personas: run recompute from `/internal`.
- Document parse error: retry with XLSX/CSV, or check the extension and the upload limit.
- Relay does not email: expected in demo-link mode unless `RESEND_API_KEY` and `EMAIL_FROM` are set.
