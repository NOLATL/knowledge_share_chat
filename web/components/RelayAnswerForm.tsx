"use client";

import { useEffect, useState } from "react";

type RelayState =
  | { status: "loading" }
  | { status: "ready"; question: string; context: string; slotKey: string; sentToEmail: string }
  | { status: "done" }
  | { status: "error"; message: string };

export default function RelayAnswerForm({ token }: { token: string }) {
  const [state, setState] = useState<RelayState>({ status: "loading" });
  const [reply, setReply] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetch(`/api/relay?token=${encodeURIComponent(token)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(await errorText(response));
        }
        return response.json();
      })
      .then((body) => {
        if (body.status !== "sent" || body.expired) {
          setState({ status: "error", message: "This relay link is no longer available." });
          return;
        }
        setState({
          status: "ready",
          question: body.question_text,
          context: body.context_text ?? "",
          slotKey: body.slot_key,
          sentToEmail: body.sent_to_email,
        });
      })
      .catch((error: Error) => setState({ status: "error", message: error.message }));
  }, [token]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      const response = await fetch(`/api/relay?token=${encodeURIComponent(token)}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ replyText: reply }),
      });
      if (!response.ok) {
        throw new Error(await errorText(response));
      }
      setState({ status: "done" });
    } catch (error) {
      setState({ status: "error", message: error instanceof Error ? error.message : "Reply could not be submitted." });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="shell">
      <p className="eyebrow">Playbook relay</p>
      <h1>Answer one discovery question</h1>
      {state.status === "loading" && <section className="panel muted">Loading question...</section>}
      {state.status === "done" && (
        <section className="panel">
          <h2>Answer submitted</h2>
          <p>Thanks. This link is now closed.</p>
        </section>
      )}
      {state.status === "error" && (
        <section className="panel error">
          <h2>Relay unavailable</h2>
          <p>{state.message}</p>
        </section>
      )}
      {state.status === "ready" && (
        <section className="panel">
          <div className="meta">
            <span>{state.slotKey}</span>
            <span>Requested for {state.sentToEmail}</span>
          </div>
          <h2>{state.question}</h2>
          {state.context && <p className="context">{state.context}</p>}
          <form onSubmit={submit}>
            <textarea
              aria-label="Relay answer"
              value={reply}
              onChange={(event) => setReply(event.target.value)}
              placeholder="Add the answer here..."
              rows={7}
            />
            <button disabled={!reply.trim() || submitting} type="submit">
              {submitting ? "Submitting..." : "Submit answer"}
            </button>
          </form>
        </section>
      )}
      <Styles />
    </main>
  );
}

async function errorText(response: Response) {
  const body = await response.json().catch(() => null);
  if (body && typeof body.detail === "string") {
    return body.detail;
  }
  return `Request failed with HTTP ${response.status}.`;
}

function Styles() {
  return (
    <style>{`
      body {
        margin: 0;
        background: var(--paper);
        color: var(--ink);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      .shell {
        width: min(720px, calc(100vw - 32px));
        margin: 0 auto;
        padding: 48px 0;
      }
      .eyebrow {
        margin: 0 0 8px;
        color: var(--accent);
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0;
        text-transform: uppercase;
      }
      h1, h2, p {
        margin-top: 0;
      }
      h1 {
        margin-bottom: 22px;
        font-size: 34px;
        line-height: 1.05;
      }
      .panel {
        padding: 24px;
        background: #fff;
        border: 1px solid var(--hairline);
        border-radius: 8px;
        box-shadow: 0 10px 30px rgba(23, 32, 38, 0.06);
      }
      .muted {
        color: #666;
      }
      .context {
        margin-bottom: 4px;
        color: #4b5563;
        font-size: 15px;
      }
      .error {
        color: var(--accent);
      }
      .meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 12px;
      }
      .meta span {
        border-radius: 999px;
        padding: 5px 8px;
        background: var(--paper-alt);
        color: #333;
        font-size: 12px;
        font-weight: 800;
      }
      textarea {
        display: block;
        width: 100%;
        box-sizing: border-box;
        margin: 12px 0;
        border: 1px solid var(--ink);
        border-radius: 6px;
        padding: 10px;
        font: inherit;
        resize: vertical;
      }
      button {
        height: 40px;
        border: 0;
        border-radius: 6px;
        padding: 0 14px;
        background: var(--ink);
        color: #fff;
        font: inherit;
        font-weight: 800;
      }
      button:disabled {
        opacity: 0.55;
      }
      @media (max-width: 640px) {
        .shell {
          width: min(100vw - 20px, 720px);
          padding-top: 24px;
        }
        h1 {
          font-size: 29px;
        }
      }
    `}</style>
  );
}
