"use client";

// External destination: one self-contained company view in the brutalist
// system — hero + segmented scope toggle + stat grid + persona/cohort bars +
// roadmap grid (from the generated report), with the cohort map, pressure
// ranking, answers, and full report text kept below (restyled).

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import Chrome from "./Chrome";
import CohortMap, { type MapPoint } from "./CohortMap";
import ReportMarkdown from "./ReportMarkdown";
import { downloadSnapshot } from "../lib/snapshot";
import { painLabel } from "../lib/painLabel";

type PainPoint = { slot_key: string; count?: number; score?: number; avg_score?: number };

type FunctionBenchmark = {
  respondent_count: number;
  avg_maturity: number | null;
  percentile_cohort: number | null;
  percentile_peer: number | null;
  peer_group: { function_key?: string; n?: number; fell_back?: boolean } | null;
  common_pain_points: PainPoint[] | null;
  common_tech_stack: string[] | null;
  computed_at: string | null;
  persona_label: string | null;
  persona_summary: string | null;
  buying_persona: string | null;
};

type CompanyBenchmark = {
  respondent_count: number;
  avg_maturity: number | null;
  percentile_cohort: number | null;
  percentile_peer: number | null;
  peer_group: { industry?: string; size_band?: string; n?: number; fell_back?: boolean } | null;
  common_pain_points: PainPoint[] | null;
  common_tech_stack: string[] | null;
  company_persona_label: string | null;
  company_persona_summary: string | null;
  company_buying_persona: string | null;
};

type Answer = {
  slot_key: string;
  category: string | null;
  question: string | null;
  raw_text: string | null;
  structured_json: { value?: unknown } | null;
  source: string;
  respondent_name: string | null;
  respondent_role: string | null;
};

type FunctionBreakdown = {
  function_key: string;
  respondents: { id: string; name: string | null; role: string | null }[];
  answers: Answer[];
  benchmark: FunctionBenchmark | null;
};

type Overview = {
  company: {
    id: string;
    account_code: string | null;
    name: string;
    industry: string | null;
    headcount_band: string | null;
    revenue_band: string | null;
  };
  functions: FunctionBreakdown[];
  company_benchmark: CompanyBenchmark | null;
  map_points: { company: MapPoint[]; function: (MapPoint & { function_key: string | null })[] };
};

type RoadmapPhase = { phase: string; items: { title: string; desc: string }[] };

type Report = {
  id: string;
  rendered_md: string;
  created_at: string;
  content_json?: { roadmap?: RoadmapPhase[] };
};

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; overview: Overview };

export default function ExternalCompanyView({ companyId }: { companyId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [scope, setScope] = useState<string>("company"); // 'company' | function_key

  useEffect(() => {
    fetch(`/api/companies/${companyId}/overview`)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `HTTP ${r.status}`);
        setState({ status: "ready", overview: (await r.json()) as Overview });
      })
      .catch((e: Error) => setState({ status: "error", message: e.message }));
  }, [companyId]);

  const companyName = state.status === "ready" ? state.overview.company.name : "Company";

  return (
    <Chrome
      active="External"
      breadcrumb={
        <>
          <Link href="/external" style={{ color: "#555", textDecoration: "none" }}>External</Link> / {companyName}
        </>
      }
      context="External Deliverable"
      footerLeft={<Link href="/external" style={{ color: "#666", textDecoration: "none" }}>← All deliverables</Link>}
      footerRight={
        state.status === "ready" && state.overview.company_benchmark
          ? `Benchmarked Against Peers — ${state.overview.company_benchmark.respondent_count} Voice${state.overview.company_benchmark.respondent_count === 1 ? "" : "s"} Assessed`
          : "Benchmarked Against Peers"
      }
    >
      {state.status === "loading" && <p style={monoNote}>Loading company overview…</p>}
      {state.status === "error" && (
        <p style={{ ...monoNote, color: "var(--accent)" }}>Could not load this company: {state.message}</p>
      )}
      {state.status === "ready" && (
        <Body overview={state.overview} companyId={companyId} scope={scope} setScope={setScope} />
      )}
    </Chrome>
  );
}

function Body({
  overview,
  companyId,
  scope,
  setScope,
}: {
  overview: Overview;
  companyId: string;
  scope: string;
  setScope: (s: string) => void;
}) {
  const active = overview.functions.find((fn) => fn.function_key === scope);
  const isCompany = scope === "company" || !active;
  // One report per scope; GET and POST share the URL.
  const reportUrl = isCompany
    ? `/api/companies/${companyId}/report`
    : `/api/companies/${companyId}/report/function?function=${encodeURIComponent((active as FunctionBreakdown).function_key)}`;
  const reportState = useReport(reportUrl);
  const scopeName = isCompany ? "company" : (active as FunctionBreakdown).function_key;
  const downloadName = `${slugify(`${overview.company.name}-${scopeName}`)}-deliverable.html`;

  return (
    <>
      <section style={{ padding: "60px 0 36px", borderBottom: "2px solid var(--ink)" }}>
        <div className="kicker-solo" style={{ marginBottom: 22 }}>External Deliverable</div>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 28 }}>
          <div>
            <h1
              style={{
                margin: 0,
                fontWeight: 900,
                fontSize: "clamp(46px, 7vw, 108px)",
                lineHeight: 0.9,
                letterSpacing: "-0.035em",
                textTransform: "uppercase",
              }}
            >
              {overview.company.name}
            </h1>
            <div
              style={{
                marginTop: 22,
                fontFamily: "var(--font-mono)",
                fontSize: 13,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: "#666",
              }}
            >
              {[overview.company.account_code, overview.company.industry, overview.company.headcount_band]
                .filter(Boolean)
                .join("  ·  ")}
            </div>
          </div>
          <div data-snapshot-exclude="" style={{ display: "flex", flexWrap: "wrap", gap: 16, flexShrink: 0 }}>
            <button onClick={reportState.generate} disabled={reportState.generating} className="hard-btn">
              {reportState.generating ? "Generating…" : reportState.report ? "Regenerate" : "Generate"}
            </button>
            <button onClick={() => downloadSnapshot(downloadName)} className="hard-btn hard-btn--ink">
              ↓ Download deliverable
            </button>
          </div>
        </div>
      </section>

      <nav className="seg" aria-label="Scope" data-snapshot-exclude="">
        <button aria-pressed={isCompany} onClick={() => setScope("company")}>
          Company (executive)
        </button>
        {overview.functions.map((fn) => (
          <button
            key={fn.function_key}
            aria-pressed={scope === fn.function_key}
            onClick={() => setScope(fn.function_key)}
          >
            {fn.function_key}
          </button>
        ))}
        <div className="seg-spacer" />
      </nav>

      {isCompany ? (
        <CompanyPanel overview={overview} reportState={reportState} onOpenFunction={setScope} />
      ) : (
        <FunctionPanel
          breakdown={active as FunctionBreakdown}
          mapPoints={(overview.map_points?.function ?? []).filter(
            (p) => p.function_key === (active as FunctionBreakdown).function_key,
          )}
          companyName={overview.company.name}
          reportState={reportState}
        />
      )}
    </>
  );
}

function CompanyPanel({
  overview,
  reportState,
  onOpenFunction,
}: {
  overview: Overview;
  reportState: ReportState;
  onOpenFunction: (key: string) => void;
}) {
  const benchmark = overview.company_benchmark;
  return (
    <>
      {benchmark ? (
        <>
          <StatGrid
            stats={[
              { label: "Maturity", value: fmt(benchmark.avg_maturity), unit: "/5", note: "Composite across all functions" },
              {
                label: "Cohort standing",
                value: pctNum(benchmark.percentile_peer),
                unit: "%",
                note: benchmark.peer_group?.fell_back
                  ? "Of all companies — too few similar companies"
                  : "Of similar companies (industry + size) at or below you",
              },
              { label: "Voices", value: String(benchmark.respondent_count), unit: "", note: "Respondents assessed" },
            ]}
          />
          <PersonaRow
            personaLabel={benchmark.company_persona_label}
            personaSummary={benchmark.company_persona_summary}
            buyingPersona={benchmark.company_buying_persona}
            bars={[
              {
                label: "Cohort standing (industry + size)",
                value: pct(benchmark.percentile_peer),
                width: benchmark.percentile_peer ?? 0,
                note: [overview.company.industry, overview.company.headcount_band].filter(Boolean).join(" · ") || "Similar companies",
              },
            ]}
          />
        </>
      ) : (
        <p style={monoNote}>Benchmarks appear after the next analytics recompute.</p>
      )}

      {benchmark && <PainBars pains={benchmark.common_pain_points} title="Pressure ranking (company)" />}

      <RoadmapSection title="Company priorities" reportState={reportState} />

      {benchmark && (
        <CohortMap
          title="Where you sit in your cohort"
          points={overview.map_points?.company ?? []}
          selfLabel={overview.company.name}
          cohortNoun="a company in your cohort (similar industry and size)"
        />
      )}

      <ReportTextSection
        header="Company Profile"
        ariaLabel="Company profile"
        reportState={reportState}
        // The page section header is now "Company Profile"; the report's inner
        // H2 of the same name becomes the stats block it actually is.
        transform={(md) => md.replace(/^##\s+Company Profile\s*$/im, "## Stats")}
      />

      <section style={{ padding: "48px 0 20px" }} aria-label="Functions">
        <div className="kicker" style={{ marginBottom: 24 }}>
          <b>[ Functions ]</b>
          <h2 style={sectionH2}>Function breakdowns</h2>
        </div>
        {overview.functions.length ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 0, border: "2px solid var(--ink)" }}>
            {overview.functions.map((fn, index) => (
              <button
                key={fn.function_key}
                onClick={() => onOpenFunction(fn.function_key)}
                className="hover-fill"
                style={{
                  textAlign: "left",
                  background: "var(--paper)",
                  border: "none",
                  borderRight: "2px solid var(--ink)",
                  borderBottom: index >= 0 ? "none" : undefined,
                  padding: "26px 24px",
                  cursor: "pointer",
                  font: "inherit",
                  color: "var(--ink)",
                }}
              >
                <strong style={{ display: "block", marginBottom: 8, fontWeight: 800, fontSize: 18, letterSpacing: "-0.01em" }}>
                  {fn.function_key}
                </strong>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: "#777",
                  }}
                >
                  {fn.respondents.length} contributor{fn.respondents.length === 1 ? "" : "s"}
                  {fn.benchmark?.avg_maturity != null && `  ·  maturity ${fmt(fn.benchmark.avg_maturity)}/5`}
                  {fn.benchmark?.percentile_peer != null && `  ·  ${pct(fn.benchmark.percentile_peer)} peer`}
                </span>
                {fn.benchmark?.persona_label && (
                  <span
                    style={{
                      display: "block",
                      marginTop: 10,
                      fontFamily: "var(--font-mono)",
                      fontWeight: 700,
                      fontSize: 12,
                      letterSpacing: "0.08em",
                      textTransform: "uppercase",
                      color: "var(--accent)",
                    }}
                  >
                    {fn.benchmark.persona_label}
                  </span>
                )}
              </button>
            ))}
          </div>
        ) : (
          <p style={monoNote}>No functions yet — sessions gain a function when discovery starts from the intake form.</p>
        )}
      </section>
    </>
  );
}

function FunctionPanel({
  breakdown,
  mapPoints,
  companyName,
  reportState,
}: {
  breakdown: FunctionBreakdown;
  mapPoints: MapPoint[];
  companyName: string;
  reportState: ReportState;
}) {
  const benchmark = breakdown.benchmark;
  return (
    <>
      {benchmark ? (
        <>
          <StatGrid
            stats={[
              { label: "Maturity", value: fmt(benchmark.avg_maturity), unit: "/5", note: `${breakdown.function_key} only` },
              {
                label: "Cohort standing",
                value: pctNum(benchmark.percentile_peer),
                unit: "%",
                note: benchmark.peer_group?.fell_back
                  ? "Of all functions — too few same-function peers"
                  : "Of the same function at other companies",
              },
              { label: "Voices", value: String(benchmark.respondent_count), unit: "", note: "Contributors" },
            ]}
          />
          <PersonaRow
            personaLabel={benchmark.persona_label}
            personaSummary={benchmark.persona_summary}
            buyingPersona={benchmark.buying_persona}
            bars={[
              {
                label: "Cohort standing (same function)",
                value: pct(benchmark.percentile_peer),
                width: benchmark.percentile_peer ?? 0,
                note: benchmark.peer_group?.fell_back
                  ? "All functions — few same-function peers"
                  : `${breakdown.function_key} at other companies`,
              },
            ]}
          />
        </>
      ) : (
        <p style={monoNote}>Function benchmarks appear after the next analytics recompute.</p>
      )}

      {benchmark && <PainBars pains={benchmark.common_pain_points} title="Pressure ranking (function)" />}

      <RoadmapSection title={breakdown.function_key} reportState={reportState} />

      {benchmark && (
        <CohortMap
          title={`Where this ${breakdown.function_key} team sits among its peers`}
          points={mapPoints}
          selfLabel={`${companyName} / ${breakdown.function_key}`}
          cohortNoun={`the ${breakdown.function_key} function at another company`}
        />
      )}

      <ReportTextSection
        header="Function Profile"
        ariaLabel={`${breakdown.function_key} report`}
        reportState={reportState}
      />

      <section style={panel} aria-label="Contributors">
        <h2 style={h2}>Contributors</h2>
        {breakdown.respondents.length ? (
          <p style={{ margin: 0, fontSize: 15 }}>
            {breakdown.respondents
              .map((r) => [r.name, r.role].filter(Boolean).join(" — ") || "Unnamed contributor")
              .join("  ·  ")}
          </p>
        ) : (
          <p style={monoNote}>No contributors recorded.</p>
        )}
      </section>

      <section style={panel} aria-label="Attributed answers">
        <h2 style={h2}>What this function told us</h2>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr>
                {["Topic", "Answer"].map((h) => (
                  <th key={h} style={th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {breakdown.answers.map((a) => (
                <tr key={a.slot_key}>
                  <td style={td}>{a.question ?? a.slot_key}</td>
                  <td style={td}>{String(a.structured_json?.value ?? a.raw_text ?? "—")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

type ReportState = {
  report: Report | null;
  status: string;
  generating: boolean;
  generate: () => Promise<void>;
};

// Loads (auto-generating once when absent) the deliverable report for the
// active scope; GET and POST share the URL.
function useReport(url: string): ReportState {
  const [report, setReport] = useState<Report | null>(null);
  const [status, setStatus] = useState<string>("");
  const [generating, setGenerating] = useState(false);
  const autoGeneratedFor = useRef<string | null>(null);

  const generate = useCallback(async () => {
    setGenerating(true);
    setStatus("Generating…");
    try {
      const r = await fetch(url, { method: "POST" });
      if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `HTTP ${r.status}`);
      setReport((await r.json()) as Report);
      setStatus("");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Generation failed.");
    } finally {
      setGenerating(false);
    }
  }, [url]);

  const loadLatest = useCallback(async () => {
    setStatus("Loading latest…");
    try {
      const r = await fetch(url);
      if (r.status === 404) {
        setReport(null);
        if (autoGeneratedFor.current !== url) {
          autoGeneratedFor.current = url;
          await generate();
        } else {
          setStatus("No report generated yet.");
        }
        return;
      }
      if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `HTTP ${r.status}`);
      setReport((await r.json()) as Report);
      setStatus("");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Could not load the report.");
    }
  }, [url, generate]);

  useEffect(() => {
    loadLatest();
  }, [loadLatest]);

  return { report, status, generating, generate };
}

// The structured Now/Next/Later grid from the generated report.
function RoadmapSection({ title, reportState }: { title: string; reportState: ReportState }) {
  const { report, status, generating } = reportState;
  const roadmap = report?.content_json?.roadmap;
  return (
    <section style={{ padding: "48px 0 20px" }} aria-label={`${title} roadmap`}>
      <div className="kicker" style={{ marginBottom: 24 }}>
        <b>[ Roadmap ]</b>
        <h2 style={sectionH2}>{title}</h2>
      </div>

      {roadmap?.length ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", border: "2px solid var(--ink)" }}>
          {roadmap.map((ph, index) => (
            <div key={ph.phase} style={{ padding: "30px 26px", borderRight: index < roadmap.length - 1 ? "2px solid var(--ink)" : "none" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 22 }}>
                <span style={{ width: 10, height: 10, background: "var(--accent)", display: "inline-block" }} />
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontWeight: 700,
                    fontSize: 13,
                    letterSpacing: "0.16em",
                    textTransform: "uppercase",
                  }}
                >
                  {ph.phase}
                </span>
              </div>
              {ph.items.map((it) => (
                <div key={it.title} style={{ padding: "14px 0", borderTop: "1px solid var(--hairline)" }}>
                  <div style={{ fontWeight: 700, fontSize: 16, lineHeight: 1.2, marginBottom: 5 }}>{it.title}</div>
                  <div style={{ fontSize: 13, lineHeight: 1.45, color: "#777" }}>{it.desc}</div>
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <p style={monoNote}>
          {generating ? "Generating the deliverable…" : status || "The roadmap appears once the deliverable is generated."}
        </p>
      )}
    </section>
  );
}

// The report text (roadmap section stripped — the grid IS that section).
function ReportTextSection({
  header,
  ariaLabel,
  reportState,
  transform,
}: {
  header: string;
  ariaLabel: string;
  reportState: ReportState;
  transform?: (md: string) => string;
}) {
  const { report, status, generating } = reportState;
  const roadmap = report?.content_json?.roadmap;
  const markdown = report ? stripRoadmapSection(report.rendered_md, Boolean(roadmap?.length)) : "";
  return (
    <section style={panel} aria-label={ariaLabel}>
      <h2 style={h2}>{header}</h2>
      {report ? (
        <article style={{ borderTop: "1px solid var(--hairline)", paddingTop: 14 }}>
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "#888",
              marginBottom: 10,
            }}
          >
            Generated {new Date(report.created_at).toLocaleString("en-US")}
          </div>
          <ReportMarkdown markdown={transform ? transform(markdown) : markdown} />
        </article>
      ) : (
        <p style={{ ...monoNote, padding: "8px 0" }}>
          {generating ? "Generating the deliverable…" : status || "The write-up appears once the deliverable is generated."}
        </p>
      )}
    </section>
  );
}

// The structured grid renders the Roadmap section; don't repeat it as text.
function stripRoadmapSection(markdown: string, hasGrid: boolean): string {
  if (!hasGrid) return markdown;
  const lines = markdown.split("\n");
  const start = lines.findIndex((line) => /^##\s+Roadmap\s*$/i.test(line.trim()));
  if (start === -1) return markdown;
  let end = lines.length;
  for (let i = start + 1; i < lines.length; i++) {
    if (/^##\s+/.test(lines[i])) {
      end = i;
      break;
    }
  }
  return [...lines.slice(0, start), ...lines.slice(end)].join("\n").trim();
}

function StatGrid({ stats }: { stats: { label: string; value: string; unit: string; note: string }[] }) {
  return (
    <section
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${stats.length}, 1fr)`,
        borderLeft: "2px solid var(--ink)",
        borderRight: "2px solid var(--ink)",
        borderBottom: "2px solid var(--ink)",
      }}
      aria-label="Benchmarks"
    >
      {stats.map((s, index) => (
        <div key={s.label} style={{ padding: "30px 26px 34px", borderRight: index < stats.length - 1 ? "2px solid var(--ink)" : "none" }}>
          <div className="mono-label" style={{ color: "#777", marginBottom: 18 }}>{s.label}</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontWeight: 900, fontSize: "clamp(40px, 4.5vw, 68px)", lineHeight: 0.85, letterSpacing: "-0.03em" }}>
              {s.value}
            </span>
            {s.unit && (
              <span style={{ fontFamily: "var(--font-mono)", fontSize: 14, color: "var(--accent)", fontWeight: 700 }}>
                {s.unit}
              </span>
            )}
          </div>
          <div style={{ marginTop: 16, fontSize: 13, lineHeight: 1.4, color: "#666" }}>{s.note}</div>
        </div>
      ))}
    </section>
  );
}

function PersonaRow({
  personaLabel,
  personaSummary,
  buyingPersona,
  bars,
}: {
  personaLabel: string | null;
  personaSummary: string | null;
  buyingPersona: string | null;
  bars: { label: string; value: string; width: number; note: string }[];
}) {
  return (
    <section style={{ display: "grid", gridTemplateColumns: "1.35fr 1fr" }}>
      <div style={{ padding: 44, borderLeft: "2px solid var(--ink)", borderBottom: "2px solid var(--ink)" }}>
        <div className="mono-label" style={{ color: "#777", letterSpacing: "0.14em", marginBottom: 14 }}>Persona</div>
        {personaLabel ? (
          <>
            <h2
              style={{
                margin: "0 0 22px",
                fontWeight: 800,
                fontSize: "clamp(26px, 3vw, 40px)",
                lineHeight: 1,
                letterSpacing: "-0.02em",
                color: "var(--accent)",
                textTransform: "uppercase",
              }}
            >
              {personaLabel}
            </h2>
            {personaSummary && <p style={{ margin: "0 0 18px", fontSize: 16, lineHeight: 1.6, color: "#2a2a2a" }}>{personaSummary}</p>}
            {buyingPersona && <p style={{ margin: 0, fontSize: 16, lineHeight: 1.6, color: "#2a2a2a" }}>{buyingPersona}</p>}
          </>
        ) : (
          <p style={{ ...monoNote, padding: 0 }}>Persona appears after the next analytics recompute.</p>
        )}
      </div>
      <div
        style={{
          padding: 44,
          borderLeft: "2px solid var(--ink)",
          borderRight: "2px solid var(--ink)",
          borderBottom: "2px solid var(--ink)",
          background: "var(--paper-alt)",
        }}
      >
        <div className="mono-label" style={{ color: "#777", letterSpacing: "0.14em", marginBottom: 26 }}>
          Where you sit in your cohort
        </div>
        {bars.map((b) => (
          <div key={b.label} style={{ marginBottom: 26 }}>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 8 }}>
              <span className="mono-label" style={{ letterSpacing: "0.08em" }}>{b.label}</span>
              <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 20 }}>{b.value}</span>
            </div>
            <div className="meter meter--mid">
              <div style={{ width: `${Math.max(0, Math.min(100, b.width))}%` }} />
            </div>
            <div style={{ marginTop: 6, fontSize: 12, lineHeight: 1.4, color: "#888" }}>{b.note}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function PainBars({ pains, title }: { pains: PainPoint[] | null; title: string }) {
  const rows = (pains ?? []).filter((p) => (p.score ?? p.count ?? 0) > 0);
  const top = rows.length ? Math.max(...rows.map((p) => p.score ?? p.count ?? 0)) : 0;
  return (
    // Breathing room below the stat/persona block — same 20px gap as between
    // the roadmap grid and the cohort chart.
    <section style={{ ...panel, marginTop: 20 }} aria-label={title}>
      <h2 style={h2}>{title}</h2>
      {rows.length ? (
        <div style={{ display: "grid", gap: 12 }}>
          {rows.map((p) => {
            const score = p.score ?? p.count ?? 0;
            return (
              <div key={p.slot_key}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <strong style={{ fontFamily: "var(--font-mono)", fontSize: 12, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                    {painLabel(p.slot_key)}
                  </strong>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "#666" }}>{score.toFixed(1)}</span>
                </div>
                <div className="meter meter--thin" style={{ borderWidth: 2, height: 10 }}>
                  <div style={{ width: `${Math.max(8, (score / top) * 100)}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p style={monoNote}>Pressure scores appear after the next analytics recompute.</p>
      )}
    </section>
  );
}

function slugify(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "deliverable";
}

function fmt(value: number | null): string {
  return typeof value === "number" ? value.toFixed(1) : "—";
}

function pctNum(value: number | null): string {
  return typeof value === "number" ? String(Math.round(value)) : "—";
}

function pct(value: number | null): string {
  return typeof value === "number" ? `${Math.round(value)}%` : "—";
}

const monoNote: React.CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: 13,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#666",
  padding: "40px 0",
};
const panel: React.CSSProperties = {
  border: "2px solid var(--ink)",
  padding: "26px 28px",
  margin: "0 0 18px",
  background: "var(--paper)",
};
const h2: React.CSSProperties = {
  margin: "0 0 16px",
  fontWeight: 800,
  fontSize: "clamp(20px, 2.2vw, 28px)",
  letterSpacing: "-0.02em",
};
const sectionH2: React.CSSProperties = {
  margin: 0,
  fontWeight: 900,
  fontSize: "clamp(30px, 4vw, 56px)",
  lineHeight: 0.95,
  letterSpacing: "-0.02em",
  textTransform: "uppercase",
};
const th: React.CSSProperties = {
  padding: "10px 8px",
  borderBottom: "2px solid var(--ink)",
  textAlign: "left",
  color: "#777",
  fontFamily: "var(--font-mono)",
  fontSize: 11,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
};
const td: React.CSSProperties = {
  padding: "10px 8px",
  borderBottom: "1px solid var(--hairline)",
  verticalAlign: "top",
};
