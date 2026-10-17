# Handoff: Playbook — Brutalist Redesign

## Overview
Playbook is an AI presales-intelligence engine for finance & accounting. A RAG-driven chatbot runs a discovery session, and from that conversation two intelligence surfaces are produced (a shareable client-facing deliverable and a restricted internal dashboard), tied together by a hub. This package is a brutalist visual redesign of all five surfaces.

## About the Design Files
The files in this bundle (`*.dc.html`) are **design references created in HTML** — prototypes showing the intended look and behavior. They are **not production code to copy directly**. They are authored in a lightweight streaming-component format ("Design Components") and load a runtime shim (`support.js`); ignore that machinery.

The task is to **recreate these designs in the target codebase's existing environment** (React, Vue, Svelte, etc.) using its established patterns, routing, and data layer. The HTML/CSS here is the source of truth for **appearance and interaction**, not architecture. Where these mocks use hard-coded sample data, wire the equivalent real data from your backend.

## Fidelity
**High-fidelity (hifi).** Final colors, typography, spacing, borders, and interaction states are all specified below and present in the files. Recreate pixel-faithfully, then swap sample content for live data.

## Design System (applies to ALL screens)

### Typography
- **Display / UI:** `Archivo` (Google Fonts), weights 400–900. Headings use 800–900, uppercase, tight tracking (`letter-spacing: -0.035em` for hero, `-0.02em` for section titles), `line-height: 0.9`.
- **Mono / labels / data:** `JetBrains Mono` (Google Fonts), weights 400/500/700. Used for kickers, nav, codes (e.g. `C-00138`), metric captions, tags, footer — always UPPERCASE with `letter-spacing` 0.08–0.22em.
- Body copy: Archivo 400, 15–20px, `line-height` 1.5–1.6, color `#333`/`#444`.
- Load: `https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap`

### Color tokens
| Token | Value | Role |
|---|---|---|
| `--ink` | `#0A0A0A` | Text, borders, filled buttons |
| `--paper` (warm) | `#F7F5EF` | Default page background |
| `--paper` (white) | `#FFFFFF` | Alternate page background (theme option) |
| `--paperAlt` (warm) | `#EFEDE6` | Recessed panels, hover fill, plot background |
| `--accent` | `#E01B13` | The single accent — kickers, links, key metrics, CTAs, active markers |
| meter track | `#E4E1D8` | Empty progress/meter background |
| hairline | `#D8D5CC` | Inner 1px dividers (inside a 2px block) |
| muted text | `#666` / `#777` / `#888` / `#999` | Secondary/caption text tiers |

`--accent` is themeable (alternates offered in mocks: `#1B44E0` blue, `#4BE01B` lime, `#FF5C00` orange). Default ships **red `#E01B13`**. This is a POC with no fixed brand color.

### Structural rules (the "brutalist" system)
- **Zero border-radius** everywhere (except the circular positioning-map bubbles).
- **2px solid `--ink` borders/rules** are the primary structural device. Cards, sections, inputs, and grids are separated by 2px black lines; sub-dividers inside a block are 1px `#D8D5CC`.
- **Hard offset shadows** on primary interactive elements: `box-shadow: 6px 6px 0 <ink|accent>`; on hover translate `-2px,-2px` and grow shadow to `8px 8px 0`; on active translate `+2/3px` and shrink to `2px 2px 0`. Transition `0.12s ease`.
- **Mono kicker pattern:** each section opens with `[ ## ]` in accent + a short mono/label descriptor.
- **Persistent chrome on every page:** a top header bar (`● PLAYBOOK` wordmark left, mono nav right) with a 2px bottom border, then a thin "meta strip" (breadcrumb left, status dot + context label right) with a 2px bottom border.
- Content max-width `1440px` (chat `1100px`), horizontal padding `40px`.
- `::selection { background: var(--accent); color: #fff; }`

### Interaction / hover conventions
- **Cards / list rows:** background shifts to `#EFEDE6` on hover; list rows also add `padding-left` (26px→38px) for a slide-in feel. Transition `0.14s ease`.
- **Tabs / segmented toggles:** active = filled `--ink` bg with `--paper` text; inactive = transparent bg, ink text. Buttons separated by 2px ink borders.
- **Text links:** accent color + `border-bottom: 2px solid var(--accent)`.
- All external links open in a new tab (`target="_blank" rel="noopener"`).

---

## Screens / Views

### 1. Hub — `Hub.dc.html`
- **Purpose:** Landing/entry; routes to Chat, External, Internal.
- **Layout:** Header + meta strip. Hero (kicker `[ 00 ]` + descriptor, giant H1 "ANALYTICS & DELIVERABLES" with the `&` in accent, intro paragraph left + red "Start a discovery session" CTA right). Below: a 2-column bordered card block (External / Internal), each a full-height `<a>` with a big mono index number (`01`/`02`), an outlined tag top-right (`Shareable` / `Internal Use`), a large uppercase H2, description, and an accent arrow link at the bottom. Footer meta row.
- **Notes:** Both card tags are outlined (2px ink border, no fill) — matched intentionally.

### 2. Chat / Discovery — `Chat.dc.html`
Two states in one view (state var `screen: 'intake' | 'session'`).
- **Intake (default):** H1 "PLAYBOOK", intro with an "analytics hub" link, then a 2px-bordered form grid (2 cols): Company name* (accent asterisk), Industry, Headcount (select), Annual revenue (select), Years in business, Function you cover (select), Your name, Your role. Selects default to a **gray `#999` "Select…"** disabled placeholder that turns `#0A0A0A` once a real option is chosen (`onChange` sets `el.style.color`). Inputs are borderless with a 2px ink underline. Red "Begin discovery session →" CTA (hard shadow) advances to session.
- **Session:** H1 "PLAYBOOK", a "Copy resume link" bar (button + accent session URL), a **coverage meter** (`covered / 14 slots · NN%`, accent fill on `#E4E1D8` track, animates width 0.4s), an upload panel row (Choose file / doc list / accepted formats mono caption), an "Open prospect roadmap →" link, the **message list** (agent bubbles left = paper bg/ink border/accent "AGENT" tag; user bubbles right = ink bg/`#F2F2F0` text/"YOU" tag; all zero-radius 2px-bordered), and a 2px-bordered composer (text input + ink "Send →" button; Enter also sends).
- **Behavior:** Sending appends the user message + a canned agent reply and bumps coverage by 2 (capped at 14). Replies cycle through a fixed list.

### 3. External Deliverables (list) — `External-Deliverables.dc.html`
- **Purpose:** Company-facing index of deliverables.
- **Layout:** Header + meta strip. Hero (kicker `[ 01 ]`, H1 "EXTERNAL DELIVERABLES", intro). Controls bar (2px-bordered): text filter input (mono, `⊘`/search glyph), "Include synthetic companies" checkbox (`accent-color: var(--accent)`), and a live `NN Companies` count. Then a bordered list where each row is an `<a>` with a 4-col grid: **name + accent code + mono meta** / **maturity meter** (label + `X.X/5`, accent fill on track) / **peer percentile** (big mono ordinal + "PEER PCT." caption) / **accent arrow**.
- **Behavior:** Filter matches name/code/industry (case-insensitive); the synthetic toggle includes/excludes `synthetic` rows; count reflects filtered length. Sample data in the logic class (`allCompanies()`), incl. ordinal helper for `82` → `82nd`.

### 4. External Company (flagship) — `External-Company.dc.html`
- **Purpose:** A single company's deliverable.
- **Layout:** Header + meta strip. Hero (accent "EXTERNAL DELIVERABLE" kicker, H1 "NIMBUSWORKS PARTNERS", mono meta `C-00138 · Software & SaaS · 1–50`, ink "↓ Download deliverable" button with accent hard shadow). A **segmented toggle** (`Company (executive)` / `Office of the CFO`) that swaps the whole dataset. A 4-col **stat grid** (each: mono label, huge 900-weight number + accent unit, note). A 2-col row: **Persona** block (mono "PERSONA" label, accent uppercase title, two body paragraphs) beside a **"Where you sit in your cohort"** panel (recessed `paperAlt` bg) with horizontal percentile bars (label + big mono value, accent fill on 2px-bordered track, caption). A **Roadmap** section (`[ Roadmap ]` kicker + title) as a 3-col bordered grid of phases **Now / Next / Later**, each with items (accent square bullet + phase name, then title + one-line desc rows separated by 1px hairlines). Footer.
- **Behavior:** Toggle state `tab: 'company' | 'cfo'` re-renders stats, persona, bars, and roadmap from `data()`.

### 5. Internal — `Internal.dc.html`
Two states in one view (state var `locked: boolean`).
- **Token gate (default):** accent "INTERNAL" kicker, H1 "COHORT INTELLIGENCE", instruction, and a 2px-bordered row with a password input ("Admin token") + red "Open dashboard →" button. Demo caption: any value unlocks. Header shows an accent-outlined "● RESTRICTED" tag.
- **Dashboard (unlocked):** Hero (accent "INTERNAL · RESTRICTED" kicker, H1, mono run-meta `Latest run … · 8 clusters · silhouette 0.375`, accent "↓ Download full dashboard" link). A **Manual recompute** card (description + ink "Run recompute" button w/ accent hard shadow; click shows "Running…" ~1.4s then updates the timestamp to now). A **Companies / Functions** segmented toggle. The **positioning map**: a 460px 2px-bordered plot with a centered crosshair (background linear-gradients at 50%), four mono quadrant labels (top-left accent "most urgent"), and absolutely-positioned circular **bubbles** (id number centered; `left` = maturity/5, `bottom` = pressure, size ∝ members; fill = accent if urgent, ink if higher-pressure, `#9A968B` otherwise; 2px ink border). Below, a 2-col **legend** (numbered swatch + persona name + `maturity · members` + priority tag, accent tag if urgent). Footer "Internal Only — Do Not Distribute".
- **Behavior:** `unlock()` flips to dashboard; `tab` swaps company/function datasets (`datasets()`); `recompute()` sets a transient running label then a fresh timestamp.
- **Stubs / not yet designed:** named-member drill-down (click bubble → members), account intel with product fit, pressure rankings, and the macro write-up / investor narrative. These sections exist on the live product but were not part of this redesign pass.

---

## State Management (per file)
- **Chat:** `screen`, `draft`, `covered` (0–14), `messages[]`. Send → append user + canned agent reply, `covered += 2`.
- **External-Company:** `tab` ('company'|'cfo') selects a data object.
- **External-Deliverables:** `query` (filter string), `includeSynthetic` (bool); derived filtered list + count.
- **Internal:** `locked`, `token`, `tab` ('companies'|'functions'), `lastRun`, `recomputing`.
- **Theme props (all files):** `accent` (hex string, default `#E01B13`), `paper` ('warm'|'white', default 'warm'). Implement as CSS variables / theme context.

## Design Tokens (quick reference)
- Colors: see table above.
- Border widths: 2px (structure), 1px (`#D8D5CC` sub-dividers).
- Radius: 0 (bubbles: 50%).
- Shadows: `6px 6px 0` idle / `8px 8px 0` hover / `2px 2px 0` active, color ink or accent.
- Spacing: page pad 40px; section vertical pad 44–72px; card/cell pad 22–48px.
- Type scale (hero H1): `clamp(44px, 6.5–9.5vw, 104–158px)`; section H2: `clamp(24px, 2.6–4vw, 34–64px)`; body 15–20px; mono labels 10–13px.

## Assets
None — no images or icon files. All glyphs are Unicode (arrows `→ ← ↓`, dot `●`, caret `▾`, search `⊘`). Fonts are Google Fonts (Archivo, JetBrains Mono). No logos; the wordmark is set type.

## Files
- `Hub.dc.html`
- `Chat.dc.html`
- `External-Deliverables.dc.html`
- `External-Company.dc.html`
- `Internal.dc.html`
- `support.js` (runtime shim for the Design Component format — reference only, do not port)

Open any file directly in a browser to see the live design and interactions before implementing.
