import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// ChatApp uses useChat + fetch on mount; mock it so the page test stays a unit.
vi.mock("@/components/ChatApp", () => ({ default: () => <div data-testid="chatapp" /> }));

import Home from "./page";

describe("Home page", () => {
  it("renders the chrome and mounts the chat", () => {
    render(<Home />);
    expect(screen.getByText("PLAYBOOK")).toBeInTheDocument();
    expect(screen.getByText("Hub / Chat / Discovery")).toBeInTheDocument();
    expect(screen.getByTestId("chatapp")).toBeInTheDocument();
  });
});
