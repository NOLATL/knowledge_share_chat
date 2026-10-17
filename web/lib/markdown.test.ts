import { describe, expect, it } from "vitest";

import { markdownToHtml, renderStandaloneHtml } from "./markdown";

describe("markdownToHtml", () => {
  it("renders headings, lists, and paragraphs", () => {
    const html = markdownToHtml("## Peer Benchmark\n\n- First win\n- Second win\n\nPlain paragraph.");
    expect(html).toContain("<h2>Peer Benchmark</h2>");
    expect(html).toContain("<ul><li>First win</li><li>Second win</li></ul>");
    expect(html).toContain("<p>Plain paragraph.</p>");
  });

  it("splits tight markdown (no blank line between heading and list)", () => {
    const html = markdownToHtml("## Stats\n- **Company:** Acme\n- **Size:** 200\nTrailing paragraph.");
    expect(html).toContain("<h2>Stats</h2>");
    expect(html).toContain("<ul><li><strong>Company:</strong> Acme</li><li><strong>Size:</strong> 200</li></ul>");
    expect(html).toContain("<p>Trailing paragraph.</p>");
  });

  it("renders ### as h3 sub-headers", () => {
    const html = markdownToHtml("## Product Fit\n\n### Financial Systems / IT\n\n- Something");
    expect(html).toContain("<h3>Financial Systems / IT</h3>");
  });

  it("indents nested bullets (two leading spaces per level)", () => {
    const html = markdownToHtml("- **Current process state:**\n  - ~100 invoices per month\n  - Gap: manual matching\n- **Planning cadence:** annual");
    expect(html).toContain("<li><strong>Current process state:</strong></li>");
    expect(html).toContain('<li style="margin-left:22px">~100 invoices per month</li>');
    expect(html).toContain('<li style="margin-left:22px;color:var(--accent)">Gap: manual matching</li>');
    expect(html).toContain("<li><strong>Planning cadence:</strong> annual</li>");
  });

  it("keeps a numbered list counting across nested sub-bullets", () => {
    const html = markdownToHtml(
      "## Prioritized Pains\n1. **Reconciliations**\n  - Major source of close delay.\n1. **Reporting assembly**\n  - Excel/SAP stitching.",
    );
    expect(html).toContain(
      '<ol><li value="1"><strong>Reconciliations</strong></li>' +
        '<li style="margin-left:22px;list-style-type:disc">Major source of close delay.</li>' +
        '<li value="2"><strong>Reporting assembly</strong></li>' +
        '<li style="margin-left:22px;list-style-type:disc">Excel/SAP stitching.</li></ol>',
    );
  });

  it("styles Gap:/Net: assessments in accent red", () => {
    const html = markdownToHtml("Gap: no knowledge-transfer story.\n\n- Net: strong coverage\n\nPlain.");
    expect(html).toContain('<p style="color:var(--accent)">Gap: no knowledge-transfer story.</p>');
    expect(html).toContain('<li style="color:var(--accent)">Net: strong coverage</li>');
    expect(html).toContain("<p>Plain.</p>");
  });

  it("renders **bold** as <strong>, including inside list items", () => {
    const html = markdownToHtml("A **key stat** here.\n\n- **Maturity**: 3.2/5");
    expect(html).toContain("<p>A <strong>key stat</strong> here.</p>");
    expect(html).toContain("<li><strong>Maturity</strong>: 3.2/5</li>");
    expect(html).not.toContain("**");
  });

  it("escapes HTML in report content", () => {
    const html = markdownToHtml("Close <script>alert(1)</script> & done");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
    expect(html).toContain("&amp;");
  });
});

describe("renderStandaloneHtml", () => {
  it("produces a self-contained styled document", () => {
    const html = renderStandaloneHtml("Acme — Deliverable", "## Quick Wins\n\n- Do the thing", "Generated now");
    expect(html).toMatch(/^<!DOCTYPE html>/);
    expect(html).toContain("<title>Acme — Deliverable</title>");
    expect(html).toContain("<style>");
    expect(html).toContain("<h2>Quick Wins</h2>");
    expect(html).toContain('class="reportMeta"');
  });
});
