# Zentropy Scout — REQ-022 Admin Pricing Dashboard & Model Registry Implementation Plan

**Created:** 2026-03-01
**Last Updated:** 2026-03-01
**Status:** In Progress
**Destination:** `docs/plan/admin_pricing_plan.md`

---

## Context

REQ-022 replaces hardcoded pricing dicts, routing tables, and margin multipliers with admin-configurable database tables and an admin UI. It covers 5 new DB tables (model_registry, pricing_config, task_routing_config, credit_packs, system_config), an `is_admin` column on users, admin auth (ADMIN_EMAILS env var bootstrap, JWT `adm` claim, `require_admin` dependency), AdminConfigService (read-side: pricing lookup, routing lookup, model registration check), metering service migration (hardcoded → DB pricing), LLM adapter migration (model_override support, MeteredLLMProvider routing), admin CRUD service + API endpoints (7 endpoint groups), admin frontend (single page with 6 tabs), and a seed migration with current hardcoded values.

**Why now:** All backend phases, frontend phases, and token metering (REQ-020) are complete. The hardcoded pricing dicts, uniform margins, and fixed routing tables are blocking per-model margin tuning, runtime model management, and the downstream Credits & Billing work (REQ-021). Without this, every pricing change requires a code deploy.

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Load the relevant REQ section via `req-reader` subagent before each task
3. Each task = one commit, sized ≤ 40k tokens of context (TDD + review + fixes included)
4. **Subtask workflow:** Run affected tests → linters → commit → compact (NO push)
5. **Phase-end workflow:** Run full test suite (backend + frontend + E2E) → push → compact
6. After each task: update status (⬜ → ✅), commit, STOP and ask user

**Workflow pattern:**

| Action | Subtask (§1–§2, §4–§5, §7–§9, §11–§13, §15–§17, §19–§20) | Phase Gate (§3, §6, §10, §14, §18, §21) |
|--------|----------------------|-------------------------------------|
| Tests | Affected files only | Full backend + frontend + E2E |
| Linters | Pre-commit hooks (~25-40s) | Pre-commit + pre-push hooks |
| Git | `git commit` only | `git push` |
| Context | Compact after commit | Compact after push |

**Why:** Pushes trigger pre-push hooks (full pytest + vitest, ~90-135s). By deferring pushes to phase boundaries, we save ~90-135s per subtask while maintaining quality gates.

**Context management for fresh sessions:** Each subtask is self-contained. A fresh context window needs:
1. This plan (find current task by status icon)
2. The REQ-022 document (via `req-reader` — load the §section listed in the task)
3. The specific files listed in the task description
4. No prior conversation history required

---

## Dependency Chain

```
Phase 1: Database Foundation (REQ-022 §4, §12)
    │
    ↓
Phase 2: Admin Auth & Read Services (REQ-022 §5, §6, §13)
    │
    ↓
Phase 3: Backend Migration (REQ-022 §7, §8, §9)
    │
    ↓
Phase 4: Admin CRUD & API (REQ-022 §10)
    │
    ↓
Phase 5: Admin Frontend (REQ-022 §11)
    │
    ↓
Phase 6: Integration & Verification (REQ-022 §15)
```

**Ordering rationale:** Bottom-up construction. Phase 1 creates the 5 DB tables + seed data everything depends on. Phase 2 builds admin authentication infrastructure and the read-side AdminConfigService (pricing lookup, routing lookup, model registration check). Phase 3 uses AdminConfigService to migrate the metering service and LLM adapters from hardcoded to DB-backed config. Phase 4 builds admin CRUD endpoints (depends on Phase 1 models + Phase 2 auth). Phase 5 builds the frontend admin UI against Phase 4's API. Phase 6 runs end-to-end integration verification.

---

## Phase 1: Database Foundation (REQ-022 §4, §12)

**Status:** ✅ Complete

*Create SQLAlchemy models for all 5 admin tables, add `is_admin` column to User, create the Alembic migration with seed data. No business logic yet — just schema and initial data.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-022 §4, §12 |
| 🧪 **TDD** | Write tests first → code → run affected tests only |
| ✅ **Verify** | `ruff check <modified_files>`, `bandit <modified_files>` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `qa-reviewer` (parallel) |
| 📝 **Commit** | `git commit` (pre-commit hooks) |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Create ORM models for 5 admin tables + User extension (TDD)** | `tdd, db, plan` | ✅ |
| 2 | **Create Alembic migration with seed data** — Single migration creates tables, indexes, and seeds all data. **Read:** REQ-022 §4.7–§4.8 (indexes, migration notes), REQ-022 §12.1–§12.5 (seed data tables), `backend/migrations/versions/020_token_metering.py` (migration pattern: type-local constants, named constraints, `op.bulk_insert`), `backend/app/providers/llm/claude_adapter.py` lines 49–62 (DEFAULT_CLAUDE_ROUTING), `backend/app/providers/llm/openai_adapter.py` lines 49–62 (DEFAULT_OPENAI_ROUTING), `backend/app/providers/llm/gemini_adapter.py` lines 51–64 (DEFAULT_GEMINI_ROUTING), `backend/app/services/metering_service.py` lines 27–64 (_LLM_PRICING dict). **Create:** `backend/migrations/versions/021_admin_pricing.py` (~250L) — **Upgrade:** (1) Add is_admin BOOLEAN NOT NULL DEFAULT FALSE to users; (2) Create model_registry table with UniqueConstraint(provider, model); (3) Create pricing_config table with UniqueConstraint(provider, model, effective_date); (4) Create task_routing_config table with UniqueConstraint(provider, task_type); (5) Create credit_packs table; (6) Create system_config table with key as VARCHAR(100) PK; (7) Create 3 indexes (ix_pricing_config_lookup, ix_task_routing_config_lookup, ix_credit_packs_active partial); (8) Seed model_registry with 9 models per §12.1; (9) Seed pricing_config with 8 entries per §12.2 (effective_date = current date); (10) Seed task_routing_config with 33 entries per §12.3 (11 per provider); (11) Seed system_config with signup_grant_credits=0; (12) Seed credit_packs with 3 packs per §12.5. Use `op.bulk_insert()` for seed data with type-local constants for all values. **Downgrade:** Drop all 5 tables, drop indexes, remove is_admin column from users. **Run:** `cd backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head` (test both directions). **Done when:** Migration applies cleanly, all tables created with seed data, downgrade removes everything, re-upgrade succeeds. | `db, commands, plan` | ✅ |
| 3 | **Phase gate — full test suite + push** — Run complete test suites, fix regressions. **Run:** `pytest tests/ -v`, `npm run test:run`, `npx playwright test`. **Also:** `ruff check .`, `npm run lint`, `npm run typecheck`. **Push:** `GIT_SSH_COMMAND="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=10" git push`. **Done when:** All tests green, pushed to remote. | `plan, commands` | ✅ |

#### Phase 1 Notes

**Migration seed data approach:** Use `op.bulk_insert(table, [...])` with `sa.table()` references for each table. All seed values are defined as type-local constants at the top of the migration file. This keeps the migration self-contained and auditable.

**SystemConfig PK:** Unlike all other models, SystemConfig uses `key VARCHAR(100)` as its primary key instead of a UUID. This matches the key-value store design in REQ-022 §4.6.

---

## Phase 2: Admin Auth & Read Services (REQ-022 §5, §6, §13)

**Status:** ✅ Complete

*Build admin authentication infrastructure (ADMIN_EMAILS bootstrap, JWT `adm` claim, `require_admin` dependency) and the read-side AdminConfigService (pricing lookup, routing lookup, model registration check, system config). No CRUD yet — just reading existing data.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-022 §5, §6, §13 |
| 🧪 **TDD** | Write tests first → code → run affected tests only |
| ✅ **Verify** | `ruff check <modified_files>`, `bandit <modified_files>` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `qa-reviewer` (parallel) |
| 📝 **Commit** | `git commit` (pre-commit hooks) |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 4 | **Add admin auth infrastructure (TDD)** — ADMIN_EMAILS config, JWT `adm` claim, `require_admin` dependency, login bootstrap. **Read:** REQ-022 §5.1–§5.5 (admin auth spec), §13 (env vars), `backend/app/core/config.py` (Settings class), `backend/app/core/auth.py` (create_jwt function lines 39–68), `backend/app/api/deps.py` (get_current_user_id, require_sufficient_balance pattern), `backend/app/core/errors.py` (error class pattern — APIError, ConflictError, ForbiddenError), `backend/app/api/v1/auth.py` (verify_password endpoint — login flow), `backend/app/repositories/user_repository.py` (_UPDATABLE_FIELDS). **Modify:** `backend/app/core/config.py` (~5L) — add `admin_emails: str = ""` to Settings class. Keep `metering_margin_multiplier` for now (defer removal to §8 to avoid breaking MeteringService). **Modify:** `backend/app/core/auth.py` (~8L) — add `is_admin: bool = False` parameter to `create_jwt()`. When `is_admin=True`, include `"adm": True` in the JWT payload. When False, omit the claim entirely (do not set to False — absence means not admin). **Modify:** `backend/app/core/errors.py` (~20L) — add `AdminRequiredError(ForbiddenError)` with code `"ADMIN_REQUIRED"` and message `"Admin access required"`. Add `UnregisteredModelError(APIError)` with code `"UNREGISTERED_MODEL"`, status 503, accepts provider + model. Add `NoPricingConfigError(APIError)` with code `"NO_PRICING_CONFIG"`, status 503, accepts provider + model. **Modify:** `backend/app/api/deps.py` (~20L) — add `async def require_admin(user_id: CurrentUserId, db: DbSession) -> uuid.UUID` dependency that queries `User.is_admin`, raises `AdminRequiredError` if not admin. Add `AdminUser = Annotated[uuid.UUID, Depends(require_admin)]` type alias. **Modify:** `backend/app/repositories/user_repository.py` (~2L) — add `"is_admin"` to `_UPDATABLE_FIELDS` frozenset. **Modify:** `backend/app/api/v1/auth.py` (~15L) — in `verify_password` endpoint, after successful authentication but before JWT issuance: parse `settings.admin_emails` (comma-separated, strip whitespace, lowercase), check if user.email matches any, if yes and not already admin then `await UserRepository.update(db, user.id, is_admin=True)` + `await db.commit()`. Pass `is_admin=user.is_admin` (refreshed after potential update) to `create_jwt()`. **Modify:** `backend/.env.example` (~2L) — add `ADMIN_EMAILS=` with comment. **Create:** `backend/tests/unit/test_admin_auth.py` (~30 tests) — Test `create_jwt` with is_admin=True includes adm claim; is_admin=False omits adm claim. Test `require_admin`: admin user passes, non-admin gets 403 ADMIN_REQUIRED, user-not-found gets 403. Test ADMIN_EMAILS bootstrap: matching email on login sets is_admin=True; case-insensitive matching; non-matching email does NOT change is_admin; already-admin user not re-updated. Test AdminRequiredError, UnregisteredModelError, NoPricingConfigError error shapes. **Run:** `pytest tests/unit/test_admin_auth.py tests/unit/test_auth.py -v` **Done when:** JWT includes adm claim for admins, require_admin dependency works, ADMIN_EMAILS bootstrap on login works, all 3 new error classes defined. | `tdd, security, plan` | ✅ |
| 5 | **Create AdminConfigService — read-side config lookups (TDD)** — Pricing lookup with effective dates, routing lookup with fallback, model registration check, system config accessors. **Read:** REQ-022 §6.1–§6.3 (service interface), §4.3 (effective date query pattern), §4.4 (routing fallback order), `backend/app/services/metering_service.py` (service pattern: `__init__` takes AsyncSession), `backend/app/models/admin_config.py` (models from §1). **Create:** `backend/app/services/admin_config_service.py` (~120L) — `AdminConfigService` class. `__init__(self, db: AsyncSession)`. `_db` private attribute. Module-level logger. Methods: (1) `async def get_pricing(self, provider: str, model: str) -> PricingResult | None` — query pricing_config WHERE provider AND model AND effective_date <= CURRENT_DATE ORDER BY effective_date DESC LIMIT 1. Return `PricingResult` frozen dataclass or None. (2) `async def get_model_for_task(self, provider: str, task_type: str) -> str | None` — query task_routing_config for exact (provider, task_type) match first; if None, query (provider, '_default'); return model or None. (3) `async def is_model_registered(self, provider: str, model: str) -> bool` — query model_registry WHERE provider AND model AND is_active=True, return exists. (4) `async def get_system_config(self, key: str, default: str | None = None) -> str | None` — query system_config by key PK, return value or default. (5) `async def get_system_config_int(self, key: str, default: int = 0) -> int` — calls get_system_config, parses to int or returns default. Define `PricingResult` as frozen dataclass: input_cost_per_1k (Decimal), output_cost_per_1k (Decimal), margin_multiplier (Decimal), effective_date (date). **Modify:** `backend/app/api/deps.py` (~5L) — add `def get_admin_config_service(db: DbSession) -> AdminConfigService` function and `AdminConfig = Annotated[AdminConfigService, Depends(get_admin_config_service)]` type alias. **Create:** `backend/tests/unit/test_admin_config_service.py` (~35 tests) — Integration tests with real DB (`db_session` fixture). Test pricing: effective_date_picks_latest_before_today, future_effective_date_not_used, effective_date_exact_match_today, multiple_effective_dates_picks_most_recent, no_pricing_returns_none. Test routing: exact_match_returns_model, fallback_to_default, no_entries_returns_none. Test model_registered: active_model_returns_true, inactive_model_returns_false, unregistered_returns_false. Test system_config: existing_key_returns_value, missing_key_returns_default, get_int_parses_correctly, get_int_returns_default_for_missing. All tests insert seed data directly via `db.add()` before assertions. **Run:** `pytest tests/unit/test_admin_config_service.py -v` **Done when:** All pricing effective date scenarios work, routing fallback order correct, model registration check works, system config typed accessors work. | `tdd, db, plan` | ✅ |
| 6 | **Phase gate — full test suite + push** — Run complete test suites, fix regressions. **Run:** `pytest tests/ -v`, `npm run test:run`, `npx playwright test`. **Also:** `ruff check .`, `npm run lint`, `npm run typecheck`. **Push:** `GIT_SSH_COMMAND="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=10" git push`. **Done when:** All tests green, pushed to remote. | `plan, commands` | ✅ |

#### Phase 2 Notes

**ADMIN_EMAILS parsing:** `[e.strip().lower() for e in settings.admin_emails.split(",") if e.strip()]`. Handle empty string gracefully (produces empty list).

**JWT adm claim:** Only include when True. Absence means non-admin. Do not set `"adm": False` in the payload — this reduces JWT size for the common case (non-admin users).

**AdminConfigService tests need Docker:** These tests use the `db_session` fixture (real PostgreSQL) since they query actual tables. Ensure Docker is up.

---

## Phase 3: Backend Migration (REQ-022 §7, §8, §9)

**Status:** ⬜ Incomplete

*Migrate MeteringService from hardcoded pricing to DB-backed pricing via AdminConfigService. Add `model_override` to LLM adapter `complete()` signatures. Wire routing into MeteredLLMProvider. All changes are backward-compatible — `metering_enabled=false` still uses hardcoded defaults.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-022 §7, §8, §9 |
| 🧪 **TDD** | Write tests first → code → run affected tests only |
| ✅ **Verify** | `ruff check <modified_files>`, `bandit <modified_files>` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `qa-reviewer` (parallel) |
| 📝 **Commit** | `git commit` (pre-commit hooks) |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 7 | **Add `model_override` to LLM adapter `complete()` signatures (TDD)** — Base class and all 3 adapters accept optional `model_override`. **Read:** REQ-022 §8.1–§8.4 (adapter changes), `backend/app/providers/llm/base.py` (LLMProvider.complete signature), `backend/app/providers/llm/claude_adapter.py` (complete method), `backend/app/providers/llm/openai_adapter.py` (complete method), `backend/app/providers/llm/gemini_adapter.py` (complete method), `backend/app/providers/metered_provider.py` (MeteredLLMProvider.complete). **Modify:** `backend/app/providers/llm/base.py` (~3L) — add `model_override: str | None = None` as last parameter to `complete()` abstract method. **Modify:** `backend/app/providers/llm/claude_adapter.py` (~5L) — accept `model_override: str | None = None` in `complete()`. Change `model = self.get_model_for_task(task)` to `model = model_override or self.get_model_for_task(task)`. Add fallback docstring comment on `DEFAULT_CLAUDE_ROUTING` per §8.4. **Modify:** `backend/app/providers/llm/openai_adapter.py` (~5L) — same pattern as Claude. **Modify:** `backend/app/providers/llm/gemini_adapter.py` (~5L) — same pattern as Gemini. **Modify:** `backend/app/providers/metered_provider.py` (~3L) — add `model_override: str | None = None` to MeteredLLMProvider.complete() signature. Pass through to inner `complete()` (temporarily — will be replaced in §9 with DB routing). **Update existing tests:** Add: test model_override used when provided, test fallback to hardcoded routing when model_override=None (per adapter). **Run:** `pytest tests/unit/test_claude_adapter.py tests/unit/test_openai_adapter.py tests/unit/test_gemini_adapter.py tests/unit/test_metered_provider.py -v` **Done when:** All 3 adapters accept model_override, use it when provided, fall back to hardcoded when None, MeteredLLMProvider passes through. | `tdd, plan` | ✅ |
| 8 | **Migrate MeteringService from hardcoded to DB pricing (TDD)** — Replace `_LLM_PRICING` and `_FALLBACK_PRICING` with AdminConfigService lookups. Per-model margins. **Read:** REQ-022 §7.1–§7.7 (metering migration spec), `backend/app/services/metering_service.py` (current implementation), `backend/app/services/admin_config_service.py` (from §5), `backend/app/core/config.py` (`metering_margin_multiplier` to remove). **Modify:** `backend/app/services/metering_service.py` (~80L rewrite) — (1) Remove `_LLM_PRICING` dict (lines 27–64). (2) Remove `_FALLBACK_PRICING` dict (lines 68–81). (3) Change `__init__` to accept `admin_config: AdminConfigService` instead of `margin_multiplier`. Store as `self._admin_config`. (4) Add private `async def _get_pricing(self, provider, model) -> tuple[Decimal, Decimal, Decimal]` that: checks `is_model_registered` (raises UnregisteredModelError if not), gets effective pricing (raises NoPricingConfigError if None), returns (input_per_1k, output_per_1k, margin). (5) Make `calculate_cost` async, call `_get_pricing` internally. (6) Update `record_and_debit` to use `_get_pricing` for per-model margin instead of uniform `self._margin`. Record the per-model `margin_multiplier` in LLMUsageRecord. **Modify:** `backend/app/core/config.py` (~3L) — remove `metering_margin_multiplier` field. Add comment: `# REMOVED: metering_margin_multiplier (REQ-022 §7.7 — now per-model in pricing_config table)`. **Modify:** `backend/.env.example` (~2L) — remove METERING_MARGIN_MULTIPLIER line, add comment noting removal per REQ-022. **Modify:** `backend/app/services/embedding_cost.py` (~3L) — add docstring to `EMBEDDING_MODELS` noting production pricing comes from `pricing_config` table. **Update:** `backend/tests/unit/test_metering_service.py` (~rewrite) — Replace all hardcoded pricing tests with mocked AdminConfigService. Test: calculate_cost uses DB pricing (mock `get_pricing` return), per-model margin applied correctly (mock returns margin=3.0 for cheap model, 1.1 for expensive), unregistered model raises UnregisteredModelError, no pricing raises NoPricingConfigError, record_and_debit uses per-model margin from DB. Remove tests that reference `_LLM_PRICING` or `_FALLBACK_PRICING`. **Run:** `pytest tests/unit/test_metering_service.py -v` **Done when:** MeteringService reads pricing from AdminConfigService, per-model margins work, unregistered models blocked, hardcoded dicts removed, `metering_margin_multiplier` removed from config. | `tdd, plan` | ✅ |
| 9 | **Wire routing + AdminConfigService into MeteredLLMProvider and dependency injection (TDD)** — MeteredLLMProvider resolves routing from DB and passes `model_override` to inner adapter. Update DI dependencies. **Read:** REQ-022 §8.3 (MeteredLLMProvider routing), §7.5 (DI update), `backend/app/providers/metered_provider.py` (current MeteredLLMProvider + MeteredEmbeddingProvider), `backend/app/api/deps.py` (get_metered_provider, get_metered_embedding_provider). **Modify:** `backend/app/providers/metered_provider.py` (~40L) — (1) MeteredLLMProvider.__init__ now takes `admin_config: AdminConfigService` parameter. Store as `self._admin_config`. (2) MeteredLLMProvider.complete(): before calling `inner.complete()`, lookup routing via `self._admin_config.get_model_for_task(provider, task_type)`. Pass `model_override=resolved_model` to `inner.complete()`. If routing returns None, pass `model_override=None` (adapter uses hardcoded fallback). (3) MeteredEmbeddingProvider.__init__ takes `admin_config: AdminConfigService`. Pricing lookups already happen via MeteringService (which now has AdminConfigService). No routing change for embeddings (§8.5). **Modify:** `backend/app/api/deps.py` (~10L) — update `get_metered_provider`: create `AdminConfigService(db)`, pass to both `MeteringService(db, admin_config)` and `MeteredLLMProvider(inner, metering_service, admin_config, user_id)`. Update `get_metered_embedding_provider` same pattern. **Update:** `backend/tests/unit/test_metered_provider.py` (~15 new tests) — Test MeteredLLMProvider: routing lookup called with correct provider+task_type, model_override passed to inner.complete(), routing None passes model_override=None, metering uses DB-backed pricing. Test MeteredEmbeddingProvider: admin_config passed through to MeteringService. **Run:** `pytest tests/unit/test_metered_provider.py tests/unit/test_metering_service.py -v` **Done when:** MeteredLLMProvider resolves routing from DB, passes model_override to adapter, MeteringService uses DB pricing, DI wiring updated, all tests pass. | `tdd, plan` | ✅ |
| 10 | **Phase gate — full test suite + push** — Run complete test suites, fix regressions. **Run:** `pytest tests/ -v`, `npm run test:run`, `npx playwright test`. **Also:** `ruff check .`, `npm run lint`, `npm run typecheck`. **Push:** `GIT_SSH_COMMAND="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=10" git push`. **Done when:** All tests green, pushed to remote. | `plan, commands` | ⬜ |

#### Phase 3 Notes

**Backward compatibility:** When `METERING_ENABLED=false`, `get_metered_provider` returns the raw singleton provider (no AdminConfigService involved). The adapter uses its hardcoded routing. Tests that don't involve metering are unaffected.

**Existing test updates:** Some existing tests mock `MeteringService.__init__` with `margin_multiplier`. These must be updated to mock with `admin_config` instead. The `AsyncMock` for AdminConfigService should return predefined `PricingResult` objects.

---

## Phase 4: Admin CRUD & API (REQ-022 §10)

**Status:** ⬜ Incomplete

*Build Pydantic schemas for all admin resources, the AdminManagementService for CRUD operations with validation, and all admin API endpoints. This is the largest phase — split into 3 code tasks.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-022 §10 |
| 🧪 **TDD** | Write tests first → code → run affected tests only |
| ✅ **Verify** | `ruff check <modified_files>`, `bandit <modified_files>` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `qa-reviewer` (parallel) |
| 📝 **Commit** | `git commit` (pre-commit hooks) |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 11 | **Create admin Pydantic schemas (TDD)** — Request/response schemas for all admin API resources. **Read:** REQ-022 §10.1–§10.7 (all endpoint specs with request/response shapes), `backend/app/schemas/usage.py` (schema pattern: `ConfigDict(extra="forbid")`, monetary values as str), `backend/app/core/responses.py` (DataResponse, ListResponse envelopes). **Create:** `backend/app/schemas/admin.py` (~200L) — All schemas with `model_config = ConfigDict(extra="forbid")`. (1) **Model Registry:** `ModelRegistryCreate` (provider: str, model: str max 100, display_name: str max 100, model_type: str — validated 'llm' or 'embedding'), `ModelRegistryUpdate` (display_name: str | None, is_active: bool | None, model_type: str | None), `ModelRegistryResponse` (id: str, provider, model, display_name, model_type, is_active: bool, created_at: datetime, updated_at: datetime). (2) **Pricing:** `PricingConfigCreate` (provider, model, input_cost_per_1k: str, output_cost_per_1k: str, margin_multiplier: str, effective_date: date), `PricingConfigUpdate` (input_cost_per_1k: str | None, output_cost_per_1k: str | None, margin_multiplier: str | None), `PricingConfigResponse` (id, provider, model, input_cost_per_1k: str, output_cost_per_1k: str, margin_multiplier: str, effective_date: date, is_current: bool, created_at, updated_at). (3) **Routing:** `TaskRoutingCreate` (provider, task_type, model), `TaskRoutingUpdate` (model: str | None), `TaskRoutingResponse` (id, provider, task_type, model, model_display_name: str | None, created_at, updated_at). (4) **Credit Packs:** `CreditPackCreate` (name max 50, price_cents: int >0, credit_amount: int >0, display_order: int default 0, description: str | None max 255, highlight_label: str | None max 50), `CreditPackUpdate` (all optional), `CreditPackResponse` (id, name, price_cents, price_display: str, credit_amount, stripe_price_id: str | None, display_order, is_active: bool, description, highlight_label, created_at, updated_at). (5) **System Config:** `SystemConfigUpsert` (value: str, description: str | None max 255), `SystemConfigResponse` (key, value, description, updated_at: datetime). (6) **Admin Users:** `AdminUserUpdate` (is_admin: bool), `AdminUserResponse` (id, email, name: str | None, is_admin: bool, is_env_protected: bool, balance_usd: str, created_at: datetime). (7) **Cache:** `CacheRefreshResponse` (message: str, caching_enabled: bool). Add `@field_validator` on provider fields to enforce allowed values (claude, openai, gemini). Add validator on monetary string fields to parse as Decimal and reject negative. **Create:** `backend/tests/unit/test_admin_schemas.py` (~30 tests) — Test: valid creation schemas accept correct data, reject extra fields, reject invalid providers, reject negative monetary values, CreditPackCreate rejects price_cents ≤ 0, model_type validator rejects invalid types, PricingConfigResponse is_current is a regular field. **Run:** `pytest tests/unit/test_admin_schemas.py -v` **Done when:** All schemas validate correctly, reject invalid input, monetary values as strings, `extra="forbid"` on all. | `tdd, plan` | ⬜ |
| 12 | **Create AdminManagementService — CRUD operations (TDD)** — Business logic for all admin operations with validation. **Read:** REQ-022 §10.1–§10.7 (validation rules per endpoint), §14 (error codes), `backend/app/services/admin_config_service.py` (read-side service pattern), `backend/app/repositories/user_repository.py` (repository pattern for user updates), `backend/app/core/errors.py` (ConflictError pattern). **Create:** `backend/app/services/admin_management_service.py` (~280L) — `AdminManagementService` class. `__init__(self, db: AsyncSession)`. Private `self._db`. Module-level logger. Methods: (1) **Model Registry:** `list_models(provider, model_type, is_active filters)`, `create_model(data) -> ModelRegistry` (validate unique provider+model, raise ConflictError DUPLICATE_MODEL), `update_model(model_id, data) -> ModelRegistry` (404 if not found), `delete_model(model_id)` (check task_routing_config references, raise ConflictError MODEL_IN_USE if referenced). (2) **Pricing:** `list_pricing(provider, model filters)` (include computed is_current flag — compare against max effective_date ≤ today per provider+model), `create_pricing(data) -> PricingConfig` (validate model exists in registry — NotFoundError MODEL_NOT_FOUND if not, validate unique provider+model+effective_date — ConflictError DUPLICATE_PRICING), `update_pricing(pricing_id, data) -> PricingConfig`, `delete_pricing(pricing_id)` (check if last current pricing for active model — ConflictError LAST_PRICING). (3) **Routing:** `list_routing(provider filter)` (join model_registry for display_name), `create_routing(data) -> TaskRoutingConfig` (validate model in registry and active, validate task_type is valid TaskType or '_default', raise ConflictError DUPLICATE_ROUTING), `update_routing(routing_id, data)`, `delete_routing(routing_id)`. (4) **Credit Packs:** `list_packs()`, `create_pack(data) -> CreditPack`, `update_pack(pack_id, data)`, `delete_pack(pack_id)`. (5) **System Config:** `list_config()`, `upsert_config(key, data)` (merge semantics — insert or update), `delete_config(key)`. (6) **Admin Users:** `list_users(page, per_page, is_admin filter) -> tuple[list, int]` (include computed is_env_protected), `toggle_admin(admin_user_id, target_user_id, is_admin) -> User` (validate: cannot demote self — ConflictError CANNOT_DEMOTE_SELF, cannot demote env-protected — ConflictError ADMIN_EMAILS_PROTECTED; side effect: set `token_invalidated_before` on target user). **Create:** `backend/tests/unit/test_admin_management_service.py` (~50 tests) — Integration tests with real DB. Test all CRUD happy paths. Test validation: duplicate model 409, model-in-use delete 409, model-not-found on pricing create 404, duplicate pricing 409, duplicate routing 409, last-pricing delete 409, env-protected demotion 409, self-demotion 409, admin toggle sets `token_invalidated_before`. **Run:** `pytest tests/unit/test_admin_management_service.py -v` **Done when:** All CRUD operations work, all validation rules enforced, all error codes correct. | `tdd, db, security, plan` | ⬜ |
| 13 | **Create admin API endpoints + router registration (TDD)** — 7 endpoint groups wired to AdminManagementService. **Read:** REQ-022 §10.1–§10.7 (endpoint specs), `backend/app/api/v1/usage.py` (endpoint pattern — router, deps, response envelopes), `backend/app/api/v1/router.py` (router registration). **Create:** `backend/app/api/v1/admin.py` (~280L) — `router = APIRouter()`. All endpoints use `AdminUser` dependency (§5.3). (1) **Models:** `GET /models` (query params: provider, model_type, is_active), `POST /models` (201), `PATCH /models/{id}`, `DELETE /models/{id}` (204). (2) **Pricing:** `GET /pricing` (query params: provider, model), `POST /pricing` (201), `PATCH /pricing/{id}`, `DELETE /pricing/{id}` (204). (3) **Routing:** `GET /routing` (query params: provider), `POST /routing` (201), `PATCH /routing/{id}`, `DELETE /routing/{id}` (204). (4) **Credit Packs:** `GET /credit-packs`, `POST /credit-packs` (201), `PATCH /credit-packs/{id}`, `DELETE /credit-packs/{id}` (204). (5) **System Config:** `GET /config`, `PUT /config/{key}`, `DELETE /config/{key}` (204). (6) **Admin Users:** `GET /users` (pagination: page, per_page, is_admin filter), `PATCH /users/{id}`. (7) **Cache:** `POST /cache/refresh` (no-op per §2.7). Each endpoint instantiates `AdminManagementService(db)`, calls the service method, maps results to response schemas, wraps in `DataResponse` or `ListResponse`. **Modify:** `backend/app/api/v1/router.py` (~3L) — import admin module, `router.include_router(admin.router, prefix="/admin", tags=["admin"])`. **Create:** `backend/tests/unit/test_admin_api.py` (~40 tests) — HTTP-level tests using TestClient. Test: auth gate (403 for non-admin on every endpoint group), successful CRUD for each resource type, correct status codes (201 for POST, 204 for DELETE), response envelope shape, pagination on users endpoint, cache refresh returns 200 with caching_enabled=false. Test with mock admin user via `app.dependency_overrides[require_admin]`. **Run:** `pytest tests/unit/test_admin_api.py -v` **Done when:** All endpoints accessible to admins, 403 for non-admins, correct HTTP status codes, response shapes match spec. | `tdd, api, security, plan` | ⬜ |
| 14 | **Phase gate — full test suite + push** — Run complete test suites, fix regressions. **Run:** `pytest tests/ -v`, `npm run test:run`, `npx playwright test`. **Also:** `ruff check .`, `npm run lint`, `npm run typecheck`. **Push:** `GIT_SSH_COMMAND="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=10" git push`. **Done when:** All tests green, pushed to remote. | `plan, commands` | ⬜ |

#### Phase 4 Notes

**is_current computed field:** The pricing listing needs to determine which pricing entry is "current" for each (provider, model). This is the entry with the latest `effective_date <= today`. The service computes this per provider+model group and sets a boolean flag, which is returned in the response schema.

**price_display computed field:** `CreditPackResponse.price_display` formats `price_cents` as `"$X.XX"` (e.g., 500 → `"$5.00"`). This is done in the API layer when constructing the response.

**AdminManagementService vs AdminConfigService:** AdminConfigService is the read-side service used by MeteringService and MeteredLLMProvider during normal operation. AdminManagementService is the write-side service used only by admin endpoints. They are separate because the read-side needs to be injected into the metering pipeline, while the write-side is admin-only.

---

## Phase 5: Admin Frontend (REQ-022 §11)

**Status:** ⬜ Incomplete

*Build the frontend admin gate (middleware + nav), admin page route, API client, and 6 tab components. Each tab provides CRUD UI for its corresponding admin API endpoint group.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-022 §11 |
| 🧪 **TDD** | Write tests first → code → run affected tests only |
| ✅ **Verify** | `npm run lint`, `npm run typecheck` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `qa-reviewer` (parallel) |
| 📝 **Commit** | `git commit` (pre-commit hooks) |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 15 | **Add admin gate + nav link + API client + types (TDD)** — Middleware admin route guard, conditional admin nav link, admin API client functions, TypeScript types, query key entries. **Read:** REQ-022 §5.4 (frontend admin gate), §11.4 (nav bar extension), `frontend/src/proxy.ts` (middleware pattern — cookie presence check), `frontend/src/components/layout/top-nav.tsx` (nav items + right-side area), `frontend/src/lib/auth-provider.tsx` (User type, useSession, checkSession, `_user_to_response` — need is_admin mapped), `frontend/src/lib/query-keys.ts` (query key factory), `frontend/src/lib/api-client.ts` (apiGet/apiPost/apiPatch/apiDelete), `frontend/src/types/usage.ts` (type pattern). **Modify:** `backend/app/api/v1/auth_magic_link.py` (~2L) — add `"is_admin": user.is_admin` to `_user_to_response()` dict (line ~295). **Modify:** `frontend/src/proxy.ts` (~15L) — add admin route check for paths starting with `/admin`: decode JWT payload from cookie (base64 parse the payload segment — no verification, UX only), check for `adm` claim. If not present, redirect to `/`. **Modify:** `frontend/src/lib/auth-provider.tsx` (~5L) — add `isAdmin: boolean` to User interface. In `checkSession`, map `me.is_admin` to `session.isAdmin`. **Modify:** `frontend/src/components/layout/top-nav.tsx` (~15L) — add conditional "Admin" link (Shield icon from lucide-react) in the right-side area, visible only when `session?.isAdmin` is true. Link navigates to `/admin/config`. **Modify:** `frontend/src/lib/query-keys.ts` (~10L) — add admin query keys: `adminModels`, `adminPricing`, `adminRouting`, `adminPacks`, `adminConfig`, `adminUsers`. **Create:** `frontend/src/types/admin.ts` (~80L) — TypeScript interfaces for all admin API resources: `ModelRegistryItem`, `PricingConfigItem`, `TaskRoutingItem`, `CreditPackItem`, `SystemConfigItem`, `AdminUserItem`. Create/update request types. **Create:** `frontend/src/lib/api/admin.ts` (~100L) — Admin API client functions using apiGet/apiPost/apiPatch/apiDelete. Functions for each endpoint group: `fetchModels()`, `createModel()`, `updateModel()`, `deleteModel()`, `fetchPricing()`, `createPricing()`, `updatePricing()`, `deletePricing()`, `fetchRouting()`, `createRouting()`, `updateRouting()`, `deleteRouting()`, `fetchPacks()`, `createPack()`, `updatePack()`, `deletePack()`, `fetchConfig()`, `upsertConfig()`, `deleteConfig()`, `fetchUsers()`, `toggleAdmin()`, `refreshCache()`. All hit `/admin/*` endpoints. **Create:** `frontend/src/lib/api/admin.test.ts` (~20 tests) — Test each API function calls correct URL with correct method. **Modify:** `frontend/src/components/layout/top-nav.test.tsx` (~5 new tests) — Test: admin link visible when session.isAdmin=true, hidden when false, navigates to /admin/config. **Run:** `npm run test:run`, `npm run lint`, `npm run typecheck` **Done when:** Middleware gates admin routes, admin nav link appears for admins only, API client functions defined, types defined, query keys registered, /auth/me includes is_admin. | `tdd, security, plan` | ⬜ |
| 16 | **Create admin page + Models tab + Pricing tab (TDD)** — Admin config page route with tab navigation, Models tab CRUD, Pricing tab CRUD with live cost preview. **Read:** REQ-022 §11.1–§11.5 (page structure, tabs, UI components), `frontend/src/app/(main)/usage/page.tsx` (page route pattern), `frontend/src/components/usage/usage-page.tsx` (page component pattern — Card layout), `frontend/src/components/settings/settings-page.tsx` (Card + section pattern). **Create:** `frontend/src/app/(main)/admin/config/page.tsx` (~20L) — thin route file with `"use client"`, imports AdminConfigPage component, guards with useSession (redirect if not admin). **Create:** `frontend/src/components/admin/admin-config-page.tsx` (~80L) — main page component. Tab navigation with 6 tabs (Models, Pricing, Routing, Packs, System, Users). Uses URL hash or state for active tab. Renders the corresponding tab component. Card-based layout with Tailwind. `data-testid` on each tab button and tab panel. **Create:** `frontend/src/components/admin/models-tab.tsx` (~150L) — Table of registered models. Columns: Provider, Model, Display Name, Type, Active (toggle), Actions (edit/delete). Add form (modal or inline) with validation. Uses `useQuery` + `useMutation` from TanStack Query. Query key: adminModels. Delete confirmation dialog. Toast on success/error. **Create:** `frontend/src/components/admin/pricing-tab.tsx` (~180L) — Table of pricing entries. Columns: Provider, Model, Input/1K, Output/1K, Margin, Effective Date, Current badge, Actions. "Current" badge computed client-side (latest effective_date ≤ today for each provider+model). Add/edit form with live cost preview: show calculated raw cost and billed cost for example 1000 input + 500 output tokens. Query key: adminPricing. **Create:** `frontend/src/components/admin/admin-config-page.test.tsx` (~10 tests) — render, tab navigation works, correct tab shown on click. **Create:** `frontend/src/components/admin/models-tab.test.tsx` (~15 tests) — render, table displays data, add form submission, delete confirmation, toggle active. **Create:** `frontend/src/components/admin/pricing-tab.test.tsx` (~15 tests) — render, table displays data, current badge shown, add form with cost preview, cost preview updates on input. **Run:** `npm run test:run`, `npm run lint`, `npm run typecheck` **Done when:** Admin page renders with tab navigation, Models tab CRUD works, Pricing tab CRUD works with live cost preview. | `tdd, plan` | ⬜ |
| 17 | **Create Routing tab + Packs tab + System tab + Users tab (TDD)** — Remaining 4 tabs. **Read:** REQ-022 §10.3–§10.7 (endpoint specs for routing, packs, config, users), §11.2 (tab content descriptions). **Create:** `frontend/src/components/admin/routing-tab.tsx` (~140L) — Per-provider routing table. Columns: Provider, Task Type, Model (with display name), Actions. Add form with model dropdown (populated from model registry). Task type validated against TaskType enum values + '_default'. Query key: adminRouting. **Create:** `frontend/src/components/admin/packs-tab.tsx` (~140L) — Credit pack table. Columns: Name, Price ($X.XX), Credits, Stripe ID, Order, Active, Highlight, Description, Actions. Add/edit form. Query key: adminPacks. **Create:** `frontend/src/components/admin/system-tab.tsx` (~100L) — Key-value config table. Columns: Key, Value, Description, Actions. Inline edit with PUT upsert. Add new key form. Query key: adminConfig. **Create:** `frontend/src/components/admin/users-tab.tsx` (~130L) — User table with pagination. Columns: Email, Name, Admin (toggle), Env Protected (badge), Balance, Joined. Toggle admin button (disabled for env-protected admins and self). Pagination using ListResponse meta. Query key: adminUsers. **Create:** `frontend/src/components/admin/routing-tab.test.tsx` (~12 tests), `frontend/src/components/admin/packs-tab.test.tsx` (~12 tests), `frontend/src/components/admin/system-tab.test.tsx` (~10 tests), `frontend/src/components/admin/users-tab.test.tsx` (~12 tests) — Test: render, table data, CRUD operations, validation (env-protected badge, self-toggle disabled, pagination). **Run:** `npm run test:run`, `npm run lint`, `npm run typecheck` **Done when:** All 6 tabs render and provide CRUD functionality, all frontend tests pass. | `tdd, plan` | ⬜ |
| 18 | **Phase gate — full test suite + push** — Run complete test suites, fix regressions. **Run:** `pytest tests/ -v`, `npm run test:run`, `npx playwright test`. **Also:** `ruff check .`, `npm run lint`, `npm run typecheck`. **Push:** `GIT_SSH_COMMAND="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=10" git push`. **Done when:** All tests green, pushed to remote. | `plan, commands` | ⬜ |

#### Phase 5 Notes

**Middleware JWT decode:** The frontend middleware (`proxy.ts`) only does a base64 decode of the JWT payload segment — NOT cryptographic verification. This is a UX convenience to avoid loading the admin page before the 403 is returned by the backend. The backend's `require_admin` dependency is the authoritative security check.

**Tab state:** Use URL hash (`#models`, `#pricing`, etc.) for tab state so direct links to specific tabs work. Default to `#models` if no hash.

**No separate admin layout:** Per REQ-022 §11.1, the admin page reuses the existing `(main)` layout with the standard nav bar. No separate admin layout needed.

---

## Phase 6: Integration & Verification (REQ-022 §15)

**Status:** ⬜ Incomplete

*Backend integration tests for the full admin + metering pipeline, E2E Playwright tests for the admin UI, and final verification gate.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-022 §15 |
| 🧪 **TDD** | Tests for the full integration flow |
| ✅ **Verify** | Full quality gate |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `qa-reviewer` (parallel) |
| 📝 **Commit** | `git commit` (pre-commit hooks) |
| ⏸️ **Compact** | Compact after push |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 19 | **Backend integration tests for full admin + metering pipeline** — End-to-end flow: admin creates model → creates pricing → creates routing → LLM call uses DB-backed config and bills at per-model margin. **Read:** REQ-022 §15.2–§15.3 (key test scenarios, integration tests), `backend/tests/integration/test_metering_pipeline.py` (existing integration test pattern), `backend/tests/unit/test_admin_management_service.py` (service-level tests from §12). **Create:** `backend/tests/integration/test_admin_pricing_pipeline.py` (~25 tests) — Full pipeline tests with real DB: (1) Seed data verification — after migration, all tables populated, LLM call works with seeded config. (2) Admin creates new model, creates pricing, creates routing, verifies LLM call to new model uses correct pricing and per-model margin. (3) Effective date transition — create future pricing, verify current pricing used today, mock date forward, verify new pricing takes effect. (4) Model deactivation — deactivate model, verify LLM calls blocked with UnregisteredModelError. (5) Admin promotion flow — non-admin user cannot access admin API, promote via ADMIN_EMAILS bootstrap on login, verify admin access granted. (6) Per-model margin — cheap model with 3x margin, expensive model with 1.1x margin, verify billed costs differ despite same raw formula. (7) Routing override — change routing for a task_type, verify MeteredLLMProvider uses new model. **Run:** `pytest tests/integration/test_admin_pricing_pipeline.py -v` **Done when:** Full pipeline works end-to-end, all scenarios verified. | `tdd, db, plan` | ⬜ |
| 20 | **E2E Playwright tests for admin page + nav + auth gate** — Browser-level tests for admin functionality. **Read:** REQ-022 §11 (frontend spec), §15.4 (frontend test scenarios), `frontend/tests/e2e/usage.spec.ts` (E2E test pattern with MockController), `frontend/tests/e2e/navigation.spec.ts` (nav tests), `frontend/tests/utils/` (mock helper patterns). **Create:** `frontend/tests/fixtures/admin-mock-data.ts` (~80L) — Mock data for all admin resources (models, pricing, routing, packs, config, users). **Create:** `frontend/tests/utils/admin-api-mocks.ts` (~60L) — MockController for admin API endpoints. **Create:** `frontend/tests/e2e/admin.spec.ts` (~20 tests) — Mock API responses for all admin endpoints. Test: (1) Non-admin redirect — no adm claim in cookie, /admin/config redirects to /. (2) Admin page renders — admin cookie, page loads, all 6 tabs visible. (3) Models tab — table renders, add model form works, deactivate toggle. (4) Pricing tab — table renders, current badge shown, live cost preview updates on input change. (5) Routing tab — table renders, model dropdown populated. (6) Packs tab — table renders, add pack form. (7) System tab — inline edit works. (8) Users tab — user list, admin toggle, env-protected badge. (9) Nav — admin link visible for admin, hidden for non-admin. **Modify:** `frontend/tests/e2e/navigation.spec.ts` (~3L) — add assertion: admin link visible when admin session. **Run:** `npx playwright test admin.spec.ts navigation.spec.ts` **Done when:** All E2E tests pass, admin UI fully functional in browser tests. | `e2e, playwright, plan` | ⬜ |
| 21 | **Final gate — full test suite + push** — Run complete test suites, fix all regressions. **Run:** `pytest tests/ -v`, `npm run test:run`, `npx playwright test`. **Also:** `ruff check .`, `npm run lint`, `npm run typecheck`. **Push:** `GIT_SSH_COMMAND="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=10" git push`. **Done when:** All tests green, pushed to remote, REQ-022 implementation complete. | `plan, commands` | ⬜ |

---

## Task Count Summary

| Phase | REQ Sections | Code Tasks | Gates | Total |
|-------|-------------|------------|-------|-------|
| 1 — Database Foundation | §4, §12 | 2 | 1 | 3 |
| 2 — Admin Auth & Read Services | §5, §6, §13 | 2 | 1 | 3 |
| 3 — Backend Migration | §7, §8, §9 | 3 | 1 | 4 |
| 4 — Admin CRUD & API | §10 | 3 | 1 | 4 |
| 5 — Admin Frontend | §11 | 3 | 1 | 4 |
| 6 — Integration & Verification | §15 | 2 | 1 | 3 |
| **Total** | | **15** | **6** | **21** |

---

## Critical Files Reference

| File | Role |
|------|------|
| `docs/requirements/REQ-022_admin_pricing.md` | Full specification (19 sections, ~1770 lines) |
| `backend/app/services/metering_service.py` | Core rewrite: hardcoded pricing → DB lookups |
| `backend/app/providers/metered_provider.py` | Routing lookup + model_override pass-through |
| `backend/app/api/deps.py` | DI wiring: require_admin, AdminUser, AdminConfig, metered providers |
| `backend/app/core/auth.py` | JWT `adm` claim via `create_jwt()` |
| `backend/app/api/v1/auth.py` | Login hook: ADMIN_EMAILS bootstrap |
| `backend/app/api/v1/auth_magic_link.py` | `/auth/me` response: add `is_admin` |
| `backend/app/providers/llm/base.py` | `model_override` on abstract `complete()` |
| `frontend/src/proxy.ts` | Admin route gate (base64 JWT decode) |
| `frontend/src/components/layout/top-nav.tsx` | Conditional Admin nav link |
| `frontend/src/lib/auth-provider.tsx` | `isAdmin` on User type |

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-01 | 0.1 | Initial draft |
| 2026-03-01 | 0.2 | Saved as active plan, Phase 1 started |
