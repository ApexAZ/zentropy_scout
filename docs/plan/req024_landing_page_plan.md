# Zentropy Scout — REQ-024 Landing Page Implementation Plan

**Created:** 2026-03-03
**Last Updated:** 2026-03-03
**Status:** ⬜ Not Started

---

## Context

Zentropy Scout currently serves the Dashboard at `/` for authenticated users and redirects unauthenticated visitors to `/login`. There is no public-facing landing page. This plan adds a marketing landing page at `/`, moves the Dashboard to `/dashboard`, and introduces Next.js middleware for auth-based routing.

**What changes:** Dashboard route `/` → `/dashboard`, new `(public)` route group with landing page at `/`, new middleware for cookie-based auth routing, 7 source files updated (11 references — login/register/nav/job-detail/onboarding redirect targets), ~61 E2E test changes (52 `goto` + 9 `toHaveURL` assertions across 14 files), Legal section added to Settings page.

**What does NOT change:** Dashboard content/behavior, authentication logic, onboarding flow, backend API, root layout providers.

**Scope:** 1 middleware file, 8 new frontend components (5 landing sections + layout + page + E2E spec), 7 source files modified (11 references), 14 E2E test files updated, 1 E2E fixture modified. No backend changes.

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Load REQ-024 via `req-reader` subagent before each task
3. Each task = one commit, sized ≤ 40k tokens of context (TDD + review + fixes included)
4. **Subtask workflow:** Run affected tests → linters → commit (NO push)
5. **Phase-end workflow:** Run full test suite (backend + frontend + E2E) → push → compact
6. After each task: update status (⬜ → ✅), commit, STOP and ask user

**Workflow pattern:**

| Action | Subtask (§1, §2, §4, §5, §7) | Phase Gate (§3, §6, §8) |
|--------|-------------------------------|-------------------------|
| Tests | Affected files only | Full backend + frontend + E2E |
| Linters | Pre-commit hooks (~25-40s) | Pre-commit + pre-push hooks |
| Git | `git commit` only | `git push` |
| Context | Compact after commit | Compact after push |

**Why:** Pushes trigger pre-push hooks (full pytest + vitest, ~90-135s). By deferring pushes to phase boundaries, we save ~90-135s per subtask while maintaining quality gates.

**Context management for fresh sessions:** Each subtask is self-contained. A fresh context window needs:
1. This plan (find current task by status icon)
2. REQ-024 (via `req-reader` — load the §section listed in the task)
3. The specific files listed in the task description
4. No prior conversation history required

---

## Dependency Chain

```
Phase 1: Route Infrastructure (REQ-024 §5.1–§5.3, §6.3)
    │
    ▼
Phase 2: Landing Page Components + Settings (REQ-024 §4.1–§4.5, §5.4–§5.5, §6.1)
    │
    ▼
Phase 3: E2E Tests (REQ-024 §6.2)
```

**Ordering rationale:** Phases are strictly sequential. Route infrastructure (dashboard move, middleware) must be in place before landing page components can be served at `/`. Components must exist before E2E tests can verify them. Settings legal section is grouped with components since it's a small addition.

---

## Phase 1: Route Infrastructure (REQ-024 §5.1–§5.3, §6.3)

**Status:** ✅ Complete

*Move Dashboard to `/dashboard`, create `(public)` route group with placeholder, update all redirect targets (7 source files / 11 references, 14 E2E test files / 61 changes), create auth-based routing in proxy.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-024 §5.1 (route structure), §5.2 (middleware), §5.3 (dashboard move), §6.3 (existing test updates). |
| 🔍 **Search** | Grep source + tests for all `"/"` dashboard references (already audited — see Critical Files below). |
| 🔧 **Create** | Public layout, placeholder page, middleware. Move dashboard. Update all redirect targets. |
| ✅ **Verify** | `npm test -- --run`, `npm run typecheck`, `npx playwright test` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` (parallel) |
| 📝 **Commit** | One commit per subtask |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Dashboard move + public route group + redirect/E2E updates** | | ✅ 2026-03-03 |
| | **Read:** REQ-024 §5.1 (route structure), §5.3 (dashboard move), §6.3 (existing test updates). | `req-reader, plan` | |
| | | | |
| | **Create:** | | |
| | — `frontend/src/app/(public)/layout.tsx` — minimal wrapper: `<main className="min-h-screen bg-background">{children}</main>` | | |
| | — `frontend/src/app/(public)/page.tsx` — placeholder: `<div data-testid="landing-page"><p>Landing page</p></div>` (replaced in §4 with full composition) | | |
| | | | |
| | **Move:** | | |
| | — `frontend/src/app/(main)/page.tsx` → `frontend/src/app/(main)/dashboard/page.tsx` (no content changes) | | |
| | | | |
| | **Modify source files (7 files, 11 references):** | | |
| | — `frontend/src/app/login/page.tsx:92` — `router.replace("/")` → `router.replace("/dashboard")` | | |
| | — `frontend/src/app/login/page.tsx:115` — `globalThis.location.assign("/")` → `globalThis.location.assign("/dashboard")` | | |
| | — `frontend/src/app/register/page.tsx:122` — `router.replace("/")` → `router.replace("/dashboard")` | | |
| | — `frontend/src/components/jobs/job-detail-header.tsx:127` — `router.push("/")` → `router.push("/dashboard")` | | |
| | — `frontend/src/components/jobs/job-detail-header.tsx:148` — `href="/"` → `href="/dashboard"` | | |
| | — `frontend/src/components/layout/top-nav.tsx:56` — `{ href: "/", label: "Dashboard" }` → `{ href: "/dashboard", label: "Dashboard" }` | | |
| | — `frontend/src/components/layout/top-nav.tsx:82` — `if (href === "/")` special case → remove (dead code after Dashboard href change; `startsWith("/dashboard")` handles it correctly) | | |
| | — `frontend/src/components/layout/top-nav.tsx:128` — `href="/"` → `href="/dashboard"` | | |
| | — `frontend/src/components/jobs/job-detail-actions.tsx:71` — `router.push("/")` → `router.push("/dashboard")` | | |
| | — `frontend/src/components/onboarding/steps/base-resume-setup-step.tsx:443` — `router.replace("/")` → `router.replace("/dashboard")` | | |
| | — `frontend/src/components/onboarding/steps/review-step.tsx:396` — `router.replace("/")` → `router.replace("/dashboard")` | | |
| | | | |
| | **Modify E2E tests (14 files, 61 changes):** | | |
| | *Part A — `goto("/")` → `goto("/dashboard")` (52 instances across 13 files):* | | |
| | `job-discovery.spec.ts` (11), `chat.spec.ts` (9), `navigation.spec.ts` (6), `responsive.spec.ts` (6), `add-job.spec.ts` (6), `usage.spec.ts` (5), `onboarding.spec.ts` (3), `smoke.spec.ts` (1), `security-headers.spec.ts` (1), `accessibility.spec.ts` (1), `auth-session-settings.spec.ts` (1), `cross-tenant-isolation.spec.ts` (1), `admin.spec.ts` (1) | | |
| | *Part B — `toHaveURL("/")` → `toHaveURL("/dashboard")` (9 instances across 5 files):* | | |
| | `job-discovery.spec.ts` (3: lines 327, 377, 468), `onboarding.spec.ts` (3: lines 55, 226, 408), `admin.spec.ts` (1: line 43), `cross-tenant-isolation.spec.ts` (1: line 79), `auth-login-register.spec.ts` (1: line 57) | | |
| | | | |
| | **Run:** `cd frontend && npm test -- --run && npm run typecheck` then `npx playwright test` | | |
| | **Done when:** Dashboard renders at `/dashboard`. `/` shows placeholder. All unit + E2E tests pass. Login/register/nav/onboarding all redirect to `/dashboard`. | | |
| 2 | **Create Next.js middleware** *(implemented in proxy.ts — Next.js 16 uses proxy convention, not middleware)* | | ✅ 2026-03-03 |
| | **Read:** REQ-024 §5.2 (middleware spec). `frontend/tests/e2e/base-test.ts` (need to add auth cookie for E2E). | `req-reader, plan` | |
| | | | |
| | **Create:** `frontend/src/middleware.ts` | | |
| | — Check for `zentropy.session-token` cookie (presence only, no JWT validation) | | |
| | — `GET /` + cookie present → redirect to `/dashboard` | | |
| | — `GET /dashboard` + no cookie → redirect to `/login` | | |
| | — `GET /login` or `/register` + cookie present → redirect to `/dashboard` | | |
| | — All other routes → pass through | | |
| | — `config.matcher = ["/", "/dashboard", "/login", "/register"]` | | |
| | | | |
| | **Modify:** `frontend/tests/e2e/base-test.ts` | | |
| | — Add `page.context().addCookies([{ name: "zentropy.session-token", value: "test-session-token", domain: "localhost", path: "/" }])` before navigation | | |
| | — This ensures all authenticated E2E tests pass through middleware without redirect to `/login` | | |
| | — Cookie value can be any non-empty string (middleware only checks presence) | | |
| | | | |
| | **⚠️ `auth-login-register.spec.ts` WILL BREAK:** This file imports `test` from `./base-test` (line 11) and navigates to `/login` and `/register`. After base-test sets the auth cookie, middleware redirects these to `/dashboard` before any page JS runs — breaking all 7 tests. **Fix:** Add `await page.context().clearCookies()` as the first line of each test in this file (before `setupUnauthMocks`), or add a shared `test.beforeEach` that clears cookies. The `auth-session-settings.spec.ts` Route Protection tests already use this pattern (line 30). | | |
| | | | |
| | **⚠️ Cookie placement:** `addCookies()` must be placed in the base-test fixture **before** `await use(page)` so the cookie is present when individual tests call `page.goto()`. Verify the `domain` matches Playwright config's `baseURL` (typically `localhost`). | | |
| | | | |
| | **Run:** `cd frontend && npm test -- --run && npm run typecheck` then `npx playwright test` (full E2E to verify middleware doesn't break existing tests). | | |
| | **Done when:** Middleware routes correctly per REQ-024 §5.2 table. All existing E2E tests pass with the auth cookie in base-test. | | |
| 3 | **Phase 1 Gate** — Full test suite + push | `phase-gate` | ✅ 2026-03-03 |
| | Run: `cd backend && python -m pytest tests/ -v`. Then `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. Then `npx playwright test`. Push with SSH keep-alive. | | |

#### Phase 1 Notes

**Source code audit (completed during planning):** Found 11 references to `"/"` meaning "dashboard" across 7 source files. REQ-024 §5.3 only mentioned login/register — the additional references in `job-detail-header.tsx`, `top-nav.tsx` (3 refs: nav item href, isActive special case, rendered href), `job-detail-actions.tsx`, `base-resume-setup-step.tsx`, `review-step.tsx`, and `login/page.tsx:115` (`location.assign`) were discovered during plan audit. All must be updated in §1.

**E2E audit (completed during plan audit):** Found 61 total E2E changes needed across 14 files: 52 `goto("/")` instances + 9 `toHaveURL("/")` assertion instances. The `toHaveURL` assertions were missed in the initial plan and caught by audit. `auth-login-register.spec.ts` (not in the initial `goto` list) has a `toHaveURL("/")` at line 57 that also needs updating.

**E2E cookie management:** The base-test fixture currently mocks API routes but does NOT set cookies. After middleware is added (§2), navigating to `/dashboard` without a cookie triggers a redirect to `/login`, breaking all authenticated E2E tests. The fix is setting the `zentropy.session-token` cookie in the base-test fixture **before `await use(page)`**. Since middleware only checks cookie presence (not JWT validity), any non-empty string works.

**`auth-login-register.spec.ts` conflict:** This file imports from `./base-test` and tests login/register page flows. After §2 adds the auth cookie to base-test, middleware redirects `/login` and `/register` to `/dashboard`, breaking all 7 tests. Fix: add `clearCookies()` to each test (pattern already used in `auth-session-settings.spec.ts:30`).

**`isActive()` dead code cleanup:** `top-nav.tsx:82` has `if (href === "/") return pathname === "/"` — a special case to prevent `"/"` from matching every route via `startsWith`. After changing the Dashboard href to `"/dashboard"`, this branch is dead code. Remove it in §1 (the generic `startsWith("/dashboard")` handles the Dashboard correctly).

**§1 before §2 ordering:** §1 moves the dashboard and updates all references WITHOUT middleware. This ensures a green test state at each commit. §2 adds middleware + cookie setup together, maintaining the green state.

**Directory creation:** §1 creates `frontend/src/app/(main)/dashboard/` (new directory) and `frontend/src/app/(public)/` (new route group). Both are implicit in the file creation/move but noted here for clarity.

---

## Phase 2: Landing Page Components + Settings (REQ-024 §4.1–§4.5, §5.4–§5.5, §6.1)

**Status:** ⬜

*Build all 5 landing page components with unit tests. Compose the full landing page. Add Legal section to Settings page.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-024 §4.1–§4.5 (page structure), §5.4–§5.5 (components), §5.6 (test IDs), §6.1 (unit tests). |
| 🧪 **TDD** | Write tests first for each component — follow `zentropy-tdd` |
| 🔧 **Create** | 5 components + 5 test files + page composition + settings legal section |
| ✅ **Verify** | `npm test -- --run`, `npm run typecheck` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `ui-reviewer` (parallel) |
| 📝 **Commit** | One commit per subtask |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 4 | **Landing page components + unit tests** | | ⬜ |
| | **Read:** REQ-024 §4.1–§4.5 (page structure), §5.5 (components table), §5.6 (test IDs), §5.7 (assets), §5.8 (responsive breakpoints), §6.1 (unit test specs). Read an existing component for Tailwind/shadcn patterns (e.g., `frontend/src/components/usage/balance-card.tsx`). | `req-reader, tdd, plan` | |
| | | | |
| | **TDD — write tests first, then implement each component:** | | |
| | | | |
| | **Component 1: `LandingNav`** (`(public)/components/landing-nav.tsx` + `.test.tsx`) | | |
| | — Test: logo renders with alt text, "Get Started" links to `/register`, "Sign In" links to `/login` | | |
| | — Impl: `<header>` with logo via `next/image`, sign-in text link, amber CTA button | | |
| | — `data-testid`: `landing-nav`, `landing-logo` | | |
| | | | |
| | **Component 2: `HeroSection`** (`(public)/components/hero-section.tsx` + `.test.tsx`) | | |
| | — Test: `<h1>` headline renders, CTA button links to `/register`, sign-in link present, graphic placeholder present | | |
| | — Impl: `<section>` with h1 headline, subtitle, CTA button, secondary sign-in link, gradient placeholder div | | |
| | — `data-testid`: `hero-section`, `hero-cta`, `hero-sign-in`, `hero-graphic` | | |
| | | | |
| | **Component 3: `FeatureCards`** (`(public)/components/feature-cards.tsx` + `.test.tsx`) | | |
| | — Test: 4 cards render (`data-testid="feature-card-0"` through `feature-card-3`), each has title text | | |
| | — Impl: `<section>` with 4 cards, Lucide icons (UserCircle, Search, FileText, BarChart3), responsive grid | | |
| | — `data-testid`: `feature-cards`, `feature-card-{0-3}` | | |
| | — Layout: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4` | | |
| | | | |
| | **Component 4: `HowItWorks`** (`(public)/components/how-it-works.tsx` + `.test.tsx`) | | |
| | — Test: 3 steps render (`data-testid="how-it-works-step-0"` through `step-2`), each has title text | | |
| | — Impl: `<section>` with 3 numbered steps, Lucide icons (UserPlus, Radar, Sparkles) | | |
| | — `data-testid`: `how-it-works`, `how-it-works-step-{0-2}` | | |
| | | | |
| | **Component 5: `LandingFooter`** (`(public)/components/landing-footer.tsx` + `.test.tsx`) | | |
| | — Test: copyright text `"© 2026 Zentropy Scout"`, ToS link, Privacy link, Sign In link | | |
| | — Impl: `<footer>` with copyright left, link row right | | |
| | — `data-testid`: `landing-footer`, `footer-tos`, `footer-privacy` | | |
| | — ToS and Privacy links are placeholder `#` hrefs until PBI #26 | | |
| | | | |
| | **Update `(public)/page.tsx`** — replace placeholder with full composition: | | |
| | — Import and render: LandingNav → HeroSection → FeatureCards → HowItWorks → LandingFooter | | |
| | — Wrap in `<div data-testid="landing-page">` | | |
| | — Use semantic HTML with `aria-label` attributes on sections (e.g., `aria-label="Features"`) | | |
| | | | |
| | **Assets:** Logo via `next/image` from `/zentropy_logo.png`. Hero placeholder: `<div>` with `bg-gradient-to-br from-primary/20 via-card to-primary/10` (~400×300). Icons: Lucide React (existing dep). | | |
| | | | |
| | **Run:** `cd frontend && npm test -- --run && npm run typecheck` | | |
| | **Done when:** All 5 component unit tests pass. Landing page at `/` renders all sections. TypeScript clean. | | |
| 5 | **Settings legal section + unit test update** | | ⬜ |
| | **Read:** REQ-024 §5.4 (settings legal spec), §5.6 (test IDs). Read `frontend/src/components/settings/settings-page.tsx` and `settings-page.test.tsx`. | `req-reader, tdd, plan` | |
| | | | |
| | **TDD:** Add test to existing `settings-page.test.tsx`: | | |
| | — `data-testid="settings-legal"` card is present | | |
| | — "Terms of Service" and "Privacy Policy" link text visible | | |
| | | | |
| | **Modify:** `frontend/src/components/settings/settings-page.tsx` | | |
| | — Add "Legal" Card after the "About" card, following existing Card pattern | | |
| | — Card contains ToS and Privacy Policy anchor links (placeholder `#` hrefs) | | |
| | — `data-testid="settings-legal"` | | |
| | | | |
| | **Run:** `cd frontend && npm test -- --run settings-page && npm run typecheck` | | |
| | **Done when:** Settings page renders 5 cards (4 existing + Legal). Test passes. TypeScript clean. | | |
| 6 | **Phase 2 Gate** — Full test suite + push | `phase-gate` | ⬜ |
| | Run: `cd backend && python -m pytest tests/ -v`. Then `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. Then `npx playwright test`. Push with SSH keep-alive. | | |

#### Phase 2 Notes

**Component colocation:** Test files live alongside components in `(public)/components/` following existing project convention (e.g., `packs-tab.test.tsx` alongside `packs-tab.tsx`).

**Responsive approach:** Use existing Tailwind breakpoints (`sm:`, `md:`, `lg:`). Feature cards: single column on mobile → 2-col grid on tablet (`sm:grid-cols-2`) → 4-col on desktop (`lg:grid-cols-4`). Hero: stacked on mobile → text-left + graphic-right on desktop.

**Hero graphic placeholder:** A `<div>` with brand gradient, ~400×300px on desktop. `data-testid="hero-graphic"` for test targeting. Will be replaced with actual asset when sourced by user (see REQ-024 §2.4).

**ui-reviewer:** Include in §4 review since the subtask creates frontend `.tsx` components.

---

## Phase 3: E2E Tests (REQ-024 §6.2)

**Status:** ⬜

*Playwright E2E tests for landing page rendering, CTA navigation, and auth-based middleware routing.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-024 §6.2 (E2E test scenarios), §5.6 (test IDs). Read `base-test.ts` and an existing E2E spec for fixture patterns. |
| 🧪 **TDD** | Write E2E tests following `zentropy-playwright` patterns |
| ✅ **Verify** | `npx playwright test tests/e2e/landing.spec.ts` |
| 🔍 **Review** | `code-reviewer` (parallel) |
| 📝 **Commit** | `test(e2e): add landing page and auth routing tests` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 7 | **Landing page + auth routing E2E tests** | | ⬜ |
| | **Read:** REQ-024 §6.2 (8 test scenarios), §5.6 (test IDs). `frontend/tests/e2e/base-test.ts` (fixture pattern). An existing spec (e.g., `smoke.spec.ts`) for structure reference. | `req-reader, playwright, e2e, plan` | |
| | | | |
| | **Create:** `frontend/tests/e2e/landing.spec.ts` | | |
| | | | |
| | **8 test scenarios (from REQ-024 §6.2):** | | |
| | | | |
| | **Unauthenticated tests (NO auth cookie, import `test` from `@playwright/test`):** | | |
| | 1. Unauthenticated user sees landing page at `/` — navigate to `/`, `data-testid="landing-page"` visible, hero headline present | | |
| | 2. CTA button navigates to register — click `hero-cta`, URL changes to `/register` | | |
| | 3. Nav Sign In link navigates to login — click "Sign In" in nav, URL changes to `/login` | | |
| | 5. Unauthenticated user redirected from `/dashboard` to `/login` — navigate to `/dashboard`, URL becomes `/login` | | |
| | 8. Landing page does not show app shell — navigate to `/` unauthenticated, sidebar and app nav are NOT present | | |
| | | | |
| | **Authenticated tests (WITH auth cookie + API mocks, import `test` from `base-test`):** | | |
| | 4. Authenticated user redirected from `/` to `/dashboard` — set cookie, navigate to `/`, URL becomes `/dashboard` | | |
| | 6. Dashboard renders at `/dashboard` — navigate to `/dashboard`, dashboard content visible | | |
| | 7. Settings page has Legal section — navigate to settings, `data-testid="settings-legal"` visible with ToS and Privacy links | | |
| | | | |
| | **⚠️ Cookie management:** Unauthenticated tests must NOT use the base-test fixture (which sets the auth cookie). Import `test` from `@playwright/test` directly for tests 1, 2, 3, 5, 8. For authenticated tests 4, 6, 7, use the base-test fixture which provides the cookie + API mocks. | | |
| | | | |
| | **Run:** `cd frontend && npx playwright test tests/e2e/landing.spec.ts` | | |
| | **Done when:** All 8 E2E test scenarios pass. | | |
| 8 | **Phase 3 Gate (Final)** — Full test suite + push | `phase-gate` | ⬜ |
| | Run full suite: `cd backend && python -m pytest tests/ -v`. `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. `cd frontend && npx playwright test`. Push with SSH keep-alive. Update this plan status to ✅ Complete. Update `CLAUDE.md` Current Status section. Update backlog PBI #20 to completed. | | |

---

## Critical Files Reference

### Source files referencing `"/"` as dashboard (7 files, 11 references — all need `/dashboard` in §1)

| File | Line | Current | Change To |
|------|------|---------|-----------|
| `frontend/src/app/login/page.tsx` | 92 | `router.replace("/")` | `router.replace("/dashboard")` |
| `frontend/src/app/login/page.tsx` | 115 | `globalThis.location.assign("/")` | `globalThis.location.assign("/dashboard")` |
| `frontend/src/app/register/page.tsx` | 122 | `router.replace("/")` | `router.replace("/dashboard")` |
| `frontend/src/components/jobs/job-detail-header.tsx` | 127 | `router.push("/")` | `router.push("/dashboard")` |
| `frontend/src/components/jobs/job-detail-header.tsx` | 148 | `href="/"` | `href="/dashboard"` |
| `frontend/src/components/layout/top-nav.tsx` | 56 | `{ href: "/", label: "Dashboard" }` | `{ href: "/dashboard", label: "Dashboard" }` |
| `frontend/src/components/layout/top-nav.tsx` | 82 | `if (href === "/") return pathname === "/"` | Remove (dead code — see Phase 1 Notes) |
| `frontend/src/components/layout/top-nav.tsx` | 128 | `href="/"` | `href="/dashboard"` |
| `frontend/src/components/jobs/job-detail-actions.tsx` | 71 | `router.push("/")` | `router.push("/dashboard")` |
| `frontend/src/components/onboarding/steps/base-resume-setup-step.tsx` | 443 | `router.replace("/")` | `router.replace("/dashboard")` |
| `frontend/src/components/onboarding/steps/review-step.tsx` | 396 | `router.replace("/")` | `router.replace("/dashboard")` |

### E2E test files (14 files, 61 total changes in §1)

**Part A — `goto("/")` → `goto("/dashboard")` (52 instances across 13 files):**

| File | Count |
|------|-------|
| `job-discovery.spec.ts` | 11 |
| `chat.spec.ts` | 9 |
| `navigation.spec.ts` | 6 |
| `responsive.spec.ts` | 6 |
| `add-job.spec.ts` | 6 |
| `usage.spec.ts` | 5 |
| `onboarding.spec.ts` | 3 |
| `smoke.spec.ts` | 1 |
| `security-headers.spec.ts` | 1 |
| `accessibility.spec.ts` | 1 |
| `auth-session-settings.spec.ts` | 1 |
| `cross-tenant-isolation.spec.ts` | 1 |
| `admin.spec.ts` | 1 |
| **Subtotal** | **52** |

**Part B — `toHaveURL("/")` → `toHaveURL("/dashboard")` (9 instances across 5 files):**

| File | Lines | Count |
|------|-------|-------|
| `job-discovery.spec.ts` | 327, 377, 468 | 3 |
| `onboarding.spec.ts` | 55, 226, 408 | 3 |
| `admin.spec.ts` | 43 | 1 |
| `cross-tenant-isolation.spec.ts` | 79 | 1 |
| `auth-login-register.spec.ts` | 57 | 1 |
| **Subtotal** | | **9** |

**Combined total: 61 changes across 14 unique files** (13 from Part A + `auth-login-register.spec.ts` from Part B only).

### New files created by this plan

| File | Phase | Purpose |
|------|-------|---------|
| `frontend/src/middleware.ts` | §2 | Auth-based routing |
| `frontend/src/app/(public)/layout.tsx` | §1 | Minimal public page wrapper |
| `frontend/src/app/(public)/page.tsx` | §1 (placeholder), §4 (full) | Landing page composition |
| `frontend/src/app/(public)/components/landing-nav.tsx` | §4 | Top nav with logo + CTA |
| `frontend/src/app/(public)/components/hero-section.tsx` | §4 | Hero headline + CTA + graphic |
| `frontend/src/app/(public)/components/feature-cards.tsx` | §4 | 4 feature highlight cards |
| `frontend/src/app/(public)/components/how-it-works.tsx` | §4 | 3-step walkthrough |
| `frontend/src/app/(public)/components/landing-footer.tsx` | §4 | Footer with links + copyright |
| `frontend/src/app/(public)/components/landing-nav.test.tsx` | §4 | Unit tests |
| `frontend/src/app/(public)/components/hero-section.test.tsx` | §4 | Unit tests |
| `frontend/src/app/(public)/components/feature-cards.test.tsx` | §4 | Unit tests |
| `frontend/src/app/(public)/components/how-it-works.test.tsx` | §4 | Unit tests |
| `frontend/src/app/(public)/components/landing-footer.test.tsx` | §4 | Unit tests |
| `frontend/tests/e2e/landing.spec.ts` | §7 | Playwright E2E tests |

---

## Verification Checklist (after all phases)

1. ✅ `/` renders landing page for unauthenticated visitors
2. ✅ `/` redirects to `/dashboard` for authenticated users
3. ✅ `/dashboard` renders Dashboard for authenticated users
4. ✅ `/dashboard` redirects to `/login` for unauthenticated users
5. ✅ Login/register pages redirect to `/dashboard` (not `/`) after auth
6. ✅ Login/register pages redirect to `/dashboard` for already-authenticated users (via middleware)
7. ✅ Landing page has: nav with logo/CTA, hero, 4 feature cards, 3-step walkthrough, footer
8. ✅ Footer has ToS/Privacy placeholder links
9. ✅ Settings page has Legal card with ToS/Privacy links
10. ✅ Landing page does NOT show app shell (sidebar, nav bar)
11. ✅ All nav links, job-detail back buttons, `location.assign`, and onboarding completions navigate to `/dashboard` (not `/`)
12. ✅ All 61 E2E changes applied (52 `goto("/")` + 9 `toHaveURL("/")` → `/dashboard`)
13. ✅ `auth-login-register.spec.ts` clears cookies before each test (not broken by base-test cookie)
14. ✅ `top-nav.tsx` `isActive()` dead code (`if (href === "/")`) removed
15. ✅ `cd frontend && npm test -- --run` — all pass
16. ✅ `cd frontend && npm run typecheck` — zero errors
17. ✅ `cd frontend && npm run lint` — zero errors
18. ✅ `cd frontend && npx playwright test` — all pass
19. ✅ `cd backend && python -m pytest tests/ -v` — all pass (no backend changes, regression check)

---

## Summary

| Phase | Subtasks | New Files | Modified Files | Commit Message |
|-------|----------|-----------|----------------|----------------|
| 1: Route Infrastructure | §1 + §2 + gate | 3 (layout, page, middleware) | 22 (7 source + 14 E2E + base-test) | `feat(frontend): add public route group, move dashboard to /dashboard` + `feat(frontend): add auth-based middleware routing` |
| 2: Landing Page + Settings | §4 + §5 + gate | 10 (5 components + 5 tests) | 2 (page.tsx full, settings-page.tsx + test) | `feat(frontend): add landing page components` + `feat(frontend): add legal section to settings` |
| 3: E2E Tests | §7 + gate | 1 (landing.spec.ts) | 0 | `test(e2e): add landing page and auth routing tests` |
| **Total** | **8 subtasks** | **14 new files** | **~24 modified files** | **5 commits** |
