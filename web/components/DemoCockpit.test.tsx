import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DemoCockpit from "./DemoCockpit";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DemoCockpit", () => {
  it("loads demo readiness and links into the selected session flow", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        session: {
          id: "s1",
          status: "in_progress",
          resume_token: "resume-1",
          current_slot: "close.days",
          respondent_id: "r1",
          respondent_name: "Jordan",
          role: "Controller",
          email: "jordan@example.com",
          source: "real",
          company_name: "Demo Co",
          company_id: "c1",
        },
        coverage: { filled_must_fill: 4, total_must_fill: 14, complete_ready: false },
        documents: { total: 1, parsed: 1, pending: 0, error: 0 },
        relays: { total: 1, sent: 0, answered: 1, expired: 0 },
        reports: {
          prospect: { id: "p1", created_at: "2026-06-30T12:00:00Z" },
          vendor: null,
        },
        analytics: {
          latest_run: { id: "run1", n_clusters: 6, silhouette_score: 0.37, created_at: "2026-06-30T12:00:00Z" },
          benchmark: {
            id: "b1",
            cluster_label: "Demo Controllers",
            maturity_score: 3.4,
            percentile_cohort: 72,
            percentile_cluster: 61,
            computed_at: "2026-06-30T12:00:00Z",
          },
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<DemoCockpit initialSessionId="s1" initialToken="secret" />);

    expect(await screen.findByText("Demo Co")).toBeInTheDocument();
    expect(screen.getByText("4/14")).toBeInTheDocument();
    expect(screen.getByText("72%")).toBeInTheDocument();
    const targets = screen.getAllByRole("link", { name: "Open" }).map((link) => link.getAttribute("href"));
    expect(targets).toContain("/session/resume-1");
    expect(targets).toContain("/external/c1");
    expect(targets).toContain("/internal?token=secret");
    expect(fetchMock).toHaveBeenCalledWith("/api/admin/demo?token=secret&sessionId=s1");
  });

  it("stays idle until token and session are entered", async () => {
    render(<DemoCockpit />);

    expect(screen.getByText("Enter a session id and admin token to load demo readiness.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load demo" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Session id"), { target: { value: "s1" } });
    fireEvent.change(screen.getByLabelText("Admin token"), { target: { value: "secret" } });

    await waitFor(() => expect(screen.getByRole("button", { name: "Load demo" })).not.toBeDisabled());
  });
});
