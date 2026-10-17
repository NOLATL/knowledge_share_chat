import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ShareQuestion from "./ShareQuestion";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ShareQuestion", () => {
  it("sends the current question and reports the email back", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      Response.json({ relay_url: "https://web.example/relay/t1", email_delivered: true }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const onSent = vi.fn();

    render(<ShareQuestion sessionId="s1" onSent={onSent} />);

    fireEvent.click(screen.getByRole("button", { name: "Share this question by email" }));
    fireEvent.change(screen.getByLabelText("Colleague email"), {
      target: { value: "peer@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(onSent).toHaveBeenCalledWith("peer@example.com"));
    expect(fetchMock).toHaveBeenCalledWith("/api/relays", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ sessionId: "s1", sentToEmail: "peer@example.com" }),
    });
    // Form collapses after a successful send.
    expect(screen.queryByLabelText("Colleague email")).not.toBeInTheDocument();
  });

  it("shows the API error and keeps the form open on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(Response.json({ detail: "no unfilled question available to share" }, { status: 400 })),
    );
    const onSent = vi.fn();

    render(<ShareQuestion sessionId="s1" onSent={onSent} />);

    fireEvent.click(screen.getByRole("button", { name: "Share this question by email" }));
    fireEvent.change(screen.getByLabelText("Colleague email"), {
      target: { value: "peer@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("no unfilled question available to share")).toBeInTheDocument();
    expect(onSent).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Colleague email")).toBeInTheDocument();
  });
});
