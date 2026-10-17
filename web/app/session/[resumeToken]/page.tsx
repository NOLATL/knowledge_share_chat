"use client";

import { use, useEffect, useState } from "react";

import ChatApp, { Bubble } from "@/components/ChatApp";
import Chrome from "@/components/Chrome";

type ResumeState = {
  id: string;
  resume_token: string;
  recap: string;
  messages: { role: string; content: string }[];
};

export default function ResumePage({ params }: { params: Promise<{ resumeToken: string }> }) {
  const { resumeToken } = use(params);
  const [state, setState] = useState<ResumeState | null>(null);
  const [error, setError] = useState(false);

  return (
    <Chrome active="Chat" breadcrumb="Hub / Chat / Resumed Session" context="Discovery" maxWidth={1100}>
      <ResumeBody resumeToken={resumeToken} state={state} error={error} setState={setState} setError={setError} />
    </Chrome>
  );
}

function ResumeBody({
  resumeToken,
  state,
  error,
  setState,
  setError,
}: {
  resumeToken: string;
  state: ResumeState | null;
  error: boolean;
  setState: (s: ResumeState) => void;
  setError: (e: boolean) => void;
}) {
  useEffect(() => {
    fetch(`/api/resume?token=${resumeToken}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setState)
      .catch(() => setError(true));
    // setState/setError are stable useState setters passed down.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeToken]);

  const monoNote = {
    fontFamily: "var(--font-mono)",
    fontSize: 13,
    letterSpacing: "0.08em",
    textTransform: "uppercase" as const,
    color: "#666",
    padding: "60px 0",
  };

  if (error) return <p style={monoNote}>Session not found.</p>;
  if (!state) return <p style={monoNote}>Restoring your session…</p>;

  return (
    <div>
      {/* Restored history in the same bubble language, then the live session. */}
      <section style={{ border: "2px solid var(--ink)", borderBottom: "none", marginTop: 44 }} aria-label="Restored conversation">
        <div style={{ padding: "8px 0" }}>
          <Bubble role="agent">{state.recap}</Bubble>
          {state.messages.map((m, i) => (
            <Bubble key={i} role={m.role === "user" ? "user" : "agent"}>
              {m.content}
            </Bubble>
          ))}
        </div>
      </section>
      <div style={{ borderTop: "2px solid var(--ink)" }} />
      <ChatApp sessionId={state.id} resumeToken={state.resume_token} />
    </div>
  );
}
