# Zentropy Scout — Brand Color Palette

**Status:** Active (dark-only theme)
**Last Updated:** 2026-03-02

---

## Core Palette

| Role | Hex | Notes |
|------|-----|-------|
| Brand primary | `#F0A500` | Amber gold — replaces Blue-600 everywhere |
| Background | `#1E2535` | Dark slate — replaces Gray-950 |
| Surface/Card | `#253044` | Slightly lighter slate for card elevation |
| Surface raised | `#2D3A52` | Second elevation level for modals, dropdowns |
| Border | `#3A4A63` | Subtle border, visible but not harsh |
| Foreground | `#F5F5F5` | Primary text |
| Muted text | `#94A3B8` | Secondary text, labels, placeholders |
| Primary hover | `#D4920A` | Amber darkened ~15% for button hover states |
| Primary foreground | `#0A0A0A` | Dark text on amber buttons for contrast |

---

## Semantic Colors

| Role | Previous | Current | Reason |
|------|----------|---------|--------|
| Warning | Amber-500 `#f59e0b` | Orange `#f97316` | Amber is now brand color — must differentiate |
| Info | Blue-500 `#3b82f6` | Sky-400 `#38bdf8` | Blue is no longer primary, use lighter sky |
| Success | Green-600 `#16a34a` | Keep `#22c55e` | Works well on dark slate |
| Destructive | Red-600 `#dc2626` | Keep `#ef4444` | Universal, no change needed |
| Stretch/Purple | `#9333ea` | Keep | Already distinctive |

---

## Component Targets

| Component | Value | Notes |
|-----------|-------|-------|
| Nav bar background | `#1A2030` | Slightly darker than page bg for subtle separation |
| Chat user bubbles | `#F0A500` text on `#0A0A0A` bg | Was blue |
| Chat agent bubbles | `#253044` bg with `#F5F5F5` text | |
| Active nav link indicator | `#F0A500` underline or left border | |
| Credit balance display | `#F0A500` text | Key metric, brand color draws attention |
| Focus rings | `#F0A500` at 50% opacity | Replaces blue focus ring |
| Skeleton loaders | `#2D3A52` to `#3A4A63` pulse | |
| Scrollbars (if styled) | `#3A4A63` track, `#F0A500` thumb | |

---

## Resume Editor Canvas — Do Not Change

The TipTap editor canvas stays white (`#FFFFFF`) with near-black (`#0A0A0A`) text.
The surrounding editor chrome (toolbar, sidebar) uses the dark palette.
This is intentional — the document canvas simulates white paper.

---

## Tailwind Mapping

Map the palette values to semantic Tailwind tokens (`primary`, `background`, `foreground`,
`muted`, `border`, `card`) so existing component classes require no changes.
CSS variables are defined in `frontend/src/app/globals.css`.

---

## Contrast Verification (WCAG AA)

| Pair | Ratio | Passes AA? |
|------|-------|------------|
| Foreground `#F5F5F5` on Background `#1E2535` | ~13.2:1 | Yes |
| Primary foreground `#0A0A0A` on Primary `#F0A500` | ~8.1:1 | Yes |
| Muted `#94A3B8` on Background `#1E2535` | ~5.4:1 | Yes |
| Foreground `#F5F5F5` on Card `#253044` | ~10.8:1 | Yes |

---

## Constraints

- Do not introduce a light mode — dark only for now
- Do not change success or destructive semantic colors
- Do not change any component logic or layout for theme purposes
- Do not introduce new dependencies for theming
