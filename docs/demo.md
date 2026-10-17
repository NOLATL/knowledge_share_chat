# Playbook Demo Runbook

This runbook covers the live POC demo path. Use production URLs, but do not put
the admin token in screenshots, recordings, or shared notes.

## URLs

- Web: `https://web-production-ac737.up.railway.app`
- API: `https://api-production-44c7.up.railway.app`
- Demo cockpit: `/admin/demo`
- Analytics dashboard: `/admin/analytics`

## Required Environment

- `ADMIN_RECOMPUTE_TOKEN` gates demo cockpit, analytics, recompute, and vendor reports.
- `OPENAI_API_KEY` is required for chat, extraction, embeddings, and report generation.
- `UPLOAD_VOLUME_PATH` must point at the Railway Volume for uploaded documents.
- `PUBLIC_WEB_BASE_URL` or `RELAY_BASE_URL` should point at the web app for relay links.
- `RESEND_API_KEY` and `EMAIL_FROM` are optional for true outbound email; without them the relay stays in demo-link mode.

## Seven-Step Demo

1. Open or resume a discovery chat.
   - Start at `/` for a new session or use `/session/{resume_token}`.
   - Expected signal: the page shows a resume link and slot coverage.

2. Upload a supported document.
   - Use PDF, DOCX, PPTX, XLSX, or CSV from the chat page.
   - Expected signal: the upload list shows the document as parsed.

3. Ask a document-grounded question.
   - Ask about a fact visible in the uploaded file.
   - Expected signal: the assistant can answer using the uploaded context while still continuing discovery.

4. Use a colleague relay link.
   - Pick a question in the chat page relay control, enter an email, and send.
   - In demo-link mode, open the returned relay link manually and submit an answer.
   - Expected signal: the relay submission is accepted and later appears as session coverage.

5. Generate the prospect roadmap.
   - Open `/reports/prospect?sessionId={session_id}`.
   - Generate or load the latest roadmap.
   - Expected signal: the report includes current state, maturity, benchmark, pains, recommendations, and quick wins.

6. Generate the vendor intelligence view.
   - Open `/admin/reports/vendor?sessionId={session_id}&token={admin_token}`.
   - Generate or load the latest vendor report.
   - Expected signal: the report includes opportunity sizing, cluster placement, market scoping, and trend/touch-point context.

7. Recompute analytics and view placement.
   - Open `/admin/analytics?token={admin_token}&sessionId={session_id}`.
   - Run manual recompute if the respondent has no benchmark yet.
   - Expected signal: the selected real respondent is highlighted on the UMAP map, benchmark card, persona card, and community graph.

## Demo Cockpit

Open `/admin/demo`, enter the admin token and session id, then use the step cards
to move through the demo. The cockpit is a status/readiness surface only; it
links to the existing chat, reports, recompute, and analytics pages for actions.

## Troubleshooting

- Missing prospect report: open the prospect roadmap page and generate it after the chat has enough answers.
- Missing vendor report: confirm the admin token, then generate from the vendor report page.
- Missing benchmark: run manual recompute from analytics after the real session has extracted answers.
- Document parse error: retry with XLSX/CSV for the demo, or check that the file extension is supported and under the upload limit.
- Relay does not email: this is expected in demo-link mode unless `RESEND_API_KEY` and `EMAIL_FROM` are configured.
- Analytics token rejected: confirm the token is the current `ADMIN_RECOMPUTE_TOKEN`; do not paste it into shared docs.
