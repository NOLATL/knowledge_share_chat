import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import CohortMap, { type MapPoint } from "./CohortMap";

const points: MapPoint[] = [
  { maturity: 3.6, pain_load: 5.2, persona: "Finance Systems Optimizers", is_self: true },
  { maturity: 2.4, pain_load: 12.1, persona: "Manual-heavy controllers", is_self: false },
  { maturity: 4.2, pain_load: 3.0, persona: "Finance Systems Optimizers", is_self: false },
  { maturity: 3.0, pain_load: 6.0, persona: null, is_self: false },
];

describe("CohortMap", () => {
  it("renders a bubble per peer, a + for the selected firm, and a persona legend", () => {
    const { container } = render(
      <CohortMap points={points} selfLabel="Foxglove" title="Cohort chart" cohortNoun="a company in your cohort" />,
    );

    // Peers are circles; the selected firm is a plus (lines), labeled by name.
    expect(container.querySelectorAll("circle")).toHaveLength(3);
    expect(screen.getAllByText("Foxglove").length).toBeGreaterThan(0);

    // Legend: persona colors + the unclustered bucket + marker/size notes.
    expect(screen.getByText("Finance Systems Optimizers")).toBeInTheDocument();
    expect(screen.getByText("Manual-heavy controllers")).toBeInTheDocument();
    expect(screen.getByText("No persona yet")).toBeInTheDocument();
    expect(screen.getByText(/size = maturity/)).toBeInTheDocument();

    // Interpretation ships with the chart.
    expect(screen.getByText(/How to read this/)).toBeInTheDocument();
    expect(screen.getByText(/median position/)).toBeInTheDocument();
  });

  it("falls back to an empty state without points", () => {
    render(<CohortMap points={[]} selfLabel="Foxglove" title="Cohort chart" cohortNoun="a company" />);
    expect(screen.getByText(/appears after the next analytics recompute/)).toBeInTheDocument();
  });
});
