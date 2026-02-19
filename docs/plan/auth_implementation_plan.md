# Zentropy Scout — Auth, Multi-Tenant & Shared Job Pool Implementation Plan

**Created:** 2026-02-18
**Last Updated:** 2026-02-18
**Status:** In Progress
**Plan file destination:** `docs/plan/auth_implementation_plan.md`

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Load only the REQ section needed via `req-reader` subagent before each task
3. Each task = one commit, sized ≤ 80k tokens (TDD + review + fixes included)
4. After each task: update status (⬜ → ✅), commit, STOP and ask user
5. After each phase: run full test suite as gate before proceeding

**Enhanced review scope (every subtask):**
- `qa-reviewer` — recommend new E2E tests needed + flag existing tests that need refactoring
- `code-reviewer` — conventions + refactoring opportunities + obsolete/orphaned code + code duplication + gap analysis
- `security-reviewer` — vulnerabilities + gap analysis + defense-in-depth recommendations

---

## Phase 1: Auth Foundation — Database & Backend (REQ-013)

**Status:** 🟡 In Progress

*Auth database schema, UserRepository, JWT validation, password endpoints, CORS. Must complete before any other phase. Depends on: REQ-005 (users table), REQ-006 (auth pattern §6.2).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-013 §6–§7 for current task |
| 🧪 **TDD** | Write backend tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🗃️ **Database** | Use `zentropy-db` for migrations, alembic patterns |
| 🔒 **Security** | Use `zentropy-api` for endpoint patterns; bcrypt, HIBP, constant-time comparison |
| ✅ **Verify** | `pytest -v`, `ruff check .`, `bandit` |
| 🔍 **Review** | `code-reviewer` (refactoring, orphaned code, duplication) + `security-reviewer` (OWASP auth bypass, timing attacks, user enumeration) + `qa-reviewer` (E2E needs) |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Research spike: `@auth/pg-adapter`** — verify compatibility with (a) UUID primary keys, (b) snake_case column names, (c) custom columns like `token_invalidated_before` (REQ-013 §8.1). Also verify Auth.js v5 (`next-auth@5.x`) compatibility with Next.js 16+ and React 19+. **Output: decision document** — either "use @auth/pg-adapter as-is" or "implement custom adapter." Go/no-go gate for Phase 2. No code changes. | `plan` | ✅ |
| 2 | **Database migration 010: auth tables** — add `name`, `email_verified`, `image`, `updated_at`, `password_hash`, `token_invalidated_before` to `users` table. Create `accounts`, `sessions`, `verification_tokens` tables per REQ-013 §6. Existing default user gets `email_verified = now()`. All new columns nullable for existing rows. TDD: test upgrade + downgrade, all constraints, indexes. | `db, tdd, security, commands, plan` | ⬜ |
| 3 | **Backend configuration** — add auth settings to `config.py`: `auth_secret`, `auth_issuer`, `auth_cookie_name` (default `authjs.session-token`), `auth_cookie_secure`, `auth_cookie_samesite`. Audit existing `auth_enabled` setting (already exists but unused). Update `.env.example` with all new env vars per REQ-013 §11. Preserve `DEFAULT_USER_ID` as dev-mode fallback. TDD: test settings loading + validation + defaults. | `api, tdd, plan` | ⬜ |
| 4 | **UserRepository** — create `backend/app/repositories/user_repository.py` with `get_by_id()`, `get_by_email()`, `create()`, `update()` methods. Follow the repository pattern planned in REQ-005. This is the first repository class — establish the pattern for all future repositories. TDD: test all CRUD operations, email uniqueness, not-found cases. | `db, api, tdd, plan` | ⬜ |
| 5 | **JWT validation** — replace `get_current_user_id()` in `deps.py`: read JWT from `authjs.session-token` cookie, decode with `AUTH_SECRET` (HS256), verify `exp`/`aud`/`iss` claims, extract `sub` as UUID, validate against `users.token_invalidated_before` (one DB query per request). When `AUTH_ENABLED=false`, fall back to `DEFAULT_USER_ID`. **BREAKING CHANGE to test infrastructure**: update `conftest.py` `client` fixture to inject a valid JWT cookie instead of `settings.default_user_id`. Fix all broken tests. TDD: test valid JWT, expired JWT, missing cookie, revoked token, auth-disabled fallback. | `api, tdd, security, plan` | ⬜ |
| 6 | **Password endpoints** — three new endpoints per REQ-013 §7.5: (a) `POST /auth/verify-password` — unauthenticated, constant-time comparison via bcrypt dummy hash (prevents user enumeration), rate limit 5/15min per email. (b) `POST /auth/register` — unauthenticated, bcrypt cost 12, HIBP breach check (k-anonymity), email uniqueness (409 on dup), rate limit 3/hour per IP. (c) `POST /auth/change-password` — authenticated, verify current password if set, `validate_password_strength()` (8-128 chars, letter+number+special), invalidate all sessions via `token_invalidated_before = now()`, rate limit 5/hour per user. TDD: test all success/failure paths, rate limiting, HIBP integration, enumeration defense. | `api, tdd, security, plan` | ⬜ |
| 7 | **CORS + rate limiting transition** — CORS: add `ALLOWED_ORIGINS` configuration, never `*` with `allow_credentials=True` (REQ-013 §7.6). Rate limiting: change `_rate_limit_key_func` in `rate_limiting.py` from `get_remote_address(request)` to `user:{sub}` for authenticated requests, `unauth:{ip}` for unauthenticated (REQ-013 §7.4). TDD: test CORS headers, rate limit key selection for both auth modes. | `api, tdd, security, plan` | ⬜ |
| 8 | **Phase 1 gate** — run full backend test suite: `pytest -v`, `ruff check .`, `bandit -r backend/app/`. All tests must pass, 0 skips. | `plan, commands` | ⬜ |

---

## Phase 2: Auth Frontend (REQ-013)

**Status:** ⬜ Incomplete

*Login/register pages, protected routes, account settings, logout. Depends on: Phase 1 (JWT validation + password endpoints operational). NOTE: Auth approach (Auth.js v5 vs custom) determined by Phase 1 §1 decision — see `docs/plan/decisions/001_auth_adapter_decision.md`.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-013 §8 for current task |
| 🧪 **TDD** | Write Vitest component tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Follow existing Next.js patterns in `frontend/src/`, read sibling test files first |
| 🔒 **Security** | CSRF protection, cookie security, credential handling, XSS prevention |
| ✅ **Verify** | `npm test`, `npm run lint`, `npm run typecheck` |
| 🔍 **Review** | `code-reviewer` (conventions, duplication, orphaned code) + `security-reviewer` (XSS, CSRF, credential exposure, open redirect) + `qa-reviewer` (E2E needs) |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Auth.js v5 setup** — install `next-auth@beta`, `@auth/pg-adapter` (or custom adapter per §1 decision). Create route handler at `app/api/auth/[...nextauth]/route.ts`. Configure 4 providers: Google OAuth (PKCE), LinkedIn OAuth (OIDC), Credentials (delegates to FastAPI `/auth/verify-password`), Email/Resend (magic link, 10min TTL). JWT strategy with 7-day maxAge. JWT callback adds `aud: "zentropy-scout"` and `iss` claims. Custom signIn page at `/login`. `allowDangerousEmailAccountLinking: false` (REQ-013 §8.1, §5). TDD: test JWT callback adds claims, test provider config shape, test adapter integration. | `tdd, security, plan` | ⬜ |
| 2 | **Login page** — create `/login` route, full-screen layout (no app shell). Google + LinkedIn OAuth buttons at top. Email/password form with submit. "Forgot password?" link triggers magic link flow (state transitions to "magic-link-sent" confirmation). Error display for invalid credentials. Post-auth redirect: `onboarding_complete=true` → `/`, else → `/onboarding` (REQ-013 §8.2). TDD: test form validation, OAuth button rendering, state transitions (idle/submitting/magic-link-sent/error), redirect logic. | `tdd, plan` | ⬜ |
| 3 | **Register page** — create `/register` route, same full-screen layout. OAuth buttons + email/password/confirm form. Real-time password strength indicator with requirements checklist (8+ chars, letter, number, special character). Post-registration → API call to `POST /auth/register` → "check your email" confirmation page → redirect to `/onboarding` after verification (REQ-013 §8.3). TDD: test form validation, password strength display, confirmation match, error handling (409 duplicate email). | `tdd, security, plan` | ⬜ |
| 4 | **Middleware + auth context** — create `frontend/src/middleware.ts` with `auth as middleware` export. Matcher protects all routes except `/login`, `/register`, `/api/auth/*`, `/_next/*`, `favicon.ico`, `robots.txt`. Unauthenticated → 302 to `/login`. Wrap app in `SessionProvider` (outermost in provider stack: Auth > Query > SSE > Chat) by updating `app/layout.tsx`. Standard `useSession()` hook from next-auth available throughout app (REQ-013 §8.4–§8.6). TDD: test middleware redirects unauthenticated, passes authenticated, SessionProvider renders children. | `tdd, security, plan` | ⬜ |
| 5 | **API client + test infrastructure** — update `api-client.ts`: add `credentials: 'include'` to all fetch calls (cookie sent automatically for same-origin; needed for cross-origin). Add 401 interceptor: on `ApiError` with status 401, redirect to `/login` and clear TanStack Query cache. **Update frontend test infrastructure**: mock `useSession()` in test setup so existing component tests pass with auth layer active. No `Authorization` header needed — JWT-in-cookie is automatic (REQ-013 §8.8). TDD: test 401 redirect, test credentials mode, verify existing tests still pass with session mock. | `tdd, security, plan` | ⬜ |
| 6 | **Account settings** — add new section to existing `/settings` page: email display + verified status badge, name edit field, password change form (current + new + confirm, or "Set password" button for OAuth-only users who have no `password_hash`), connected providers list with link/unlink buttons, "Sign out" button, "Sign out all devices" button (calls backend to set `token_invalidated_before = now()`) (REQ-013 §8.3a). TDD: test password change form, provider list rendering, sign-out-all confirmation dialog. | `tdd, security, plan` | ⬜ |
| 7 | **Logout flow** — `signOut()` from next-auth → clears session cookie → deletes `sessions` table row → clear TanStack Query cache → redirect to `/login`. "Sign out all devices" sets `token_invalidated_before = now()` server-side, then calls `signOut()` locally (REQ-013 §8.9). TDD: test cache clearing, redirect, session deletion. | `tdd, plan` | ⬜ |
| 8 | **E2E auth tests** — Playwright tests for full auth flows: login with email/password, register new account (mock email verification), forgot password (mock magic link), OAuth redirect (mock provider), protected route redirect to `/login`, logout + cache cleared, session persistence across page reload, 401 API response triggers redirect. Mock all auth/email endpoints. ~10 tests. | `playwright, e2e, tdd, plan` | ⬜ |
| 9 | **Phase 2 gate** — run full test suite: `pytest tests/ -v` (backend), `npm test` (Vitest), `npx playwright test` (E2E), `npm run lint`, `npm run typecheck`. All green. | `plan, commands` | ⬜ |

---

## Phase 3: Multi-Tenant Data Isolation (REQ-014)

**Status:** ⬜ Incomplete

*Ownership verification on all endpoints, cross-tenant test coverage, TenantScopedSession for agents. Depends on: Phase 2 (authenticated user_id available end-to-end). Does NOT modify job_postings ownership yet — that's Phase 4.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-014 §4–§7 for current task |
| 🧪 **TDD** | Write cross-tenant tests first — follow `zentropy-tdd` |
| 🗃️ **Database** | Use `zentropy-db` for index migrations |
| 🔒 **Security** | Ownership patterns from REQ-014 §5 — return 404 not 403 (prevents enumeration) |
| ✅ **Verify** | `pytest -v`, `ruff check .`, `bandit` |
| 🔍 **Review** | `code-reviewer` (orphaned stub code being replaced, duplication across routers) + `security-reviewer` (tenant bypass, 403-vs-404, IDOR) + `qa-reviewer` (E2E needs) |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Database indexes migration 011** — add `idx_personas_user_id`, `idx_job_postings_persona_id`, `idx_cover_letters_persona_id`, `idx_applications_persona_id`, `idx_base_resumes_persona_id`, `idx_work_histories_persona_id`, `idx_skills_persona_id`. Use `IF NOT EXISTS` — some may already exist (REQ-014 §8). TDD: test upgrade + downgrade. | `db, tdd, commands, plan` | ⬜ |
| 2 | **Ownership verification — core endpoints** — implement `personas` GET/{id}, PATCH/{id}, DELETE/{id} with Pattern A (`WHERE persona.user_id = :uid`, return 404 for wrong user). Audit `base_resumes` existing ownership checks against `_get_owned_resume()` reference pattern. List endpoints must scope to authenticated user. Remove SECURITY TODO stubs (REQ-014 §5, §6). TDD: test own-resource access succeeds, cross-tenant returns 404, list returns only owned. | `api, tdd, security, plan` | ⬜ |
| 3 | **Ownership verification — secondary endpoints** — implement ownership for: `applications` (Pattern B: JOIN through persona, includes bulk operations + timeline sub-resource), `cover_letters` (Pattern B: JOIN through persona), `user_source_preferences` (Pattern A: direct persona ownership check), `job_variants` (Pattern C: deep join BaseResume → Persona), `persona_change_flags` (verify pattern). Replace all remaining stubs with real DB queries. Return 404 for cross-tenant (REQ-014 §5, §6). TDD: test each router for own-resource + cross-tenant 404. | `api, tdd, security, plan` | ⬜ |
| 4 | **TenantScopedSession + agent scoping** — create `TenantScopedSession` wrapper class that adds `WHERE persona.user_id = :uid` to queries. Audit ALL agent code in `backend/app/agents/` for raw `AsyncSession` usage — replace with `TenantScopedSession`. Explicitly verify `scouter_graph.py` sources `user_id` from JWT-validated dependency, not from `settings.default_user_id`. Audit `chat.py`, `refresh.py`, `files.py` (REQ-014 §7). TDD: test wrapper scoping, agent session usage, flag raw session imports. | `agents, tdd, security, plan` | ⬜ |
| 5 | **Cross-tenant leakage tests** — create `user_a`/`user_b` test fixtures and `client_user_a`/`client_user_b` HTTP clients (override `get_current_user_id` via JWT). Test EVERY router for: GET detail returns 404 for wrong user, GET list returns only own data, PATCH/DELETE returns 404 for wrong user, POST rejects wrong persona_id. Coverage target: every router in REQ-014 §6.1 (REQ-014 §10). | `tdd, security, plan` | ⬜ |
| 6 | **E2E multi-tenant tests** — Playwright tests verifying frontend correctly handles 404 responses for cross-tenant resources. Verify navigation shows only owned data. Test that accessing another user's resource URL shows error state, not data. ~5 tests. | `playwright, e2e, tdd, plan` | ⬜ |
| 7 | **Phase 3 gate** — run full test suite: `pytest tests/ -v`, `npm test`, `npx playwright test`, `ruff check .`, `bandit`. All green. | `plan, commands` | ⬜ |

---

## Phase 4: Shared Job Pool — Schema Migration (REQ-015)

**Status:** ⬜ Incomplete

*Transform job_postings from per-user to shared pool. Create persona_jobs link table. Complex data migration with cross-persona dedup. Depends on: Phase 3 (ownership patterns established). WARNING: Migration 014 (drop columns) is destructive and not trivially reversible — test downgrade paths thoroughly.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-015 §4, §11 for current task |
| 🧪 **TDD** | Test migration upgrade AND downgrade — follow `zentropy-tdd` |
| 🗃️ **Database** | Use `zentropy-db` for complex migrations, backfill patterns, FK surgery |
| ✅ **Verify** | `alembic upgrade head`, `alembic downgrade -1`, `pytest -v` |
| 🔍 **Review** | `code-reviewer` (migration correctness, model consistency) + `security-reviewer` (data integrity, FK constraint safety, cascading behavior) + `qa-reviewer` (E2E impact assessment) |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Migration 012: DDL + PersonaJob model** — create `persona_jobs` table with all per-user columns (`status`, `is_favorite`, `dismissed_at`, `fit_score`, `stretch_score`, `failed_non_negotiables`, `score_details`, `discovery_method`, `discovered_at`, `scored_at`), UNIQUE(persona_id, job_posting_id), ON DELETE RESTRICT for job_posting_id. Add `is_active BOOLEAN DEFAULT true` to `job_postings`. Add UNIQUE on `job_postings(source_id, external_id)` WHERE both NOT NULL. Create `PersonaJob` SQLAlchemy model with relationships. Add `is_active` field to `JobPosting` model (REQ-015 §4, §11 steps 1–3). TDD: test upgrade + downgrade, all constraints, model relationships. | `db, tdd, commands, plan` | ⬜ |
| 2 | **Migration 013: backfill persona_jobs** — populate `persona_jobs` from existing `job_postings` data: `INSERT INTO persona_jobs SELECT` mapping old columns. Set `is_active = false` for `status='Expired'` job postings, `true` for all others. Verify row counts match. This is a data-only migration — no DDL (REQ-015 §11 steps 4–5). TDD: test backfill correctness, row count integrity, is_active values. | `db, tdd, commands, plan` | ⬜ |
| 3 | **Cross-persona dedup script** — standalone Python script (not Alembic migration) to deduplicate job_postings across personas: group by `description_hash`, verify `company_name` matches (hash collision guard), pick oldest as canonical, reassign ALL child FKs (`applications`, `cover_letters`, `job_variants`, `extracted_skills`, `job_embeddings`), merge `also_found_on` JSONB arrays, create additional `persona_jobs` links for merged records, delete duplicate rows. Run after migration 013, verify before proceeding to migration 014 (REQ-015 §11 step 6). TDD: test dedup merging, FK reassignment, hash collision guard, persona_jobs link creation. | `db, tdd, commands, plan` | ⬜ |
| 4 | **Migration 014: drop per-user columns + FK updates** — add `persona_job_id` FK to `applications` (backfill from persona_id + job_posting_id lookup through persona_jobs). Update `applications` UNIQUE constraint from `(persona_id, job_posting_id)` to `(persona_id, persona_job_id)`. Drop per-user columns from `job_postings`: `persona_id`, `status`, `is_favorite`, `fit_score`, `stretch_score`, `failed_non_negotiables`, `dismissed_at`, `score_details`. Drop old indexes (`idx_jobposting_persona`, `idx_jobposting_status`, `idx_jobposting_fitscore`), create new (`idx_jobposting_active`, `idx_jobposting_title_company`, `idx_jobposting_first_seen`). Update `JobPosting` model (remove per-user fields), update `Application` model (add `persona_job_id` FK). Update entity ownership graph: job_postings → Tier 0, persona_jobs → Tier 2 (REQ-015 §4, §5, §11 steps 7–10). TDD: test downgrade restores columns + constraints, test model relationships. | `db, tdd, commands, plan` | ⬜ |
| 5 | **Phase 4 gate: test suite repair** — run full backend test suite. **Many existing tests will break** due to schema changes (any test inserting `JobPosting` with `persona_id`, `status`, `fit_score` etc.). Fix ALL broken tests to use new schema (create via persona_jobs). Ensure all migrations pass upgrade AND downgrade. `pytest tests/ -v`, `ruff check .`. | `tdd, plan, commands` | ⬜ |

---

## Phase 5: Shared Job Pool — Backend Logic (REQ-015)

**Status:** ⬜ Incomplete

*Repository refactor, API endpoint updates, global dedup, surfacing worker, Scouter changes, content security. Depends on: Phase 4 (schema in place, models updated).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-015 §6–§10 for current task |
| 🧪 **TDD** | Write tests first for every service/endpoint — follow `zentropy-tdd` |
| 🔒 **Security** | Pool poisoning defense, quarantine, sanitization, cross-tenant in surfacing |
| 🤖 **Agents** | Use `zentropy-agents` for Scouter graph changes |
| ✅ **Verify** | `pytest -v`, `ruff check .`, `bandit` |
| 🔍 **Review** | `code-reviewer` (orphaned code from old job_postings patterns, duplication across services) + `security-reviewer` (injection via shared pool, cross-tenant in surfacing worker, timing side-channels) + `qa-reviewer` (E2E needs) |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Repositories + response models** — create `JobPostingRepository` (shared pool: global CRUD, dedup lookup by source_id/external_id and description_hash) and `PersonaJobRepository` (per-user: JOIN persona_jobs ↔ job_postings, scoped to persona.user_id). Create response models: `JobPostingResponse` (factual data only, excludes `also_found_on` per privacy rules), `PersonaJobResponse` (nested: shared data + per-user status/scores/favorite) (REQ-015 §8, §9). TDD: test all query patterns, user scoping, response model shapes. | `db, api, tdd, plan` | ⬜ |
| 2 | **API endpoint updates** — rewrite all job-posting endpoints: `GET /job-postings` returns persona_jobs + nested job data, `GET /job-postings/{id}` lookup via persona_jobs (404 if no link), `POST /job-postings` creates in shared pool + creates persona_jobs link, `PATCH /job-postings/{id}` updates persona_jobs only (shared data immutable), `POST /job-postings/ingest/confirm` creates in shared pool + persona_jobs link (**critical: this is the only fully-implemented job creation endpoint — update it explicitly**), `POST /job-postings/bulk-dismiss` + `bulk-favorite` update persona_jobs, new `POST /job-postings/rescore` triggers re-scoring (REQ-015 §9). TDD: test all CRUD, 404 for no-link, immutability of shared fields, ingest-confirm creates persona_jobs. | `api, tdd, security, plan` | ⬜ |
| 3 | **Global deduplication service** — update dedup to work globally (not per-persona). 4-step dedup: (1) source_id + external_id match → UPDATE existing, (2) description_hash match → ADD to also_found_on, (3) company + title + description similarity → LINK as repost, (4) no match → CREATE new in shared pool. After dedup: create persona_jobs link for discovering user. Race condition handling: `ON CONFLICT DO NOTHING` on UNIQUE constraint, losing Scouter looks up existing record and creates its own persona_jobs link (REQ-015 §6). TDD: test each dedup step, race condition recovery, link creation after dedup. | `api, tdd, plan` | ⬜ |
| 4 | **Pool surfacing worker** — asyncio background task via FastAPI `lifespan` event (NOT Celery/ARQ — no Redis/queue infrastructure exists). Every ~15 min: query new pool jobs since last run, score against active personas that haven't seen them. Match criteria: (a) keyword overlap with persona skills, (b) embedding cosine similarity above threshold, (c) seniority/work model alignment. Threshold: `fit_score >= persona.minimum_fit_threshold` (default 50). Rate limit: max 50 jobs per pass, max 100 personas per new job. Creates persona_jobs with `discovery_method='pool'`. UNIQUE constraint prevents re-surfacing. Use lightweight keyword pre-screen before full LLM scoring (REQ-015 §7). TDD: test matching logic, threshold filtering, rate limiting, UNIQUE dedup, worker lifecycle (start/stop). | `provider, tdd, security, plan` | ⬜ |
| 5 | **Scouter agent changes** — replace `deduplicate_jobs` node → `check_shared_pool` (global dedup). Replace `save_jobs` node → `save_to_pool` (shared pool + persona_jobs link). Add `notify_surfacing_worker` node (triggers background task for cross-user matching). Update state schema. Race condition: UNIQUE constraint on `(source_id, external_id)` + `ON CONFLICT` → losing Scouter creates its own persona_jobs link. Node mapping: deduplicate_jobs → check_shared_pool, save_jobs → save_to_pool (REQ-015 §10). TDD: test updated graph flow, pool save, surfacing notification, race condition recovery. | `agents, tdd, plan` | ⬜ |
| 6 | **Content security** — pool poisoning defenses per REQ-015 §8.4: (a) Validate on write: reject descriptions containing detected injection patterns in ingest endpoint. (b) Quarantine manual submissions: `discovery_method='manual'` jobs visible only to submitter until independently confirmed OR 7-day auto-release (no rejection signal) OR admin approval; extend quarantine indefinitely if reported. (c) Rate limit manual submissions: max 20/user/day. (d) Timing side-channel: return "processing" immediately for ingest (consistent response time regardless of dedup hit/miss). (e) Sanitize on read: all pool content passes `sanitize_llm_input()` before any LLM prompt. TDD: test injection rejection, quarantine logic, auto-release timer, rate limit, consistent response timing. | `api, tdd, security, plan` | ⬜ |
| 7 | **Phase 5 gate** — run full backend test suite: `pytest tests/ -v`, `ruff check .`, `bandit`. Verify all services, agents, endpoints, and surfacing worker pass. | `plan, commands` | ⬜ |

---

## Phase 6: Shared Job Pool — Frontend & Final Integration (REQ-015)

**Status:** ⬜ Incomplete

*Update frontend components for new persona_jobs response shape. E2E tests for full shared pool workflow. Final integration gate. Depends on: Phase 5 (all backend APIs operational with new schema).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-015 §8 and REQ-012 §8 for current task |
| 🧪 **TDD** | Write Vitest + Playwright tests — follow `zentropy-tdd` |
| ✅ **Verify** | `npm test`, `npm run lint`, `npm run typecheck`, `npx playwright test` |
| 🔍 **Review** | `code-reviewer` (orphaned types/hooks from old job_postings response shape, duplication) + `security-reviewer` (shared data exposure in UI, cross-user info leakage) + `qa-reviewer` (full E2E coverage audit) |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Job dashboard update** — update TypeScript types: `PersonaJobResponse` (nested shared + per-user fields). Update `useJobPostings` and related hooks for new API contract. Update job list component: status/favorite from `persona_jobs`, factual data from nested `job_posting`. Update job cards: display `discovery_method` identically (scouter/manual/pool shown the same per REQ-015 §8 privacy rules — users cannot tell if job came from pool). Remove any references to old `job_postings.status`, `job_postings.fit_score` etc. TDD: test type compatibility, component rendering with new shape, hook data transformation. | `tdd, plan` | ⬜ |
| 2 | **Job detail view + rescore** — update detail view for nested `PersonaJobResponse`. Add rescore button wired to `POST /job-postings/rescore`. Update dismiss/favorite actions to PATCH persona_jobs fields. Ensure shared data fields (title, company, description, salary) are read-only in UI — no edit controls. TDD: test detail rendering with nested data, rescore trigger + loading state, dismiss/favorite mutations, shared field immutability. | `tdd, plan` | ⬜ |
| 3 | **E2E shared pool tests** — Playwright tests: job list displays persona_jobs data correctly, job detail shows nested shared data, dismiss updates persona_jobs status, favorite toggle works, rescore triggers and shows updated scores. Mock surfacing worker results (jobs with `discovery_method='pool'` appear identically to scouter-discovered). Verify shared data not editable. ~8 tests. | `playwright, e2e, tdd, plan` | ⬜ |
| 4 | **Final integration gate** — run EVERYTHING: `pytest tests/ -v` (backend), `npm test` (Vitest), `npx playwright test` (E2E), `npm run lint`, `npm run typecheck`, `ruff check .`, `bandit`. ALL green = auth/multi-tenant/shared-job-pool phase COMPLETE. | `plan, commands` | ⬜ |

---

## Status Legend

| Icon | Meaning |
|------|---------|
| ⬜ | Incomplete |
| 🟡 | In Progress |
| ✅ | Complete |

---

## Dependency Chain

```
Phase 1: Auth Backend (REQ-013)
    │   DB migration, JWT validation, password endpoints
    ↓
Phase 2: Auth Frontend (REQ-013)
    │   Login/register pages, middleware
    ↓
Phase 3: Multi-Tenant Isolation (REQ-014)
    │   Ownership verification, cross-tenant tests
    ↓
Phase 4: Shared Job Pool Schema (REQ-015)
    │   persona_jobs table, backfill, dedup, column drops
    ↓
Phase 5: Shared Job Pool Backend (REQ-015)
    │   Repositories, API endpoints, surfacing worker, Scouter
    ↓
Phase 6: Shared Job Pool Frontend + Integration (REQ-015)
        Frontend updates, E2E tests, final gate
```

---

## Decisions

| # | Decision | Date | Document |
|---|----------|------|----------|
| 001 | Auth adapter strategy: Custom FastAPI-owned auth (not Auth.js v5, not Better Auth) | 2026-02-18 | `docs/plan/decisions/001_auth_adapter_decision.md` |

---

## Implementation Notes

1. **AUTH_ENABLED feature flag**: when `false`, all code paths fall back to `DEFAULT_USER_ID`. No endpoint signatures change. This bridges local dev and hosted mode.

2. **404 not 403**: cross-tenant access returns 404 to prevent resource enumeration. Never reveal that a resource exists but belongs to someone else.

3. **JWT-in-cookie, not Authorization header**: `EventSource` (SSE) cannot send custom headers. Cookies are the only automatic credential mechanism. Frontend `api-client.ts` needs `credentials: 'include'` but no `Authorization` header.

4. **Phase 4 migrations are destructive**: dropping columns from `job_postings` is not trivially reversible. Test downgrade paths thoroughly. Consider blue-green deployment for production.

5. **Surfacing worker is NOT part of Scouter**: the pool surfacing worker runs as a system-level asyncio background task. A user's Scouter reading other users' persona data would be a cross-tenant violation.

6. **Existing tests will break in Phase 4**: schema changes break test fixtures referencing `job_postings.persona_id`, `status`, `fit_score`, etc. Budget time in §4.5 for comprehensive test repair.

7. **UserRepository is the first repository**: Phase 1 §4 establishes the repository pattern. All future repositories follow its conventions.

8. **ingest_confirm endpoint**: `job_postings.py:confirm_ingest_job_posting()` is the only fully-implemented job creation endpoint (others are stubs). Phase 5 §2 must explicitly update it to create persona_jobs links.

9. **Application UNIQUE constraint**: Phase 4 §4 must change `applications(persona_id, job_posting_id)` to `applications(persona_id, persona_job_id)` since multiple personas can now apply to the same shared job.

10. **Plan file**: save this plan as `docs/plan/auth_implementation_plan.md` on first commit.

---

## Task Count Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| Phase 1 | 8 | Auth backend — DB, config, JWT, passwords, CORS |
| Phase 2 | 9 | Auth frontend — pages, middleware, settings |
| Phase 3 | 7 | Multi-tenant — ownership, cross-tenant tests |
| Phase 4 | 5 | Shared pool schema — migrations, backfill, dedup |
| Phase 5 | 7 | Shared pool backend — APIs, dedup, surfacing, Scouter |
| Phase 6 | 4 | Shared pool frontend + final integration |
| **Total** | **40** | |

---

## Critical Files

| File | Impact |
|------|--------|
| `backend/app/api/deps.py` | Phase 1 §5: `get_current_user_id()` switches from env var to JWT — cascades to every test fixture |
| `backend/tests/conftest.py` | Phase 1 §5: client fixture switches from `settings.default_user_id` to JWT cookie injection |
| `backend/app/models/job_posting.py` | Phase 4 §1+§4: `persona_id` FK removed, `is_active` added, per-user fields dropped |
| `backend/app/models/application.py` | Phase 4 §4: `persona_job_id` FK added, UNIQUE constraint updated |
| `backend/app/api/v1/job_postings.py` | Phase 5 §2: all endpoints rewritten for persona_jobs + shared pool |
| `backend/app/agents/scouter_graph.py` | Phase 5 §5: dedup/save nodes replaced for shared pool |
| `backend/app/services/job_deduplication.py` | Phase 5 §3: converted from per-persona to global dedup |
| `frontend/src/lib/api-client.ts` | Phase 2 §5: `credentials: 'include'` + 401 redirect |
| `frontend/src/middleware.ts` | Phase 2 §4: NEW — protects all routes, redirects to /login |
| `frontend/src/app/layout.tsx` | Phase 2 §4: wraps app in SessionProvider (outermost) |
