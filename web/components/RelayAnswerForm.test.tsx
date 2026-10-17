import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import RelayAnswerForm from "./RelayAnswerForm";

afterEach(() => {
  vi.restoreAllMocks();
});

function mockFetch(...responses: Response[]) {
  const fetchMock = vi.fn();
  for (const response of responses) {
    fetchMock.mockResolvedValueOnce(response);
  }
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("RelayAnswerForm", () => {
  it("submits a relay answer", async () => {
    const fetchMock = mockFetch(
      Response.json({
        token: "t1",
        slot_key: "close.days",
        question_text: "How many days does close take?",
        sent_to_email: "peer@example.com",
        status: "sent",
        expires_at: "2026-07-01T12:00:00Z",
        expired: false,
      }),
      Response.json({ status: "answered" }),
    );

    render(<RelayAnswerForm token="t1" />);

    expect(await screen.findByText("How many days does close take?")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Relay answer"), { target: { value: "Close takes 12 days." } });
    fireEvent.click(screen.getByRole("button", { name: "Submit answer" }));

    await waitFor(() => expect(screen.getByText("Answer submitted")).toBeInTheDocument());
    expect(fetchMock).toHaveBeenLastCalledWith("/api/relay?token=t1", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ replyText: "Close takes 12 days." }),
    });
  });

  it("shows closed state for expired relay", async () => {
    mockFetch(
      Response.json({
        token: "t1",
        slot_key: "close.days",
        question_text: "How many days does close take?",
        sent_to_email: "peer@example.com",
        status: "expired",
        expires_at: "2026-06-29T12:00:00Z",
        expired: true,
      }),
    );

    render(<RelayAnswerForm token="t1" />);

    expect(await screen.findByText("This relay link is no longer available.")).toBeInTheDocument();
  });
});
