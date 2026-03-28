# REQ-030: Billing & Metering Hardening

**Status:** Not Started
**Version:** 0.1
**PRD Reference:** §6 Technical Architecture
**Backlog Item:** #29
**Last Updated:** 2026-03-27

---

## 1. Overview

This document specifies hardening of the billing, metering, and Stripe webhook stack based on a steelman security review (2026-03-27) that identified 13 findings across 4 severity tiers. Three independent reviews (original analysis + code-reviewer + security-reviewer subagents) reached consensus on severity and prioritization.

The core architectural change is replacing the current **post-debit fire-and-forget** metering pattern with a **pre-debit reservation pattern** — analogous to credit card pre-authorization. This eliminates two classes of financial integrity bugs (ledger/balance drift and fail-open metering) and aligns with industry standard patterns for prepaid usage-based billing.

**Relationship to existing REQs:**

- **REQ-020** (Token Metering, v0.3): REQ-030 **supersedes** §6.2–6.3 (metering pipeline) and **amends** §2.2 (balance tracking), §7.1 (balance gating), §11 (configuration). All other REQ-020 sections remain authoritative.
- **REQ-021** (Credits & Billing, v0.6): REQ-030 **amends** the balance model by adding a held balance concept, and **amends** §10.3 (configuration matrix — invalid combo rejected in production). All other REQ-021 sections remain authoritative.
- **REQ-029** (Stripe Checkout, v0.3): REQ-030 **amends** §7.1 (webhook routing), §7.3 (refund handler), §4.3 (schema), §6.3 (customer creation), §8.3 (purchase display), §9.4 (frontend redirect), §11.4 (config matrix). All other REQ-029 sections remain authoritative.

When REQ-030 conflicts with earlier documents, **REQ-030 takes precedence** for the sections listed above.

### 1.1 Problem Statement

The current metering architecture has three systemic weaknesses:

1. **Ledger/balance drift:** `MeteringService.record_and_debit()` inserts a `CreditTransaction` before the atomic debit. If the debit fails (insufficient balance after a concurrent request), the transaction record persists but the balance was never reduced. Over time, `SUM(credit_transactions.amount_usd)` diverges from `users.balance_usd`.

2. **Fail-open metering:** Two layers of `except Exception` (in `metering_service.py` and `metered_provider.py`) silently swallow all recording failures. DB errors, pricing misconfigurations, and constraint violations all result in free LLM calls — contradicting REQ-020's fail-closed requirement.

3. **Webhook handler fragility:** The `charge.refunded` handler lacks a savepoint (unlike `checkout.session.completed` which has one), doesn't validate refund amounts against purchase totals, and doesn't guard against null `payment_intent` values.

Additionally, 11 lower-severity findings address configuration validation gaps, display bugs, stale data, and documentation inconsistencies.

### 1.2 Solution

Replace the fire-and-forget post-debit pattern with a **reservation-based metering pipeline**:

1. **Reserve** — Before the LLM call, estimate max cost and atomically hold that amount from the user's available balance
2. **Execute** — Call the LLM provider (outside any DB transaction)
3. **Settle** — After the call, calculate actual cost, atomically: debit the actual amount, release the hold, record the usage
4. **On failure** — If settlement fails, the hold stays (user temporarily over-charged). A background sweep releases stale holds. Over-charges are reconcilable; under-charges (current behavior) are irrecoverable revenue loss.

Separately, harden webhook handlers with savepoints and validation, reject invalid config combinations, and fix display/consistency issues.

### 1.3 Scope

| In Scope | Out of Scope |
|----------|-------------|
| Reservation-based metering pipeline | Subscription/recurring billing |
| `usage_reservations` table + `held_balance_usd` column | New public API endpoints |
| Background stale reservation sweep | Kafka/event streaming infrastructure |
| Webhook handler hardening (refund savepoint, cap, null guard) | New webhook event types beyond `checkout.session.expired` |
| `checkout.session.expired` webhook handler | Stripe Meters API integration |
| Configuration validation (reject invalid combos) | Token counting / tokenizer library |
| Display fixes (`int()` → `round()`, query invalidation) | Streaming LLM metering (deferred — warning only) |
| Documentation fixes (CLAUDE.md, type consistency) | Balance reconciliation admin UI |

### 1.4 Traceability Map

| Source Section | Status | Authoritative Source | Notes |
|----------------|--------|---------------------|-------|
| REQ-020 §2.2 Balance Tracking Strategy | Amended | **REQ-030 §2.1** | Adds `held_balance_usd` to cached balance model |
| REQ-020 §6.2 MeteredLLMProvider Interface | Superseded | **REQ-030 §5.4** | Post-debit `complete()` replaced by reserve-settle pattern |
| REQ-020 §6.3 Recording Logic | Superseded | **REQ-030 §5.2–5.3** | `record_and_debit()` replaced by `reserve()` + `settle()` |
| REQ-020 §7.1 Balance Check Dependency | Amended | **REQ-030 §6.1** | Check uses available balance (`balance - held`) |
| REQ-020 §11 Configuration | Amended | **REQ-030 §9.2** | New reservation config variables |
| REQ-021 §6.7 Balance Crediting SQL | **REQ-021 authoritative** | REQ-021 §6.7 | Unchanged — purchase credits don't use reservation |
| REQ-021 §10.3 Configuration Matrix | Amended | **REQ-030 §9.1** | Invalid combo rejected in production |
| REQ-029 §4.3 stripe_purchases Schema | Amended | **REQ-030 §4.3** | `amount_cents` type alignment |
| REQ-029 §6.3 Customer Creation | Amended | **REQ-030 §8.1** | Savepoint replaces full rollback |
| REQ-029 §7.1 Webhook Endpoint | Amended | **REQ-030 §7.3** | Adds `checkout.session.expired` handler |
| REQ-029 §7.3 charge.refunded Handler | Amended | **REQ-030 §7.2** | Savepoint + cap + null guard |
| REQ-029 §8.3 Purchase History | Amended | **REQ-030 §10.1** | `int()` → `round()` |
| REQ-029 §9.4 Stripe Redirect Handler | Amended | **REQ-030 §10.2** | Invalidate `queryKeys.purchases` |
| REQ-029 §11.4 Configuration Matrix | Amended | **REQ-030 §9.1** | Warn → reject in production |

### 1.5 Findings Register

| ID | Tier | Title | Severity | REQ-030 Section |
|----|------|-------|----------|----------------|
| F-01 | 1 | Ledger/balance drift on failed atomic debit | HIGH-CRITICAL | §5.3 |
| F-02 | 1 | Fail-open metering (double `except Exception`) | HIGH | §5.4 |
| F-03 | 1 | Refund handler missing `begin_nested()` savepoint | HIGH | §7.2a |
| F-04 | 1 | Refund handler doesn't cap at `purchase.amount_cents` | HIGH | §7.2b |
| F-05 | 1 | Refund handler: `payment_intent` can be None | MEDIUM | §7.2c |
| F-06 | 2 | `credits_enabled + !metering_enabled` not rejected in production | MEDIUM | §9.1 |
| F-07 | 2 | No `checkout.session.expired` webhook handler | MEDIUM | §7.3 |
| F-08 | 2 | `int()` truncation in purchase history display | MEDIUM | §10.1 |
| F-09 | 3 | Frontend `queryKeys.purchases` not invalidated on checkout success | LOW | §10.2 |
| F-10 | 3 | `MeteredLLMProvider.stream()` completely unmetered | LOW (dormant) | §5.6 |
| F-11 | 3 | `get_or_create_customer` uses `db.rollback()` instead of savepoint | LOW | §8.1 |
| F-12 | 4 | `grant_cents` BIGINT vs `amount_cents` INTEGER asymmetry | LOW | §4.3 |
| F-13 | 4 | CLAUDE.md error hierarchy docs out of sync | LOW | §10.3 |

---

## 2. Design Decisions

### 2.1 Pre-Debit Reservation Pattern

**Decision:** Replace the current post-debit fire-and-forget pattern with a pre-debit reservation (credit hold) pattern.

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Pre-debit reservation (hold → call → settle) | ✓ | Balance is held before the LLM call. If settlement fails, user is over-charged (reconcilable). If LLM call fails, hold is released. No free calls possible. Industry standard for prepaid billing. |
| B. Post-debit fire-and-forget (current) | — | LLM call executes first, debit attempted after. On failure, user gets free service. Under-charging is irrecoverable revenue loss. |
| C. Synchronous blocking debit before LLM call | — | Requires knowing the exact cost before the call, which is impossible (output tokens are unknown). Would require pessimistic debit of `max_tokens × price` followed by refund of the difference — equivalent to option A but without the explicit reservation concept. |

**Why reservation over post-debit:** The fundamental problem is that LLM calls are irrevocable — once tokens are consumed, you cannot undo the cost. The only question is whether your DB reflects the cost correctly. Post-debit accepts the risk of recording failure; reservation eliminates it by holding funds before the irrevocable action. Research into production billing systems (Stripe Meters, OpenMeter, Orb, LiteLLM, Helicone, Azure API Management, WarpStream) confirms that prepaid billing systems universally use some form of pre-debit hold.

**The industry consensus:** Every production system must choose — over-charge or under-charge on failure? Over-charge (with reconciliation) is preferred because under-charging is irrecoverable revenue loss. The reservation pattern makes this choice explicit.

### 2.2 Reservation State Tracking

**Decision:** Use a separate `usage_reservations` table alongside a cached `held_balance_usd` column on `users`.

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Separate `usage_reservations` table + cached `held_balance_usd` | ✓ | Individual reservations are auditable, stale detection queries are simple, reconciliation can compare table sum with cached column. Mirrors the existing `credit_transactions` + `balance_usd` pattern. |
| B. `held_balance_usd` column only (no individual tracking) | — | Simpler but no visibility into individual holds. Cannot detect which reservation is stale. Cannot audit or reconcile. |

The `held_balance_usd` column on `users` is a cached aggregate — same pattern as `balance_usd` vs `credit_transactions` (REQ-020 §2.2). The `usage_reservations` table is the source of truth for individual holds.

### 2.3 Cost Estimation Strategy

**Decision:** Estimate worst-case cost using `max_tokens × output_price_per_1k / 1000 × margin`.

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. `max_tokens × output_price` ceiling | ✓ | Output tokens dominate cost. `max_tokens` is the upper bound on output (already a parameter of every `complete()` call). No historical data, tokenizer, or per-task tuning required. Over-estimates safely — excess released at settlement. |
| B. Flat per-task-type estimate | — | Requires maintaining per-task estimates that drift as prompts change. Under-estimates are dangerous (same problem we're fixing). |
| C. Historical average per task type | — | Requires accumulating history before working. Cold-start problem. Average can under-estimate for outlier calls. |

**Input token estimation:** Input tokens are unknown before the call (would require a tokenizer library). The estimation uses output tokens only (`max_tokens` ceiling). This over-estimates, which is safe — the excess is released at settlement. If `max_tokens` is `None`, use the provider's `default_max_tokens` from config (currently 4096).

**Estimation formula:**

```python
estimated_cost = (max_tokens / 1000) * output_price_per_1k * margin_multiplier
```

### 2.4 Stale Reservation Handling

**Decision:** Background sweep job releases stale reservations on a configurable interval.

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Background sweep on interval | ✓ | Simple, decoupled from request path, can log/alert. Runs every `RESERVATION_SWEEP_INTERVAL_SECONDS` (default 300). |
| B. On-demand reconciliation at balance check time | — | Adds latency to every balance check. Mixes concerns. |
| C. Database-level TTL (pg_cron) | — | Requires pg_cron extension. Harder to test. Less portable. |

Reservations with status `held` and `created_at` older than `RESERVATION_TTL_SECONDS` (default 300) are released by the sweep. The sweep atomically: decrements `held_balance_usd`, updates reservation status to `stale`, logs at warning level.

### 2.5 Settlement Failure Mode

**Decision:** On settlement failure, the reservation stays in `held` status (fail-closed).

The LLM call has already completed — the user received their response and the tokens are consumed at the provider. If settlement fails:

- **Current behavior (fail-open):** Usage goes unrecorded, user gets free service, revenue lost.
- **New behavior (fail-closed):** Reservation hold stays. User is temporarily over-charged by the estimated amount. The background sweep will eventually release the stale hold, or manual reconciliation can settle it.

This is the conservative choice. Over-charges are visible (user sees lower available balance) and reconcilable. Under-charges are invisible and irrecoverable.

---

## 3. Dependencies

### 3.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-020 Token Metering v0.3 | Foundation | Metering architecture, pricing, balance model |
| REQ-021 Credits & Billing v0.6 | Foundation | Credit transaction model, signup grant, refund semantics |
| REQ-022 Admin Pricing v0.1 | Integration | DB-backed pricing and routing used for cost estimation |
| REQ-029 Stripe Checkout v0.3 | Integration | Webhook handlers, Stripe service, purchase tracking |

### 3.2 Prerequisite Implementation Order

```
REQ-020 ✅ → REQ-022 ✅ → REQ-023 ✅ → REQ-029 ✅ → REQ-030 (this)
```

All prerequisites are complete. This REQ can be implemented immediately.

### 3.3 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-020 Token Metering | Amended sections | §2.2, §6.2–6.3, §7.1, §11 amended by this REQ |
| REQ-021 Credits & Billing | Amended concept | Balance model gains `held_balance_usd` |
| REQ-029 Stripe Checkout | Amended sections | §4.3, §6.3, §7.1, §7.3, §8.3, §9.4, §11.4 amended |

---

## 4. Database Schema

### 4.1 Users Table Amendment

Add `held_balance_usd` column alongside existing `balance_usd`:

```sql
ALTER TABLE users
ADD COLUMN held_balance_usd NUMERIC(10,6) NOT NULL DEFAULT 0.000000;
```

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `held_balance_usd` | `NUMERIC(10,6)` | NOT NULL | `0.000000` | `CHECK (held_balance_usd >= 0)` |

**Semantics:** Sum of all active (status=`held`) reservations. Cached aggregate — `usage_reservations` table is the source of truth. Updated atomically alongside reservation insert/release/settle.

**Available balance:** `balance_usd - held_balance_usd`. This replaces `balance_usd` alone in the gating check (§6.1).

**Amends:** REQ-020 §4.1 (users table), REQ-020 §2.2 (balance tracking strategy).

### 4.2 Usage Reservations Table (New)

```sql
CREATE TABLE usage_reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    estimated_cost_usd NUMERIC(10,6) NOT NULL,
    actual_cost_usd NUMERIC(10,6),
    status VARCHAR(20) NOT NULL DEFAULT 'held',
    task_type VARCHAR(50) NOT NULL,
    provider VARCHAR(20),
    model VARCHAR(100),
    max_tokens INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    settled_at TIMESTAMPTZ,
    CONSTRAINT ck_reservation_status_valid
        CHECK (status IN ('held', 'settled', 'released', 'stale')),
    CONSTRAINT ck_reservation_estimated_positive
        CHECK (estimated_cost_usd > 0),
    CONSTRAINT ck_reservation_actual_nonneg
        CHECK (actual_cost_usd IS NULL OR actual_cost_usd >= 0)
);

CREATE INDEX ix_reservation_user_status
    ON usage_reservations (user_id, status);

CREATE INDEX ix_reservation_stale_sweep
    ON usage_reservations (status, created_at)
    WHERE status = 'held';
```

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `UUID` | NOT NULL | `gen_random_uuid()` | Primary key |
| `user_id` | `UUID` | NOT NULL | — | FK to `users.id` |
| `estimated_cost_usd` | `NUMERIC(10,6)` | NOT NULL | — | Worst-case cost from §2.3 formula |
| `actual_cost_usd` | `NUMERIC(10,6)` | NULL | — | Set at settlement from real token counts |
| `status` | `VARCHAR(20)` | NOT NULL | `'held'` | `held` → `settled` / `released` / `stale` |
| `task_type` | `VARCHAR(50)` | NOT NULL | — | TaskType enum value |
| `provider` | `VARCHAR(20)` | NULL | — | Set at settlement (unknown pre-call for some paths) |
| `model` | `VARCHAR(100)` | NULL | — | Set at settlement (routing resolves model) |
| `max_tokens` | `INTEGER` | NULL | — | Upper bound used for estimation |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | Reservation creation time |
| `settled_at` | `TIMESTAMPTZ` | NULL | — | When settlement or release occurred |

**Status transitions:**

```
held → settled   (normal: LLM call succeeded, actual cost recorded)
held → released  (LLM call failed, provider error/timeout)
held → stale     (background sweep: reservation exceeded TTL without settlement)
```

No transition from `settled`, `released`, or `stale` — these are terminal states.

**Indexes:**
- `ix_reservation_user_status` — supports `require_sufficient_balance` if it ever needs to verify held balance against the table
- `ix_reservation_stale_sweep` — partial index on `status = 'held'` for the background sweep query

### 4.3 Stripe Purchases Type Alignment

Normalize `amount_cents` and `grant_cents` to both use `INTEGER` on `stripe_purchases`:

```sql
ALTER TABLE stripe_purchases
    ALTER COLUMN grant_cents TYPE INTEGER;
```

**Rationale:** `grant_cents` was `BIGINT` while `amount_cents` was `INTEGER` — no practical reason for the asymmetry. Individual purchase amounts will never exceed `INTEGER` range (~$21M). Using the same type eliminates "why are these different?" confusion for future readers.

**Also applies to:** `funding_packs.grant_cents` — same change for consistency.

**Addresses:** F-12 (Tier 4, consistency/readability).

### 4.4 Migration

**File:** `backend/migrations/versions/028_billing_hardening.py`
**Revision chain:** `down_revision = "027_stripe_payment_intent_index"`

**Upgrade operations:**
1. Add `held_balance_usd` column to `users`
2. Create `usage_reservations` table with indexes
3. Alter `grant_cents` from `BIGINT` to `INTEGER` on `stripe_purchases`
4. Alter `grant_cents` from `BIGINT` to `INTEGER` on `funding_packs`

**Downgrade operations:**
1. Alter `grant_cents` back to `BIGINT` on `funding_packs`
2. Alter `grant_cents` back to `BIGINT` on `stripe_purchases`
3. Drop `usage_reservations` table
4. Drop `held_balance_usd` column from `users`

---

## 5. Reservation-Based Metering Pipeline

This section supersedes REQ-020 §6.2–6.3.

### 5.1 Sequence Diagram

```
Endpoint          deps.py              MeteredLLMProvider       MeteringService        Inner Provider
   |                 |                        |                       |                      |
   |  request        |                        |                       |                      |
   |---------------->|                        |                       |                      |
   |                 | require_sufficient_     |                       |                      |
   |                 | balance (available =    |                       |                      |
   |                 | balance - held > 0)     |                       |                      |
   |                 |--- 402 if insufficient  |                       |                      |
   |                 |                        |                       |                      |
   |                 | inject MeteredProvider  |                       |                      |
   |                 |----------------------->|                       |                      |
   |                 |                        | 1. reserve()          |                      |
   |                 |                        |---------------------->|                      |
   |                 |                        |   INSERT reservation  |                      |
   |                 |                        |   UPDATE held_balance |                      |
   |                 |                        |   return reservation  |                      |
   |                 |                        |<----------------------|                      |
   |                 |                        |                       |                      |
   |                 |                        | 2. complete()         |                      |
   |                 |                        |---------------------------------------------->|
   |                 |                        |                       |          LLM API call |
   |                 |                        |<----------------------------------------------|
   |                 |                        |   LLMResponse (tokens)|                      |
   |                 |                        |                       |                      |
   |                 |                        | 3. settle()           |                      |
   |                 |                        |---------------------->|                      |
   |                 |                        |   begin_nested()      |                      |
   |                 |                        |     INSERT usage_rec  |                      |
   |                 |                        |     INSERT credit_txn |                      |
   |                 |                        |     UPDATE balance -  |                      |
   |                 |                        |       actual          |                      |
   |                 |                        |     UPDATE held -     |                      |
   |                 |                        |       estimated       |                      |
   |                 |                        |     UPDATE reservation|                      |
   |                 |                        |       → settled       |                      |
   |                 |                        |<----------------------|                      |
   |                 |                        |                       |                      |
   |  response       |                        |                       |                      |
   |<----------------|                        |                       |                      |
```

**If the LLM call fails (provider error/timeout):**

```
   |                 |                        | 2. complete() → error |                      |
   |                 |                        |                       |                      |
   |                 |                        | release(reservation)  |                      |
   |                 |                        |---------------------->|                      |
   |                 |                        |   UPDATE held -       |                      |
   |                 |                        |     estimated         |                      |
   |                 |                        |   UPDATE reservation  |                      |
   |                 |                        |     → released        |                      |
   |                 |                        |<----------------------|                      |
   |                 |                        |                       |                      |
   |                 |                        | re-raise error        |                      |
```

### 5.2 MeteringService.reserve()

New method on `MeteringService`. Replaces the first half of `record_and_debit()`.

```python
async def reserve(
    self,
    user_id: uuid.UUID,
    task_type: str,
    max_tokens: int | None = None,
) -> UsageReservation:
    """Reserve estimated cost from user's available balance.

    Args:
        user_id: User making the LLM call.
        task_type: Task type for pricing lookup.
        max_tokens: Output token ceiling. Uses provider default if None.

    Returns:
        UsageReservation with status='held'.

    Raises:
        NoPricingConfigError: If no pricing exists for the routed model.
        UnregisteredModelError: If the model is not in the registry.
    """
```

**Steps:**

1. Resolve the routed `(provider, model)` for the task type via `AdminConfigService.get_routing_for_task()`
2. Look up pricing via `AdminConfigService.get_pricing(provider, model)`
3. If `max_tokens` is None, use the provider's `default_max_tokens` from config (4096)
4. Calculate estimated cost: `(max_tokens / 1000) * output_price_per_1k * margin_multiplier`
5. Insert `UsageReservation` row with `status='held'`, `estimated_cost_usd`, `task_type`, `max_tokens`
6. Atomically increment `held_balance_usd`: `UPDATE users SET held_balance_usd = held_balance_usd + :amount WHERE id = :user_id`
7. Flush and return the reservation

**Note:** `reserve()` does NOT check balance sufficiency — that is the job of `require_sufficient_balance` (§6). The reservation always succeeds if the user row exists. This separation keeps concerns clean: gating is at the API layer, reservation is at the service layer.

**Error handling:** If pricing lookup fails (`UnregisteredModelError`, `NoPricingConfigError`), the error propagates. The LLM call never executes. This is **fail-closed** — no reservation, no call, no free service.

### 5.3 MeteringService.settle()

New method. Replaces the second half of `record_and_debit()`.

```python
async def settle(
    self,
    reservation_id: uuid.UUID,
    user_id: uuid.UUID,
    provider: str,
    model: str,
    task_type: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Settle a reservation with actual token counts.

    Atomically: record usage, create debit transaction, debit balance,
    release hold, update reservation status.

    All operations are wrapped in a savepoint (begin_nested). If any
    step fails, the savepoint rolls back — reservation stays 'held'
    (fail-closed). The background sweep will release it.

    Args:
        reservation_id: Reservation to settle.
        user_id: User who made the call.
        provider: Provider that handled the call.
        model: Exact model identifier from the response.
        task_type: Task type for the call.
        input_tokens: Actual input tokens from the response.
        output_tokens: Actual output tokens from the response.
    """
```

**Steps (all within `async with self._db.begin_nested()`):**

1. Look up pricing for `(provider, model)` — same as current `record_and_debit()`
2. Calculate actual cost: `raw_cost = (input_tokens * input_per_1k + output_tokens * output_per_1k) / 1000`, `billed_cost = raw_cost * margin`
3. Insert `LLMUsageRecord` (same fields as current)
4. Insert `CreditTransaction` with `amount_usd = -billed_cost`, `transaction_type = 'usage_debit'`
5. Atomic combined update: `UPDATE users SET balance_usd = balance_usd - :actual, held_balance_usd = held_balance_usd - :estimated WHERE id = :user_id`
6. Update reservation: `status = 'settled'`, `actual_cost_usd = billed_cost`, `provider`, `model`, `settled_at = now()`

**Key fix for F-01:** The savepoint ensures that the `CreditTransaction` insert and the balance debit are atomic. If the debit portion of step 5 causes an error, the savepoint rolls back the `CreditTransaction` insert too. This eliminates the ledger/balance drift.

**Error handling:** If any step inside the savepoint fails, the outer `try/except` catches the exception, logs it at error level, and returns. The reservation stays in `held` status — this is fail-closed behavior (F-02 fix). The double `except Exception` pattern is eliminated.

```python
try:
    async with self._db.begin_nested():
        # steps 1-6
except Exception:
    logger.exception(
        "Settlement failed for reservation %s (user %s) — "
        "hold remains active, background sweep will release",
        reservation_id,
        user_id,
    )
```

### 5.4 MeteredLLMProvider.complete() Rewrite

Supersedes REQ-020 §6.2.

**Current pattern (being replaced):**

```python
# WRONG — post-debit fire-and-forget (REQ-020 §6.2)
response = await adapter.complete(...)
try:
    await self._metering_service.record_and_debit(...)
except Exception:
    logger.exception(...)  # Silently swallowed — free LLM call
return response
```

**New pattern:**

```python
# CORRECT — reservation pattern (REQ-030 §5.4)
routing = await self._admin_config.get_routing_for_task(task.value)
adapter, model_override = self._resolve_adapter(routing)

reservation = await self._metering_service.reserve(
    user_id=self._user_id,
    task_type=task.value,
    max_tokens=max_tokens,
)

try:
    response = await adapter.complete(
        messages, task,
        max_tokens=max_tokens,
        model_override=model_override,
        # ... other kwargs
    )
except Exception:
    await self._metering_service.release(reservation.id, self._user_id)
    raise

await self._metering_service.settle(
    reservation_id=reservation.id,
    user_id=self._user_id,
    provider=adapter.provider_name,
    model=response.model,
    task_type=task.value,
    input_tokens=max(0, response.input_tokens),
    output_tokens=max(0, response.output_tokens),
)

return response
```

**Key changes:**
- `reserve()` is called BEFORE `adapter.complete()` — if reservation fails, the LLM call never happens
- If the LLM call fails, `release()` returns the held amount to the user
- `settle()` wraps all recording in a savepoint — no more ledger drift
- The double `except Exception` is eliminated — errors in `reserve()` propagate (fail-closed), errors in `settle()` leave the hold active (fail-closed)
- **Addresses:** F-01 (ledger drift), F-02 (fail-open metering)

### 5.5 MeteringService.release()

New method for releasing a reservation when the LLM call fails.

```python
async def release(
    self,
    reservation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Release a held reservation (LLM call failed).

    Atomically decrements held_balance_usd and updates reservation
    status to 'released'.
    """
```

**Steps:**

1. `UPDATE users SET held_balance_usd = held_balance_usd - :amount WHERE id = :user_id`
2. Update reservation: `status = 'released'`, `settled_at = now()`
3. Flush

**Error handling:** If release fails, log at error level. The hold stays — background sweep will eventually release it. This is a degraded but safe state (user temporarily over-charged).

### 5.6 MeteredLLMProvider.stream() — Metering Gap

The `stream()` method currently has no metering (F-10). Full stream metering requires accumulating token counts from the stream, which is provider-specific (Claude's `stream.get_final_message()`, OpenAI's `stream_options`).

**For this REQ:** Add a log warning when `stream()` is called with metering enabled:

```python
async def stream(self, messages, task, **kwargs):
    logger.warning(
        "stream() called with metering enabled but stream metering is not "
        "implemented — usage will not be recorded for user %s",
        self._user_id,
    )
    # ... delegate to inner provider unchanged
```

Full stream metering is deferred to a future REQ when a streaming endpoint is added.

**Addresses:** F-10 (Tier 3, latent risk mitigation).

### 5.7 MeteredEmbeddingProvider

The `MeteredEmbeddingProvider.embed()` method also needs the reservation pattern. The flow is analogous:

1. **Reserve:** Estimate cost using `sum(len(text))/4` for input tokens (existing heuristic from REQ-020 §6.5), `output_tokens=0`
2. **Execute:** Call `inner.embed(texts)`
3. **Settle:** Use actual `result.total_tokens` for cost calculation

The same `reserve()` / `settle()` / `release()` methods are reused. The `task_type` is `"embedding"`.

---

## 6. Balance Gating Amendment

Amends REQ-020 §7.1.

### 6.1 Available Balance Formula

Change the balance check in `require_sufficient_balance` (`backend/app/api/deps.py`):

**Current (REQ-020 §7.1):**

```python
result = await db.execute(select(User.balance_usd).where(User.id == user_id))
balance = result.scalar_one_or_none()
if balance is None:
    balance = Decimal("0.000000")
if balance <= threshold:
    raise InsufficientBalanceError(balance=balance, minimum_required=threshold)
```

**New (REQ-030 §6.1):**

```python
result = await db.execute(
    select(User.balance_usd, User.held_balance_usd).where(User.id == user_id)
)
row = result.one_or_none()
if row is None:
    available = Decimal("0.000000")
else:
    available = row.balance_usd - row.held_balance_usd

if available <= threshold:
    raise InsufficientBalanceError(balance=available, minimum_required=threshold)
```

**Key change:** The `InsufficientBalanceError` reports `available` balance (total minus held), not total balance. Users see their spendable balance, not their gross balance including money already reserved for in-flight LLM calls.

---

## 7. Webhook Handler Hardening

### 7.1 Overview

Modifications to `backend/app/services/stripe_webhook_service.py` and `backend/app/api/v1/webhooks.py`.

### 7.2 charge.refunded Handler Fixes

Three changes to `_process_charge_refunded()`. Amends REQ-029 §7.3.

**(a) Savepoint (F-03):**

Wrap the credit creation + balance debit + purchase update in `async with db.begin_nested()`:

```python
async with db.begin_nested():
    await CreditRepository.create(
        db, user_id=purchase.user_id,
        amount_usd=-this_refund_usd,
        transaction_type="refund",
        reference_id=charge["id"],
        stripe_event_id=event_id,
        description=f"Refund — ${this_refund_usd:.2f}",
    )
    new_balance = await CreditRepository.atomic_refund_debit(
        db, user_id=purchase.user_id, amount=this_refund_usd
    )
    await StripePurchaseRepository.mark_refunded(
        db, purchase_id=purchase.id,
        refund_amount_cents=total_refunded_cents,
        is_full_refund=is_full_refund,
    )
```

This matches the pattern already used in `_process_checkout_completed` (line 100). If any step fails, the savepoint rolls back all three operations — no partial state.

**(b) Cap refund total (F-04):**

Add validation before processing:

```python
total_refunded_cents = min(int(charge["amount_refunded"]), purchase.amount_cents)
```

Stripe should never send `amount_refunded > amount`, but this guard prevents over-debit from corrupted or unexpected data.

**(c) Null payment_intent guard (F-05):**

Add early return:

```python
payment_intent_id = charge.get("payment_intent")
if payment_intent_id is None:
    logger.error(
        "charge.refunded event %s has null payment_intent — skipping",
        event_id,
    )
    return
```

Stripe checkout sessions always create a PaymentIntent, but the `charge` object schema has `payment_intent` as nullable (e.g., for legacy direct charges). This guard prevents a `TypeError` that would be silently swallowed by the outer `except Exception`.

### 7.3 checkout.session.expired Handler (F-07)

Add to `backend/app/api/v1/webhooks.py` match statement. Amends REQ-029 §7.1.

```python
match event.type:
    case "checkout.session.completed":
        await handle_checkout_completed(db, event=event)
    case "charge.refunded":
        await handle_charge_refunded(db, event=event)
    case "checkout.session.expired":
        await handle_checkout_expired(db, event=event)
    case _:
        pass
```

**Handler logic** (new function in `stripe_webhook_service.py`):

```python
async def handle_checkout_expired(
    db: AsyncSession,
    *,
    event: stripe_module.Event,
) -> None:
    """Mark a pending purchase as expired when Stripe session expires."""
    try:
        session = event.data.object
        session_id = session["id"]
        await StripePurchaseRepository.mark_expired(db, stripe_session_id=session_id)
    except Exception:
        logger.exception("Error processing checkout.session.expired %s", event.id)
```

**Repository method** (new on `StripePurchaseRepository`):

```python
@staticmethod
async def mark_expired(db: AsyncSession, *, stripe_session_id: str) -> bool:
    """Transition a pending purchase to expired status."""
    stmt = select(StripePurchase).where(
        StripePurchase.stripe_session_id == stripe_session_id,
        StripePurchase.status == "pending",
    )
    result = await db.execute(stmt)
    purchase = result.scalar_one_or_none()
    if purchase is None:
        return False
    purchase.status = "expired"
    await db.flush()
    return True
```

**Schema change:** Add `'expired'` to the `stripe_purchases` status check constraint:

```sql
ALTER TABLE stripe_purchases
    DROP CONSTRAINT ck_stripe_purchases_status_valid;
ALTER TABLE stripe_purchases
    ADD CONSTRAINT ck_stripe_purchases_status_valid
    CHECK (status IN ('pending', 'completed', 'refunded', 'partial_refund', 'expired'));
```

Include in migration 028.

---

## 8. Stripe Service Hardening

### 8.1 get_or_create_customer: Savepoint Fix (F-11)

Amends REQ-029 §6.3.

**Current pattern** (`backend/app/services/stripe_service.py` lines 112-122):

```python
# WRONG — rolls back entire transaction
user.stripe_customer_id = customer.id
try:
    await db.flush()
except IntegrityError:
    await db.rollback()  # Rolls back EVERYTHING
    user = await UserRepository.get_by_id(db, user_id)
```

**New pattern:**

```python
# CORRECT — savepoint scopes the rollback
user.stripe_customer_id = customer.id
try:
    async with db.begin_nested():
        await db.flush()
except IntegrityError:
    # Savepoint rolled back — only the flush is undone
    await db.refresh(user)  # Re-read from DB
    user = await UserRepository.get_by_id(db, user_id)
    if user and user.stripe_customer_id:
        return user.stripe_customer_id
    raise StripeServiceError(_DEFAULT_STRIPE_ERROR_MESSAGE) from None
```

This scopes the rollback to the nested savepoint, preserving any other operations that may have been added to the session earlier in the request lifecycle.

---

## 9. Configuration Hardening

### 9.1 Reject Invalid Config in Production (F-06)

Amends REQ-021 §10.3, REQ-029 §11.4.

In `backend/app/core/config.py` `check_production_security()`, change the `credits_enabled + !metering_enabled` handler:

**Current:**

```python
if self.credits_enabled and not self.metering_enabled:
    logger.warning(
        "Invalid configuration: credits_enabled=True but "
        "metering_enabled=False..."
    )
```

**New:**

```python
if self.credits_enabled and not self.metering_enabled:
    if self.environment == "production":
        raise ValueError(
            "credits_enabled=True requires metering_enabled=True in production. "
            "Users can purchase credits but usage will not be deducted."
        )
    logger.warning(
        "Invalid configuration: credits_enabled=True but "
        "metering_enabled=False..."
    )
```

**Keep the warning** for non-production environments (development, testing) to allow flexible local setups.

### 9.2 New Configuration Variables

| Variable | Type | Default | Required | Notes |
|----------|------|---------|----------|-------|
| `RESERVATION_TTL_SECONDS` | `int` | `300` | No | Stale reservation timeout for background sweep |
| `RESERVATION_SWEEP_INTERVAL_SECONDS` | `int` | `300` | No | Background sweep frequency |

```python
# backend/app/core/config.py — add to Settings class
reservation_ttl_seconds: int = 300
reservation_sweep_interval_seconds: int = 300
```

---

## 10. Display & Consistency Fixes

### 10.1 Purchase History int() Truncation Fix (F-08)

Amends REQ-029 §8.3.

In `backend/app/api/v1/credits.py` line 184:

**Current:**

```python
amount_display=format_usd_display(int(txn.amount_usd * Decimal(100))),
```

**New:**

```python
amount_display=format_usd_display(int(round(txn.amount_usd * Decimal(100)))),
```

`int()` truncates toward zero — `int(Decimal("4.999"))` = 4. `round()` does proper rounding — `round(Decimal("4.999"))` = 5. For financial display, rounding is correct. The `int()` outer call converts the `Decimal` result of `round()` to `int` for the `format_usd_display(cents: int)` signature.

### 10.2 Frontend queryKeys.purchases Invalidation (F-09)

Amends REQ-029 §9.4.

In `frontend/src/components/usage/usage-page.tsx` `StripeRedirectHandler`:

**Current:**

```typescript
if (status === "success") {
    showToast.success("Payment successful! Your balance has been updated.");
    queryClient.invalidateQueries({ queryKey: queryKeys.balance });
}
```

**New:**

```typescript
if (status === "success") {
    showToast.success("Payment successful! Your balance has been updated.");
    queryClient.invalidateQueries({ queryKey: queryKeys.balance });
    queryClient.invalidateQueries({ queryKey: queryKeys.purchases });
}
```

### 10.3 CLAUDE.md Error Hierarchy (F-13)

Update the error handling snippet in `CLAUDE.md`:

**Current:**

```python
class ZentropyError(Exception): ...
class NotFoundError(ZentropyError): ...
class ValidationError(ZentropyError): ...
```

**New (matches `backend/app/core/errors.py`):**

```python
class APIError(Exception): ...
class NotFoundError(APIError): ...
class ValidationError(APIError): ...
```

---

## 11. Background Reconciliation

### 11.1 Stale Reservation Sweep

A background task that runs every `RESERVATION_SWEEP_INTERVAL_SECONDS` (default 300):

```python
async def sweep_stale_reservations(db: AsyncSession) -> int:
    """Release reservations that exceeded TTL without settlement.

    Returns:
        Number of stale reservations released.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.reservation_ttl_seconds)
    stmt = select(UsageReservation).where(
        UsageReservation.status == "held",
        UsageReservation.created_at < cutoff,
    )
    result = await db.execute(stmt)
    stale = result.scalars().all()

    for reservation in stale:
        reservation.status = "stale"
        reservation.settled_at = datetime.now(UTC)
        await db.execute(
            text(
                "UPDATE users SET held_balance_usd = held_balance_usd - :amount "
                "WHERE id = :user_id"
            ),
            {"amount": reservation.estimated_cost_usd, "user_id": reservation.user_id},
        )
        logger.warning(
            "Released stale reservation %s for user %s (held $%s for %s)",
            reservation.id,
            reservation.user_id,
            reservation.estimated_cost_usd,
            reservation.task_type,
        )

    await db.flush()
    return len(stale)
```

**Trigger:** FastAPI lifespan event with `asyncio.create_task` and `asyncio.sleep` loop. Configurable via `RESERVATION_SWEEP_INTERVAL_SECONDS`.

### 11.2 Balance/Ledger Drift Detection

Optional audit check (can run alongside the stale sweep or as a separate admin endpoint):

```sql
SELECT u.id, u.balance_usd,
       COALESCE(SUM(ct.amount_usd), 0) AS ledger_sum,
       u.balance_usd - COALESCE(SUM(ct.amount_usd), 0) AS drift
FROM users u
LEFT JOIN credit_transactions ct ON ct.user_id = u.id
GROUP BY u.id
HAVING ABS(u.balance_usd - COALESCE(SUM(ct.amount_usd), 0)) > 0.000001;
```

Log any drift at error level. This detects existing F-01 drift from before the hardening, as well as any future regressions.

---

## 12. Error Handling

### 12.1 New Error Codes

| Code | HTTP | When |
|------|------|------|
| `RESERVATION_FAILED` | 503 | Pricing lookup failed during reservation (model not registered, no pricing config) |

**Note:** `RESERVATION_FAILED` surfaces the existing `UnregisteredModelError` (503) and `NoPricingConfigError` (503) from the reservation step. These errors already exist in `backend/app/core/errors.py` — they're now raised before the LLM call instead of being swallowed after it.

### 12.2 Removed Error Patterns

The double `except Exception` in `metering_service.py` (line 191) and `metered_provider.py` (line 156) is eliminated. Errors in `reserve()` propagate to the caller. Errors in `settle()` leave the reservation held (logged, not raised).

---

## 13. Security Considerations

### 13.1 Fail-Closed Principle

The reservation pattern is fail-closed at every step:

| Failure Point | Current Behavior (fail-open) | New Behavior (fail-closed) |
|---------------|------------------------------|---------------------------|
| Pricing lookup fails | Error swallowed, free LLM call | Error propagates, no LLM call |
| DB error during recording | Error swallowed, free LLM call | Reservation hold stays, background sweep releases |
| Atomic debit rowcount=0 | CreditTransaction orphaned, ledger drifts | Savepoint rolls back all records |
| LLM call fails | N/A | Reservation released, user not charged |

### 13.2 Financial Integrity Summary

| Finding | Risk | Mitigation |
|---------|------|-----------|
| F-01 Ledger drift | Silent data corruption | Savepoint in `settle()` (§5.3) |
| F-02 Fail-open | Revenue leakage | Reservation pattern eliminates both `except Exception` layers (§5.4) |
| F-03 Refund partial commit | Double-debit on retry | Savepoint in refund handler (§7.2a) |
| F-04 Refund uncapped | Excess balance debit | `min()` cap (§7.2b) |
| F-06 Invalid config | Unlimited free calls | Reject in production (§9.1) |

---

## 14. Files Modified/Created

### 14.1 Backend (New)

| File | Purpose |
|------|---------|
| `backend/app/models/usage_reservation.py` | `UsageReservation` ORM model |
| `backend/migrations/versions/028_billing_hardening.py` | Schema migration |

### 14.2 Backend (Modified)

| File | Change | Findings |
|------|--------|----------|
| `backend/app/models/user.py` | Add `held_balance_usd` column | F-01, F-02 |
| `backend/app/models/stripe.py` | `grant_cents` → `INTEGER`, add `'expired'` to status constraint | F-07, F-12 |
| `backend/app/services/metering_service.py` | Add `reserve()`, `settle()`, `release()`; deprecate `record_and_debit()` | F-01, F-02 |
| `backend/app/providers/metered_provider.py` | Reservation flow in `complete()`; warning in `stream()` | F-02, F-10 |
| `backend/app/repositories/credit_repository.py` | New `atomic_reserve()`, `atomic_settle()` if needed | F-01, F-02 |
| `backend/app/repositories/stripe_repository.py` | Add `mark_expired()` method | F-07 |
| `backend/app/api/deps.py` | Available balance check (`balance - held`) | F-01, F-02 |
| `backend/app/api/v1/webhooks.py` | Add `checkout.session.expired` case | F-07 |
| `backend/app/api/v1/credits.py` | `int()` → `round()` in purchase display | F-08 |
| `backend/app/services/stripe_webhook_service.py` | Refund: savepoint + cap + null guard; new `handle_checkout_expired` | F-03, F-04, F-05, F-07 |
| `backend/app/services/stripe_service.py` | Savepoint in `get_or_create_customer` | F-11 |
| `backend/app/core/config.py` | Reject invalid config combo in production; new reservation vars | F-06 |

### 14.3 Frontend (Modified)

| File | Change | Findings |
|------|--------|----------|
| `frontend/src/components/usage/usage-page.tsx` | Invalidate `queryKeys.purchases` on checkout success | F-09 |

### 14.4 Documentation (Modified)

| File | Change | Findings |
|------|--------|----------|
| `CLAUDE.md` | Fix error hierarchy (`ZentropyError` → `APIError`) | F-13 |
| `docs/requirements/REQ-020_token_metering.md` | Add forward reference to REQ-030 | Traceability |
| `docs/requirements/REQ-021_credits_billing.md` | Add forward reference to REQ-030 | Traceability |
| `docs/requirements/REQ-029-stripe-checkout.md` | Add forward reference to REQ-030 | Traceability |

---

## 15. Testing Requirements

### 15.1 Unit Tests

| Test Area | Key Scenarios | Findings |
|-----------|---------------|----------|
| `MeteringService.reserve()` | Inserts reservation + increments `held_balance`; returns reservation ID; pricing lookup failure propagates (no reservation created) | F-01, F-02 |
| `MeteringService.settle()` | Calculates actual cost; savepoint wraps all operations; settlement failure leaves hold active (fail-closed); reservation status updated to `settled` | F-01 |
| `MeteringService.release()` | Decrements `held_balance`; updates status to `released`; release failure logged (hold stays) | F-02 |
| `MeteredLLMProvider.complete()` | Reserve → call → settle happy path; reserve → call fails → release path; reserve fails → no call (error propagates) | F-02 |
| `MeteredLLMProvider.stream()` | Logs warning when metering enabled | F-10 |
| `MeteredEmbeddingProvider.embed()` | Reserve → embed → settle flow with token estimation | F-02 |
| `handle_charge_refunded` | Savepoint rolls back on partial failure; refund capped at `amount_cents`; null `payment_intent` returns early | F-03, F-04, F-05 |
| `handle_checkout_expired` | Updates purchase status to `expired`; no balance change; idempotent (already non-pending is no-op) | F-07 |
| `get_or_create_customer` | Savepoint on IntegrityError (not full rollback); winner's customer ID returned | F-11 |
| `config.check_production_security` | Rejects `credits + !metering` in production; warns in development | F-06 |
| `get_purchases` | Uses `round()` not `int()` for display amounts | F-08 |
| `require_sufficient_balance` | Uses `balance - held` for available balance; held balance reduces available | F-01, F-02 |
| `sweep_stale_reservations` | Releases reservations older than TTL; decrements `held_balance`; counts released | F-01, F-02 |

### 15.2 Integration Tests

| Test Area | Key Scenarios |
|-----------|---------------|
| Reservation lifecycle | Reserve → complete → settle → balance correct, reservation `settled` |
| Reservation release | Reserve → provider error → release → balance restored, reservation `released` |
| Concurrent reservations | Two concurrent reserves → both succeed → one settles, one released → balances correct |
| Stale reservation sweep | Create old `held` reservation → sweep → status=`stale`, `held_balance` decremented |
| Ledger integrity | After reservation cycle, `SUM(credit_transactions) == balance_usd` |
| Refund with savepoint | Partial refund failure → ledger and balance unchanged (savepoint rollback) |
| Expired checkout | Create pending purchase → send expired event → status=`expired` |

### 15.3 Mocking Strategy

| Component | Mock Approach |
|-----------|---------------|
| `AdminConfigService` | Mock `get_pricing()` and `get_routing_for_task()` for cost estimation |
| LLM Provider | Mock `adapter.complete()` to control success/failure/token counts |
| Stripe SDK | Mock `stripe.Webhook.construct_event()` for webhook tests |
| Database | Use real async test DB with transaction fixtures (existing pattern) |

---

## 16. Open Questions

| # | Question | Context | Recommendation |
|---|----------|---------|----------------|
| 1 | Should `record_and_debit()` be removed or kept as deprecated? | Removing simplifies the codebase. Keeping allows gradual migration if any code path still calls it directly. | Remove. All call paths go through `MeteredLLMProvider`/`MeteredEmbeddingProvider`. |
| 2 | Should the stale sweep run as a FastAPI background task or a separate process? | Background task is simpler (no new infrastructure). Separate process is more robust for production. | FastAPI background task for MVP. Separate process can be added when deploying to Render. |
| 3 | Should the cost estimation include input tokens? | Input tokens are unknown pre-call (would require a tokenizer). Including a fixed estimate per task type would tighten the estimate but adds maintenance. | Output-only ceiling for MVP. Input estimation can be added later if over-estimation is excessive. |
| 4 | Should the balance/ledger drift check be a scheduled job or an admin endpoint? | A scheduled job is proactive. An admin endpoint is on-demand. | Both — scheduled job logs drift, admin endpoint shows current state. |

---

## 17. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-27 | 0.1 | Initial version. Addresses 16 findings from steelman billing/metering review. Core change: reservation-based metering pattern replacing post-debit fire-and-forget. Amends REQ-020 §2.2, §6.2–6.3, §7.1, §11; REQ-029 §4.3, §6.3, §7.1, §7.3, §8.3, §9.4, §11.4; REQ-021 balance model. |
