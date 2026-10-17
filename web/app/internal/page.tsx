import InternalDashboard from "@/components/InternalDashboard";
import Chrome from "@/components/Chrome";
import { VENDOR_NAME } from "@/lib/branding";

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

// Internal destination: token-gated cohort god-view (brutalist system).
export default async function InternalPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const rawToken = params?.token;
  const token = Array.isArray(rawToken) ? rawToken[0] : rawToken;

  return (
    <Chrome
      active="Internal"
      restricted
      breadcrumb="Hub / Internal / Cohort Intelligence"
      context="Internal Only"
      footerLeft={token ? VENDOR_NAME : undefined}
      footerRight={token ? "Internal Only — Do Not Distribute" : undefined}
    >
      {token ? <InternalDashboard token={token} /> : <TokenGate />}
    </Chrome>
  );
}

function TokenGate() {
  return (
    <section style={{ padding: "96px 0 120px" }}>
      <div className="kicker-solo" style={{ marginBottom: 22 }}>Internal</div>
      <h1
        style={{
          margin: 0,
          fontWeight: 900,
          fontSize: "clamp(48px, 8vw, 128px)",
          lineHeight: 0.9,
          letterSpacing: "-0.035em",
          textTransform: "uppercase",
        }}
      >
        Cohort
        <br />
        Intelligence
      </h1>
      <p style={{ margin: "36px 0 40px", maxWidth: 520, fontSize: 19, lineHeight: 1.5, color: "#333" }}>
        Enter the admin token to open the internal dashboard.
      </p>
      <form
        action="/internal"
        style={{ display: "flex", flexWrap: "wrap", alignItems: "stretch", maxWidth: 680, border: "2px solid var(--ink)" }}
      >
        <input
          name="token"
          type="password"
          placeholder="Admin token"
          aria-label="Admin token"
          style={{
            flex: "1 1 320px",
            minWidth: 0,
            border: "none",
            outline: "none",
            background: "transparent",
            padding: "22px 24px",
            fontFamily: "var(--font-mono)",
            fontSize: 15,
            letterSpacing: "0.08em",
            color: "var(--ink)",
          }}
        />
        <button
          type="submit"
          style={{
            flex: "0 0 auto",
            border: "none",
            borderLeft: "2px solid var(--ink)",
            cursor: "pointer",
            background: "var(--accent)",
            color: "#fff",
            padding: "22px 32px",
            fontFamily: "var(--font-mono)",
            fontWeight: 700,
            fontSize: 14,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}
        >
          Open dashboard →
        </button>
      </form>
    </section>
  );
}
