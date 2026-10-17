import Link from "next/link";

import Chrome from "@/components/Chrome";

// Landing page: two doors (External / Internal), brutalist system.
export default function HubPage() {
  return (
    <Chrome
      active="Hub"
      breadcrumb="Hub / Analytics & Deliverables"
      context="Presales Intelligence Engine"
      footerLeft="Playbook © 2026 — Presales Intelligence"
      footerRight="RAG Discovery → Two Surfaces"
    >
      <section style={{ padding: "72px 0 56px", borderBottom: "2px solid var(--ink)" }}>
        <div className="kicker" style={{ marginBottom: 30 }}>
          <b>[ 00 ]</b>
          <span style={{ color: "#444" }}>Everything discovery learns, delivered at two levels</span>
        </div>

        <h1
          style={{
            margin: 0,
            fontWeight: 900,
            fontSize: "clamp(52px, 9.5vw, 158px)",
            lineHeight: 0.9,
            letterSpacing: "-0.035em",
            textTransform: "uppercase",
          }}
        >
          Analytics <span style={{ color: "var(--accent)" }}>&amp;</span>
          <br />
          Deliverables
        </h1>

        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "flex-end",
            justifyContent: "space-between",
            gap: 40,
            marginTop: 48,
          }}
        >
          <p style={{ margin: 0, maxWidth: 560, fontSize: 20, lineHeight: 1.5, color: "#333" }}>
            A RAG-driven chatbot runs the discovery session with finance &amp; accounting teams. From
            that conversation, Playbook produces company and prospect analytics.
          </p>
          <Link href="/" className="hard-btn" style={{ flexShrink: 0 }}>
            Start a discovery session <span style={{ fontSize: 18 }}>→</span>
          </Link>
        </div>
      </section>

      <section
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          borderLeft: "2px solid var(--ink)",
          borderRight: "2px solid var(--ink)",
        }}
      >
        <HubCard
          href="/external"
          index="01"
          tag="Shareable"
          title="External"
          description="The company-facing deliverable: an executive rollup plus a roadmap for each business function, benchmarked against peers. Viewable in-browser and downloadable per function or as one paginated document. Vendor-agnostic — safe to share."
          cta="Open external deliverables"
        />
        <HubCard
          href="/internal"
          index="02"
          tag="Internal Use"
          title="Internal"
          description="Cohort intelligence for the room only: function and company personas with named-member drill-down, account intel with product fit, pressure rankings, the positioning map, and the macro write-up with the investor narrative. Admin token required."
          cta="Open internal dashboard"
          divider
        />
      </section>
    </Chrome>
  );
}

function HubCard({
  href,
  index,
  tag,
  title,
  description,
  cta,
  divider = false,
}: {
  href: string;
  index: string;
  tag: string;
  title: string;
  description: string;
  cta: string;
  divider?: boolean;
}) {
  return (
    <Link
      href={href}
      className="hover-fill"
      style={{
        display: "flex",
        flexDirection: "column",
        padding: 44,
        textDecoration: "none",
        color: "var(--ink)",
        borderBottom: "2px solid var(--ink)",
        borderLeft: divider ? "2px solid var(--ink)" : undefined,
        background: "var(--paper)",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 40 }}>
        <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 56, lineHeight: 1 }}>{index}</span>
        <span className="tag">{tag}</span>
      </div>
      <h2
        style={{
          margin: "0 0 18px",
          fontWeight: 900,
          fontSize: "clamp(38px, 4.6vw, 64px)",
          lineHeight: 0.92,
          letterSpacing: "-0.02em",
          textTransform: "uppercase",
        }}
      >
        {title}
      </h2>
      <p style={{ margin: "0 0 28px", fontSize: 16, lineHeight: 1.55, color: "#444" }}>{description}</p>
      <div
        style={{
          marginTop: "auto",
          display: "flex",
          alignItems: "center",
          gap: 12,
          fontFamily: "var(--font-mono)",
          fontWeight: 700,
          fontSize: 13,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--accent)",
        }}
      >
        {cta} <span style={{ fontSize: 18 }}>→</span>
      </div>
    </Link>
  );
}
