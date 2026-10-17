# Build Plan — Playbook (Finance/Tax/Accounting POC)

> Working repo name: `playbook` (rename if you like). This document is the single source of truth for the agent. Build the backlog **in order, one task at a time**, opening one PR per task. Do not start a task until its dependencies are merged. Stop at each task's acceptance criteria and let the human review.

---

## PART 1 — OVERVIEW (read before doing anything)

### Mission
Build a proof-of-concept web app that runs an AI-driven, vendor-agnostic discovery conversation with finance/accounting prospects (the "Focus Controller" persona), captures their answers as clean structured data, and feeds those into an analytics layer that discovers personas/clusters and benchmarks each respondent against a cohort. The POC produces two outputs: a **prospect-facing roadmap** and a **vendor-facing intelligence view**.

### Why this matters strategically (design the build to honor this)
The benchmarking is not a static feature — **it compounds.** Every company that goes through discovery makes the cohort richer, which makes the next company's benchmark more accurate and the persona/cluster map more credible. This is the project's core long-term value, and the build must be designed so that this compounding is real (and demonstrable), not bolted on later. Three downstream payoffs flow from it, and the architecture should make each of them easy to reach:

1. **A recurring engagement flywheel for the vendor.** Because benchmarks shift as the dataset grows, each new respondent is a future touch point: re-benchmark reports, "how you've moved vs. your cohort" updates, periodic industry-trend releases, and natural hooks for announcing new product releases. The data model must preserve history (every cluster run and benchmark is timestamped and retained) so a respondent can be compared against themselves and against the cohort *over time*.
2. **A fundable, defensible asset.** The accumulated, structured discovery dataset is exactly the kind of proprietary market intelligence that strengthens future VC rounds — it is evidence of a data moat that gets stronger with usage. Keep the cohort data clean, attributable, exportable, and longitudinal so it can later back an investor narrative.
3. **Baked-in market scoping that justifies product investment.** Because every respondent is tagged to a persona/cluster with sized common pain points, the dataset *quantifies* which segments are largest and most underserved — which directly justifies where to invest product-development effort. The vendor view and cohort intelligence should surface this segment-sizing explicitly, so "build feature X because N% of the cohort in the largest cluster has pain Y" is a one-click argument.

**Build implication:** never overwrite or collapse historical analytics. Cluster runs, benchmarks, and persona snapshots are append-only and timestamped. The POC only needs *one* recompute to work, but the schema and pipeline must already support many runs over time so the longitudinal story is true on day one and the flywheel/funding/scoping narratives are demonstrable, not hypothetical.

### Locked decisions (do NOT revisit)
- **Hosting:** Railway. One project, multiple services, one Postgres+pgvector DB.
- **LLM provider:** OpenAI. Chat = GPT-5.4 mini; extraction/reports = GPT-5.4; embeddings = text-embedding-3-small (1536 dims). Verify exact model IDs against the OpenAI dashboard at build time; if `text-embedding-3-small` is deprecated, use the current recommended small embedding model and keep the dimension consistent in the schema.
- **Frontend:** Next.js 15 (App Router) + Vercel AI SDK (`ai` + `@ai-sdk/react`) `useChat`.
- **Backend:** Python + FastAPI (owns all LLM orchestration, state, RAG, reports).
- **Analytics:** Python worker (UMAP + HDBSCAN + NetworkX/Louvain).
- **DB:** Postgres + pgvector (Railway template), HNSW indexes.

### Global ground rules (these MUST hold across every task)
1. **Vendor-agnostic.** Recommendations are category-level ("adopt automated reconciliation tooling"), never a single named vendor as "the answer." This rule lives in the system prompt and in report generation. Add a test that asserts no hard-coded vendor name appears in prospect-report output.
2. **Two-call pattern.** Each conversational turn = (a) one streamed chat call for the natural reply, and (b) one separate, non-streamed Structured Outputs call that extracts typed facts. Never make one call do both.
3. **Server-side state.** Authoritative session state lives in Postgres, not in the prompt or the browser. The prompt receives a compact injected summary of filled/unfilled slots each turn.
4. **Strict structured outputs.** All extraction and tool schemas use Pydantic with `strict: true`. Disable parallel tool calls when strict is on.
5. **Simpler fork always.** Tokenized email links over inbound email parsing; cron worker over Redis queue; Docling+pandas over a multi-parser pipeline; magic-link resume over full auth. Do not build the harder option unless a task explicitly says so.
6. **Files on a Volume.** Railway container FS is ephemeral. Uploaded files go to a mounted Railway Volume; parsed text + embeddings go to Postgres.
7. **No scope creep.** Real-time multi-user collab, true inbound reply-by-email, and authenticated accounts are OUT of scope. If a task seems to need them, stop and flag it.
8. **Append-only analytics history.** Cluster runs, benchmarks, and persona snapshots are never overwritten or deleted — each recompute creates a new timestamped `cluster_run` and new `benchmarks` rows. Benchmarking must work as a time series so a respondent can be compared against the cohort *and against their own prior benchmark*. This is what makes the compounding-data flywheel real; do not "optimize" it away by mutating the latest run in place.
9. **The script is config, not code.** The discovery questionnaire (the "script") and the agent's behavioral rules must be editable by a non-engineer without touching application code or redeploying. The question bank lives in one human-readable, version-controlled config file that is the single source of truth; a reseed command syncs it to the DB. The conversational system prompt's editable pieces (philosophy, improvisation rules, SPIN follow-up guidance) likewise live in a config/template file, not inline string literals scattered through the code. Expect this script to be refined repeatedly by domain experts over time — make editing it a one-file, one-command operation.
10. **`slot_key`s are an immutable contract.** You may freely edit a question's wording, tier, order, framework tag, or retire it (set `active=false`) — those changes are safe and pulled in by reseed. But never rename or reuse an existing `slot_key`, because feature vectors and longitudinal benchmarks are keyed on it; renaming silently breaks cross-cohort comparability. To "change" a slot, retire the old one and add a new key. Retiring (not deleting) preserves historical answers.

### Service / repo layout
```
playbook/
├─ web/                  # Next.js 15 app (frontend + thin BFF)
├─ api/                  # FastAPI: chat orchestration, extraction, RAG, reports, relay
├─ worker/              # Python analytics pipeline (cron + manual trigger)
├─ shared/              # shared Pydantic models / question bank seed / schemas
├─ migrations/          # SQL or Alembic migrations (pgvector extension + tables)
└─ scripts/             # synthetic data generator, seed scripts, eval scripts
```
On Railway: one service each for `web`, `api`, `worker`, plus the Postgres+pgvector plugin. Use per-service watch paths so unchanged services skip redeploy.

### Conventions
- **One PR per task.** Branch name = task ID (e.g., `task-1.3-extraction`). PR description restates the acceptance criteria as a checklist and marks each.
- **Migrations** are forward-only and committed with the task that needs them. pgvector index creation that uses `CONCURRENTLY` must be non-transactional.
- **Env vars** are declared in `.env.example` the moment a task introduces one. Never hard-code secrets.
- **Tests** ship with the task. Acceptance criteria phrased as "test passes" mean an automated test in the PR.
- **CI gate:** lint + tests must pass before Railway deploys (Wait-for-CI enabled in Task 0.3).

### Definition of Done (global)
A task is done when: code is merged, its migration (if any) is applied, `.env.example` is updated, tests for its acceptance criteria pass in CI, and the deployed service still boots and streams a hello-world end-to-end.

### How to work this backlog
Go top to bottom. The order deliberately **de-risks the analytics layer early** (Epic 2) because that is the hardest part and the most likely to silently fail. Do not jump ahead to RAG or dashboards before the spine and analytics work.

---

## PART 2 — THE STEPS (sequenced backlog)

### EPIC 0 — Scaffold & CI/CD

**Task 0.1 — Repo + service skeletons**
- Goal: monorepo with bootable `web`, `api`, `worker` skeletons.
- Build: Next.js 15 app in `web/` (renders a placeholder page); FastAPI app in `api/` with `GET /health`; Python `worker/` with a no-op entrypoint that exits cleanly; `shared/` package importable by `api` and `worker`.
- Acceptance criteria:
  - [ ] `api` `GET /health` returns 200 `{"status":"ok"}`.
  - [ ] `web` renders a placeholder page locally.
  - [ ] `worker` runs and exits 0.
  - [ ] `.env.example` exists with `OPENAI_API_KEY`, `DATABASE_URL` placeholders.
- Depends on: none.

**Task 0.2 — Postgres + pgvector + base migrations**
- Goal: database with pgvector enabled and the full schema applied.
- Build: Railway Postgres+pgvector plugin; migration that runs `CREATE EXTENSION IF NOT EXISTS vector;` and creates all tables from the full schema in Appendix A (copy it verbatim); HNSW indexes on vector columns.
- Acceptance criteria:
  - [ ] Migration applies cleanly on a fresh DB.
  - [ ] `\dt` shows all tables in Appendix A.
  - [ ] A smoke test inserts and cosine-searches a dummy `vector(1536)` row successfully.
- Depends on: 0.1.

**Task 0.3 — CI/CD + Railway deploy**
- Goal: push-to-deploy with a CI gate.
- Build: GitHub Actions (lint + test) for each service; connect each Railway service to its repo with autodeploy on `main`; enable Wait-for-CI; add a Railway Volume mounted in `api` for uploads; set pre-deploy command to run migrations.
- Acceptance criteria:
  - [ ] A push to `main` deploys all three services only after CI passes.
  - [ ] A failing CI run blocks (SKIPS) the deploy.
  - [ ] `api` `/health` is reachable at its public Railway domain.
  - [ ] Volume mount path is set via env var and writable at runtime.
- Depends on: 0.1, 0.2.

---

### EPIC 1 — Discovery spine

**Task 1.1 — Question bank as editable, versioned config**
- Goal: the backbone "script" as a single human-editable source of truth that anyone can refine without code changes, synced to the DB by one command.
- Build:
  - A version-controlled config file `shared/question_bank.yaml` that is the **single source of truth**. It carries a top-level `version` string (e.g. `2026.06.0`) and a list of questions, each with `slot_key`, `category`, `text`, `framework_tag`, `tier`, `order_hint`, `active`. Populate it from Appendix B.
  - A reseed command (`scripts/reseed_questions.py`, runnable locally and as a Railway one-off) that **upserts by `slot_key`** — inserts new keys, updates wording/tier/order/framework/active on existing keys, and sets `active=false` for any slot_key no longer present in the file (never deletes). It refuses to run if two rows share a slot_key and warns loudly if a slot_key that has answers attached would be retired.
  - Stamp the file's `version` onto each new session's `sessions.script_version` at session start, so every session records which script it was answered against.
  - Keep a short editing guide at the top of the YAML (how to add/retire/reword, and the slot_key immutability rule) so a domain expert editing it sees the rules in context.
- Acceptance criteria:
  - [ ] Editing `text`/`tier`/`order_hint` in the YAML and re-running reseed updates the existing rows in place (no duplicates), confirmed by a test.
  - [ ] Removing a question from the YAML sets its row `active=false` rather than deleting it; its historical `answers` remain intact.
  - [ ] Adding a new `slot_key` inserts a new active row.
  - [ ] At least 12 (we ship 13) `must_fill` slots exist spanning all six categories; every row has a valid `framework_tag` and `tier`.
  - [ ] New sessions record the current `version` in `sessions.script_version`.
- Depends on: 0.2.
- Note: the conversation engine (1.2) must read the active question set from the DB at runtime — never hard-code questions in the agent code — so a reseed takes effect on the next session with no redeploy.

**Task 1.1b — Minimal question-bank editor (convenience path for non-engineers)**
- Goal: let domain experts refine the script through a browser, not a YAML file, once the project is past the initial build. The file+reseed path from 1.1 always remains the canonical, version-controlled mechanism; this UI is a convenience layer over the same `questions` table.
- Build: a simple admin page (`/admin/questions`) listing active and retired questions, allowing edit of `text`, `tier`, `order_hint`, `framework_tag`, toggle `active`, and add a new question (which requires a new unique `slot_key`, validated against reuse). Edits write to the `questions` table and bump `updated_at`. Provide an "export to YAML" action so DB edits can be round-tripped back into `shared/question_bank.yaml` and committed (keeps the source of truth in sync).
- Acceptance criteria:
  - [ ] An expert can reword a question and reorder the script from the browser; the change shows up in the next session with no redeploy.
  - [ ] The editor blocks renaming/reusing an existing `slot_key` (enforces ground rule 10) and blocks hard deletion (retire only).
  - [ ] Export produces a YAML file identical in shape to `shared/question_bank.yaml`.
- Depends on: 1.1. (Lower priority than the spine — fine to defer until after Milestone A, but it directly serves the "refine with experts over time" goal, so don't drop it.)

**Task 1.2 — Chat orchestration (streamed reply)**
- Goal: a guided conversation that streams responses and tracks slot state server-side.
- Build: `POST /sessions` (creates session + resume_token, stamps `script_version`), `POST /sessions/{id}/messages` (streams an assistant turn). **Load the active question set from the `questions` table at runtime** (respect `active` and `order_hint`); never hard-code questions in the agent. The system prompt is assembled from an **editable template file** (`shared/system_prompt.md` or similar) holding the editable pieces — vendor-agnostic philosophy, SPIN sequencing guidance, one-question-at-a-time rule, Implication-follow-up guidance — with the live slot state injected into it. Inject compact filled/unfilled slot JSON each turn. Persist every message to `messages`.
- Acceptance criteria:
  - [ ] Starting a session returns an id + resume_token and records `script_version`.
  - [ ] The question backbone is read from the DB at runtime; a reseed (Task 1.1) changes the next session's questions with no redeploy (verify by reseeding and starting a new session in a test).
  - [ ] Editable prompt guidance lives in a template file, not inline literals (assert the engine loads it from file).
  - [ ] Assistant asks one question at a time and streams to the client.
  - [ ] When a pain is mentioned, the next turn asks a SPIN Implication-style follow-up (verify with a scripted transcript test).
  - [ ] All messages persist to `messages`.
  - [ ] System prompt contains the vendor-agnostic rule (assert in test).
- Depends on: 1.1.

**Task 1.3 — Structured extraction (second call)**
- Goal: turn each user turn into typed `answers` rows.
- Build: after each user message, a separate non-streamed GPT-5.4 call with a strict Pydantic schema extracts values for any slots addressed; write to `answers` (slot_key, raw_text, structured_json, confidence, source='chat'). Update `sessions.current_slot` and coverage.
- Acceptance criteria:
  - [ ] A scripted multi-turn conversation produces correctly typed `answers` rows for the addressed slots.
  - [ ] Low-confidence extractions are flagged (confidence field populated).
  - [ ] Extraction call uses `strict: true`; a malformed-output test shows schema is enforced.
  - [ ] Coverage logic prevents "complete" until all must-fill slots are filled.
- Depends on: 1.2.

**Task 1.4 — Chat UI (`useChat`)**
- Goal: usable chat front end.
- Build: Next.js chat page using `useChat` against the BFF route that proxies to `api`; render streaming, show progress (filled vs. total must-fill slots), handle the known gotcha (persist user message immediately, finalize assistant message on stream finish).
- Acceptance criteria:
  - [ ] User can hold a full conversation in the browser with streaming.
  - [ ] A progress indicator reflects slot coverage.
  - [ ] Closing the tab mid-stream loses at most the in-flight assistant message; the user message is saved.
- Depends on: 1.3.

**Task 1.5 — Save / resume**
- Goal: leave and return to a session.
- Build: magic link `/session/{resume_token}`; on resume, reload state and have the agent open with a recap generated from filled-slot state; autosave every turn (already happening).
- Acceptance criteria:
  - [ ] Visiting the resume link restores the full conversation and slot state.
  - [ ] The resume greeting accurately names what's already covered and what's next.
  - [ ] `sessions.status` transitions in_progress → paused → in_progress correctly.
- Depends on: 1.4.

> **Milestone A:** A full guided discovery conversation runs end-to-end and writes clean typed `answers`, with save/resume. Demo this before proceeding.

---

### EPIC 2 — Analytics + synthetic data (HIGHEST RISK — do not rush)

**Implementation status (2026-06-29):** Epic 2 is closed for the current
solo/demo stage. The production cohort has 150 synthetic respondents, 150
completed sessions, and 3,750 answers. Manual recompute is live through
`POST /admin/recompute` and the `/admin/analytics` dashboard. The latest
production recompute after content-weighted pain scoring processed 150
respondents, wrote 150 embeddings/benchmarks, produced 6 clusters, and passed
the silhouette gate at 0.376. Synthetic data remains clearly tagged with
`source='synthetic'`, recompute history is append-only, and frequent Railway
cron recompute remains disabled for cost control.

**Deferred beyond Epic 2:** calibrating synthetic data from real survey data,
individual benchmark-history drill-down UI, force-directed network graph /
central-node output, and richer narrative summaries. Do not restart synthetic
quality work until real survey/reference data is selected.

**Task 2.1 — Synthetic respondent generator**
- Goal: 150–300 varied synthetic respondents that run through the same pipeline as real ones.
- Build: an archetype matrix (persona × company size × maturity level); for each, sample attributes FIRST, then prompt GPT-5.4 to role-play and answer the full backbone in realistic free text; run them through the 1.3 extraction so synthetic and real `answers` are interchangeable. Seed deliberate variation; do not let the model collapse to a stereotype.
- Acceptance criteria:
  - [ ] Generates ≥150 respondents with `source` tagged synthetic.
  - [ ] Distribution across maturity levels and archetypes is visibly varied (a summary script prints counts per archetype/level and no single bucket exceeds ~40%).
  - [ ] Each synthetic respondent has the same `answers` shape as a real session.
- Depends on: 1.3. (Can start in parallel with Epic 1 tail once 1.3 is merged.)

**Task 2.2 — Feature + embedding build**
- Goal: two representations per respondent.
- Build: a structured feature vector (scaled numerics, one-hots for tools/ERPs, maturity scores) from `answers`, plus a semantic embedding of a natural-language profile via text-embedding-3-small; store in `respondent_embeddings` (embedding + feature_vector jsonb + model).
- Acceptance criteria:
  - [ ] Every respondent (synthetic + real) gets a feature vector and an embedding.
  - [ ] A test confirms embedding dimension matches the schema (1536 or the chosen model's dim).
- Depends on: 2.1.

**Task 2.3 — Clustering pipeline**
- Goal: discover coherent personas/neighborhoods.
- Build: UMAP dimensionality reduction → HDBSCAN clustering; k-means cross-check with silhouette/elbow for forced assignment; store results in `clusters` + `cluster_runs` (algorithm, params, silhouette_score, n_clusters); compute centroids/medoids; persist UMAP 2D coords for later viz.
- Acceptance criteria:
  - [ ] Pipeline produces **≥3–5 clusters** with **silhouette > ~0.2–0.3** on the synthetic cohort. **If not met, stop and iterate on features/weighting in 2.2 before continuing — this is the gate for the whole project.**
  - [ ] HDBSCAN noise points are handled (not crashing assignment).
  - [ ] A run is fully reproducible from stored params.
- Depends on: 2.2.

**Task 2.4 — Cluster labeling + pain aggregation**
- Goal: human-readable personas.
- Build: feed each cluster's member profiles to GPT-5.4 to produce a persona label + top 3 pain points + summary; aggregate per-cluster common pain `slot_key`s, avg maturity, common tech stacks, size; write to `clusters`.
- Acceptance criteria:
  - [ ] Every cluster has a label, summary, and ranked common pain points.
  - [ ] Labels are distinct and plausibly map to finance archetypes (human spot-check).
- Depends on: 2.3.

**Task 2.5 — Network analysis**
- Goal: complementary community view + demo visual.
- Build: respondent-similarity graph (kNN edges over embeddings); Louvain / greedy modularity communities; betweenness/degree centrality to find bridge/archetype nodes; store community assignments and central nodes.
- Acceptance criteria:
  - [ ] Communities are detected and stored per respondent.
  - [ ] Most-central node per community is identified.
  - [ ] Output is serializable for a force-directed graph (nodes + edges + community id).
- Depends on: 2.2.

**Task 2.6 — Benchmarking (longitudinal)**
- Goal: place any one respondent against the cohort, and track how that placement moves as the cohort grows.
- Build: nearest-neighbor lookup (pgvector `<->`), nearest-cluster assignment, percentile rank of maturity vs. cohort and vs. cluster; write a NEW `benchmarks` row per run (never update in place — see ground rule 8). Add a query that, given a respondent, returns their benchmark history across runs (percentile and cluster over time) so "you've moved from the 40th to the 55th percentile as 30 more peers joined" is computable.
- Acceptance criteria:
  - [ ] Given a respondent id, returns current cluster, percentile(s), and nearest-neighbor ids.
  - [ ] A new (real) respondent added after a run can be benchmarked without a full recluster.
  - [ ] Running two recomputes produces two retained `benchmarks` rows for the same respondent (history is preserved, not overwritten).
  - [ ] A history query returns the respondent's percentile/cluster across all runs in time order.
- Depends on: 2.4.

**Task 2.7 — Worker scheduling + manual trigger**
- Goal: run the pipeline on demand and on a schedule.
- Build: a `worker` entrypoint that runs 2.2→2.6 end-to-end; a Railway cron service (≥5-min interval, exits cleanly); a manual trigger endpoint on `api` (`POST /admin/recompute`).
- Acceptance criteria:
  - [ ] Cron run completes and exits 0.
  - [ ] Manual trigger recomputes and updates `cluster_runs`/`benchmarks`.
- Depends on: 2.6.

> **Milestone B:** Clustering produces labeled finance personas at the silhouette gate, and any respondent can be benchmarked. This is the differentiator — demo it before adding RAG.

---

### EPIC 3 — Document ingestion / RAG

**Implementation status (2026-07-02):** Epic 3 is closed for the current
POC/demo stage. Session-scoped upload/list endpoints are live, files are written
under the configured Railway Volume, and supported PDF, DOCX, PPTX, XLSX, and
CSV uploads parse synchronously for small demo files. Parsed document text is
chunked, embedded with the existing `text-embedding-3-small` model, and
retrieved with company/session scoping before chat turns. The chat page includes
the upload control, document-grounded Q&A has been manually verified with XLSX,
and document-derived answers write `source='document'` rows without replacing
chat answers. Image/vision parsing remains deferred.

**Task 3.1 — Upload + parse**
- Goal: accept and parse prospect docs.
- Build: upload endpoint (file → Volume); Docling for PDF/PPTX/DOCX, pandas/openpyxl for XLSX/CSV (preserve tables), GPT-5.4 vision for images/schematics; store parsed text + doc_type + status in `documents`.
- Acceptance criteria:
  - [ ] Each supported type parses to text without crashing; failures set status='error' gracefully.
  - [ ] Spreadsheet parsing preserves tabular structure (not flattened to prose).
- Depends on: 0.3 (Volume).

**Task 3.2 — Chunk + embed + retrieve**
- Goal: doc context available to the conversation and reports.
- Build: chunk parsed text (~500-token windows w/ overlap), embed with text-embedding-3-small, store in `document_chunks` (HNSW index); retrieval filtered by `company_id`.
- Acceptance criteria:
  - [ ] Cosine retrieval returns relevant chunks for a test query in single-digit ms at POC scale.
  - [ ] Retrieval is scoped to the right company (no cross-company leakage — test it).
- Depends on: 3.1.

**Task 3.3 — RAG into conversation + doc-derived slot fill**
- Goal: the agent uses uploaded docs.
- Build: before each turn, embed current topic, retrieve top-k, inject as context; also run doc facts through 1.3 extraction so an uploaded budget can pre-fill slots.
- Acceptance criteria:
  - [ ] With a sample close-calendar/budget uploaded, the agent references a specific fact from it in conversation (scripted test).
  - [ ] At least one slot is auto-filled from a document with `source='document'`.
- Depends on: 3.2, 1.3.

---

### EPIC 4 — Outputs

**Implementation status (2026-07-02):** Epic 4 is closed for the current
POC/demo stage. Prospect roadmap and vendor intelligence reports are generated
on demand, stored append-only in `reports`, rendered as Markdown, and exposed
through separate prospect and admin/vendor routes. Vendor report generation and
viewing are gated by `ADMIN_RECOMPUTE_TOKEN`. Report generation uses the
configured report model, tests mock OpenAI calls, and prompts preserve the
vendor-agnostic rule.

**Task 4.1 — Prospect roadmap (vendor-agnostic)**
- Goal: the prospect deliverable.
- Build: GPT-5.4 generates from structured profile + maturity scores + retrieved doc facts: current-state, maturity assessment (6 FP&A dimensions, 1–5, vs. cohort benchmark), prioritized pains w/ impact, category-level recommendations (JTBD-framed), quick wins. Store in `reports` (type='prospect'); render markdown.
- Acceptance criteria:
  - [ ] Report includes all six sections.
  - [ ] **Vendor-agnostic test passes:** no hard-coded single-vendor "answer" in output.
  - [ ] Maturity scores shown against cohort percentile from `benchmarks`.
- Depends on: 2.6, 3.3.

**Task 4.2 — Vendor intelligence view (with market scoping)**
- Goal: the internal deliverable, framed to drive engagement, product investment, and the investor narrative.
- Build: same data, different lens: opportunity identification + rough value sizing from the prospect's own numbers, benchmark vs. cohort, persona/cluster placement, plus cohort-level intelligence (top pains, biggest/most-urgent clusters, ICP signals). Add an explicit **market-scoping block**: for each cluster, show size (count + % of cohort), average maturity, and ranked common pains, sorted to make "the largest underserved segments" obvious — so a product-investment argument ("N% of the cohort sits in cluster X with pain Y") is one read away. Add a **trend/touch-point block** noting how the cohort and this respondent's percentile have shifted across cluster runs (the recurring-report hook). Store as type='vendor'; separate route from the prospect report.
- Acceptance criteria:
  - [ ] Vendor view is reachable only on its own route, distinct from the prospect report.
  - [ ] Includes opportunity sizing tied to the respondent's stated numbers, benchmark, and cluster placement.
  - [ ] Market-scoping block ranks clusters by size and surfaces the largest/most-underserved segments with their dominant pains (the product-investment justification).
  - [ ] Trend block shows cohort growth and the respondent's percentile movement across at least two cluster runs (the iterative-release / re-benchmark touch point).
- Depends on: 4.1.

---

### EPIC 5 — Email relay (multi-contributor, simple path)

**Implementation status (2026-07-02):** Epic 5 is closed for the current
POC/demo stage as tokenized relay links. The chat page can create a single-use
relay token for a selected question, the relay page submits an answer back to
the originating session with `source='email'`, and demo-link mode works without
an outbound email provider. True outbound email delivery remains a refinement.
The current question dropdown loads all questions immediately; narrowing it is
also deferred.

**Task 5.1 — Tokenized question links**
- Goal: let a colleague answer one slot.
- Build: `email_relays` row + unique token; outbound email (Resend/Postmark/SendGrid) with a link to a minimal `/relay/{token}` page; the colleague's answer posts back through the same `save_answer` pipeline with `source='email'`.
- Acceptance criteria:
  - [ ] Sending a relay creates a row and emails a working link.
  - [ ] Submitting the relay page writes an `answers` row for the right slot/session with `source='email'`.
  - [ ] Token is single-use / expires.
- Depends on: 1.3.

---

### EPIC 6 — Dashboard + demo polish

**Implementation status (2026-07-02):** Epic 6 is closed for the current
POC/demo stage. The token-gated `/admin/demo` cockpit summarizes session demo
readiness and links into chat, upload, relay, reports, recompute, and analytics.
The `/admin/analytics` dashboard supports selected session/respondent context,
highlights the selected real respondent on UMAP, shows benchmark history and
nearest neighbors, and renders a simple community/network view from live DB
rows. `docs/demo.md` documents the seven-step production demo. A follow-up fix
created default real respondent/company rows for new public sessions and
backfills answered legacy sessions during recompute so real sessions can appear
in the analytics selector.

**Task 6.1 — Analytics dashboard**
- Goal: the visual payoff.
- Build: UMAP scatter colored by cluster; persona cards (label, common pains, size); network/community graph; benchmark view showing where a selected respondent lands vs. cohort.
- Acceptance criteria:
  - [ ] Scatter, persona cards, network graph, and benchmark view all render from live DB data.
  - [ ] Selecting the real demo respondent highlights its cluster and percentile.
- Depends on: 2.7, 4.2.

**Task 6.2 — One real end-to-end run + demo script**
- Goal: prove the whole loop.
- Build: conduct one real discovery session, land it alongside the synthetic cohort, generate both reports, recompute analytics, and verify the 7-step demo flow (Appendix C). Add basic error handling and a README.
- Acceptance criteria:
  - [ ] The 7-step demo in Appendix C runs without manual DB edits.
  - [ ] README documents setup, env vars, and how to run the demo.
- Depends on: all prior.

> **Milestone C (POC complete):** the 7-step demo runs live end-to-end.

---

## Appendix A — Full schema (create in Task 0.2)

This is the authoritative schema. Later tasks assume these exact table and column names — do not rename without updating every dependent task. Use `uuid` primary keys (default `gen_random_uuid()`), `timestamptz` for times. `vector(1536)` assumes text-embedding-3-small; if a different embedding model is chosen, set the dimension consistently everywhere and update this appendix.

```sql
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
```

Add the `respondents.cluster_id → clusters.id` foreign key in a follow-up migration after `clusters` exists, to avoid a circular dependency at create time.

## Appendix B — Full starter question bank (seed in Task 1.1)

Seed each row with the `slot_key`, `category`, `framework_tag`, and `tier` shown. `slot_key`s are the stable contract the extraction step (1.3) and analytics (2.2) depend on — keep them exactly as written. **must_fill** = required before a session can complete; **nice_to_have** = asked if the conversation allows. The agent improvises the wording and follow-ups; these are the canonical intents, not verbatim scripts.

**A. Company & role context**
- `ctx.role` (A, SPIN-Situation, must_fill) — Your role and which finance/accounting functions you own.
- `ctx.company_profile` (A, SPIN-Situation, must_fill) — Company size, entities, geographies, public/private.
- `ctx.team_structure` (A, SPIN-Situation, nice_to_have) — Size and structure of the finance/FP&A team.

**B. Core accounting processes**
- `close.days` (B, SPIN-Situation, must_fill) — Days to complete month-end close, and the most painful part.
- `recon.manual_vs_auto` (B, SPIN-Problem, must_fill) — Which accounts (bank, intercompany, balance sheet) are reconciled manually vs. automated.
- `apar.volume` (B, SPIN-Situation, nice_to_have) — Monthly invoice/payment volume and how much matching is manual.
- `consolidation.method` (B, SPIN-Situation, must_fill) — Number of entities/ERPs consolidated and how (Excel, EPM tool).
- `reporting.process` (B, SPIN-Problem, nice_to_have) — How management/board reports are built and how long it takes.
- `fpa.cadence` (B, SPIN-Situation, must_fill) — Budgeting/forecasting cadence; driver-based or spreadsheet; scenario planning.
- `tax.process` (B, SPIN-Problem, nice_to_have) — How sales/use tax, VAT/GST, and transfer pricing are prepared and reconciled.

**C. Systems & tech stack**
- `sys.erp` (C, SPIN-Situation, must_fill) — ERP(s): NetSuite, SAP, Oracle, Dynamics, QuickBooks, Sage, etc.
- `sys.dataprep_tools` (C, SPIN-Situation, must_fill) — Data-prep/automation tools: Excel, Power Query, Alteryx, Tableau Prep, Power BI, SQL, Python.
- `sys.data_location` (C, SPIN-Situation, nice_to_have) — Where data lives: SharePoint/Excel, warehouse, lake, CRM (Salesforce).
- `sys.epm_close_tools` (C, SPIN-Situation, nice_to_have) — RPA, EPM (Anaplan, Pigment, Workday Adaptive), close tools (BlackLine, FloQast).

**D. Technical skill levels**
- `skill.builders` (D, MEDDIC-DecisionProcess, must_fill) — Who builds workflows today: business analysts vs. data engineers/IT.
- `skill.sql_python` (D, SPIN-Situation, nice_to_have) — Team comfort with SQL/Python; self-service vs. IT-dependent.
- `skill.onboarding_time` (D, SPIN-Implication, nice_to_have) — Time to onboard a new analyst to current tooling.

**E. Pain points**
- `pain.error_cost` (E, SPIN-Implication, must_fill) — Where errors occur most and the cost/risk when they do.
- `pain.manual_hours` (E, SPIN-Implication, must_fill) — Hours/month on manual data prep vs. analysis.
- `pain.bus_factor` (E, SPIN-Implication, nice_to_have) — What breaks when a key person is out; bus-factor risk.
- `pain.audit_burden` (E, SPIN-Problem, nice_to_have) — How audit/SOX evidence is captured today.

**F. Goals & decision context**
- `goal.future_state` (F, SPIN-NeedPayoff, must_fill) — What "great" looks like in 12 months and the metric that proves it.
- `goal.trigger` (F, MEDDIC-Metrics, must_fill) — What's triggering this evaluation now (critical event).
- `goal.decision_process` (F, MEDDIC-EconomicBuyer, must_fill) — Who decides, who funds, how tools are evaluated/bought.
- `goal.blockers` (F, MEDDIC-IdentifyPain, nice_to_have) — What has blocked solving this already.

That's 13 must_fill slots across all six categories (satisfies Task 1.1's acceptance criterion) and 11 nice_to_have. Tune the must/nice split if a real session feels too long — Gong's call data suggests ~11–16 high-value questions is the sweet spot.

## Appendix C — 7-step demo (target for Task 6.2)
1. Fresh session as a Focus Controller; show fluid-but-guided convo + an Implication follow-up. 2. Upload a budget/close-calendar; agent references it. 3. Pause + resume via magic link. 4. Email a question to a colleague (tokenized link), feed answer back. 5. Complete session; generate prospect roadmap + vendor view. 6. Open dashboard: clusters, network graph, named personas, where this respondent lands. 7. Close on the narrative: repeatable AI-assisted discovery playbook + segment intelligence, vendor-agnostic.

## Appendix D — Definition of "blocked / flag the human"
Stop and ask if: the silhouette gate in 2.3 can't be met after feature iteration; a task appears to require auth, real-time collab, or inbound email parsing; an OpenAI model ID in the locked decisions is unavailable; or any global ground rule would have to be broken to proceed.

## Appendix E — Kickoff prompt for Claude Code (plan mode)

Drop this file into the repo root as `BUILD_PLAN.md`, open the project in VS Code with Claude Code, enter **plan mode**, and paste the prompt below. It scopes the first planning pass to the spine (through Milestone A) so the plan stays reviewable rather than a 25-task wall.

```
Read BUILD_PLAN.md in full — it is the single source of truth for this project.
Do not summarize it back to me; confirm you've absorbed the 10 global ground
rules and the locked tech decisions, then plan.

We are building in VS Code with you (Claude Code), solo for now.
Work the backlog strictly in order, one task = one branch = one PR, stopping at
each task's acceptance criteria for my review. Do not start a task whose
dependencies aren't merged.

For THIS plan-mode pass, plan only Epic 0 (Scaffold & CI/CD) and Epic 1
(Discovery spine), i.e. through Milestone A. Do not plan Epics 2–6 yet.

Hold these especially tight while planning:
- Ground rule 2 (two-call pattern: separate streamed chat call + non-streamed
  strict-structured-output extraction call — never one call doing both).
- Ground rule 3 (authoritative state in Postgres, not the prompt or browser).
- Ground rules 9 and 10 (the script is editable config, not code; the question
  bank is one versioned YAML file synced by an upsert reseed; slot_keys are
  immutable — retire, never rename). The engine must read questions from the DB
  at runtime so edits take effect with no redeploy. Editable system-prompt
  pieces live in a template file, not inline string literals.
- Ground rule 8 (analytics history is append-only) — keep the schema honest now
  even though clustering comes later.

Output a plan as: ordered tasks (0.1 → 1.5, plus 1.1b), and for each, the files
you'll create/change, the migration (if any), the tests that prove the
acceptance criteria, and the env vars introduced. Flag anything ambiguous or any
locked decision you think needs verifying (e.g. current OpenAI model IDs) before
I approve. Then wait for my go-ahead before writing code.
```

When Milestone A is merged and demoed, start a fresh plan-mode pass for **Epic 2 (analytics + synthetic data)** on its own — it's the highest-risk epic and deserves its own focused planning session, with the Task 2.3 silhouette gate treated as the go/no-go for the whole project.
