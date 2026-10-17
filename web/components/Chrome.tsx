import Link from "next/link";
import type { ReactNode } from "react";

// Persistent page chrome (Spec_FrontEnd_Design): header bar with wordmark +
// mono nav, thin meta strip (breadcrumb / status), content shell, footer.

const NAV = [
  { label: "Hub", href: "/hub" },
  { label: "Chat", href: "/" },
  { label: "External", href: "/external" },
  { label: "Internal", href: "/internal" },
];

export default function Chrome({
  active,
  breadcrumb,
  context,
  restricted = false,
  maxWidth = 1440,
  footerLeft,
  footerRight,
  children,
}: {
  active?: "Hub" | "Chat" | "External" | "Internal";
  breadcrumb: ReactNode;
  context: string;
  restricted?: boolean;
  maxWidth?: number;
  footerLeft?: ReactNode;
  footerRight?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div style={{ minHeight: "100vh" }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "22px 40px",
          borderBottom: "2px solid var(--ink)",
        }}
      >
        <Link href="/hub" style={{ display: "flex", alignItems: "center", gap: 12, textDecoration: "none", color: "var(--ink)" }}>
          <span style={{ width: 12, height: 12, background: "var(--accent)", display: "inline-block" }} />
          <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 15, letterSpacing: "0.22em" }}>
            PLAYBOOK
          </span>
        </Link>
        <nav
          style={{
            display: "flex",
            alignItems: "center",
            gap: 28,
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}
        >
          {restricted && <span className="tag tag--accent" style={{ fontSize: 11, padding: "5px 9px" }}>● Restricted</span>}
          {NAV.map((item) =>
            item.label === active ? (
              <span key={item.label} style={{ color: "var(--accent)", borderBottom: "2px solid var(--accent)" }}>
                {item.label}
              </span>
            ) : (
              <Link key={item.label} href={item.href} style={{ color: "var(--ink)", textDecoration: "none" }}>
                {item.label}
              </Link>
            ),
          )}
        </nav>
      </header>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 40px",
          borderBottom: "2px solid var(--ink)",
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          color: "#555",
        }}
      >
        <span>{breadcrumb}</span>
        <span style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--ink)" }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--accent)", display: "inline-block" }} />
          {context}
        </span>
      </div>

      <main style={{ maxWidth, margin: "0 auto", padding: "0 40px" }}>
        {children}
        {(footerLeft || footerRight) && (
          <footer
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 16,
              justifyContent: "space-between",
              padding: "28px 0 48px",
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "#666",
            }}
          >
            <span>{footerLeft}</span>
            <span>{footerRight}</span>
          </footer>
        )}
      </main>
    </div>
  );
}
