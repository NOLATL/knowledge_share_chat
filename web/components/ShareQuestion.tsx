"use client";

import { useState } from "react";

/** Share icon on the current question: click -> email box -> send relay. */
export default function ShareQuestion({
  sessionId,
  askedText,
  onSent,
}: {
  sessionId: string;
  // The agent's actual last question, so the email matches the conversation.
  askedText?: string;
  onSent: (email: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    setSending(true);
    setError("");
    try {
      const response = await fetch("/api/relays", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, sentToEmail: email, askedQuestion: askedText }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body && typeof body.detail === "string" ? body.detail : `HTTP ${response.status}`);
      }
      const sentTo = email;
      setOpen(false);
      setEmail("");
      onSent(sentTo);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the question.");
    } finally {
      setSending(false);
    }
  };

  return (
    <span className="shareWrap">
      <button
        type="button"
        className="shareIcon"
        aria-label="Share this question by email"
        title="Send this question to a colleague"
        onClick={() => {
          setOpen((value) => !value);
          setError("");
        }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="18" cy="5" r="3" />
          <circle cx="6" cy="12" r="3" />
          <circle cx="18" cy="19" r="3" />
          <line x1="8.6" y1="10.6" x2="15.4" y2="6.4" />
          <line x1="8.6" y1="13.4" x2="15.4" y2="17.6" />
        </svg>
      </button>
      {open && (
        <form onSubmit={send} className="shareForm">
          <input
            aria-label="Colleague email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="colleague@example.com"
            type="email"
            required
          />
          <button type="submit" disabled={!email || sending}>
            {sending ? "Sending..." : "Send"}
          </button>
          <button type="button" onClick={() => setOpen(false)}>
            Cancel
          </button>
        </form>
      )}
      {error && <span className="shareError">{error}</span>}
      <style>{`
        .shareWrap {
          display: inline-flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 6px;
        }
        .shareIcon {
          display: inline-flex;
          align-items: center;
          border: 2px solid var(--ink);
          padding: 3px 5px;
          background: var(--paper);
          color: var(--ink);
          cursor: pointer;
        }
        .shareIcon:hover {
          background: var(--paper-alt);
        }
        .shareForm {
          display: inline-flex;
          gap: 6px;
        }
        .shareForm input {
          min-width: 210px;
          border: 2px solid var(--ink);
          background: var(--paper);
          padding: 4px 8px;
          font-family: var(--font-mono);
          font-size: 12px;
          color: var(--ink);
          outline: none;
        }
        .shareForm button {
          border: 2px solid var(--ink);
          padding: 4px 10px;
          background: var(--ink);
          color: var(--paper);
          font-family: var(--font-mono);
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          cursor: pointer;
        }
        .shareForm button[type="button"] {
          background: var(--paper);
          color: var(--ink);
        }
        .shareForm button:disabled {
          opacity: 0.55;
        }
        .shareError {
          color: var(--accent);
          font-family: var(--font-mono);
          font-size: 12px;
        }
      `}</style>
    </span>
  );
}
