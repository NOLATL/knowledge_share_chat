import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ProgressIndicator from "./ProgressIndicator";

describe("ProgressIndicator", () => {
  it("shows filled/total and percent", () => {
    render(<ProgressIndicator filled={3} total={12} />);
    expect(screen.getByText(/3 \/ 12 slots/)).toBeInTheDocument();
    expect(screen.getByText(/25%/)).toBeInTheDocument();
  });

  it("handles zero total without dividing by zero", () => {
    render(<ProgressIndicator filled={0} total={0} />);
    expect(screen.getByText(/0 \/ 0 slots/)).toBeInTheDocument();
    expect(screen.getByText(/0%/)).toBeInTheDocument();
  });
});
