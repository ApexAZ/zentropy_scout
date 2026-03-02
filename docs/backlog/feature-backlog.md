# Zentropy Scout — Feature Backlog

**Created:** 2026-02-16
**Last Updated:** 2026-03-01

**Items:** 22 (7 completed, 15 pending)

---

## How to Use This Document

**Purpose:** Capture feature ideas, enhancements, and future work that aren't part of the current implementation plan. Ideas here are unscoped and unprioritized until promoted to a plan or GitHub Issue.

**Format:** Each entry has a short title, description, and rough category. Add context links (REQ sections, related files, external docs) when available.

**Lifecycle:** Idea here → scope/estimate when ready → add to implementation plan or create GitHub Issue → remove from backlog.

---

## MVP Priority — Ordered by Dependency

These items are required to launch Zentropy Scout as a production SaaS tool on Render with real billing. Ordered so each item's dependencies are satisfied by items above it.

---

### 16. Admin Pricing Dashboard & Model Registry

**Category:** Backend / Frontend / Admin
**Added:** 2026-03-01
**Priority:** P1 — Required before launch. Must be able to configure pricing and models without code changes.
**Depends on:** ~~#12 (Token Metering)~~ ✅

Admin-configurable pricing and model management. Replaces the hardcoded pricing dict in the metering service and the hardcoded model routing tables in the LLM adapters with DB-backed configuration editable from the admin UI.

**What needs to be built:**
- **`pricing_config` table** — `id`, `provider`, `model`, `input_cost_per_1k`, `output_cost_per_1k`, `margin_multiplier`, `effective_date`, `created_at`, `updated_at`
- **`model_registry` table** — `id`, `provider`, `model`, `display_name`, `is_active`, `created_at` — canonical list of available models. Calls to unregistered models are blocked (prevents unmetered usage).
- **`task_routing_config` table** — `id`, `provider`, `task_type`, `model_id` (FK to model_registry) — replaces hardcoded `DEFAULT_CLAUDE_ROUTING` / `DEFAULT_OPENAI_ROUTING` dicts. Admin can reroute task types to different models without code changes.
- **`system_config` table** — key/value store for global settings like `credits_per_dollar`
- **Migrate metering service** — read pricing from DB instead of hardcoded Python dict, with caching (pricing doesn't change often)
- **Migrate LLM adapters** — `get_model_for_task()` reads from `task_routing_config` instead of hardcoded dicts
- **Block unknown models** — if a (provider, model) pair has no `pricing_config` row, the call is rejected. Prevents unmetered usage when providers release new models.
- **Admin API endpoints** — CRUD for pricing config, model registry, task routing, system config
- **Admin UI** — pricing table editor with live cost preview, effective date picker, model registry management, task routing editor
- **Admin auth/role** — admin-only access gate (could be a simple `is_admin` flag on user for MVP)

**Key consideration:** Effective dates on pricing changes — when a provider raises prices, admin updates the raw cost and sets an effective date. The system applies the new pricing from that date forward. Prevents running a deficit between provider price change and admin noticing.

---

### 19. Credit Denomination & Display Configuration

**Category:** Backend / Frontend / Admin
**Added:** 2026-03-01
**Priority:** P1 — Needed to launch credit packs. Closely tied to #16.
**Depends on:** #16 (Admin Pricing Dashboard)

Global configuration for how credits are denominated, displayed, and labeled across the product. Controls the credits-per-dollar ratio, display precision (decimal places), unit label ("credits", "tokens", custom), and rounding behavior. All frontend display logic and Stripe credit pack descriptions derive from these settings.

**What needs to be built:**
- **Display config** in `system_config` — `credits_per_dollar`, `credit_display_name`, `display_precision`, `rounding_mode` (up/nearest/down)
- **Frontend formatting utility** — single source of truth for rendering credit amounts everywhere (nav balance, usage page, transaction history, Stripe pack descriptions)
- **Admin UI** — preview how different denominations look across all user-facing surfaces before committing

**Key consideration:** Abstract credits from day one — not dollar-denominated. Decouples from USD, allows margin flexibility, psychologically easier for users. Denomination (e.g., 10,000 credits per dollar) is tunable from admin without code changes.

---

### 13. Stripe Credits Integration

**Category:** Backend / Frontend / Payments
**Added:** 2026-02-27
**Updated:** 2026-03-01 (reordered after #16/#19, narrowed scope to payment rail)
**Priority:** P2 — Monetization. Users purchase credits to use the tool.
**Depends on:** ~~#12 (Token Metering)~~ ✅, #16 (Admin Pricing Dashboard), #19 (Credit Denomination)

Integrate Stripe as the payment rail for credit pack purchases. Users buy credits via Stripe Checkout, webhook confirms payment and credits the ledger. Pricing intelligence and margin configuration live in #16 — Stripe just processes the payment and triggers the credit grant.

**What needs to be built:**
- **Stripe Checkout integration** — create checkout sessions for predefined credit packs
- **Webhook handler** — `POST /api/v1/webhooks/stripe` — verify signature, process `checkout.session.completed`, credit the user's ledger
- **Credit pack tiers** — pack amounts derived from credit denomination (#19), e.g., Starter ($5 / 50,000 credits), Standard ($15 / 175,000 credits), Pro ($40 / 500,000 credits) — exact amounts TBD based on denomination tuning
- **Purchase history** — `GET /api/v1/credits/purchases` — list of Stripe transactions with amounts and credit grants
- **Frontend purchase flow** — credits page with pack options, "Buy Credits" buttons that redirect to Stripe Checkout, success/cancel return URLs
- **Low-balance notifications** — frontend warning when credits drop below threshold (e.g., 10% of last purchase)
- **Stripe Customer mapping** — link Stripe customer ID to user account (new column on users table or separate table)

**Key considerations:**
- **Stripe Checkout (hosted)** over Stripe Elements — simpler, PCI-compliant out of the box, no card data touches our servers
- **Webhook idempotency** — use Stripe's `checkout.session.id` as idempotency key to prevent double-crediting
- **Refunds** — Stripe refund webhook should debit the credit ledger (or flag for manual review if credits already spent)
- **No subscriptions for MVP** — prepaid credit packs only. Subscriptions add complexity (proration, failed payments, dunning) better deferred to post-MVP

**Key files (new):**
- `backend/app/api/v1/stripe_webhooks.py` — webhook endpoint
- `backend/app/api/v1/credits.py` — credit balance, purchase history, checkout session creation
- `backend/app/services/stripe_service.py` — Stripe SDK calls, checkout session creation, webhook processing
- `frontend/src/app/(main)/credits/page.tsx` — purchase flow UI

**Dependencies (Python):**
- `stripe` — official Stripe Python SDK

**Open questions:**
- Stripe account: personal or business? (Tax/legal implications)
- Minimum purchase: is $5 the floor?
- Subscription model for post-MVP? (Monthly credit allotment with overage billing)
- Stripe Tax: collect sales tax automatically, or defer?
- Test mode: use Stripe test keys in dev/staging, live keys only in production

---

### 20. Landing Page & Home Dashboard

**Category:** Frontend
**Added:** 2026-03-01
**Priority:** P2 — Needed before public launch. First thing users see.
**Depends on:** Nothing (can start anytime, parallelizes with backend items)

Public landing page for unauthenticated visitors (marketing, value prop, sign-up CTA) and an authenticated home dashboard for logged-in users. New users get the option to skip onboarding and start with free credits to explore the tool immediately.

**What needs to be built:**
- **Public landing page** (`/`) — value proposition, feature highlights, sign-up/sign-in CTAs. Unauthenticated visitors see this. Clean, professional first impression.
- **Authenticated home dashboard** (`/dashboard` or `/`) — logged-in users see their activity summary: recent jobs, application pipeline status, credit balance, quick actions. Future home for insight engine cards (#11).
- **Skip onboarding flow** — new users can bypass the 11-step onboarding wizard and go straight to the dashboard with a starter credit grant. Onboarding is available later from settings/profile. "Get started free" path lowers friction.
- **Starter credit grant** — on account creation, automatically grant free credits (amount configurable in `system_config` via #16). Lets users try the tool before purchasing.

**Key files (existing):**
- `frontend/src/app/(main)/page.tsx` — current home page (placeholder)
- `frontend/src/app/(main)/layout.tsx` — authenticated layout
- `frontend/src/app/(auth)/` — login/register pages

**Open questions:**
- Landing page content: what's the core value prop headline?
- How many free starter credits? Enough for 2-3 job analyses + 1 ghostwriter run?
- Should the landing page be a separate Next.js route group (static, no auth layout)?
- SEO considerations: meta tags, Open Graph, structured data?

---

### 14. UI Design Improvements

**Category:** Frontend / Design
**Added:** 2026-02-27
**Priority:** P3 — Parallel with P1/P2 backend work. Needed before public launch.
**Depends on:** Nothing (can start anytime, parallelizes with backend items)

Elevate the visual design from functional-but-generic shadcn/ui defaults to a polished, branded product experience. The technical foundation is solid (28 shadcn/ui components, full CSS variable theming, dark mode, Tailwind v4) — the gap is visual identity and design polish.

**Current state:**
- shadcn/ui + Radix primitives with default styling
- CSS variable theming with light/dark mode (globals.css)
- System font stack (no custom typography)
- Blue-600 primary — standard, not distinctive
- Minimal visual hierarchy beyond basic card layouts
- No illustrations, empty states, or visual storytelling

**Areas to improve:**
- **Brand identity** — distinctive color palette, logo, favicon, consistent visual language
- **Typography** — custom web font (Inter, Cal Sans, or similar) for headings to add personality
- **Component polish** — refined shadows, borders, hover/focus states, micro-animations
- **Empty states** — illustrated or iconographic empty states instead of plain text
- **Data visualization** — charts/graphs for job scoring, application pipeline, credit usage
- **Dashboard layout** — information density improvements, better card hierarchy, status indicators
- **Onboarding flow** — progress indicators, step illustrations, smoother transitions
- **Responsive refinement** — mobile-first polish (currently functional but basic at mobile breakpoints)
- **Loading states** — skeleton screens are in place; add subtle transitions and branded loading indicators

**Approach options:**
- **Option A:** Iterative self-improvement — pick a design reference (Linear, Vercel, Notion) and systematically align component styling
- **Option B:** Tailwind UI / shadcn themes — purchase and apply a polished theme pack for rapid uplift
- **Option C:** Designer engagement — hire a designer for brand identity + component specs, implement from their deliverables

**Key files:**
- `frontend/src/app/globals.css` — CSS variables, theme definitions
- `frontend/src/components/ui/` — 28 shadcn/ui components (customizable)
- `frontend/src/app/(main)/page.tsx` — home/dashboard page
- `frontend/src/app/(main)/layout.tsx` — main layout with navigation

**Open questions:**
- Design reference: which existing product should we visually aspire to?
- Custom font: worth the web font loading cost?
- Illustrations: use an icon library (Lucide already included) or custom illustrations?
- Dark mode: primary mode or secondary? (Affects design priority)
- Scope: full redesign or targeted polish of highest-traffic pages first?

---

### 23. Job Capture Bookmarklet

**Category:** Backend / Frontend / API
**Added:** 2026-03-02
**Priority:** P2 — Core job capture workflow. Lightweight alternative to Chrome Extension (#4.1, postponed).
**Depends on:** Nothing (can start anytime)

Personalized bookmarklet that lets users capture job postings from any browser with one click. Replaces the postponed Chrome Extension (Phase 4.1) with a zero-install, cross-browser solution. The bookmarklet sends the page URL + title to the backend, which fetches the page server-side, strips it to clean text, and feeds it to the existing job analysis pipeline.

**What needs to be built:**

- **Bookmarklet generator** — personalized `javascript:` snippet with user auth token baked in at generation time. Served from a settings or onboarding page with drag-to-bookmarks-bar instructions.
- **Backend capture endpoint** — `POST /api/v1/jobs/capture` — accepts `{ url, title }`, fetches the page server-side, returns job data or status.
- **HTML stripping** — BeautifulSoup to remove nav, footer, scripts, ads, sidebars. Extract clean text from the main content area. Cap at ~15,000 characters before sending to LLM.
- **LinkedIn detection** — detect LinkedIn domain and return a friendly message: "LinkedIn pages can't be captured automatically. Paste the job description text instead." (LinkedIn blocks server-side fetches.)
- **ATS apply URL detection** — scan fetched HTML for apply links matching known ATS platforms: Workday, Greenhouse, Lever, iCIMS, Taleo, SmartRecruiters, Jobvite, and generic `apply` href patterns.
- **Apply type classification** — categorize as `ats_external`, `linkedin_easy_apply`, `company_direct`, or `indeed_apply`.
- **Job record fields** — store `job_page_url`, `ats_apply_url`, `ats_platform`, `apply_type` per job posting.
- **Visual confirmation** — bookmarklet injects a toast notification into the page after firing (success/error/LinkedIn message).
- **CORS configuration** — API endpoint must accept cross-origin requests from bookmarklet (runs in the context of the job posting page).
- **Setup UI** — bookmarklet installation instructions on the settings page (or onboarding). Show the bookmarklet link, drag-to-toolbar instructions, and a test button.

**Key considerations:**
- Auth token in the bookmarklet means regeneration is needed if the token is rotated. Include a "Regenerate bookmarklet" button.
- Server-side fetch avoids CORS issues with job sites but means the backend needs `httpx` or similar for async HTTP requests.
- Some job sites may block server-side fetches (Cloudflare, bot detection). Graceful fallback: "Couldn't fetch this page. Paste the job description text instead."
- Bookmarklet code size is limited (~2KB practical limit for `javascript:` URLs). Keep the bookmarklet thin — just collect URL/title, POST to API, show toast.

**Key files (new):**
- `backend/app/api/v1/job_capture.py` — capture endpoint
- `backend/app/services/page_fetch_service.py` — server-side fetch + HTML stripping
- `backend/app/services/ats_detection_service.py` — ATS URL and apply type detection
- `frontend/src/app/(main)/settings/bookmarklet/` — setup UI and generator

**Dependencies (Python):**
- `beautifulsoup4` — HTML parsing and content extraction
- `httpx` — async HTTP client for server-side page fetching (already in project or similar)

**Open questions:**
- Should the bookmarklet auto-trigger job analysis, or just capture and let the user trigger analysis?
- Rate limiting on the capture endpoint? (Prevent abuse if token leaks)
- Should fetched HTML be stored temporarily for debugging, or discarded after extraction?
- Mobile browser support — bookmarklets work poorly on mobile. Offer a "paste URL" fallback?

---

### 4. Render Deployment Configuration

**Category:** DevOps / Infrastructure
**Added:** 2026-02-16
**Updated:** 2026-03-01 (updated dependencies for new ordering)
**Priority:** P4 — Deploy after metering + payments are functional.
**Depends on:** ~~#1 (Authentication), #2 (Multi-Tenant)~~ ✅, ~~#12 (Token Metering)~~ ✅, #16 (Admin Pricing), #13 (Stripe Integration)

Configure `render.yaml` to deploy the Next.js frontend, FastAPI backend, and Python background workers on Render. Render is already familiar, uses fixed predictable pricing, has native background worker and cron job support, and no cold-start surprises.

**Render service breakdown (~$21/month to start):**
- **Web service** — FastAPI + uvicorn ($7/month, Starter tier)
- **PostgreSQL** — Render-managed Postgres with pgvector ($7/month)
- **Background worker** — Scouter polling, insight engine cron, TTL cleanup ($7/month)
- **Static site** — Next.js frontend (free for static; $7/month if SSR needed)

**Key areas:**
- **`render.yaml`** — infrastructure-as-code defining all services, env vars, and build commands
- **Environment:** Production env vars via Render dashboard or `render.yaml` envVarGroups (includes Stripe keys, LLM API keys, auth secrets)
- **Build:** Python (pip + uvicorn) for backend, Node.js (`npm run build && npm start`) for frontend
- **Networking:** Render private network between services, public URLs for frontend and API
- **Database migrations:** Alembic `upgrade head` as a pre-deploy job or startup command
- **pgvector:** Confirm availability on Render managed Postgres (available on Starter+)
- **Stripe webhooks:** Configure Stripe webhook endpoint URL to point to production API

**Existing overlap:**
- **Docker Compose** (`docker-compose.yml`) already defines the PostgreSQL + pgvector service for local dev. `render.yaml` mirrors this structure.
- **Backend is deployable** — FastAPI app with uvicorn, Alembic migrations, structured settings via env vars. No filesystem dependencies (BYTEA storage).
- **Frontend is deployable** — standard Next.js 14 App Router app.
- **Pre-deployment security task** §13.5a (disable ZAP public issue writing) should be completed before going live.

**Open questions:**
- Does Render managed Postgres Starter tier include pgvector? (Likely yes — confirm before assuming.)
- Static export vs SSR for Next.js frontend — can all routes be statically rendered?
- Redis needed for session storage / caching, or PostgreSQL-only for MVP?
- Custom domain — Render supports custom domains on all paid tiers.
- CI/CD — deploy on push to main via Render GitHub integration, or manual promote?

---

## Post-MVP

These items add value but don't block launching the tool as a usable, billable product.

---

### 11. Chat Agent Redesign — Replace General-Purpose Chatbot with Proactive Insight Engine

**Category:** Backend / Frontend / Architecture
**Added:** 2026-02-23

**Background:**
The Chat Agent is implemented as a 9-node LangGraph `StateGraph` in `backend/app/agents/chat.py` (856 lines). It was designed as the primary user interface — a general-purpose conversational layer with 25+ tools across 6 categories. Code review (2026-02-23) found all routing is deterministic regex pattern matching against a confidence threshold. No LLM makes routing decisions. `execute_tools` is a placeholder returning empty results.

**Why the current design is wrong:**
The product vision is a job application tracker with AI-powered insights — not a chat-first app. The tracker is the foundation (jobs, applications, resumes, cover letters as structured views). AI sits on top as a proactive insight layer that watches the data and surfaces things worth acting on. A blank chat box is a blank page problem — users won't remember to ask the right questions. The insight finds the user, not the other way around.

**The right model — proactive insight engine:**
A rules-based background service queries tracker data, recognizes situations that need attention, and surfaces actionable cards on a home screen feed. Each card has an observation, context, and action buttons. User approves or dismisses. Agent executes approved actions directly within the app.
```
Scout observes situation in tracker data
    → surfaces insight card with human-readable summary
    → offers specific action button(s)
    → user approves or dismisses
    → agent executes approved action within the app
```

**MVP scope boundary:**
- **In scope** — agent acts within the app: update application status, log timeline events, dismiss/favorite jobs, trigger Ghostwriter, snooze insights, add skills to persona
- **Out of scope for MVP** — anything external: sending emails, visiting portals, submitting applications
- **Post-MVP path** — V2 adds email draft for user review/send; V3 adds opt-in auto-send. Action handler pattern designed for extension — adding external actions means adding a new tool, no rearchitecting

**Insight catalog (MVP — all rules-based, no LLM required for detection):**

| Situation | Trigger | Action Offered |
|-----------|---------|----------------|
| High match sitting idle | fit_score ≥ 80, discovered 3+ days, no draft | Draft materials |
| Applied, no response | Applied 14+ days, status unchanged | Mark follow-up / Close |
| Stale application | Applied 30+ days, no movement | Close this out? |
| Draft ready, unreviewed | JobVariant = Draft, created 3+ days ago | Review now |
| Materials approved, no application logged | CoverLetter approved, no Application record | Mark as applied? |
| Posting closing soon | expiry_date within 48 hours | Draft materials / Dismiss |
| Profile stale | Persona last_updated > 60 days | Update profile |

**Narrow tool set (8 tools, not 25):**
`update_application_status`, `log_timeline_event`, `dismiss_job`, `favorite_job`, `trigger_ghostwriter`, `snooze_insight`, `add_skill_to_persona`, `trigger_rescore`

**What happens to `chat.py`:**
- **Delete:** graph construction, routing nodes, delegation nodes, LangGraph imports
- **Keep:** `classify_intent` + `INTENT_PATTERNS` (useful when post-MVP chat input is added), `request_clarification` / `needs_clarification` (same), `format_response` helpers (reusable)

**New files:**
- `backend/app/services/insight_engine.py` — runs after each Scouter poll and daily cron, evaluates rules, persists insight cards
- `backend/app/models/insight.py` — `Insight` model with `actions` JSONB field driving action buttons declaratively
- `backend/app/api/v1/insights.py` — `GET /insights`, `POST /insights/{id}/action`, `POST /insights/{id}/dismiss`, `POST /insights/{id}/snooze`
- `frontend/src/components/feed/InsightFeed.tsx` — home screen component
- `frontend/src/components/feed/InsightCard.tsx` — individual card with action buttons

**Open-ended chat is explicitly deferred to post-MVP.** When added, it lives as a text input at the bottom of the insight feed, scoped to insight-related actions first, using the preserved intent classification logic from `chat.py`.

**Requirements references:** REQ-007 §4 (superseded by this item), REQ-012 (frontend home screen)

---

### 3. Job Content TTL for Legal Compliance

**Category:** Backend / Database
**Added:** 2026-02-16

Split job posting storage into permanent metadata and time-limited content:
- **Job metadata** (permanent): title, company, location, salary range, source URL, extracted skills, scores
- **Job content** (24-hour TTL): full description text, raw HTML, original posting body

After TTL expires, the full content is purged but metadata and extracted data remain. Users can re-fetch content by visiting the source URL.

**Motivation:** Legal compliance with job board terms of service (LinkedIn, Indeed, etc.) that prohibit long-term storage of scraped posting content.

**Key files:**
- `backend/app/models/job_posting.py` (current schema — single table)
- REQ-003 (job posting schema)
- REQ-005 (database schema)

**Existing overlap:**
- **Job posting schema** (REQ-003, `backend/app/models/job_posting.py`) currently stores everything in one table — description, raw content, extracted skills, scores, metadata all in `job_postings`. This feature would split that table.
- **Extracted data** (skills, culture signals, salary parsing) is already stored as structured JSONB fields separate from raw text. These are derivatives, not original content — likely safe to keep permanently.
- **Frontend job detail page** renders description text and extracted data. Would need a "content expired" state when raw text is purged, with a "View on source site" link.

**Open questions:**
- Is 24 hours the right TTL? Some ToS may allow longer.
- Separate table (`job_content`) or nullable columns on existing table?
- Background worker (cron) for TTL cleanup, or database-level expiry (pg_cron)?
- Should extracted/transformed data (skills, culture signals) be considered "content" or "metadata"?
- Does the user need to be notified when content expires?

---

### 5. Socket.dev Supply Chain Protection

**Category:** Security / Dependencies
**Added:** 2026-02-18

Add Socket.dev GitHub App for npm supply chain attack detection. Dependabot and npm audit catch *known* CVEs in published packages, but Socket.dev catches a different threat class: malicious packages, typosquatting, compromised maintainer accounts, hidden install scripts, and unexpected network/filesystem access.

**Motivation:** As Zentropy Scout moves to SaaS with public users, the threat surface expands beyond known CVEs to active supply chain attacks. Socket.dev is free for open-source repos and provides PR-level alerts when a dependency introduces suspicious behavior.

**Key areas:**
- Install Socket.dev GitHub App (no config files needed — it reads `package.json`/`package-lock.json`)
- Review initial findings and configure alert thresholds
- Add to session start checklist in CLAUDE.md if it provides an API

**Existing overlap:**
- **Dependabot alerts** — catches known CVEs but not malicious/suspicious packages
- **npm audit** — same as Dependabot, known CVEs only
- **gitleaks** — catches secrets in *your* commits, not in dependency code

**Open questions:**
- Free tier limits for open-source repos?
- Does it provide a queryable API for session-start checks?
- Alert noise level — how many false positives on a typical Next.js + FastAPI project?

---

### 6. Full Stack E2E Test Tier (Testcontainers)

**Category:** Testing / Quality
**Added:** 2026-02-23

Add a true end-to-end test tier using Testcontainers to spin up real PostgreSQL + pgvector instances in Docker for integration tests. Current tests mock the database layer, which means no test currently validates that queries, migrations, and schema constraints work together correctly against a real database.

**Why this is needed:**
Code review found that unit tests mock SQLAlchemy sessions and repository calls, meaning the test suite gives false confidence — a broken migration or an invalid query would pass all current tests. Testcontainers provides a real Postgres instance per test session, no mocking required, no shared state between runs.

**Key areas:**
- `pytest-testcontainers` or `testcontainers-python` for Postgres container lifecycle
- Alembic migrations run against the test container on startup — validates migration integrity
- Repository-layer tests rewritten to use real DB rather than mocks
- pgvector extension confirmed available in container
- CI pipeline runs Testcontainers tier (Docker must be available in CI environment)

**Prerequisite:** Backend service layer must be stable enough that repository interfaces aren't changing weekly. Defer until after LangGraph removal items (7–10) are complete to avoid rewriting tests twice.

**Open questions:**
- Shared container per test session or per test? Per session is faster; per test is cleaner. Start with per session.
- Replace all mock-based repository tests or run both tiers? Replace — mocks provide false confidence once real DB tests exist.

---

### 21. Recruiter Portal

**Category:** Frontend / Backend / Architecture
**Added:** 2026-03-01
**Priority:** Post-MVP — Future revenue stream and product expansion.
**Depends on:** Core product stable and launched

Separate portal for recruiters to discover and connect with job seekers. Flips the marketplace — instead of only candidates searching for jobs, recruiters can search for candidates whose skills and preferences match their open positions.

**Scope is intentionally vague — this is a future vision item, not a near-term deliverable.** Details to be scoped when the candidate-side product is stable and generating revenue.

**Potential areas:**
- Recruiter accounts (separate from job seeker accounts)
- Candidate discovery — search/filter by skills, experience, location, availability
- Candidate opt-in — job seekers choose whether to be visible to recruiters
- Messaging/outreach — recruiters contact candidates through the platform
- Recruiter pricing model — separate from candidate credits (per-seat, per-contact, or subscription)
- Privacy controls — candidates control what recruiters can see (anonymized profiles until mutual interest)

---

### 15. Async/Sync Performance Audit

**Category:** Backend / Performance
**Added:** 2026-02-28
**Priority:** Post-MVP — No user-facing impact until high concurrency.
**Depends on:** Nothing

Deep audit of the entire backend for async/sync correctness under high concurrency. Ensure all FastAPI dependency functions, service methods, and provider calls use the optimal async/sync pattern to avoid unnecessary thread pool dispatch overhead at scale.

**Motivation:** During REQ-020 implementation, SonarCloud S7503 findings revealed that `async def` without `await` is an intentional FastAPI optimization (avoids `run_in_threadpool()` overhead). This raised the question: are there other places where sync functions unnecessarily use the thread pool when they could be async, or vice versa?

**Key areas to audit:**
- All FastAPI dependency functions in `backend/app/api/deps.py`
- Service layer methods that only perform fast synchronous operations
- Provider factory functions and singleton patterns
- Database session lifecycle management
- Middleware and exception handler async patterns
- Background task scheduling patterns

**Expected outcome:** Documentation of which functions are intentionally async-without-await (with rationale), identification of any functions that should be converted for better scalability, and SonarCloud baseline updates.

**Open questions:**
- Is `run_in_threadpool()` overhead measurable at expected user scale (hundreds to low thousands)?
- Should this be a formal load testing exercise or code-review-only audit?
- Profile tools: `py-spy`, `viztracer`, or FastAPI's built-in timing middleware?

---

### 17. Pricing Simulation Tool

**Category:** Backend / Frontend / Admin
**Added:** 2026-03-01
**Priority:** P2 — Important for informed pricing decisions before and after launch.
**Depends on:** #16 (Admin Pricing Dashboard)

Before committing a pricing change, preview "here's what last week's (or any date range's) usage would have cost users under the proposed rates." Queries existing `llm_usage_records` with proposed pricing applied and shows a comparison: current revenue vs. projected revenue, per-user impact, cost distribution by model.

**What needs to be built:**
- **Simulation API endpoint** — accepts proposed pricing config, date range; returns comparison report
- **Admin UI panel** — side-by-side view of current vs. proposed pricing impact, histogram of per-user cost changes
- **No user-facing changes** — purely an admin tool

---

### 18. A/B Test Support for Pricing

**Category:** Backend / Frontend / Admin
**Added:** 2026-03-01
**Priority:** Post-MVP — Needs real users and usage data to be meaningful.
**Depends on:** #16 (Admin Pricing Dashboard)

Assign users to pricing cohorts, each with their own margin multipliers. Compare retention, usage volume, and revenue across cohorts. Enables data-driven pricing optimization.

**What needs to be built:**
- **Cohort assignment** — `pricing_cohort` column on users table, assignment logic (random, manual, or rule-based)
- **Per-cohort pricing overrides** — cohort-specific margin multipliers that override the default pricing config
- **Metering integration** — metering service resolves pricing by checking user's cohort first, falling back to default
- **Reporting dashboard** — compare cohorts on revenue per user, usage frequency, churn, credit purchase patterns
- **Admin UI** — create/manage cohorts, assign users, view comparison reports

**Open questions:**
- How many concurrent cohorts? 2 (A/B) or more (A/B/C/D)?
- Duration-based auto-expiry for experiments?
- Should users be notified they're in a pricing experiment? (Legal/ethical consideration)

---

### 22. User Dark Mode Setting

**Category:** Frontend / Backend
**Added:** 2026-03-01
**Priority:** Post-MVP — Quality-of-life feature. Infrastructure already exists.
**Depends on:** Nothing (can start anytime)

Add a user-facing dark mode toggle in the settings page. The frontend already has dark mode CSS variables and Tailwind dark mode classes defined in `globals.css` — the gap is a user-persisted preference.

**What needs to be built:**
- **User preference storage** — `theme_preference` column on `users` table (`VARCHAR(10)`: `'light'`, `'dark'`, `'system'`; default `'system'`)
- **Settings UI** — theme toggle in the existing Settings page (3-way: Light / Dark / System)
- **Frontend implementation** — read preference from user profile, apply `class="dark"` on `<html>`, persist on change via API
- **API endpoint** — `PATCH /api/v1/users/me/preferences` to save theme preference (or extend existing user settings endpoint)
- **SSR consideration** — read preference from cookie or JWT claim to avoid dark-mode flash on page load

**Current state:**
- CSS variables for both light and dark themes exist in `frontend/src/app/globals.css`
- Tailwind dark mode is configured (class-based strategy)
- No user preference persistence — currently relies on system preference only

**Key files:**
- `frontend/src/app/globals.css` — theme CSS variables (already has dark mode definitions)
- `frontend/src/app/(main)/settings/page.tsx` — settings page (add toggle here)
- `backend/app/models/user.py` — add `theme_preference` column

---

<!-- Add new ideas above this line -->

---

## Completed

### ~~1. Authentication System with Account Linking~~ ✅

**Status:** Promoted to plan and completed
**Implemented in:** `docs/plan/auth_implementation_plan.md` — Phases 1–2 (REQ-013)
**Decision:** Custom FastAPI-owned auth instead of Auth.js v5 — see `docs/plan/decisions/001_auth_adapter_decision.md`
**Completed:** Google OAuth, LinkedIn OAuth, magic link, email/password, account linking, middleware, session context, login/register pages, account settings, E2E tests.

---

### ~~2. Multi-Tenant Architecture~~ ✅

**Status:** Promoted to plan and completed
**Implemented in:** `docs/plan/auth_implementation_plan.md` — Phase 3 (REQ-014)
**Completed:** Row-level isolation via `user_id` FK, ownership verification on all endpoints (404 not 403), cross-tenant leakage tests, TenantScopedSession for agents, E2E multi-tenant tests.

---

### ~~7. Scouter Redesign — Replace LangGraph with Service Layer~~ ✅

**Status:** Promoted to plan and completed
**Implemented in:** `docs/plan/llm_redesign_plan.md` — Phase 1 (REQ-016)
**Completed:** Replaced 10-node LangGraph StateGraph with JobPoolRepository, JobEnrichmentService, and JobFetchService. Deleted scouter_graph.py (895L). All tests passing.

---

### ~~8. Strategist Redesign — Replace LangGraph with JobScoringService~~ ✅

**Status:** Promoted to plan and completed
**Implemented in:** `docs/plan/llm_redesign_plan.md` — Phase 2 (REQ-017)
**Completed:** Replaced 10-node LangGraph StateGraph (9 placeholder nodes) with single JobScoringService. Relocated prompts to `backend/app/prompts/` package, moved ScoreResult to score_types.py. Deleted strategist_graph.py (662L). All tests passing.

---

### ~~9. Ghostwriter Redesign — Replace LangGraph with ContentGenerationService (MVP: User-Initiated Only)~~ ✅

**Status:** Promoted to plan and completed
**Implemented in:** `docs/plan/llm_redesign_plan.md` — Phase 3 (REQ-018)
**Completed:** Replaced 9-node LangGraph StateGraph with ContentGenerationService orchestrating 15 existing production-ready service files. Relocated prompts to `backend/app/prompts/ghostwriter.py`. Deleted ghostwriter_graph.py (687L). Auto-draft remains deferred (MVP: user-initiated only). All tests passing.

---

### ~~10. Onboarding Redesign — Replace LangGraph Agent with HTML Wizard + Free Resume Parsing~~ ✅

**Status:** Promoted to plan and completed
**Implemented in:** `docs/plan/llm_redesign_plan.md` — Phase 4 (REQ-019)
**Completed:** Replaced 13-node LangGraph StateGraph (2490L) with ResumeParsingService (pdfplumber + Gemini 2.5 Flash) and resume-parse API endpoint. Deleted ~1784L of graph/state-machine code, kept ~706L of post-onboarding utilities. Frontend updated from 12→11 steps (removed base-resume step). E2E tests rewritten for 11-step flow. All tests passing.

---

### ~~12. Token Metering & Usage Tracking~~ ✅

**Status:** Promoted to plan and completed
**Implemented in:** `docs/plan/token_metering_plan.md` — Phases 1–7 (REQ-020)
**Completed:** Full metering pipeline — `llm_usage_records` + `credit_transactions` tables, MeteringService with pricing tables, MeteredLLMProvider/MeteredEmbeddingProvider proxies, balance-gating middleware (402), usage/credits/transactions API endpoints, frontend usage dashboard with balance indicator in nav. 19 integration tests, 17 E2E tests. Zero-trust suppression audit of 448 lint suppressions (154 fixed, 294 verified). 4074 backend + 3319 frontend tests passing.
