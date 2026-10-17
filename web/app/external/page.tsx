"use client";

// External destination index: pick a company, open its deliverable view.
import { useEffect, useState } from "react";
import Link from "next/link";

import Chrome from "@/components/Chrome";

type Company = {
  id: string;
  account_code: string;
  name: string;
  industry: string | null;
  respondent_count: number;
  has_real_respondents: boolean;
  avg_maturity: number | null;
  percentile_peer: number | null;
};

function ordinal(n: number | null): string {
  if (n == null) return "—";
  const rounded = Math.round(n);
  const s = ["th", "st", "nd", "rd"];
  const v = rounded % 100;
  return rounded + (s[(v - 20) % 10] || s[v] || s[0]);
}

export default function ExternalIndexPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [includeSynthetic, setIncludeSynthetic] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    fetch(`/api/companies?includeSynthetic=${includeSynthetic}`)
      .then((r) => r.json())
      .then((d: Company[]) => setCompanies(d))
      .catch(() => setCompanies([]));
  }, [includeSynthetic]);

  const lowered = query.trim().toLowerCase();
  const visible = lowered
    ? companies.filter((c) =>
        [c.name, c.account_code, c.industry ?? ""].some((v) => v.toLowerCase().includes(lowered)),
      )
    : companies;

  return (
    <Chrome
      active="External"
      breadcrumb={
        <>
          <Link href="/hub" style={{ color: "#555", textDecoration: "none" }}>Hub</Link> / External / Deliverables
        </>
      }
      context="Company-Facing"
      footerLeft={<Link href="/hub" style={{ color: "#666", textDecoration: "none" }}>← Back to Hub</Link>}
      footerRight="Vendor-Agnostic — Safe to Share"
    >
      <section style={{ padding: "64px 0 40px", borderBottom: "2px solid var(--ink)" }}>
        <div className="kicker" style={{ marginBottom: 26 }}>
          <b>[ 01 ]</b>
          <span style={{ color: "#444" }}>Executive rollup &amp; per-function breakdowns</span>
        </div>
        <h1
          style={{
            margin: 0,
            fontWeight: 900,
            fontSize: "clamp(48px, 8vw, 130px)",
            lineHeight: 0.9,
            letterSpacing: "-0.035em",
            textTransform: "uppercase",
          }}
        >
          External
          <br />
          Deliverables
        </h1>
        <p style={{ margin: "40px 0 0", maxWidth: 620, fontSize: 19, lineHeight: 1.5, color: "#333" }}>
          Company-facing view. Every discovery session becomes an executive rollup plus a roadmap for
          each business function — benchmarked against peers, downloadable, safe to share.
        </p>
      </section>

      <section
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "stretch",
          borderLeft: "2px solid var(--ink)",
          borderRight: "2px solid var(--ink)",
          borderBottom: "2px solid var(--ink)",
        }}
      >
        <div style={{ flex: "1 1 320px", display: "flex", alignItems: "center", gap: 14, padding: "18px 24px", borderRight: "2px solid var(--ink)" }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 15, color: "#999" }}>⌕</span>
          <input
            type="text"
            aria-label="Filter companies"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by name, code, or industry…"
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              fontFamily: "var(--font-mono)",
              fontSize: 14,
              color: "var(--ink)",
              letterSpacing: "0.02em",
            }}
          />
        </div>
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "18px 24px",
            cursor: "pointer",
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "var(--ink)",
          }}
        >
          <input
            type="checkbox"
            checked={includeSynthetic}
            onChange={(e) => setIncludeSynthetic(e.target.checked)}
            style={{ width: 16, height: 16, accentColor: "var(--accent)" }}
          />
          Include synthetic companies
        </label>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            padding: "18px 24px",
            borderLeft: "2px solid var(--ink)",
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "#666",
            marginLeft: "auto",
          }}
        >
          {visible.length} Companies
        </div>
      </section>

      <section style={{ borderLeft: "2px solid var(--ink)", borderRight: "2px solid var(--ink)" }}>
        {visible.map((co) => {
          const meta = [
            co.industry,
            `${co.respondent_count} respondent${co.respondent_count === 1 ? "" : "s"}`,
            co.avg_maturity != null ? `maturity ${co.avg_maturity.toFixed(1)}/5` : null,
            co.percentile_peer != null ? `${ordinal(co.percentile_peer)} peer pct.` : null,
          ]
            .filter(Boolean)
            .join("  ·  ");
          return (
            <Link
              key={co.id}
              href={`/external/${co.id}`}
              className="row-slide"
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(0,1fr) 200px 130px 40px",
                alignItems: "center",
                gap: 24,
                padding: "26px 28px",
                textDecoration: "none",
                color: "var(--ink)",
                borderBottom: "2px solid var(--ink)",
                background: "var(--paper)",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
                  <span style={{ fontWeight: 800, fontSize: "clamp(20px, 2.2vw, 30px)", letterSpacing: "-0.01em" }}>
                    {co.name}
                  </span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--accent)", letterSpacing: "0.08em" }}>
                    {co.account_code}
                  </span>
                </div>
                <div
                  style={{
                    marginTop: 7,
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: "#777",
                  }}
                >
                  {meta}
                </div>
              </div>
              <div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    justifyContent: "space-between",
                    marginBottom: 6,
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    color: "#999",
                  }}
                >
                  <span>Maturity</span>
                  <span style={{ color: "var(--ink)", fontWeight: 700 }}>
                    {co.avg_maturity != null ? `${co.avg_maturity.toFixed(1)}/5` : "—"}
                  </span>
                </div>
                <div className="meter meter--thin">
                  <div style={{ width: co.avg_maturity != null ? `${Math.round((co.avg_maturity / 5) * 100)}%` : "0%" }} />
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 22, lineHeight: 1 }}>
                  {ordinal(co.percentile_peer)}
                </div>
                <div
                  style={{
                    marginTop: 4,
                    fontFamily: "var(--font-mono)",
                    fontSize: 9,
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    color: "#999",
                  }}
                >
                  Peer pct.
                </div>
              </div>
              <span style={{ justifySelf: "end", color: "var(--accent)", fontSize: 22 }}>→</span>
            </Link>
          );
        })}
        {!visible.length && (
          <p
            style={{
              margin: 0,
              padding: "26px 28px",
              borderBottom: "2px solid var(--ink)",
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "#777",
            }}
          >
            No companies match.
          </p>
        )}
      </section>
    </Chrome>
  );
}
