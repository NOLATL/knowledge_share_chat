import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import InternalDashboard from "./InternalDashboard";

afterEach(() => {
  vi.restoreAllMocks();
});

const snapshot = {
  run: { id: "run1", n_clusters: 2, silhouette_score: 0.37, created_at: "2026-07-01T12:00:00Z" },
  scopes: {
    company: {
      clusters: [
        {
          id: "p1",
          label: "Strategic CFOs in Growth Mode",
          size: 24,
          avg_maturity: 2.4,
          common_pain_points: [{ slot_key: "pain.manual_hours", score: 200 }],
          common_tech_stack: ["excel"],
          summary: "The big pressured group.",
          buying_persona: "CFO buyers.",
          members: [
            {
              company_id: "c1",
              company_name: "Foxglove",
              account_code: "C-00135",
              function_key: "FP&A",
              avg_maturity: 2.4,
              percentile_cohort: 40,
              percentile_peer: 8,
              umap_x: 0,
              umap_y: 0,
            },
          ],
        },
        {
          id: "p2",
          label: "Strategic FP&A Directors",
          size: 7,
          avg_maturity: 4.0,
          common_pain_points: [{ slot_key: "pain.audit_burden", score: 20 }],
          common_tech_stack: ["sql"],
          summary: "The mature group.",
          buying_persona: "Director buyers.",
          members: [],
        },
      ],
      pressure: [{ slot_key: "pain.manual_hours", score: 220 }],
    },
    function: { clusters: [], pressure: [] },
  },
};

function stubFetch() {
  const fetchMock = vi.fn().mockImplementation((url: RequestInfo | URL) => {
    const path = String(url);
    if (path.startsWith("/api/admin/internal")) return Promise.resolve(Response.json(snapshot));
    if (path.startsWith("/api/admin/reports/internal")) {
      return Promise.resolve(new Response(JSON.stringify({ detail: "not found" }), { status: 404 }));
    }
    return Promise.resolve(new Response(JSON.stringify({ detail: "not found" }), { status: 404 }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("InternalDashboard", () => {
  it("shows legend priority tags and reveals the detail card only on selection", async () => {
    stubFetch();
    render(<InternalDashboard token="secret" />);

    // Legend rows: numbered swatch + label + stat + priority tag. No detail card yet.
    expect((await screen.findAllByText("Strategic CFOs in Growth Mode")).length).toBeGreaterThan(0);
    expect(screen.getByText("Most urgent")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.queryByText(/Largest group/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Persona detail")).not.toBeInTheDocument();

    // Companies is the default grain; pressure ranking starts unfiltered.
    expect(screen.getByText("Pressure ranking (company grain) — All")).toBeInTheDocument();

    // Clicking a legend row opens the in-depth card (takeaway sentence lives
    // there) with member chips, and filters the pressure ranking.
    fireEvent.click(screen.getAllByRole("button", { name: /Strategic CFOs in Growth Mode/ })[0]);
    expect(screen.getByLabelText("Persona detail")).toBeInTheDocument();
    expect(screen.getByText(/Largest group/)).toBeInTheDocument();
    expect(screen.getByText("The big pressured group.")).toBeInTheDocument();
    // Clicking a member chip opens the drill-down (client write-up) with a
    // button through to the company's external site in a new tab.
    fireEvent.click(screen.getByRole("button", { name: /Foxglove \(C-00135\) \/ FP&A/ }));
    expect(screen.getByLabelText("Member drill-down")).toBeInTheDocument();
    const externalLink = screen.getByRole("link", { name: /Open external view/ });
    expect(externalLink).toHaveAttribute("href", "/external/c1");
    expect(externalLink).toHaveAttribute("target", "_blank");
    expect(await screen.findByText("No account intel generated yet.")).toBeInTheDocument();
    expect(
      screen.getByText("Pressure ranking (company grain) — Strategic CFOs in Growth Mode"),
    ).toBeInTheDocument();

    // The dropdown reflects and drives the same selection.
    const dropdown = screen.getByLabelText("Drill into a persona") as HTMLSelectElement;
    expect(dropdown.value).toBe("p1");
    fireEvent.change(dropdown, { target: { value: "p2" } });
    expect(screen.getByText("The mature group.")).toBeInTheDocument();
    fireEvent.change(dropdown, { target: { value: "" } });
    expect(screen.queryByLabelText("Persona detail")).not.toBeInTheDocument();
    expect(screen.getByText("Pressure ranking (company grain) — All")).toBeInTheDocument();
  });

  it("renders one write-up section and no duplicate intelligence panel", async () => {
    stubFetch();
    render(<InternalDashboard token="secret" />);

    expect(await screen.findByLabelText("Internal intelligence write-up")).toBeInTheDocument();
    expect(screen.queryByText(/^Internal intelligence \(.+ only\)$/)).not.toBeInTheDocument();
    expect(await screen.findByText(/No write-up generated yet/)).toBeInTheDocument();
    // Recompute is the only action — no per-section generate/HTML controls.
    expect(screen.queryByRole("button", { name: /^(Generate|Regenerate)$/ })).not.toBeInTheDocument();
    expect(screen.queryByText("Open as HTML")).not.toBeInTheDocument();
  });
});
