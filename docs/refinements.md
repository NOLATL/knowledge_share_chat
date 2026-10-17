# Refinements

These items are intentionally deferred until the core build is complete.

- Narrow the "Ask a colleague" dropdown so it does not load every question immediately. Prefer context-aware defaults such as current slot, unfilled must-fill slots, or a compact searchable picker.
- Set up true outbound email relay delivery instead of demo-link mode, including sender/domain configuration and production email provider settings.
- ~~Add a company-level analytics layer.~~ DONE (Epic 8, 2026-07-02): company rollup with peer benchmarking (`company_benchmarks`), external per-company deliverable + HTML download, internal intelligence view, movement across runs, and generated `account_code` identifiers (C-00001…) trackable over time and across respondents.
- ~~Improve company identity capture in public sessions~~ DONE (Task 8.1): pre-chat intake form captures name/industry/firmographics; empty backfill shells are hidden from the company directory. Remaining: merge legacy "Demo discovery company" shells into real companies once their identity is known.
- Calibrate the synthetic cohort's **answer content** with real survey/reference data before further quality tuning. (Structural enrichment — varied industries, firmographics, multi-respondent companies — was done 2026-07-02 for company analytics; what remains deferred is calibrating answer distributions/wording against a real reference dataset.)
- Add richer respondent benchmark drill-downs, including nearest-neighbor excerpts and more readable benchmark history.
- Upgrade the analytics network graph only if the simple SVG/community view becomes insufficient for demos.
