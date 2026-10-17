import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DocumentUpload from "./DocumentUpload";

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

describe("DocumentUpload", () => {
  it("shows idle upload controls", async () => {
    const fetchMock = mockFetch(Response.json([]));
    render(<DocumentUpload sessionId="s1" />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText("Upload document")).toBeInTheDocument();
    expect(screen.getByText("Choose file")).toBeInTheDocument();
    expect(screen.getByText("No documents attached yet")).toBeInTheDocument();
  });

  it("shows parsed status and refreshes document list after upload", async () => {
    mockFetch(
      Response.json([]),
      Response.json({ id: "d1", filename: "budget.csv", status: "parsed", chunk_count: 1 }),
      Response.json([
        {
          id: "d1",
          filename: "budget.csv",
          doc_type: "financials",
          status: "parsed",
          chunk_count: 1,
          created_at: "2026-06-30T10:00:00Z",
        },
      ]),
    );
    render(<DocumentUpload sessionId="s1" />);

    const file = new File(["metric,value\nClose days,12\n"], "budget.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText("Upload document"), { target: { files: [file] } });

    expect(await screen.findByText("Document parsed and ready for the conversation.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("budget.csv")).toBeInTheDocument());
    expect(screen.getByText(/Ready for chat - 1 searchable chunks/)).toBeInTheDocument();
    expect(screen.getByText(/financials/)).toBeInTheDocument();
  });

  it("fires onUploaded with the filename after a successful upload", async () => {
    mockFetch(
      Response.json([]),
      Response.json({ id: "d1", filename: "budget.csv", status: "parsed", chunk_count: 1 }),
      Response.json([]),
    );
    const onUploaded = vi.fn();
    render(<DocumentUpload sessionId="s1" onUploaded={onUploaded} />);

    const file = new File(["metric,value\nClose days,12\n"], "budget.csv", { type: "text/csv" });
    fireEvent.change(screen.getByLabelText("Upload document"), { target: { files: [file] } });

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith("budget.csv"));
  });

  it("does not fire onUploaded when the upload fails", async () => {
    mockFetch(Response.json([]), Response.json({ detail: "unsupported file type: .png" }, { status: 400 }));
    const onUploaded = vi.fn();
    render(<DocumentUpload sessionId="s1" onUploaded={onUploaded} />);

    const file = new File(["x"], "diagram.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Upload document"), { target: { files: [file] } });

    await screen.findByText("unsupported file type: .png");
    expect(onUploaded).not.toHaveBeenCalled();
  });

  it("shows a clean error status when upload fails with an API detail", async () => {
    mockFetch(Response.json([]), Response.json({ detail: "unsupported file type: .png" }, { status: 400 }));
    render(<DocumentUpload sessionId="s1" />);

    const file = new File(["x"], "diagram.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Upload document"), { target: { files: [file] } });

    expect(await screen.findByText("unsupported file type: .png")).toBeInTheDocument();
    expect(screen.queryByText(/"detail"/)).not.toBeInTheDocument();
  });
});
