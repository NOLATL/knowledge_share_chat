// Report markdown -> HTML for the downloadable standalone deliverable.
// Same block grammar as the in-app <Markdown> renderer (H1/H2, ul, ol, p);
// ponytail: hand-rolled on purpose — add a markdown lib only if reports start
// using tables/nested markup.

export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Escape first, then **bold** → <strong> (the only inline markup reports use).
function inlineHtml(text: string): string {
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

// Gap/Net assessments pop in accent red (write-up convention).
function accentAttr(text: string): string {
  return /^(Gap|Net):/.test(text) ? ' style="color:var(--accent)"' : "";
}

// Any list line: "-"/"*" bullet or "1." numbered, optionally indented.
export const LIST_MARKER = /^\s*(?:[-*]|\d+\.)\s+/;

// List items: accent red plus indentation for nested bullets (two leading
// spaces = one level; the flat <ul>/<ol> stays, only the <li> shifts —
// nested items inside an <ol> switch to disc bullets).
function liAttr(line: string, text: string, ordered: boolean): string {
  const depth = Math.floor(/^\s*/.exec(line)![0].length / 2);
  const styles = [
    ...(depth ? [`margin-left:${depth * 22}px`] : []),
    ...(depth && ordered ? ["list-style-type:disc"] : []),
    ...(/^(Gap|Net):/.test(text) ? ["color:var(--accent)"] : []),
  ];
  return styles.length ? ` style="${styles.join(";")}"` : "";
}

// One list block, bullets and/or numbered with indented sub-items. The <ol>
// counter counts nested disc <li>s too, so top-level items carry an explicit
// value (also renumbers markdown's lazy "1. 1. 1."). ponytail: sub-items
// always render as disc bullets, even when numbered in the source.
function listHtml(lines: string[]): string {
  const ordered = /^\s*\d+\./.test(lines[0]);
  let n = 0;
  const items = lines.map((line) => {
    const text = line.replace(LIST_MARKER, "");
    const value = ordered && !/^\s/.test(line) ? ` value="${++n}"` : "";
    return `<li${value}${liAttr(line, text, ordered)}>${inlineHtml(text)}</li>`;
  });
  const tag = ordered ? "ol" : "ul";
  return `<${tag}>${items.join("")}</${tag}>`;
}

type BlockKind = "heading" | "ul" | "ol" | "p";

function kindOf(line: string): BlockKind | null {
  if (!line.trim()) return null;
  if (/^#{1,3}\s/.test(line)) return "heading";
  if (/^\s*[-*]\s+/.test(line)) return "ul";
  if (/^\s*\d+\.\s+/.test(line)) return "ol";
  return "p";
}

// Line-based block splitting shared by both renderers. Generated reports often
// use "tight" markdown (no blank line between a heading and its list), so
// splitting on blank lines alone would glue whole sections into one block.
export function splitBlocks(markdown: string): string[] {
  const blocks: string[] = [];
  let current: string[] = [];
  let currentKind: BlockKind | null = null;
  const flush = () => {
    if (current.length) blocks.push(current.join("\n"));
    current = [];
    currentKind = null;
  };
  for (const line of markdown.split("\n")) {
    const kind = kindOf(line);
    if (!kind) {
      flush();
      continue;
    }
    // An indented list line is a sub-item: it stays in the surrounding list
    // block (otherwise "1. …\n  - …\n2. …" splits into <ol>s that restart at 1)
    // and doesn't change the block's top-level kind.
    const isSubItem =
      (kind === "ul" || kind === "ol") &&
      (currentKind === "ul" || currentKind === "ol") &&
      /^\s/.test(line);
    if (!isSubItem && (kind !== currentKind || kind === "heading")) flush();
    current.push(line);
    if (!isSubItem) currentKind = kind;
  }
  flush();
  return blocks;
}

export function markdownToHtml(markdown: string): string {
  const blocks = splitBlocks(markdown);
  return blocks
    .map((block) => {
      if (block.startsWith("### ")) {
        return `<h3>${inlineHtml(block.replace(/^###\s+/, ""))}</h3>`;
      }
      if (block.startsWith("## ")) {
        return `<h2>${inlineHtml(block.replace(/^##\s+/, ""))}</h2>`;
      }
      if (block.startsWith("# ")) {
        return `<h1>${inlineHtml(block.replace(/^#\s+/, ""))}</h1>`;
      }
      const lines = block.split("\n");
      if (lines.every((line) => LIST_MARKER.test(line))) return listHtml(lines);
      return `<p${accentAttr(block)}>${inlineHtml(block)}</p>`;
    })
    .join("\n");
}

// Brutalist system (Spec_FrontEnd_Design): the downloaded HTML matches the app.
const FONTS_LINK =
  '<link rel="preconnect" href="https://fonts.googleapis.com" />\n' +
  '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n' +
  '<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet" />';

const REPORT_CSS = `
  :root { --ink: #0A0A0A; --paper: #F7F5EF; --accent: #E01B13; --hairline: #D8D5CC; }
  * { box-sizing: border-box; }
  ::selection { background: var(--accent); color: #fff; }
  body { margin: 0; background: var(--paper); color: var(--ink);
         font-family: "Archivo", "Helvetica Neue", Arial, sans-serif; -webkit-font-smoothing: antialiased; }
  .report { width: min(920px, calc(100vw - 32px)); margin: 32px auto 56px; padding: 40px;
            background: var(--paper); border: 2px solid var(--ink); }
  .reportMeta { margin-bottom: 20px; color: #666; font-family: "JetBrains Mono", monospace;
                font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 700; }
  h1 { margin: 0 0 14px; font-weight: 900; font-size: clamp(30px, 4.5vw, 54px); line-height: 0.95;
       letter-spacing: -0.03em; text-transform: uppercase; }
  h2 { margin: 30px 0 12px; padding-top: 20px; border-top: 2px solid var(--ink); font-weight: 800;
       font-size: 21px; letter-spacing: -0.01em; text-transform: uppercase; }
  h2:first-of-type { margin-top: 0; padding-top: 0; border-top: 0; }
  h3 { margin: 22px 0 8px; font-weight: 800; font-size: 16px; letter-spacing: -0.01em; }
  p, li { color: #333; font-size: 15px; line-height: 1.6; }
  ul, ol { margin: 0 0 16px 22px; padding: 0; }
  li + li { margin-top: 7px; border-top: 1px solid var(--hairline); padding-top: 7px; }
  a { color: var(--accent); text-decoration: none; border-bottom: 2px solid var(--accent); }
`;

// Multi-section download: one HTML file, one .report card per section, each
// starting on its own printed page (the "paginated" whole-company deliverable).
// `html` is a trusted raw fragment (e.g. the chart SVG) injected before the markdown.
export function renderPaginatedHtml(
  title: string,
  sections: { markdown: string; meta?: string; html?: string }[],
): string {
  const articles = sections
    .map(
      (section) =>
        '<article class="report">' +
        (section.meta ? `<div class="reportMeta">${escapeHtml(section.meta)}</div>` : "") +
        (section.html ?? "") +
        markdownToHtml(section.markdown) +
        "</article>",
    )
    .join("\n");
  return [
    "<!DOCTYPE html>",
    '<html lang="en">',
    "<head>",
    '<meta charset="utf-8" />',
    '<meta name="viewport" content="width=device-width, initial-scale=1" />',
    `<title>${escapeHtml(title)}</title>`,
    FONTS_LINK,
    `<style>${REPORT_CSS}\n  .report + .report { page-break-before: always; margin-top: 24px; }</style>`,
    "</head>",
    "<body>",
    articles,
    "</body>",
    "</html>",
  ].join("\n");
}

export function renderStandaloneHtml(title: string, markdown: string, meta?: string): string {
  return [
    "<!DOCTYPE html>",
    '<html lang="en">',
    "<head>",
    '<meta charset="utf-8" />',
    '<meta name="viewport" content="width=device-width, initial-scale=1" />',
    `<title>${escapeHtml(title)}</title>`,
    FONTS_LINK,
    `<style>${REPORT_CSS}</style>`,
    "</head>",
    "<body>",
    '<article class="report">',
    meta ? `<div class="reportMeta">${escapeHtml(meta)}</div>` : "",
    markdownToHtml(markdown),
    "</article>",
    "</body>",
    "</html>",
  ]
    .filter(Boolean)
    .join("\n");
}
