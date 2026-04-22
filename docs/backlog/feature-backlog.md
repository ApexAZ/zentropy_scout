# Zentropy Scout — Feature Backlog

**Created:** 2026-02-16
**Last Updated:** 2026-04-21

**Items:** 32 (11 completed, 21 pending)

---

## How to Use This Document

**Purpose:** Capture feature ideas, enhancements, and future work that aren't part of the current implementation plan. Ideas here are unscoped and unprioritized until promoted to a plan or GitHub Issue.

**Format:** Each entry has a short title, description, and rough category. Add context links (REQ sections, related files, external docs) when available.

**Lifecycle:** Idea here → scope/estimate when ready → add to implementation plan or create GitHub Issue → remove from backlog.

---

## MVP Priority — Ordered by Dependency

These items are required to launch Zentropy Scout as a production SaaS tool on Render with real billing. Ordered so each item's dependencies are satisfied by items above it.

---

---

### 19. USD-Direct Billing & Pack Configuration ✅

**Category:** Backend / Frontend / Admin
**Added:** 2026-03-01
**Updated:** 2026-03-03 (completed — REQ-023 implemented)
**Completed:** 2026-03-03
**Priority:** P1 — Needed to launch credit packs. Closely tied to #16.
**Depends on:** ~~#16 (Admin Pricing Dashboard)~~ ✅

Configure the billing model for USD-direct display and tiered pack pricing. Repurpose the existing `credit_packs` table for USD-denominated balance packs and update frontend display to show dollar amounts with a usage depletion bar.

#### Decision Record: USD-Direct Over Abstract Credits (2026-03-02)

**Original proposal:** Abstract credit system with configurable `credits_per_dollar` conversion rate (e.g., 10,000 credits per dollar). Users would see "175,000 credits" instead of "$17.50". Four new `system_config` keys (`credits_per_dollar`, `credit_display_name`, `display_precision`, `rounding_mode`) and a frontend formatting utility to convert USD to credits at display time.

**Decision:** Use USD directly — no abstract credit layer. Users see dollar amounts everywhere.

**Why abstract credits were rejected:**

1. **Denomination dilemma with no good answer.** At 10,000 credits/dollar, a $20 purchase shows "200,000 credits" — feels like a mobile game, not a professional tool. At 1,000 credits/dollar, the cheapest LLM calls (Gemini Flash ~$0.000169) round to 0 credits at integer display. At 100 credits/dollar, most operations round to 0. Every ratio has a fatal tradeoff between relatable numbers and display precision.

2. **Redenomination risk.** `credits_per_dollar` is a global display multiplier applied retroactively to all existing balances. Changing it from 10,000 to 5,000 instantly halves every user's displayed balance overnight — a redenomination event. Options to mitigate (snapshot at transaction time, lock after first set, dual-rate tracking) all add significant complexity for a scenario that ideally never happens.

3. **Margin flexibility already exists.** The admin pricing dashboard (REQ-022) provides `margin_multiplier` per model in `pricing_config`. Adjusting margins doesn't require a credit abstraction — it's already configurable per-model from the admin UI.

4. **Transparency is a feature for professional SaaS.** Anthropic, OpenAI, Vercel, and AWS all show USD costs directly. For a job application assistant (a productivity tool, not a game), transparent pricing builds trust. The "psychological abundance" of large credit numbers is a gaming industry pattern that was widely criticized and largely abandoned (Microsoft Points, Wii Points).

5. **The system already works in USD.** The metering pipeline calculates in USD, `balance_usd` stores USD, `credit_transactions.amount_usd` is USD, the frontend already displays `$X.XX`. Abstract credits would add a conversion layer on top of a system that already does the right thing.

**Why USD-direct works:**

- **Pack changes only affect future purchases.** When a user buys a pack, the granted amount is written to `credit_transactions` as an immutable ledger entry. Changing pack pricing later doesn't affect existing balances — it's just a menu change. No redenomination risk.
- **Volume bonuses supported but deferred.** The `credit_packs` table has both `price_cents` (what user pays) and `credit_amount` (what they get). For MVP launch, these are equal (dollar-for-dollar, no bonuses). If volume bonuses are added later, the `credit_amount` exceeding `price_cents` IS the bonus — tracked implicitly by the two existing fields. Effective margin in that case: `base_margin × (price_cents / credit_amount)`.
- **Fully reconfigurable from admin UI.** Pack tiers, prices, and grant amounts are editable anytime from the admin Packs tab. No code deploy needed to adjust pricing. Only future purchases are affected.

**What this eliminates:**
- ~~`credits_per_dollar` system config key~~ — not needed
- ~~`credit_display_name` system config key~~ — not needed
- ~~`display_precision` system config key~~ — not needed (USD uses 2 decimal places)
- ~~`rounding_mode` system config key~~ — not needed
- ~~Frontend credit formatting utility~~ — not needed (existing `formatBalance`/`formatCost` already display USD)
- ~~Admin denomination preview UI~~ — not needed
- ~~Column renames (`balance_usd` → `balance_credits`)~~ — not needed (column names are now accurate)

#### Decision Record: Funding Model & Pack Structure (2026-03-02)

**Model: "Add Funds" with quick-select amounts, not differentiated tiers.**

Packs are not tiers with differentiated value — they are suggested funding amounts with admin-controlled descriptions to help users make informed choices. The `credit_packs` table is repurposed as a menu of quick-select options with context labels tied to service volume (number of jobs/resumes), not time.

**Rationale for quick-select over free-entry:** Fewer clicks — a row of amount buttons that go straight to Stripe checkout is faster than a text input with validation. Predefined amounts also let the admin attach volume-based descriptions so users understand what they're buying.

**Rationale for volume-based labels over time-based:** Users aren't buying time in the job market. They're buying a service — job analysis, resume generation, cover letter creation. Labels should communicate service volume: "Analyze ~250 jobs and generate tailored materials" not "3 months of use."

**Initial configuration (3 options, admin-editable):**

| Amount | Name | Description (admin-controlled) |
|--------|------|-------------------------------|
| $5 | Starter | e.g., "Analyze ~250 jobs and generate tailored materials" |
| $10 | Standard | e.g., "Analyze ~500 jobs and generate tailored materials" |
| $15 | Pro | e.g., "Analyze ~750 jobs and generate tailored materials" |

Exact descriptions are set by admin from the Packs tab. Names, descriptions, and `highlight_label` (e.g., "Most Popular") are all editable without code changes. Amounts, number of options, and descriptions can all be reconfigured at any time — only future purchases are affected.

**No volume bonuses for MVP.** Dollar-for-dollar — pay $10, get $10.00 in balance. Volume bonuses can be added later by setting `credit_amount` > `price_cents` on a pack. The infrastructure supports it; the business decision is deferred.

**Usage cost context (informs amount sizing):**

| User Profile | Monthly Usage | Monthly Cost (1.3x margin) |
|-------------|---------------|---------------------------|
| Light (5 jobs, 2 resumes, 2 cover letters) | ~15 LLM calls | ~$0.05 |
| Typical (20 jobs, 10 resumes, 10 cover letters) | ~65 LLM calls | ~$0.22 |
| Heavy (50 jobs, 20 resumes, 20 cover letters) | ~130 LLM calls | ~$0.50 |
| Power (100 jobs, 50 resumes, 50 cover letters) | ~300 LLM calls | ~$1.60 |

**Per-operation cost breakdown (at 1.3x margin):**

| Operation | Model (default routing) | Approx. Cost |
|-----------|------------------------|-------------|
| Job extraction | Claude Haiku | ~$0.002 |
| Job scoring/rationale | Claude Haiku | ~$0.002 |
| Cover letter generation | Claude Sonnet | ~$0.008 |
| Resume tailoring decisions | Claude Haiku | ~$0.002 |
| Story selection | Claude Sonnet | ~$0.004 |
| Resume parsing | Gemini 2.5 Flash | ~$0.002 |
| Embedding (per call) | OpenAI text-embedding-3-small | ~$0.00003 |

**Stripe fee impact:**

| Amount | Stripe Fee (~$0.30 + 2.9%) | Net Revenue | Fee % |
|--------|----------------------------|-------------|-------|
| $5 | $0.45 | $4.55 | 9.0% |
| $10 | $0.59 | $9.41 | 5.9% |
| $15 | $0.74 | $14.26 | 4.9% |

**What needs to be built:**

- **Update `credit_packs` seed data** — Change from abstract credits (50000, 175000, 500000) to USD cents matching price (500, 1000, 1500). Update descriptions to volume-based labels. Alembic migration to update seed data. The `credit_amount` column stays as-is (reinterpret as cents). Rename deferred until bonuses are needed.
- **Frontend usage bar** — Depletion-style progress indicator showing the user's current dollar balance visually.
- **Update `signup_grant_credits` system config key** — Rename to `signup_grant_cents`. Value represents USD cents granted on signup (0 = no grant).

**Scope reduction:** This feature shrank dramatically from the original abstract-credits design. The four `system_config` denomination keys, the frontend formatting utility, the admin preview UI, the column renames, the bonus math display, and the effective margin columns are all eliminated or deferred. The remaining work is a seed data migration, a usage bar component, and a config key rename. This could fold into #13 (Stripe Integration) as a preparatory subtask.

**Key files (modify):**
- `backend/migrations/versions/` — new migration to update `credit_packs` seed data and rename `signup_grant_credits` config key
- `backend/app/models/admin_config.py` — update CreditPack column comments/docs
- `frontend/src/components/usage/balance-card.tsx` — add usage depletion bar
- `frontend/src/components/layout/top-nav.tsx` — balance display (already USD, may add bar)

**Open questions:**
- Should this remain standalone (#19), or fold into #13 (Stripe Integration) as a preparatory subtask?
- Usage bar reference point: absolute dollar balance, or "last purchase amount" as 100%?
- `signup_grant_cents` default: how much free balance for new users? Enough for 2-3 job analyses (~$0.05-$0.10)?

---

### 13. Stripe Credits Integration ✅

**Category:** Backend / Frontend / Payments
**Added:** 2026-02-27
**Updated:** 2026-03-11 (completed — REQ-029 implemented)
**Completed:** 2026-03-11
**Priority:** P2 — Monetization. Users purchase balance packs to use the tool.
**Depends on:** ~~#12 (Token Metering)~~ ✅, ~~#16 (Admin Pricing Dashboard)~~ ✅, ~~#19 (USD-Direct Billing)~~ ✅
**Status:** Complete — implemented via REQ-029 (Stripe Checkout). 6 phases, 28 tasks. Stripe SDK, funding packs API, checkout sessions, webhook fulfillment, usage dashboard, signup grant in all auth flows.

Integrate Stripe as the payment rail for "Add Funds" purchases. Users select a quick-select amount ($5/$10/$15 — admin-configurable), Stripe Checkout processes the payment, webhook confirms and credits the user's dollar balance. Pricing intelligence and margin configuration live in #16 — Stripe just processes the payment and triggers the balance grant.

**What needs to be built:**
- **Stripe Checkout integration** — create checkout sessions for the selected funding amount
- **Webhook handler** — `POST /api/v1/webhooks/stripe` — verify signature, process `checkout.session.completed`, credit the user's ledger
- **"Add Funds" UI** — quick-select amount buttons ($5/$10/$15) with admin-controlled volume-based descriptions, leading to Stripe Checkout. Amounts and descriptions configurable from admin Packs tab.
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

### 20. Customizable Activity Dashboard

**Category:** Frontend
**Added:** 2026-03-01
**Updated:** 2026-03-04 (scoped down — landing page complete via REQ-024, skip onboarding and starter credits won't do)
**Priority:** P3 — Deferred until frontend UI/UX is more crystallized.
**Depends on:** Nothing (can start anytime)

Customizable authenticated home dashboard at `/dashboard` for logged-in users. Activity summary with recent jobs, application pipeline status, credit balance, and quick actions. Users should be able to customize which widgets/cards are visible and their layout order.

#### Decision Record (2026-03-04)

| Original Scope | Decision | Rationale |
|----------------|----------|-----------|
| Public landing page | ✅ Complete | Implemented as REQ-024 (landing page at `/`, auth routing, middleware). |
| Skip onboarding flow | Won't Do | Onboarding LLM cost is trivial (~$0.001/user with Gemini 2.0 Flash). Better UX to give everyone the full onboarding experience at our expense than to drop them on an empty dashboard. |
| Starter credit grant | Won't Do | Users will purchase credits when ready. No free tier — onboarding itself is free but ongoing LLM features (job scoring, ghostwriting) require purchased credits. |
| Activity dashboard | Deferred | Wait until frontend UI/UX is more refined before investing in dashboard widgets. |

**What needs to be built:**
- **Activity dashboard** (`/dashboard`) — logged-in users see their activity summary: recent jobs, application pipeline status, credit balance, quick actions. Future home for insight engine cards (#11).
- **User customization** — users can choose which widgets/cards to display and reorder them. Persist preferences per user (e.g., `dashboard_layout` JSON column or `user_preferences` table).

**Key files (existing):**
- `frontend/src/app/(main)/dashboard/page.tsx` — current dashboard page
- `frontend/src/app/(main)/layout.tsx` — authenticated layout

**Open questions:**
- Widget set: which cards are available? (Recent jobs, pipeline status, credit balance, quick actions, insight engine cards)
- Persistence: JSON column on users table vs separate preferences table?
- Default layout for new users?
- Drag-and-drop reordering or simpler toggle-based customization?

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

**The problem:** The current UI looks like generic AI-generated React — functional but lifeless. Default shadcn/ui styling, no visual personality, no brand identity. It needs a human eye (or a vision-capable AI acting as one) to assess the actual rendered experience and draft concrete improvements.

**Approach options:**
- **Option A:** Iterative self-improvement — pick a design reference (Linear, Vercel, Notion) and systematically align component styling
- **Option B:** Tailwind UI / shadcn themes — purchase and apply a polished theme pack for rapid uplift
- **Option C:** Designer engagement — hire a designer for brand identity + component specs, implement from their deliverables
- **Option D (preferred): Claude Vision audit via Desktop / Cowork** — use Claude Code's desktop integration (cowork mode) with vision capabilities to automate requirements gathering. The workflow:
  1. **Screenshot capture** — run the app locally and capture screenshots of every major page/flow (onboarding, dashboard, persona, jobs, resumes, cover letters, settings, chat, admin)
  2. **Vision-based audit** — feed screenshots to Claude with vision to analyze the current UX: layout issues, visual hierarchy gaps, inconsistent spacing, missing affordances, generic styling, empty state problems, mobile breakpoint issues
  3. **Design critique document** — Claude drafts a per-page critique with specific, actionable findings (not vague "make it better" — concrete issues like "the job card score badge has no visual weight", "onboarding steps lack progress context", "empty states use plain text with no illustration or CTA")
  4. **Reference comparison** — capture screenshots of design reference targets (Linear, Vercel, Notion) and have Claude compare specific components side-by-side with ours to identify the delta
  5. **Improvement spec** — from the critique, generate a prioritized improvement plan with before/after mockup descriptions, targeting the highest-impact pages first
  6. **Iterative implementation** — implement changes page-by-page, re-screenshotting after each pass to verify the visual improvement lands as intended

  **Why this works:** Claude can literally see what a user sees — no guessing from JSX whether the rendered output looks good. Vision-based audit catches things code review never will: awkward whitespace, visual imbalance, color contrast issues, information density problems, and the overall "feel" that makes a UI look polished vs. generated.

  **Requirements:** Claude Code desktop app or VS Code extension with cowork mode, local dev server running (`npm run dev`), browser accessible for screenshots.

**Key files:**
- `frontend/src/app/globals.css` — CSS variables, theme definitions
- `frontend/src/components/ui/` — 28 shadcn/ui components (customizable)
- `frontend/src/app/(main)/page.tsx` — home/dashboard page
- `frontend/src/app/(main)/layout.tsx` — main layout with navigation

**Admin UI improvements (routing table — REQ-022 §10.3):**
- Task type field should be a dropdown populated from `TaskType` enum (REQ-009 §4.3), not freeform text
- Clarify provider column — currently unclear which row maps to which provider
- Clean up vestigial multi-provider rows (BYOK from REQ-009 replaced by centralized billing in REQ-023). Single-provider mode only needs one row per task type; consider preventing duplicate task_type entries or at minimum making it obvious which entry is active. See also PBI #27 (Remove BYOK).

**Open questions:**
- Design reference: which existing product should we visually aspire to?
- Custom font: worth the web font loading cost?
- Illustrations: use an icon library (Lucide already included) or custom illustrations?
- Dark mode: primary mode or secondary? (Affects design priority)
- Scope: full redesign or targeted polish of highest-traffic pages first?
- Cowork/Desktop: which pages to screenshot first? (Suggest: onboarding flow and job dashboard — highest user traffic)

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

### 24. Resume Editor — TipTap Rich Text ✅

**Category:** Frontend / Backend / LLM
**Added:** 2026-03-02
**Updated:** 2026-03-04 (promoted to REQ-025, REQ-026, REQ-027)
**Completed:** 2026-03-06
**Priority:** P2 — Core resume workflow upgrade. Replaces current static resume view with an interactive editor.
**Depends on:** Nothing (can start anytime)
**Status:** Complete — implemented via REQ-025 (TipTap Editor Foundation), REQ-026 (Resume Editing Workflow), REQ-027 (Resume Collaboration & AI-Assisted Editing). 9 phases, 28 tasks.

Replace the current resume management flow with a TipTap rich text editor that supports real-time AI-assisted writing. Users pick a starter template, Claude streams tailored content directly into the editor, and users can edit, tweak, then export to PDF or DOCX.

**What needs to be built:**

- **TipTap editor integration** — embed TipTap (ProseMirror-based) rich text editor in the Next.js frontend. Right-side panel layout for the editor, left side for controls/context.
- **Starter templates** — pre-baked markdown/HTML templates: Clean/Minimal, Modern, Executive, Technical. Each defines section structure, heading styles, and layout conventions.
- **Template picker UI** — selection screen when creating a new resume. Preview thumbnails or rendered previews of each template style.
- **AI writing into editor** — Claude generates resume content and writes it directly into the TipTap editor via full document replace (Option 1: tailoring workflow — AI generates complete document, user edits from there).
- **Streaming output** — stream LLM response into the editor in real time so the user watches the resume populate progressively. Uses SSE or similar streaming transport from the backend.
- **Export to PDF** — leverage existing ReportLab + Platypus backend pipeline. Convert editor content (markdown/HTML) to PDF server-side.
- **Export to DOCX** — new export path using `python-docx`. Convert editor content to formatted Word document server-side.
- **Markdown storage** — store resume content as markdown on the backend for clean LLM read/write. TipTap renders markdown ↔ rich text bidirectionally. Markdown is the canonical format for LLM input/output.

**Key considerations:**
- TipTap has a free open-source core (`@tiptap/core`, `@tiptap/react`) and paid pro extensions. The free tier covers what we need (headings, lists, bold/italic, links). Evaluate whether pro extensions (collaboration, comments) are needed later.
- Streaming into the editor requires careful handling — TipTap transactions need to be batched so the editor doesn't re-render on every token. Buffer chunks and flush at sentence or paragraph boundaries.
- Template structure should be defined as markdown with front-matter metadata (template name, category, description) so templates are easy to add and maintain.
- Markdown ↔ HTML round-tripping must be lossless for the features we use. TipTap's markdown extension handles this, but test edge cases (nested lists, links, bold+italic).
- DOCX export styling should approximate the PDF output for consistency. Users expect similar-looking documents regardless of export format.

**Key files (new):**
- `frontend/src/components/resume/resume-editor.tsx` — TipTap editor wrapper
- `frontend/src/components/resume/template-picker.tsx` — template selection UI
- `frontend/src/lib/templates/` — starter template definitions (markdown files)
- `backend/app/services/docx_export_service.py` — DOCX generation via python-docx
- `backend/app/api/v1/resume_export.py` — export endpoints (PDF + DOCX)

**Dependencies (new):**
- `@tiptap/core`, `@tiptap/react`, `@tiptap/starter-kit`, `@tiptap/extension-markdown` — TipTap editor (npm, free/open-source)
- `python-docx` — DOCX generation (pip)

**Open questions:**
- Should users be able to edit the template structure itself (add/remove sections), or only fill in content within the template's predefined sections?
- Collaborative editing (multiple tabs/devices) — needed for MVP or deferred?
- Version history in the editor — show diffs between AI-generated versions?
- How to handle template switching after content exists — warn and replace, or attempt content migration?
- Should markdown be the source of truth with HTML as a render format, or store both?

---

### 27. Remove BYOK Multi-Provider Architecture ✅

**Category:** Backend / Refactor
**Added:** 2026-03-04
**Closed:** 2026-03-09 — Superseded by REQ-028 (Cross-Provider Task Routing)
**Priority:** P1 — Simplify before building new features on top of vestigial complexity.
**Depends on:** #24 (TipTap Resume Editor) — do this right after the TipTap implementation
**Status:** Closed — superseded. REQ-028 formalized multi-provider routing as a feature (admin-configured per-task routing across Claude/OpenAI/Gemini). The multi-provider architecture is no longer vestigial; it is actively used. BYOK was marked "Not Planned" in REQ-009 §10.

The original architecture (REQ-009 §4 Provider Abstraction Layer) supported Bring Your Own Key (BYOK) where each user could configure their own LLM provider (Claude, OpenAI, Gemini). REQ-023 (USD-Direct Billing) replaced this with centralized billing where the platform pays for LLM calls and bills users via funding packs. The admin routing table (REQ-022 §10.3) was designed for multi-provider routing but now only needs single-provider support. BYOK is no longer part of the product model.

**Decision context:** During REQ-025/026/027 audit (2026-03-04), reviewing gap #12 (LLM model selection for resume generation) revealed the admin routing table has vestigial multi-provider rows per task type. Since REQ-023 moved to centralized billing, the multi-provider architecture adds complexity without value.

**What remains from BYOK that should be removed:**
- **Three provider adapters** — `claude_adapter.py`, `openai_adapter.py`, `gemini_adapter.py` each with their own routing tables. Only one provider is used at a time; the others are dead code.
- **Per-provider routing rows in admin table** — each task type has 3 rows (one per provider). Single-provider mode only needs one row per task type.
- **`LLM_PROVIDER` env var** — selects active provider at startup. Should be replaced with direct configuration.
- **Provider factory/selection logic** — `get_llm_provider()` in deps.py dynamically picks the adapter. Can be simplified to a single adapter.
- **User-facing API key settings** — any endpoints or UI for users to input their own API keys (if they exist).

**Approach:**
1. Pick the production provider (likely Claude or Gemini based on cost/quality testing)
2. Collapse the three adapters into one, or keep only the chosen adapter
3. Simplify routing table to one row per task type (remove provider column or make it implicit)
4. Remove provider selection logic from DI container
5. Clean up unused env vars, schemas, and tests for removed providers
6. Keep the `LLMProvider` interface — good abstraction even with one implementation (testability, future flexibility)

**Estimated scope:** Medium — touches provider layer, DI, admin routing, tests. No user-facing behavior change.

**Key files:**
- `backend/app/providers/llm/` — all three adapters + base
- `backend/app/providers/metered_provider.py` — MeteredLLMProvider
- `backend/app/api/deps.py` — provider DI wiring
- `backend/app/models/admin_config.py` — routing table model
- `backend/app/services/admin_config_service.py` — routing lookup

---

### 4. Render Deployment Configuration

**Category:** DevOps / Infrastructure
**Added:** 2026-02-16
**Updated:** 2026-03-01 (updated dependencies for new ordering)
**Priority:** P4 — Deploy after metering + payments are functional.
**Depends on:** ~~#1 (Authentication), #2 (Multi-Tenant)~~ ✅, ~~#12 (Token Metering)~~ ✅, ~~#16 (Admin Pricing)~~ ✅, ~~#13 (Stripe Integration)~~ ✅

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

### 25. MVP Security Audit & Penetration Testing

**Category:** Security / Testing / Quality
**Added:** 2026-03-02
**Priority:** Critical — Complete before public launch. Final gate before real user data is at risk.
**Depends on:** All MVP items complete (~~#16~~ ✅, ~~#19~~ ✅, ~~#13~~ ✅, #20, #23, #24, #14, #4), private Render deployment live
**Assigned to:** Claude Code (Opus 4.6) + Brian (joint review)

Structured white-box security audit and penetration test of the full Zentropy Scout system. Conducted against the live Render deployment (not localhost) to capture infrastructure-level issues. Goal: surface and remediate vulnerabilities before real user data and payment information are at risk.

**Prerequisites:**
- MVP feature complete and deployed to Render (private access only)
- Architecture document generated from actual codebase (Phase 1 output)
- Brian actively using the system for job search (dogfooding)
- All existing scanner findings (Semgrep, ZAP, SonarCloud, pip-audit, npm audit) resolved or triaged

**Existing security coverage (do not duplicate):**
- 8 automated security tools across 3 stages (pre-commit, CI, runtime) — see CLAUDE.md "Security Tooling Stack"
- 56 unit tests for LLM sanitization pipeline (syntactic injection patterns, Unicode normalization, confusable mapping)
- 4 custom Semgrep taint rules for LLM-specific injection detection
- Hypothesis fuzz testing for sanitization invariants
- Playwright E2E tests validating all security headers (HSTS, CSP, X-Frame-Options, etc.)
- CORS runtime validation (app refuses to start with wildcard + credentials)
- NullByteMiddleware (strips `\x00` from query strings and JSON bodies)
- Cross-tenant leakage tests for applications and job postings

**What needs to be tested (10 phases):**

---

#### Phase 1: Architecture Document Generation (~1-2 days)

Goal: Produce a ground-truth map of the system before auditing it.

Have Claude Code traverse the full codebase and generate a system architecture document covering:
- All API endpoints with auth requirements and rate limits
- Database schema with `user_id` scoping patterns and FK chains
- Auth flow diagrams for all four paths (Google OAuth, LinkedIn OAuth, magic link, email/password)
- Account linking/unification logic flow
- JWT lifecycle: creation, claims (`sub`, `aud`, `iss`, `exp`, `iat`, `adm`, `pwr`), revocation via `token_invalidated_before`
- Credit transaction flow end to end (balance gating → LLM call → atomic debit → ledger entry)
- Bookmarklet capture endpoint and server-side fetch pipeline
- LLM routing (task_routing_config → MeteredLLMProvider → adapter model_override) and prompt construction paths
- Admin auth pipeline (ADMIN_EMAILS bootstrap → JWT `adm` claim → `require_admin` dependency)
- Shared job pool isolation boundaries (REQ-015)

Verify architecture doc matches actual implementation. Flag any drift from design intent or undocumented behavior.

---

#### Phase 2: Blast Radius Audit (~1 day)

Goal: Prioritize attack surfaces by potential damage before testing begins.

Have Opus audit the architecture document and codebase:

> "You are a security auditor preparing a penetration test. Audit this codebase and produce a prioritized list of attack surfaces ranked by blast radius — the potential damage if exploited. For each surface identify the specific attack vectors, what the existing automated scanning has already covered, and what requires adversarial behavioral testing. Do not rubber stamp anything. Assume previous automated reviews missed things. Trace actual data flow — do not reason abstractly."

**Expected output — three tiers:**

**Tier 1 — Audit Before Anything Else:**
- Auth flows (all four paths + account linking + JWT revocation)
- Row-level security / multitenancy scoping (all 25+ entity types)
- Credit transaction logic (atomic debit, balance gating, ledger consistency)
- Admin privilege escalation (can non-admin access admin endpoints? can admin bypass metering?)

**Tier 2 — Audit Before Public Launch:**
- Bookmarklet capture endpoint (SSRF, auth token validation, domain restrictions)
- Server-side URL fetch (redirect following, internal network access, response size/timeout)
- LLM prompt construction (semantic injection via user personas, job descriptions, shared pool content)
- Account linking/unification edge cases (pre-auth linking, orphan accounts, cross-provider)
- Password security (HIBP fail-open behavior, bcrypt timing, reset token replay)

**Tier 3 — Audit First Month Post-Launch:**
- Remaining endpoints and flows
- Performance under concurrent load
- Rate limiting effectiveness under sustained attack

---

#### Phase 3: DAST Coverage Mapping (~0.5 day)

Goal: Understand what ZAP already tests vs. what requires custom Playwright tests.

- Map current ZAP configuration coverage (endpoints probed, attack categories, auth config)
- Note: `.github/zap-rules.tsv` is currently empty — all ZAP alerts flow unfiltered
- Identify gaps DAST cannot catch:
  - Cross-account authorization errors (requires two authenticated sessions)
  - Race conditions in credit consumption (requires concurrent requests)
  - Business logic errors requiring specific input sequences
  - Pre-authentication linking attacks (multi-step stateful flows)
  - Semantic prompt injection (requires understanding context, not pattern matching)
- Gap list becomes input for Phases 4-9 Playwright test suites

---

#### Phase 4: Auth Security Test Suite — Playwright (~3-5 days)

Goal: Adversarial behavioral testing of all four auth paths, account linking, JWT lifecycle, and password security.

Note: The project has existing Playwright mock infrastructure (`MockController` pattern in `frontend/tests/utils/`). OAuth flows require mocking provider responses. Mock edge cases real providers won't serve: email already in system, no email returned, expired token, deleted provider account.

**Four Auth Paths (all must be tested):**
- Google OAuth (PKCE + state cookie + CSRF)
- LinkedIn OAuth (PKCE + state cookie + CSRF)
- Magic link (passwordless email token)
- Email + password (bcrypt + HIBP breach check)

**OAuth State & CSRF Tests:**
- Expired state cookie (>10 minute TTL) is rejected
- Replayed state cookie is rejected (single-use)
- Tampered state cookie is rejected (HMAC validation)
- State from different browser/session is rejected
- Missing PKCE code_verifier is rejected

**Account Linking Attack Tests:**
- User A cannot link their OAuth provider to User B's existing account
- Same OAuth provider account cannot be linked to two different user accounts
- Linking attempt with unverified email is rejected

**Pre-Authentication Linking Attack Tests:**
- Attacker creates email/password account with victim's email → victim signs in with OAuth → accounts are NOT merged without email verification
- OAuth identity cannot be claimed before legitimate owner authenticates
- Email verification required before any OAuth linking completes

**Account Unlink / Orphan Tests:**
- Cannot unlink last remaining auth method (account becomes inaccessible)
- Unlinked OAuth provider cannot be immediately claimed by a new registration
- Unlinking one method does not expose account to takeover via remaining method

**JWT Revocation Tests (project-specific):**
- JWT with `iat` before `token_invalidated_before` is rejected (401)
- JWT missing `iat` claim entirely is rejected (401) — critical for revocation mechanism
- After password change, old JWTs are invalidated (`token_invalidated_before` updated)
- After admin demotion, old JWTs with `adm` claim are invalidated
- Clock skew edge case: `iat` at exact microsecond boundary of `token_invalidated_before`

**Password Security Tests:**
- HIBP breach check: known-breached password is rejected during registration
- HIBP timeout: when HIBP API is unreachable, password is allowed (fail-open — document this as accepted risk or fix)
- Password validation: minimum 8 chars, requires letter + digit + special char
- Timing-safe comparison: login with valid email + wrong password takes same time as invalid email (DUMMY_HASH pattern)
- Account enumeration: error messages for signup/login/reset do not reveal whether email exists

**Password Reset Tests (`pwr` JWT claim):**
- Reset token expires after configured TTL
- Reset token cannot be replayed after use
- Reset token scope is limited to password change only (cannot be used for session auth)

**Magic Link Tests:**
- Magic link token expires after configured TTL
- Magic link token cannot be replayed after use
- Magic link for non-existent email does not reveal whether email is registered

**Cross-Provider Consistency Tests:**
- LinkedIn OAuth session cannot access Google OAuth-created account data (unless linked)
- Email/password reset flow cannot be triggered for OAuth-only accounts
- Session tokens are invalidated on logout across all auth paths
- Concurrent sessions behave correctly
- Token expiry is enforced

---

#### Phase 5: Authorization & Access Control Tests — Playwright (~2-3 days)

Goal: Verify user A cannot access user B's data, regular users cannot access admin endpoints, and shared resources have correct isolation boundaries.

**Multitenancy Isolation (for every resource type):**
- Personas, skills, experiences, preferences — direct `user_id` FK
- Resumes, resume versions, master resumes — join through persona
- Cover letters — join through persona
- Job postings (user-scoped via `user_jobs`) — verify shared pool entries don't leak private analysis
- Applications, timeline events — join through user_jobs
- Credit transactions, usage records — direct `user_id` FK

For each resource type verify:
- Direct ID access by another authenticated user returns 404 (not 403 — prevents enumeration)
- All list endpoints return only the authenticated user's data
- Update/delete operations on another user's resource return 404
- UUIDs are used everywhere (not sequential IDs — confirm no integer IDs exist)

**Admin Access Control Tests:**
- Non-admin user receives 403 on all admin endpoints (models, pricing, routing, packs, config, users, cache)
- JWT without `adm` claim cannot access admin endpoints
- Crafted JWT with `adm: true` but invalid signature is rejected
- Admin cannot demote themselves (`CANNOT_DEMOTE_SELF` error)
- Env-protected admins (ADMIN_EMAILS) cannot be demoted (`ADMIN_EMAILS_PROTECTED` error)
- Admin operations are logged (verify audit trail exists)
- Admin toggle sets `token_invalidated_before` on target user (forces re-auth)

**Shared Job Pool Isolation (REQ-015):**
- Shared job posting content visible to all users
- User-specific analysis (scores, fit signals) private to owning user
- Injection via shared job content: malicious job description does not affect other users' LLM prompts (sanitization boundary test)

**Balance Gating (HTTP 402):**
- LLM-triggering endpoints return 402 when balance insufficient
- Non-LLM endpoints work normally with zero balance
- 402 response does not leak balance amount or pricing details

---

#### Phase 6: Credit System Integrity Tests (~1-2 days)

Goal: Verify credit math is correct and cannot be manipulated.

- Cannot spend credits not in balance (atomic debit SQL returns 0 rows → debit fails)
- Race condition test: 100 concurrent LLM requests to same endpoint — balance never goes negative
- Credit deduction and LLM call are atomic — partial failure (LLM error after debit) records usage but does not leave inconsistent state
- Ledger reconciliation: `SUM(credit_transactions.amount_usd)` equals `users.balance_usd` after any sequence of operations
- Admin multiplier changes via pricing_config do not retroactively affect in-flight transactions (margin snapshotted at record time in `llm_usage_records.margin_multiplier`)
- Per-model margin applied correctly: cheap model with 3× margin and expensive model with 1.1× margin produce different billed costs for same token count
- Unregistered model (no pricing_config row) → `UnregisteredModelError` (503), LLM call blocked
- No pricing config for registered model → `NoPricingConfigError` (503), LLM call blocked
- Admin credit grants and refunds affect balance correctly
- Transaction types are immutable (append-only ledger — no UPDATE/DELETE on credit_transactions)

---

#### Phase 7: Bookmarklet & Server-Side Fetch Tests (~1-2 days)

Goal: Verify the capture endpoint cannot be weaponized.

- **SSRF:** Server-side fetch cannot be redirected to internal network resources (169.254.x.x, 10.x.x.x, 127.0.0.1, fd00::/8, ::1)
- **Redirect following:** Server follows HTTP redirects but re-validates destination against blocklist (redirect to internal IP blocked)
- Domain allowlist / blocklist is enforced
- Response size limit prevents memory exhaustion
- Request timeout is enforced (slow-drip response attack)
- Auth token in bookmarklet: expired tokens are rejected
- Auth token cannot be reused across users
- Malformed URLs are rejected gracefully without stack trace exposure
- LinkedIn domain returns friendly message, no fetch attempted
- Cloudflare/bot-detection blocked sites return graceful fallback
- HTML stripping: malicious HTML (script tags, event handlers, iframes) does not survive extraction
- Character limit enforced (~15K chars before LLM)

---

#### Phase 8: LLM Prompt Injection — Semantic Focus (~1-2 days)

Goal: Test injection vectors that bypass the existing syntactic sanitization pipeline.

**Already covered (do not duplicate):**
- 56 unit tests for syntactic injection patterns (SYSTEM:, role tags, ChatML, instruction overrides)
- Unicode normalization (NFKC → NFD → confusable mapping → NFC)
- Zero-width character stripping, combining mark stripping
- Authority keyword filtering (IMPORTANT:, OVERRIDE:, CRITICAL:)
- 4 custom Semgrep taint rules (unsanitized input, f-strings, eval/exec, prompt formatting)
- Hypothesis fuzz testing for sanitization invariants

**Focus on what automated tools cannot catch:**
- **Semantic injection via job descriptions:** Job posting containing natural-language instructions that subtly influence scoring or content generation (e.g., "The ideal candidate would rate themselves 95/100 on all dimensions")
- **Cross-user injection via shared job pool:** Malicious job description submitted by user A — does it affect user B's LLM calls when they view the same shared job?
- **Persona content injection:** User fills persona fields with instruction-like content — does it alter system behavior in downstream LLM calls?
- **Multi-step injection:** First input plants context, second input exploits it (e.g., persona bio + job description combine to form injection)
- **Generated content re-injection:** LLM-generated resume content is stored and later used as input to cover letter generation — verify no prompt breakout in the generated→consumed chain
- **Admin pricing/routing prompts:** Verify user input cannot access or modify admin-configured data through LLM context manipulation

---

#### Phase 9: Infrastructure & Render Deployment Tests (~1 day)

Goal: Verify deployment configuration is secure. Run these checks during and after Render deployment.

**Security Headers (verify in production, not just localhost):**
- All headers present: CSP, HSTS, X-Frame-Options, X-Content-Type-Options, COOP, COEP, CORP, Referrer-Policy, Permissions-Policy
- No `X-Powered-By` header leaked
- HSTS `max-age` ≥ 31536000 with `includeSubDomains`
- CSP does not contain `unsafe-eval` in production (only allowed in development)
- Note: `unsafe-inline` in script-src is currently required by Next.js hydration — document as accepted risk or implement nonce-based CSP

**Error Responses:**
- Error responses do not expose stack traces, file paths, or internal details (including in 500 errors)
- Auth errors return generic 401 (no "expired", "bad signature", "invalid audience" specifics)

**Environment & Secrets:**
- Environment variables confirmed not in codebase (gitleaks pre-commit already covers this — verify)
- Database connection string not logged at any log level
- `AUTH_SECRET` is ≥32 characters (runtime validation exists — confirm it fires)
- `METERING_ENABLED=true` in production (not accidentally `false`)

**CORS:**
- `allowed_origins` set to production frontend domain only (not `http://localhost:3000`)
- No wildcard `*` with credentials (runtime validation blocks startup — confirm)

**Rate Limiting:**
- Rate limits enforced on: login (10/min), signup (5/min), OAuth initiation (10/hour), LLM endpoints (10/min), embeddings (5/min)
- Rate limiting uses per-user keying when authenticated, per-IP when not
- Note: in-memory rate limit storage is single-instance only — if multi-instance deployment planned, requires Redis backend (`RATELIMIT_STORAGE_URL`)

**NullByteMiddleware:**
- `%00` in query string is stripped (not passed to PostgreSQL)
- `\x00` in JSON body string values is stripped
- Double-encoding (`%2500`) is handled
- Oversized JSON body (>10MB) behavior is documented (currently passed through unsanitized)

**Admin Endpoints:**
- Admin routes not publicly discoverable (no links in public UI for non-admins)
- Admin API endpoints return 403 for unauthenticated and non-admin requests

---

#### Phase 10: Remediation & Regression (~2-5 days, variable)

Goal: Fix all findings and prevent regression.

- All Tier 1 findings remediated before any user access beyond Brian
- All Tier 2 findings remediated before public launch announcement
- Each Playwright security test that finds a real vulnerability becomes a permanent regression test in the E2E suite
- Findings log maintained per finding: attack vector, blast radius, which automated tool missed it and why, fix applied, regression test added
- Architecture document updated to reflect any implementation changes made during remediation
- Security scanner baselines updated (SonarCloud, ZAP rules, Semgrep)

---

**Success criteria — public launch approved when:**
- All Tier 1 and Tier 2 blast radius items have been tested and resolved
- All Playwright auth, authorization, and credit integrity tests pass
- No HIGH or CRITICAL findings outstanding in Semgrep, ZAP, SonarCloud, pip-audit, or npm audit
- Brian has used the system for his own job search for at least 2 weeks on Render without data issues
- Architecture document accurately reflects the deployed system
- Findings log is complete with regression tests for every real vulnerability found

**Effort estimate:** ~15-25 working days total across all phases. Phase 4 (auth) is the largest and most valuable.

**Key considerations:**
- Zero-trust posture throughout — do not accept "this is fine" without data flow trace
- The security-triage subagent false positive challenge protocol remains active — subagent findings challenged with same rigor as true positives
- Manual review by Brian remains the final layer — automated systems have demonstrated gaps
- Each finding should document: attack vector, blast radius, which automated tool missed it and why, fix applied, regression test added

**Open questions:**
- Should HIBP fail-open be converted to fail-closed before launch? (Reject password if breach check is unavailable)
- CSP `unsafe-inline` for scripts — implement nonce-based CSP via Next.js middleware, or accept the risk?
- Multi-instance rate limiting — will Render deployment use multiple instances requiring Redis?
- Should the audit produce a formal report document, or is the findings log sufficient?
- External penetration testing — hire a third-party firm for a second opinion, or rely on internal audit only?

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

**Chat-driven resume editing (deferred from REQ-027):** The chat agent should have tool access to resume editing — the user can modify resumes through natural language conversation (e.g., "Make the summary more concise", "Emphasize my SAFe experience"). This was originally specified in REQ-027 §3 (v0.1) but deferred here because it requires the same chat infrastructure, conversation persistence, and agentic tool-use patterns that the broader chat agent needs. Building it as part of the chat agent avoids duplicating chat infrastructure. The chat agent's tool set should include resume operations alongside the existing 8 tools: `edit_resume_section`, `rewrite_resume`, `tailor_variant_for_job`, etc. When editing variants, the chat context should include job posting requirements for job-aware conversational editing.

**Requirements references:** REQ-007 §4 (superseded by this item), REQ-012 (frontend home screen), REQ-027 §3 v0.1 (chat-driven resume editing, deferred here)

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

### 15. Performance Audit, Stress Testing & CI/CD Workflow Automation

**Category:** Backend / Frontend / DevOps / Performance
**Added:** 2026-02-28
**Updated:** 2026-03-02 (expanded scope — stress testing, profiling, CI/CD integration)
**Priority:** Post-MVP — No user-facing impact until high concurrency, but should be addressed before scaling.
**Depends on:** #4 (Render Deployment) for production profiling; can start local stress testing anytime

Comprehensive performance audit and workflow automation to prepare for scaling. Covers async/sync correctness, load testing, profiling, database query optimization, and CI/CD pipeline improvements.

#### Part 1: Async/Sync Correctness Audit

**Motivation:** During REQ-020 implementation, SonarCloud S7503 findings revealed that `async def` without `await` is an intentional FastAPI optimization (avoids `run_in_threadpool()` overhead). This raised the question: are there other places where sync functions unnecessarily use the thread pool when they could be async, or vice versa?

**Key areas to audit:**
- All FastAPI dependency functions in `backend/app/api/deps.py`
- Service layer methods that only perform fast synchronous operations
- Provider factory functions and singleton patterns
- Database session lifecycle management
- Middleware and exception handler async patterns
- Background task scheduling patterns

**Expected outcome:** Documentation of which functions are intentionally async-without-await (with rationale), identification of any functions that should be converted for better scalability, and SonarCloud baseline updates.

#### Part 2: Load Testing & Stress Testing

Stress test the system under realistic and adversarial loads to identify bottlenecks before real users hit them.

**Tools to explore:**
- **Locust** — Python-native load testing (familiar stack, scriptable user scenarios)
- **k6** — JavaScript-based load testing (Grafana ecosystem, good CI integration)
- **Artillery** — YAML-defined load scenarios (quick setup, good for API testing)
- **vegeta** — HTTP load testing CLI (simple, good for targeted endpoint stress)

**Scenarios to test:**
- Concurrent LLM-triggering requests (metering + balance gating under contention)
- Database connection pool exhaustion under sustained load
- Concurrent resume/cover letter generation (PDF + LLM pipeline)
- Rate limiter behavior under burst traffic (in-memory vs Redis-backed)
- Cold start latency (first request after idle — relevant for Render deployment)
- Sustained API throughput (CRUD operations without LLM calls)
- WebSocket/SSE streaming under concurrent connections (if applicable)

**Key metrics to capture:**
- p50/p95/p99 response times per endpoint
- Throughput ceiling (requests/sec before degradation)
- Database connection pool utilization
- Memory usage under sustained load
- Error rate under stress (5xx, timeouts, connection refused)

#### Part 3: Profiling & Query Optimization

**Backend profiling tools:**
- `py-spy` — sampling profiler (low overhead, attach to running process)
- `viztracer` — trace-based profiler (detailed call graphs)
- FastAPI timing middleware (per-request latency logging)
- SQLAlchemy query logging + `EXPLAIN ANALYZE` for slow queries

**Database optimization targets:**
- Missing indexes on frequently filtered columns
- N+1 query patterns in list endpoints
- Connection pool sizing (`pool_size`, `max_overflow`, `pool_timeout`)
- Query plan analysis for vector similarity searches (pgvector `ivfflat` vs `hnsw` index performance)

**Frontend profiling:**
- React DevTools Profiler (component render frequency)
- Lighthouse performance scores
- Bundle size analysis (`next/bundle-analyzer`)
- Core Web Vitals baseline measurement

#### Part 4: CI/CD Workflow Automation

Improve the development and deployment pipeline for reliability and speed.

**Current CI state:**
- Pre-commit: ruff, bandit, gitleaks, mypy, ESLint, Prettier, TypeScript check
- Pre-push: full pytest + Vitest (~90-135s)
- GitHub Actions: Semgrep, SonarCloud, ZAP DAST, pip-audit, npm audit, Dependabot

**Potential improvements to explore:**
- **Performance regression testing in CI** — run a lightweight load test on every PR to catch regressions (e.g., k6 with threshold assertions)
- **Parallel test execution** — split pytest across workers (`pytest-xdist`) to reduce pre-push time
- **Test result caching** — skip unchanged test files on pre-push (e.g., `pytest --lf` or hash-based caching)
- **Deployment automation** — Render deploy-on-merge pipeline (when #4 is complete)
- **Database migration safety** — automated migration dry-run in CI before merge
- **Dependency update automation** — Dependabot PR auto-merge for patch versions with passing CI
- **Performance budget enforcement** — Lighthouse CI or bundle size checks that block PRs exceeding thresholds
- **Canary/staged deployments** — gradual rollout strategy for Render (if multi-instance)

#### Open Questions

- Which load testing tool best fits the stack? (Locust feels natural for Python, k6 has better CI integration)
- What's the target scale? (hundreds? low thousands? tens of thousands concurrent?)
- Should performance baselines be enforced in CI (fail PR if p95 regresses) or advisory-only?
- Is Render's free/starter tier sufficient for load testing, or do we need a dedicated staging environment?
- Should database connection pooling use PgBouncer on Render, or rely on SQLAlchemy pool alone?
- Pre-push hooks take ~90-135s — is `pytest-xdist` parallelization worth the setup complexity?

---

### 26. Terms of Service & Privacy Policy

**Category:** Legal / Frontend
**Added:** 2026-03-02
**Priority:** Post-MVP — Required before public launch with real users and payment processing.
**Depends on:** ~~#13 (Stripe Credits Integration)~~ ✅, #4 (Render Deployment) — ToS must reflect the final billing model and hosting setup

Draft and implement Terms of Service and Privacy Policy for Zentropy Scout. Both documents must be drafted together since they cross-reference each other (ToS §7 and §10 reference the Privacy Policy directly). These are legal requirements before accepting real user data and payments.

**Note:** This outline is a starting point, not legal advice. Consider professional legal review before publishing.

#### Terms of Service — Outline

**§1. Acceptance of Terms**
- Agreement by using the service
- Age requirement (13+ or 18+)
- Updates to terms and notification method

**§2. Description of Service**
- What Zentropy is (AI-assisted job search tool)
- Free tier vs paid features
- AI-generated content is assistive, not guaranteed accurate
- Service provided "as is"

**§3. Account Registration**
- Accurate information requirement
- Account security responsibility
- One account per user
- Account termination rights (user's and Zentropy's)

**§4. Acceptable Use**
- No scraping or automated abuse
- No impersonation
- No illegal activity
- No attempts to circumvent credit system
- No uploading malicious content
- No reselling access

**§5. Credits and Payment**
- How credits work (USD-direct, pay as you go)
- No refunds on consumed credits
- Unused balance policy
- What happens to balance on account termination
- Stripe as payment processor
- Price change notice

**§6. AI-Generated Content**
- Content is AI-assisted, not professional advice
- Not a substitute for professional career counseling
- User responsible for verifying accuracy before submitting to employers
- No guarantee of job search outcomes
- User owns their generated resumes and cover letters

**§7. User Data and Privacy** *(references Privacy Policy)*
- Reference to Privacy Policy (separate document)
- What data is collected
- How job data works (shared pool vs personal data)
- Job posting data contributed to shared database is not deleted on account termination
- Personal profile, resume, and application data deleted on request

**§8. Intellectual Property**
- Zentropy owns the platform, brand, and underlying technology
- User owns content they create (resumes, cover letters)
- User grants Zentropy license to process their data to provide the service
- No license to use Zentropy branding

**§9. Third Party Services**
- Stripe (payments)
- Anthropic (AI)
- Google (OAuth, AI)
- Render (hosting)
- Not responsible for third party terms or outages

**§10. Job Data and Crowdsourcing** *(references Privacy Policy)*
- How the shared job database works
- User contributions to shared pool
- No guarantee of job posting accuracy or freshness
- Zentropy not responsible for job posting content
- Not an employer or recruiter

**§11. Limitation of Liability**
- No guarantee of service availability
- Not liable for job search outcomes
- Not liable for AI content accuracy
- Cap on liability (typically limited to amount paid in last 12 months)
- No consequential damages

**§12. Disclaimers and Warranties**
- No warranty of fitness for particular purpose
- No warranty of uninterrupted service
- AI outputs may contain errors

**§13. Indemnification**
- User indemnifies Zentropy for misuse
- User responsible for their own job applications

**§14. Termination**
- How users can close their account
- How Zentropy can terminate accounts (ToS violations)
- What happens to data on termination
- What happens to unused credits on termination

**§15. Dispute Resolution**
- Governing law (Arizona)
- Informal resolution first
- Arbitration clause (optional but common for SaaS)
- Class action waiver (optional)

**§16. Changes to Terms**
- Right to modify terms
- Notice period
- Continued use constitutes acceptance

**§17. Contact Information**
- How to reach Zentropy for ToS questions
- DMCA contact if applicable

#### Privacy Policy — Outline (Separate Document, Draft Together)

Must be consistent with ToS §7 and §10. Detailed outline to be expanded when scoping begins. Key areas:
- What personal data is collected (persona, work history, skills, preferences)
- What job data is collected and how it enters the shared pool
- How AI providers process user data (Anthropic, Google, OpenAI)
- Data retention and deletion policies
- Cookie and session token usage
- Third-party data sharing (Stripe, auth providers, hosting)
- User rights (access, correction, deletion, export)
- CCPA/GDPR considerations based on user base geography
- Children's privacy (COPPA if age threshold is 13+)

#### Implementation Notes

**What needs to be built:**
- **Frontend pages** — `/terms` and `/privacy` routes with rendered legal content
- **Consent capture** — checkbox or banner during registration/first login ("By continuing, you agree to our Terms of Service and Privacy Policy")
- **Version tracking** — store ToS version accepted by each user + timestamp, re-prompt on major updates
- **Footer links** — ToS and Privacy Policy links in site footer (visible on all pages including login)
- **Account deletion flow** — must align with ToS §14 and Privacy Policy deletion commitments
- **Data export** — consider "download my data" feature to support user rights (Privacy Policy)

#### Open Questions

- Professional legal review — hire a lawyer or use a template service (Termly, Iubenda, etc.)?
- Age requirement — 13+ (broader reach, COPPA implications) vs 18+ (simpler compliance)?
- Arbitration clause — include or skip? (Common in SaaS but user-hostile)
- Class action waiver — include or skip?
- GDPR scope — will Zentropy have EU users? If so, need DPA and EU-specific provisions
- Data export format — JSON dump? PDF? Both?
- Cookie consent banner — needed for EU visitors even if not targeting EU market?

---

### 17. Pricing Simulation Tool

**Category:** Backend / Frontend / Admin
**Added:** 2026-03-01
**Priority:** P2 — Important for informed pricing decisions before and after launch.
**Depends on:** ~~#16 (Admin Pricing Dashboard)~~ ✅

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
**Depends on:** ~~#16 (Admin Pricing Dashboard)~~ ✅

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

### 28. Test Suite Audit & Cleanup

**Category:** Testing / DX
**Added:** 2026-03-08
**Priority:** Post-MVP — Technical debt. Suite passes but has quality issues.
**Depends on:** Nothing (can start anytime)

Audit the full backend test suite for consistency, isolation, and pytest-asyncio best practices. A fixture decorator mismatch (`@pytest.fixture` on `async def` instead of `@pytest_asyncio.fixture`) and a missing root `pytest.ini` caused 570 false failures in full-suite runs — fixed in commit `7b0d3e4`, but a broader audit is warranted.

**What needs to be done:**
- **Fixture decorator audit** — scan for any remaining `@pytest.fixture` on `async def` functions (the batch fix in 7b0d3e4 caught 12 files; verify no new ones appear)
- **Test isolation verification** — confirm no test relies on execution order or shared mutable state
- **Antipattern hook review** — the conftest AST scanner reports `isinstance` usage in ~15 tests; evaluate whether these are genuine antipatterns or false positives
- **pytest-asyncio configuration** — evaluate `asyncio_default_fixture_loop_scope` setting; ensure consistency between root `pytest.ini` and `backend/pyproject.toml`
- **Test runtime profiling** — the full suite takes ~8 minutes; identify slow tests and consider parallelization (`pytest-xdist`)
- **CI alignment** — ensure CI runs `pytest` the same way local dev does (same config, same CWD)

**Key files:**
- `pytest.ini` — root-level pytest config (added in 7b0d3e4)
- `backend/pyproject.toml` — `[tool.pytest.ini_options]` section
- `backend/tests/conftest.py` — top-level test fixtures
- `backend/tests/unit/conftest.py` — unit test fixtures

---

### 29. Billing & Metering Hardening — Reservation Pattern + Stripe Fixes

**Category:** Backend / Frontend / Security / Billing
**Added:** 2026-03-27
**Priority:** P1 — Financial integrity. Must complete before public launch.
**Depends on:** ~~#13 (Stripe Credits Integration)~~ ✅, ~~#19 (USD-Direct Billing)~~ ✅, ~~#12 (Token Metering)~~ ✅, ~~#16 (Admin Pricing)~~ ✅

Steelman analysis of the billing/metering/Stripe stack identified 16 findings across 4 tiers. Three independent reviews (original analysis + code-reviewer + security-reviewer) reached consensus on severity and prioritization. The most significant architectural gap is that the metering system uses a post-debit pattern where the balance check and the debit are separate steps with a race window — industry standard for prepaid billing is a **pre-debit reservation pattern** (similar to credit card pre-auth).

#### Origin

Adversarial code review session on 2026-03-27. Full trace of all billing files across backend and frontend. Cross-referenced against REQ-020 (metering), REQ-021 (credits/billing), REQ-022 (admin pricing), REQ-023 (USD-direct billing), and REQ-029 (Stripe checkout).

#### Findings Summary (16 items, 4 tiers)

**Tier 1 — Must Fix (financial integrity):**
1. `record_and_debit` ledger/balance drift — CreditTransaction inserted even when atomic debit fails (rowcount=0), causing ledger sum to diverge from `users.balance_usd` (REQ-020 §6.3)
2. Fail-open metering — double `except Exception` in metering_service.py and metered_provider.py means DB errors = free LLM calls, contradicting REQ-020's fail-closed requirement
3. Refund handler missing `begin_nested()` savepoint — partial failure can commit credit+debit without updating `purchase.refund_amount_cents`, causing double-debit on next refund event (REQ-029 §7.3)
4. Refund handler doesn't cap `total_refunded_cents` at `purchase.amount_cents` — defense-in-depth gap (REQ-029 §7.3)
5. Refund handler doesn't guard against `payment_intent` being None — Stripe charge objects have nullable `payment_intent` (REQ-029 §7.3)

**Tier 2 — Should Fix (operational safety):**
6. `credits_enabled=True` + `metering_enabled=False` only warned, not rejected in production — allows unlimited free LLM calls after any purchase (REQ-020 §11, REQ-029 §11)
7. No `checkout.session.expired` webhook handler — orphaned `pending` records in `stripe_purchases` accumulate forever (REQ-029 §7.1)
8. `int()` truncation in purchase history display — `int(txn.amount_usd * Decimal(100))` truncates toward zero instead of rounding; sub-cent precision from margin calculations gets silently dropped (REQ-029 §8.3)

**Tier 3 — Nice to Have (hardening/hygiene):**
9. Frontend: `queryKeys.purchases` not invalidated on checkout success — balance updates but purchase history shows stale data (REQ-029 §9.4)
10. `MeteredLLMProvider.stream()` never calls `record_and_debit` — streaming calls completely unmetered; currently dormant (no call path) but latent risk (REQ-020 §6.2)
11. `get_or_create_customer` uses `db.rollback()` instead of savepoint — rolls back entire transaction on IntegrityError, fragile if called later in a multi-step flow (REQ-029 §6.3)

**Tier 4 — Consistency/Readability:**
12. `grant_cents` is BIGINT but `amount_cents` is INTEGER on `stripe_purchases` — inconsistent, creates "why are these different?" cognitive load for future readers
13. CLAUDE.md documents `ZentropyError` as base error class but code uses `APIError` — docs/code out of sync

#### Architectural Decision: Pre-Debit Reservation Pattern

Research into how production billing systems (Stripe Meters, OpenMeter, Orb, LiteLLM, Helicone, WarpStream, Azure API Management) handle the metering reliability problem identified the **pre-debit reservation pattern** as the industry standard for prepaid balance billing:

1. **Before LLM call:** Estimate max cost (input_tokens + max_tokens × price), atomically reserve from balance
2. **Execute LLM call** (outside any transaction)
3. **After LLM call:** Calculate actual cost, settle reservation (release hold, debit actual amount)
4. **On settlement failure:** Reservation stays held (user temporarily over-charged, reconcilable) — versus current behavior where failure means user under-charged (irrecoverable revenue loss)

This pattern eliminates findings #1 and #2 as side effects, because:
- The reservation is the balance check AND the hold in one atomic step (no race window)
- If settlement fails, the money is already held (no free calls)

Requires a new REQ document (REQ-030) before implementation.

#### Key Files

**Backend (billing core):**
- `backend/app/services/metering_service.py` — cost calculation, usage recording, balance debit
- `backend/app/services/stripe_webhook_service.py` — webhook handlers (checkout.completed, charge.refunded)
- `backend/app/providers/metered_provider.py` — MeteredLLMProvider, MeteredEmbeddingProvider
- `backend/app/repositories/credit_repository.py` — atomic balance operations
- `backend/app/repositories/stripe_repository.py` — purchase lifecycle
- `backend/app/api/deps.py` — `require_sufficient_balance`, `get_metered_provider`
- `backend/app/api/v1/webhooks.py` — webhook router
- `backend/app/api/v1/credits.py` — credits API
- `backend/app/core/config.py` — production validation
- `backend/app/models/stripe.py` — StripePurchase model
- `backend/app/models/usage.py` — CreditTransaction, LLMUsageRecord

**Frontend:**
- `frontend/src/components/usage/usage-page.tsx` — Stripe redirect handler
- `frontend/src/components/usage/funding-packs.tsx` — checkout flow

#### REQ References (Bidirectional)

| REQ | Sections Affected | Direction |
|-----|-------------------|-----------|
| REQ-020 (metering) | §6.2 (metered provider), §6.3 (atomic debit), §7.1 (balance gating), §11 (config) | This work amends REQ-020's balance check + post-debit pattern → reservation + settlement |
| REQ-021 (credits/billing) | §6.7 (transaction + atomic update), §8 (signup grant) | This work adds `held_balance` concept to the balance model |
| REQ-022 (admin pricing) | §7.4 (cost calculation) | Cost calculation unchanged; routing into reservation wrapper |
| REQ-029 (Stripe checkout) | §7.2 (checkout webhook), §7.3 (refund webhook), §7.1 (webhook router), §11 (config) | Refund handler fixes + expired session handler |
| REQ-030 (NEW — to be written) | All sections | New REQ specifying reservation pattern, settlement, reconciliation |

---

### 30. Reduce oauth_callback() Cognitive Complexity

**Category:** Backend / Code Quality
**Added:** 2026-03-28
**Priority:** P3 — Code quality (SonarCloud python:S3776, not a security vulnerability)
**Depends on:** Nothing

SonarCloud flagged `backend/app/api/v1/auth_oauth.py:oauth_callback()` with cognitive complexity 16 (limit 15). Appeared after commit acc0444 moved signup grant logic into the callback. Extract the signup credits block (~lines 261-269) or admin bootstrap block (~lines 271-281) into a helper function (`_maybe_grant_signup_credits()` or `_maybe_promote_admin()`) to reduce complexity below 15.

**Key files:** `backend/app/api/v1/auth_oauth.py`

---

### 31. Job Source Adapter Implementation — Adzuna, The Muse, RemoteOK, USAJobs

**Category:** Backend / API Integration
**Added:** 2026-04-03
**Priority:** P1 — Core job discovery pipeline. Without this, the Scouter only surfaces manually-submitted jobs.
**Depends on:** #7 (Scouter Redesign ✅), REQ-016 (JobFetchService ✅)
**Traces to:** REQ-007 §6.3, REQ-016 §1.4, REQ-003 §4.1

The `JobFetchService` orchestration and all four source adapters are scaffolded but `fetch_jobs()` on each adapter returns `[]` — intentionally deferred. This PBI implements the actual API calls that feed the shared job pool automatically.

**What needs to be built:**

- **`fetch_jobs()` on all four adapters** — real HTTP calls replacing the stub:
  - `AdzunaAdapter` — REST, 250 req/day free tier, API key auth
  - `TheMuseAdapter` — REST, 3,600 req/hour, API key auth
  - `RemoteOKAdapter` — REST, generous limits, no auth required
  - `USAJobsAdapter` — REST, 200 req/day, `User-Agent` + email header auth
- **`SearchParams` construction from persona** — translate `Persona.job_titles`, `Persona.skills`, `Persona.location_preferences`, `Persona.remote_preference`, `Persona.target_industries` into per-source query parameters
- **Pagination** — fetch multiple pages up to a configurable max (avoid blowing daily rate limits)
- **API key configuration** — env vars (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `THE_MUSE_API_KEY`, `USAJOBS_API_KEY`, `USAJOBS_EMAIL`) wired into adapter construction via `Settings`
- **Per-source error handling** — 429 rate limit backoff, 5xx retries, partial failure (one source down shouldn't abort the others)
- **Graceful degradation** — if a source's API key is not configured, skip it silently and log a warning

**REQ:** [REQ-034](../requirements/REQ-034_job_source_adapters.md) — Job Source Adapter Implementation & AI-Driven Search Profiles

**Key files (existing stubs to implement):**
- `backend/app/adapters/sources/adzuna.py`
- `backend/app/adapters/sources/remoteok.py`
- `backend/app/adapters/sources/themuse.py`
- `backend/app/adapters/sources/usajobs.py`
- `backend/app/adapters/sources/base.py` — `SearchParams` construction logic
- `backend/app/services/discovery/job_fetch_service.py` — `SearchParams` built from persona

**Open questions (to resolve in REQ-034 discussion):**
- How should AI be used to improve search relevance? (query expansion, keyword weighting, post-fetch re-ranking)
- Should `SearchParams` be persona-driven (one search per persona's profile) or job-title-driven (one search per target role)?
- How do we handle sources that don't support keyword search (RemoteOK is tag/category based)?
- What's the right page depth per source given daily rate limits?
- Should source adapters be user-configurable (opt in/out per source) or system-wide?

---

### 32. Add Fuzzer & Write Harnesses for Untrusted-Input Code Paths

**Category:** Security / Testing
**Added:** 2026-04-21

Add a formal fuzzing tier to the existing security stack (SonarQube + Semgrep SAST, ZAP DAST) to cover the gap those tools don't reach: edge-case input handling in isolated code units. Fuzzing complements the existing tools rather than replacing any of them — SAST reads source, DAST probes the running app over HTTP, fuzzing drives many-input iterations directly at specific functions to surface crashes, hangs, and unexpected exceptions.

**Motivation:** Zentropy Scout processes user-provided content at several sensitive boundaries (resume parsing, job content ingestion from heterogeneous sources, prompt construction, auth token handling). These are exactly the code shapes where fuzzing pays off — pure-ish functions that transform untrusted input and have enough branching that edge cases are hard to enumerate by hand. ZAP covers HTTP-level probing; SAST catches known pattern anti-patterns; neither will exercise a parser with a million mutated inputs the way a fuzzer will.

**Stack context:** Zentropy Scout is Python (FastAPI) backend + Next.js frontend. The highest-value fuzz targets — resume parsing, job ingestion adapters, auth token handling, prompt construction — all live server-side in Python. Tool choices below reflect that.

**Approach:**

- **Primary tool: Hypothesis** (property-based testing, already installed). One existing usage at `backend/tests/unit/test_llm_sanitization_fuzz.py` covers the sanitization pipeline; the work here is expanding that pattern to additional targets, not adopting a new tool. Harnesses are pytest files — you declare properties ("for all inputs of shape X, the parser should not raise anything other than `ValueError`") and Hypothesis generates randomized inputs hunting for counterexamples. Runs on every PR as part of the normal pytest suite. No new CI infrastructure needed.
- **Atheris (coverage-guided mutation fuzzing) — deferred.** Google's Python port of libFuzzer would find deeper bugs than Hypothesis (coverage-guided mutation vs. strategy-based generation), but at a real cost: a long-running CI job separate from the PR suite, binary corpus/reproducer management, a libFuzzer-style mental model, and some maintenance risk (Atheris's release cadence has been slow, particularly around new Python versions). The payoff shape suits high-volume public-API parsers more than our threat model (occasional user-uploaded PDFs and scraped job listings). Revisit if (a) Hypothesis plateaus after broad coverage expansion and real crashes still seem likely, or (b) the project becomes eligible for **OSS-Fuzz**, which runs Atheris harnesses as a free Google-operated service and removes most of the CI cost.
- **Frontend (fast-check) — not worth it.** Minimal pure-function logic in the Next.js client justifies the overhead; real validation lives server-side.
- **Harnesses are small (5–20 lines each)** — each Hypothesis strategy + test pair bridges generated input to a specific target function, declaring what exceptions are "expected" (e.g., `ValueError` from a parser on bad input) vs. what indicates a real bug.
- **Seed examples** — use `@example(...)` decorators or load sanitized real inputs (resumes, scraped postings, tokens) as fixtures to anchor Hypothesis's search.

**Candidate fuzz targets (in rough priority order, all Python):**

1. **Resume parsing pipeline** — pdfplumber extraction + downstream field normalization + Gemini-backed `ResumeParsingService` at `backend/app/services/rendering/resume_parsing_service.py`. High-value: malformed PDFs are a real edge-case source, and parser crashes here break onboarding.
2. **Job content ingestion / sanitization** — content coming from `AdzunaAdapter`, `TheMuseAdapter`, `RemoteOKAdapter`, `USAJobsAdapter` (`backend/app/adapters/sources/`). External data, heterogeneous shapes, worth fuzzing any normalization layer in `base.py` or the per-source adapters.
3. **Auth token handling** — JWT parsing, OAuth callback parameter parsing (Google, LinkedIn), magic link token decoding. Security-sensitive; crashes here can mean auth bypass or DoS. Related to the cognitive-complexity backlog item on `oauth_callback()` (#30).
4. **Prompt construction / templating** — any code path in `backend/app/prompts/` that interpolates user input into LLM prompts. Fuzzing can surface prompt-injection-adjacent edge cases and broken escapes.
5. **URL / query-param parsing** — bookmarklet capture (REQ-023 / item #23), job URL handling. Low priority but cheap to cover.

**How to approach implementation (read this before starting):**

The mechanical part — writing Hypothesis tests — is the smaller half of the work. The larger half is **identifying each target's invariants**: the properties that must always hold regardless of input. The tests just enforce the invariants once they're written down. Don't skip to the tests.

**The core design question for each target** is: *which exceptions are "allowed" (domain-valid rejections) vs. "forbidden" (crashes or contract violations)?* Writing this down forces clarity about the function's contract. Everything else flows from that answer.

**Step-by-step workflow:**

1. Read `backend/tests/unit/test_llm_sanitization_fuzz.py` to internalize the existing Hypothesis pattern used in this repo (it's the only existing fuzz file — follow its conventions).
2. Pick the highest-priority unstarted target from the list below.
3. Read the target file + its immediate callers + its return type. Ask: what does every caller assume about the output? What exceptions do callers handle? What do they NOT handle?
4. Draft a list of candidate invariants, split into "allowed exceptions" and "forbidden behaviors." Flag ambiguous ones for the user to confirm before writing tests (threat-model calls like "is `MemoryError` on a 2GB input acceptable?" belong to the user, not to Claude).
5. Once invariants are agreed, write the Hypothesis harness: strategies that generate plausible + adversarial inputs, properties that assert the invariants, `@example(...)` decorators seeding any known-interesting cases.
6. Run locally (`pytest backend/tests/fuzz/...` — fast, no special CI setup). Hypothesis will shrink any counterexample to a minimal reproducer.
7. For every crash Hypothesis finds: triage the reproducer (why does this input break the contract?), propose a fix, and add the minimized input as an `@example` so the test locks in the regression.
8. Commit per-target (one target = one subtask = one commit).

**Example invariants by target** (to anchor the mental model — not exhaustive):

- **Resume parser (`ResumeParsingService`):**
  - Allowed: `ValueError`, `ParseError` on malformed input.
  - Forbidden: `KeyError`, `IndexError`, `AttributeError`, `TypeError` (those mean a crash, not a rejection).
  - Forbidden: returning `None` or a partially-populated object. If it returns, the result has at minimum a `raw_text` field.
  - Forbidden: unbounded runtime on adversarial input.
- **Source adapters (`AdzunaAdapter`, etc.):**
  - Allowed: rejecting a malformed API response with a defined adapter error.
  - Forbidden: producing a `JobPosting` with missing required fields.
  - Forbidden: returning salary values that are `NaN`, negative, or where `min > max`.
  - Forbidden: Unicode corruption through normalization (input → normalize → round-trip should not mangle valid titles).
- **JWT / auth token handling:**
  - Forbidden: authenticating a token with a tampered signature (must raise, never return partial claims).
  - Forbidden: accepting a token missing `iat` (we already enforce this — lock it in with a property test).
  - Forbidden: accepting an expired token.
  - Allowed: any `InvalidTokenError` subclass on malformed input.

**Division of labor (Claude + Brian):**

- Brian picks the target and adjudicates ambiguous invariants (threat-model calls).
- Claude reads the target, drafts invariants, writes the Hypothesis harness following the existing pattern.
- Brian reviews and runs the tests (Hypothesis runs are seconds-to-minutes, no dedicated CI).
- If Hypothesis surfaces a crash, Claude triages the minimized reproducer and proposes the fix; Brian reviews.
- Commit per-target.

**Relationship to existing stack:**

- **SonarQube / Semgrep** (SAST) — reads source, finds pattern-based issues. No overlap with property tests.
- **ZAP** (DAST) — HTTP-level probing with curated attack payloads against the running app. Operates at a different layer (app-wide via network) than property tests (function-level direct calls into Python code).
- **Hypothesis** — function-level, many-input, property-driven. Finds crashes and invariant violations the other tools structurally can't reach.

**Open questions:**

- Corpus / example management — store anchor examples inline with `@example(...)` decorators or load from `backend/tests/fuzz/corpus/` fixtures?
- Which targets warrant a database-backed fixture (real sanitized resumes) vs. synthetic-only strategies?
- If a target's input is too complex for Hypothesis strategies to hit meaningfully (deeply nested PDFs, for example), that's the signal to revisit Atheris for that specific surface rather than adopting it wholesale.

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

### ~~16. Admin Pricing Dashboard & Model Registry~~ ✅

**Status:** Promoted to plan and completed
**Implemented in:** `docs/plan/admin_pricing_plan.md` — Phases 1–6 (REQ-022)
**Completed:** 5 admin DB tables (model_registry, pricing_config, task_routing_config, credit_packs, system_config), admin auth (ADMIN_EMAILS bootstrap, JWT `adm` claim, `require_admin` dependency), AdminConfigService (read-side pricing/routing/registration lookups), metering migration (hardcoded → DB-backed per-model pricing and margins), LLM adapter model_override support, AdminManagementService (CRUD with validation), 7 admin API endpoint groups, 6-tab admin frontend UI, backend integration tests, Playwright E2E tests. All tests passing.

---

### ~~12. Token Metering & Usage Tracking~~ ✅

**Status:** Promoted to plan and completed
**Implemented in:** `docs/plan/token_metering_plan.md` — Phases 1–7 (REQ-020)
**Completed:** Full metering pipeline — `llm_usage_records` + `credit_transactions` tables, MeteringService with pricing tables, MeteredLLMProvider/MeteredEmbeddingProvider proxies, balance-gating middleware (402), usage/credits/transactions API endpoints, frontend usage dashboard with balance indicator in nav. 19 integration tests, 17 E2E tests. Zero-trust suppression audit of 448 lint suppressions (154 fixed, 294 verified). 4074 backend + 3319 frontend tests passing.
