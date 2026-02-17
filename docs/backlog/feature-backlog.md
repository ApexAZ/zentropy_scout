# Zentropy Scout — Feature Backlog

**Created:** 2026-02-16
**Last Updated:** 2026-02-16

**Items:** 6

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

**Note:** The deduplication/normalization service (ensuring "Senior Dev at Meta" and "Sr. React Engineer at Facebook" don't show as separate entries) is partially addressed by the Scouter agent's cross-source matching (REQ-003 §8-9, REQ-007 §6.4). May need enhancement for multi-source fetch.

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

**Open questions:**
- Railway pricing tier — which plan supports the required services?
- Single `railway.toml` with multiple services, or monorepo with service directories?
- Redis needed for session storage / caching, or PostgreSQL-only?
- Custom domain setup?
- CI/CD — deploy on push to main, or manual promote?

---

<!-- Add new ideas above this line -->
