# Zentropy Scout — REQ-029 Stripe Checkout Implementation Plan

**Created:** 2026-03-10
**Last Updated:** 2026-03-10
**Status:** ⬜ Incomplete
**Destination:** `docs/plan/stripe_checkout_plan.md`

---

## Context

REQ-029 specifies Stripe Checkout (hosted redirect) integration for self-service "Add Funds" purchases. All prerequisites are complete: REQ-020 (metering ✅), REQ-022 (admin pricing ✅), REQ-023 (USD-direct billing ✅). The current "Add Funds" button on the usage page is disabled with `"Coming soon — REQ-021"`.

**What gets built:**
- **Backend:** StripeClient factory, Stripe service (checkout, webhooks, refunds, signup grant), 3 new API endpoints (GET /packs, POST /checkout, GET /purchases), webhook endpoint (POST /webhooks/stripe), Alembic migration 025 (`stripe_purchases` table, `stripe_customer_id` + `stripe_event_id` columns)
- **Frontend:** Funding pack cards, purchase history table, low-balance warning banner, success/cancel toast handling, enable "Add Funds" button
- **Auth:** Signup grant integration into OAuth, email+password, and magic link flows

**What doesn't change:** Existing metering pipeline, balance gating, usage history, admin pack CRUD. The `funding_packs` table schema doesn't change — `stripe_price_id` values are populated by admins via the existing admin UI.

**Key decisions (REQ-029 §2):**
- `StripeClient` pattern (not deprecated `stripe.api_key` global)
- Hosted redirect mode (SAQ A — card data never touches our servers)
- Customer created on first purchase (not at registration)
- Idempotency via `stripe_event_id` UNIQUE constraint on `credit_transactions`
- Refund via `charge.refunded` webhook (admin-initiated via Stripe Dashboard)

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Load REQ-029 via `req-reader` subagent before each task (load the §sections listed)
3. Each task = one commit, sized ≤ 40k tokens of context (TDD + review + fixes included)
4. **Subtask workflow:** Run affected tests → linters → commit → compact (NO push)
5. **Phase-end workflow:** Run full test suite (backend + frontend + E2E) → push → compact
6. After each task: update status (⬜ → ✅), commit, STOP and ask user

| Action | Subtask | Phase Gate |
|--------|---------|------------|
| Tests | Affected files only | Full backend + frontend + E2E |
| Linters | Pre-commit hooks (~25-40s) | Pre-commit + pre-push hooks |
| Git | `git commit` only | `git push` |
| Context | Compact after commit | Compact after push |

**Why:** Pushes trigger pre-push hooks (full pytest + vitest, ~90-135s). By deferring pushes to phase boundaries, we save ~90-135s per subtask while maintaining quality gates.

**Context management for fresh sessions:** Each subtask is self-contained. A fresh context needs:
1. This plan (find current task by status icon)
2. REQ-029 (via `req-reader` — load the §section listed in the task)
3. The specific files listed in the task description
4. No prior conversation history required

---

## Dependency Chain

```
Phase 1: Foundation (Config + Deps + StripeClient)
    │
    ▼
Phase 2: Database (Models + Migration + Repository)
    │
    ▼
Phase 3: Stripe Service (Checkout + Webhooks + Signup Grant)
    │
    ▼
Phase 4: Backend API (Schemas + Endpoints + Registration)
    │
    ▼
Phase 5: Frontend (API Client + Components + Page Integration)
    │
    ▼
Phase 6: Auth Integration (Signup Grant → Auth Flows)
```

**Ordering rationale:** Phases are strictly sequential. Config/deps must exist before any Stripe code (imported everywhere). Models + migration must exist before repository/service can reference them. Service must exist before API endpoints consume it. Backend must be complete before frontend calls it. Auth integration is last because the `grant_signup_credits` method is built in Phase 3, but wiring it into auth flows is a standalone integration task.

---

## Phase 1: Foundation — Config, Dependency & StripeClient

**Status:** ✅ Complete

*Install the Stripe SDK, add configuration variables with production security checks, create the StripeClient factory with FastAPI dependency injection.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-029 §5.1 (dependency), §11 (configuration), §5.2 (StripeClient) |
| 🧪 **TDD** | Write config validation tests first, then StripeClient tests |
| 🗃️ **Patterns** | Use `zentropy-api` for DI pattern, `zentropy-tdd` for tests |
| ✅ **Verify** | `pytest -v` affected tests, lint, typecheck |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). Verdicts: CLEAR → mark complete, proceed. VULNERABLE → fix immediately. FALSE POSITIVE → complete full PROSECUTION PROTOCOL before dismissing. NEEDS INVESTIGATION → escalate to user via AskUserQuestion. | `plan, security` | ✅ |
| 2 | **Install `stripe[async]` + Stripe config vars + production security checks** — Add the Stripe SDK dependency, Stripe configuration variables (SecretStr), production startup validation, and `.env.example` documentation. | `plan, tdd, security` | ✅ |
| | **Read:** REQ-029 §5.1 (dependency spec), §11.1–§11.3 (env vars, config.py additions, production checks). Read `backend/pyproject.toml` (dependency format). Read `backend/app/core/config.py` (~Settings class, `check_production_security()`). Read `.env.example` (format). | `req-reader` | |
| | **Modify `backend/pyproject.toml`:** Add `"stripe[async]>=14.0.0,<15.0.0"` to dependencies. Run `pip install -e .` in venv. | | |
| | **Modify `backend/app/core/config.py`:** Add 4 settings to `Settings` class: `stripe_secret_key: SecretStr = SecretStr("")`, `stripe_webhook_secret: SecretStr = SecretStr("")`, `stripe_publishable_key: str = ""`, `credits_enabled: bool = True`. Add production security checks in `check_production_security()` — require non-empty Stripe keys when `credits_enabled`, reject `sk_test_` prefix in production. Add startup warning when `credits_enabled=True` but `metering_enabled=False` (invalid combo per REQ-029 §11.4 / REQ-021 §10.3). | | |
| | **Modify `.env.example`:** Document `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PUBLISHABLE_KEY`, `CREDITS_ENABLED` with descriptions matching §11.1. | | |
| | **TDD:** Update existing config tests (`test_config*.py`) — verify new settings load, SecretStr masking works, production check raises on missing keys, production check raises on `sk_test_` key, `credits_enabled` defaults to `true`, startup warning logged for `credits_enabled=True` + `metering_enabled=False`. | | |
| | **Run:** `pytest tests/unit/test_config*.py -v` | | |
| | **Done when:** `import stripe` works, all 4 config vars load, production checks pass, `.env.example` documented. | | |
| 3 | **StripeClient factory + FastAPI dependency injection** — Create the `get_stripe_client()` factory function and `StripeClientDep` type alias for endpoint injection. | `plan, tdd, api` | ✅ |
| | **Read:** REQ-029 §5.2 (StripeClient config, API version pinning). Read `backend/app/api/deps.py` (existing DI patterns for `DbSession`, `CurrentUserId`). | `req-reader` | |
| | **Create `backend/app/core/stripe_client.py`:** `get_stripe_client()` factory returning `StripeClient(api_key=settings.stripe_secret_key.get_secret_value(), stripe_version="2025-12-18.preview")`. Export `StripeClientDep = Annotated[StripeClient, Depends(get_stripe_client)]`. | | |
| | **Create `backend/tests/unit/test_stripe_client.py`:** Test factory creates client, test API version is pinned, test dependency type alias exists. Mock `settings.stripe_secret_key` — do NOT use real keys. | | |
| | **Run:** `pytest tests/unit/test_stripe_client.py -v` | | |
| | **Done when:** Factory creates StripeClient with pinned API version. `StripeClientDep` ready for endpoint use. | | |
| 4 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright + lint + typecheck). Fix regressions, commit, push. | `plan, commands` | ✅ |

#### Phase 1 Notes

**Dependency installation:** After modifying `pyproject.toml`, activate the backend venv (`source backend/.venv/bin/activate`) and run `pip install -e .` to install `stripe[async]` and its `httpx` transitive dependency. Verify with `python -c "import stripe; print(stripe.VERSION)"`.

**SecretStr pattern:** Existing precedent in `config.py` — `auth_secret` already uses `SecretStr`. Follow the same pattern for `stripe_secret_key` and `stripe_webhook_secret`.

**API version pinning:** `stripe_version="2025-12-18.preview"` locks Stripe API behavior regardless of the Dashboard's default. This prevents breaking changes from Stripe's rolling updates.

---

## Phase 2: Database — Models, Migration & Repository

**Status:** ✅ Complete

*Update existing models with Stripe columns, create the StripePurchase model, write the Alembic migration (schema + signup grant data migration), and create the StripePurchase repository.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-029 §4 (full DB schema), REQ-021 §8 (signup grant), REQ-021 §6.7 (balance crediting SQL) |
| 🧪 **TDD** | Write model/repo tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-db` for migration, model, and repository patterns |
| ✅ **Verify** | `alembic upgrade/downgrade`, `pytest -v` affected tests, lint |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 5 | **Security triage gate** — Spawn `security-triage` subagent. | `plan, security` | ✅ |
| 6 | **Model updates — user.py, usage.py, new stripe.py, __init__.py** — Add `stripe_customer_id` to User, `stripe_event_id` to CreditTransaction, create StripePurchase model, export from `__init__.py`. | `plan, tdd, db` | ✅ |
| | **Read:** REQ-029 §4.1 (`stripe_customer_id`), §4.2 (`stripe_event_id`), §4.3 (`stripe_purchases` table). Read `backend/app/models/user.py`, `backend/app/models/usage.py`, `backend/app/models/__init__.py`. | `req-reader` | |
| | **Modify `backend/app/models/user.py`:** Add `stripe_customer_id: Mapped[str \| None] = mapped_column(String(255), unique=True, nullable=True)`. | | |
| | **Modify `backend/app/models/usage.py`:** Add `stripe_event_id: Mapped[str \| None] = mapped_column(String(255), unique=True, nullable=True)` to `CreditTransaction`. | | |
| | **Create `backend/app/models/stripe.py`:** `StripePurchase` model per §4.3 — `id` (UUID PK), `user_id` (FK users), `pack_id` (FK funding_packs), `stripe_session_id` (VARCHAR 255, UNIQUE), `stripe_customer_id` (VARCHAR 255), `stripe_payment_intent` (VARCHAR 255, nullable), `amount_cents` (INTEGER), `grant_cents` (BIGINT), `currency` (VARCHAR 3, default 'usd'), `status` (VARCHAR 20, default 'pending'), `completed_at`, `refunded_at`, `refund_amount_cents` (INTEGER, default 0), `created_at`, `updated_at`. Indexes: `ix_stripe_purchases_user`, partial index on `status='pending'`. | | |
| | **Modify `backend/app/models/__init__.py`:** Export `StripePurchase`. | | |
| | **TDD:** Write model tests — field types, nullable constraints, unique constraints, FK relationships, default values. Follow sibling test file patterns. | | |
| | **Run:** `pytest tests/unit/test_*models*.py -v` (affected model tests) | | |
| | **Done when:** All 3 model files updated, StripePurchase defined with correct schema, `__init__.py` exports it, model tests pass. | | |
| 7 | **Alembic migration 025 — schema DDL + signup grant data migration** — Create `025_stripe_checkout.py` with schema changes and existing-user signup grant. | `plan, tdd, db, commands` | ✅ |
| | **Read:** REQ-029 §4.6 (migration spec), §4.1–§4.3 (column/table SQL), REQ-021 §8 (signup grant details). Read `backend/migrations/versions/024_gemini_embedding_dimensions.py` (revision chain, format). | `req-reader` | |
| | **Create `backend/migrations/versions/025_stripe_checkout.py`:** | | |
| | `revision = "025_stripe_checkout"`, `down_revision = "024_gemini_embedding_dimensions"` | | |
| | **Upgrade (in order):** | | |
| | (1) `ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(255) UNIQUE` | | |
| | (2) `ALTER TABLE credit_transactions ADD COLUMN stripe_event_id VARCHAR(255) UNIQUE` | | |
| | (3) `CREATE TABLE stripe_purchases (...)` with all columns per §4.3 | | |
| | (4) `CREATE INDEX ix_stripe_purchases_user ON stripe_purchases(user_id)` | | |
| | (5) `CREATE INDEX ix_stripe_purchases_status ON stripe_purchases(status) WHERE status = 'pending'` | | |
| | (6) **Data migration:** For all existing users without a `signup_grant` transaction, INSERT a `credit_transactions` row (`transaction_type='signup_grant'`, `amount_usd` from `system_config.signup_grant_cents` / 100, `description='Welcome bonus — free starter balance'`). Atomically credit each user's `balance_usd`. | | |
| | **Downgrade (reverse order):** | | |
| | (1) Delete all `signup_grant` transactions (rollback data migration) | | |
| | (2) Debit `balance_usd` for affected users (reverse the credit) | | |
| | (3) Drop indexes, drop `stripe_purchases` table | | |
| | (4) `ALTER TABLE credit_transactions DROP COLUMN stripe_event_id` | | |
| | (5) `ALTER TABLE users DROP COLUMN stripe_customer_id` | | |
| | **Verify:** `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head`. SQL queries to verify columns, table, and signup grant data. | | |
| | **Run:** `pytest tests/ -v -k "migration or alembic"` (if migration tests exist) | | |
| | **Done when:** Migration runs cleanly in both directions. `stripe_purchases` table exists. `stripe_customer_id` and `stripe_event_id` columns exist. Existing users have `signup_grant` transactions. | | |
| 8 | **StripePurchase repository + CreditTransaction extensions** — CRUD repository for `stripe_purchases` table and `find_by_stripe_event_id` for idempotency checks. | `plan, tdd, db` | ✅ |
| | **Read:** REQ-029 §7.2 (idempotency via `stripe_event_id`), §7.3 (refund via `payment_intent`), §8.3 (purchases query). Read existing repository: `backend/app/repositories/` (sibling files for pattern). | `req-reader` | |
| | **Create `backend/app/repositories/stripe_repository.py`:** | | |
| | — `StripePurchaseRepository(db: AsyncSession)` | | |
| | — `create(user_id, pack_id, session_id, customer_id, amount_cents, grant_cents) -> StripePurchase` | | |
| | — `find_by_session_id(session_id) -> StripePurchase \| None` | | |
| | — `find_by_payment_intent(payment_intent_id) -> StripePurchase \| None` | | |
| | — `mark_completed(stripe_session_id, stripe_payment_intent) -> None` | | |
| | — `mark_refunded(purchase_id, refund_amount_cents, is_full_refund) -> None` | | |
| | — `get_user_purchases(user_id, page, per_page) -> tuple[list[StripePurchase], int]` (paginated) | | |
| | **Extend existing credit transaction handling:** Add `find_by_stripe_event_id(event_id) -> CreditTransaction \| None` method (for idempotency checks in webhook handlers). | | |
| | **TDD:** Write repository tests with mock/test DB session. Test each CRUD method, pagination, and idempotency lookup. | | |
| | **Run:** `pytest tests/unit/test_stripe_repository.py -v` | | |
| | **Done when:** All repository methods work, paginated queries return correct results, `find_by_stripe_event_id` returns existing or None. | | |
| 9 | **Phase gate — full test suite + push** | `plan, commands` | ✅ |

#### Phase 2 Notes

**Signup grant data migration complexity:** The data migration must handle the case where `signup_grant_cents` is 0 (grants disabled) — in that case, skip the INSERT. It must also handle users who already have a `signup_grant` transaction (shouldn't happen, but be defensive). Use a subquery: `INSERT INTO credit_transactions ... SELECT ... FROM users WHERE users.id NOT IN (SELECT user_id FROM credit_transactions WHERE transaction_type = 'signup_grant')`.

**Downgrade data migration:** Reversing signup grants requires deducting from `balance_usd`. If a user has already spent their balance below the grant amount, the deduction could make `balance_usd` negative. This is acceptable in a downgrade scenario (it's a development/emergency operation).

**Repository pattern:** Follow existing repository files in `backend/app/repositories/`. The credit transaction extension (adding `find_by_stripe_event_id`) may go in an existing repository class or a new method on the StripeRepository that queries `credit_transactions` — follow whichever pattern exists.

---

## Phase 3: Stripe Service — Checkout, Webhooks & Signup Grant

**Status:** ⬜ Incomplete

*Build the core business logic: checkout session creation with Stripe Customer management, webhook handlers for checkout.session.completed and charge.refunded, and the signup grant service method.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-029 §6 (checkout flow), §7 (webhooks), §12 (signup grant), REQ-021 §6.6 (error scenarios), §6.7 (balance SQL), §8 (signup grant details) |
| 🧪 **TDD** | Write service tests with mocked StripeClient — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-provider` for external API mocking patterns |
| ✅ **Verify** | `pytest -v` affected tests, lint |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 10 | **Security triage gate** — Spawn `security-triage` subagent. | `plan, security` | ✅ |
| 11 | **StripeService — checkout session creation + customer management** — `create_checkout_session()` and `get_or_create_customer()` methods. | `plan, tdd, security` | ✅ |
| | **Read:** REQ-029 §6.2 (checkout session creation), §6.3 (customer management), §13.3 (Stripe error mapping), REQ-021 §12.2 (full error mapping). Read `backend/app/services/` (sibling service files for pattern). | `req-reader` | |
| | **Create `backend/app/services/stripe_service.py`:** | | |
| | — `StripeService(db: AsyncSession)` — initialize with repos | | |
| | — `get_or_create_customer(user_id, email, stripe_client) -> str` — Check `users.stripe_customer_id`. If exists, return it. If not, call `stripe_client.customers.create_async()` with `email` and `metadata={"zentropy_user_id": str(user_id)}`, save to users table, return `customer.id`. | | |
| | — `create_checkout_session(user_id, user_email, pack, stripe_client) -> tuple[str, str]` — Get/create customer, call `stripe_client.checkout.sessions.create_async()` with line_items, mode="payment", success/cancel URLs (§6.2), metadata (user_id, pack_id, grant_cents). Record pending purchase in `stripe_purchases`. Return `(session.url, session.id)`. | | |
| | — Validate pack has non-null `stripe_price_id` before creating session. | | |
| | — Stripe error handling: catch `stripe.StripeError` subclasses and map to API error codes (§13.3). Never expose Stripe error details to users. | | |
| | **TDD:** Mock StripeClient methods. Test: valid checkout creates session + pending purchase, existing customer reused, new customer created and saved, pack without `stripe_price_id` raises error, inactive pack raises error, Stripe API error mapped correctly. | | |
| | **Run:** `pytest tests/unit/test_stripe_service.py -v` | | |
| | **Done when:** Checkout session created with correct metadata, customer management idempotent, Stripe errors handled gracefully. | | |
| 12 | **StripeService — `handle_checkout_completed` webhook handler** — Process `checkout.session.completed` events: verify payment status, extract metadata, credit balance, update purchase record. | `plan, tdd, security` | ✅ |
| | **Read:** REQ-029 §7.2 (handler logic, event payload fields), §7.4 (retry behavior), §13.2 (webhook error scenarios), REQ-021 §6.6 (error table), §6.7 (atomic balance SQL). | `req-reader` | |
| | **Add to `stripe_service.py`:** | | |
| | — `handle_checkout_completed(event) -> None` — per §7.2: | | |
| | (1) Extract `session.payment_status` — skip if not `"paid"` | | |
| | (2) Extract metadata: `user_id`, `pack_id`, `grant_cents` | | |
| | (3) Idempotency check via `find_by_stripe_event_id(event.id)` — return if exists | | |
| | (4) Validate user exists in DB | | |
| | (5) Create `credit_transactions` row: `amount_usd = Decimal(grant_cents) / Decimal(100)`, `transaction_type='purchase'`, `reference_id=session.id`, `stripe_event_id=event.id` | | |
| | (6) Atomically credit `users.balance_usd` | | |
| | (7) Update `stripe_purchases` status → 'completed', set `completed_at` and `stripe_payment_intent` | | |
| | **TDD:** Test: balance credited correctly, idempotent (same event ID skipped), missing metadata logged + skipped, user not found logged + skipped, unpaid session skipped, purchase record updated to 'completed'. | | |
| | **Run:** `pytest tests/unit/test_stripe_service.py -v -k "checkout_completed"` | | |
| | **Done when:** Webhook handler is idempotent, credits balance atomically, handles all error scenarios from §13.2. | | |
| 13 | **StripeService — `handle_charge_refunded` + `grant_signup_credits`** — Refund webhook handler with cumulative partial refund tracking, plus the signup grant service method. | `plan, tdd, security` | ✅ |
| | **Read:** REQ-029 §7.3 (refund handler, cumulative `amount_refunded`), §12 (signup grant flow), REQ-021 §8 (signup grant integration points, idempotency). | `req-reader` | |
| | **Add to `stripe_service.py`:** | | |
| | — `handle_charge_refunded(event) -> None` — per §7.3: | | |
| | (1) Idempotency check via `stripe_event_id` | | |
| | (2) Find original purchase by `charge.payment_intent` | | |
| | (3) Calculate delta: `this_refund = charge.amount_refunded - purchase.refund_amount_cents` | | |
| | (4) Skip if delta ≤ 0 | | |
| | (5) Create `credit_transactions` row: negative `amount_usd`, `transaction_type='refund'`, `reference_id=charge.id`, `stripe_event_id=event.id` | | |
| | (6) Debit `users.balance_usd` | | |
| | (7) Update `stripe_purchases`: `refund_amount_cents`, status ('refunded' or 'partial_refund'), `refunded_at` | | |
| | (8) Warn if balance went negative | | |
| | — `grant_signup_credits(user_id) -> None` — per §12: | | |
| | (1) Read `signup_grant_cents` from `system_config` (default 10) | | |
| | (2) If 0, skip (grants disabled) | | |
| | (3) Idempotency: check for existing `signup_grant` transaction for this user | | |
| | (4) Insert `credit_transactions` row: `transaction_type='signup_grant'`, `amount_usd = cents / 100` | | |
| | (5) Credit `balance_usd` | | |
| | **TDD:** Refund tests: full refund debits correctly, partial refund tracks delta, duplicate event skipped, purchase not found logged, balance goes negative (warning logged). Signup grant tests: grants on first call, skips on duplicate, zero amount disables, converts cents to USD correctly. | | |
| | **Run:** `pytest tests/unit/test_stripe_service.py -v -k "refund or signup"` | | |
| | **Done when:** Refund handler handles full/partial/duplicate correctly. Signup grant is idempotent and configurable. | | |
| 14 | **Phase gate — full test suite + push** | `plan, commands` | ⬜ |

#### Phase 3 Notes

**Mocking strategy (REQ-029 §16.3):** All StripeClient methods are mocked — no real Stripe API calls in tests. Mock `checkout.sessions.create_async()`, `customers.create_async()`, `customers.retrieve_async()`. For webhook events, construct test event objects with the documented payload fields (§7.2, §7.3).

**Atomic balance operations:** Credit: `UPDATE users SET balance_usd = balance_usd + :amount WHERE id = :user_id`. Debit: `UPDATE users SET balance_usd = balance_usd - :amount WHERE id = :user_id`. Debit does NOT have a `WHERE balance_usd >= :amount` guard (refunds can legitimately make balance negative). See REQ-021 §6.7.

**Cumulative refund tracking (§7.3):** `charge.amount_refunded` is cumulative across all partial refunds. The handler computes the delta by comparing with `stripe_purchases.refund_amount_cents` (our tracked total). This correctly handles multiple partial refund events.

---

## Phase 4: Backend API — Schemas, Endpoints & Registration

**Status:** ⬜ Incomplete

*Create Pydantic schemas for credit endpoints, build the credits router (packs, checkout, purchases) and webhooks router (Stripe webhook), and register both in the main router.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-029 §8 (API endpoints), §7.1 (webhook endpoint), §13 (error codes), REQ-006 (response envelope) |
| 🧪 **TDD** | Write endpoint tests with mocked service — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-api` for router/response patterns |
| ✅ **Verify** | `pytest -v` affected tests, lint, typecheck |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 15 | **Security triage gate** — Spawn `security-triage` subagent. | `plan, security` | ⬜ |
| 16 | **Credit schemas** — Pydantic models for credit endpoint request/response bodies. | `plan, tdd, api` | ⬜ |
| | **Read:** REQ-029 §8.1 (GET /packs response), §8.2 (POST /checkout request/response), §8.3 (GET /purchases response), §13.1 (error codes). Read `backend/app/schemas/admin.py` (sibling schema file for format/pattern). | `req-reader` | |
| | **Create `backend/app/schemas/credits.py`:** | | |
| | — `CheckoutRequest`: `pack_id: UUID` (required) | | |
| | — `CheckoutResponse`: `checkout_url: str`, `session_id: str` | | |
| | — `PackResponse`: `id: UUID`, `name: str`, `price_cents: int`, `price_display: str`, `grant_cents: int`, `amount_display: str`, `description: str`, `highlight_label: str \| None` | | |
| | — `PurchaseResponse`: `id: UUID`, `amount_usd: str`, `amount_display: str`, `transaction_type: str`, `description: str`, `created_at: datetime` | | |
| | — Helper: `format_usd_display(cents: int) -> str` — format `500` → `"$5.00"` | | |
| | **TDD:** Write schema validation tests — valid data passes, missing required fields rejected, UUID format validated, display formatting correct. | | |
| | **Run:** `pytest tests/unit/test_credit_schemas.py -v` | | |
| | **Done when:** All schemas validate correctly. Display formatters produce expected output. | | |
| 17 | **Credits router — GET /packs, POST /checkout, GET /purchases** — Three credit-related endpoints for pack listing, checkout initiation, and purchase history. | `plan, tdd, api, security` | ⬜ |
| | **Read:** REQ-029 §8.1–§8.3 (endpoint specs), §8.5 (router registration). Read `backend/app/api/v1/usage.py` (sibling router for pattern). Read `backend/app/api/v1/router.py` (registration). | `req-reader` | |
| | **Create `backend/app/api/v1/credits.py`:** | | |
| | — `GET /packs` — No auth required. Query active `FundingPack` rows with non-null `stripe_price_id`. Return `PackResponse[]`. | | |
| | — `POST /checkout` — Auth required (`CurrentUserId`). Accept `CheckoutRequest`. Look up pack (validate active + has `stripe_price_id`). Call `StripeService.create_checkout_session()`. Return `CheckoutResponse`. Check `credits_enabled` — 503 if disabled. | | |
| | — `GET /purchases` — Auth required. Accept `page`/`per_page` query params. Return paginated `PurchaseResponse[]`. Query `credit_transactions` for current user with types: `purchase`, `signup_grant`, `admin_grant`, `refund`. | | |
| | **TDD:** Test each endpoint — auth requirements, valid/invalid requests, error codes (INVALID_PACK_ID 400, STRIPE_ERROR 502, CREDITS_UNAVAILABLE 503), pagination. Mock StripeService. | | |
| | **Run:** `pytest tests/unit/test_credits_api.py -v` | | |
| | **Done when:** All 3 endpoints work with correct auth, validation, and error handling. | | |
| 18 | **Webhooks router + router registration** — Stripe webhook endpoint with signature verification, event routing, and rate limit exemption. Register credits and webhooks routers. | `plan, tdd, api, security` | ⬜ |
| | **Read:** REQ-029 §7.1 (webhook endpoint), §5.3 (signature verification), §7.4 (retry behavior), §10.2 (webhook security). Read `backend/app/api/v1/router.py` (current registrations). | `req-reader` | |
| | **Create `backend/app/api/v1/webhooks.py`:** | | |
| | — `POST /stripe` — No auth (public endpoint). Read raw `request.body()` bytes. Verify `Stripe-Signature` header via `stripe.Webhook.construct_event()`. Route by `event.type` using `match/case`: `checkout.session.completed` → `stripe_service.handle_checkout_completed()`, `charge.refunded` → `stripe_service.handle_charge_refunded()`, default → ignore (return 200). Return `{"received": True}`. | | |
| | — Handle `ValueError` → 400 INVALID_PAYLOAD, `stripe.SignatureVerificationError` → 401 INVALID_SIGNATURE. | | |
| | — Exempt from rate limiting (per REQ-029 §10.2). | | |
| | **Modify `backend/app/api/v1/router.py`:** Register `credits.router` at `/credits` and `webhooks.router` at `/webhooks` per §8.5. | | |
| | **TDD:** Test: valid signature processes event, invalid signature returns 401, malformed payload returns 400, unknown event type returns 200 (no processing), duplicate event handled idempotently. Mock `stripe.Webhook.construct_event`. | | |
| | **Run:** `pytest tests/unit/test_webhooks_api.py -v` | | |
| | **Done when:** Webhook verifies signatures, routes events, returns 200 for unhandled types. Routers registered. | | |
| 19 | **Phase gate — full test suite + push** | `plan, commands` | ⬜ |

#### Phase 4 Notes

**Raw body for webhook (CRITICAL):** The webhook endpoint must use `await request.body()` to get raw bytes. If FastAPI auto-parses the JSON first (e.g., via a Pydantic body parameter), the HMAC signature verification will fail because the body was already consumed/decoded. Use `request: Request` parameter, not a typed body.

**Rate limit exemption:** Stripe may send bursts of webhooks. The webhook endpoint should be excluded from `slowapi` rate limiting. Check how existing endpoints handle rate limiting and follow the exemption pattern.

**Public vs authenticated endpoints:** GET /packs is public (no auth — anyone can see pricing). POST /checkout and GET /purchases require `CurrentUserId`. The webhook is public but secured by signature verification.

---

## Phase 5: Frontend — API Client, Components & Page Integration

**Status:** ⬜ Incomplete

*Build the frontend: API client for credit endpoints, funding pack cards, purchase history table, low-balance warning, and integrate into the existing usage page.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-029 §9 (frontend), §8 (API response shapes for type defs) |
| 🧪 **TDD** | Write component tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-tdd` for Vitest, follow sibling component patterns in `components/usage/` |
| ✅ **Verify** | `npm test -- --run`, `npm run typecheck`, `npm run lint` |
| 🔍 **Review** | `code-reviewer` + `ui-reviewer` (for .tsx tasks) |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 20 | **Security triage gate** — Spawn `security-triage` subagent. | `plan, security` | ⬜ |
| 21 | **Credits API client + types + query keys** — TypeScript API functions, type definitions, and React Query keys for credit endpoints. | `plan, tdd` | ⬜ |
| | **Read:** REQ-029 §8.1–§8.3 (API response shapes), §9.6 (query keys). Read `frontend/src/lib/api/` (sibling API client for pattern). Read `frontend/src/types/usage.ts`. Read `frontend/src/lib/query-keys.ts`. | `req-reader` | |
| | **Create `frontend/src/lib/api/credits.ts`:** | | |
| | — `fetchCreditPacks(): Promise<PackItem[]>` — GET /credits/packs (no auth needed) | | |
| | — `createCheckoutSession(packId: string): Promise<{checkout_url: string, session_id: string}>` — POST /credits/checkout | | |
| | — `fetchPurchases(page, perPage): Promise<PaginatedResponse<PurchaseItem>>` — GET /credits/purchases | | |
| | **Modify `frontend/src/types/usage.ts`:** Add `PackItem`, `PurchaseItem` interfaces matching API response shapes. | | |
| | **Modify `frontend/src/lib/query-keys.ts`:** Add `creditPacks: ["credits", "packs"]` and `purchases: ["credits", "purchases"]`. | | |
| | **TDD:** Write API client tests (mock fetch). Test each function calls correct URL, passes correct params, returns typed data. | | |
| | **Run:** `npm test -- --run credits` | | |
| | **Done when:** API functions typed correctly, query keys defined, tests pass. | | |
| 22 | **FundingPacks component** — Pack selection cards with highlight badge and "Add Funds" buttons. | `plan, tdd, ui` | ⬜ |
| | **Read:** REQ-029 §9.2 (pack card spec), §9.3 (checkout flow). Read `frontend/src/components/usage/` (sibling components for pattern). Read `frontend/src/components/usage/balance-card.tsx` (existing disabled "Add Funds" button). | `req-reader` | |
| | **Create `frontend/src/components/usage/funding-packs.tsx`:** | | |
| | — Fetch packs via `useQuery` with `creditPacks` key | | |
| | — Render each pack as a card: name, description, `price_display`, highlight badge (if `highlight_label` present), "Add Funds" button | | |
| | — Highlighted pack gets visual emphasis (border accent, badge) | | |
| | — "Add Funds" click: call `createCheckoutSession(packId)`, set loading state, redirect via `window.location.href = checkout_url` (REQ-029 §9.3 — no Stripe JS needed) | | |
| | — Loading state: disable all buttons during checkout redirect | | |
| | — Error state: toast on failure, re-enable buttons | | |
| | **Create `frontend/src/components/usage/funding-packs.test.tsx`:** | | |
| | — Renders pack cards from API data | | |
| | — Shows highlight badge on highlighted pack | | |
| | — "Add Funds" button calls checkout API | | |
| | — Loading state disables buttons | | |
| | — Error shows toast | | |
| | **Run:** `npm test -- --run funding-packs` | | |
| | **Done when:** Pack cards render correctly, checkout redirect works, loading/error states handled. | | |
| 23 | **PurchaseTable + LowBalanceWarning components** — Purchase history table with pagination and low-balance alert banner. | `plan, tdd, ui` | ⬜ |
| | **Read:** REQ-029 §8.3 (purchases response shape), §9.5 (low-balance warning thresholds). Read `frontend/src/lib/format-utils.ts` (`BALANCE_THRESHOLD_HIGH`, `BALANCE_THRESHOLD_LOW`). Read `frontend/src/components/usage/transaction-table.tsx` (sibling table for pattern). | `req-reader` | |
| | **Create `frontend/src/components/usage/purchase-table.tsx`:** | | |
| | — Fetch purchases via `useQuery` with `purchases` key, paginated | | |
| | — Table columns: date, description, amount (with sign: +$10.00 / -$0.50), type | | |
| | — Pagination controls (page/per_page) | | |
| | — Empty state: "No purchases yet" | | |
| | **Create `frontend/src/components/usage/low-balance-warning.tsx`:** | | |
| | — Accept `balance` prop (number) | | |
| | — Balance < `BALANCE_THRESHOLD_LOW` ($0.10): Red (destructive) warning with CTA to scroll to funding packs | | |
| | — Balance < `BALANCE_THRESHOLD_HIGH` ($1.00): Amber (primary) warning with CTA | | |
| | — Balance >= $1.00: render nothing | | |
| | — Use existing color constants from `format-utils.ts` | | |
| | **TDD:** PurchaseTable: renders rows, pagination, empty state. LowBalanceWarning: red at <$0.10, amber at <$1.00, hidden at >=$1.00, CTA links to packs section. | | |
| | **Run:** `npm test -- --run purchase-table && npm test -- --run low-balance` | | |
| | **Done when:** Both components render correctly with all threshold states, pagination works. | | |
| 24 | **Wire up usage page — integrate components + enable "Add Funds" + success/cancel handling** — Integrate all new components into the usage page, enable the balance card's "Add Funds" button, and handle Stripe redirect query params. | `plan, tdd, ui` | ⬜ |
| | **Read:** REQ-029 §9.1 (page layout), §9.4 (success/cancel handling). Read `frontend/src/components/usage/usage-page.tsx`. Read `frontend/src/components/usage/balance-card.tsx` (disabled "Add Funds" button). | `req-reader` | |
| | **Modify `frontend/src/components/usage/usage-page.tsx`:** | | |
| | — Add layout order: (1) LowBalanceWarning, (2) Balance Card (existing), (3) FundingPacks (new), (4) PurchaseTable (new), (5) Usage Summary (existing), (6) Usage History (existing) | | |
| | — Add success/cancel URL param handling (§9.4): read `status` from `useSearchParams()` (wrap in `<Suspense>`), show success toast + invalidate balance query on `status=success`, show info toast on `status=cancelled`, clean URL via `router.replace("/usage")` | | |
| | **Modify `frontend/src/components/usage/balance-card.tsx`:** | | |
| | — Remove `disabled` and `"Coming soon — REQ-021"` title from "Add Funds" button | | |
| | — Make "Add Funds" scroll to the funding packs section (anchor link or `scrollIntoView`) | | |
| | **TDD:** Test usage page renders all sections in order. Test success param shows toast and refreshes balance. Test cancel param shows toast. Test URL params cleaned after handling. Test "Add Funds" button is no longer disabled. | | |
| | **Run:** `npm test -- --run usage-page && npm test -- --run balance-card` | | |
| | **Done when:** Usage page shows all components in correct order, success/cancel toasts work, "Add Funds" enabled and scrolls to packs. | | |
| 25 | **Phase gate — full test suite + push** | `plan, commands` | ⬜ |

#### Phase 5 Notes

**No Stripe client-side library:** The hosted redirect flow uses a plain `window.location.href` redirect. No `@stripe/react-stripe-js`, no `loadStripe()`, no publishable key on the frontend. This significantly simplifies the frontend.

**`useSearchParams` + Suspense (CRITICAL):** Next.js App Router requires `useSearchParams()` to be wrapped in a `<Suspense>` boundary. Without it, the page fails at build time. The existing usage page may or may not already have this — check before implementing.

**Threshold constants:** Reuse `BALANCE_THRESHOLD_HIGH` ($1.00) and `BALANCE_THRESHOLD_LOW` ($0.10) from `frontend/src/lib/format-utils.ts`. These are already used by the balance card color scheme and nav bar — do NOT define new constants.

**"Add Funds" button:** The current button in `balance-card.tsx` is disabled with `title="Coming soon — REQ-021"`. This phase enables it and makes it scroll to the FundingPacks section. The actual checkout redirect happens from the FundingPacks component's per-pack "Add Funds" buttons.

---

## Phase 6: Auth Integration — Signup Grant

**Status:** ⬜ Incomplete

*Wire the `grant_signup_credits` service method into all three authentication flows so new users receive their startup balance.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-029 §12, REQ-021 §8 (full signup grant spec with file paths and line numbers) |
| 🧪 **TDD** | Write integration tests for each auth path — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-api` for dependency patterns |
| ✅ **Verify** | `pytest -v` affected tests, lint, typecheck |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 26 | **Security triage gate** — Spawn `security-triage` subagent. | `plan, security` | ⬜ |
| 27 | **Wire signup grant into auth flows** — Call `StripeService.grant_signup_credits(user_id)` from all three user registration paths: OAuth account linking, email+password registration, and magic link signup. | `plan, tdd, security, api` | ⬜ |
| | **Read:** REQ-029 §12 (signup grant summary), REQ-021 §8.1–§8.2 (detailed spec with exact file paths and integration points). Read: `backend/app/api/v1/account_linking.py`, `backend/app/api/v1/auth.py`, `backend/app/api/v1/auth_magic_link.py` (find the user creation points). | `req-reader` | |
| | **Modify 3 auth files:** At each user creation point, after the user record is created and committed, call `await stripe_service.grant_signup_credits(user_id)`. Wrap in try/except to ensure signup grant failure doesn't block registration (log error, continue). | | |
| | **TDD:** Integration tests for each auth path: (1) New user → grant_signup_credits called → balance credited. (2) Existing user login → grant NOT called (not a new user). (3) Grant failure → registration still succeeds (error logged). Mock StripeService in auth tests. | | |
| | **Run:** `pytest tests/unit/test_auth*.py tests/unit/test_account_linking*.py -v` | | |
| | **Done when:** All 3 auth flows call signup grant on new user creation. Grant failures don't break registration. | | |
| 28 | **Phase gate (FINAL) — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright + lint + typecheck). Fix regressions, commit, push. | `plan, commands` | ⬜ |

#### Phase 6 Notes

**Graceful degradation:** Signup grant failure must NOT prevent user registration. Wrap the call in try/except and log the error. The user can still register and use the app (they just won't have the $0.10 starter balance until it's manually granted or they purchase a pack).

**Integration points (REQ-021 §8.2):** The exact file paths and line numbers are documented in REQ-021 §8.2. Use `req-reader` to load that section — it specifies exactly where in each auth flow to add the grant call.

**Existing user migration:** The Alembic migration in Phase 2 (§7) already handles granting signup balance to existing users via a data migration step. This phase only needs to wire the grant into future registrations.

---

## Verification Checklist (after all phases)

1. ⬜ `stripe` importable in backend venv — `python -c "import stripe; print(stripe.VERSION)"`
2. ⬜ `alembic upgrade head` runs cleanly — `stripe_purchases` table, `stripe_customer_id`, `stripe_event_id` columns exist
3. ⬜ `alembic downgrade -1` then `upgrade head` — round-trip clean
4. ⬜ `cd backend && pytest -v` — all pass
5. ⬜ `cd frontend && npm test -- --run` — all pass
6. ⬜ `cd frontend && npm run typecheck` — zero errors
7. ⬜ `cd frontend && npm run lint` — zero errors
8. ⬜ `cd frontend && npx playwright test` — E2E tests pass
9. ⬜ GET /api/v1/credits/packs returns active packs (no auth)
10. ⬜ POST /api/v1/credits/checkout creates Stripe session (with auth)
11. ⬜ POST /api/v1/webhooks/stripe verifies signature and credits balance
12. ⬜ GET /api/v1/credits/purchases returns paginated history (with auth)
13. ⬜ "Add Funds" button on usage page is enabled and scrolls to packs
14. ⬜ Low-balance warning shows at correct thresholds
15. ⬜ New user registration triggers signup grant
16. ⬜ Production security check rejects missing/test Stripe keys

---

## Task Count Summary

| Phase | REQ Sections | Code Tasks | Gates | Total |
|-------|-------------|------------|-------|-------|
| 1 — Foundation | §5.1, §5.2, §11 | 2 | 2 | 4 |
| 2 — Database | §4, §12 | 3 | 2 | 5 |
| 3 — Stripe Service | §6, §7, §12, §13 | 3 | 2 | 5 |
| 4 — Backend API | §7.1, §8, §13 | 3 | 2 | 5 |
| 5 — Frontend | §9 | 4 | 2 | 6 |
| 6 — Auth Integration | §12 | 1 | 2 | 3 |
| **Total** | | **16** | **12** | **28** |

---

## Critical Files Reference

| File | Role |
|------|------|
| `docs/requirements/REQ-029-stripe-checkout.md` | Primary specification (1241 lines) |
| `docs/requirements/REQ-021_credits_billing.md` | Supplemental: §2 design rationale, §6.6 errors, §6.7 SQL, §6.8 reference_id, §8 signup grant, §10.3 config matrix, §12 Stripe errors, §15 resolved questions |
| `backend/app/core/config.py` | Add Stripe env vars + production checks |
| `backend/app/core/stripe_client.py` | NEW — StripeClient factory + DI |
| `backend/app/models/user.py` | Add `stripe_customer_id` |
| `backend/app/models/usage.py` | Add `stripe_event_id` to CreditTransaction |
| `backend/app/models/stripe.py` | NEW — StripePurchase model |
| `backend/app/schemas/credits.py` | NEW — CheckoutRequest, PackResponse, PurchaseResponse |
| `backend/app/repositories/stripe_repository.py` | NEW — StripePurchase CRUD |
| `backend/app/services/stripe_service.py` | NEW — checkout, webhooks, refund, signup grant |
| `backend/app/api/v1/credits.py` | NEW — GET /packs, POST /checkout, GET /purchases |
| `backend/app/api/v1/webhooks.py` | NEW — POST /stripe webhook |
| `backend/app/api/v1/router.py` | Register credits + webhooks routers |
| `backend/migrations/versions/025_stripe_checkout.py` | NEW — schema + data migration |
| `backend/pyproject.toml` | Add `stripe[async]` dependency |
| `.env.example` | Document Stripe env vars |
| `frontend/src/lib/api/credits.ts` | NEW — API client functions |
| `frontend/src/components/usage/funding-packs.tsx` | NEW — Pack selection cards |
| `frontend/src/components/usage/purchase-table.tsx` | NEW — Purchase history |
| `frontend/src/components/usage/low-balance-warning.tsx` | NEW — Low-balance alert |
| `frontend/src/components/usage/usage-page.tsx` | Integrate new components |
| `frontend/src/components/usage/balance-card.tsx` | Enable "Add Funds" button |
| `frontend/src/lib/query-keys.ts` | Add creditPacks + purchases keys |
| `frontend/src/types/usage.ts` | Add PackItem + PurchaseItem types |
| `backend/app/api/v1/account_linking.py` | Wire signup grant (OAuth) |
| `backend/app/api/v1/auth.py` | Wire signup grant (email+password) |
| `backend/app/api/v1/auth_magic_link.py` | Wire signup grant (magic link) |

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-10 | 0.2 | Audit fix: Added configuration matrix warning (`credits_enabled=True` + `metering_enabled=False` → log warning) to §2 task description and TDD list. Based on REQ-029 v0.3 (§16.4 threshold fix). |
| 2026-03-10 | 0.1 | Initial plan. 6 phases, 28 tasks (16 code, 6 security gates, 6 phase gates). Based on REQ-029 v0.2 with REQ-021 v0.6 supplemental. |
