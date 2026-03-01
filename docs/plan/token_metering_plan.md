# Zentropy Scout — REQ-020 Token Metering Implementation Plan

**Created:** 2026-02-27
**Last Updated:** 2026-03-01
**Status:** ✅ Complete
**Destination:** `docs/plan/token_metering_plan.md`

---

## Context

REQ-020 and REQ-021 specify a metering and billing system. REQ-020 (this plan) adds the **metering layer** — recording every LLM/embedding call, calculating costs with margin, maintaining per-user USD balances, gating access when exhausted, and exposing usage data via API + frontend. REQ-021 (Credits & Billing) builds on top of this to add Stripe payments and will be planned separately after REQ-020 is complete.

**Why now:** All backend phases (1.1–3.2), frontend phases (1–15), and LLM redesign are complete. Token metering is the next logical step before the app can be deployed to real users — without it, there's no cost visibility, no billing foundation, and no abuse protection.

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Load the relevant REQ section via `req-reader` subagent before each task
3. Each task = one commit, sized ≤ 40k tokens of context (TDD + review + fixes included)
4. **Subtask workflow:** Run affected tests → linters → commit → compact (NO push)
5. **Phase-end workflow:** Run full test suite (backend + frontend + E2E) → push → compact
6. After each task: update status (⬜ → ✅), commit, STOP and ask user

**Workflow pattern:**

| Action | Subtask (§1–§3, §5–§9, §11, §13–§14, §16–§17) | Phase Gate (§4, §10, §12, §15, §18) |
|--------|----------------------|-------------------------------------|
| Tests | Affected files only | Full backend + frontend + E2E |
| Linters | Pre-commit hooks (~25-40s) | Pre-commit + pre-push hooks |
| Git | `git commit` only | `git push` |
| Context | Compact after commit | Compact after push |

**Why:** Pushes trigger pre-push hooks (full pytest + vitest, ~90-135s). By deferring pushes to phase boundaries, we save ~90-135s per subtask while maintaining quality gates.

**Context management for fresh sessions:** Each subtask is self-contained. A fresh context window needs:
1. This plan (find current task by status icon)
2. The REQ-020 document (via `req-reader` — load the §section listed in the task)
3. The specific files listed in the task description
4. No prior conversation history required

---

## Dependency Chain

```
Phase 1: Database Foundation (REQ-020 §4)
    │
    ↓
Phase 2: Metering Core (REQ-020 §5, §6.3)
    │
    ↓
Phase 3: Metered Providers (REQ-020 §6.2, §6.5)
    │
    ↓
Phase 4: Service Refactoring + Balance Gating (REQ-020 §2.1, §7)
    │
    ↓
Phase 5: API Endpoints (REQ-020 §8)
    │
    ↓
Phase 6: Frontend (REQ-020 §9)
    │
    ↓
Phase 7: Integration & Verification (REQ-020 §12)
```

**Ordering rationale:** Bottom-up construction. Phase 1 creates the DB schema everything depends on. Phase 2 builds the business logic (pricing, cost calculation, repositories). Phase 3 builds provider wrappers that use Phase 2's service. Phase 4 refactors existing services and wires metered providers into endpoints — depends on Phases 2-3. Phase 5 adds API endpoints that query Phase 1's tables. Phase 6 builds frontend against Phase 5's API. Phase 7 runs end-to-end integration verification.

---

## Phase 1: Database Foundation (REQ-020 §4)

**Status:** ✅ Complete

*Create SQLAlchemy models for `LLMUsageRecord` and `CreditTransaction`, add `balance_usd` column to `User`, and create the Alembic migration. No business logic yet — just schema.*

#### Tasks
| § | Task | Status |
|---|------|--------|
| 1 | **Create ORM models + Alembic migration (TDD)** — Two new models and one User column. | ✅ |

---

## Phase 2: Metering Core (REQ-020 §5, §6.3)

**Status:** ✅ Complete

*Create the pricing table, cost calculation service, config settings, and repositories for usage records and credit transactions. Pure business logic — no provider or API dependencies.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-020 §5, §6.3 |
| 🧪 **TDD** | Write tests first → code → run affected tests only |
| ✅ **Verify** | `ruff check <modified_files>`, `bandit <modified_files>` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `qa-reviewer` (parallel) |
| 📝 **Commit** | `git commit` (pre-commit hooks) |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 2 | **Create pricing table + cost calculation service (TDD)** — Hardcoded pricing dict and cost formula. **Read:** REQ-020 §5.1–§5.4 (pricing tables + formula), REQ-020 §11 (configuration), `backend/app/services/embedding_cost.py` (existing pattern for pricing constants — reuse embedding prices from here), `backend/app/core/config.py` (settings pattern). **Create:** `backend/app/services/metering_service.py` (~180L) — `MeteringService` class with `__init__(self, db: AsyncSession)`. Constants: `_LLM_PRICING: dict[tuple[str, str], dict[str, Decimal]]` mapping `(provider, model)` → `{"input_per_1k": Decimal("..."), "output_per_1k": Decimal("...")}` for 6 LLM models per REQ-020 §5.1, plus 2 embedding models per §5.2. `_FALLBACK_PRICING: dict[str, dict[str, Decimal]]` per provider (use highest tier price). Methods: `calculate_cost(provider, model, input_tokens, output_tokens) -> tuple[Decimal, Decimal]` (returns raw_cost, billed_cost using formula from §5.4), `record_and_debit(user_id, provider, model, task_type, input_tokens, output_tokens) -> None` (full pipeline: calculate cost → insert LLMUsageRecord → insert CreditTransaction with type="usage_debit" and amount=-billed_cost → atomic debit balance). Uses `UsageRepository` and `CreditRepository` from §3. **Modify:** `backend/app/core/config.py` (~4L) — add to Settings class: `metering_enabled: bool = True`, `metering_margin_multiplier: float = 1.30`, `metering_minimum_balance: float = 0.00`. **Create:** `backend/tests/unit/test_metering_service.py` (~30 tests) — Test `calculate_cost()` for each of 8 model entries (6 LLM + 2 embedding), margin applied correctly (raw × 1.30 = billed), 0-token edge case returns 0 cost, unknown model falls back to provider max price + logs warning, Decimal precision preserved (no float drift). Test `record_and_debit()` with mocked DB: inserts usage record, inserts debit transaction, calls atomic_debit, handles debit failure gracefully (logs warning, doesn't raise). **Run:** `pytest tests/unit/test_metering_service.py -v` **Done when:** All 8 pricing entries produce correct costs, margin applies, recording pipeline works. | `tdd, plan` | ✅ |
| 3 | **Create usage + credit repositories (TDD)** — DB access layer for metering tables. **Read:** REQ-020 §4, §8 (query shapes needed by API endpoints), `backend/app/repositories/user_repository.py` (stateless @staticmethod pattern), `backend/app/core/pagination.py` (PaginationParams). **Create:** `backend/app/repositories/usage_repository.py` (~120L) — `UsageRepository` with `@staticmethod` methods: `create(db, *, user_id, provider, model, task_type, input_tokens, output_tokens, raw_cost_usd, billed_cost_usd, margin_multiplier) -> LLMUsageRecord`, `list_by_user(db, user_id, *, offset=0, limit=50, task_type=None, provider=None) -> tuple[list[LLMUsageRecord], int]` (paginated + filtered + count), `get_summary(db, user_id, period_start, period_end) -> dict` (aggregates: total_calls, total_input/output_tokens, total_raw/billed_cost, by_task_type list, by_provider list — uses SQL GROUP BY). **Create:** `backend/app/repositories/credit_repository.py` (~100L) — `CreditRepository` with `@staticmethod` methods: `create(db, *, user_id, amount_usd, transaction_type, reference_id=None, description=None) -> CreditTransaction`, `list_by_user(db, user_id, *, offset=0, limit=50, transaction_type=None) -> tuple[list[CreditTransaction], int]` (paginated + filtered), `get_balance(db, user_id) -> Decimal` (reads `users.balance_usd`), `atomic_debit(db, user_id, amount: Decimal) -> bool` (SQL: `UPDATE users SET balance_usd = balance_usd - :amount WHERE id = :user_id AND balance_usd >= :amount`; returns True if rowcount > 0), `atomic_credit(db, user_id, amount: Decimal) -> Decimal` (SQL: `UPDATE users SET balance_usd = balance_usd + :amount WHERE id = :user_id RETURNING balance_usd`; returns new balance). **Create:** `backend/tests/unit/test_usage_repository.py` (~20 tests) — Integration tests with real DB (`db_session` fixture): create records, list with pagination (page 1 + page 2), filter by task_type, filter by provider, summary aggregation by task_type and provider, period filtering. **Create:** `backend/tests/unit/test_credit_repository.py` (~18 tests) — Integration tests with real DB: create credit and debit records, list with pagination, filter by transaction_type, get_balance returns correct value, atomic_debit success (sufficient balance), atomic_debit failure (insufficient — returns False, balance unchanged), atomic_credit success, verify `SUM(transactions) == users.balance_usd` invariant after multiple ops. **Run:** `pytest tests/unit/test_usage_repository.py tests/unit/test_credit_repository.py -v` **Done when:** All CRUD operations work, pagination correct, atomic debit prevents overdraft, reconciliation invariant holds. | `tdd, db, plan` | ✅ |
| 4 | **Phase gate — full test suite + push** — Run complete test suites, fix regressions. **Run:** `pytest tests/ -v`, `npm run test:run`, `npx playwright test`. **Also:** `ruff check .`, `npm run lint`, `npm run typecheck`. **Push:** `git push` (SSH keep-alive). **Done when:** All tests green, pushed to remote. | `plan, commands` | ✅ |

#### Phase 2 Notes

**Atomic debit SQL:** `UPDATE users SET balance_usd = balance_usd - :amount WHERE id = :user_id AND balance_usd >= :amount`. If 0 rows updated, balance was insufficient. Per REQ-020 §6.3 step 7, the metering service logs a warning but does NOT fail the request — the user already received the LLM response.

**Repository tests need Docker:** These tests use the `db_session` fixture (real PostgreSQL). They'll skip if Docker isn't running (`skip_if_no_postgres`). Ensure Docker is up.

---

## Phase 3: Metered Providers (REQ-020 §6.2, §6.5)

**Status:** ✅ Complete

*Add `provider_name` abstract property to all adapter classes. Create `MeteredLLMProvider` and `MeteredEmbeddingProvider` wrappers. Create FastAPI dependency functions for injecting metered providers.*

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 5 | **Add `provider_name` to all adapters (TDD)** | See full plan for details | ✅ |
| 6 | **Create MeteredLLMProvider + MeteredEmbeddingProvider + FastAPI dependencies (TDD)** | See full plan for details | ✅ |

---

## Phase 4: Service Refactoring + Balance Gating (REQ-020 §2.1, §7)

**Status:** ✅ Complete

#### Tasks
| § | Task | Status |
|---|------|--------|
| 7 | **Add InsufficientBalanceError + balance gating dependency (TDD)** | ✅ |
| 8 | **Refactor extract_job_data + wire metered providers into both endpoints (TDD)** | ✅ |
| 9 | **Refactor remaining internal services to accept provider parameter (TDD)** | ✅ |
| 10 | **Phase gate — full test suite + push** | ✅ |

---

## Phase 5: API Endpoints (REQ-020 §8)

**Status:** ✅ Complete

#### Tasks
| § | Task | Status |
|---|------|--------|
| 11 | **Create usage schemas + 4 API endpoints + router registration (TDD)** | ✅ |
| 12 | **Phase gate — full test suite + push** | ✅ |

---

## Phase 6: Frontend (REQ-020 §9)

**Status:** ✅ Complete

#### Tasks
| § | Task | Status |
|---|------|--------|
| 13 | **Add balance display to top nav + 402 handling (TDD)** | ✅ |
| 14 | **Create usage dashboard page (TDD)** | ✅ |
| 15 | **Phase gate — full test suite + push** | ✅ |

---

## Phase 7: Integration & Verification (REQ-020 §12)

**Status:** ✅ Complete

#### Tasks
| § | Task | Status |
|---|------|--------|
| 16 | **Backend integration tests for full metering pipeline** | ✅ |
| 17 | **E2E Playwright tests for usage page + nav balance** — **Read:** REQ-020 §9, `frontend/tests/e2e/navigation.spec.ts`, `frontend/tests/e2e/settings.spec.ts`. **Create:** `frontend/tests/e2e/usage.spec.ts` (~15 tests) — mock API responses for balance/summary/history/transactions. Test: balance in nav, color coding, click → /usage, page renders all sections, pagination, 402 toast. **Modify:** `frontend/tests/e2e/navigation.spec.ts` (~3L) — assert balance indicator visible. **Run:** `npx playwright test usage.spec.ts navigation.spec.ts` **Done when:** All E2E tests pass. | ✅ |
| 17.1 | **Audit SonarCloud + Semgrep suppression history** — Review all `# noqa`, `# nosec`, `# type: ignore`, Semgrep `nosemgrep` comments, and SonarCloud accepted/dismissed findings across the entire codebase. For each suppression: verify the justification is still valid, check whether the underlying issue has been fixed (making the suppression stale), and investigate whether any were added as lazy bypasses rather than genuine exceptions. Fix any findings that can be resolved; remove stale suppressions. Update security-triage baseline if counts change. **Run:** `grep -rn "noqa\|nosec\|nosemgrep\|type: ignore" backend/ frontend/` + review SonarCloud dismissed history via API. **Done when:** Every suppression has a verified justification or has been removed/fixed. | ✅ |
| 18 | **Final gate — full test suite + push** | ✅ |

---

## Task Count Summary

| Phase | REQ Sections | Code Tasks | Gates | Total |
|-------|-------------|------------|-------|-------|
| 1 — Database Foundation | §4 | 1 | 0 | 1 |
| 2 — Metering Core | §5, §6.3 | 2 | 1 | 3 |
| 3 — Metered Providers | §6.2, §6.5 | 2 | 0 | 2 |
| 4 — Service Refactoring | §2.1, §7 | 3 | 1 | 4 |
| 5 — API Endpoints | §8 | 1 | 1 | 2 |
| 6 — Frontend | §9 | 2 | 1 | 3 |
| 7 — Integration | §12 | 3 | 1 | 4 |
| **Total** | | **14** | **5** | **19** |

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-27 | 0.1 | Initial draft |
| 2026-02-27 | 0.2 | Phase 1 §1 complete — models, migration, 30 tests |
| 2026-02-28 | 0.3 | Phase 2 §2 complete — metering service, pricing table, config, 30 tests |
| 2026-02-28 | 0.4 | Phase 2 §3 complete — usage + credit repositories, 40 tests |
| 2026-02-28 | 0.5 | Phase 2 §4 gate — 3977 backend + 3261 frontend + 213 E2E tests pass, ESLint coverage ignore fix |
| 2026-02-28 | 0.6 | Phase 3 §5 complete — provider_name abstract property on all adapters, 11 tests |
| 2026-02-28 | 0.7 | Phase 3 §6 complete — MeteredLLMProvider + MeteredEmbeddingProvider + DI deps, 23 tests |
| 2026-02-28 | 0.8 | Phase 4 §7 complete — InsufficientBalanceError + balance gating dependency, 16 tests |
| 2026-02-28 | 0.9 | Phase 4 §8 complete — extract_job_data refactor + metered providers in both endpoints, 2 new 402 tests |
| 2026-02-28 | 1.0 | Phase 4 §9 complete — all internal services accept provider parameter, backward compat preserved |
| 2026-02-28 | 1.1 | Phase 4 §10 gate — 4029 backend + 3261 frontend + 213 E2E tests pass, S3776 fix, 1 test assertion fix |
| 2026-02-28 | 1.2 | Phase 5 §11 complete — usage schemas, 4 API endpoints, router registration, 26 tests |
| 2026-03-01 | 1.3 | Phase 5 §12 gate — 4055 backend + 3261 frontend + 213 E2E tests pass |
| 2026-03-01 | 1.4 | Phase 6 §13 — Balance display in top nav + 402 toast handling |
| 2026-03-01 | 1.5 | Phase 6 §14 complete — Usage dashboard page, 6 components, shared format-utils, 40 tests |
| 2026-03-01 | 1.6 | Phase 6 §15 gate — 4055 backend + 3319 frontend + 213 E2E tests pass, app-shell useBalance mock fix |
| 2026-03-01 | 1.7 | Phase 7 §16 complete — 19 integration tests for full metering pipeline |
| 2026-03-01 | 1.8 | Phase 7 §17 complete — 17 E2E tests for usage page + nav balance, 1 nav balance test, 2 flaky test fixes |
| 2026-03-01 | 1.9 | Phase 7 §18 gate — 4073 backend + 3319 frontend + 226 E2E tests pass, all lints clean |
