"use client";

// Internal destination: cohort personas at company/function grain, brutalist
// system. The positioning map (absolutely-positioned bubbles on a crosshair
// plot), legend rows, and dropdown share one selection; the detail card with
// member drill-down appears only when a persona is picked. One recompute
// action updates clusters, the write-up, and everything on the page.

import { useCallback, useEffect, useMemo, useState } from "react";
import ReportMarkdown from "./ReportMarkdown";
import { painLabel } from "../lib/painLabel";

type Member = {
  company_id: string;
  company_name: string;
  account_code: string | null;
  function_key: string | null;
  avg_maturity: number | null;
  percentile_cohort: number | null;
  percentile_peer: number | null;
  umap_x: number | null;
  umap_y: number | null;
};

type Persona = {
  id: string;
  label: string;
  size: number;
  avg_maturity: number | null;
  common_pain_points: { slot_key: string; score?: number; count?: number }[] | null;
  common_tech_stack: string[] | null;
  summary: string | null;
  buying_persona: string | null;
  members: Member[];
};

type Scope = { clusters: Persona[]; pressure: { slot_key: string; score: number }[] };

type Snapshot = {
  run: { id: string; n_clusters: number; silhouette_score: number | null; created_at: string } | null;
  scopes: { function: Scope; company: Scope };
};

type Report = { id: string; rendered_md: string; created_at: string };

type RecomputeResult = {
  respondents_processed: number;
  run_id: string | null;
  function_entities: number;
  function_clusters: number;
  function_silhouette: number;
  company_entities: number;
  company_clusters: number;
};

type RecomputeState = {
  status: "idle" | "running" | "success" | "error";
  message: string;
  result: RecomputeResult | null;
};

// Derived per-persona plot/legend attributes (mock's urgency taxonomy).
type PersonaViz = {
  persona: Persona;
  index: number;
  maturity: number | null;
  pressure: number; // normalized 0-1
  fill: string;
  tag: "Most urgent" | "Priority" | "Healthy";
  urgent: boolean;
};

const NEUTRAL_FILL = "#9A968B";

export default function InternalDashboard({ token }: { token: string }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [grain, setGrain] = useState<"function" | "company">("company");
  const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(null);
  const [selectedMember, setSelectedMember] = useState<Member | null>(null);
  const [writeupKey, setWriteupKey] = useState(0);
  const [recompute, setRecompute] = useState<RecomputeState>({ status: "idle", message: "", result: null });

  const fetchSnapshot = useCallback(async () => {
    const r = await fetch(`/api/admin/internal?token=${encodeURIComponent(token)}`);
    if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `HTTP ${r.status}`);
    setSnapshot((await r.json()) as Snapshot);
  }, [token]);

  useEffect(() => {
    fetchSnapshot().catch((e: Error) => setError(e.message));
  }, [fetchSnapshot]);

  // The one compute action: re-cluster, regenerate the write-up, and refresh
  // everything on the page (ultimately this whole chain goes nightly).
  const runRecompute = useCallback(async () => {
    setRecompute({
      status: "running",
      message: "Recomputing personas and benchmarks. This may take 20-60 seconds.",
      result: null,
    });
    try {
      const response = await fetch("/api/admin/recompute", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof body.detail === "string" ? body.detail : `HTTP ${response.status}`);
      }
      const result = body as RecomputeResult;
      setRecompute({
        status: "running",
        message: "Personas recomputed. Rewriting the intelligence write-up and refreshing the dashboard…",
        result,
      });
      const r = await fetch("/api/admin/reports/internal", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (!r.ok) {
        throw new Error((await r.json().catch(() => null))?.detail ?? "Write-up regeneration failed.");
      }
      await fetchSnapshot();
      setSelectedPersonaId(null);
      setSelectedMember(null);
      setWriteupKey((k) => k + 1);
      setRecompute({
        status: "success",
        message: `Run ${result.run_id ?? "complete"} finished — dashboard and write-up updated.`,
        result,
      });
    } catch (e) {
      setRecompute({
        status: "error",
        message: e instanceof Error ? e.message : "Recompute failed.",
        result: null,
      });
    }
  }, [token, fetchSnapshot]);

  const scope = snapshot?.scopes[grain];
  const viz = useMemo(() => buildViz(scope?.clusters ?? []), [scope]);
  const takeaways = useMemo(() => buildTakeaways(viz), [viz]);

  if (error) return <p style={{ ...monoNote, color: "var(--accent)" }}>{error}</p>;
  if (!snapshot || !scope) return <p style={monoNote}>Loading cohort intelligence…</p>;

  const selectPersona = (id: string | null) => {
    setSelectedPersonaId(id);
    setSelectedMember(null);
  };
  const selected = viz.find((v) => v.persona.id === selectedPersonaId) ?? null;

  return (
    <>
      <section style={{ padding: "56px 0 34px", borderBottom: "2px solid var(--ink)" }}>
        <div className="kicker-solo" style={{ marginBottom: 20 }}>Internal · Restricted</div>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", justifyContent: "space-between", gap: 28 }}>
          <div>
            <h1
              style={{
                margin: 0,
                fontWeight: 900,
                fontSize: "clamp(44px, 6.5vw, 104px)",
                lineHeight: 0.9,
                letterSpacing: "-0.035em",
                textTransform: "uppercase",
              }}
            >
              Cohort Intelligence
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
              {snapshot.run
                ? `Latest run ${new Date(snapshot.run.created_at).toLocaleString("en-US")}  ·  ${snapshot.run.n_clusters} clusters  ·  silhouette ${snapshot.run.silhouette_score?.toFixed(3) ?? "—"}`
                : "No analytics run yet — run a recompute."}
            </div>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 16, flexShrink: 0 }}>
            <button onClick={runRecompute} disabled={recompute.status === "running"} className="hard-btn">
              {recompute.status === "running" ? "Running…" : "Run recompute"}
            </button>
            <a
              href={`/api/admin/internal/html?token=${encodeURIComponent(token)}`}
              className="hard-btn hard-btn--ink"
            >
              ↓ Download dashboard
            </a>
          </div>
        </div>
      </section>

      {(recompute.message || recompute.result) && (
        <section
          aria-label="Recompute status"
          style={{
            borderLeft: "2px solid var(--ink)",
            borderRight: "2px solid var(--ink)",
            borderBottom: "2px solid var(--ink)",
            padding: "18px 28px",
          }}
        >
          <p
            style={{
              margin: 0,
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              letterSpacing: "0.04em",
              fontWeight: 700,
              color:
                recompute.status === "error" ? "var(--accent)" : recompute.status === "running" ? "#666" : "var(--ink)",
            }}
          >
            {recompute.message}
          </p>
          {recompute.result && (
            <dl
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
                gap: 10,
                margin: "14px 0 0",
              }}
            >
              {[
                ["Respondents", String(recompute.result.respondents_processed)],
                ["Function personas", `${recompute.result.function_clusters} (${recompute.result.function_entities} fn)`],
                ["Company personas", `${recompute.result.company_clusters} (${recompute.result.company_entities} co)`],
                ["Silhouette", recompute.result.function_silhouette.toFixed(3)],
              ].map(([label, value]) => (
                <div key={label} style={{ padding: "10px 12px", background: "var(--paper-alt)", border: "1px solid var(--hairline)" }}>
                  <dt className="mono-label" style={{ fontSize: 10 }}>{label}</dt>
                  <dd style={{ margin: "4px 0 0", fontSize: 18, fontWeight: 800 }}>{value}</dd>
                </div>
              ))}
            </dl>
          )}
        </section>
      )}

      <nav className="seg" aria-label="Grain">
        <button aria-pressed={grain === "company"} onClick={() => { setGrain("company"); selectPersona(null); }}>
          Companies
        </button>
        <button aria-pressed={grain === "function"} onClick={() => { setGrain("function"); selectPersona(null); }}>
          Functions
        </button>
        <div className="seg-spacer" />
      </nav>

      <section
        style={{
          borderLeft: "2px solid var(--ink)",
          borderRight: "2px solid var(--ink)",
          borderBottom: "2px solid var(--ink)",
          padding: "32px 28px",
        }}
        aria-label="Positioning map"
      >
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 16, marginBottom: 8 }}>
          <h2 style={{ margin: 0, fontWeight: 800, fontSize: "clamp(24px, 2.6vw, 34px)", letterSpacing: "-0.02em" }}>
            Where the {grain === "company" ? "companies" : "functions"} cluster
          </h2>
          <select
            value={selectedPersonaId ?? ""}
            onChange={(e) => selectPersona(e.target.value || null)}
            aria-label="Drill into a persona"
            style={{
              border: "2px solid var(--ink)",
              background: "var(--paper)",
              padding: "10px 14px",
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              color: "var(--ink)",
              cursor: "pointer",
            }}
          >
            <option value="">Drill into a persona…</option>
            {viz.map((v) => (
              <option key={v.persona.id} value={v.persona.id}>
                {v.persona.label}
              </option>
            ))}
          </select>
        </div>
        <p style={{ margin: "0 0 26px", maxWidth: 900, fontSize: 13, lineHeight: 1.55, color: "#666" }}>
          <strong style={{ color: "var(--ink)" }}>How to read this:</strong> each bubble is a persona
          — a group that answers discovery the same way. Right = more mature operations; higher =
          more pressure (weighted pain). Bigger bubble = more members. Best position is bottom-right;
          top-left personas need the most help. Click a bubble or a legend row to drill in.
        </p>

        <div
          style={{
            position: "relative",
            height: 460,
            border: "2px solid var(--ink)",
            background: "var(--paper-alt)",
            backgroundImage:
              "linear-gradient(90deg, transparent 49.6%, var(--hairline) 49.6%, var(--hairline) 50.4%, transparent 50.4%)," +
              "linear-gradient(0deg, transparent 49.6%, var(--hairline) 49.6%, var(--hairline) 50.4%, transparent 50.4%)",
          }}
        >
          <QuadrantLabel style={{ top: 14, left: 18, color: "var(--accent)", fontWeight: 700, maxWidth: 200 }}>
            Low maturity · high pressure — most urgent
          </QuadrantLabel>
          <QuadrantLabel style={{ top: 14, right: 18, textAlign: "right" }}>High maturity · high pressure</QuadrantLabel>
          <QuadrantLabel style={{ bottom: 14, left: 18 }}>Low maturity · low pressure</QuadrantLabel>
          <QuadrantLabel style={{ bottom: 14, right: 18, textAlign: "right" }}>
            High maturity · low pressure — healthiest
          </QuadrantLabel>

          {viz.map((v) => {
            if (v.maturity == null) return null;
            // ponytail: mock's size formula, capped so a 40-member persona still fits the plot
            const size = Math.min(46 + v.persona.size * 3.2, 130);
            const active = selectedPersonaId === v.persona.id;
            return (
              <button
                key={v.persona.id}
                onClick={() => selectPersona(active ? null : v.persona.id)}
                title={`${v.persona.label} — maturity ${v.maturity.toFixed(1)}/5, ${v.persona.size} member(s)`}
                style={{
                  position: "absolute",
                  left: `${(v.maturity / 5) * 82 + 9}%`,
                  bottom: `${v.pressure * 78 + 8}%`,
                  width: size,
                  height: size,
                  transform: "translate(-50%, 50%)",
                  borderRadius: "50%",
                  border: "2px solid var(--ink)",
                  background: v.fill,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontFamily: "var(--font-mono)",
                  fontWeight: 700,
                  fontSize: 14,
                  color: "#fff",
                  cursor: "pointer",
                  padding: 0,
                  boxShadow: active ? "0 0 0 4px var(--paper), 0 0 0 6px var(--ink)" : "none",
                }}
              >
                {v.index + 1}
              </button>
            );
          })}
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, 1fr)",
            gap: "0 40px",
            marginTop: 26,
            borderTop: "2px solid var(--ink)",
          }}
        >
          {viz.map((v) => (
            <button
              key={v.persona.id}
              onClick={(e) => {
                e.currentTarget.blur();
                selectPersona(selectedPersonaId === v.persona.id ? null : v.persona.id);
              }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 16,
                padding: "15px 8px",
                borderBottom: "1px solid var(--hairline)",
                background: selectedPersonaId === v.persona.id ? "var(--paper-alt)" : "transparent",
                border: "none",
                borderBottomStyle: "solid",
                borderBottomWidth: 1,
                borderBottomColor: "var(--hairline)",
                cursor: "pointer",
                font: "inherit",
                textAlign: "left",
                color: "var(--ink)",
              }}
            >
              <span
                style={{
                  flexShrink: 0,
                  width: 30,
                  height: 30,
                  borderRadius: "50%",
                  border: "2px solid var(--ink)",
                  background: v.fill,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontFamily: "var(--font-mono)",
                  fontWeight: 700,
                  fontSize: 12,
                  color: "#fff",
                }}
              >
                {v.index + 1}
              </span>
              <span style={{ flex: 1, minWidth: 0 }}>
                <span style={{ display: "block", fontWeight: 700, fontSize: 15, lineHeight: 1.15 }}>
                  {v.persona.label}
                </span>
                <span
                  style={{
                    display: "block",
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    letterSpacing: "0.05em",
                    textTransform: "uppercase",
                    color: "#888",
                    marginTop: 3,
                  }}
                >
                  {v.maturity != null ? `maturity ${v.maturity.toFixed(1)}/5` : "unplaced"}  ·  {v.persona.size} members
                </span>
              </span>
              <span
                style={{
                  flexShrink: 0,
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  color: v.urgent ? "var(--accent)" : "#888",
                  fontWeight: 700,
                }}
              >
                {v.tag}
              </span>
            </button>
          ))}
          {!viz.length && <p style={monoNote}>No {grain}-grain personas yet — run a recompute.</p>}
        </div>
      </section>

      {selected && (
        <article style={card} aria-label="Persona detail">
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <h2 style={{ margin: "0 0 4px", fontWeight: 800, fontSize: 22, letterSpacing: "-0.01em", display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  border: "2px solid var(--ink)",
                  background: selected.fill,
                  display: "inline-block",
                }}
              />
              {selected.persona.label}
            </h2>
            <button
              onClick={() => selectPersona(null)}
              style={{
                border: "none",
                background: "none",
                cursor: "pointer",
                color: "#888",
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              ✕ Close
            </button>
          </div>
          <p style={{ margin: "6px 0 10px", fontSize: 15, lineHeight: 1.5, color: "#333" }}>
            {takeaways.get(selected.persona.id)}
          </p>
          <p
            style={{
              margin: "0 0 12px",
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              color: "#888",
            }}
          >
            {selected.persona.size} member(s)
            {selected.persona.avg_maturity != null && `  ·  avg maturity ${selected.persona.avg_maturity.toFixed(1)}/5`}
            {selected.persona.common_tech_stack?.length ? `  ·  ${selected.persona.common_tech_stack.join(", ")}` : ""}
          </p>
          {selected.persona.summary && <p style={{ margin: "0 0 8px", fontSize: 15, lineHeight: 1.55 }}>{selected.persona.summary}</p>}
          {selected.persona.buying_persona && (
            <p style={{ margin: "0 0 14px", fontSize: 15, lineHeight: 1.55 }}>{selected.persona.buying_persona}</p>
          )}
          {selected.persona.common_pain_points?.length ? (
            <p style={{ margin: "0 0 14px", fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.05em", textTransform: "uppercase", color: "var(--accent)" }}>
              Top pains:{" "}
              {selected.persona.common_pain_points
                .slice(0, 3)
                .map((p) => painLabel(p.slot_key))
                .join(", ")}
            </p>
          ) : null}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {selected.persona.members.map((member) => {
              const isActive =
                selectedMember?.company_id === member.company_id &&
                selectedMember?.function_key === member.function_key;
              return (
                <button
                  key={`${member.company_id}:${member.function_key ?? ""}`}
                  onClick={() => setSelectedMember(isActive ? null : member)}
                  className="flat-btn"
                  style={isActive ? { background: "var(--ink)", color: "var(--paper)" } : undefined}
                >
                  {member.company_name}
                  {member.account_code ? ` (${member.account_code})` : ""}
                  {member.function_key ? ` / ${member.function_key}` : ""}
                </button>
              );
            })}
            {!selected.persona.members.length && <span style={{ ...monoNote, padding: 0 }}>No members benchmarked yet.</span>}
          </div>
        </article>
      )}

      {selectedMember && <MemberDrilldown member={selectedMember} token={token} />}

      <PressurePanel
        title={`Pressure ranking (${grain} grain) — ${selected?.persona.label ?? "All"}`}
        pressure={
          selected
            ? (selected.persona.common_pain_points ?? [])
                .map((p) => ({ slot_key: p.slot_key, score: p.score ?? p.count ?? 0 }))
                .sort((a, b) => b.score - a.score)
            : scope.pressure
        }
      />

      <MacroWriteup token={token} refreshKey={writeupKey} />
    </>
  );
}

// Normalize pressure + derive urgency fills/tags (mock taxonomy: accent =
// urgent, ink = high-pressure, neutral otherwise).
function buildViz(personas: Persona[]): PersonaViz[] {
  const loads = personas.map((p) =>
    (p.common_pain_points ?? []).reduce((sum, pain) => sum + (pain.score ?? pain.count ?? 0), 0),
  );
  const maxLoad = Math.max(1, ...loads);
  const maturities = personas.map((p) => p.avg_maturity).filter((m): m is number => m != null);
  const medianMaturity = median(maturities.length ? maturities : [3]);
  const pressures = loads.map((l) => l / maxLoad);
  const medianPressure = median(pressures.length ? pressures : [0.5]);

  return personas.map((p, index) => {
    const pressure = pressures[index] ?? 0;
    const maturity = p.avg_maturity;
    const urgent = maturity != null && maturity < medianMaturity && pressure > medianPressure;
    const healthy = maturity != null && maturity >= medianMaturity && pressure <= medianPressure;
    return {
      persona: p,
      index,
      maturity,
      pressure,
      urgent,
      tag: urgent ? "Most urgent" : healthy ? "Healthy" : "Priority",
      fill: urgent ? "var(--accent)" : pressure > 0.5 ? "var(--ink)" : NEUTRAL_FILL,
    };
  });
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

// One sentence per persona for the detail card: superlatives first (largest /
// most pressure / most mature), quadrant position otherwise.
function buildTakeaways(viz: PersonaViz[]): Map<string, string> {
  const out = new Map<string, string>();
  if (!viz.length) return out;
  const largest = [...viz].sort((a, b) => b.persona.size - a.persona.size)[0];
  const pressured = [...viz].sort((a, b) => b.pressure - a.pressure)[0];
  const placed = viz.filter((v) => v.maturity != null);
  const mature = [...placed].sort((a, b) => (b.maturity ?? 0) - (a.maturity ?? 0))[0];

  for (const v of viz) {
    const flags: string[] = [];
    if (viz.length > 1) {
      if (v.persona.id === largest.persona.id) flags.push("largest group — the cohort's center of gravity");
      if (v.persona.id === pressured.persona.id) flags.push("carries the most pressure");
      if (mature && v.persona.id === mature.persona.id) {
        flags.push(`most mature (${(v.maturity as number).toFixed(1)}/5) — what "good" looks like`);
      }
    }
    let sentence: string;
    if (flags.length) {
      const joined = flags.join("; ");
      sentence = joined.charAt(0).toUpperCase() + joined.slice(1) + ".";
    } else if (v.maturity == null) {
      sentence = "Not yet placed on the map.";
    } else {
      sentence =
        v.tag === "Most urgent"
          ? "Low maturity with high pressure — the most urgent conversations."
          : v.tag === "Healthy"
            ? "High maturity, low pressure — a strong position."
            : "Mid position — worth watching as the cohort grows.";
    }
    out.set(v.persona.id, sentence);
  }
  return out;
}

// The client write-up: account intel for the clicked member, formatted like
// every other write-up panel, with a button through to the External view.
function MemberDrilldown({ member, token }: { member: Member; token: string }) {
  return (
    <section style={card} aria-label="Member drill-down">
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
        <div>
          <h2 style={{ ...h2, marginBottom: 6 }}>
            {member.company_name}
            {member.function_key ? ` / ${member.function_key}` : ""}
          </h2>
          <p
            style={{
              margin: "0 0 14px",
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              color: "#888",
            }}
          >
            {[
              member.account_code,
              member.avg_maturity != null ? `maturity ${member.avg_maturity.toFixed(1)}/5` : null,
              member.percentile_peer != null ? `${Math.round(member.percentile_peer)}th peer pct.` : null,
              member.percentile_cohort != null ? `${Math.round(member.percentile_cohort)}th cohort pct.` : null,
            ]
              .filter(Boolean)
              .join("  ·  ")}
          </p>
        </div>
        <a
          href={`/external/${member.company_id}`}
          target="_blank"
          rel="noreferrer"
          className="flat-btn"
          style={{ textDecoration: "none", flexShrink: 0 }}
        >
          Open external view →
        </a>
      </div>
      <AccountIntel companyId={member.company_id} token={token} />
    </section>
  );
}

function AccountIntel({ companyId, token }: { companyId: string; token: string }) {
  const [report, setReport] = useState<Report | null>(null);
  const [status, setStatus] = useState("");
  const [generating, setGenerating] = useState(false);
  const query = `companyId=${encodeURIComponent(companyId)}&token=${encodeURIComponent(token)}`;

  useEffect(() => {
    setStatus("Loading account intel…");
    setReport(null);
    fetch(`/api/admin/reports/account?${query}`)
      .then(async (r) => {
        if (r.status === 404) {
          setStatus("No account intel generated yet.");
          return;
        }
        if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `HTTP ${r.status}`);
        setReport((await r.json()) as Report);
        setStatus("");
      })
      .catch((e: Error) => setStatus(e.message));
  }, [query]);

  const generate = async () => {
    setGenerating(true);
    setStatus("Generating account intel…");
    try {
      const r = await fetch(`/api/admin/reports/account?${query}`, { method: "POST" });
      if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `HTTP ${r.status}`);
      setReport((await r.json()) as Report);
      setStatus("");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Generation failed.");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 14, marginBottom: 12 }}>
        <h3 className="mono-label" style={{ margin: 0, fontSize: 12, letterSpacing: "0.14em", color: "#777" }}>
          Account intel (opportunity, ideal customer profile, product fit)
        </h3>
        <button onClick={generate} disabled={generating} className="flat-btn">
          {generating ? "Generating…" : report ? "Regenerate" : "Generate"}
        </button>
        {status && !generating && <span style={{ ...monoNote, padding: 0 }}>{status}</span>}
      </div>
      {report && (
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
          <ReportMarkdown markdown={report.rendered_md} />
        </article>
      )}
    </div>
  );
}

// Same section shape as the External write-up panel (header, generated line,
// hairline rule, report text).
function MacroWriteup({ token, refreshKey }: { token: string; refreshKey: number }) {
  const [report, setReport] = useState<Report | null>(null);
  const [status, setStatus] = useState("Loading write-up…");

  useEffect(() => {
    fetch(`/api/admin/reports/internal?token=${encodeURIComponent(token)}`)
      .then(async (r) => {
        if (r.status === 404) {
          setStatus("No write-up generated yet — run a recompute.");
          return;
        }
        if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `HTTP ${r.status}`);
        setReport((await r.json()) as Report);
        setStatus("");
      })
      .catch((e: Error) => setStatus(e.message));
  }, [token, refreshKey]);

  return (
    <section style={{ ...card, marginBottom: 18 }} aria-label="Internal intelligence write-up">
      <h2 style={h2}>Internal intelligence write-up</h2>
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
          <ReportMarkdown markdown={report.rendered_md} />
        </article>
      ) : (
        <p style={{ ...monoNote, padding: "8px 0" }}>{status}</p>
      )}
    </section>
  );
}

function PressurePanel({
  pressure,
  title,
}: {
  pressure: { slot_key: string; score: number }[];
  title: string;
}) {
  const top = pressure.length ? pressure[0].score : 0;
  return (
    <section style={card} aria-label="Pressure ranking">
      <h2 style={h2}>{title}</h2>
      {pressure.length ? (
        <div style={{ display: "grid", gap: 12 }}>
          {pressure.map((p) => (
            <div key={p.slot_key}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <strong style={{ fontFamily: "var(--font-mono)", fontSize: 12, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                  {painLabel(p.slot_key)}
                </strong>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "#666" }}>{p.score.toFixed(1)}</span>
              </div>
              <div className="meter" style={{ height: 10 }}>
                <div style={{ width: `${Math.max(8, (p.score / top) * 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p style={{ ...monoNote, padding: 0 }}>Pressure scores appear after the next recompute.</p>
      )}
    </section>
  );
}

function QuadrantLabel({ style, children }: { style: React.CSSProperties; children: React.ReactNode }) {
  return (
    <span
      style={{
        position: "absolute",
        fontFamily: "var(--font-mono)",
        fontSize: 11,
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        color: "#888",
        ...style,
      }}
    >
      {children}
    </span>
  );
}

// Detached card, same border/padding as the External panels, separated by the
// same 20px gap the External view uses between its cards.
const card: React.CSSProperties = {
  border: "2px solid var(--ink)",
  padding: "26px 28px",
  marginTop: 20,
  background: "var(--paper)",
};
const h2: React.CSSProperties = {
  margin: "0 0 16px",
  fontWeight: 800,
  fontSize: "clamp(20px, 2.2vw, 28px)",
  letterSpacing: "-0.02em",
};
const monoNote: React.CSSProperties = {
  fontFamily: "var(--font-mono)",
  fontSize: 13,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "#666",
  padding: "40px 0",
};
