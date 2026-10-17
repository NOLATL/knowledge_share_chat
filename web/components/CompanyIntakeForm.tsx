"use client";

import { useState } from "react";

// Firmographics captured before the chat so analytics is company-centric.
// Bands are coarse on purpose — peer benchmarking groups on industry + size.
const HEADCOUNT_BANDS = ["1-50", "51-200", "201-1000", "1000+"];
const REVENUE_BANDS = ["<$10M", "$10-50M", "$50-250M", "$250M-1B", ">$1B"];
// Mirrors the synthetic-cohort industry pool (playbook_shared/analytics/synthetic.py)
// so real companies land in populated peer groups; free text still allowed.
const INDUSTRY_SUGGESTIONS = [
  "Manufacturing",
  "Software & SaaS",
  "Retail & E-commerce",
  "Healthcare",
  "Logistics & Transportation",
  "Financial Services",
  "Business Services",
];
// The business function this discovery covers — the user-facing analytics grain.
// Free text still allowed; suggestions keep answers consistent for roll-up.
const FUNCTION_SUGGESTIONS = [
  "Accounting / Controllership",
  "Financial Planning & Analysis (FP&A)",
  "Treasury",
  "Tax",
  "Accounts Payable",
  "Accounts Receivable",
  "Financial Systems / IT",
  "Audit & Compliance",
  "Office of the CFO",
];

export type CompanyIntake = {
  name: string;
  industry?: string;
  headcount_band?: string;
  revenue_band?: string;
  years_in_business?: number;
  respondent_name?: string;
  respondent_role?: string;
  respondent_email?: string;
  function_key?: string;
};

export default function CompanyIntakeForm({ onSubmit }: { onSubmit: (intake: CompanyIntake) => void }) {
  const [f, setF] = useState<CompanyIntake>({ name: "" });
  const set = (k: keyof CompanyIntake) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setF((prev) => ({ ...prev, [k]: e.target.value }));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!f.name.trim()) return;
    const years = f.years_in_business ? Number(f.years_in_business) : undefined;
    onSubmit({ ...f, name: f.name.trim(), years_in_business: Number.isFinite(years) ? years : undefined });
  };

  return (
    <form onSubmit={submit}>
      <p style={{ margin: "0 0 24px", fontSize: 15, color: "#666" }}>
        Tell us about your company so we can benchmark you against peers.
      </p>

      <section style={{ border: "2px solid var(--ink)", marginBottom: 48 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr" }}>
          <Cell label="Company name" required right divider>
            <input
              aria-label="Company name"
              className="line-input"
              required
              placeholder="Acme Financial"
              value={f.name}
              onChange={set("name")}
            />
          </Cell>
          <Cell label="Industry" divider>
            <input
              aria-label="Industry"
              className="line-input"
              list="industry-suggestions"
              placeholder="Software & SaaS"
              value={f.industry ?? ""}
              onChange={set("industry")}
            />
            <datalist id="industry-suggestions">
              {INDUSTRY_SUGGESTIONS.map((industry) => (
                <option key={industry} value={industry} />
              ))}
            </datalist>
          </Cell>
          <Cell label="Headcount" right divider>
            <BandSelect aria="Headcount" value={f.headcount_band ?? ""} onChange={set("headcount_band")} options={HEADCOUNT_BANDS} />
          </Cell>
          <Cell label="Annual revenue" divider>
            <BandSelect aria="Annual revenue" value={f.revenue_band ?? ""} onChange={set("revenue_band")} options={REVENUE_BANDS} />
          </Cell>
          <Cell label="Years in business" right divider>
            <input
              aria-label="Years in business"
              className="line-input"
              type="number"
              min={0}
              placeholder="8"
              value={f.years_in_business ?? ""}
              onChange={set("years_in_business")}
            />
          </Cell>
          <Cell label="Function you cover" divider>
            <input
              aria-label="Function"
              className="line-input"
              list="function-suggestions"
              placeholder="Controllership"
              value={f.function_key ?? ""}
              onChange={set("function_key")}
            />
            <datalist id="function-suggestions">
              {FUNCTION_SUGGESTIONS.map((fn) => (
                <option key={fn} value={fn} />
              ))}
            </datalist>
          </Cell>
          <Cell label="Your name" right divider>
            <input
              aria-label="Your name"
              className="line-input"
              placeholder="Jordan Lee"
              value={f.respondent_name ?? ""}
              onChange={set("respondent_name")}
            />
          </Cell>
          <Cell label="Your role" divider>
            <input
              aria-label="Your role"
              className="line-input"
              placeholder="VP Finance"
              value={f.respondent_role ?? ""}
              onChange={set("respondent_role")}
            />
          </Cell>
          <Cell label="Your email" right>
            <input
              aria-label="Your email"
              className="line-input"
              type="email"
              placeholder="jordan@acme.com"
              value={f.respondent_email ?? ""}
              onChange={set("respondent_email")}
            />
          </Cell>
        </div>
      </section>

      <section style={{ paddingBottom: 56 }}>
        <button type="submit" className="hard-btn" style={{ fontSize: 15, letterSpacing: "0.12em", padding: "20px 32px" }}>
          Begin discovery session <span style={{ fontSize: 18 }}>→</span>
        </button>
      </section>
    </form>
  );
}

function Cell({
  label,
  required = false,
  right = false,
  divider = false,
  children,
}: {
  label: string;
  required?: boolean;
  right?: boolean;
  divider?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label
      style={{
        display: "flex",
        flexDirection: "column",
        padding: "22px 24px",
        borderRight: right ? "2px solid var(--ink)" : undefined,
        borderBottom: divider ? "2px solid var(--ink)" : undefined,
      }}
    >
      <span className="mono-label" style={{ marginBottom: 10 }}>
        {label} {required && <span style={{ color: "var(--accent)" }}>*</span>}
      </span>
      {children}
    </label>
  );
}

function BandSelect({
  aria,
  value,
  onChange,
  options,
}: {
  aria: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  options: string[];
}) {
  return (
    <div style={{ position: "relative" }}>
      <select
        aria-label={aria}
        className="line-input"
        value={value}
        onChange={onChange}
        // Gray placeholder text until a real option is chosen (per the mock).
        style={{ cursor: "pointer", color: value ? "var(--ink)" : "#999" }}
      >
        <option value="" disabled>
          Select…
        </option>
        {options.map((b) => (
          <option key={b} value={b}>
            {b}
          </option>
        ))}
      </select>
      <span style={{ position: "absolute", right: 2, top: 10, color: "var(--accent)", pointerEvents: "none" }}>▾</span>
    </div>
  );
}
