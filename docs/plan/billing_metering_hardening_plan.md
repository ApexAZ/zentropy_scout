# Zentropy Scout — REQ-030 Billing & Metering Hardening Implementation Plan

**Created:** 2026-03-27
**Last Updated:** 2026-03-28
**Status:** 🟡 In Progress (Phase 7 added 2026-03-28)
**Branch:** `feat/billing-metering-hardening`
**Backlog Item:** #29

---

## Context

REQ-030 specifies hardening of the billing/metering/Stripe stack based on a steelman security review that identified 13 findings across 4 tiers. The core architectural change is replacing the post-debit fire-and-forget metering pattern with a **pre-debit reservation pattern**. All prerequisites (REQ-020, REQ-022, REQ-023, REQ-029) are complete. REQ-030 and forward references to REQ-020/021/029 are already committed.

**What gets built:**
- **Database:** `usage_reservations` table, `users.held_balance_usd` column, type alignment on `stripe_purchases`/`funding_packs`, `expired` status on `stripe_purchases`
- **Metering pipeline:** `MeteringService.reserve()`, `settle()`, `release()` replacing `record_and_debit()`. `MeteredLLMProvider.complete()` rewritten to reserve→call→settle pattern.
- **Webhook hardening:** Refund handler savepoint + cap + null guard. New `checkout.session.expired` handler.
- **Quick fixes:** Config validation, display rounding, frontend query invalidation, CLAUDE.md docs, type consistency.
- **Background sweep:** Stale reservation cleanup + balance/ledger drift detection.

**What doesn't change:** Stripe checkout flow, signup grants, admin pricing dashboard, credit transaction ledger structure, existing API endpoint contracts.

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Load REQ-030 via `req-reader` subagent before each task (load the §sections listed)
3. Each task = one commit, sized ≤ 40k tokens of context (TDD + review + fixes included)
4. **Subtask workflow:** Run affected tests → linters → commit → STOP and ask user (NO push)
5. **Phase-end workflow:** Run full test suite (backend + frontend + E2E) → push → STOP and ask user
6. After each task: update status (⬜ → ✅), commit, STOP and ask user

---

## Dependency Chain

```
Phase 1: Database & Foundation (Migration + Models + Config)
    │
    ▼
Phase 2: Reservation Pipeline (reserve/settle/release + Provider Rewrite)
    │
    ▼
Phase 3: Webhook & Stripe Hardening (Refund fixes + Expired handler + Customer savepoint)
    │     (independent of Phase 2 — but ordered after Phase 1 for migration)
    ▼
Phase 4: Quick Fixes & Frontend (Display, config, docs, query invalidation)
    │     (independent — small fixes, low risk)
    ▼
Phase 5: Background Reconciliation (Stale sweep + Drift detection)
    │     (depends on Phase 2 — reservation pipeline must be working)
    ▼
Phase 6: Integration Testing & Polish
    │
    ▼
Phase 7: Post-Audit Hardening (12 findings from adversarial red-team audit)
```

**Ordering rationale:** Phase 1 is the migration — everything else depends on the new columns/tables existing. Phase 2 is the core architectural change (reservation pipeline). Phase 3 is webhook hardening (independent of reservation but needs the migration for `expired` status). Phase 4 is quick fixes that can land anytime after Phase 1. Phase 5 is the background sweep (needs the reservation pipeline from Phase 2). Phase 6 is integration testing across all changes.

---

## Phase 1: Database & Foundation

**Status:** ✅ Complete

*Add the `held_balance_usd` column, `usage_reservations` table, type alignment fixes, `expired` status, and new config variables. This is additive and doesn't break existing code.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-030 §4 (Database Schema), §9.2 (Config Variables) |
| 🧪 **TDD** | Write migration tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-db` for migrations, `zentropy-api` for config |
| ✅ **Verify** | `pytest -v` affected tests, lint, typecheck |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** — Skipped per user (other agent addressing findings). | `plan, security` | ✅ |
| 2 | **UsageReservation ORM model** — Create `backend/app/models/usage_reservation.py` with the `UsageReservation` model matching REQ-030 §4.2 schema. Include all columns, check constraints, and indexes. Add `held_balance_usd` column to User model (`backend/app/models/user.py`). Add `'expired'` to StripePurchase status constraint (`backend/app/models/stripe.py`). | `plan, tdd, db` | ✅ |
| | **Read:** REQ-030 §4.1 (users amendment), §4.2 (usage_reservations), §4.3 (type alignment), §7.3 (expired status). Read `backend/app/models/user.py`, `backend/app/models/usage.py` (existing patterns), `backend/app/models/stripe.py`. | `req-reader` | |
| | **TDD:** Write tests for model instantiation, constraint validation (status values, positive estimated_cost, non-negative actual_cost), held_balance_usd default. | | |
| | **Done when:** Models importable, constraints match REQ-030 §4.2 exactly. | | |
| 3 | **Alembic migration 028** — Create `backend/migrations/versions/028_billing_hardening.py`. Add `held_balance_usd` to `users`, create `usage_reservations` table with indexes, alter `grant_cents` BIGINT→INTEGER on `stripe_purchases` and `funding_packs`, update `stripe_purchases` status constraint to include `'expired'`. Test upgrade AND downgrade. | `plan, tdd, db, commands` | ✅ |
| | **Read:** REQ-030 §4.4 (migration spec). Read `backend/migrations/versions/027_stripe_payment_intent_index.py` (revision chain). | `req-reader` | |
| | **TDD:** Write migration test verifying upgrade creates columns/table, downgrade removes them. Verify `grant_cents` type changes. Verify constraint includes `expired`. | | |
| | **Run:** `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` | | |
| | **Done when:** Migration applies cleanly, all columns/tables/indexes exist, downgrade works. | | |
| 4 | **Config variables for reservation system** — Add `reservation_ttl_seconds` and `reservation_sweep_interval_seconds` to Settings class. Reject `credits_enabled + !metering_enabled` in production (upgrade from warning to ValueError). | `plan, tdd, security` | ✅ |
| | **Read:** REQ-030 §9.1 (config rejection), §9.2 (new variables). Read `backend/app/core/config.py` (existing Settings, check_production_security). Read `backend/tests/unit/test_core_config_stripe.py` (existing config tests). | `req-reader` | |
| | **TDD:** Test new vars load with defaults. Test production rejection of credits+!metering. Test non-production still warns (not raises). | | |
| | **Done when:** Config vars load, production check raises, dev check warns. | | |
| 5 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright + lint + typecheck). Fix regressions, commit, push. | `plan, commands` | ✅ |

#### Phase 1 Notes

- The migration is additive — existing code continues to work unchanged
- The `grant_cents` type change (BIGINT→INTEGER) is a narrowing change; verify no data exceeds INTEGER range before applying in production (current seed data: 500, 1000, 1500 — well within range)
- The `expired` status addition to the constraint requires dropping and recreating the constraint in the migration

---

## Phase 2: Reservation Pipeline

**Status:** ✅ Complete

*Implement the core reserve→call→settle pattern. This is the biggest behavioral change — replaces the fire-and-forget post-debit metering with pre-debit reservations.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-030 §5 (Reservation Pipeline), §6 (Balance Gating) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-tdd` for mocking, `zentropy-provider` for LLM patterns |
| ✅ **Verify** | `pytest -v` affected tests, lint, typecheck |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 6 | **Security triage gate** — Skipped per user (other agent addressing findings). | `plan, security` | ✅ |
| 7 | **MeteringService.reserve()** — Add the `reserve()` method to `backend/app/services/metering_service.py`. Resolves routing, looks up pricing, calculates estimated cost from `max_tokens × output_price`, inserts `UsageReservation`, increments `held_balance_usd`. | `plan, tdd, provider` | ✅ |
| | **Read:** REQ-030 §5.2 (reserve spec), §2.3 (estimation formula). Read `backend/app/services/metering_service.py` (current class), `backend/app/services/admin_config_service.py` (pricing/routing lookups). | `req-reader` | |
| | **TDD:** Test happy path (reservation created, held_balance incremented). Test pricing lookup failure propagates (no reservation created). Test max_tokens=None uses default. Test estimated cost calculation matches formula. | | |
| | **Done when:** `reserve()` creates reservation, increments held balance, returns UsageReservation. Pricing errors propagate. | | |
| 8 | **MeteringService.settle() + release()** — Add `settle()` (wraps all recording in savepoint) and `release()` (decrements held balance on LLM failure) to `backend/app/services/metering_service.py`. | `plan, tdd, security` | ✅ |
| | **Read:** REQ-030 §5.3 (settle spec), §5.5 (release spec). Read existing `record_and_debit()` in `metering_service.py` (being replaced). | `req-reader` | |
| | **TDD:** Test settle happy path (usage record + credit transaction + balance debit + held release + reservation settled). Test settle savepoint rollback on failure (reservation stays held = fail-closed). Test release happy path (held decremented, status=released). Test release failure logged (hold stays). | | |
| | **Done when:** `settle()` atomically records + debits + releases hold. `release()` restores held balance. Both handle errors gracefully. | | |
| 9 | **MeteredLLMProvider.complete() rewrite** — Rewrite `complete()` in `backend/app/providers/metered_provider.py` to use reserve→call→settle pattern. Remove the double `except Exception`. Add stream() warning for metering gap. | `plan, tdd, provider, security` | ✅ |
| | **Read:** REQ-030 §5.4 (complete rewrite), §5.6 (stream warning). Read `backend/app/providers/metered_provider.py` (current complete/stream). Read `backend/tests/unit/test_metered_provider.py` (existing tests to update). | `req-reader` | |
| | **TDD:** Test reserve→call→settle happy path. Test reserve→call fails→release path (user not charged). Test reserve fails→no LLM call (error propagates). Test stream() logs warning when metering enabled. Update existing metered_provider tests for new behavior. | | |
| | **Done when:** `complete()` uses reservation pattern. Double `except Exception` eliminated. `stream()` logs warning. All existing tests updated and passing. | | |
| 10 | **MeteredEmbeddingProvider.embed() rewrite** — Adapt `embed()` in `backend/app/providers/metered_provider.py` to use reserve→embed→settle pattern with token estimation heuristic. | `plan, tdd, provider` | ✅ |
| | **Read:** REQ-030 §5.7 (embedding provider). Read existing `embed()` in `metered_provider.py`. | `req-reader` | |
| | **TDD:** Test reserve→embed→settle flow. Test token estimation (sum(len)/4). Test release on embed failure. | | |
| | **Done when:** `embed()` uses reservation pattern. Estimation uses existing heuristic. | | |
| 11 | **Balance gating: available balance** — Update `require_sufficient_balance` in `backend/app/api/deps.py` to check `balance_usd - held_balance_usd > threshold`. Update `InsufficientBalanceError` to report available balance. | `plan, tdd, security` | ✅ |
| | **Read:** REQ-030 §6.1 (available balance formula). Read `backend/app/api/deps.py` lines 306-346. Read `backend/tests/unit/test_balance_gating.py`. | `req-reader` | |
| | **TDD:** Test available balance = balance - held. Test held balance reduces available. Test zero held balance unchanged from current behavior. Update existing gating tests. | | |
| | **Done when:** Balance check uses available balance. Existing gating tests updated and passing. | | |
| 12 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright + lint + typecheck). Fix regressions, commit, push. | `plan, commands` | ✅ |

#### Phase 2 Notes

- This is the highest-risk phase — the metering pipeline touches every LLM call
- The `record_and_debit()` method should be removed after all callers are switched (REQ-030 §16 Q1 recommends removal)
- Existing tests in `test_metered_provider.py`, `test_metering_integration.py`, and `test_balance_gating.py` will need updates to reflect the new reserve→settle flow
- The `get_metered_provider` dependency in `deps.py` may need to pass additional context (max_tokens default) — verify during implementation

---

## Phase 3: Webhook & Stripe Hardening

**Status:** ✅ Complete

*Harden the webhook handlers and Stripe service. These fixes are independent of the reservation pipeline but need the migration from Phase 1 (for `expired` status).*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-030 §7 (Webhook Hardening), §8 (Stripe Service) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-tdd` for mocking, `zentropy-api` for endpoints |
| ✅ **Verify** | `pytest -v` affected tests, lint, typecheck |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 13 | **Security triage gate** — Skipped per user (other agent addressing findings). | `plan, security` | ✅ |
| 14 | **Refund handler: savepoint + cap + null guard** — Wrap `_process_charge_refunded()` operations in `begin_nested()`. Cap `total_refunded_cents` at `purchase.amount_cents`. Guard against null `payment_intent`. Three changes in `backend/app/services/stripe_webhook_service.py`. | `plan, tdd, security` | ✅ |
| | **Read:** REQ-030 §7.2a (savepoint), §7.2b (cap), §7.2c (null guard). Read `backend/app/services/stripe_webhook_service.py` (current refund handler). Read `backend/tests/unit/test_stripe_webhook_refund.py` (existing tests). | `req-reader` | |
| | **TDD:** Test savepoint rolls back on partial failure (no orphaned credit txn). Test refund capped at amount_cents. Test null payment_intent returns early with log. Update existing refund tests. | | |
| | **Done when:** Refund handler is atomic (savepoint), caps refunds, guards against null PI. | | |
| 15 | **checkout.session.expired handler** — Add `handle_checkout_expired` to `stripe_webhook_service.py`, `mark_expired` to `stripe_repository.py`, wire into webhook router `match` statement. | `plan, tdd, api` | ✅ |
| | **Read:** REQ-030 §7.3 (expired handler). Read `backend/app/api/v1/webhooks.py` (router), `backend/app/repositories/stripe_repository.py` (existing mark_* methods). | `req-reader` | |
| | **TDD:** Test expired event transitions pending→expired. Test non-pending purchase is no-op. Test webhook routes to handler. | | |
| | **Done when:** Expired sessions transition to `expired` status. No balance changes. | | |
| 16 | **get_or_create_customer savepoint fix** — Replace `db.rollback()` with `db.begin_nested()` savepoint in `backend/app/services/stripe_service.py`. | `plan, tdd, security` | ✅ |
| | **Read:** REQ-030 §8.1 (savepoint fix). Read `backend/app/services/stripe_service.py` lines 112-124. Read `backend/tests/unit/test_stripe_service.py`. | `req-reader` | |
| | **TDD:** Test IntegrityError only rolls back the savepoint (not entire session). Test winner's customer ID is returned on race. | | |
| | **Done when:** Race condition uses savepoint instead of full rollback. | | |
| 17 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright + lint + typecheck). Fix regressions, commit, push. | `plan, commands` | ✅ |

#### Phase 3 Notes

- F-03/F-04/F-05 are all in the same function (`_process_charge_refunded`) — combined into one task (§14) for atomicity, but still three distinct changes with separate test cases
- The `mark_expired` repository method follows the exact same pattern as `mark_completed` and `mark_refunded` — reference those for consistency
- The `get_or_create_customer` fix is small but touches payment-critical code — security review is important

---

## Phase 4: Quick Fixes & Frontend

**Status:** ✅ Complete

*Small, independent fixes: display rounding, frontend query invalidation, CLAUDE.md docs. Low risk, can land anytime after Phase 1.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-030 §10 (Display & Consistency Fixes) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-tdd` for backend, `zentropy-lint` for frontend |
| ✅ **Verify** | `pytest -v` + `npm test`, lint, typecheck |
| 🔍 **Review** | Use `code-reviewer` + `ui-reviewer` (for frontend task) |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 18 | **Purchase display rounding fix** — Change `int()` to `int(round())` in `backend/app/api/v1/credits.py` line 184. Fix F-08 (int truncation). | `plan, tdd` | ✅ |
| | **Read:** REQ-030 §10.1. Read `backend/app/api/v1/credits.py` (purchase history endpoint). Read `backend/tests/unit/test_credits_api.py`. | `req-reader` | |
| | **TDD:** Test that sub-cent amounts round correctly (e.g., Decimal("4.999") → 5 cents, not 4). | | |
| | **Done when:** `format_usd_display` receives correctly rounded cents. | | |
| 19 | **Frontend: invalidate purchases on checkout success + CLAUDE.md docs fix** — Add `queryKeys.purchases` invalidation in `frontend/src/components/usage/usage-page.tsx`. Fix CLAUDE.md error hierarchy (`ZentropyError` → `APIError`). | `plan, tdd, ui` | ✅ |
| | **Read:** REQ-030 §10.2 (query invalidation), §10.3 (CLAUDE.md). Read `frontend/src/components/usage/usage-page.tsx` (StripeRedirectHandler). Read CLAUDE.md error handling section. | `req-reader` | |
| | **TDD:** Update frontend test to verify purchases query is invalidated on success redirect. | | |
| | **Done when:** Checkout success invalidates both balance and purchases. CLAUDE.md matches code. | | |
| 20 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright + lint + typecheck). Fix regressions, commit, push. | `plan, commands` | ✅ |

#### Phase 4 Notes

- These are all one-line or few-line changes — low risk, high confidence
- §19 combines a frontend fix with a docs fix because both are trivial and don't warrant separate commits
- The `ui-reviewer` should verify the checkout redirect behavior hasn't regressed

---

## Phase 5: Background Reconciliation

**Status:** ✅ Complete

*Add the stale reservation sweep and balance/ledger drift detection. Depends on Phase 2 (reservation pipeline must exist).*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-030 §11 (Background Reconciliation) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-tdd` for mocking, `zentropy-api` for lifespan |
| ✅ **Verify** | `pytest -v` affected tests, lint, typecheck |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 21 | **Security triage gate** — Skipped per user (other agent addressing findings). | `plan, security` | ✅ |
| 22 | **Stale reservation sweep** — Implement `sweep_stale_reservations()` function in a new `backend/app/services/reservation_sweep.py`. Wire into FastAPI lifespan event with configurable interval. | `plan, tdd, security` | ✅ |
| | **Read:** REQ-030 §11.1 (sweep spec), §2.4 (stale handling design). Read `backend/app/main.py` (existing lifespan events). | `req-reader` | |
| | **TDD:** Test sweep releases stale reservations (status→stale, held_balance decremented). Test sweep ignores non-held and recent reservations. Test configurable TTL. | | |
| | **Done when:** Sweep runs on interval, releases stale holds, logs warnings. | | |
| 23 | **Balance/ledger drift detection** — Implement drift detection query as a function in `reservation_sweep.py` (runs alongside sweep). Log any drift at error level. | `plan, tdd, db` | ✅ |
| | **Read:** REQ-030 §11.2 (drift detection). | `req-reader` | |
| | **TDD:** Test drift detection finds mismatches. Test no drift returns clean. | | |
| | **Done when:** Drift check runs, logs errors on mismatch, returns clean on match. | | |
| 24 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright + lint + typecheck). Fix regressions, commit, push. | `plan, commands` | ✅ |

#### Phase 5 Notes

- The sweep should be careful about transaction boundaries — each stale reservation release should be atomic
- The drift detection is diagnostic only (logging, not corrective) — it detects problems but doesn't fix them
- Consider adding a `RESERVATION_SWEEP_ENABLED` toggle for testing environments

---

## Phase 6: Integration Testing & Polish

**Status:** ✅ Complete

*End-to-end integration tests across the full hardened pipeline. Verify all 13 findings are resolved. Final quality gate.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-030 §15 (Testing Requirements) |
| 🧪 **TDD** | Write integration tests — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-tdd` for integration patterns |
| ✅ **Verify** | Full test suite, lint, typecheck |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 25 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). | `plan, security` | ✅ |
| 26 | **Integration tests: reservation lifecycle** — Write integration tests covering: reserve→settle happy path, reserve→release on failure, concurrent reservations, ledger integrity after full cycle. Use real async DB with transaction fixtures. | `plan, tdd, db` | ✅ |
| | **Read:** REQ-030 §15.2 (integration test scenarios). Read `backend/tests/integration/test_admin_pricing_pipeline.py` (existing integration test pattern). | `req-reader` | |
| | **Done when:** All 7 integration test scenarios from §15.2 are covered and passing. | | |
| 27 | **Integration tests: webhook hardening** — Write integration tests for: refund savepoint rollback, expired checkout transition, concurrent customer creation. | `plan, tdd, security` | ✅ |
| | **Read:** REQ-030 §15.2 (refund + expired scenarios). Read `backend/tests/unit/test_stripe_webhook_checkout.py` (existing pattern). | `req-reader` | |
| | **Done when:** Refund atomicity, expired transition, and customer race all verified. | | |
| 28 | **Findings verification audit** — Cross-check all 13 findings from REQ-030 §1.5 against the implementation. Verify each finding has tests, code changes, and passes. Document verification in this plan. | `plan, security` | ✅ |
| | **Read:** REQ-030 §1.5 (findings register), §13 (security considerations). | `req-reader` | |
| | **Done when:** All 13 findings verified resolved with test coverage. | | |
| 29 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright + lint + typecheck). Fix regressions, commit, push. Final push for the feature branch. | `plan, commands` | ✅ |

#### Phase 6 Notes

- §28 (findings audit) is a verification task — read each finding, confirm the code change exists, confirm a test covers it
- After §29, the feature branch is ready for PR review
- Consider running the security-triage subagent one final time as part of §25 to ensure no new scanner findings

#### §28 Findings Verification Audit (2026-03-28)

All 13 findings from REQ-030 §1.5 verified resolved with code changes and test coverage:

| ID | Title | Code Location | Tests | Status |
|----|-------|---------------|-------|--------|
| F-01 | Ledger/balance drift — savepoint in settle() | `metering_service.py:222-283` (begin_nested) | `test_metering_service.py::TestSettle` — 7 tests (savepoint, failure stays held, pricing failure) | ✅ |
| F-02 | Fail-open metering — reserve→call→settle | `metered_provider.py:144-178` (no bare except swallowing) | `test_metered_provider.py::TestMeteredLLMProviderComplete` — 5 tests + integration | ✅ |
| F-03 | Refund savepoint — begin_nested() wraps 3 ops | `stripe_webhook_service.py:216` (begin_nested) | `test_stripe_webhook_refund_hardening.py::TestRefundSavepointAtomicity` + integration | ✅ |
| F-04 | Refund cap — min() limits debit | `stripe_webhook_service.py:203` (min cap) | `test_stripe_webhook_refund_hardening.py::TestRefundCap` — 2 tests | ✅ |
| F-05 | Null payment_intent guard | `stripe_webhook_service.py:180-186` (early return) | `test_stripe_webhook_refund_hardening.py::TestNullPaymentIntentGuard` — 2 tests | ✅ |
| F-06 | Config rejects credits+!metering in prod | `config.py:171-182` (ValueError in production) | `test_core_config_stripe.py::TestStripeConfigMatrix` — 2 tests | ✅ |
| F-07 | Expired checkout handler | `webhooks.py:67-68`, `stripe_webhook_service.py:128-143`, `stripe_repository.py:180-208`, `stripe.py:69` | `test_stripe_webhook_expired.py` — 4 tests + integration | ✅ |
| F-08 | round() replaces int() truncation | `credits.py:185` (int(round(...))) | `test_credits_api.py::test_sub_cent_amount_rounds_correctly` | ✅ |
| F-09 | Frontend purchases query invalidation | `usage-page.tsx:64-65` | `usage-page.test.tsx` — 2 tests | ✅ |
| F-10 | stream() warning for unmetered usage | `metered_provider.py:205-209` (warning log) | `test_metered_provider.py::TestMeteredLLMProviderStream` — 2 tests | ✅ |
| F-11 | Customer creation savepoint | `stripe_service.py:113-122` (begin_nested) | `test_stripe_service.py` — 3 tests + integration | ✅ |
| F-12 | grant_cents BIGINT→INTEGER alignment | `stripe.py:105-112`, migration `028:128-141` | `test_migration_028.py` — 4 tests (upgrade + downgrade) | ✅ |
| F-13 | CLAUDE.md error hierarchy updated | `CLAUDE.md:129-138` (APIError, not ZentropyError) | Documentation only — no tests needed | ✅ |

**Integration test coverage (Phase 6, §26-§27):**
- `test_reservation_lifecycle.py` — reserve→settle, reserve→release (F-01, F-02)
- `test_reservation_advanced.py` — concurrent reservations, stale sweep, ledger integrity (F-01, F-02)
- `test_webhook_hardening.py` — refund savepoint, expired transition, customer creation savepoint (F-03, F-07, F-11)

---

## Phase 7: Post-Audit Hardening

**Status:** ⬜ Incomplete

*Addresses 12 findings from a comprehensive adversarial red-team audit conducted 2026-03-28 after PR #61 merged. The audit traced every balance modification path, reviewed all 42 changed files, and launched parallel security, code, and codebase exploration agents. Findings range from HIGH (race conditions, missing balance guards) to LOW (documentation, config types). Ordered by severity — HIGH items first.*

#### Audit Context

The audit was conducted with zero-trust posture across the full billing/metering data path:
- **Security reviewer:** Investigated 12 attack vectors (race conditions, negative balance, webhook replay, savepoint correctness, decimal overflow, config bypass, stream gap, dead code)
- **Code reviewer:** Checked 16 production files for correctness, convention compliance, and edge cases
- **Explore agents:** Traced all callers of `record_and_debit()`, mapped all 11 balance modification points, assessed stream metering gap exposure
- **Result:** 12 findings (3 HIGH, 4 MEDIUM, 5 LOW)

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Re-read audit findings in this phase's context section for each task |
| 🧪 **TDD** | Write failing test first for each fix — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-tdd` for mocking, `zentropy-db` for SQL patterns |
| ✅ **Verify** | `pytest -v` affected tests, lint, typecheck |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 30 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). Verdicts: CLEAR → mark complete, proceed. VULNERABLE → fix immediately. FALSE POSITIVE → complete full PROSECUTION PROTOCOL before dismissing. NEEDS INVESTIGATION → escalate to user via AskUserQuestion. | `plan, security` | ✅ |
| 31 | **[HIGH] Fix settle/sweep race — conditional SQL UPDATE in settle() (AF-01)** — Replace ORM attribute assignment in `MeteringService.settle()` (lines 278-282) with a conditional SQL `UPDATE usage_reservations SET status = 'settled' ... WHERE id = :id AND status = 'held'`. If `rowcount == 0`, the sweep already handled the reservation — abort cleanly (return without error). This eliminates the race where sweep marks a reservation 'stale' but settle overwrites it back to 'settled', causing double-decrement of `held_balance_usd` and a free LLM call. Also update `release()` with the same conditional pattern for consistency. | `plan, tdd, security` | ⬜ |
| | **Read:** `backend/app/services/metering_service.py` (settle at 190-290, release at 292-339). `backend/app/services/reservation_sweep.py` (sweep at 35-119, conditional UPDATE at 74-79). | | |
| | **TDD:** Test that settle returns cleanly when reservation is already stale (rowcount=0). Test that settle still works for normal held→settled. Test that release returns cleanly when reservation is already settled/stale. Test concurrent settle+sweep scenario cannot double-decrement held_balance_usd. | | |
| | **Done when:** settle() and release() use conditional SQL UPDATE. No ORM attribute assignment for status changes. Race is impossible by construction. | | |
| 32 | **[HIGH] Add balance overdraft protection to settle() (AF-02)** — The settle() UPDATE at line 263 does `balance_usd = balance_usd - :actual` with no floor check. There is NO CHECK constraint on `balance_usd >= 0` (only `held_balance_usd` has one). Concurrent requests can drive balance negative through settlement. Add `RETURNING balance_usd` to the settle UPDATE and log at ERROR level if the new balance is negative (overdraft via usage, distinct from intentional negative via refund). Consider adding a DB CHECK constraint `balance_usd >= -<overdraft_limit>` as a hard cap. | `plan, tdd, security, db` | ⬜ |
| | **Read:** `backend/app/services/metering_service.py` (settle UPDATE at 263-275). `backend/app/models/user.py` (no CHECK on balance_usd). `backend/app/repositories/credit_repository.py` (atomic_debit has WHERE clause at 207-208, atomic_refund_debit intentionally allows negative at 273-278). `backend/app/api/deps.py` (soft gate at 306-352). | | |
| | **TDD:** Test settle logs error when balance goes negative. Test that the usage record is still created (service was already consumed). Test that the overdraft alert includes user_id, reservation_id, and amount. | | |
| | **Done when:** Overdraft is detected and logged at ERROR. Usage is still recorded (fail-forward for consumed service). Alert enables operator investigation. | | |
| 33 | **[MEDIUM] Include input token cost in reserve() estimation (AF-03)** — The reservation formula (`max_tokens / 1000 * output_per_1k * margin`) ignores input tokens. For large-prompt scenarios, `actual_cost >> estimated_cost`, making the soft gate ineffective. Add an input token ceiling to the estimate: `estimated = (input_ceiling * input_per_1k + max_tokens * output_per_1k) / 1000 * margin`. Use a configurable default input ceiling (e.g., 4096). | `plan, tdd, provider` | ⬜ |
| | **Read:** `backend/app/services/metering_service.py` (reserve at 118-188, cost formula at 155-156). `backend/app/core/config.py` (existing reservation config vars). | | |
| | **TDD:** Test that estimated cost now includes input component. Test that zero input_per_1k still works (output-only pricing). Test default input ceiling is used when not specified. | | |
| | **Done when:** Reserve() produces estimates that include both input and output cost components. Over-estimation is still preferred over under-estimation. | | |
| 34 | **[MEDIUM] Remove dead record_and_debit() method and tests (AF-04)** — `record_and_debit()` is the legacy fire-and-forget pattern superseded by reserve/settle/release. Zero production callers confirmed by codebase search. Remove the method from `MeteringService`, the `TestRecordAndDebit` class from `test_metering_service.py` (11 tests), and 4 calls from `test_admin_pricing_pipeline.py`. Replace integration test calls with reserve/settle pattern tests. | `plan, tdd` | ⬜ |
| | **Read:** `backend/app/services/metering_service.py` (record_and_debit at 341-429). `backend/tests/unit/test_metering_service.py` (TestRecordAndDebit at ~238-386). `backend/tests/integration/test_admin_pricing_pipeline.py` (4 calls at 369, 405, 429, 626). | | |
| | **TDD:** Verify no import errors after removal. Verify remaining tests still pass. Update integration tests to use reserve/settle instead of record_and_debit. | | |
| | **Done when:** record_and_debit() removed. All tests updated to use reservation pipeline. No dead code remains. | | |
| 35 | **[MEDIUM] Guard zero-cost reservation in reserve() (AF-05)** — `PricingConfig` allows `output_cost_per_1k >= 0` but `UsageReservation` requires `estimated_cost_usd > 0`. If an admin configures a model with zero output cost, `reserve()` produces `estimated_cost = 0`, causing `IntegrityError` on flush. Add a floor: `estimated_cost = max(estimated_cost, Decimal("0.000001"))`. | `plan, tdd, db` | ⬜ |
| | **Read:** `backend/app/services/metering_service.py` (reserve at 155-156). `backend/app/models/admin_config.py` (PricingConfig constraints, output_cost_per_1k at ~119). `backend/app/models/usage_reservation.py` (ck_reservation_estimated_positive). | | |
| | **TDD:** Test that zero-priced model produces minimum estimated cost, not IntegrityError. Test that normal pricing is unchanged. | | |
| | **Done when:** reserve() never produces zero estimated cost. Floor is documented. | | |
| 36 | **[MEDIUM] Move mark_completed inside savepoint in checkout handler (AF-06)** — In `handle_checkout_completed`, the savepoint wraps `CreditRepository.create` + `atomic_credit` (lines 101-111), but `mark_completed` (line 114) is outside. If mark_completed fails, the user is credited but the purchase stays "pending." Move mark_completed inside the savepoint for full atomicity. | `plan, tdd, security` | ⬜ |
| | **Read:** `backend/app/services/stripe_webhook_service.py` (handle_checkout_completed at 24-125). `backend/app/repositories/stripe_repository.py` (mark_completed). | | |
| | **TDD:** Test that mark_completed failure rolls back the credit. Test that happy path still credits AND marks completed. | | |
| | **Done when:** Credit + balance update + purchase status update are all atomic within one savepoint. | | |
| 37 | **[MEDIUM] Narrow settle() and release() exception handling (AF-07)** — Both methods use bare `except Exception` catch-all (lines 284, 333), swallowing programming errors (`TypeError`, `AttributeError`) alongside expected DB errors. Narrow to `except (SQLAlchemyError, NoPricingConfigError, UnregisteredModelError)` or add a return value indicating success/failure so callers can react. | `plan, tdd, security` | ⬜ |
| | **Read:** `backend/app/services/metering_service.py` (settle except at 284-290, release except at 333-339). `backend/app/providers/metered_provider.py` (callers of settle/release at 172-178). | | |
| | **TDD:** Test that expected DB errors are still caught and logged. Test that unexpected errors (e.g., TypeError) are re-raised or reported distinctly. | | |
| | **Done when:** Programming errors in settle/release are not silently swallowed. Expected financial errors are still handled gracefully. | | |
| 38 | **[LOW] Stream fail-closed when credits enabled (AF-09)** — `MeteredLLMProvider.stream()` is unmetered. Currently no production callers exist (dormant risk), but the method is on the public interface. Make stream() fail-closed by raising `ProviderError` when `settings.credits_enabled` is True, preventing accidental unmetered usage if streaming is wired up in the future. | `plan, tdd, provider, security` | ⬜ |
| | **Read:** `backend/app/providers/metered_provider.py` (stream at 182-216). `backend/app/core/config.py` (credits_enabled). | | |
| | **TDD:** Test stream raises ProviderError when credits_enabled=True. Test stream still works when credits_enabled=False. | | |
| | **Done when:** Stream is fail-closed for metered environments. Unmetered environments unaffected. | | |
| 39 | **[LOW] Frontend query invalidation + config Decimal + documentation (AF-08, AF-10, AF-11, AF-12)** — Four small fixes: (a) Add `usageTransactions` query invalidation on checkout success in `usage-page.tsx`. (b) Change `metering_minimum_balance` from `float` to `str` in config.py (avoids float→Decimal precision issues). (c) Add code comment documenting refund+active-reservation interaction in `stripe_webhook_service.py`. (d) Add `# nosemgrep` comment to migration 028 f-string SQL with justification. | `plan, tdd, ui` | ⬜ |
| | **Read:** `frontend/src/components/usage/usage-page.tsx` (StripeRedirectHandler at 55-75, query invalidation at 64-65). `backend/app/core/config.py` (metering_minimum_balance). `backend/app/services/stripe_webhook_service.py` (refund handler at 162-240). `backend/migrations/versions/028_billing_hardening.py` (f-string at 121-123). `backend/app/api/deps.py` (Decimal conversion at 344). | | |
| | **TDD:** Test frontend: checkout success invalidates usageTransactions. Test backend: metering_minimum_balance loads correctly as Decimal. | | |
| | **Done when:** All four minor fixes applied. No stale cache on checkout success. Config precision is clean. Documentation items addressed. | | |
| 40 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright + lint + typecheck). Fix regressions, commit, push. | `plan, commands` | ⬜ |

#### Phase 7 Notes

- Tasks are ordered by severity (HIGH → MEDIUM → LOW), not by dependency. Most are independent and could be implemented in any order, except: §31 (settle race fix) should land before §32 (overdraft protection) since both modify settle()
- §31 is the highest-impact fix: eliminates a race condition that could result in free LLM calls
- §34 (remove record_and_debit) is a breaking change for tests only — zero production impact
- §39 groups four genuinely trivial fixes (1-3 lines each) into one commit. Each is independent but too small to warrant separate review cycles
- The audit was conducted against the merged PR #61 code on `main`. Phase 7 work should branch from current `main`

#### Audit Findings Register

| ID | Severity | Title | Task | Impact |
|----|----------|-------|------|--------|
| AF-01 | HIGH | Settle/sweep race — free LLM calls | §31 | Financial: user gets unmetered service |
| AF-02 | HIGH | No balance_usd floor in settle() | §32 | Financial: balance goes negative via usage |
| AF-03 | MEDIUM | Reservation ignores input token cost | §33 | Financial: under-estimation enables overdraft |
| AF-04 | MEDIUM | Dead record_and_debit() method | §34 | Integrity: legacy path could bypass reservations |
| AF-05 | MEDIUM | Zero-cost reservation hits CHECK constraint | §35 | Availability: IntegrityError on zero-priced models |
| AF-06 | MEDIUM | mark_completed outside savepoint | §36 | Integrity: credit without purchase status update |
| AF-07 | MEDIUM | settle/release swallow programming errors | §37 | Debuggability: silent failures in financial code |
| AF-08 | LOW | Refund + active reservation interaction | §39 | Documentation: confusing state, not a bug |
| AF-09 | LOW | Stream metering gap (dormant) | §38 | Financial: zero current exposure, future risk |
| AF-10 | LOW | Frontend usageTransactions stale cache | §39 | UX: stale data after checkout |
| AF-11 | LOW | Migration f-string SQL (false positive) | §39 | Tooling: Semgrep false positive |
| AF-12 | LOW | metering_minimum_balance is float | §39 | Precision: float→Decimal conversion risk |

---

## Task Count Summary

| Phase | Tasks | Subtasks | Gates |
|-------|-------|----------|-------|
| Phase 1: Database & Foundation | 5 | 3 | 1 security + 1 phase |
| Phase 2: Reservation Pipeline | 7 | 5 | 1 security + 1 phase |
| Phase 3: Webhook & Stripe Hardening | 5 | 3 | 1 security + 1 phase |
| Phase 4: Quick Fixes & Frontend | 3 | 2 | 1 phase |
| Phase 5: Background Reconciliation | 4 | 2 | 1 security + 1 phase |
| Phase 6: Integration Testing & Polish | 5 | 3 | 1 security + 1 phase |
| Phase 7: Post-Audit Hardening | 11 | 9 | 1 security + 1 phase |
| **Total** | **40** | **27** | **6 security + 7 phase** |

---

## Critical Files Reference

| File | Phase(s) | REQ-030 Section |
|------|----------|----------------|
| `backend/app/models/usage_reservation.py` | 1 | §4.2 |
| `backend/app/models/user.py` | 1 | §4.1 |
| `backend/app/models/stripe.py` | 1 | §4.3, §7.3 |
| `backend/app/services/metering_service.py` | 2, 7 | §5.2, §5.3, §5.5 + AF-01–AF-05, AF-07 |
| `backend/app/providers/metered_provider.py` | 2, 7 | §5.4, §5.6, §5.7 + AF-07, AF-09 |
| `backend/app/api/deps.py` | 2 | §6.1 |
| `backend/app/services/stripe_webhook_service.py` | 3, 7 | §7.2, §7.3 + AF-06, AF-08 |
| `backend/app/repositories/stripe_repository.py` | 3 | §7.3 |
| `backend/app/api/v1/webhooks.py` | 3 | §7.3 |
| `backend/app/services/stripe_service.py` | 3 | §8.1 |
| `backend/app/api/v1/credits.py` | 4 | §10.1 |
| `frontend/src/components/usage/usage-page.tsx` | 4, 7 | §10.2 + AF-10 |
| `CLAUDE.md` | 4 | §10.3 |
| `backend/app/services/reservation_sweep.py` | 5 | §11.1, §11.2 |
| `backend/app/core/config.py` | 1, 7 | §9.1, §9.2, AF-12 |
| `backend/migrations/versions/028_billing_hardening.py` | 1, 7 | §4.4, AF-11 |

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-27 | 0.1 | Initial plan. 6 phases, 29 tasks (18 implementation + 5 security gates + 6 phase gates). |
| 2026-03-28 | 0.2 | Added Phase 7: Post-Audit Hardening. 12 findings from adversarial red-team audit (3 HIGH, 4 MEDIUM, 5 LOW). 11 new tasks (§30–§40). Total: 7 phases, 40 tasks. |
