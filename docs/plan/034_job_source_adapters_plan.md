# Zentropy Scout — REQ-034 Job Source Adapter Implementation Plan

**Created:** 2026-04-03
**Last Updated:** 2026-04-03
**Status:** Not Started
**Branch:** main
**REQ:** REQ-034 (v0.1)

---

## Context

The Scouter pipeline (`JobFetchService`, source adapters, `PoolSurfacingWorker`) is fully
scaffolded but has four functional gaps:

1. All four `fetch_jobs()` adapters return `[]` (stubs)
2. `SearchParams` is hardcoded to `keywords=["software", "engineer"]` for every poll
3. No poll scheduler — polls only fire on manual request; `next_poll_at` is calculated but never read
4. `extract_skills_and_culture()` returns an empty placeholder

This plan closes all four gaps and adds the `SearchProfile` entity (AI-generated, user-reviewed
search criteria split into fit/stretch buckets), the `PollSchedulerWorker` background task,
skill extraction wiring, and frontend UI for the full job search configuration workflow.

**Phase gate sequence:** Each phase (except Phase 6) ends with a push to remote (pre-push
hooks: pytest + vitest). No code ships until all quality gates pass.

---

## How to Use This Document

1. Find the first `🟡` or `⬜` task — that's where to start
2. Load relevant REQ-034 sections via `req-reader` before each phase (section listed in Workflow table)
3. Each task = one unit of work = one commit (no push until phase gate)
4. Follow the zentropy-planner subtask workflow: TDD → review → resolve → verify → commit → STOP
5. Phase-end gate: full test suite (pytest + vitest + Playwright) → push → STOP

---

## Dependency Chain

```
Phase 1: Foundation (DB migrations, SearchParams, env vars, TaskType)
    ↓
Phase 2: SearchProfile Backend (model, repository, service, API endpoints)
    ↓
Phase 3: Adapters, Pipeline & Skill Extraction (fetch_jobs(), SearchParams construction,
         search_bucket flow, skill extraction wiring)
    ↓
Phase 4: Poll Scheduler (PollSchedulerWorker)
    ↓
Phase 5: Frontend (types, onboarding step, settings section, job card treatment)
    ↓
Phase 6: API Key Setup (guided registration, wire keys, smoke test)
```

---

## Phase 1: Foundation

**Status:** ✅ Complete

*DB schema changes, SearchParams extensions, env vars, and TaskType seed data that all later
phases depend on.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-034 §5.1, §10, §11 |
| 🧪 **TDD** | Write migration tests (upgrade + downgrade), model field unit tests |
| 🗃️ **Patterns** | Use `zentropy-db` for migrations |
| ✅ **Verify** | `pytest -v`, `ruff check .`, `pyright` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). Verdicts: CLEAR → proceed. VULNERABLE → fix immediately. FALSE POSITIVE → full PROSECUTION PROTOCOL. NEEDS INVESTIGATION → escalate via AskUserQuestion. | `plan, security` | ✅ |
| 2 | **DB migration: `search_profiles` table** — New Alembic migration creating `search_profiles` per REQ-034 §4.2. Fields: `id` (UUID PK), `persona_id` (UUID FK → personas, UNIQUE, CASCADE), `fit_searches` (JSONB), `stretch_searches` (JSONB), `persona_fingerprint` (String 64), `is_stale` (bool, default true), `generated_at` (DateTime nullable), `approved_at` (DateTime nullable), `created_at`, `updated_at`. Include downgrade. Test upgrade + downgrade. | `db, commands, tdd, docs, plan` | ✅ |
| 3 | **DB migration: `search_bucket` + `last_seen_external_ids`** — Two-column Alembic migration. (a) `persona_jobs`: add `search_bucket VARCHAR(20) NULL CHECK (search_bucket IN ('fit','stretch','manual','pool'))`. (b) `polling_configurations`: add `last_seen_external_ids JSONB NOT NULL DEFAULT '{}'::jsonb`. Include downgrade. Test upgrade + downgrade. | `db, commands, tdd, docs, plan` | ✅ |
| 4 | **Extend `SearchParams` dataclass** — In `backend/app/adapters/sources/base.py`: add `max_days_old: int | None = None`, `posted_after: datetime | None = None`, `remoteok_tags: list[str] | None = None` fields per REQ-034 §5.1. All new fields have defaults — existing callers unchanged. Update existing tests. | `tdd, docs, plan` | ✅ |
| 5 | **Add API key env vars to `config.py` + `.env.example`** — Add `adzuna_app_id: str | None = None`, `adzuna_app_key: str | None = None`, `the_muse_api_key: str | None = None`, `usajobs_user_agent: str | None = None`, `usajobs_email: str | None = None` to `Settings` in `backend/app/core/config.py` per REQ-034 §10. Update `.env.example` with commented-out entries and registration URLs as inline comments. | `docs, plan` | ✅ |
| 6 | **Add `SEARCH_PROFILE_GENERATION` TaskType + seed migration** — Locate `TaskType` enum in the backend. Add `SEARCH_PROFILE_GENERATION` variant. Create Alembic data migration inserting a `task_routing_config` row for this task type, routing to Gemini Flash (same tier as `EXTRACTION`). Test that task routing resolves to expected model. | `db, provider, tdd, docs, plan` | ✅ |
| 7 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + vitest + Playwright + lint + typecheck). Fix regressions. Commit plan update. Push. | `plan, commands` | ✅ |

---

## Phase 2: SearchProfile Backend

**Status:** ✅ Complete

*New `SearchProfile` entity — SQLAlchemy model, repository, service (AI generation + staleness
detection), persona update hook, and API endpoints.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-034 §4 |
| 🧪 **TDD** | Tests first for repository CRUD, service logic, API endpoints |
| 🗃️ **Patterns** | `zentropy-db` (model), `zentropy-api` (endpoints), `zentropy-provider` (AI call) |
| ✅ **Verify** | `pytest -v`, `ruff check .`, `pyright` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). | `plan, security` | ✅ |
| 2 | **`SearchProfile` SQLAlchemy model + Pydantic schemas** — Create `backend/app/models/search_profile.py` with `SearchProfile(Base, TimestampMixin)` mapping REQ-034 §4.2 fields. Create `backend/app/schemas/search_profile.py` with `SearchBucketSchema` (JSONB shape validator), `SearchProfileRead`, `SearchProfileCreate`, `SearchProfileUpdate`. Include JSONB validation that `fit_searches` / `stretch_searches` items are valid `SearchBucket` objects. | `db, tdd, docs, plan` | ✅ |
| 3 | **`SearchProfileRepository` CRUD** — Create `backend/app/repositories/search_profile_repository.py`. Methods: `get_by_persona_id(db, persona_id) -> SearchProfile | None`, `create(db, data) -> SearchProfile`, `update(db, profile_id, data) -> SearchProfile`, `upsert(db, persona_id, data) -> SearchProfile`. Follow existing repository patterns. Async DB session unit tests. | `db, tdd, docs, plan` | ✅ |
| 4 | **`SearchProfileService` — fingerprint + staleness** — Create `backend/app/services/discovery/search_profile_service.py`. Implement: `compute_fingerprint(persona) -> str` (SHA-256 of FINGERPRINT_FIELDS from REQ-034 §4.4: skills, target_roles, target_skills, stretch_appetite, location_preferences, remote_preference), `check_staleness(persona, profile) -> bool`, `mark_stale(db, persona_id) -> None`. Unit tests: fingerprint stable for same input, changes on material field update, non-material fields don't change fingerprint. | `tdd, docs, plan` | ✅ |
| 5 | **`SearchProfileService` — AI generation** — Add `generate_profile(db, persona, provider) -> SearchProfile` to `SearchProfileService` per REQ-034 §4.3. Use `TaskType.SEARCH_PROFILE_GENERATION` + `MeteredLLMProvider`. Build prompt from persona snapshot (titles, skills, target_roles, target_skills, stretch_appetite, location, remote_preference). Parse JSON response into `fit_searches` + `stretch_searches` arrays of `SearchBucket` objects including `remoteok_tags`. On LLM failure: raise `ServiceError`. Unit tests: mock provider returns valid JSON → profile populated; mock provider raises → `ServiceError` propagated. | `provider, tdd, security, docs, plan` | ✅ |
| 6 | **Staleness hook on persona update** — In the service/handler that processes `PATCH /personas/{id}`, add post-update call to `SearchProfileService.check_staleness()`. If fingerprint differs → call `mark_stale()`. Integration tests: PATCH a fingerprint-relevant field → `is_stale` becomes True. PATCH a non-material field (e.g., bio) → no staleness change. | `api, tdd, docs, plan` | ✅ |
| 7 | **SearchProfile API endpoints** — New router at `backend/app/api/v1/search_profiles.py`. Three endpoints per REQ-034 §4.5: `GET /search-profiles/{persona_id}` (returns profile or 404), `POST /search-profiles/{persona_id}/generate` (triggers AI generation, returns profile), `PATCH /search-profiles/{persona_id}` (update buckets / set `approved_at`). Wire into main router. Endpoint tests for each. | `api, tdd, security, docs, plan` | ✅ |
| 8 | **Phase gate — full test suite + push** — Run test-runner in Full mode. Fix regressions. Commit plan update. Push. | `plan, commands` | ✅ |

---

## Phase 3: Adapters, Pipeline & Skill Extraction

**Status:** ✅ Complete

*Implement all four `fetch_jobs()` methods, replace hardcoded `SearchParams`, wire
`search_bucket` through the dedup pipeline, and un-stub skill extraction.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-034 §3, §5, §6, §8 |
| 🧪 **TDD** | Mock `httpx` responses; test delta calculation, pagination, error handling, `search_bucket` propagation |
| 🗃️ **Patterns** | `zentropy-provider` for skill extraction LLM call; `zentropy-db` for model changes |
| ✅ **Verify** | `pytest -v`, `ruff check .`, `pyright` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). | `plan, security` | ✅ |
| 2 | **Adzuna `fetch_jobs()` implementation** — Implement in `backend/app/adapters/sources/adzuna.py` per REQ-034 §5.3. Use `httpx.AsyncClient`. Query params: `app_id`, `app_key`, `results_per_page`, `what` (joined keywords), optional `where`, `max_days_old`, `where=remote` when `remote_only`. Paginate until 0 results or results < results_per_page. Rate-limit: `asyncio.sleep(2.4)` between pages (25 req/min cap). Call `normalize()` on each result. Raise `SourceError` on 4xx/5xx/timeout/429. Skip gracefully if credentials are None. Unit tests: mock httpx, pagination termination, delta params, 429 handling, credential-missing skip. | `tdd, security, docs, plan` | ✅ |
| 3 | **The Muse `fetch_jobs()` implementation** — Implement in `backend/app/adapters/sources/themuse.py` per REQ-034 §5.3. Zero-indexed `page` param, fixed 20 results/page. Paginate until `page >= response["page_count"]`. Client-side keyword filter: discard jobs where none of `params.keywords` appear in normalized title (case-insensitive). Add `?category=Engineering` filter when role family is known. Skip gracefully if `the_muse_api_key` is None (falls back to 500/hr unauthenticated tier). Unit tests: mock httpx, keyword filtering, page_count termination, unauthenticated fallback. | `tdd, security, docs, plan` | ✅ |
| 4 | **RemoteOK `fetch_jobs()` implementation** — Implement in `backend/app/adapters/sources/remoteok.py` per REQ-034 §5.3. Single call, no pagination. Skip index 0 (metadata object). Apply `?tag={remoteok_tags[0]}` if `params.remoteok_tags` is non-empty; else pull all. No credentials required. Unit tests: mock httpx, metadata skip, tag param, empty-tag fallback, full dataset parse. | `tdd, security, docs, plan` | ✅ |
| 5 | **USAJobs `fetch_jobs()` implementation** — Implement in `backend/app/adapters/sources/usajobs.py` per REQ-034 §5.3. Header-based auth (`Authorization: USAJOBS-DEMO-TOKEN`, `User-Agent`, `Email-Address`, `Host`). `ResultsPerPage` capped at 500. `DatePosted` delta param. Paginate up to 20 pages (10k row cap). Skip gracefully if credentials are None. Unit tests: mock httpx, auth headers, DatePosted delta, 20-page cap, credential-missing skip. | `tdd, security, docs, plan` | ✅ |
| 6 | **`build_search_params()` + replace hardcoded SearchParams** — Create `build_search_params(bucket: SearchBucket, persona: Persona, last_poll_at: datetime | None) -> SearchParams` per REQ-034 §5.2. Delta: `max(1, ceil((now - last_poll_at).total_seconds() / 86400) + 1)`; seed `max_days_old=7` on first poll. In `backend/app/services/discovery/job_fetch_service.py` (~line 221), replace hardcoded `SearchParams(keywords=["software", "engineer"])` with a loop over `SearchProfile` fit + stretch buckets. Tag each result with bucket type for downstream `search_bucket` propagation. Unit tests: delta calculation (first poll → 7, subsequent → correct days, boundary), `SearchParams` fields from bucket. | `tdd, docs, plan` | ✅ |
| 7 | **`search_bucket` flow through `deduplicate_and_save()`** — Add `search_bucket: Literal["fit","stretch","manual","pool"] | None = None` parameter to `deduplicate_and_save()` in `backend/app/services/discovery/global_dedup_service.py`. Pass through to `PersonaJob` creation. Update `backend/app/models/persona_job.py` to map the new column. Update all existing callers with `search_bucket=None` default for backward compat. Unit tests: verify `search_bucket` value propagates to created `PersonaJob`. | `db, tdd, docs, plan` | ✅ |
| 8 | **Skill extraction wiring** — In `backend/app/services/discovery/job_enrichment_service.py` `extract_skills_and_culture()` (~line 183), replace stub return with LLM call using `TaskType.EXTRACTION` per REQ-034 §8. Guard: `provider is None` → return empty extraction (test/stub mode). Parse JSON response into `required_skills`, `preferred_skills`, `culture_text`. On LLM failure: log warning + return empty extraction (non-blocking). Unit tests: mock provider returns valid JSON → fields populated; mock provider raises → empty extraction; provider=None → empty extraction. | `provider, tdd, security, docs, plan` | ✅ |
| 9 | **Phase gate — full test suite + push** — Run test-runner in Full mode. Fix regressions. Commit plan update. Push. | `plan, commands` | ✅ |

---

## Phase 4: Poll Scheduler

**Status:** ⬜ Incomplete

*New `PollSchedulerWorker` background task that reads `next_poll_at` and triggers polls on
schedule — closing the gap where `next_poll_at` is calculated but never acted upon.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-034 §7 |
| 🧪 **TDD** | Unit tests for loop logic, semaphore concurrency, missed-window catch-up; follow `pool_surfacing_worker.py` test patterns |
| 🗃️ **Patterns** | Follow `backend/app/services/discovery/pool_surfacing_worker.py` lifecycle pattern (start/stop/run_once) |
| ✅ **Verify** | `pytest -v`, `ruff check .`, `pyright` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). | `plan, security` | ✅ |
| 2 | **`PollSchedulerWorker` implementation** — Create `backend/app/services/discovery/poll_scheduler_worker.py` per REQ-034 §7.2. Lifecycle: `__init__(session_factory, *, interval_seconds=1800)`, `start()`, `stop()`, `run_once()` (mirrors `PoolSurfacingWorker`). Loop: query personas where `next_poll_at <= now AND onboarding_complete=True AND polling_frequency != 'Manual Only'`; resolve enabled sources from `UserSourcePreference`; call `JobFetchService.run_poll()` per persona; update `PollingConfiguration.last_poll_at / next_poll_at`; limit via `asyncio.Semaphore(5)`. Startup look-back: catch personas that missed their window by up to 24hrs. Unit tests: semaphore limits to 5 concurrent polls; 'Manual Only' personas skipped; 24hr catch-up window included. | `tdd, security, docs, plan` | ✅ |
| 3 | **Register `PollSchedulerWorker` in `main.py` lifespan** — Add to `_lifespan()` in `backend/app/main.py` alongside existing workers. Store in `app.state.poll_scheduler_worker`. Graceful `stop()` in `finally` block. Smoke test: start dev server, confirm worker loop log line appears. | `docs, plan` | ✅ |
| 4 | **Phase gate — full test suite + push** — Run test-runner in Full mode. Fix regressions. Commit plan update. Push. | `plan, commands` | ⬜ |

---

## Phase 5: Frontend

**Status:** ⬜ Incomplete

*TypeScript types, API hooks, onboarding step, Job Search settings card section, and job card
fit/stretch visual treatment.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-034 §9 |
| 🧪 **TDD** | Vitest unit tests for components; Playwright E2E for onboarding step flow |
| 🗃️ **Patterns** | Step pattern: `onboarding-steps.ts` array + `page.tsx` switch. Settings: card sections in `settings-page.tsx`. Job card: `chat-job-card.tsx` (`ScoreTierBadge` + conditional rendering). |
| ✅ **Verify** | `npm test`, `npm run lint`, `npm run typecheck` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `ui-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). | `plan, security` | ⬜ |
| 2 | **TypeScript types + API client hooks for SearchProfile** — Create `frontend/src/types/search-profile.ts` with `SearchBucket` and `SearchProfile` interfaces matching REQ-034 §4.2 JSONB shapes. Add `queryKeys.searchProfile(personaId)` to `frontend/src/lib/query-keys.ts`. Add `getSearchProfile`, `generateSearchProfile`, `updateSearchProfile` functions to API client helper. | `tdd, docs, plan` | ⬜ |
| 3 | **Onboarding step: "Your Job Search Criteria"** — Insert new step at position 10 in `frontend/src/components/onboarding/onboarding-steps.ts` (`key: "search-criteria"`, `name: "Your Job Search Criteria"`, `skippable: false`). Renumber existing steps 10→11, 11→12. Create `frontend/src/components/onboarding/steps/search-criteria-step.tsx`: fetch `SearchProfile` on mount (auto-trigger generation if none exists), loading state during generation, editable tag lists for fit + stretch buckets (add/remove chips), "Looks good" button calls `updateSearchProfile` to set `approved_at`. Update switch statement in `frontend/src/app/onboarding/page.tsx` for new step numbers. Vitest tests: loading state, tag add/remove, approve action. | `tdd, ui, docs, plan` | ⬜ |
| 4 | **Job Search settings card section** — Create `frontend/src/components/settings/job-search-section.tsx` per REQ-034 §9.2. Follows existing card-section pattern (e.g., `AccountSection`). Contains: (a) Search Criteria — editable `SearchProfile` fit/stretch buckets (extract shared `SearchProfileEditor` component reused from onboarding step if needed), (b) Poll Schedule — display `polling_frequency`, `last_poll_at`, `next_poll_at`, (c) Job Sources — embed existing `JobSourcesSection` toggles, (d) "Refresh Criteria" button → calls `generateSearchProfile()`, (e) Staleness banner when `is_stale=true`. Add `JobSearchSection` to `frontend/src/components/settings/settings-page.tsx`. Vitest tests for section. | `tdd, ui, docs, plan` | ⬜ |
| 5 | **Job card: fit/stretch visual treatment** — In `frontend/src/components/chat/chat-job-card.tsx` (and any jobs-page card), add conditional "Growth Role" amber chip per REQ-034 §9.3. Decision rule: `stretch_score > fit_score + 10` → stretch; else fit. Stretch: amber chip (`--color-logo-accent` #fbbf24) in card header, score label `{stretch_score}% stretch`. Fit: unchanged (`{fit_score}% match`). Add `search_bucket` prop; prefer it when available, fall back to score rule. Vitest tests for both rendering paths. | `tdd, ui, docs, plan` | ⬜ |
| 6 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + vitest + Playwright + lint + typecheck). Fix regressions. Commit plan update. Push. | `plan, commands, e2e` | ⬜ |

---

## Phase 6: API Key Setup & Smoke Test

**Status:** ⬜ Incomplete

*Guided registration for Adzuna, The Muse, and USAJobs — wire credentials into `.env` and
verify live adapter calls. No code changes, no pre-push hooks, no test gate.*

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **API key registration walkthrough** — Claude guides you through: (a) **Adzuna** — developer.adzuna.com → register app → copy `app_id` + `app_key`. (b) **The Muse** — themuse.com/developers/api/v2 → register → copy `api_key`. (c) **USAJobs** — developer.usajobs.gov → email-based registration → note email + choose app name string (e.g. `ZentropyScount/1.0`). RemoteOK: no registration needed. | `plan` | ⬜ |
| 2 | **Wire credentials + smoke test** — Add keys to local `.env`: `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `THE_MUSE_API_KEY`, `USAJOBS_USER_AGENT`, `USAJOBS_EMAIL`. Run manual integration test for each adapter (one-off Python invocation via `! python`) to verify each `fetch_jobs()` returns live results. Confirm RemoteOK returns ~97 jobs in one call. Document any auth or rate-limit issues encountered. | `plan, commands` | ⬜ |

---

## Task Count Summary

| Phase | Tasks | Gate |
|-------|-------|------|
| Phase 1: Foundation | 7 | Push |
| Phase 2: SearchProfile Backend | 8 | Push |
| Phase 3: Adapters, Pipeline & Skill Extraction | 9 | Push |
| Phase 4: Poll Scheduler | 4 | Push |
| Phase 5: Frontend | 6 | Push |
| Phase 6: API Key Setup | 2 | None |
| **Total** | **36** | |

---

## Critical Files Reference

### Backend — Modified
| File | Change |
|------|--------|
| `backend/app/adapters/sources/base.py` | Add 3 fields to `SearchParams` |
| `backend/app/adapters/sources/adzuna.py` | Implement `fetch_jobs()` |
| `backend/app/adapters/sources/remoteok.py` | Implement `fetch_jobs()` |
| `backend/app/adapters/sources/themuse.py` | Implement `fetch_jobs()` |
| `backend/app/adapters/sources/usajobs.py` | Implement `fetch_jobs()` |
| `backend/app/services/discovery/job_fetch_service.py` | Replace hardcoded `SearchParams` (~line 221) |
| `backend/app/services/discovery/job_enrichment_service.py` | Un-stub `extract_skills_and_culture()` (~line 183) |
| `backend/app/services/discovery/global_dedup_service.py` | Add `search_bucket` param to `deduplicate_and_save()` |
| `backend/app/models/persona_job.py` | Map new `search_bucket` column |
| `backend/app/models/job_source.py` | Map new `last_seen_external_ids` on `PollingConfiguration` |
| `backend/app/core/config.py` | Add 5 API key fields to `Settings` |
| `backend/app/main.py` | Register `PollSchedulerWorker` in `_lifespan()` |

### Backend — New
| File | Purpose |
|------|---------|
| `backend/app/models/search_profile.py` | `SearchProfile` SQLAlchemy model |
| `backend/app/schemas/search_profile.py` | Pydantic read/create/update schemas |
| `backend/app/repositories/search_profile_repository.py` | CRUD repository |
| `backend/app/services/discovery/search_profile_service.py` | Fingerprint, staleness, AI generation |
| `backend/app/services/discovery/poll_scheduler_worker.py` | Background polling worker |
| `backend/app/api/v1/search_profiles.py` | API router (3 endpoints) |
| `backend/alembic/versions/<hash>_add_search_profiles.py` | Create `search_profiles` table |
| `backend/alembic/versions/<hash>_add_search_bucket_and_cursors.py` | Alter `persona_jobs` + `polling_configurations` |
| `backend/alembic/versions/<hash>_seed_search_profile_task_type.py` | Data migration for task routing config |

### Frontend — Modified
| File | Change |
|------|--------|
| `frontend/src/components/onboarding/onboarding-steps.ts` | Insert step 10, renumber 10→11, 11→12 |
| `frontend/src/app/onboarding/page.tsx` | Update switch statement for new step numbers |
| `frontend/src/components/settings/settings-page.tsx` | Add `JobSearchSection` |
| `frontend/src/lib/query-keys.ts` | Add `searchProfile(personaId)` key |
| `frontend/src/components/chat/chat-job-card.tsx` | Add fit/stretch visual treatment |
| `.env.example` | Add 5 API key template entries |

### Frontend — New
| File | Purpose |
|------|---------|
| `frontend/src/types/search-profile.ts` | `SearchBucket`, `SearchProfile` TS interfaces |
| `frontend/src/components/onboarding/steps/search-criteria-step.tsx` | New onboarding step component |
| `frontend/src/components/settings/job-search-section.tsx` | New settings card section |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-04-03 | Plan created |
