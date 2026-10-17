"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type DocumentRow = {
  id: string;
  filename: string;
  doc_type: string | null;
  status: string;
  created_at?: string;
  chunk_count: number;
};

function statusLabel(status: string, chunkCount: number): string {
  if (status === "parsed") {
    return chunkCount > 0 ? "Ready for chat" : "Parsed, no searchable text";
  }
  if (status === "error") return "Needs attention";
  if (status === "pending") return "Processing";
  return status;
}

function statusColor(status: string): string {
  if (status === "parsed") return "#4d7c0f";
  if (status === "error") return "var(--accent)";
  if (status === "pending") return "#92400e";
  return "#555";
}

async function uploadErrorMessage(res: Response): Promise<string> {
  const text = await res.text();
  if (!text) return "Upload failed";
  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    // Fall back to the raw upstream body.
  }
  return text;
}

export default function DocumentUpload({
  sessionId,
  onUploaded,
}: {
  sessionId: string;
  onUploaded?: (filename: string) => void;
}) {
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [status, setStatus] = useState<"idle" | "uploading" | "parsed" | "error">("idle");
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLInputElement | null>(null);

  const refresh = useCallback(() => {
    fetch(`/api/documents?sessionId=${sessionId}`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setDocuments)
      .catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Choosing a file uploads it immediately (mock has a single "Choose file" action).
  const upload = async () => {
    const file = inputRef.current?.files?.[0];
    if (!file || status === "uploading") return;
    setStatus("uploading");
    setMessage("Uploading and reading document...");

    const form = new FormData();
    form.set("sessionId", sessionId);
    form.set("file", file);

    try {
      const res = await fetch("/api/documents", { method: "POST", body: form });
      if (!res.ok) {
        throw new Error(await uploadErrorMessage(res));
      }
      setStatus("parsed");
      setMessage("Document parsed and ready for the conversation.");
      if (inputRef.current) inputRef.current.value = "";
      refresh();
      onUploaded?.(file.name);
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "Upload failed");
    }
  };

  return (
    <section
      aria-label="Documents"
      style={{ border: "2px solid var(--ink)", padding: "18px 22px", marginBottom: 18 }}
    >
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <label className="flat-btn" style={{ display: "inline-block" }}>
            {status === "uploading" ? "Uploading..." : "Choose file"}
            <input
              ref={inputRef}
              aria-label="Upload document"
              type="file"
              accept=".pdf,.docx,.pptx,.xlsx,.csv"
              disabled={status === "uploading"}
              onChange={upload}
              style={{ display: "none" }}
            />
          </label>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "#888" }}>
            {documents.length === 0 ? "No documents attached yet" : `${documents.length} document(s) attached`}
          </span>
        </div>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            color: "#999",
          }}
        >
          PDF · DOCX · PPTX · XLSX · CSV
        </span>
      </div>

      {message && (
        <p
          role="status"
          style={{
            margin: "10px 0 0",
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            color: status === "error" ? "var(--accent)" : "#555",
          }}
        >
          {message}
        </p>
      )}

      {documents.length > 0 && (
        <ul style={{ margin: "12px 0 0", padding: 0, listStyle: "none" }}>
          {documents.map((doc) => (
            <li
              key={doc.id}
              style={{
                borderTop: "1px solid var(--hairline)",
                padding: "10px 0",
                display: "flex",
                flexWrap: "wrap",
                alignItems: "baseline",
                gap: "4px 14px",
              }}
            >
              <span style={{ fontWeight: 700, fontSize: 14 }}>{doc.filename}</span>
              <span style={{ color: statusColor(doc.status), fontFamily: "var(--font-mono)", fontSize: 11, letterSpacing: "0.04em" }}>
                {statusLabel(doc.status, doc.chunk_count)}
                {doc.chunk_count ? ` - ${doc.chunk_count} searchable chunks` : ""}
              </span>
              <span style={{ color: "#888", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                {doc.doc_type ?? "document"}
                {doc.created_at ? ` - ${new Date(doc.created_at).toLocaleString()}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
