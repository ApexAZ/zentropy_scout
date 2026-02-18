# Zentropy Scout — Feature Backlog

**Created:** 2026-02-16
**Last Updated:** 2026-02-16

**Items:** 7

---

## How to Use This Document

**Purpose:** Capture feature ideas, enhancements, and future work that aren't part of the current implementation plan. Ideas here are unscoped and unprioritized until promoted to a plan or GitHub Issue.

**Format:** Each entry has a short title, description, and rough category. Add context links (REQ sections, related files, external docs) when available.

**Lifecycle:** Idea here → scope/estimate when ready → add to implementation plan or create GitHub Issue → remove from backlog.

---

## Ideas

### 1. OpenRouter Provider Adapter

**Category:** Backend / Provider Abstraction
**Added:** 2026-02-16

Add an OpenRouter adapter to enable mixing models from different providers (Anthropic, OpenAI, Google, Mistral, etc.) through a single API key. OpenRouter uses an OpenAI-compatible API, so the adapter can extend or mirror `OpenAIAdapter` with a different base URL.

**Motivation:** Cost optimization — route cheap extraction tasks to budget models (e.g., Mistral Small) while keeping quality tasks on Claude Sonnet. Single API key simplifies configuration.

**Existing overlap:**
- Provider abstraction layer already exists with adapter pattern, task-based model routing, and singleton factory (`backend/app/providers/`). Claude, OpenAI, and Gemini adapters are implemented. OpenRouter adapter follows the same pattern — no new architecture needed.
- Task-based routing (`TaskType` enum → model lookup) already maps each agent task to a specific model. OpenRouter just adds more model options to the routing table.

**Key files:**
- `backend/app/providers/llm/openai_adapter.py` (base to extend)
- `backend/app/providers/factory.py` (add `"openrouter"` case)
- `backend/app/providers/config.py` (add `OPENROUTER_API_KEY`)

**Open questions:**
- Which models for which task types? Need to benchmark quality vs cost.
- Streaming support differences between OpenRouter and native OpenAI?
- Rate limiting — OpenRouter has its own limits on top of upstream provider limits.

---

### 2. Authentication System with Account Linking

**Category:** Full Stack / Auth
**Added:** 2026-02-16

Implement user authentication with three identity providers:
- **Google OAuth** — social login via Google
- **LinkedIn OAuth** — social login via LinkedIn
- **Magic Link (email)** — passwordless email login (send a sign-in link)

**Preferred library:** NextAuth v5 (Auth.js) — the latest stable version built for Next.js 14/15 App Router. Handles OAuth flows, session management, and database adapters out of the box.

**Automatic account linking:** If a user signs in with Google using `jane@example.com`, then later signs in with LinkedIn using the same email, the accounts automatically merge into one profile. No manual linking step needed — matching is by verified email address. Users can then sign in with any linked method.

**Onboarding gate:** Middleware detects whether a newly authenticated user has completed their job preferences (skills, salary, location) and forces the onboarding flow before granting dashboard access. (Note: this gate already exists in the frontend — see `frontend/src/components/onboarding/onboarding-gate.tsx` — but currently checks persona status without auth.)

**Motivation:** Required for hosted/multi-tenant deployment on Railway. Current MVP is single-user with no auth.

**Key files:**
- `backend/app/core/config.py` (auth settings, OAuth client IDs/secrets)
- `backend/app/api/v1/router.py` (auth endpoints)
- `frontend/src/components/onboarding/onboarding-gate.tsx` (existing gate to extend)
- REQ-006 §6 (current auth placeholder)
- REQ-012 §12.4 (frontend auth placeholder)

**Existing overlap:**
- **Onboarding gate** already exists at `frontend/src/components/onboarding/onboarding-gate.tsx` — checks whether persona exists and redirects to `/onboarding` if not. Needs to be extended to check auth status first, then persona status.
- **Onboarding flow** (12-step wizard) is fully built (Phase 5). The "job preferences" step the user completes before seeing the dashboard is already implemented — just needs to run after auth instead of on first visit.
- **Auth placeholder** exists in REQ-006 §6 (backend) and REQ-012 §12.4 (frontend settings page has an "About" section with auth placeholder text).
- **API client** (`frontend/src/lib/api-client.ts`) currently makes unauthenticated requests. Needs auth header injection (Bearer token or cookie forwarding).

**Open questions:**
- Auth.js runs on the Next.js side — does the FastAPI backend verify JWT tokens from Auth.js, or does Auth.js proxy all API calls?
- Password option vs magic-link-only? (Magic link is simpler but requires email delivery service.)
- Email delivery provider for magic links (Resend, SendGrid, AWS SES)?
- How to handle the transition from single-user MVP to auth-required? Migration path for existing data?

---

### 3. Multi-Tenant Architecture

**Category:** Full Stack / Infrastructure
**Added:** 2026-02-16
**Depends on:** #2 (Authentication System)

Convert from single-user local-first architecture to multi-tenant hosted service. Each authenticated user gets their own isolated data (personas, jobs, applications, resumes, cover letters).

**Motivation:** Required for Railway deployment — multiple users sharing the same instance.

**User/Profile data split:** Separate lightweight auth data (user ID, email, OAuth tokens, session) from heavy persona/agent data (resumes, work history, skills, cover letters). Auth tables stay fast for session validation; persona tables can grow without affecting login performance.

**Key areas:**
- **Database:** Add `user_id` foreign key to all tenant-scoped tables (personas, job_postings, applications, resumes, cover_letters, etc.). Row-level filtering on every query. Auth tables (users, accounts, sessions) separate from persona tables.
- **API:** Extract authenticated user from JWT/session, inject into all repository calls. Ensure no cross-tenant data leakage.
- **Frontend:** Login/register pages, token storage, auth-aware API client, redirect to login on 401.
- **LLM/Embeddings:** Per-user usage tracking and potential rate limiting.
- **File storage:** BYTEA columns already tenant-safe (no shared filesystem paths).

**Existing overlap:**
- **Database schema** (REQ-005) currently has a single `personas` table as the root — all other tables (work_history, skills, resumes, etc.) hang off `persona_id`. Multi-tenant adds a `users` table above personas, with `user_id` FK on personas and other top-level tables (job_postings, applications).
- **Repository pattern** (`backend/repositories/`) already centralizes all DB queries. Adding `user_id` filtering means modifying each repository's query methods rather than hunting through scattered SQL.
- **BYTEA file storage** is already tenant-safe — no shared filesystem paths to worry about.
- **Frontend API client** already uses a centralized `apiGet`/`apiPost`/etc. pattern — auth header injection is a single-point change.

**Open questions:**
- Shared database with row-level isolation vs schema-per-tenant? (Row-level is simpler for MVP scale.)
- Per-user LLM API key (BYOK) vs shared pool with usage limits?
- Data export/deletion for GDPR compliance?
- Admin dashboard for user management?
- Pricing model — free tier with limits vs paid-only?

---

### 4. Tiered Job Fetch Strategy

**Category:** Backend / Job Sourcing
**Added:** 2026-02-16

API-first job fetching engine with a cost-conscious tier system:
1. **Local cache** — check PostgreSQL first for already-fetched postings
2. **Free aggregators** — query free APIs (e.g., Adzuna) for new postings
3. **Premium sources** — fall back to paid APIs (e.g., SerpApi for Google Jobs, LinkedIn scraping) only when free sources don't have results

**Motivation:** Minimize API costs by exhausting cheap/free sources before hitting paid ones. Current Scouter agent (REQ-007 §6) defines the agent flow but doesn't implement the tiered fetch priority.

**Key files:**
- `backend/app/agents/scouter/` (current Scouter agent)
- `backend/app/services/` (job fetching services to create)
- REQ-007 §6 (Scouter behavior spec)
- REQ-003 §4.2b (job source preferences)

**Open questions:**
- Which free aggregators beyond Adzuna? (Indeed API is restricted, Remotive for remote jobs?)
- SerpApi pricing model — per-search vs monthly cap?
- How to handle rate limits across multiple sources?
- User-configurable source priority? (Already spec'd in REQ-003 §4.2b and frontend settings page.)

**Existing overlap:**
- **Scouter agent** (`backend/app/agents/scouter/`) already defines the job discovery flow (REQ-007 §6) but doesn't implement specific source adapters or tiered priority. The agent calls service-layer functions that would need to be built/extended.
- **Cross-source deduplication** is partially spec'd in REQ-003 §8-9 (repost history, "Also found on" display) and REQ-007 §6.4 (Scouter cross-source matching). The normalization service (ensuring "Senior Dev at Meta" and "Sr. React Engineer at Facebook" merge) would extend this existing logic.
- **Job source preferences** UI already exists in the frontend settings page (`frontend/src/app/settings/`) — users can toggle sources on/off and drag-reorder priority (REQ-003 §4.2b, REQ-012 §12.2). The tiered fetch engine would respect these preferences.
- **Frontend job list** already supports source display, cross-source links, and ghost detection badges.

---

### 5. Job Content TTL for Legal Compliance

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

### 6. Railway Deployment Configuration

**Category:** DevOps / Infrastructure
**Added:** 2026-02-16
**Depends on:** #2 (Authentication), #3 (Multi-Tenant)

Configure `railway.toml` to deploy both the Next.js frontend and Python backend (FastAPI + background workers) on Railway.

**Key areas:**
- **Services:** Next.js frontend, FastAPI API server, Python background workers (Scouter polling, TTL cleanup)
- **Database:** Railway-managed PostgreSQL with pgvector extension
- **Environment:** Production env vars (API keys, database URL, OAuth secrets)
- **Build:** Docker or Nixpacks build configuration for both Python and Node.js services
- **Networking:** Internal service communication, public domain routing

**Motivation:** Move from local-only development to hosted deployment for real-world use.

**Existing overlap:**
- **Docker Compose** (`docker-compose.yml`) already defines the PostgreSQL + pgvector service for local dev. Railway config mirrors this but uses Railway-managed Postgres.
- **Backend is deployable** — FastAPI app with uvicorn, Alembic migrations, structured settings via env vars. No filesystem dependencies (BYTEA storage).
- **Frontend is deployable** — standard Next.js 14 App Router app with `npm run build && npm start`.
- **Pre-deployment security task** §13.5a (disable ZAP public issue writing) should be completed before Railway goes live.

**Open questions:**
- Railway pricing tier — which plan supports the required services?
- Single `railway.toml` with multiple services, or monorepo with service directories?
- Redis needed for session storage / caching, or PostgreSQL-only?
- Custom domain setup?
- CI/CD — deploy on push to main, or manual promote?

---

### 7. Socket.dev Supply Chain Protection

**Category:** Security / Dependencies
**Added:** 2026-02-18

Add Socket.dev GitHub App for npm supply chain attack detection. Dependabot and npm audit catch *known* CVEs in published packages, but Socket.dev catches a different threat class: malicious packages, typosquatting, compromised maintainer accounts, hidden install scripts, and unexpected network/filesystem access.

**Motivation:** As Zentropy Scout moves to SaaS with public users, the threat surface expands beyond known CVEs to active supply chain attacks. Socket.dev is free for open-source repos and provides PR-level alerts when a dependency introduces suspicious behavior.

**Key areas:**
- Install Socket.dev GitHub App (no config files needed — it reads package.json/package-lock.json)
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

<!-- Add new ideas above this line -->
