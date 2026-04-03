# REQ-033: UI Design System & Visual Redesign

**Status:** In Progress
**Version:** 0.3
**PRD Reference:** §7 Frontend Application
**Backlog Item:** #14
**Last Updated:** 2026-04-03

---

## 1. Overview

Zentropy Scout's current UI is functional but visually generic — default shadcn/ui styling, Blue-600 primary, system font stack, no brand identity. This REQ defines the visual design system that elevates the product from "AI-generated React" to a polished, branded SaaS experience.

The design direction is **zen + premium dark**: calm, professional, and distinctive. The product's value proposition is bringing order and calm to a stressful process — the visual language should reinforce that.

**Scope:** This REQ is built iteratively. Each section is filled in as design decisions are made and validated. Sections marked `TBD` are placeholders pending Stitch exploration and design review.

### 1.1 Design Philosophy

- **Purposeful motion** — animate to reveal, not to impress. Every animation must serve a function.
- **Space is design** — generous whitespace is a feature, not waste.
- **Dark primary** — dark slate base conveys premium and calm simultaneously.
- **Zen contrast** — job searching is chaos; Zentropy is the calm center. The UI should feel like relief.

### 1.2 Scope

| In Scope | Out of Scope |
|----------|-------------|
| Color palette (CSS variables in `globals.css`) | Backend changes |
| Typography — heading font selection | New features or behavioral changes |
| Component polish — shadows, borders, hover/focus states | Landing page structure (REQ-024) |
| Empty states | Data visualization / charts (deferred) |
| App interior pages (dashboard, jobs, scoring, onboarding) | Chrome extension (REQ-011, postponed) |
| Landing page visual treatment (after app interior is done) | |
| Micro-animations and scroll reveals | |

### 1.3 Relationship to Existing REQs

| REQ | Relationship |
|-----|-------------|
| REQ-012 | Base frontend application spec. REQ-033 applies visual design on top — no behavioral changes. |
| REQ-024 | Landing page structure and routing. REQ-033 will define the visual treatment of that page. |

---

## 2. Dependencies

### 2.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| REQ-012 | Context | Existing frontend architecture, component inventory |
| REQ-024 | Context | Landing page structure (visual treatment added here) |
| `frontend/src/app/globals.css` | Source | All CSS variables and theme definitions live here |
| `frontend/src/components/ui/` | Source | 28 shadcn/ui components to be restyled |

### 2.2 Other Documents Depend On This

| Document | How |
|----------|-----|
| REQ-024 | Landing page visual treatment defined here |

---

## 3. Color Palette

**Status:** 🟢 Complete (v1 — subject to Stitch refinement)

### 3.1 Design Direction

Dark slate base with soft indigo/violet primary accent and amber logo accent. Defined entirely via Tailwind v4 `@theme inline` in `globals.css` — no light mode, dark-first.

### 3.2 Token Definitions

All tokens live in `frontend/src/app/globals.css` under `@theme inline`.

| Token | Value | Usage |
|-------|-------|-------|
| `--background` | `slate-950` | Page background |
| `--foreground` | `slate-50` | Primary text |
| `--card` | `slate-900` | Card surfaces |
| `--card-foreground` | `slate-50` | Text on cards |
| `--primary` | soft indigo | Primary actions, CTAs, active states |
| `--primary-foreground` | `slate-50` | Text on primary |
| `--secondary` | `slate-800` | Secondary actions |
| `--muted` | `slate-800` | Muted backgrounds |
| `--muted-foreground` | `slate-400` | Muted text, labels |
| `--destructive` | red | Error/danger states |
| `--success` | green | Success states, high match scores |
| `--border` | `slate-800` | Borders, dividers |
| `--color-logo-accent` | `#fbbf24` (amber-400) | "zen" wordmark accent, starfield |

### 3.3 Semantic Colors (Domain-Specific)

Used in balance indicator (top nav) and application status badges.

| Usage | Token / Class |
|-------|--------------|
| Balance > $1.00 | `text-success` |
| Balance $0.10–$1.00 | `text-primary` |
| Balance < $0.10 | `text-destructive` |
| Application: Interview | amber |
| Application: Offer | `text-success` |
| Application: Rejected | `text-destructive` |
| Job match ≥ 87% | `text-success` |
| Job match 68–86% | `text-primary` |
| Job match < 68% | `text-muted-foreground` |

---

## 4. Typography

**Status:** 🟢 Complete (v1)

### 4.1 Font Selection

| Role | Font | Weight | Notes |
|------|------|--------|-------|
| All text | Nunito Sans | 400–800 | Loaded via `next/font/google`, applied globally via `--font-nunito` |
| Mono | system mono | — | Code blocks, job IDs (unchanged) |

Single font family across headings and body — different weights handle hierarchy. Nunito Sans chosen for its rounded, approachable feel that complements the "zen" direction.

### 4.2 Type Scale

Shared heading components in `frontend/src/components/ui/headings.tsx`:

| Component | Element | Classes |
|-----------|---------|---------|
| `PageTitle` | `<h1>` | `text-2xl font-semibold tracking-tight` |
| `SectionHeading` | `<h2>` | `text-lg font-semibold` |
| `SubHeading` | `<h3>` | `text-base font-semibold` |

All page-level headings use these components — edit one file to update all pages.

---

## 5. Component Polish

**Status:** 🟡 In Progress

### 5.1 Completed

| Component | Changes |
|-----------|---------|
| `ZentropyLogo` | SVG wordmark component replacing static PNG; "zen" in `--color-logo-accent` amber, "tropy" in foreground; scales via `text-*` class |
| `TopNav` | Height `h-16`, `px-6` padding, active tab indicator (absolute-positioned underline, content-width), `translate-y-[2px]` nudge |
| `DataTable` | `gap-4` between toolbar and table header |
| SVG favicon | Amber "z" on dark slate background |

### 5.2 Pending

- Shadcn/ui component-level polish (cards, buttons, inputs, badges) — pending Stitch exploration
- Empty states
- Hover/focus states audit

---

## 6. Page-by-Page Design Specs

**Status:** 🟡 In Progress

### 6.1 Completed

| Page | Changes |
|------|---------|
| All interior pages | `PageTitle`, `SectionHeading`, `SubHeading` components applied; `px-6 py-6` content padding |
| Persona | Dropped "Your" prefix; heading hierarchy applied |
| Resumes | Dropped "Your" prefix |
| Dashboard | Nav order: Applications → Persona → Resumes → Dashboard |
| Landing page | Full revamp (see §6.2) |

### 6.2 Landing Page

**Status:** 🟡 In Progress — functional, screenshots pending

| Element | Status | Notes |
|---------|--------|-------|
| Header / nav | ✅ Removed | Sign In / Get Started moved to hero + footer |
| Logo in hero | ✅ `text-9xl`, left-aligned, `mb-8` | Same `ZentropyLogo` component as top nav |
| Hero headline | ✅ "AI-Powered Job Search Assistant" | Left column, `flex-[2]` of 5 |
| Hero CTA buttons | ✅ "Get Started Free" + "Already have an account? Sign in" | Left column |
| Feature showcase | 🟡 Placeholder | Right column, `flex-[3]` of 5; 4-slide rotating mockup — to be replaced with real app screenshots |
| Starfield background | ✅ | 300–700 dots (viewport-scaled), amber/primary/white, 6–11s fade cycle |
| How It Works | ✅ Unchanged | 3-step walkthrough below hero |
| Footer | ✅ | Borderless, `© 2026 Zentropy`, pinned to bottom |
| Max-width constraint | ✅ `max-w-7xl` | Landing page only |

### 6.3 Pending Interior Pages

- Job Dashboard
- Job Detail / Scoring view
- Onboarding flow (pending Stitch exploration)
- Further polish on all pages once screenshots are captured

---

## 7. Animation & Motion

**Status:** 🔴 TBD

---

## 8. Empty States

**Status:** 🔴 TBD

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-02 | Dark mode as primary | Premium and calm simultaneously; better fit for "zen" brand direction |
| 2026-04-02 | App interior before landing page | Landing page hero will feature the app — must look good first |
| 2026-04-02 | Iterative REQ build | Design decisions made incrementally via Stitch + vision audit, not all upfront |
