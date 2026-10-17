export default function ProgressIndicator({
  filled,
  total,
}: {
  filled: number;
  total: number;
}) {
  const pct = total > 0 ? Math.round((filled / total) * 100) : 0;
  return (
    <section aria-label="coverage progress" style={{ border: "2px solid var(--ink)", padding: "20px 24px", marginBottom: 18 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 10 }}>
        <span className="mono-label" style={{ letterSpacing: "0.1em" }}>Coverage</span>
        <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: 13 }}>
          {filled} / {total} slots&nbsp;&nbsp;·&nbsp;&nbsp;{pct}%
        </span>
      </div>
      <div className="meter">
        <div style={{ width: `${pct}%` }} />
      </div>
    </section>
  );
}
