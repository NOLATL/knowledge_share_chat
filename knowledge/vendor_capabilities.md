# Corbel Analytics — Platform Capabilities (Internal Presales Reference)

> **Demo vendor.** Corbel Analytics is a fictional company created for this
> portfolio project. This document describes an illustrative product so the
> internal reports have a concrete capability set to map prospect pain against.
> Nothing here describes a real vendor.

## Positioning

Corbel is a cloud-hosted, no-code analytics-automation platform for corporate
finance and accounting teams. It sits between source systems (ERP, banks,
billing, CRM, spreadsheets, documents) and the people who close the books,
replacing hand-built spreadsheet pipelines with governed, repeatable workflows
that finance owns without needing engineering.

Primary buyer: Controller / VP Finance. Primary user: senior accountants and
finance analysts who live in Excel and Power Query today.

## Current Product

### Data connectivity
- Native read/write connectors for common mid-market and enterprise ERPs,
  billing and payments platforms, CRMs, cloud warehouses, SharePoint/Drive and
  SFTP drops.
- Scheduled and event-triggered pulls (time-based, file-arrival, webhook).
- Bank statement ingestion via SFTP and bank APIs (BAI2, CAMT.053, CSV).

### No-code data preparation
- Visual, step-by-step workflow builder: join, append, de-duplicate,
  anti-join ("find what's missing"), pivot/unpivot, fill-down, window functions.
- Chart-of-accounts mapping across entities, with suggested mappings for review.
- Every workflow is self-documenting: each step is visible and replayable,
  which replaces "the macro only Dana understands."

### Document extraction
- AI-assisted extraction of tables and fields from PDFs, scans and emailed
  attachments (invoices, statements, remittances, trial-balance packs).
- Low-confidence fields are routed to a human review queue before they
  reach a workflow.

### Reconciliation and matching
- Rules-plus-fuzzy matching engine for bank-to-GL, subledger-to-GL,
  intercompany, and processor/payout-to-ledger reconciliations.
- Cash application assist: matches remittances and un-itemized receipts to
  open AR, surfaces exceptions in a worklist.
- Variance and threshold flags with exception routing to owners.

### Close workflow support
- Accrual support workflows (e.g. goods-received-not-invoiced, prepaid
  amortization schedules) that prepare proposed journal entries.
- Proposed entries go through configurable approval and can be posted back to
  the ERP via connector.
- Consolidation prep: pulls entity trial balances, normalizes to a corporate
  chart of accounts, flags intercompany mismatches.

### Reporting and distribution
- Formatted Excel/PDF outputs and refreshed datasets for BI tools.
- Scheduled delivery to email, Slack and Teams.

### Governance and controls
- Separate development and production workspaces; promotion to production
  requires an approver (supports segregation of duties).
- Version history for every workflow, with side-by-side comparison and restore.
- Activity log of runs, edits, logins and connection changes, exportable as
  audit evidence.
- Role-based access, SSO/MFA, encryption in transit and at rest, and a managed
  secrets store for credentials.

### AI assist
- Natural-language help for building workflow steps and categorizing messy
  text fields (vendor names, memo lines, GL descriptions).
- Customers can bring their own LLM provider to keep data in their cloud.

## Known Gaps (roadmap candidates)

These are adjacent problems prospects raise that Corbel does **not** solve
today, but that fit the platform's direction:
- **Close management / task checklists.** No close calendar, task assignment
  or sign-off tracker; teams still run the close checklist elsewhere.
- **Flux / variance commentary.** Detects variances but does not draft the
  narrative explanations reviewers want.
- **Sales and indirect tax.** Can reconcile tax collected vs. payable from
  source data, but has no rates engine or filing capability.
- **Lease accounting schedules.** Can prepare data, but no ASC 842 / IFRS 16
  calculation engine.
- **Semantic metrics layer.** No governed, shared KPI definitions; metric
  logic lives inside individual workflows.

## Out of Scope (third-party territory)

Corbel deliberately does not compete in these categories; recommend a
category of tool instead:
- **ERP / general ledger** (system of record).
- **FP&A planning, budgeting and forecasting** (driver-based models, scenarios).
- **Payroll processing and HRIS.**
- **Treasury execution** (payments, cash pooling, FX hedging, bank portals).
- **AP invoice capture-to-pay suites** with supplier portals and payments.
- **Revenue recognition sub-ledgers** (ASC 606 allocation engines).
- **Billing / subscription management.**

## Typical Fit Signals
- Recurring reconciliations built in Excel/Power Query that take days each month.
- Multiple ERPs or entities with manual chart-of-accounts mapping.
- Data pulled from PDFs or portals and re-keyed.
- Auditors asking for evidence of who changed a spreadsheet and when.
- A small analytics/IT team that can't take on finance's backlog.
