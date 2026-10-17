import { beforeEach, describe, expect, it } from "vitest";

import { buildSnapshotHtml } from "./snapshot";

describe("buildSnapshotHtml", () => {
  beforeEach(() => {
    document.head.innerHTML = "<style>.hard-btn { color: red; } @font-face { src: url('/font.woff2'); }</style>";
    document.body.innerHTML =
      '<h1>Bluewater Freight Group</h1>' +
      '<div data-snapshot-exclude=""><button>Regenerate</button></div>' +
      "<script>alert(1)</script>";
  });

  it("keeps page content, inlines CSS, and drops scripts and excluded controls", () => {
    const html = buildSnapshotHtml();
    expect(html).toMatch(/^<!DOCTYPE html>/);
    expect(html).toContain("Bluewater Freight Group");
    expect(html).toContain(".hard-btn");
    expect(html).not.toContain("Regenerate");
    expect(html).not.toContain("alert(1)");
  });

  it("absolutizes root-relative asset URLs so fonts resolve from the saved file", () => {
    const html = buildSnapshotHtml();
    expect(html).not.toMatch(/url\(["']?\/font\.woff2/);
    expect(html).toContain(`${location.origin}/font.woff2`);
  });
});
