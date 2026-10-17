"use client";

import { useChat } from "@ai-sdk/react";
import Link from "next/link";
import { TextStreamChatTransport, type UIMessage } from "ai";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import CompanyIntakeForm, { CompanyIntake } from "./CompanyIntakeForm";
import DocumentUpload from "./DocumentUpload";
import ProgressIndicator from "./ProgressIndicator";
import ResumeLink from "./ResumeLink";
import ShareQuestion from "./ShareQuestion";

export default function ChatApp({
  sessionId: provided,
  resumeToken: providedResumeToken,
}: {
  sessionId?: string;
  resumeToken?: string | null;
}) {
  const [sessionId, setSessionId] = useState<string | null>(provided ?? null);
  const [resumeToken, setResumeToken] = useState<string | null>(providedResumeToken ?? null);
  const [initialMessage, setInitialMessage] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    setResumeToken(providedResumeToken ?? null);
  }, [providedResumeToken]);

  const start = useCallback((intake: CompanyIntake) => {
    setStarting(true);
    fetch("/api/session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ company: intake }),
    })
      .then((r) => r.json())
      .then((d) => {
        setSessionId(d.id);
        setResumeToken(d.resume_token ?? null);
        setInitialMessage(d.initial_message ?? null);
      })
      .catch(() => setStarting(false));
  }, []);

  // Resume flow supplies a sessionId directly and skips the intake form.
  if (!sessionId) {
    return (
      <>
        <Hero kicker="Discovery Intake">
          <p style={{ margin: "30px 0 8px", maxWidth: 640, fontSize: 18, lineHeight: 1.5, color: "#333" }}>
            AI-guided finance &amp; accounting discovery.
            <br />
            Find the analytic report at the <Link href="/hub" className="accent-link">analytics hub</Link>.
          </p>
        </Hero>
        {starting ? (
          <p style={{ fontFamily: "var(--font-mono)", fontSize: 13, letterSpacing: "0.08em", textTransform: "uppercase", color: "#666" }}>
            Starting session…
          </p>
        ) : (
          <CompanyIntakeForm onSubmit={start} />
        )}
      </>
    );
  }
  return <Conversation sessionId={sessionId} resumeToken={resumeToken} initialMessage={initialMessage} />;
}

function Hero({ kicker, children }: { kicker: string; children?: React.ReactNode }) {
  return (
    <section style={{ padding: "60px 0 30px" }}>
      <div className="kicker-solo" style={{ marginBottom: 20 }}>{kicker}</div>
      <h1
        style={{
          margin: 0,
          fontWeight: 900,
          fontSize: "clamp(48px, 8vw, 120px)",
          lineHeight: 0.9,
          letterSpacing: "-0.035em",
          textTransform: "uppercase",
        }}
      >
        Playbook
      </h1>
      {children}
    </section>
  );
}

// Zero-radius chat bubble; also used by the resume page for restored history.
export function Bubble({ role, children }: { role: "agent" | "user"; children: React.ReactNode }) {
  const isAgent = role === "agent";
  return (
    <div style={{ display: "flex", padding: "16px 24px", justifyContent: isAgent ? "flex-start" : "flex-end" }}>
      <div
        style={{
          maxWidth: "74%",
          border: "2px solid var(--ink)",
          background: isAgent ? "var(--paper)" : "var(--ink)",
          padding: "16px 18px",
        }}
      >
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: isAgent ? "var(--accent)" : "#9A968B",
            marginBottom: 8,
          }}
        >
          {isAgent ? "Agent" : "You"}
        </div>
        <div style={{ fontSize: 15, lineHeight: 1.55, color: isAgent ? "#2a2a2a" : "#F2F2F0" }}>{children}</div>
      </div>
    </div>
  );
}

function partsToText(parts: { type: string; text?: string }[] | undefined): string {
  return (parts ?? []).map((p) => (p.type === "text" ? p.text ?? "" : "")).join("");
}

function Conversation({
  sessionId,
  resumeToken,
  initialMessage,
}: {
  sessionId: string;
  resumeToken?: string | null;
  initialMessage?: string | null;
}) {
  const [input, setInput] = useState("");
  const [coverage, setCoverage] = useState({ filled: 0, total: 0 });
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // The transport closes over sessionId and forwards the latest user text to the BFF.
  const transport = useMemo(
    () =>
      new TextStreamChatTransport({
        api: "/api/chat",
        prepareSendMessagesRequest: ({ messages }) => {
          const last = messages[messages.length - 1];
          return { body: { sessionId, message: partsToText(last?.parts) } };
        },
      }),
    [sessionId],
  );

  const { messages, sendMessage, status } = useChat({
    id: sessionId,
    transport,
    messages: initialMessage
      ? ([{ id: "welcome", role: "assistant", parts: [{ type: "text", text: initialMessage }] }] as UIMessage[])
      : undefined,
  });

  const refreshCoverage = useCallback(() => {
    fetch(`/api/coverage?sessionId=${sessionId}`)
      .then((r) => r.json())
      .then((d) => setCoverage({ filled: d.filled_must_fill, total: d.total_must_fill }))
      .catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    refreshCoverage();
  }, [refreshCoverage]);

  // Mark the session paused when the user leaves (best-effort, survives unload).
  useEffect(() => {
    const pause = () => navigator.sendBeacon?.(`/api/pause?sessionId=${sessionId}`);
    window.addEventListener("pagehide", pause);
    return () => window.removeEventListener("pagehide", pause);
  }, [sessionId]);

  // After each completed turn, the extracted answers may have moved coverage.
  useEffect(() => {
    if (status === "ready") refreshCoverage();
  }, [status, refreshCoverage]);

  // Keep the conversation pinned to the newest message (messages changes on
  // every append and while the assistant reply streams in).
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || status === "streaming" || status === "submitted") return;
    sendMessage({ text });
    setInput("");
  };

  return (
    <div>
      <Hero kicker="Discovery Session" />

      {resumeToken && <ResumeLink token={resumeToken} />}
      <ProgressIndicator filled={coverage.filled} total={coverage.total} />
      <DocumentUpload
        sessionId={sessionId}
        onUploaded={(filename) => sendMessage({ text: `I've uploaded ${filename}.` })}
      />
      <section style={{ border: "2px solid var(--ink)", borderBottom: "none" }} aria-label="Conversation">
        <div ref={scrollRef} style={{ maxHeight: 440, overflowY: "auto", padding: "8px 0" }}>
          {messages.map((m, index) => (
            <Bubble key={m.id} role={m.role === "user" ? "user" : "agent"}>
              {partsToText(m.parts as { type: string; text?: string }[])}
              {m.role === "assistant" && index === messages.length - 1 && status === "ready" && (
                <div style={{ marginTop: 10 }}>
                  <ShareQuestion
                    sessionId={sessionId}
                    askedText={partsToText(m.parts as { type: string; text?: string }[])}
                    onSent={(email) => sendMessage({ text: `I've sent that question to ${email} — let's continue.` })}
                  />
                </div>
              )}
            </Bubble>
          ))}
        </div>
      </section>

      <form onSubmit={onSubmit} style={{ display: "flex", border: "2px solid var(--ink)", marginBottom: 56 }}>
        <input
          aria-label="message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          style={{
            flex: 1,
            minWidth: 0,
            border: "none",
            outline: "none",
            background: "transparent",
            padding: "20px 22px",
            fontFamily: "var(--font-display)",
            fontSize: 16,
            color: "var(--ink)",
          }}
        />
        <button
          type="submit"
          disabled={status === "streaming" || status === "submitted"}
          style={{
            flexShrink: 0,
            border: "none",
            borderLeft: "2px solid var(--ink)",
            background: "var(--ink)",
            color: "var(--paper)",
            cursor: "pointer",
            padding: "20px 30px",
            fontFamily: "var(--font-mono)",
            fontWeight: 700,
            fontSize: 13,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}
        >
          Send →
        </button>
      </form>
    </div>
  );
}
