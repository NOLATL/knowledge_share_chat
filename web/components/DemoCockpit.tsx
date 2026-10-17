"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type DemoStatus = {
  session: {
    id: string;
    status: string;
    resume_token: string;
    current_slot: string | null;
    respondent_id: string | null;
    respondent_name: string | null;
    role: string | null;
    email: string | null;
    source: string | null;
    company_name: string | null;
    company_id: string | null;
  };
  coverage: {
    filled_must_fill: number;
    total_must_fill: number;
    complete_ready: boolean;
  };
  documents: { total: number; parsed: number; pending: number; error: number };
  relays: { total: number; sent: number; answered: number; expired: number };
  reports: {
    prospect: { id: string; created_at: string } | null;
    vendor: { id: string; created_at: string } | null;
  };
  analytics: {
    latest_run: { id: string; n_clusters: number; silhouette_score: number; created_at: string } | null;
    benchmark: {
      id: string;
      cluster_label: string | null;
      maturity_score: number | null;
      percentile_cohort: number | null;
      percentile_cluster: number | null;
      computed_at: string;
    } | null;
  };
};

type LoadState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: DemoStatus }
  | { status: "error"; message: string };

export default function DemoCockpit({
  initialToken = "",
  initialSessionId = "",
}: {
  initialToken?: string;
  initialSessionId?: string;
}) {
  const [token, setToken] = useState(initialToken);
  const [sessionId, setSessionId] = useState(initialSessionId);
  const [state, setState] = useState<LoadState>(initialToken && initialSessionId ? { status: "loading" } : { status: "idle" });

  const query = useMemo(() => {
    const params = new URLSearchParams();
    params.set("token", token.trim());
    params.set("sessionId", sessionId.trim());
    return params.toString();
  }, [sessionId, token]);
  const canLoad = Boolean(token.trim() && sessionId.trim());

  const loadStatus = useCallback(() => {
    if (!canLoad) {
      setState({ status: "idle" });
      return;
    }
    setState({ status: "loading" });
    fetch(`/api/admin/demo?${query}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(await errorText(response));
        }
        setState({ status: "ready", data: (await response.json()) as DemoStatus });
      })
      .catch((error: Error) => setState({ status: "error", message: error.message }));
  }, [canLoad, query]);

  useEffect(() => {
    if (initialToken && initialSessionId) loadStatus();
  }, [initialToken, initialSessionId, loadStatus]);

  const active = state.status === "ready" ? state.data : null;
  const resumeUrl = active ? `/session/${active.session.resume_token}` : "#";
  const externalUrl = active?.session.company_id ? `/external/${active.session.company_id}` : "#";
  const internalUrl = `/internal?token=${encodeURIComponent(token.trim())}`;

  return (
    <main className="shell">
      <header className="header">
        <div>
          <p className="eyebrow">Admin demo</p>
          <h1>Live POC demo cockpit</h1>
          <p className="lede">Track the session, documents, relay, reports, recompute, and analytics from one place.</p>
        </div>
        <a className="secondaryLink" href="/internal">
          Internal dashboard
        </a>
      </header>

      <section className="controlPanel">
        <label>
          Session id
          <input value={sessionId} onChange={(event) => setSessionId(event.target.value)} placeholder="Session UUID" />
        </label>
        <label>
          Admin token
          <input value={token} onChange={(event) => setToken(event.target.value)} placeholder="Admin token" type="password" />
        </label>
        <button type="button" disabled={!canLoad || state.status === "loading"} onClick={loadStatus}>
          {state.status === "loading" ? "Loading..." : "Load demo"}
        </button>
      </section>

      {state.status === "idle" && <section className="panel muted">Enter a session id and admin token to load demo readiness.</section>}
      {state.status === "error" && (
        <section className="panel error">
          <h2>Demo status unavailable</h2>
          <p>{state.message}</p>
        </section>
      )}
      {state.status === "ready" && (
        <>
          <section className="summary">
            <Metric label="Coverage" value={`${active!.coverage.filled_must_fill}/${active!.coverage.total_must_fill}`} detail="must-fill slots" />
            <Metric label="Documents" value={`${active!.documents.parsed}/${active!.documents.total}`} detail="parsed uploads" />
            <Metric label="Reports" value={`${Number(Boolean(active!.reports.prospect)) + Number(Boolean(active!.reports.vendor))}/2`} detail="generated outputs" />
            <Metric label="Benchmark" value={active!.analytics.benchmark ? formatPercent(active!.analytics.benchmark.percentile_cohort) : "n/a"} detail="cohort percentile" />
          </section>

          <section className="identity panel">
            <div>
              <h2>{active!.session.company_name ?? "Selected session"}</h2>
              <p>
                {active!.session.role ?? "Finance respondent"} · {active!.session.status}
                {active!.session.current_slot ? ` · current slot ${active!.session.current_slot}` : ""}
              </p>
            </div>
            <button type="button" onClick={loadStatus}>Refresh status</button>
          </section>

          <section className="steps" aria-label="Demo steps">
            <StepCard
              number="1"
              title="Start or resume discovery"
              status={active!.coverage.filled_must_fill > 0 ? "In progress" : "Ready"}
              detail="Resume the active chat and continue one-question-at-a-time discovery."
              href={resumeUrl}
            />
            <StepCard
              number="2"
              title="Upload a document"
              status={active!.documents.parsed ? "Parsed" : active!.documents.total ? "Needs review" : "Ready"}
              detail="Use the chat page upload control for PDF, DOCX, PPTX, XLSX, or CSV."
              href={resumeUrl}
            />
            <StepCard
              number="3"
              title="Ask a document-grounded question"
              status={active!.documents.parsed ? "Ready" : "Needs parsed doc"}
              detail="Ask about a fact from the uploaded file to show RAG context in the chat."
              href={resumeUrl}
            />
            <StepCard
              number="4"
              title="Use colleague relay"
              status={active!.relays.answered ? "Answered" : active!.relays.total ? "Sent" : "Ready"}
              detail="Create a single-use relay link from the chat page and submit a colleague answer."
              href={resumeUrl}
            />
            <StepCard
              number="5"
              title="Open the external deliverable"
              status={active!.session.company_id ? "Ready" : "No company"}
              detail="Executive rollup + function roadmaps and downloads for this company."
              href={externalUrl}
            />
            <StepCard
              number="6"
              title="Open the internal dashboard"
              status={active!.analytics.latest_run ? "Analytics ready" : "Needs recompute"}
              detail="Cohort personas, account intel, product fit, and the macro write-up."
              href={internalUrl}
            />
          </section>
        </>
      )}

      <Styles />
    </main>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <article className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function StepCard({
  number,
  title,
  status,
  detail,
  href,
}: {
  number: string;
  title: string;
  status: string;
  detail: string;
  href: string;
}) {
  return (
    <article className="stepCard">
      <div className="stepTop">
        <span>{number}</span>
        <strong>{status}</strong>
      </div>
      <h2>{title}</h2>
      <p>{detail}</p>
      <a href={href}>Open</a>
    </article>
  );
}

function formatPercent(value: number | null) {
  return typeof value === "number" ? `${Math.round(value)}%` : "n/a";
}

async function errorText(response: Response) {
  const body = await response.json().catch(() => null);
  if (body && typeof body.detail === "string") return body.detail;
  return `Request failed with HTTP ${response.status}.`;
}

function Styles() {
  return (
    <style>{`
      body {
        margin: 0;
        background: var(--paper);
        color: var(--ink);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      .shell {
        width: min(1120px, calc(100vw - 32px));
        margin: 0 auto;
        padding: 32px 0 52px;
      }
      .header {
        display: flex;
        justify-content: space-between;
        gap: 22px;
        align-items: flex-start;
        margin-bottom: 20px;
      }
      .eyebrow {
        margin: 0 0 8px;
        color: var(--accent);
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0;
        text-transform: uppercase;
      }
      h1, h2, p {
        margin-top: 0;
      }
      h1 {
        margin-bottom: 10px;
        font-size: 36px;
        line-height: 1.05;
      }
      h2 {
        margin-bottom: 8px;
        font-size: 18px;
      }
      .lede {
        max-width: 650px;
        color: #666;
        line-height: 1.5;
      }
      .secondaryLink, .stepCard a {
        color: var(--accent);
        font-weight: 800;
      }
      .controlPanel, .panel, .metric, .stepCard {
        background: #fff;
        border: 1px solid var(--hairline);
        border-radius: 8px;
        box-shadow: 0 10px 30px rgba(23, 32, 38, 0.06);
      }
      .controlPanel {
        display: grid;
        grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr) auto;
        gap: 12px;
        align-items: end;
        margin-bottom: 16px;
        padding: 18px;
      }
      label {
        display: grid;
        gap: 6px;
        color: #4b5563;
        font-size: 13px;
        font-weight: 800;
      }
      input, button {
        height: 42px;
        border-radius: 6px;
        font: inherit;
      }
      input {
        min-width: 0;
        border: 1px solid var(--ink);
        padding: 0 12px;
      }
      button {
        border: 0;
        padding: 0 14px;
        background: var(--ink);
        color: #fff;
        font-weight: 800;
        cursor: pointer;
      }
      button:disabled {
        cursor: not-allowed;
        opacity: 0.55;
      }
      .panel {
        padding: 20px;
      }
      .muted {
        color: #666;
      }
      .error {
        color: var(--accent);
      }
      .summary {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin-bottom: 16px;
      }
      .metric {
        padding: 18px;
      }
      .metric span, .metric small {
        display: block;
        color: #666;
      }
      .metric strong {
        display: block;
        margin: 6px 0;
        font-size: 28px;
        line-height: 1;
      }
      .identity {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: center;
        margin-bottom: 16px;
      }
      .identity p {
        margin-bottom: 0;
        color: #666;
      }
      .steps {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
      }
      .stepCard {
        padding: 18px;
      }
      .stepTop {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
        margin-bottom: 12px;
      }
      .stepTop span {
        display: grid;
        width: 30px;
        height: 30px;
        place-items: center;
        border-radius: 999px;
        background: var(--ink);
        color: #fff;
        font-weight: 900;
      }
      .stepTop strong {
        color: var(--accent);
        font-size: 13px;
      }
      .stepCard p {
        min-height: 66px;
        color: #4b5563;
        line-height: 1.45;
      }
      @media (max-width: 900px) {
        .header, .identity {
          display: block;
        }
        .controlPanel, .summary, .steps {
          grid-template-columns: 1fr;
        }
        .identity button {
          margin-top: 12px;
        }
      }
      @media (max-width: 620px) {
        .shell {
          width: min(100vw - 20px, 1120px);
          padding-top: 18px;
        }
        h1 {
          font-size: 29px;
        }
      }
    `}</style>
  );
}
