# Zentropy Scout — Feature Backlog

**Created:** 2026-02-16
**Last Updated:** 2026-02-27

**Items:** 11 (6 completed, 5 pending)

---

## How to Use This Document

**Purpose:** Capture feature ideas, enhancements, and future work that aren't part of the current implementation plan. Ideas here are unscoped and unprioritized until promoted to a plan or GitHub Issue.

**Format:** Each entry has a short title, description, and rough category. Add context links (REQ sections, related files, external docs) when available.

**Lifecycle:** Idea here → scope/estimate when ready → add to implementation plan or create GitHub Issue → remove from backlog.

---

## Ideas

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

### 4. Render Deployment Configuration

**Category:** DevOps / Infrastructure
**Added:** 2026-02-16
**Updated:** 2026-02-23 (switched from Railway to Render)
**Depends on:** ~~#1 (Authentication), #2 (Multi-Tenant)~~ ✅ Dependencies satisfied

Configure `render.yaml` to deploy the Next.js frontend, FastAPI backend, and Python background workers on Render. Render is already familiar, uses fixed predictable pricing, has native background worker and cron job support, and no cold-start surprises.

**Render service breakdown (~$21/month to start):**
- **Web service** — FastAPI + uvicorn ($7/month, Starter tier)
- **PostgreSQL** — Render-managed Postgres with pgvector ($7/month)
- **Background worker** — Scouter polling, insight engine cron, TTL cleanup ($7/month)
- **Static site** — Next.js frontend (free for static; $7/month if SSR needed)

**Key areas:**
- **`render.yaml`** — infrastructure-as-code defining all services, env vars, and build commands
- **Environment:** Production env vars via Render dashboard or `render.yaml` envVarGroups
- **Build:** Python (pip + uvicorn) for backend, Node.js (`npm run build && npm start`) for frontend
- **Networking:** Render private network between services, public URLs for frontend and API
- **Database migrations:** Alembic `upgrade head` as a pre-deploy job or startup command
- **pgvector:** Confirm availability on Render managed Postgres (available on Starter+)

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

<!-- Add new ideas above this line -->
