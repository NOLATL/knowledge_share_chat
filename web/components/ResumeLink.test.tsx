import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ResumeLink from "./ResumeLink";

describe("ResumeLink", () => {
  it("renders a resume link and copy button", () => {
    render(<ResumeLink token="abc-123" />);
    expect(screen.getByRole("button", { name: "Copy resume link" })).toBeInTheDocument();
    expect(screen.getByRole("link").getAttribute("href")).toBe("/session/abc-123");
  });

  it("shows feedback after clicking copy", async () => {
    render(<ResumeLink token="abc-123" />);
    fireEvent.click(screen.getByRole("button", { name: "Copy resume link" }));
    expect(await screen.findByRole("button", { name: "Copied!" })).toBeInTheDocument();
  });
});
