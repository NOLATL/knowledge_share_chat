// "Download deliverable" = save the page you're looking at. Clone the live
// DOM, drop scripts and anything marked data-snapshot-exclude (the controls
// that only make sense in the app), inline every same-origin stylesheet, and
// absolutize root-relative asset URLs (next/font files) so the saved file can
// still resolve them. By construction the download matches the site exactly.
// ponytail: fonts/images need the app origin reachable when the file is opened;
// falls back to the theme's system font stacks offline.

export function buildSnapshotHtml(): string {
  const root = document.documentElement.cloneNode(true) as HTMLElement;
  root
    .querySelectorAll('script, [data-snapshot-exclude], link[rel="stylesheet"], style')
    .forEach((el) => el.remove());
  const css = Array.from(document.styleSheets)
    .map((sheet) => {
      try {
        return Array.from(sheet.cssRules)
          .map((rule) => rule.cssText)
          .join("\n");
      } catch {
        return ""; // cross-origin stylesheet — rules unreadable, skip
      }
    })
    .join("\n")
    .replace(/url\((["']?)\/(?!\/)/g, `url($1${location.origin}/`);
  const style = document.createElement("style");
  style.textContent = css;
  (root.querySelector("head") ?? root).appendChild(style);
  return "<!DOCTYPE html>\n" + root.outerHTML;
}

export function downloadSnapshot(filename: string): void {
  const url = URL.createObjectURL(new Blob([buildSnapshotHtml()], { type: "text/html" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
