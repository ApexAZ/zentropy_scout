# REQ-024: Public Landing Page

**Status:** Not Started
**Version:** 0.2
**PRD Reference:** §1 (product vision)
**Backlog Item:** #20
**Last Updated:** 2026-03-03

---

## 1. Overview

Zentropy Scout needs a public-facing landing page — the first thing a new visitor sees. Authenticated users bypass it entirely and go straight to the app dashboard.

The page is dark-themed (matching the authenticated app's dark slate palette), features the Zentropy Scout logo (white + amber wordmark), and has a single goal: convert visitors into sign-ups.

**Why this REQ exists:** The current app serves the Dashboard at `/` inside the `(main)` route group. There is no public-facing page for unauthenticated visitors — they are redirected to `/login`. This REQ adds a landing page at `/`, moves the Dashboard to `/dashboard`, and introduces Next.js middleware for auth-based routing.

**Scope boundary:** This REQ covers the landing page, the Dashboard route move, middleware creation, and a Legal section in Settings. It does not change the Dashboard's content, the onboarding flow, or any backend endpoints.

### 1.1 What Changes

| Change | From | To |
|--------|------|----|
| `/` route (unauthenticated) | Redirects to `/login` | Renders public landing page |
| `/` route (authenticated) | Renders Dashboard | Redirects to `/dashboard` |
| Dashboard URL | `/` via `(main)/page.tsx` | `/dashboard` via `(main)/dashboard/page.tsx` |
| Auth routing | Client-side (`useSession` + `router.replace`) | Server-side middleware (cookie check) |
| Login/register redirect target | `router.replace("/")` | `router.replace("/dashboard")` |
| Settings page | 4 sections (Account, Job Sources, Agent Config, About) | 5 sections (+ Legal with ToS/Privacy links) |

### 1.2 What Does NOT Change

- **Authenticated app layout and navigation** — `(main)/layout.tsx` (AppShell with OnboardingGate) is unchanged
- **Dashboard content** — `DashboardTabs` component and its behavior are unchanged; only the route path moves
- **Onboarding flow** — no skip-onboarding in this REQ
- **Auth endpoints or logic** — existing sign-in/sign-up pages remain at `/login` and `/register` (root-level routes, not in a route group)
- **Backend** — no API changes required
- **Root layout providers** — `AuthProvider > QueryProvider > SSEProvider > ChatProvider` remain in root layout. `AuthProvider` handles unauthenticated state gracefully (sets status to `"unauthenticated"`). SSE and Chat providers are inert without an authenticated session — no visible UI on the landing page.

### 1.3 Impact on Other Routes

| Route | Current Behavior | New Behavior |
|-------|-----------------|--------------|
| `/` (unauth) | Redirect to `/login` | Landing page |
| `/` (auth) | Dashboard | Redirect to `/dashboard` |
| `/dashboard` (auth) | Does not exist | Dashboard (moved from `/`) |
| `/dashboard` (unauth) | Does not exist | Redirect to `/login` (via middleware) |
| `/login` (auth) | `router.replace("/")` → Dashboard | `router.replace("/dashboard")` → Dashboard (no double-redirect) |
| `/register` (auth) | `router.replace("/")` → Dashboard | `router.replace("/dashboard")` → Dashboard (no double-redirect) |

---

## 2. Design Decisions

### 2.1 Routing: Unauthenticated Landing vs Authenticated App

**Decision:** `/` renders the landing page for unauthenticated visitors. Authenticated users hitting `/` are redirected to `/dashboard`.

**Why:**
1. Standard SaaS pattern (Resend, Linear, Vercel, SonarCloud all do this)
2. Landing page is a marketing surface — logged-in users don't need to see it
3. Clean separation: public content has no auth layout (no sidebar, no nav)

**Implementation:** Next.js middleware (new file) checks for the `zentropy.session-token` cookie. Cookie presence = authenticated (server-side check, no JWT validation — the `AuthProvider` handles full validation client-side). Middleware redirects authenticated users from `/` to `/dashboard` and unauthenticated users from `/dashboard` to `/login`.

### 2.2 Dashboard Move to `/dashboard`

**Decision:** Move the Dashboard from `/` to `/dashboard` to free up `/` for the landing page.

**Why:**
1. Next.js App Router does not allow two route groups to both claim `/` — a `(public)/page.tsx` and `(main)/page.tsx` both resolving to `/` causes a build error
2. `/dashboard` is the standard SaaS convention (Linear, Vercel, Notion all use `/dashboard` or similar)
3. Clean URL semantics: `/` = public, `/dashboard` = authenticated workspace

**Implementation:** Move `frontend/src/app/(main)/page.tsx` to `frontend/src/app/(main)/dashboard/page.tsx`. Update login/register redirect targets from `"/"` to `"/dashboard"`. No content changes to the Dashboard component itself.

### 2.3 No Footer in the Authenticated App — ToS/Privacy in Settings

**Decision:** Footer with ToS/Privacy links appears only on the landing page. The authenticated app has no footer. Instead, ToS and Privacy Policy links are added to the existing Settings page as a "Legal" card section.

**Why:**
1. Modern SaaS convention — Resend, Linear, Vercel, SonarCloud have no in-app footer
2. Every pixel in the app is workspace
3. ToS/Privacy links in Settings is the standard pattern for authenticated access to legal documents

### 2.4 Hero Graphic

**Decision:** Include an eye-catching graphic or illustration in the hero section. The specific asset will be sourced separately by the user from design resources (Behance, Dribbble, unDraw, Storyset, or custom).

**Placeholder approach:** The implementation will include a placeholder area for the graphic with defined dimensions and positioning. Use a subtle gradient or abstract shape using the brand palette as a temporary visual. The actual graphic will be swapped in when the asset is ready. This allows the page structure and all other content to be built and tested without blocking on asset creation.

### 2.5 Dark Theme

**Decision:** The landing page uses the same dark slate background as the authenticated app.

**Why:**
1. Brand consistency — visitor's first impression matches the product experience
2. The logo (white "zen" + amber "tropy") is designed for dark backgrounds
3. Amber-on-dark is distinctive and professional

**Palette reference (from `globals.css`):**
- Background: `#1e2535` (dark slate)
- Text: `#f5f5f5` (foreground)
- Primary/CTA: `#f0a500` (amber gold)
- Card surfaces: `#253044` (elevated dark)
- Muted text: `#94a3b8` (slate gray)
- Borders: `#3a4a63` (subtle slate)

---

## 3. Dependencies

### 3.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-012 | Foundation | Frontend app structure, Tailwind, shadcn/ui, route groups |
| REQ-013 | Foundation | Auth cookie (`zentropy.session-token`), sign-in/sign-up pages |

### 3.2 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| PBI #26 (ToS/Privacy) | Integration | ToS/Privacy links in footer and Settings are placeholders until #26 is built |

### 3.3 Prerequisite Implementation Order

```
REQ-012 (Frontend Application) [✅ Implemented]
    ↓
REQ-013 (Authentication) [✅ Implemented]
    ↓
REQ-024 (Landing Page — THIS DOCUMENT)
    ↓
PBI #26 (ToS/Privacy — future)
```

---

## 4. Page Structure

### 4.1 Navigation Bar

Minimal top bar on the landing page (not the authenticated app's sidebar):
- **Left:** Zentropy Scout logo (`/zentropy_logo.png`) — links to `/` (top of page). Use `next/image` component with `alt="Zentropy Scout"`.
- **Right:** "Sign In" text link (links to `/login`) + "Get Started" primary button (amber CTA, links to `/register`)
- **Mobile:** All three elements (logo, Sign In, Get Started) remain visible in a single row. No hamburger menu — the nav is simple enough to fit on mobile without collapsing.

### 4.2 Hero Section

The first and most prominent section. Occupies the viewport above the fold.

- **Headline:** One strong line explaining the product value (e.g., "Your AI-Powered Job Search Assistant"). Rendered as `<h1>`.
- **Subtitle:** 1–2 sentences elaborating (e.g., "Build your professional persona, find matching jobs, and generate tailored resumes and cover letters — all powered by AI."). Rendered as `<p>` in muted foreground.
- **CTA button:** "Get Started Free" — amber primary button, links to `/register`
- **Secondary link:** "Already have an account? Sign in" — text link to `/login`
- **Hero graphic:** Positioned to the right of the text on desktop, below on mobile. Placeholder div with gradient background until asset is sourced (see §2.4).

### 4.3 Feature Highlights

4 cards showcasing core capabilities. Each card has a Lucide icon, a short title, and a one-line description.

| Icon | Title | Description |
|------|-------|-------------|
| `UserCircle` | Build Your Persona | Create a comprehensive professional profile that AI uses to tailor everything to you. |
| `Search` | Smart Job Matching | AI analyzes job postings and scores them against your skills, experience, and preferences. |
| `FileText` | Tailored Documents | Generate customized resumes and cover letters targeted to each specific job posting. |
| `BarChart3` | Track Applications | Manage your entire job search pipeline from discovery to offer in one place. |

Layout: horizontal row on desktop (4 columns), 2×2 grid on tablet, vertical stack on mobile.

### 4.4 How It Works

3-step visual walkthrough. Simple numbered steps with Lucide icons.

| Step | Icon | Title | Description |
|------|------|-------|-------------|
| 1 | `UserPlus` | Build your persona | Tell us about your skills, experience, and what you're looking for. |
| 2 | `Radar` | Scout finds matches | AI analyzes job postings and ranks them by fit. |
| 3 | `Sparkles` | Generate & apply | Get tailored resumes and cover letters for your top matches. |

Layout: horizontal row with step numbers on desktop, vertical stack on mobile.

### 4.5 Footer

Minimal footer at the bottom of the landing page only (not in the authenticated app).

- **Left:** `© 2026 Zentropy Scout`
- **Right:** Links — "Sign In" | "Terms of Service" | "Privacy Policy"
- ToS and Privacy links are placeholder `#` hrefs until PBI #26 is implemented

---

## 5. Frontend Implementation

### 5.1 Route Structure

```
frontend/src/app/
├── (public)/                      # New route group — landing page only
│   ├── layout.tsx                 # Minimal wrapper (no sidebar, no app nav)
│   └── page.tsx                   # Landing page — composes all sections
├── (main)/                        # Existing — authenticated app
│   ├── layout.tsx                 # AppShell with OnboardingGate (unchanged)
│   ├── dashboard/
│   │   └── page.tsx               # Dashboard (MOVED from (main)/page.tsx)
│   ├── settings/
│   ...
├── login/                         # Existing — root-level route (not in a group)
├── register/                      # Existing — root-level route (not in a group)
├── onboarding/                    # Existing — root-level route
├── layout.tsx                     # Root layout with providers (unchanged)
└── middleware.ts                   # NEW — auth-based routing
```

**Route conflict resolution:** The current Dashboard lives at `(main)/page.tsx` which resolves to `/`. The landing page also needs `/`. Since Next.js does not allow two route groups to both claim the same path, the Dashboard is moved to `(main)/dashboard/page.tsx` (resolves to `/dashboard`). The `(public)/page.tsx` then owns `/` without conflict.

**`(public)/layout.tsx`:** Minimal wrapper nested inside the root layout. The root layout already provides all providers (`AuthProvider`, `QueryProvider`, `SSEProvider`, `ChatProvider`). The `(public)` layout is just:

```tsx
export default function PublicLayout({ children }: { children: React.ReactNode }) {
    return <main className="min-h-screen bg-background">{children}</main>;
}
```

`LandingNav` and `LandingFooter` are composed inside `page.tsx`, not the layout (the layout exists only to provide the wrapper and prevent the `(main)` AppShell from rendering).

### 5.2 Middleware (New File)

Create `frontend/src/middleware.ts` — this file does NOT currently exist.

**Behavior:**

| Request | Cookie Present? | Action |
|---------|----------------|--------|
| `GET /` | Yes | Redirect to `/dashboard` |
| `GET /` | No | Allow through (landing page) |
| `GET /dashboard` | No | Redirect to `/login` |
| `GET /login` | Yes | Redirect to `/dashboard` |
| `GET /register` | Yes | Redirect to `/dashboard` |
| All other routes | — | Pass through (no middleware action) |

**Cookie detection:** Check for `zentropy.session-token` cookie existence. This is a presence check only — no JWT validation on the server side. Full JWT validation happens client-side in `AuthProvider`. If the cookie exists but is expired/invalid, `AuthProvider` will catch it and redirect to `/login`.

**Matcher config:** The middleware runs only on specific routes to avoid intercepting API calls, static assets, and Next.js internals:

```typescript
export const config = {
    matcher: ["/", "/dashboard", "/login", "/register"],
};
```

### 5.3 Dashboard Route Move

Move the Dashboard from `/` to `/dashboard`:

1. Move `frontend/src/app/(main)/page.tsx` → `frontend/src/app/(main)/dashboard/page.tsx`
2. Update `frontend/src/app/login/page.tsx`: change `router.replace("/")` → `router.replace("/dashboard")`
3. Update `frontend/src/app/register/page.tsx`: change `router.replace("/")` → `router.replace("/dashboard")`
4. Update any E2E tests that navigate to `/` expecting the Dashboard

### 5.4 Settings Page — Legal Section

Add a "Legal" card to `frontend/src/components/settings/settings-page.tsx` (the component, not the route file). Follow the existing pattern of Card sections (Account, Job Sources, Agent Config, About).

Add after the "About" card:

```tsx
<Card data-testid="settings-legal">
    <CardHeader>
        <CardTitle>Legal</CardTitle>
    </CardHeader>
    <CardContent className="space-y-2">
        <a href="#" className="text-sm text-primary hover:underline block">Terms of Service</a>
        <a href="#" className="text-sm text-primary hover:underline block">Privacy Policy</a>
    </CardContent>
</Card>
```

ToS and Privacy links are placeholder `#` hrefs until PBI #26 provides real content and routes.

### 5.5 Components

New components for the landing page:

| Component | File | Purpose |
|-----------|------|---------|
| `LandingNav` | `(public)/components/landing-nav.tsx` | Top navigation bar with logo + sign-in/CTA |
| `HeroSection` | `(public)/components/hero-section.tsx` | Hero headline, subtitle, CTA, graphic placeholder |
| `FeatureCards` | `(public)/components/feature-cards.tsx` | 4 feature highlight cards |
| `HowItWorks` | `(public)/components/how-it-works.tsx` | 3-step walkthrough |
| `LandingFooter` | `(public)/components/landing-footer.tsx` | Footer with links and copyright |

All components use existing Tailwind classes and brand palette tokens. No new UI library dependencies.

**Semantic HTML:** Use `<header>` for nav, `<main>` for content, `<footer>` for footer, `<section>` for each content block. Add `aria-label` attributes to each `<section>` (e.g., `aria-label="Features"`, `aria-label="How it works"`).

### 5.6 Test IDs

| Element | `data-testid` |
|---------|---------------|
| Landing page wrapper | `landing-page` |
| Landing nav | `landing-nav` |
| Logo (in nav) | `landing-logo` |
| Hero section | `hero-section` |
| Hero CTA button | `hero-cta` |
| Hero sign-in link | `hero-sign-in` |
| Hero graphic placeholder | `hero-graphic` |
| Feature cards container | `feature-cards` |
| Individual feature card | `feature-card-{index}` (0-based) |
| How it works container | `how-it-works` |
| Individual step | `how-it-works-step-{index}` (0-based) |
| Landing footer | `landing-footer` |
| Footer ToS link | `footer-tos` |
| Footer privacy link | `footer-privacy` |
| Settings legal card | `settings-legal` |

### 5.7 Assets

- **Logo:** `frontend/public/zentropy_logo.png` (existing). Use `next/image` with `alt="Zentropy Scout"`. Render at a reasonable nav height (e.g., `height={32}` with proportional width).
- **Hero graphic:** Placeholder `<div>` with gradient background using brand colors (`bg-gradient-to-br from-primary/20 to-accent/30` or similar). Defined dimensions (~400×300 on desktop). Swapped for real asset later.
- **Icons:** Lucide React (existing dependency) for feature cards and how-it-works steps.

### 5.8 Responsive Breakpoints

Follow existing Tailwind breakpoints:
- **Mobile** (`< 640px`): Single column, stacked sections, nav remains single row
- **Tablet** (`640px–1024px`): 2-column grid for features
- **Desktop** (`> 1024px`): Full horizontal layouts, hero text + graphic side by side

---

## 6. Testing

### 6.1 Unit Tests (Vitest)

| Test | File | What It Verifies |
|------|------|-----------------|
| `LandingNav` renders logo and CTA | `landing-nav.test.tsx` | Logo image with alt text, "Get Started" button links to `/register`, "Sign In" links to `/login` |
| `HeroSection` renders headline and CTA | `hero-section.test.tsx` | `data-testid="hero-section"` present, CTA button with `data-testid="hero-cta"` links to `/register` |
| `FeatureCards` renders 4 cards | `feature-cards.test.tsx` | 4 cards rendered (`data-testid="feature-card-0"` through `feature-card-3`), each has title and description text |
| `HowItWorks` renders 3 steps | `how-it-works.test.tsx` | 3 steps rendered (`data-testid="how-it-works-step-0"` through `step-2`), each has title and description |
| `LandingFooter` renders links | `landing-footer.test.tsx` | Copyright text, ToS link (`data-testid="footer-tos"`), Privacy link (`data-testid="footer-privacy"`), Sign In link |
| Settings Legal section renders | Existing `settings-page.test.tsx` | `data-testid="settings-legal"` present, ToS and Privacy Policy links visible |

### 6.2 E2E Tests (Playwright)

| Test | What It Verifies |
|------|-----------------|
| Unauthenticated user sees landing page at `/` | Navigate to `/`, `data-testid="landing-page"` visible, hero headline present |
| CTA button navigates to register page | Click `data-testid="hero-cta"`, URL changes to `/register` |
| Nav Sign In link navigates to login page | Click "Sign In" in nav, URL changes to `/login` |
| Authenticated user redirected from `/` to `/dashboard` | Set auth cookie mock, navigate to `/`, URL becomes `/dashboard` |
| Unauthenticated user redirected from `/dashboard` to `/login` | Navigate to `/dashboard` without auth, URL becomes `/login` |
| Dashboard renders at `/dashboard` | Authenticate, navigate to `/dashboard`, dashboard content visible |
| Settings page has Legal section | Navigate to settings, `data-testid="settings-legal"` visible with ToS and Privacy links |
| Landing page does not show app shell | Navigate to `/` unauthenticated, sidebar and app nav are NOT present |

### 6.3 Existing Test Updates

Tests that navigate to `/` expecting the Dashboard need to be updated to use `/dashboard`:
- Search all E2E test files for `goto("/")` or navigation to `/` and update to `/dashboard`
- Search all unit tests for route references to `/` in the context of the Dashboard

### 6.4 Visual / Manual Testing

- Verify logo renders correctly on dark background (white "zen" + amber "tropy" visible)
- Verify amber CTA button has sufficient contrast on dark slate background (WCAG 2.1 AA: 4.5:1 for normal text, 3:1 for large text — amber `#f0a500` on dark `#1e2535` should pass for large text/buttons)
- Verify placeholder graphic area is visible and properly sized
- Verify footer ToS/Privacy links are present (even as `#` placeholders)
- Verify no chat UI, SSE indicators, or app shell elements appear on landing page

---

## 7. Files Modified

| File | Change |
|------|--------|
| `frontend/src/middleware.ts` | **New.** Auth-based routing: `/` redirect for authenticated users, `/dashboard` protection, login/register redirect for authenticated users. |
| `frontend/src/app/(public)/layout.tsx` | **New.** Minimal wrapper layout for public pages. |
| `frontend/src/app/(public)/page.tsx` | **New.** Landing page — composes LandingNav, HeroSection, FeatureCards, HowItWorks, LandingFooter. |
| `frontend/src/app/(public)/components/landing-nav.tsx` | **New.** Top nav with logo + sign-in/CTA. |
| `frontend/src/app/(public)/components/hero-section.tsx` | **New.** Hero section with headline, subtitle, CTA, graphic placeholder. |
| `frontend/src/app/(public)/components/feature-cards.tsx` | **New.** 4 feature highlight cards with Lucide icons. |
| `frontend/src/app/(public)/components/how-it-works.tsx` | **New.** 3-step walkthrough with Lucide icons. |
| `frontend/src/app/(public)/components/landing-footer.tsx` | **New.** Footer with links and copyright. |
| `frontend/src/app/(main)/dashboard/page.tsx` | **Moved** from `frontend/src/app/(main)/page.tsx`. No content changes. |
| `frontend/src/app/(main)/page.tsx` | **Deleted.** Dashboard moved to `dashboard/page.tsx`. |
| `frontend/src/app/login/page.tsx` | **Modified.** Change `router.replace("/")` to `router.replace("/dashboard")`. |
| `frontend/src/app/register/page.tsx` | **Modified.** Change `router.replace("/")` to `router.replace("/dashboard")`. |
| `frontend/src/components/settings/settings-page.tsx` | **Modified.** Add Legal card with ToS/Privacy placeholder links. |
| `frontend/src/app/(public)/components/landing-nav.test.tsx` | **New.** Unit tests for LandingNav. |
| `frontend/src/app/(public)/components/hero-section.test.tsx` | **New.** Unit tests for HeroSection. |
| `frontend/src/app/(public)/components/feature-cards.test.tsx` | **New.** Unit tests for FeatureCards. |
| `frontend/src/app/(public)/components/how-it-works.test.tsx` | **New.** Unit tests for HowItWorks. |
| `frontend/src/app/(public)/components/landing-footer.test.tsx` | **New.** Unit tests for LandingFooter. |
| `frontend/tests/e2e/landing.spec.ts` | **New.** Playwright E2E tests for landing page and auth routing. |
| Various E2E test files | **Modified.** Update `goto("/")` → `goto("/dashboard")` where tests expect the Dashboard. |

---

## 8. Open Questions

1. **Hero headline copy** — what's the final headline? Starting point: "Your AI-Powered Job Search Assistant". Can iterate after initial build.
2. **Hero graphic** — user to source from design resources (Behance, Dribbble, unDraw, Storyset). Implementation uses a placeholder gradient until asset is ready.
3. **Feature card copy** — exact titles and descriptions. Starting points in §4.3 are editable.
4. **Analytics** — add any tracking (Google Analytics, Plausible, etc.) to the landing page? Deferred unless requested.

---

## 9. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-03 | 0.1 | Initial version. Public landing page for unauthenticated visitors. Dark theme, hero + features + how-it-works + footer. |
| 2026-03-03 | 0.2 | Post-audit revision. Added: Dashboard move to `/dashboard` (§2.2), middleware creation spec (§5.2), route conflict resolution (§5.1), `data-testid` table (§5.6), semantic HTML guidance (§5.5), login/register redirect updates (§5.3), settings file path corrected to `settings-page.tsx` (§5.4), provider behavior for unauthenticated users documented (§1.2), route impact table (§1.3), prerequisite diagram (§3.3), existing test update notes (§6.3), contrast/accessibility notes (§6.4). Removed ambiguous `(auth)` route group reference. Fixed feature card count to 4. Resolved Open Question #4 (CTA goes to `/register`). |
