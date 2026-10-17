"use client";

// External evaluation chart: one bubble per cohort member (company grain) or
// per same-function team at another company (function grain). Color = persona,
// bubble size = maturity, the selected firm renders as a "+" at the same
// maturity sizing. Anonymized — only the selected firm is named.

import { useMemo, useState } from "react";

export type MapPoint = {
  maturity: number | null;
  pain_load: number;
  persona: string | null;
  is_self: boolean;
};

const WIDTH = 760;
const HEIGHT = 400;
const PAD = 46;
// Persona palette for the external cohort chart (accent-first, then flat
// editorial tones that hold up on the warm paper background).
const COLORS = ["#E01B13", "#0A0A0A", "#1B44E0", "#4D7C0F", "#7C3AED", "#A16207", "#0369A1", "#9A968B"];
const UNCLUSTERED = "#9ca3af";

export default function CohortMap({
  points,
  selfLabel,
  title,
  cohortNoun,
}: {
  points: MapPoint[];
  selfLabel: string;
  title: string;
  // What one bubble is, e.g. "a company in your cohort" / "this function at another company".
  cohortNoun: string;
}) {
  const [hovered, setHovered] = useState<MapPoint | null>(null);

  const plotted = points.filter((p) => p.maturity != null);
  const self = plotted.find((p) => p.is_self) ?? null;
  const maxPain = Math.max(1, ...plotted.map((p) => p.pain_load));

  // Persona -> color, most common persona first so colors are stable-ish.
  const personaColor = useMemo(() => {
    const counts = new Map<string, number>();
    for (const p of plotted) {
      if (p.persona) counts.set(p.persona, (counts.get(p.persona) ?? 0) + 1);
    }
    const ordered = [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([label]) => label);
    return new Map(ordered.map((label, i) => [label, COLORS[i % COLORS.length]]));
  }, [plotted]);

  const x = (maturity: number) => PAD + ((maturity - 1) / 4) * (WIDTH - 2 * PAD);
  const y = (pain: number) => HEIGHT - PAD - (pain / maxPain) * (HEIGHT - 2 * PAD);
  const r = (maturity: number) => 5 + ((maturity - 1) / 4) * 13;
  const colorOf = (p: MapPoint) => (p.persona ? personaColor.get(p.persona) ?? UNCLUSTERED : UNCLUSTERED);

  const insights = useMemo(() => buildInsights(plotted, self, selfLabel), [plotted, self, selfLabel]);

  if (!plotted.length) {
    return (
      <section style={panel} aria-label={title}>
        <h2 style={h2}>{title}</h2>
        <p style={muted}>The chart appears after the next analytics recompute.</p>
      </section>
    );
  }

  return (
    <section style={panel} aria-label={title}>
      <h2 style={h2}>{title}</h2>
      <p style={{ ...muted, margin: "0 0 4px", fontSize: 14 }}>
        <strong>How to read this:</strong> each bubble is {cohortNoun}, colored by its persona and
        sized by maturity. Right = more mature operations; higher = more pressure (weighted pain).
        The best position is bottom-right. The <strong>+</strong> is {selfLabel}.
      </p>

      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`${title}: maturity vs pressure`}
        style={{ display: "block", width: "100%", height: "auto" }}
        onMouseLeave={() => setHovered(null)}
      >
        <rect x={0} y={0} width={WIDTH} height={HEIGHT} fill="var(--paper-alt)" stroke="var(--ink)" strokeWidth={2} />
        <line x1={x(3)} y1={PAD - 8} x2={x(3)} y2={HEIGHT - PAD + 8} stroke="var(--hairline)" strokeDasharray="4 4" />
        <line x1={PAD - 8} y1={y(maxPain / 2)} x2={WIDTH - PAD + 8} y2={y(maxPain / 2)} stroke="var(--hairline)" strokeDasharray="4 4" />
        <QuadrantLabel xPos={PAD} yPos={PAD - 14} text="Low maturity · high pressure — most urgent" />
        <QuadrantLabel xPos={WIDTH - PAD} yPos={PAD - 14} text="High maturity · high pressure" anchor="end" />
        <QuadrantLabel xPos={PAD} yPos={HEIGHT - PAD + 26} text="Low maturity · low pressure" />
        <QuadrantLabel xPos={WIDTH - PAD} yPos={HEIGHT - PAD + 26} text="High maturity · low pressure — best position" anchor="end" />

        <text x={WIDTH / 2} y={HEIGHT - 8} textAnchor="middle" fontSize={12} fill="#666" fontFamily="var(--font-mono)">
          Maturity (1–5) →
        </text>
        <text
          x={12}
          y={HEIGHT / 2}
          textAnchor="middle"
          fontSize={12}
          fill="#666"
          fontFamily="var(--font-mono)"
          transform={`rotate(-90 12 ${HEIGHT / 2})`}
        >
          Pressure load →
        </text>

        {plotted
          .filter((p) => !p.is_self)
          .map((p, i) => (
            <circle
              key={i}
              cx={x(p.maturity as number)}
              cy={y(p.pain_load)}
              r={r(p.maturity as number)}
              fill={colorOf(p)}
              opacity={0.65}
              stroke="#fff"
              strokeWidth={1.5}
              onMouseEnter={() => setHovered(p)}
            >
              <title>{tooltip(p, cohortNoun)}</title>
            </circle>
          ))}

        {self && (
          <g onMouseEnter={() => setHovered(self)}>
            <PlusMark
              cx={x(self.maturity as number)}
              cy={y(self.pain_load)}
              arm={r(self.maturity as number) + 4}
              color={colorOf(self)}
            />
            <text
              x={x(self.maturity as number)}
              y={y(self.pain_load) - r(self.maturity as number) - 10}
              textAnchor="middle"
              fontSize={12}
              fontWeight={800}
              fill="var(--ink)"
            >
              {selfLabel}
            </text>
            <title>{tooltip(self, selfLabel)}</title>
          </g>
        )}
      </svg>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px 14px", margin: "12px 0 0", fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.05em", textTransform: "uppercase", color: "#555" }}>
        {[...personaColor.entries()].map(([label, color]) => (
          <span key={label} style={legendItem}>
            <i style={{ ...swatch, background: color }} />
            {label}
          </span>
        ))}
        {plotted.some((p) => !p.persona) && (
          <span style={legendItem}>
            <i style={{ ...swatch, background: UNCLUSTERED }} />
            No persona yet
          </span>
        )}
        <span style={legendItem}>
          <strong style={{ fontSize: 14, lineHeight: 1 }}>+</strong> {selfLabel}
        </span>
        <span style={legendItem}>◯ size = maturity</span>
      </div>

      {hovered && (
        <p style={{ ...muted, margin: "8px 0 0", fontSize: 13 }}>
          {hovered.is_self ? selfLabel : `A peer (${hovered.persona ?? "no persona yet"})`} — maturity{" "}
          {(hovered.maturity as number).toFixed(1)}/5, pressure {hovered.pain_load.toFixed(1)}
        </p>
      )}

      {insights.length > 0 && (
        <div style={{ marginTop: 14, padding: "14px 16px", background: "var(--paper)", border: "2px solid var(--ink)" }}>
          <strong style={{ fontFamily: "var(--font-mono)", fontSize: 12, letterSpacing: "0.14em", textTransform: "uppercase", color: "#777" }}>
            What this shows
          </strong>
          <ul style={{ margin: "6px 0 0 18px", padding: 0 }}>
            {insights.map((line) => (
              <li key={line} style={{ fontSize: 14, color: "#333", marginTop: 4 }}>
                {line}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function tooltip(p: MapPoint, who: string): string {
  return `${p.is_self ? who : p.persona ?? "No persona yet"} — maturity ${(p.maturity as number).toFixed(1)}/5, pressure ${p.pain_load.toFixed(1)}`;
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function buildInsights(points: MapPoint[], self: MapPoint | null, selfLabel: string): string[] {
  if (points.length < 2) return [];
  const insights: string[] = [];
  const medMaturity = median(points.map((p) => p.maturity as number));
  const medPain = median(points.map((p) => p.pain_load));
  insights.push(
    `The cohort's median position is maturity ${medMaturity.toFixed(1)}/5 with a pressure load of ${medPain.toFixed(1)}.`,
  );
  if (self?.maturity != null) {
    const m = self.maturity;
    insights.push(
      `${selfLabel} sits ${m >= medMaturity ? "at or above" : "below"} the cohort's median maturity and carries ${
        self.pain_load >= medPain ? "more" : "less"
      } pressure than the typical member — ${
        m >= medMaturity && self.pain_load < medPain
          ? "a strong position."
          : m < medMaturity && self.pain_load >= medPain
            ? "the group with the most to gain from acting now."
            : "a mixed position."
      }`,
    );
    if (self.persona) {
      const kin = points.filter((p) => !p.is_self && p.persona === self.persona).length;
      insights.push(`${selfLabel} shares the "${self.persona}" persona with ${kin} other member(s) of this cohort.`);
    }
  }
  return insights;
}

function PlusMark({ cx, cy, arm, color }: { cx: number; cy: number; arm: number; color: string }) {
  return (
    <g>
      <line x1={cx - arm} y1={cy} x2={cx + arm} y2={cy} stroke="#fff" strokeWidth={7} strokeLinecap="round" />
      <line x1={cx} y1={cy - arm} x2={cx} y2={cy + arm} stroke="#fff" strokeWidth={7} strokeLinecap="round" />
      <line x1={cx - arm} y1={cy} x2={cx + arm} y2={cy} stroke={color} strokeWidth={4} strokeLinecap="round" />
      <line x1={cx} y1={cy - arm} x2={cx} y2={cy + arm} stroke={color} strokeWidth={4} strokeLinecap="round" />
    </g>
  );
}

function QuadrantLabel({
  xPos,
  yPos,
  text,
  anchor = "start",
}: {
  xPos: number;
  yPos: number;
  text: string;
  anchor?: "start" | "end";
}) {
  return (
    <text x={xPos} y={yPos} textAnchor={anchor} fontSize={11} fontWeight={700} fill="#888" fontFamily="var(--font-mono)" letterSpacing="0.06em" style={{ textTransform: "uppercase" }}>
      {text}
    </text>
  );
}

const panel: React.CSSProperties = {
  background: "var(--paper)",
  border: "2px solid var(--ink)",
  padding: "26px 28px",
  marginBottom: 18,
};
const h2: React.CSSProperties = {
  margin: "0 0 8px",
  fontWeight: 800,
  fontSize: "clamp(20px, 2.2vw, 28px)",
  letterSpacing: "-0.02em",
};
const muted: React.CSSProperties = { color: "#666" };
const legendItem: React.CSSProperties = { display: "inline-flex", alignItems: "center", gap: 6 };
const swatch: React.CSSProperties = { width: 10, height: 10, borderRadius: "50%", border: "1px solid var(--ink)", display: "inline-block" };
