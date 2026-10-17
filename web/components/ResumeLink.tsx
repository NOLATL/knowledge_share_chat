"use client";

import { useState } from "react";

export default function ResumeLink({ token }: { token: string }) {
  const [copied, setCopied] = useState(false);
  const path = `/session/${token}`;
  const url = typeof window !== "undefined" ? `${window.location.origin}${path}` : path;

  const copy = async () => {
    try {
      await navigator.clipboard?.writeText(url);
    } catch {
      // clipboard may be unavailable; the link is still shown below
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section
      style={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: 14,
        padding: "16px 20px",
        border: "2px solid var(--ink)",
        marginBottom: 18,
      }}
    >
      <button type="button" onClick={copy} className="flat-btn">
        {copied ? "Copied!" : "Copy resume link"}
      </button>
      <a
        href={path}
        style={{
          color: "var(--accent)",
          textDecoration: "none",
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          letterSpacing: "0.02em",
          wordBreak: "break-all",
        }}
      >
        {url}
      </a>
    </section>
  );
}
