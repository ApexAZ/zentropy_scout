# REQ-029: Stripe Checkout Integration

**Status:** Not Started
**Version:** 0.2
**PRD Reference:** §6 Technical Architecture
**Backlog Item:** #13
**Last Updated:** 2026-03-10

---

## 1. Overview

This document specifies the Stripe Checkout integration for Zentropy Scout's "Add Funds" purchase flow. Users select a funding pack, pay via Stripe's hosted checkout page, and receive a USD balance grant confirmed by webhook.

**Relationship to REQ-021:** REQ-021 (Credits & Billing, v0.6) was the original specification for this feature. REQ-029 **supersedes specific sections** of REQ-021 with updated Stripe SDK patterns and additional infrastructure. When REQ-021 and REQ-029 conflict, **REQ-029 takes precedence**. See §1.4 below for the precise traceability map.

**Scope boundary:** This REQ covers Stripe as a payment rail only — checkout sessions, webhooks, refunds, purchase history, and Stripe Customer management. Pricing configuration and margin multipliers are specified in REQ-022. Pack definitions and USD-direct billing are specified in REQ-023. Metering and balance gating are specified in REQ-020.

### 1.1 Problem Statement

The metering infrastructure (REQ-020) gates LLM calls behind a USD balance check (402 Payment Required), but no mechanism exists for users to add funds. Without a purchase flow:

1. **No revenue** — Users cannot pay for the service
2. **Zero balance on signup** — New users are immediately gated after exhausting their signup grant ($0.10)
3. **No self-service** — Balance can only be changed via admin grants or database operations

### 1.2 Solution

A Stripe Checkout (hosted redirect) integration where:

1. User clicks "Add Funds" on a funding pack ($5 / $10 / $15)
2. Backend creates a Stripe Checkout Session via the `StripeClient` SDK
3. User completes payment on Stripe's hosted page (card data never touches our servers)
4. Stripe sends a `checkout.session.completed` webhook
5. Backend verifies the webhook signature, then atomically credits the user's USD balance
6. User sees updated balance on return to the credits page

### 1.3 Scope

| In Scope | Out of Scope |
|----------|-------------|
| Stripe Checkout (hosted redirect mode) | Stripe Elements / embedded card forms |
| "Add Funds" pack purchase flow | Custom amounts / pay-what-you-want |
| One-time purchases | Subscriptions / recurring billing |
| Webhook handling (signature verified) | Stripe Connect / marketplace payouts |
| Idempotent webhook processing | Invoice generation |
| Stripe Customer creation per user | Saved payment methods / card-on-file |
| Purchase history API + frontend | Admin refund UI (manual via Stripe Dashboard) |
| Refund webhook handling | Mobile payments (Apple Pay, Google Pay) |
| Low-balance frontend warning | Tax calculation (deferred — see §14) |

### 1.4 Traceability Map (REQ-021 → REQ-029)

| REQ-021 Section | Status | Authoritative Source | Notes |
|-----------------|--------|---------------------|-------|
| §1 Overview | Superseded | **REQ-029 §1** | REQ-029 adds scope items (low-balance warning, `stripe_purchases` table) |
| §2.1–2.6 Design Decisions | **REQ-021 authoritative** | REQ-021 §2 | Full decision rationale with alternatives analysis. REQ-029 §2 summarizes and adds §2.1 (StripeClient pattern, new). |
| §3 Dependencies | Superseded | **REQ-029 §3** | REQ-029 marks all prereqs as ✅ |
| §4.1–4.2 DB Schema (users, credit_transactions) | Aligned | Both identical | Same columns, same types, same constraints |
| §4.3 Funding Packs Table | **REQ-021 authoritative** | REQ-021 §4.3 | Reference schema. REQ-029 does not re-specify. Fixed in REQ-021 v0.6: `stripe_price_id` is nullable. |
| §4.4 Transaction Type | Aligned | Both identical | Both add `signup_grant` |
| §5 Funding Packs (definitions, Stripe Price setup) | **REQ-021 authoritative** | REQ-021 §5 | Pack definitions, Stripe fee analysis, Product/Price setup instructions |
| §6.1 New Files | Superseded | **REQ-029 §15** | REQ-029 adds `stripe_client.py`, `stripe.py` model, `stripe_repository.py` |
| §6.2 StripeService (class design) | Superseded | **REQ-029 §6–7** | REQ-029 uses `StripeClient` DI + repository pattern instead of DB-session-coupled class |
| §6.3 Checkout Session Metadata | Aligned | Both identical | Same metadata keys: `user_id`, `pack_id`, `grant_cents` |
| §6.4 Webhook Processing | Superseded | **REQ-029 §7.1** | REQ-029 uses `match/case`, adds `payment_status` check, adds `stripe_purchases` update |
| §6.5 SDK Configuration | **Superseded** | **REQ-029 §5.2** | **Key change:** `StripeClient` replaces deprecated `stripe.api_key` global |
| §6.6 Error Handling | **REQ-021 authoritative** | REQ-021 §6.6 | 7 detailed error scenarios. REQ-029 §13 summarizes. |
| §6.7 Balance Crediting (SQL) | **REQ-021 authoritative** | REQ-021 §6.7 | Raw SQL reference for atomic INSERT + UPDATE |
| §6.8 `reference_id` Type Amendment | **REQ-021 authoritative** | REQ-021 §6.8 | Documents `reference_id` VARCHAR(255) change and per-type values |
| §7 API Endpoints | Aligned | Both identical | Same routes, same request/response shapes, same error codes |
| §8 Signup Grant Flow | **REQ-021 authoritative** | REQ-021 §8 | Full integration points (file paths, line numbers), idempotency, existing user migration |
| §9.1 Credits Page Layout | Superseded | **REQ-029 §9.1** | REQ-029 adds funding packs section and purchase history |
| §9.2–9.3 Frontend Flow (checkout, success/cancel) | **REQ-021 authoritative** | REQ-021 §9.2–9.3 | Detailed Suspense, query key, toast patterns. REQ-029 §9.3–9.4 summarizes. |
| §10 Configuration | Superseded | **REQ-029 §11** | REQ-029 drops `STRIPE_PUBLISHABLE_KEY` requirement for hosted redirect |
| §10.3 Configuration Matrix | **REQ-021 authoritative** | REQ-021 §10.3 | `METERING_ENABLED` × `CREDITS_ENABLED` behavior matrix |
| §11 Security | Aligned | Both cover same topics | REQ-029 §10 is self-contained; REQ-021 §11.2 has deeper rate-limiting rationale |
| §12 Error Handling (codes, Stripe mapping) | **REQ-021 authoritative** | REQ-021 §12 | Detailed Stripe error → user message mapping |
| §13 Testing | Superseded | **REQ-029 §16** | REQ-029 adds `stripe_purchases` tests, frontend component tests |
| §14 Dependency (`stripe` package) | Superseded | **REQ-029 §5.1** | REQ-029 specifies `stripe[async]>=14.0.0,<15.0.0` |
| §15 Resolved Questions | **REQ-021 authoritative** | REQ-021 §15 | 6 resolved questions with decisions and rationale |
| — (new) `stripe_purchases` table | New in REQ-029 | **REQ-029 §4.3** | Session lifecycle tracking, not in REQ-021 |
| — (new) Low-balance warning | New in REQ-029 | **REQ-029 §9.5** | Frontend warning component, not in REQ-021 |
| — (new) StripeClient DI pattern | New in REQ-029 | **REQ-029 §5.2** | FastAPI dependency injection, not in REQ-021 |

**Reading order for implementers:** Start with REQ-029 (implementation spec). Cross-reference REQ-021 for: design rationale (§2), signup grant integration points (§8.2), detailed error scenarios (§6.6, §12), `reference_id` semantics (§6.8), configuration matrix (§10.3), and resolved questions (§15).

---

## 2. Design Decisions

### 2.1 SDK Pattern: StripeClient (Not Global State)

**Decision:** Use the `StripeClient` class, not the deprecated global `stripe.api_key` pattern.

The legacy pattern (`stripe.api_key = "sk_..."`) uses mutable global state and is being deprecated. The `StripeClient` pattern provides per-instance configuration, is thread-safe, and will be the only supported pattern in future SDK versions.

```python
# CORRECT — StripeClient (REQ-029)
from stripe import StripeClient
client = StripeClient(settings.stripe_secret_key.get_secret_value())
session = await client.checkout.sessions.create_async(...)

# WRONG — Deprecated global state (REQ-021 §6.5)
import stripe
stripe.api_key = settings.stripe_secret_key.get_secret_value()
session = await stripe.checkout.Session.create_async(...)
```

**Async support:** The SDK provides async methods by appending `_async` to any method name. The async client uses `httpx` internally, compatible with FastAPI's event loop. Install with `stripe[async]` extra to pull in `httpx`.

**Note on REQ-021:** REQ-021 §6.5 specifies the deprecated global pattern. This REQ supersedes that section.

### 2.2 Checkout Mode: Hosted Redirect

**Decision:** Stripe Checkout in hosted redirect mode (same as REQ-021 §2.1).

User is redirected to `checkout.stripe.com` where Stripe handles the entire payment form, card validation, 3D Secure challenges, and fraud detection. Our PCI responsibility is SAQ A (minimal — see §10.1).

### 2.3 Stripe Customer: Create on First Purchase

**Decision:** Create a Stripe Customer object on the user's first purchase (same as REQ-021 §2.3).

- Store `stripe_customer_id` (`cus_xxx`) on the `users` table
- On subsequent purchases, pass the existing customer ID to pre-fill email and show prior payment methods
- Store `user_id` in Stripe Customer metadata for bidirectional lookup
- Do NOT create customers at registration (avoids orphan records for users who never pay)

### 2.4 Webhook Idempotency: Event ID on credit_transactions

**Decision:** Store `stripe_event_id` (`evt_xxx`) on `credit_transactions` with a UNIQUE constraint (same as REQ-021 §2.4).

Stripe may deliver the same webhook multiple times (network retries, catch-up after downtime). The unique constraint prevents double-crediting at the database level.

### 2.5 Refund Handling: Webhook-Driven Debit

**Decision:** Refunds are initiated manually via Stripe Dashboard. The `charge.refunded` webhook automatically debits the user's balance (same as REQ-021 §2.6).

- Full refund: debit the entire grant amount
- Partial refund: debit proportional to the refund amount
- If balance goes negative after refund, log a warning (user already spent the funds)
- Newer events (`refund.created`, `refund.updated`, `refund.failed`) are available for granular tracking but not required for MVP — `charge.refunded` is sufficient

### 2.6 Stripe Price IDs: Stored in Database

**Decision:** Stripe Price IDs are stored in the `funding_packs.stripe_price_id` column, not in environment variables (same as REQ-021 §5.2).

Each funding pack maps to a Stripe Product/Price pair created in the Stripe Dashboard. The admin configures the Price ID via the admin UI. Test and live mode have different Price IDs — the admin sets the appropriate IDs per environment.

**Note:** `funding_packs.stripe_price_id` is nullable in the current schema (packs exist without Stripe configuration until this REQ is implemented). The checkout endpoint must validate that the selected pack has a non-null `stripe_price_id` before creating a session — return `INVALID_PACK_ID` (400) if null. See REQ-021 §4.3 for the full table schema.

---

## 3. Dependencies

### 3.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-020 Token Metering v0.5 | Foundation | `credit_transactions` table, `balance_usd` column, balance API, metering pipeline |
| REQ-022 Admin Pricing | Foundation | `funding_packs` table, `system_config` table, admin auth |
| REQ-023 USD-Direct Billing | Foundation | Corrected seed data (USD cents), `signup_grant_cents` config key, `grant_cents` column |
| REQ-005 Database Schema | Schema | `users` table to extend with `stripe_customer_id` |
| REQ-006 API Contract | Integration | Response envelope, error codes |
| REQ-013 Authentication | Integration | `CurrentUserId` dependency, user creation flow |

### 3.2 Prerequisite Implementation Order

```
REQ-020 (metering) ✅ → REQ-022 (admin pricing) ✅ → REQ-023 (USD-direct billing) ✅ → REQ-029 (this)
```

All prerequisites are complete. This REQ can be implemented immediately.

### 3.3 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-012 Frontend | Integration | Credits page, "Add Funds" buttons |

---

## 4. Database Schema

### 4.1 Users Table Extension

Add one column to the existing `users` table:

```sql
ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(255) UNIQUE;
```

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `stripe_customer_id` | `VARCHAR(255)` | NULL | NULL | Stripe Customer ID (`cus_xxx`). Created on first purchase. Unique constraint prevents duplicate customers per user. |

### 4.2 Credit Transactions Extension

Add one column to the `credit_transactions` table:

```sql
ALTER TABLE credit_transactions ADD COLUMN stripe_event_id VARCHAR(255) UNIQUE;
```

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `stripe_event_id` | `VARCHAR(255)` | NULL | NULL | Stripe event ID (`evt_xxx`). Unique constraint prevents double-crediting from duplicate webhooks. Only populated for `purchase` and `refund` transaction types. |

### 4.3 Stripe Purchases Table (New)

Track Stripe checkout sessions and their fulfillment status for audit and debugging:

```sql
CREATE TABLE stripe_purchases (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id),
    pack_id             UUID NOT NULL REFERENCES funding_packs(id),
    stripe_session_id   VARCHAR(255) NOT NULL UNIQUE,  -- cs_xxx
    stripe_customer_id  VARCHAR(255) NOT NULL,          -- cus_xxx
    stripe_payment_intent VARCHAR(255),                 -- pi_xxx (from webhook)
    amount_cents        INTEGER NOT NULL,               -- price in cents at time of purchase
    grant_cents         BIGINT NOT NULL,                -- grant amount at time of purchase
    currency            VARCHAR(3) NOT NULL DEFAULT 'usd',
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending | completed | refunded | partial_refund
    completed_at        TIMESTAMPTZ,                    -- when webhook confirmed payment
    refunded_at         TIMESTAMPTZ,                    -- when refund webhook received
    refund_amount_cents INTEGER DEFAULT 0,              -- cumulative refund amount
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_stripe_purchases_user ON stripe_purchases(user_id);
CREATE INDEX ix_stripe_purchases_status ON stripe_purchases(status) WHERE status = 'pending';
```

**Why a separate table?** The `credit_transactions` table is the append-only ledger (immutable). `stripe_purchases` tracks the lifecycle of a Stripe session — from creation through completion to potential refund — with mutable status. This separation keeps the ledger clean while providing full Stripe audit context.

**Snapshot fields:** `amount_cents` and `grant_cents` are captured at checkout session creation time, not looked up from `funding_packs`. This protects against admin pack changes between session creation and webhook delivery.

### 4.4 `reference_id` Semantics

The `credit_transactions.reference_id` column (`VARCHAR(255)`, changed from UUID by REQ-020 v0.3 for Stripe ID compatibility) stores the external reference for each transaction type:

| Transaction Type | `reference_id` Value | Example |
|-----------------|---------------------|---------|
| `purchase` | Stripe Checkout Session ID | `cs_test_a1b2c3...` |
| `usage_debit` | `llm_usage_records.id` (UUID as string) | `550e8400-e29b-...` |
| `refund` | Stripe Charge ID | `ch_3abc...` |
| `signup_grant` | NULL | — |
| `admin_grant` | NULL | — |

See REQ-021 §6.8 for the full amendment history.

### 4.5 Transaction Type Extension

REQ-020 defines `transaction_type` as `VARCHAR(20)` with values: `purchase`, `usage_debit`, `admin_grant`, `refund`.

This REQ adds:
- `signup_grant` — Free balance granted on account creation (12 characters, fits in VARCHAR(20))

### 4.6 Migration

**File:** `backend/migrations/versions/025_stripe_checkout.py`

```python
revision: str = "025_stripe_checkout"
down_revision: str = "024_gemini_embedding_dimensions"
```

Operations:
1. Add `stripe_customer_id` column to `users` (VARCHAR(255), nullable, unique)
2. Add `stripe_event_id` column to `credit_transactions` (VARCHAR(255), nullable, unique)
3. Create `stripe_purchases` table with indexes
4. Insert `signup_grant` transaction for all existing users who don't have one (data migration)

Downgrade:
1. Drop `stripe_purchases` table and indexes
2. Remove `stripe_event_id` column from `credit_transactions`
3. Remove `stripe_customer_id` column from `users`
4. Delete `signup_grant` transactions (data rollback)

---

## 5. Stripe SDK Integration

### 5.1 Python Dependency

```toml
# backend/pyproject.toml
stripe = {version = ">=14.0.0,<15.0.0", extras = ["async"]}
```

The `[async]` extra pulls in `httpx` for async HTTP support. Without it, async methods fall back to sync execution in a thread pool.

**Current SDK version:** v14.4.0 (as of March 2026). Pin to `>=14.0.0,<15.0.0` to stay within the v14 major version.

### 5.2 StripeClient Configuration

```python
# backend/app/core/stripe_client.py
from stripe import StripeClient

from backend.app.core.config import settings


def get_stripe_client() -> StripeClient:
    """Create a StripeClient instance for Stripe API calls.

    Uses the STRIPE_SECRET_KEY env var. The StripeClient pattern
    avoids mutable global state (no stripe.api_key assignment).
    """
    return StripeClient(
        api_key=settings.stripe_secret_key.get_secret_value(),
        stripe_version="2025-12-18.preview",  # Pin API version
    )
```

**API version pinning:** The `stripe_version` parameter locks the API behavior regardless of the Stripe Dashboard's default API version. Update intentionally with testing, not as a surprise from Stripe's rolling updates.

**FastAPI dependency injection:**

```python
from stripe import StripeClient

StripeClientDep = Annotated[StripeClient, Depends(get_stripe_client)]
```

### 5.3 Webhook Signature Verification

Webhook signature verification uses the **module-level** function (not `StripeClient`):

```python
import stripe

event = stripe.Webhook.construct_event(
    payload=raw_body,      # bytes from request.body()
    sig_header=sig_header,  # Stripe-Signature header
    secret=settings.stripe_webhook_secret.get_secret_value(),
)
```

**Critical:** The `payload` must be the raw request body bytes (`await request.body()`), NOT parsed JSON. Letting FastAPI parse the body first breaks the HMAC signature.

**Timestamp tolerance:** The SDK rejects events older than 300 seconds (5 minutes) by default. This prevents replay attacks.

---

## 6. Checkout Session Flow

### 6.1 Sequence Diagram

```
User            Frontend           Backend              Stripe
 |                 |                  |                    |
 |  Click "Add     |                  |                    |
 |  Funds ($10)"   |                  |                    |
 |---------------->|                  |                    |
 |                 |  POST /credits/  |                    |
 |                 |  checkout        |                    |
 |                 |  {pack_id: ...}  |                    |
 |                 |----------------->|                    |
 |                 |                  |  Look up pack      |
 |                 |                  |  Get/create customer|
 |                 |                  |  create_async()    |
 |                 |                  |------------------->|
 |                 |                  |  Session URL       |
 |                 |                  |<-------------------|
 |                 |  {checkout_url}  |                    |
 |                 |<-----------------|                    |
 |  Redirect to    |                  |                    |
 |  Stripe         |                  |                    |
 |<----------------|                  |                    |
 |                 |                  |                    |
 |  Complete       |                  |                    |
 |  payment on     |                  |                    |
 |  Stripe page    |                  |                    |
 |------------------------------------>                    |
 |                 |                  |                    |
 |  Redirect to    |                  |  Webhook:          |
 |  success URL    |                  |  checkout.session  |
 |<------------------------------------|  .completed       |
 |                 |                  |<-------------------|
 |                 |                  |  Verify signature  |
 |                 |                  |  Credit balance    |
 |                 |                  |  Return 200        |
 |                 |                  |------------------->|
 |  Show success   |                  |                    |
 |  toast          |                  |                    |
 |<----------------|                  |                    |
```

### 6.2 Checkout Session Creation

**Endpoint:** `POST /api/v1/credits/checkout`

```python
async def create_checkout_session(
    user_id: UUID,
    user_email: str,
    pack: FundingPack,
    stripe_client: StripeClient,
    db: AsyncSession,
) -> str:
    """Create a Stripe Checkout Session and return the URL.

    Steps:
    1. Get or create Stripe Customer for this user
    2. Create Checkout Session with pack's Stripe Price ID
    3. Record the pending purchase in stripe_purchases
    4. Return session.url for frontend redirect
    """
    # 1. Get or create customer
    customer_id = await get_or_create_customer(user_id, user_email, stripe_client, db)

    # 2. Create checkout session
    session = await stripe_client.checkout.sessions.create_async(
        customer=customer_id,
        line_items=[{"price": pack.stripe_price_id, "quantity": 1}],
        mode="payment",
        success_url=f"{settings.frontend_url}/usage?status=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.frontend_url}/usage?status=cancelled",
        metadata={
            "user_id": str(user_id),
            "pack_id": str(pack.id),
            "grant_cents": str(pack.grant_cents),
        },
    )

    # 3. Record pending purchase
    # ... insert into stripe_purchases with status='pending'

    return session.url
```

**Metadata:** The `grant_cents` value is captured in session metadata at creation time. The webhook uses this value (not the current pack definition) to determine the grant amount. This protects against admin pack changes between session creation and payment completion.

**`{CHECKOUT_SESSION_ID}` template:** This is a Stripe template variable — do NOT interpolate it. In an f-string, use double braces (`{{CHECKOUT_SESSION_ID}}`). Stripe replaces it with the actual session ID (e.g., `cs_test_a1b2c3...`) during redirect.

### 6.3 Customer Management

```python
async def get_or_create_customer(
    user_id: UUID,
    email: str,
    stripe_client: StripeClient,
    db: AsyncSession,
) -> str:
    """Look up or create a Stripe Customer, return customer ID.

    1. Check users.stripe_customer_id
    2. If exists, return it
    3. If not, create via Stripe API with user metadata
    4. Save to users table, return it
    """
    # Check for existing customer ID
    result = await db.execute(
        select(User.stripe_customer_id).where(User.id == user_id)
    )
    existing_id = result.scalar_one_or_none()
    if existing_id:
        return existing_id

    # Create new customer
    customer = await stripe_client.customers.create_async(
        email=email,
        metadata={"zentropy_user_id": str(user_id)},
    )

    # Save customer ID to users table
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(stripe_customer_id=customer.id)
    )
    await db.flush()

    return customer.id
```

---

## 7. Webhook Handler

### 7.1 Endpoint

**Route:** `POST /api/v1/webhooks/stripe`

The webhook endpoint is **public** (no auth). Security comes from Stripe signature verification, not JWT authentication.

```python
@router.post("/stripe")
async def stripe_webhook(request: Request, db: DbSession) -> dict:
    """Handle Stripe webhook events.

    1. Read raw request body (bytes, not parsed JSON)
    2. Verify Stripe-Signature header
    3. Route to appropriate handler
    4. Return 200 OK (Stripe retries on non-2xx)
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header,
            settings.stripe_webhook_secret.get_secret_value(),
        )
    except ValueError:
        raise APIError(code="INVALID_PAYLOAD", message="Invalid webhook payload", status_code=400)
    except stripe.SignatureVerificationError:
        raise APIError(code="INVALID_SIGNATURE", message="Invalid webhook signature", status_code=401)

    stripe_service = StripeService(db)

    match event.type:
        case "checkout.session.completed":
            await stripe_service.handle_checkout_completed(event)
        case "charge.refunded":
            await stripe_service.handle_charge_refunded(event)
        case _:
            pass  # Ignore unhandled events (return 200 to stop retries)

    return {"received": True}
```

**Rate limiting exemption:** The webhook endpoint is exempt from `slowapi` rate limiting. Stripe may send bursts of webhooks (batch refunds, catch-up retries). Signature verification provides sufficient security. See REQ-021 §11.2 for full rationale.

### 7.2 `checkout.session.completed` Handler

```python
async def handle_checkout_completed(self, event: stripe.Event) -> None:
    """Process completed checkout — credit the user's balance.

    Idempotent: duplicate events (same event.id) are safely skipped
    via the UNIQUE constraint on credit_transactions.stripe_event_id.
    """
    session = event.data.object
    event_id = event.id                        # evt_xxx
    session_id = session.id                    # cs_xxx
    customer_id = session.customer             # cus_xxx
    payment_intent = session.payment_intent    # pi_xxx
    payment_status = session.payment_status    # "paid"

    # Only process paid sessions
    if payment_status != "paid":
        logger.warning("Checkout session %s has status %s, skipping", session_id, payment_status)
        return

    # Extract metadata (set during session creation)
    user_id = UUID(session.metadata["user_id"])
    pack_id = UUID(session.metadata["pack_id"])
    grant_cents = int(session.metadata["grant_cents"])
    grant_usd = Decimal(grant_cents) / Decimal(100)

    # Idempotency check
    existing = await self._credit_repo.find_by_stripe_event_id(event_id)
    if existing:
        return  # Already processed

    # Validate user exists
    user = await self._user_repo.get_by_id(user_id)
    if not user:
        logger.error("User %s not found for checkout session %s", user_id, session_id)
        return  # Return 200 to stop retries — manual investigation needed

    # Credit the balance (atomic: insert transaction + update balance)
    await self._credit_repo.create_transaction(
        user_id=user_id,
        amount_usd=grant_usd,
        transaction_type="purchase",
        reference_id=session_id,
        stripe_event_id=event_id,
        description=f"Funding pack purchase",
    )
    await self._user_repo.credit_balance(user_id, grant_usd)

    # Update stripe_purchases record
    await self._purchase_repo.mark_completed(
        stripe_session_id=session_id,
        stripe_payment_intent=payment_intent,
    )
```

**Event payload key fields (`checkout.session.completed`):**

| Field | Example | Notes |
|-------|---------|-------|
| `event.id` | `evt_1abc...` | Unique event ID (idempotency key) |
| `event.data.object.id` | `cs_test_...` | Checkout Session ID |
| `event.data.object.customer` | `cus_abc...` | Stripe Customer ID |
| `event.data.object.payment_intent` | `pi_abc...` | PaymentIntent ID |
| `event.data.object.payment_status` | `"paid"` | `"paid"`, `"unpaid"`, `"no_payment_required"` |
| `event.data.object.amount_total` | `1000` | Total in cents |
| `event.data.object.currency` | `"usd"` | ISO currency code |
| `event.data.object.metadata` | `{...}` | Our custom metadata |

**Note:** `line_items` is NOT included in the webhook payload by default. Our metadata carries all the information needed for fulfillment.

### 7.3 `charge.refunded` Handler

```python
async def handle_charge_refunded(self, event: stripe.Event) -> None:
    """Process a refund — debit the user's balance.

    Handles both full and partial refunds. Uses the charge's
    amount_refunded field for cumulative refund tracking.
    """
    charge = event.data.object
    event_id = event.id
    payment_intent_id = charge.payment_intent  # pi_xxx
    customer_id = charge.customer               # cus_xxx

    # Idempotency check
    existing = await self._credit_repo.find_by_stripe_event_id(event_id)
    if existing:
        return

    # Find the original purchase by payment_intent
    purchase = await self._purchase_repo.find_by_payment_intent(payment_intent_id)
    if not purchase:
        logger.error("No purchase found for payment_intent %s", payment_intent_id)
        return

    # Calculate this refund's amount
    # charge.amount_refunded is cumulative; compare with our tracked refund total
    total_refunded_cents = charge.amount_refunded
    previous_refunded_cents = purchase.refund_amount_cents or 0
    this_refund_cents = total_refunded_cents - previous_refunded_cents
    this_refund_usd = Decimal(this_refund_cents) / Decimal(100)

    if this_refund_cents <= 0:
        logger.warning("No new refund amount for charge %s", charge.id)
        return

    # Debit balance (negative amount_usd)
    await self._credit_repo.create_transaction(
        user_id=purchase.user_id,
        amount_usd=-this_refund_usd,
        transaction_type="refund",
        reference_id=charge.id,
        stripe_event_id=event_id,
        description=f"Refund — ${this_refund_usd:.2f}",
    )
    await self._user_repo.debit_balance(purchase.user_id, this_refund_usd)

    # Update purchase record
    is_full_refund = charge.refunded  # True only if fully refunded
    await self._purchase_repo.mark_refunded(
        purchase_id=purchase.id,
        refund_amount_cents=total_refunded_cents,
        is_full_refund=is_full_refund,
    )

    # Warn if balance went negative
    new_balance = await self._user_repo.get_balance(purchase.user_id)
    if new_balance < 0:
        logger.warning(
            "User %s balance went negative (%s) after refund",
            purchase.user_id, new_balance,
        )
```

**Refund event key fields (`charge.refunded`):**

| Field | Example | Notes |
|-------|---------|-------|
| `charge.amount` | `1000` | Original charge amount in cents |
| `charge.amount_refunded` | `500` | **Cumulative** refund amount in cents |
| `charge.refunded` | `false` | `true` only if fully refunded |
| `charge.payment_intent` | `pi_xxx` | Links to original checkout session |
| `charge.customer` | `cus_xxx` | Stripe Customer ID |

**Partial refunds:** Multiple partial refunds fire multiple `charge.refunded` events. Each event contains the cumulative `amount_refunded`. The handler compares with the previously tracked refund total to calculate the incremental amount.

### 7.4 Stripe Retry Behavior

| Environment | Retry Duration | Strategy |
|-------------|---------------|----------|
| Live mode | Up to **3 days** | Exponential backoff |
| Test mode | **3 retries** over a few hours | Shorter intervals |

Stripe expects a 2xx response. Any other status code (4xx, 5xx, timeout) triggers retries. **Always return 200** for events that don't match a handler (the `case _: pass` above) to prevent infinite retries for event types we don't handle.

---

## 8. API Endpoints

All endpoints except the webhook require authentication (`CurrentUserId` dependency). All follow REQ-006 response envelope conventions.

### 8.1 GET /api/v1/credits/packs

Returns active funding packs. **No authentication required** (public pricing page).

**Response:** `200 OK`
```json
{
    "data": [
        {
            "id": "a1b2c3d4-...",
            "name": "Starter",
            "price_cents": 500,
            "price_display": "$5.00",
            "grant_cents": 500,
            "amount_display": "$5.00",
            "description": "Analyze ~250 jobs and generate tailored materials",
            "highlight_label": null
        },
        {
            "id": "e5f6g7h8-...",
            "name": "Standard",
            "price_cents": 1000,
            "price_display": "$10.00",
            "grant_cents": 1000,
            "amount_display": "$10.00",
            "description": "Analyze ~500 jobs and generate tailored materials",
            "highlight_label": "Most Popular"
        },
        {
            "id": "i9j0k1l2-...",
            "name": "Pro",
            "price_cents": 1500,
            "price_display": "$15.00",
            "grant_cents": 1500,
            "amount_display": "$15.00",
            "description": "Analyze ~750 jobs and generate tailored materials",
            "highlight_label": "Best Value"
        }
    ]
}
```

### 8.2 POST /api/v1/credits/checkout

Creates a Stripe Checkout Session. **Requires authentication.**

**Request Body:**
```json
{
    "pack_id": "a1b2c3d4-..."
}
```

**Response:** `200 OK`
```json
{
    "data": {
        "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
        "session_id": "cs_test_..."
    }
}
```

**Error Responses:**
| Code | HTTP | When |
|------|------|------|
| `INVALID_PACK_ID` | 400 | Unknown, inactive, or missing `stripe_price_id` on pack |
| `STRIPE_ERROR` | 502 | Stripe API error during session creation |
| `CREDITS_UNAVAILABLE` | 503 | Credits system disabled (`CREDITS_ENABLED=false`) |

**Success/Cancel URLs:** Constructed from `settings.frontend_url`:
- Success: `{frontend_url}/usage?status=success&session_id={CHECKOUT_SESSION_ID}`
- Cancel: `{frontend_url}/usage?status=cancelled`

### 8.3 GET /api/v1/credits/purchases

Returns the user's purchase history. **Requires authentication.**

**Query Parameters:**
| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 20 | Items per page (max 100) |

**Response:** `200 OK`
```json
{
    "data": [
        {
            "id": "a1b2c3d4-...",
            "amount_usd": "10.000000",
            "amount_display": "$10.00",
            "transaction_type": "purchase",
            "description": "Funding pack purchase",
            "created_at": "2026-03-10T15:30:00Z"
        },
        {
            "id": "e5f6g7h8-...",
            "amount_usd": "0.100000",
            "amount_display": "$0.10",
            "transaction_type": "signup_grant",
            "description": "Welcome bonus — free starter balance",
            "created_at": "2026-03-08T10:00:00Z"
        }
    ],
    "meta": {
        "page": 1,
        "per_page": 20,
        "total": 2,
        "total_pages": 1
    }
}
```

Includes transactions of types: `purchase`, `signup_grant`, `admin_grant`, `refund`.

### 8.4 POST /api/v1/webhooks/stripe

Stripe webhook endpoint. **No authentication — signature verified.** See §7.1.

### 8.5 Router Registration

```python
# backend/app/api/v1/router.py
from backend.app.api.v1 import credits, webhooks

router.include_router(credits.router, prefix="/credits", tags=["credits"])
router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
```

---

## 9. Frontend

### 9.1 Credits Page Enhancement

**Route:** `/usage` (existing usage page, enhanced)

The existing usage page (`frontend/src/components/usage/`) gains a "Funding Packs" section between the balance card and the usage summary:

1. **Current Balance** (existing) — USD display with usage bar and color coding
2. **Funding Packs** (new) — Cards for each active pack with "Add Funds" buttons
3. **Purchase History** (new) — Paginated table of credit transactions
4. **Usage Summary** (existing) — Period breakdown of LLM usage
5. **Usage History** (existing) — Paginated LLM call history

### 9.2 Funding Pack Cards

Each active pack renders as a card showing:
- Pack name and description
- Price (`price_display` from API)
- Highlight label badge (if present)
- "Add Funds" button

The highlighted pack (the one with `highlight_label`) gets visual emphasis (border, badge).

### 9.3 Checkout Flow (Frontend)

```typescript
const handleAddFunds = async (packId: string) => {
    setLoading(true);
    try {
        const response = await apiPost<{ checkout_url: string; session_id: string }>(
            "/credits/checkout",
            { pack_id: packId }
        );
        // Full page redirect to Stripe
        window.location.href = response.data.checkout_url;
    } catch (error) {
        showToast.error("Unable to start checkout. Please try again.");
        setLoading(false);
    }
};
```

**No Stripe client-side library needed.** The hosted redirect flow uses a plain `window.location.href` redirect. No `@stripe/react-stripe-js`, no `loadStripe()`, no publishable key on the frontend.

### 9.4 Success/Cancel Handling

```typescript
// /usage page checks URL params on mount (wrap in <Suspense>)
const searchParams = useSearchParams();
const status = searchParams.get("status");

useEffect(() => {
    if (status === "success") {
        showToast.success("Payment successful! Your balance has been updated.");
        queryClient.invalidateQueries({ queryKey: queryKeys.balance });
        router.replace("/usage");
    } else if (status === "cancelled") {
        showToast.info("Purchase cancelled.");
        router.replace("/usage");
    }
}, [status]);
```

**`useSearchParams` + Suspense:** Next.js App Router requires `useSearchParams()` to be wrapped in a `<Suspense>` boundary. Without it, the page fails to build.

**Optimistic display:** The success toast shows immediately on redirect. The actual balance update happens asynchronously via webhook (typically 1-2 seconds). The `invalidateQueries` call refreshes the balance display.

### 9.5 Low-Balance Warning

Add a warning banner to the usage page when balance drops below a threshold. Thresholds align with the existing color scheme (defined in `frontend/src/lib/format-utils.ts` and used by the balance card and nav bar):

| Condition | Display |
|-----------|---------|
| Balance < `BALANCE_THRESHOLD_LOW` ($0.10) | Red (destructive) warning: "Your balance is nearly empty. Add funds to continue using Zentropy Scout." |
| Balance < `BALANCE_THRESHOLD_HIGH` ($1.00) | Amber (primary) warning: "Your balance is running low. Add funds to continue." |
| Balance >= `BALANCE_THRESHOLD_HIGH` ($1.00) | No warning |

Uses the same `BALANCE_THRESHOLD_HIGH` ($1.00) and `BALANCE_THRESHOLD_LOW` ($0.10) constants from `format-utils.ts` (REQ-020 §9.1). The warning includes a link/button that scrolls to the funding packs section on the same page.

### 9.6 Query Keys

Add to `frontend/src/lib/query-keys.ts`:

```typescript
creditPacks: ["credits", "packs"] as const,
purchases: ["credits", "purchases"] as const,
```

The existing `balance` key from usage is reused.

---

## 10. Security Considerations

### 10.1 PCI Compliance (SAQ A)

Stripe Checkout (hosted redirect) gives us **SAQ A** — the minimal PCI self-assessment. Card data never touches our servers.

| Responsibility | Owner |
|----------------|-------|
| Card number collection, validation, storage | **Stripe** |
| 3D Secure / SCA authentication | **Stripe** |
| PCI Level 1 certification | **Stripe** |
| Fraud detection (Radar) | **Stripe** |
| Our API endpoints use HTTPS | **Us** |
| Never store/log card data | **Us** |
| Protect Stripe API keys | **Us** |

**What we CAN safely store** (not PCI-sensitive): card brand, last four digits, expiration month/year (returned by Stripe after payment). These are stored on `stripe_purchases` for display purposes if needed in the future.

**What we MUST NOT do:**
- Store full card numbers, CVV, or magnetic stripe data
- Log raw card data in application logs
- Transmit card data through our servers
- Put card data in Stripe metadata fields

### 10.2 Webhook Security

| Threat | Mitigation |
|--------|------------|
| Forged webhook | HMAC-SHA256 signature verification via `stripe.Webhook.construct_event()` |
| Replay attack | Stripe includes timestamp in signature; SDK rejects events older than 300 seconds |
| Double crediting | UNIQUE constraint on `credit_transactions.stripe_event_id` |
| Information leakage | Webhook returns minimal response (`{"received": true}`) |
| Denial of service | Exempt from rate limiting (signature verification is sufficient) |

### 10.3 Secret Management

| Secret | Type | Exposure |
|--------|------|----------|
| `STRIPE_SECRET_KEY` | `SecretStr` | Never logged, never in API responses |
| `STRIPE_WEBHOOK_SECRET` | `SecretStr` | Never logged, never in API responses |
| `STRIPE_PUBLISHABLE_KEY` | `str` | Safe for client-side (Stripe designs it for this). Only needed for future embedded checkout — not required for hosted redirect. |

### 10.4 Metadata Integrity

Webhook metadata is trustworthy because:
1. Signature verification proves the event came from Stripe
2. Metadata was set by our backend during session creation
3. Users cannot modify Checkout Session metadata

Still, always validate:
- `user_id` exists in our database
- `pack_id` exists in our database
- `grant_cents` is a valid positive integer

---

## 11. Configuration

### 11.1 New Environment Variables

| Variable | Type | Default | Required | Notes |
|----------|------|---------|----------|-------|
| `STRIPE_SECRET_KEY` | SecretStr | — | Yes (if `CREDITS_ENABLED`) | Secret key (`sk_test_...` or `sk_live_...`) |
| `STRIPE_WEBHOOK_SECRET` | SecretStr | — | Yes (if `CREDITS_ENABLED`) | Webhook signing secret (`whsec_...`) |
| `STRIPE_PUBLISHABLE_KEY` | str | — | No | Not needed for hosted redirect. Reserved for future embedded checkout. |
| `CREDITS_ENABLED` | bool | `true` | No | Master switch. When `false`, checkout returns 503. Signup grant still works. |

### 11.2 Config.py Addition

```python
# backend/app/core/config.py — add to Settings class
stripe_secret_key: SecretStr = SecretStr("")
stripe_webhook_secret: SecretStr = SecretStr("")
stripe_publishable_key: str = ""
credits_enabled: bool = True
```

### 11.3 Production Security Checks

Add to `Settings.check_production_security()`:

```python
if self.environment == "production" and self.credits_enabled:
    if not self.stripe_secret_key.get_secret_value():
        raise ValueError("STRIPE_SECRET_KEY required in production when credits enabled")
    if not self.stripe_webhook_secret.get_secret_value():
        raise ValueError("STRIPE_WEBHOOK_SECRET required in production when credits enabled")
    if self.stripe_secret_key.get_secret_value().startswith("sk_test_"):
        raise ValueError("STRIPE_SECRET_KEY must use live keys in production (got sk_test_)")
```

### 11.4 Local Development

**Without Stripe (default):**
```bash
CREDITS_ENABLED=false
METERING_ENABLED=false
```

**With Stripe test mode:**
```bash
CREDITS_ENABLED=true
METERING_ENABLED=true
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...  # From Stripe CLI
```

**Configuration matrix** (see REQ-021 §10.3 for full details):

| `METERING_ENABLED` | `CREDITS_ENABLED` | Behavior |
|--------------------|-------------------|----------|
| `false` | `false` | Local dev — no metering, no gating, no checkout |
| `false` | `true` | Invalid — log warning on startup |
| `true` | `false` | Admin-grant only — metering active, no self-purchase |
| `true` | `true` | Production — full metering + self-service purchases |

Use Stripe CLI for local webhook testing:
```bash
# Install: https://github.com/stripe/stripe-cli/releases
stripe login
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
# CLI outputs the whsec_... signing secret for local use
```

### 11.5 Stripe Test Mode

**Test card numbers:**

| Card Number | Scenario |
|-------------|----------|
| `4242 4242 4242 4242` | Visa, succeeds |
| `5555 5555 5555 4444` | Mastercard, succeeds |
| `4000 0025 0000 3155` | Requires 3D Secure |
| `4000 0000 0000 9995` | Declined (insufficient funds) |
| `4000 0000 0000 0002` | Declined (generic) |

All test cards: any future expiration, any CVC.

**API key prefixes:**

| Key Type | Test | Live |
|----------|------|------|
| Secret | `sk_test_` | `sk_live_` |
| Publishable | `pk_test_` | `pk_live_` |
| Webhook | `whsec_` | `whsec_` |

**Trigger test events:**
```bash
stripe trigger checkout.session.completed
stripe trigger charge.refunded
```

---

## 12. Signup Grant Flow

See REQ-021 §8 for the full specification. Summary:

1. New user registers (OAuth, email+password, or magic link)
2. Backend calls `stripe_service.grant_signup_credits(user_id)`
3. Service reads `signup_grant_cents` from `system_config` (default: 10 = $0.10)
4. If amount is 0, skip (grants disabled by admin)
5. Check idempotency (existing `signup_grant` transaction for this user)
6. Insert `credit_transactions` row with `transaction_type = 'signup_grant'`
7. Atomically credit `balance_usd`

**Integration points:** `account_linking.py` (OAuth), `auth.py` (email+password), `auth_magic_link.py` (magic link). See REQ-021 §8.2 for exact file locations.

**Existing users:** The Alembic migration includes a data migration step that grants signup balance to all existing users who don't already have a `signup_grant` transaction.

---

## 13. Error Handling

### 13.1 Error Codes

| Code | HTTP | When |
|------|------|------|
| `INVALID_PACK_ID` | 400 | Unknown, inactive, or unconfigured pack |
| `STRIPE_ERROR` | 502 | Stripe API returned an error |
| `INVALID_PAYLOAD` | 400 | Webhook payload is malformed |
| `INVALID_SIGNATURE` | 401 | Webhook signature verification failed |
| `CREDITS_UNAVAILABLE` | 503 | Credits disabled or Stripe unreachable |

### 13.2 Webhook Error Scenarios

These scenarios return 200 OK (to stop Stripe retries) but do NOT credit balance:

| Scenario | Behavior |
|----------|----------|
| Duplicate webhook (same `event_id`) | Skip processing (idempotent). Already recorded via UNIQUE constraint. |
| Metadata missing `user_id` or `pack_id` | Log error. Do NOT credit balance. Alert for manual investigation. |
| `user_id` in metadata not found in DB | Log error. Do NOT credit balance. Manual investigation needed. |
| `payment_status` is not `"paid"` | Log warning. Skip — session may be pending async payment. |
| Stripe API unreachable during customer creation | 502 Bad Gateway to the checkout request (not webhook). |

See REQ-021 §6.6 for the complete error handling table with all 7 scenarios and user-facing messages.

### 13.3 Stripe Error Mapping

See REQ-021 §12.2 for the complete mapping. Summary:

| Stripe Exception | User Message |
|-----------------|-------------|
| `stripe.RateLimitError` | "Payment service is busy. Please try again in a moment." |
| `stripe.AuthenticationError` | "Payment service temporarily unavailable." (log + alert internally) |
| `stripe.APIConnectionError` | "Payment service temporarily unavailable. Please try again." |
| `stripe.InvalidRequestError` | "Payment service error. Please try again." (log + alert internally) |
| Any other `stripe.StripeError` | "Payment service error. Please try again." |

**Never expose** Stripe error details (codes, messages, request IDs) to the user. Log them server-side.

---

## 14. Open Questions

| # | Question | Context |
|---|----------|---------|
| 1 | **Stripe account: personal or business?** | Business accounts have different tax reporting requirements (1099-K). A business account is recommended for a SaaS product. |
| 2 | **Minimum purchase amount?** | The current floor is $5.00 (Starter pack). Stripe's minimum is $0.50. Should we allow smaller amounts? Lower amounts have worse Stripe fee ratios ($0.30 fixed fee on a $1 purchase is 30%). |
| 3 | **Subscription model for post-MVP?** | Monthly credit allotment with overage billing could reduce churn. Deferred to avoid subscription complexity (proration, failed payments, dunning). `funding_packs` infrastructure supports both one-time and future subscription models. |
| 4 | **Stripe Tax?** | Stripe Tax can automatically calculate and collect sales tax. Deferred for MVP — adds complexity and requires tax registration. Can be added later by enabling it on Checkout Sessions (`automatic_tax: {enabled: true}`). |
| 5 | **Receipt emails?** | Stripe can send receipt emails automatically. Should we enable this at the Checkout Session level (`payment_intent_data: {receipt_email: user.email}`)? |
| 6 | **Webhook endpoint authentication?** | Should the webhook endpoint validate that the request comes from Stripe IP ranges in addition to signature verification? Signature verification alone is considered sufficient by Stripe's documentation, but IP allowlisting adds defense-in-depth. |

---

## 15. Files Modified/Created

### 15.1 Backend (New)

| File | Purpose |
|------|---------|
| `backend/app/services/stripe_service.py` | Stripe SDK calls — session creation, customer management, webhook processing |
| `backend/app/api/v1/credits.py` | Credit purchase endpoints — packs, checkout, purchases |
| `backend/app/api/v1/webhooks.py` | Stripe webhook endpoint — signature verification, event routing |
| `backend/app/schemas/credits.py` | Pydantic schemas — CheckoutRequest, PackResponse, PurchaseResponse |
| `backend/app/models/stripe.py` | StripePurchase model |
| `backend/app/repositories/stripe_repository.py` | StripePurchase CRUD |
| `backend/app/core/stripe_client.py` | StripeClient factory + FastAPI dependency |
| `backend/migrations/versions/025_stripe_checkout.py` | Schema migration + data migration |

### 15.2 Backend (Modified)

| File | Change |
|------|--------|
| `backend/app/models/user.py` | Add `stripe_customer_id` column |
| `backend/app/models/usage.py` | Add `stripe_event_id` column to `CreditTransaction` |
| `backend/app/models/__init__.py` | Export `StripePurchase` |
| `backend/app/core/config.py` | Add Stripe env vars, production security checks |
| `backend/app/api/v1/router.py` | Register credits and webhooks routers |
| `backend/pyproject.toml` | Add `stripe[async]>=14.0.0,<15.0.0` dependency |
| `.env.example` | Add Stripe env var documentation |

### 15.3 Frontend (New)

| File | Purpose |
|------|---------|
| `frontend/src/components/usage/funding-packs.tsx` | Pack selection cards with "Add Funds" buttons |
| `frontend/src/components/usage/purchase-table.tsx` | Purchase history table |
| `frontend/src/components/usage/low-balance-warning.tsx` | Low-balance alert banner |
| `frontend/src/lib/api/credits.ts` | API client functions for credits endpoints |

### 15.4 Frontend (Modified)

| File | Change |
|------|--------|
| `frontend/src/components/usage/usage-page.tsx` | Add funding packs section and purchase table |
| `frontend/src/components/usage/balance-card.tsx` | Enable "Add Funds" button (currently disabled) |
| `frontend/src/lib/query-keys.ts` | Add `creditPacks` and `purchases` keys |
| `frontend/src/types/usage.ts` | Add pack and purchase types |

---

## 16. Testing Requirements

### 16.1 Unit Tests

| Test Area | Key Scenarios |
|-----------|---------------|
| `StripeService.create_checkout_session` | Valid pack creates session; inactive pack raises error; pack without `stripe_price_id` raises error; customer created on first purchase; existing customer reused |
| `StripeService.handle_checkout_completed` | Credits balance correctly; idempotent (same `event_id` skipped); missing metadata logged and skipped; invalid `user_id` logged and skipped; unpaid session skipped |
| `StripeService.handle_charge_refunded` | Full refund debits correctly; partial refund handled incrementally; idempotent; balance can go negative (warning logged) |
| `StripeService.grant_signup_credits` | Grants on first call; skips on duplicate; reads `signup_grant_cents`; zero amount disables; converts cents to USD |
| Webhook signature verification | Valid signature accepted; invalid signature rejected (401); expired timestamp rejected |
| Packs endpoint | Returns active packs only; correct display fields; no auth required |
| Checkout endpoint | Requires auth; valid pack returns URL; inactive pack returns 400; credits disabled returns 503 |
| Purchases endpoint | Requires auth; returns only current user's transactions; pagination works |

### 16.2 Integration Tests

| Test Area | Key Scenarios |
|-----------|---------------|
| End-to-end purchase | Session created → webhook → balance credited → visible in purchases API |
| Duplicate webhook | Same event twice → balance credited only once |
| Signup grant + purchase | New user → grant → purchase → balance = grant + purchase |
| Full refund | Purchase → refund webhook → balance reduced → transaction history shows both |
| Partial refund | Purchase → partial refund → correct debit → full refund → remaining debit |

### 16.3 Mocking Strategy

| Component | Mock Approach |
|-----------|---------------|
| `StripeClient` | Mock `checkout.sessions.create_async`, `customers.create_async`, `customers.retrieve_async` |
| `stripe.Webhook` | Mock `construct_event` to return test event objects |
| Webhook payloads | Use Stripe's documented example event structures |
| `system_config` | Mock reads for `signup_grant_cents` in unit tests |

**No real Stripe API calls** in automated tests. All Stripe interactions are mocked. The Stripe CLI (`stripe trigger`) is for manual local testing only.

### 16.4 Frontend Tests

| Component | Key Scenarios |
|-----------|---------------|
| `FundingPacks` | Renders pack cards from API; shows highlight badge; "Add Funds" button calls checkout API; loading state during redirect |
| `PurchaseTable` | Renders transaction list; pagination; empty state |
| `LowBalanceWarning` | Shows amber at <$0.50; shows red at $0.00; hidden when balance sufficient |
| Success/cancel flow | Success param shows toast + refreshes balance; cancel param shows info toast; params cleaned from URL |

---

## 17. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-10 | 0.2 | **Coherence review with REQ-021 v0.6.** (1) Replaced vague "supersedes" statement with precise section-by-section traceability map (§1.4) — clarifies exactly which REQ-021 sections are superseded, which remain authoritative, and which are new in REQ-029. (2) Fixed all frontend page routes from `/credits` to `/usage` (actual page is at `frontend/src/app/(main)/usage/page.tsx`) — affects §6.2 success/cancel URLs, §8.2 redirect URLs, §9.1 route, §9.4 `router.replace()` calls. API routes (`/api/v1/credits/*`) unchanged. (3) Fixed low-balance warning thresholds (§9.5) from arbitrary $0.50/$0.00 to existing `BALANCE_THRESHOLD_HIGH` ($1.00) / `BALANCE_THRESHOLD_LOW` ($0.10) from `format-utils.ts` — aligns with REQ-020 §9.1 and existing balance-card color scheme. (4) Added §4.4 `reference_id` semantics table — documents what each transaction type stores in this column (was only in REQ-021 §6.8). (5) Added §13.2 webhook error scenarios table — documents metadata-missing, user-not-found, and unpaid-session cases (complements REQ-021 §6.6). (6) Added §13.3 cross-reference to REQ-021 §12.2 for Stripe error mapping. (7) Added configuration matrix to §11.4 (references REQ-021 §10.3). (8) Added `stripe_price_id` nullable note to §2.6 — checkout must validate non-null before creating session. (9) Fixed section numbering (§4.4→4.6 migration). (10) REQ-021 updated to v0.6 with reciprocal supersession notice, backlog item #13, `stripe_price_id` nullable fix, REQ-023 ✅, and `/credits`→`/usage` route fixes. |
| 2026-03-10 | 0.1 | Initial version. Supersedes REQ-021 for Stripe-specific sections. Key differences from REQ-021: (1) Uses `StripeClient` pattern (not deprecated global `stripe.api_key`). (2) Adds `stripe_purchases` table for session lifecycle tracking. (3) Adds `stripe[async]` extra for native httpx async support. (4) Documents current SDK v14.4.0 patterns. (5) Adds low-balance warning specification. (6) Includes Stripe test mode details (test cards, CLI commands). (7) Adds open questions from backlog #13 (business account, minimum purchase, tax, subscriptions, receipts). (8) Consolidates checkout flow, webhook handling, refund processing, and customer management into a single implementation-ready document. |
