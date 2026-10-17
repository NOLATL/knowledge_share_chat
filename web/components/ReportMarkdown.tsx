// Shared in-app renderer for report markdown (H1-H3, ul, ol, p, **bold**) —
// the client twin of lib/markdown.ts's markdownToHtml. ponytail: hand-rolled
// on purpose; add a markdown lib only if reports start using tables/nested markup.

import { LIST_MARKER, splitBlocks } from "../lib/markdown";

// **bold** → <strong>; odd-indexed split parts are the captured bold runs.
function inline(text: string): React.ReactNode {
  return text.split(/\*\*(.+?)\*\*/g).map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : part));
}

// Gap/Net assessments pop in accent red (write-up convention).
function accent(text: string): React.CSSProperties | undefined {
  return /^(Gap|Net):/.test(text) ? { color: "var(--accent)" } : undefined;
}

// List items: accent plus indentation for nested bullets (two leading spaces
// = one level; the flat <ul>/<ol> stays, only the <li> shifts — nested items
// inside an <ol> switch to disc bullets).
function liStyle(line: string, text: string, ordered: boolean): React.CSSProperties | undefined {
  const depth = Math.floor(/^\s*/.exec(line)![0].length / 2);
  if (!depth) return accent(text);
  return { ...accent(text), marginLeft: depth * 22, ...(ordered ? { listStyleType: "disc" } : {}) };
}

// One list block, bullets and/or numbered with indented sub-items. The <ol>
// counter counts nested disc <li>s too, so top-level items carry an explicit
// value (also renumbers markdown's lazy "1. 1. 1."). ponytail: sub-items
// always render as disc bullets, even when numbered in the source.
function ListBlock({ lines }: { lines: string[] }) {
  const ordered = /^\s*\d+\./.test(lines[0]);
  let n = 0;
  const items = lines.map((line) => {
    const text = line.replace(LIST_MARKER, "");
    return (
      <li
        key={line}
        value={ordered && !/^\s/.test(line) ? ++n : undefined}
        style={liStyle(line, text, ordered)}
      >
        {inline(text)}
      </li>
    );
  });
  return ordered ? <ol>{items}</ol> : <ul>{items}</ul>;
}

export default function ReportMarkdown({ markdown }: { markdown: string }) {
  const blocks = splitBlocks(markdown);
  return (
    <>
      {blocks.map((block, index) => {
        if (block.startsWith("### ")) return <h3 key={index}>{inline(block.replace(/^###\s+/, ""))}</h3>;
        if (block.startsWith("## ")) return <h2 key={index}>{inline(block.replace(/^##\s+/, ""))}</h2>;
        if (block.startsWith("# ")) return <h1 key={index}>{inline(block.replace(/^#\s+/, ""))}</h1>;
        const lines = block.split("\n");
        if (lines.every((line) => LIST_MARKER.test(line))) return <ListBlock key={index} lines={lines} />;
        return <p key={index} style={accent(block)}>{inline(block)}</p>;
      })}
    </>
  );
}
