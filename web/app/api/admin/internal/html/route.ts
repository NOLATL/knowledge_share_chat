// BFF: the full internal-dashboard download — cohort personas per grain (with
// the positioning chart) plus the macro write-up, paginated (one printed page
// per section). Admin-gated.
import { escapeHtml, renderPaginatedHtml } from "@/lib/markdown";
import { painLabel } from "@/lib/painLabel";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";

type Member = {
  company_name: string;
  account_code: string | null;
  function_key: string | null;
  avg_maturity: number | null;
  percentile_peer: number | null;
};
type Persona = {
  label: string;
  size: number;
  avg_maturity: number | null;
  summary: string | null;
  buying_persona: string | null;
  common_pain_points: { slot_key: string; score?: number; count?: number }[] | null;
  common_tech_stack: string[] | null;
  members: Member[];
};
type Snapshot = {
  run: { created_at: string } | null;
  scopes: Record<string, { clusters: Persona[]; pressure: { slot_key: string; score: number }[] }>;
};

// Static render of the dashboard's positioning chart (same geometry, urgency
// fills, and numbering as InternalDashboard.tsx) so the download matches the
// screen. Brutalist system: ink/accent/neutral fills, crosshair plot.
const INK = "#0A0A0A";
const ACCENT = "#E01B13";
const NEUTRAL = "#9A968B";
const HAIRLINE = "#D8D5CC";
const PAPER_ALT = "#EFEDE6";

function painLoadOf(pains: Persona["common_pain_points"]): number {
  return (pains ?? []).reduce((sum, p) => sum + (p.score ?? p.count ?? 0), 0);
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function personaMapHtml(clusters: Persona[]): string {
  const loads = clusters.map((c) => painLoadOf(c.common_pain_points));
  const maxLoad = Math.max(1, ...loads);
  const pressures = loads.map((l) => l / maxLoad);
  const maturities = clusters.map((c) => c.avg_maturity).filter((m): m is number => m != null);
  if (!maturities.length) return "";
  const medMaturity = median(maturities);
  const medPressure = median(pressures.length ? pressures : [0.5]);

  const mono = "font-family:'JetBrains Mono',monospace;";
  const quadrant = (pos: string, text: string, urgent = false) =>
    `<span style="position:absolute;${pos};${mono}font-size:11px;letter-spacing:0.06em;text-transform:uppercase;` +
    `color:${urgent ? ACCENT : "#888"};${urgent ? "font-weight:700;max-width:200px;" : ""}">${text}</span>`;

  const bubbles = clusters
    .map((c, index) => {
      if (c.avg_maturity == null) return "";
      const pressure = pressures[index] ?? 0;
      const urgent = c.avg_maturity < medMaturity && pressure > medPressure;
      const fill = urgent ? ACCENT : pressure > 0.5 ? INK : NEUTRAL;
      const size = Math.min(46 + c.size * 3.2, 130);
      return (
        `<div style="position:absolute;left:${((c.avg_maturity / 5) * 82 + 9).toFixed(1)}%;` +
        `bottom:${(pressure * 78 + 8).toFixed(1)}%;width:${size.toFixed(0)}px;height:${size.toFixed(0)}px;` +
        `transform:translate(-50%,50%);border-radius:50%;border:2px solid ${INK};background:${fill};` +
        `display:flex;align-items:center;justify-content:center;${mono}font-weight:700;font-size:14px;color:#fff;">${index + 1}</div>`
      );
    })
    .join("");

  const legend = clusters
    .map((c, index) => {
      const pressure = pressures[index] ?? 0;
      const urgent = c.avg_maturity != null && c.avg_maturity < medMaturity && pressure > medPressure;
      const healthy = c.avg_maturity != null && c.avg_maturity >= medMaturity && pressure <= medPressure;
      const fill = urgent ? ACCENT : pressure > 0.5 ? INK : NEUTRAL;
      const tag = urgent ? "Most urgent" : healthy ? "Healthy" : "Priority";
      return (
        `<div style="display:flex;align-items:center;gap:14px;padding:12px 0;border-bottom:1px solid ${HAIRLINE};">` +
        `<span style="flex-shrink:0;width:28px;height:28px;border-radius:50%;border:2px solid ${INK};background:${fill};` +
        `display:flex;align-items:center;justify-content:center;${mono}font-weight:700;font-size:12px;color:#fff;">${index + 1}</span>` +
        `<span style="flex:1;min-width:0;"><span style="display:block;font-weight:700;font-size:14px;">${escapeHtml(c.label)}</span>` +
        `<span style="display:block;${mono}font-size:10px;letter-spacing:0.05em;text-transform:uppercase;color:#888;margin-top:2px;">` +
        `${c.avg_maturity != null ? `maturity ${c.avg_maturity.toFixed(1)}/5` : "unplaced"} · ${c.size} members</span></span>` +
        `<span style="flex-shrink:0;${mono}font-size:10px;letter-spacing:0.08em;text-transform:uppercase;font-weight:700;` +
        `color:${urgent ? ACCENT : "#888"};">${tag}</span></div>`
      );
    })
    .join("");

  return (
    `<div style="position:relative;height:420px;border:2px solid ${INK};background:${PAPER_ALT};` +
    `background-image:linear-gradient(90deg,transparent 49.6%,${HAIRLINE} 49.6%,${HAIRLINE} 50.4%,transparent 50.4%),` +
    `linear-gradient(0deg,transparent 49.6%,${HAIRLINE} 49.6%,${HAIRLINE} 50.4%,transparent 50.4%);">` +
    quadrant("top:14px;left:18px", "Low maturity · high pressure — most urgent", true) +
    quadrant("top:14px;right:18px;text-align:right", "High maturity · high pressure") +
    quadrant("bottom:14px;left:18px", "Low maturity · low pressure") +
    quadrant("bottom:14px;right:18px;text-align:right", "High maturity · low pressure — healthiest") +
    bubbles +
    `</div>` +
    `<div style="margin:14px 0 18px;border-top:2px solid ${INK};">${legend}</div>`
  );
}

function memberLabel(member: Member): string {
  const name = `${member.company_name}${member.account_code ? ` (${member.account_code})` : ""}`;
  const fn = member.function_key ? ` / ${member.function_key}` : "";
  const stats = [
    member.avg_maturity != null ? `maturity ${member.avg_maturity.toFixed(1)}` : null,
    member.percentile_peer != null ? `${Math.round(member.percentile_peer)}th peer pct.` : null,
  ]
    .filter(Boolean)
    .join(", ");
  return `${name}${fn}${stats ? ` — ${stats}` : ""}`;
}

function scopeMarkdown(scope: Snapshot["scopes"][string]): string {
  const lines: string[] = [];
  if (scope.pressure.length) {
    lines.push("## Pressure ranking", "");
    scope.pressure.forEach((p) => lines.push(`- ${painLabel(p.slot_key)}: ${p.score.toFixed(1)}`));
    lines.push("");
  }
  for (const persona of scope.clusters) {
    lines.push(`## ${persona.label}`, "");
    const stats = [
      `${persona.size} member(s)`,
      persona.avg_maturity != null ? `average maturity ${persona.avg_maturity.toFixed(1)}/5` : null,
      persona.common_tech_stack?.length ? `common tools: ${persona.common_tech_stack.join(", ")}` : null,
    ]
      .filter(Boolean)
      .join(" · ");
    lines.push(stats, "");
    if (persona.summary) lines.push(persona.summary, "");
    if (persona.buying_persona) lines.push(persona.buying_persona, "");
    if (persona.members.length) {
      persona.members.forEach((m) => lines.push(`- ${memberLabel(m)}`));
      lines.push("");
    }
  }
  return lines.join("\n");
}

export async function GET(req: Request) {
  const token = new URL(req.url).searchParams.get("token");
  if (!token) {
    return Response.json({ detail: "missing admin token" }, { status: 400 });
  }
  const headers = { authorization: `Bearer ${token}` };
  const snapshotRes = await fetch(`${API_BASE}/admin/internal`, { headers, cache: "no-store" });
  if (!snapshotRes.ok) {
    return new Response(await snapshotRes.text(), {
      status: snapshotRes.status,
      headers: { "content-type": "application/json" },
    });
  }
  const snapshot = (await snapshotRes.json()) as Snapshot;
  const generated = snapshot.run
    ? `Run of ${new Date(snapshot.run.created_at).toLocaleString("en-US")}`
    : "No analytics run yet";

  const sections: { markdown: string; meta?: string; html?: string }[] = [
    {
      markdown: scopeMarkdown(snapshot.scopes.company),
      meta: generated,
      html: `<h1>Cohort personas — company grain</h1>${personaMapHtml(snapshot.scopes.company.clusters)}`,
    },
    {
      markdown: scopeMarkdown(snapshot.scopes.function),
      meta: generated,
      html: `<h1>Cohort personas — function grain</h1>${personaMapHtml(snapshot.scopes.function.clusters)}`,
    },
  ];
  const macroRes = await fetch(`${API_BASE}/reports/internal/latest`, { headers, cache: "no-store" });
  if (macroRes.ok) {
    const macro = (await macroRes.json()) as { rendered_md: string; created_at: string };
    sections.push({
      markdown: macro.rendered_md,
      meta: `Internal intelligence write-up · Generated ${new Date(macro.created_at).toLocaleString("en-US")}`,
    });
  }

  const html = renderPaginatedHtml("Internal Dashboard — Cohort View", sections);
  return new Response(html, {
    status: 200,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "content-disposition": 'attachment; filename="internal-dashboard.html"',
    },
  });
}
