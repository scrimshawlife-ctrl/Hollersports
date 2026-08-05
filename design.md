# Design — HollerSports Operator Workbench

Locked design system for the **app** (`packages/operator-web`). All three
routes (Today / Book / Health) share this system. Do not invent per-page themes.

Docs map: [docs/README.md](docs/README.md) · package README: [packages/operator-web/README.md](packages/operator-web/README.md).

## Genre

**atmospheric** — dark paper, low chroma, technical-austere operator console.

## Macrostructure family

- **App pages (all routes):** Workbench — N3 side rail, dense main column, Ft4-style
  system colophon. Variation knobs: section density (primary vs advanced),
  action grouping, panel chrome weight.
- Marketing / content: none (this package is app-only).

## Theme (Cobalt · locked)

| Token | Value |
|-------|--------|
| `--color-paper` | `oklch(16% 0.018 250)` |
| `--color-paper-2` | `oklch(20% 0.02 250)` |
| `--color-paper-3` | `oklch(24% 0.022 250)` |
| `--color-ink` | `oklch(93% 0.015 250)` |
| `--color-muted` | `oklch(68% 0.02 250)` |
| `--color-accent` | `oklch(68% 0.13 245)` |
| `--color-accent-ink` | `oklch(16% 0.018 250)` |
| `--color-warn` | `oklch(78% 0.11 85)` |
| `--color-fail` | `oklch(68% 0.15 25)` |
| `--color-ok` | `oklch(72% 0.12 155)` |
| `--color-rule` | hairline mix of ink @ 12% |

## Typography

- Display: **Space Grotesk**, weight 500–600, **roman only** (no italic headers)
- Body: **IBM Plex Sans**, 400–500
- Mono: **IBM Plex Mono**, 400–500 (packets, IDs, tables)
- Section titles: display, sentence-ish small caps optional — prefer **small display** not full shouty uppercase on every heading

## Spacing

4-point scale via named tokens only (`--space-2xs` … `--space-xl`).  
**No raw `style={{ marginBottom: 12 }}`** — use utility classes.

## Motion

- Easings: `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)`
- Duration: `--dur-fast: 120ms` · `--dur-short: 200ms`
- Reduced-motion: transitions none / opacity ≤ 150ms
- Stance: silent success; no celebratory toasts

## Microinteractions

- Buttons: default · hover · focus-visible · active · disabled · loading (`data-busy` / `aria-busy`)
- Primary CTA fill: accent-tinted surface, one primary per action group
- Secondary: outline hairline
- Tables: row hover lift 3% ink; selected = accent 12%

## CTA voice

- Primary: “Run full day…”, one per group
- Secondary: observe / compete / paper steps
- Danger/network: still secondary chrome, not red buttons (fail is for errors)

## What pages MUST share

- Wordmark + “advise · never fund”
- Cobalt tokens and fonts
- Shell rail + colophon product law
- Chip vocabulary (neutral / warn / fail / ok)

## What pages MAY differ on

- Section order and which panels collapse
- Action group labels (Today vs Book vs Health)
- Density: Health may use collapsible “advanced” blocks

## Redesign goals (from audit)

1. Kill inline style improvisation → utility classes  
2. Complete button state surface  
3. Group Today actions (fixture · free-first · paper loop)  
4. Soften Health panel monotony (panel cards + subnav anchors)  
5. Colophon wraps on small screens  
6. Empty states upright mono, not italic  

## Exports

Canonical tokens live in `packages/operator-web/tokens.css`.
