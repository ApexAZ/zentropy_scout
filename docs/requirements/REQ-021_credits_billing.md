# REQ-021: Credits & Billing

**Status:** Not Started
**Version:** 0.7
**PRD Reference:** §6 Technical Architecture
**Backlog Item:** #13
**Last Updated:** 2026-03-29

> **Supersession Notice (v0.6):** REQ-029 (Stripe Checkout Integration) supersedes the Stripe SDK and implementation sections of this document. See REQ-029 §1 for the precise traceability map. This document remains the authoritative source for design decision rationale (§2), signup grant integration points (§8), frontend UX patterns (§9.3 Suspense/toast/query keys), webhook rate limiting rationale (§11.2), and resolved questions (§15). When REQ-021 and REQ-029 conflict, **REQ-029 takes precedence**.
>
> **Amendment Notice:** REQ-030 (Billing & Metering Hardening) amends the balance model by adding a `held_balance_usd` concept for pre-debit reservations, and amends §10.3 (configuration matrix — invalid combo rejected in production). When REQ-021 and REQ-030 conflict, **REQ-030 takes precedence**.

---

## 1. Overview

This document specifies the Stripe payment rail for adding funds to user balances and displaying purchase history. It builds on the metering infrastructure defined in REQ-020 (Token Metering & Usage Tracking) and depends on the Admin Pricing Dashboard (backlog #16 / REQ-022) and USD-Direct Billing configuration (backlog #19 / REQ-023) for pack definitions and display model.

**Scope boundary:** This REQ covers **Stripe as a payment rail only** — checkout, webhooks, refunds, purchase history. Pricing configuration, model registry, and margin multipliers are specified in REQ-022 (backlog #16). USD-direct billing decisions and seed data corrections are specified in REQ-023 (backlog #19). REQ-021 consumes those systems; it does not define them.

> **v0.4–0.5 Errata (2026-03-02):** This document was originally written assuming abstract credits (v0.3). A design review (documented in backlog PBI #19 and REQ-023) rejected abstract credits in favor of USD-direct billing. v0.4 replaced all references to abstract credits, `credits_per_dollar`, and credit formatting utilities with USD-direct equivalents. v0.5 aligned table/column names with REQ-023's naming clean-up: `credit_packs` → `funding_packs`, `credit_amount` → `grant_cents`. See REQ-023 §6.1 for the full change map and §2.3 for the naming rationale.

### 1.1 Problem Statement

REQ-020 defines a per-user credit balance and an append-only credit ledger (`credit_transactions`), but provides no mechanism for users to add funds. Without a purchase flow:

1. **No revenue** — Users cannot pay for the service
2. **Zero balance on signup** — New users are immediately gated (402) on their first LLM call
3. **No self-service** — Balance can only be changed via manual database operations or admin grants

### 1.2 Solution

A Stripe Checkout integration that:
1. **Offers** admin-configurable funding packs at fixed USD prices (packs grant USD balance, dollar-for-dollar)
2. **Redirects** users to Stripe's hosted checkout page for secure payment
3. **Processes** completed payments via Stripe webhooks
4. **Credits** the user's USD balance atomically via the `credit_transactions` ledger
5. **Displays** purchase history and current balance in the frontend
6. **Grants** a free starter balance on signup so new users can try the service

### 1.3 Scope

| In Scope | Out of Scope |
|----------|-------------|
| Stripe Checkout (hosted redirect mode) | Stripe Elements / embedded card forms |
| "Add Funds" pack purchase flow (packs defined in admin UI) | Custom amounts / pay-what-you-want |
| One-time purchases | Subscriptions / recurring billing |
| Stripe webhook handling (signature verified) | Stripe Connect / marketplace payouts |
| Idempotent webhook processing | Invoice generation / tax calculation |
| Free starter balance on signup | Referral / promo codes |
| Stripe Customer creation per user | Saved payment methods / card-on-file |
| Purchase history API + frontend | Admin refund UI (manual via Stripe Dashboard) |
| Frontend "Add Funds" page | Mobile payment (Apple Pay, Google Pay) |
| | Pricing config / model registry / margin config (REQ-022 / backlog #16) |

---

## 2. Design Decisions

### 2.1 Checkout Mode

**How should users pay?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Stripe Checkout (hosted redirect) | ✅ | Zero PCI burden — card data never touches our servers. Stripe hosts the entire payment form. Handles 3D Secure, address collection, and error states. Minimal frontend code (redirect to URL). Battle-tested conversion optimization by Stripe. |
| B. Stripe Checkout (embedded mode) | — | Lower cart abandonment, but requires `@stripe/react-stripe-js` dependency, more complex frontend setup, and Content Security Policy changes for Stripe's iframe. Added complexity without clear benefit for a simple credit pack purchase. |
| C. Stripe Elements (custom form) | — | Maximum control but highest PCI burden (SAQ A-EP). Requires building the entire payment form, handling card validation, error states, and 3D Secure flows. Over-engineering for fixed-price credit packs. |
| D. Stripe Payment Links (no-code) | — | No server-side control. Cannot pass user metadata, cannot programmatically create sessions, no webhook customization. |

**Chosen: Option A — Stripe Checkout (Hosted Redirect)**

Flow:
1. User clicks "Add Funds" on a pack
2. Frontend calls `POST /api/v1/credits/checkout` with the pack ID
3. Backend creates a Stripe Checkout Session with the pack's price and the user's ID in metadata
4. Backend returns the Checkout Session URL
5. Frontend redirects the user to Stripe's hosted checkout page
6. User completes payment on Stripe's domain
7. Stripe redirects user back to our success/cancel URL
8. Stripe sends a `checkout.session.completed` webhook to our backend
9. Backend verifies webhook signature, credits the user's USD balance

### 2.2 Pricing Strategy

**How should credit packs be structured?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Fixed funding packs (quick-select) | ✅ | Simple, clear pricing. Users pick an amount. No decision fatigue. Standard SaaS pattern. Quick-select buttons go straight to Stripe checkout. |
| B. Custom amount (pay-what-you-want) | — | More flexible but adds UI complexity (amount input, validation, dynamic Stripe price creation). No clear user demand. |
| C. Single fixed amount | — | Too restrictive. Users with different budgets want different options. |

**Chosen: Option A — Fixed Funding Packs (Quick-Select)**

Pack definitions are **admin-configurable** via the Admin Pricing Dashboard (REQ-022 / backlog #16), stored in the `funding_packs` table (see §4.3). Packs grant **USD balance** — dollar-for-dollar for MVP (no volume bonuses). Each pack has a corresponding Stripe Price ID for checkout. Descriptions are volume-based and admin-editable to help users understand what they're buying.

See §5 for pack definitions and example values.

### 2.3 Stripe Customer Management

**Should we create Stripe Customer objects?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Create Stripe Customer on first purchase | ✅ | Links all purchases to one customer. Stripe Dashboard shows purchase history per customer. Required for future features (saved cards, subscriptions). Minimal overhead — one API call on first purchase only. |
| B. No customer (guest checkout) | — | Simpler but loses purchase history in Stripe Dashboard. Cannot pre-fill email on repeat purchases. Blocks future subscription support. |
| C. Create Stripe Customer on signup | — | Creates customers who may never purchase. Wastes Stripe API calls. Customer should only be created when a purchase intent exists. |

**Chosen: Option A — Create on First Purchase**

The `stripe_customer_id` is stored on the `users` table. On subsequent purchases, the existing customer ID is passed to the Checkout Session, pre-filling the user's email and showing their previous payment methods.

### 2.4 Webhook Idempotency

**How should duplicate webhook deliveries be handled?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Stripe event ID as unique constraint | ✅ | Simple, reliable. Store `stripe_event_id` on `credit_transactions` with a unique index. Duplicate webhook → unique constraint violation → skip. No separate events table needed. |
| B. Separate `stripe_events` table | — | Adds a table just for deduplication. The event ID can live on `credit_transactions` directly since each successful webhook creates exactly one transaction. |
| C. In-memory deduplication | — | Lost on restart. Not durable. |

**Chosen: Option A — Event ID on credit_transactions**

The `credit_transactions` table gains a `stripe_event_id` column with a unique index. When a webhook arrives:
1. Verify signature
2. Check if a `credit_transactions` row exists with this `stripe_event_id`
3. If yes → return 200 (already processed, idempotent)
4. If no → process the event and insert the row

### 2.5 Free Trial Grant

**Should new users get free credits?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Configurable starter balance on signup | ✅ | Lets users explore all features before paying. Grant amount is admin-configurable via `system_config` (REQ-022 / backlog #16). Creates a `credit_transactions` row with `type = 'signup_grant'`. |
| B. No free balance | — | New users hit 402 immediately. Terrible onboarding experience. Forces payment before users understand value. |
| C. Free tier (unlimited free usage up to N calls) | — | Requires separate gating logic. Harder to implement than a simple balance grant. Doesn't teach users about the billing model. |

**Chosen: Option A — Configurable Starter Balance**

Granted once per user at account creation. The grant amount is stored in the `system_config` table (key: `signup_grant_cents`, renamed from `signup_grant_credits` by REQ-023) and configurable via the Admin System Config tab. Default: 10 cents ($0.10) — enough for ~5 job extractions or ~2 complete workflows at typical margins. Creates a `credit_transactions` row with `transaction_type = 'signup_grant'`. This is a new transaction type added to the enum defined in REQ-020 §4.3.

**Updated `transaction_type` enum:** `purchase`, `usage_debit`, `admin_grant`, `refund`, `signup_grant`.

### 2.6 Refund Handling

**How should refunds work?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Manual via Stripe Dashboard only | ✅ | Refunds are rare at MVP scale. Stripe Dashboard provides full refund UI (partial, full, with reason). No custom admin UI needed. Webhook handles the balance adjustment automatically. |
| B. In-app refund UI | — | Requires admin role system. Over-engineering for MVP. |

**Chosen: Option A — Manual via Stripe Dashboard**

When a refund is issued via Stripe Dashboard, the `charge.refunded` webhook fires. The backend creates a `credit_transactions` row with `transaction_type = 'refund'` and a **negative** USD amount, then reduces the user's balance accordingly.

**Why negative?** A refund returns money to the user via Stripe, so we must remove the corresponding balance. The negative `amount_usd` reflects balance being taken back — the money refund happens entirely on Stripe's side. The amount to remove matches the refund: if the user paid $10 and receives a full refund, $10.00 is debited from their balance. For partial refunds, the debit matches the refund amount. If the user has already spent some or all of the refunded balance, their `balance_usd` may go negative. This is expected and logged as a warning.

---

## 3. Dependencies

### 3.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-020 Token Metering v0.5 | Foundation | `credit_transactions` table, user balance column, balance API endpoints, metering pipeline |
| REQ-022 Admin Pricing (backlog #16) | Foundation | `funding_packs` table (renamed from `credit_packs` by REQ-023), `system_config` table (signup grant amount), admin auth gate |
| REQ-023 USD-Direct Billing (backlog #19) | Foundation | Corrected seed data (USD cents), `signup_grant_cents` config key, usage bar |
| REQ-005 Database Schema v0.10 | Schema | `users` table to extend with `stripe_customer_id` |
| REQ-006 API Contract v0.8 | Integration | Response envelope pattern (§7), error codes (§8) |
| REQ-013 Authentication v0.1 | Integration | `CurrentUserId` dependency, user creation flow (for signup grant) |

### 3.2 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-012 Frontend Application | Integration | Credits page, balance display |

### 3.3 Prerequisite Implementation Order

This REQ **cannot be implemented** until:
1. **Backlog #16 / REQ-022** (Admin Pricing Dashboard) is complete ✅ — provides `funding_packs` table (renamed from `credit_packs` by REQ-023), `system_config` table, and admin auth
2. **Backlog #19 / REQ-023** (USD-Direct Billing) is complete ✅ — renames `credit_packs` → `funding_packs` and `credit_amount` → `grant_cents`, provides corrected seed data (USD cents), renamed `signup_grant_cents` config key, and usage bar

No column renames are needed on `users` or `credit_transactions`. The existing USD-denominated columns (`balance_usd`, `amount_usd`) are correct as-is — the USD-direct decision (REQ-023 §2.1) means the column names match their semantic meaning. The `credit_packs` → `funding_packs` and `credit_amount` → `grant_cents` renames are handled by REQ-023's migration (§4.1).

---

## 4. Database Schema

### 4.1 Users Table Extension

Add one column to the existing `users` table:

```sql
ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(255) UNIQUE;
```

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `stripe_customer_id` | `VARCHAR(255)` | NULL | NULL | Stripe Customer ID (e.g., `cus_abc123`). Created on first purchase. Unique constraint prevents duplicate customers. |

### 4.2 Credit Transactions Extension

Add one column to the `credit_transactions` table:

```sql
ALTER TABLE credit_transactions ADD COLUMN stripe_event_id VARCHAR(255) UNIQUE;
```

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `stripe_event_id` | `VARCHAR(255)` | NULL | NULL | Stripe event ID (e.g., `evt_abc123`). Used for webhook idempotency. Unique constraint prevents double-crediting. Only populated for `purchase` and `refund` transaction types. |

**Migration note:** REQ-020 is already implemented. This column is added in a separate Alembic migration by this REQ.

### 4.3 Funding Packs Table

**Defined by backlog #16 (Admin Pricing Dashboard), renamed by backlog #19 (REQ-023), consumed by this REQ.** Listed here for reference with post-rename names:

```sql
CREATE TABLE funding_packs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(50) NOT NULL,         -- "Starter", "Standard", "Pro"
    price_cents     INTEGER NOT NULL,              -- USD price in cents (e.g., 500 = $5.00)
    grant_cents     BIGINT NOT NULL,               -- USD cents to grant (e.g., 500 = $5.00). Equals price_cents for MVP (dollar-for-dollar).
    stripe_price_id VARCHAR(255) UNIQUE,            -- Stripe Price ID (e.g., "price_abc123"). Nullable until admin configures Stripe.
    display_order   INTEGER NOT NULL DEFAULT 0,    -- Sort order in UI
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,  -- Soft-disable without deleting
    description     VARCHAR(255),                  -- "Get started with Zentropy Scout"
    highlight_label VARCHAR(50),                   -- "Most Popular", "Best Value"
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Why `price_cents` (integer) instead of `price_usd` (decimal)?** Following Stripe's convention — storing monetary amounts as integers in the smallest currency unit (cents for USD) eliminates floating-point rounding issues. Stripe's API uses the same convention.

**Why `grant_cents` (bigint)?** BIGINT accommodates future volume bonuses where `grant_cents > price_cents`. For MVP, `grant_cents == price_cents` (dollar-for-dollar). See REQ-023 §2.3 for the naming rationale and §4.1 for the rename migration.

**Naming history:** Originally created as `credit_packs` with `credit_amount` column (REQ-022). Renamed to `funding_packs` with `grant_cents` by REQ-023 to eliminate confusion between the rejected "abstract credits" concept and accounting credits (`credit_transactions`). See REQ-023 §2.3 for rationale.

This table is created by the Admin Pricing Dashboard (REQ-022 / backlog #16), renamed and re-seeded by REQ-023 (backlog #19). REQ-021 reads from it; it does not write to it.

### 4.4 Transaction Type Extension

REQ-020 defines `transaction_type` as `VARCHAR(20)` with values: `purchase`, `usage_debit`, `admin_grant`, `refund`.

REQ-021 adds one new value:
- `signup_grant` — Free credits granted on account creation

No schema change needed — `VARCHAR(20)` accommodates the new value (12 characters).

### 4.5 Indexes

The unique index on `stripe_event_id` (§4.2) serves both lookup and idempotency purposes. No additional indexes needed beyond those defined in REQ-020.

---

## 5. Funding Packs

### 5.1 Pack Definitions

Packs are **admin-configurable** via the Admin Pricing Dashboard (REQ-022 / backlog #16). The admin sets:
- **Name** and volume-based description
- **USD price** (what Stripe charges the user)
- **Grant amount** (USD cents credited to the user's balance — equals price for MVP)
- **Stripe Price ID** (links to the corresponding Stripe Product/Price)
- **Display order** and optional highlight label

**Default configuration** (set by REQ-023 seed data migration, admin-editable):

| Name | Price (USD) | Grant | Bonus | Description | Highlight |
|------|-------------|-------|-------|-------------|-----------|
| Starter | $5.00 | $5.00 | — | Analyze ~250 jobs and generate tailored materials | — |
| Standard | $10.00 | $10.00 | — | Analyze ~500 jobs and generate tailored materials | Most Popular |
| Pro | $15.00 | $15.00 | — | Analyze ~750 jobs and generate tailored materials | Best Value |

**Dollar-for-dollar for MVP.** `grant_cents == price_cents` — no volume bonuses. Volume bonuses can be added later by setting `grant_cents > price_cents`. See REQ-023 §2.2 for rationale.

**Stripe fee impact:** Stripe charges 2.9% + $0.30 per domestic card transaction. At the Starter tier ($5.00), Stripe takes $0.45 (9.0%). At the Pro tier ($15.00), Stripe takes $0.74 (4.9%). The per-model margin multipliers (configured in REQ-022) are the primary revenue source.

### 5.2 Stripe Product/Price Setup

Each pack corresponds to a Stripe Product with a one-time Price, created in the Stripe Dashboard:

1. Create a Product for each pack (e.g., "Zentropy Scout — Starter ($5)")
2. Add a one-time Price to each Product (e.g., $5.00 USD)
3. Copy the Price ID (`price_abc123`) into the `funding_packs` table via the admin UI

**Test vs Live:** Test mode and live mode have different Price IDs. The admin configures the appropriate IDs for each environment. No env var mapping needed — the Price IDs live in the database.

---

## 6. Stripe Integration

### 6.1 New Files

| File | Purpose |
|------|---------|
| `backend/app/services/stripe_service.py` | Stripe SDK interactions (session creation, customer management, webhook processing) |
| `backend/app/api/v1/credits.py` | Credit purchase endpoints (checkout, packs, purchases) |
| `backend/app/api/v1/webhooks.py` | Stripe webhook endpoint (signature verified, no auth) |
| `backend/app/schemas/credits.py` | Pydantic schemas for credit purchase request/response |

### 6.2 Stripe Service

```python
class StripeService:
    """Handles all Stripe SDK interactions."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_checkout_session(
        self,
        *,
        user_id: UUID,
        user_email: str,
        pack_id: UUID,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a Stripe Checkout Session and return the URL.

        Steps:
        1. Look up pack in funding_packs table (must be active)
        2. Look up or create Stripe Customer for this user
        3. Create Checkout Session with pack's Stripe Price ID
        4. Return session.url for frontend redirect
        """
        ...

    async def get_or_create_customer(
        self,
        user_id: UUID,
        email: str,
    ) -> str:
        """Look up or create a Stripe Customer, return customer ID.

        1. Check users.stripe_customer_id
        2. If exists, return it
        3. If not, create via Stripe API, save to users table, return it
        """
        ...

    async def handle_checkout_completed(
        self,
        event: stripe.Event,
    ) -> None:
        """Process a checkout.session.completed webhook event.

        Steps:
        1. Extract session from event.data.object
        2. Extract user_id and pack_id from session.metadata
        3. Look up pack to determine grant amount (grant_cents)
        4. Check idempotency (stripe_event_id already processed?)
        5. Insert credit_transactions row (type='purchase', amount_usd=+grant in USD)
        6. Atomically credit user's balance_usd
        """
        ...

    async def handle_charge_refunded(
        self,
        event: stripe.Event,
    ) -> None:
        """Process a charge.refunded webhook event.

        Steps:
        1. Extract charge from event.data.object
        2. Look up the original purchase transaction by reference_id
        3. Calculate refund amount in USD (matches Stripe refund amount)
        4. Check idempotency
        5. Insert credit_transactions row (type='refund', amount_usd=-refund_usd)
        6. Atomically debit user's balance_usd
        7. If balance goes negative after refund, log warning
        """
        ...

    async def grant_signup_credits(
        self,
        user_id: UUID,
    ) -> None:
        """Grant free starter credits to a new user.

        Steps:
        1. Read signup_grant_cents from system_config (REQ-023)
        2. If amount is 0, skip (grants disabled)
        3. Check if user already has a signup_grant transaction (prevent double-grant)
        4. Convert cents to USD, insert credit_transactions row (type='signup_grant', amount_usd=+grant_usd)
        5. Atomically credit user's balance_usd
        """
        ...
```

### 6.3 Checkout Session Metadata

The Checkout Session must include metadata so the webhook can identify the user and pack:

```python
session = await stripe.checkout.Session.create_async(
    customer=customer_id,
    line_items=[{"price": pack.stripe_price_id, "quantity": 1}],
    mode="payment",
    success_url=success_url,
    cancel_url=cancel_url,
    metadata={
        "user_id": str(user_id),
        "pack_id": str(pack.id),
        "grant_cents": str(pack.grant_cents),
    },
)
```

**Why store `grant_cents` in metadata?** If the admin changes pack pricing between session creation and webhook processing, the metadata preserves the grant amount the user was promised at checkout time. The webhook uses `metadata.grant_cents`, not the current pack definition.

### 6.4 Webhook Processing

The webhook endpoint is a public endpoint (no auth) that verifies the Stripe signature:

```python
@router.post("/stripe")
async def stripe_webhook(request: Request, db: DbSession) -> dict:
    """Handle Stripe webhook events.

    This endpoint:
    1. Reads the raw request body
    2. Verifies the Stripe-Signature header using the webhook secret
    3. Routes to the appropriate handler based on event type
    4. Returns 200 OK (Stripe retries on non-2xx)
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        raise APIError(code="INVALID_PAYLOAD", message="Invalid webhook payload", status_code=400)
    except stripe.SignatureVerificationError:
        raise APIError(code="INVALID_SIGNATURE", message="Invalid webhook signature", status_code=401)

    stripe_service = StripeService(db)

    if event.type == "checkout.session.completed":
        await stripe_service.handle_checkout_completed(event)
    elif event.type == "charge.refunded":
        await stripe_service.handle_charge_refunded(event)
    else:
        pass  # Ignore unhandled event types (return 200 to prevent retries)

    return {"received": True}
```

**Important:** The webhook endpoint must NOT use `CurrentUserId` or any auth dependency. Stripe calls this endpoint directly — there is no user session. The user is identified from the event metadata.

### 6.5 Stripe SDK Configuration

```python
import stripe

# Set in app startup or config initialization
stripe.api_key = settings.stripe_secret_key.get_secret_value()

# Pin Stripe API version to prevent breaking changes from Stripe's rolling updates.
# Use the latest version at implementation time. Check https://stripe.com/docs/upgrades
stripe.api_version = "2025-12-18"  # Example — use latest at time of implementation
```

**API version pinning:** Stripe makes breaking changes between API versions. Pinning ensures consistent behavior regardless of what version the Stripe Dashboard is set to. Update the pinned version intentionally (with testing) rather than getting surprise changes.

**Async support:** The Stripe Python SDK (v14+) provides async methods (`create_async`, `list_async`, etc.) compatible with FastAPI's async request handling.

### 6.6 Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid or inactive pack_id in checkout request | 400 Bad Request with `INVALID_PACK_ID` error code |
| Stripe API error during session creation | 502 Bad Gateway with `STRIPE_ERROR` error code. Log full error. Return user-friendly message. |
| Webhook signature invalid | 401 Unauthorized. Do NOT process the event. |
| Webhook payload malformed | 400 Bad Request. Do NOT process the event. |
| Duplicate webhook (same event_id) | 200 OK. Skip processing (idempotent). |
| Metadata missing user_id or pack_id | Log error, return 200 OK (prevent retries), do NOT credit balance. Alert for manual investigation. |
| User not found for user_id in metadata | Log error, return 200 OK, do NOT credit balance. Alert for manual investigation. |
| Stripe API unreachable | 502 Bad Gateway. User sees "Payment service temporarily unavailable." |

### 6.7 Balance Crediting (Atomic)

When a purchase is confirmed via webhook:

```sql
-- 1. Insert credit transaction (idempotent via stripe_event_id unique constraint)
-- grant_cents from metadata is in cents; convert to USD for the NUMERIC(10,6) column
INSERT INTO credit_transactions (user_id, amount_usd, transaction_type, reference_id, stripe_event_id, description)
VALUES (:user_id, :grant_usd, 'purchase', :stripe_session_id, :stripe_event_id, :description);

-- 2. Atomically credit balance
UPDATE users SET balance_usd = balance_usd + :grant_usd WHERE id = :user_id;
```

Both operations run in the same database transaction. If either fails, both roll back.

**Column names:** `amount_usd` and `balance_usd` are the actual column names — no renames needed. The USD-direct decision (REQ-023 §2.1) means these names are semantically correct.

### 6.8 REQ-020 Amendment: `reference_id` Type

REQ-020 v0.3 already changed `credit_transactions.reference_id` from `UUID` to `VARCHAR(255)` for Stripe ID compatibility. This amendment is complete — no further action needed.

The column stores:
- `llm_usage_records.id` (UUID cast to string) for `usage_debit` transactions
- Stripe Checkout Session ID (`cs_...`) for `purchase` transactions
- Stripe Refund ID (`re_...`) for `refund` transactions
- NULL for `signup_grant` and `admin_grant` transactions

---

## 7. API Endpoints

All endpoints except the webhook require authentication (`CurrentUserId` dependency). All follow REQ-006 response envelope conventions.

### 7.1 GET /api/v1/credits/packs

Returns the active funding packs. No authentication required (public pricing page).

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

**Display fields:** `price_display` and `amount_display` are computed server-side. For MVP (dollar-for-dollar), they are identical. If volume bonuses are added later, `amount_display` would show the bonus amount (e.g., "$12.00" for a $10 pack with 20% bonus). The frontend renders these strings directly — no client-side formatting needed.

### 7.2 POST /api/v1/credits/checkout

Creates a Stripe Checkout Session and returns the redirect URL. Requires authentication.

**Request Body:**
```json
{
    "pack_id": "a1b2c3d4-..."
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `pack_id` | UUID string | Yes | Must reference an active funding pack |

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
- `400 Bad Request` — Invalid or inactive `pack_id`
- `502 Bad Gateway` — Stripe API error

**Success/Cancel URLs:** The backend constructs these from the existing `frontend_url` config value:
- Success: `{frontend_url}/usage?status=success&session_id={CHECKOUT_SESSION_ID}`
- Cancel: `{frontend_url}/usage?status=cancelled`

**Note:** `{CHECKOUT_SESSION_ID}` is a Stripe template variable — do NOT interpolate it server-side. Pass it as a literal string in the URL. Stripe's redirect automatically replaces it with the actual session ID (e.g., `cs_test_a1b2c3...`) when redirecting the user back to your site.

### 7.3 GET /api/v1/credits/purchases

Returns the user's purchase history (credit transactions of type `purchase`, `signup_grant`, `admin_grant`, `refund`). Requires authentication.

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
            "description": "Standard Pack",
            "created_at": "2026-02-27T15:30:00Z"
        },
        {
            "id": "e5f6g7h8-...",
            "amount_usd": "0.100000",
            "amount_display": "$0.10",
            "transaction_type": "signup_grant",
            "description": "Welcome bonus — free starter balance",
            "created_at": "2026-02-25T10:00:00Z"
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

### 7.4 POST /api/v1/webhooks/stripe

Stripe webhook endpoint. No authentication — uses signature verification instead. See §6.4 for implementation details.

**Request:** Raw body from Stripe with `Stripe-Signature` header.

**Response:** `200 OK`
```json
{
    "received": true
}
```

**Error Responses:**
- `400 Bad Request` — Invalid payload
- `401 Unauthorized` — Invalid signature

**Router registration:** Add to `backend/app/api/v1/router.py`:
```python
from app.api.v1 import credits, webhooks
router.include_router(credits.router, prefix="/credits", tags=["credits"])
router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
```

---

## 8. Signup Grant Flow

### 8.1 When to Grant

The signup grant is applied when a new user account is created, after the user record is inserted:

1. User registers (OAuth, email+password, or magic link)
2. Backend creates the `users` row
3. Backend calls `stripe_service.grant_signup_credits(user_id)`
4. Service reads `signup_grant_cents` from `system_config` table (renamed by REQ-023)
5. If amount is 0, skip (grants disabled by admin)
6. Converts cents to USD, inserts a `credit_transactions` row with `transaction_type = 'signup_grant'`
7. User's `balance_usd` is atomically incremented by the grant amount

### 8.2 Integration Points

The signup grant logic must be called from all user creation paths:

| Path | File | Integration Point |
|------|------|-------------------|
| Google OAuth (new user) | `backend/app/core/account_linking.py` | Inside `find_or_create_user_for_oauth()`, after `db.flush()` on the newly created user (line ~147). This is where both Google and LinkedIn OAuth user creation happens — `auth_oauth.py` calls this function, it doesn't call `UserRepository.create()` directly. |
| LinkedIn OAuth (new user) | `backend/app/core/account_linking.py` | Same function as Google OAuth above — both providers share the same account linking flow. |
| Email + Password registration | `backend/app/api/v1/auth.py` | Inside `register()` endpoint, after `db.commit()` (line ~191). Note: the file is `auth.py`, not `auth_register.py`. |
| Magic Link (new user) | `backend/app/api/v1/auth_magic_link.py` | Inside `verify_magic_link()` endpoint, after `db.commit()` (line ~202). Only applies when the magic link creates a new user, not when it logs in an existing user. |

**Important:** OAuth user creation is centralized in `account_linking.py`, not in `auth_oauth.py`. The grant should be placed in the account linking module so both OAuth providers automatically get it without duplicating the call.

### 8.3 Idempotency

The grant is idempotent — if a `signup_grant` transaction already exists for the user, the grant is skipped:

```python
async def grant_signup_credits(self, user_id: UUID) -> None:
    existing = await self._credit_repo.find_by_user_and_type(
        user_id, "signup_grant"
    )
    if existing:
        return  # Already granted

    grant_cents = await self._get_system_config_int("signup_grant_cents")
    if grant_cents == 0:
        return  # Grants disabled

    grant_usd = Decimal(grant_cents) / Decimal(100)
    await self._credit_repo.create_transaction(
        user_id=user_id,
        amount_usd=grant_usd,
        transaction_type="signup_grant",
        description="Welcome bonus — free starter balance",
    )
    await self._user_repo.credit_balance(user_id, grant_usd)
```

### 8.4 Existing Users

Users who registered before REQ-021 is deployed will have zero balance and no `signup_grant` transaction. Options:

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Data migration grants credits to existing users | ✅ | Fair to early adopters. One-time migration script. Idempotent (checks for existing grant). |
| B. No retroactive grant | — | Punishes early users. Creates support burden. |

**Chosen: Option A — Data migration**

The Alembic migration includes a data migration step that inserts a `signup_grant` transaction for every existing user who doesn't already have one, and credits their balance accordingly.

---

## 9. Frontend

### 9.1 Credits Page

**Route:** `/usage`

**Sections:**

1. **Current Balance** — Large display showing USD amount (e.g., "$12.54") with usage bar (REQ-023 §5.1). Color coding same as nav bar (see REQ-020 §9.1): green > $1.00, amber $0.10–$1.00, red < $0.10.
2. **Funding Packs** — Cards for each active pack showing name, price, description, and "Add Funds" button. Server-rendered display strings (`price_display`, `amount_display`, `highlight_label`) are used directly — no client-side formatting needed. The pack with `highlight_label` is visually emphasized.
3. **Purchase History** — Paginated table showing all credit transactions (purchases, grants, refunds). Each row shows date, type, USD amount (`amount_display`), and description.

### 9.2 Checkout Flow (Frontend)

1. User clicks "Add Funds" on a pack card
2. Frontend calls `POST /api/v1/credits/checkout` with `{ pack_id: "a1b2c3d4-..." }`
3. Frontend receives `checkout_url` in response
4. Frontend redirects to `checkout_url` via `window.location.href = checkout_url`
5. User completes payment on Stripe's hosted page
6. Stripe redirects to `/usage?status=success&session_id=cs_test_...`
7. Frontend shows success toast: "Payment successful! Your balance has been updated."
8. Frontend invalidates the balance query key to refresh the balance display (see query key pattern below)

**Cancel flow:** If the user cancels on Stripe's page, they're redirected to `/usage?status=cancelled`. Frontend shows an info toast: "Purchase cancelled." No balance change.

### 9.3 Success/Cancel Handling

The `/usage` page checks URL query parameters on mount:

```typescript
// Pseudocode — must be wrapped in <Suspense> (see note below)
const searchParams = useSearchParams();
const status = searchParams.get("status");

useEffect(() => {
    if (status === "success") {
        showToast.success("Payment successful! Your balance has been updated.");
        queryClient.invalidateQueries({ queryKey: queryKeys.balance });
        // Clean up URL params
        router.replace("/usage");
    } else if (status === "cancelled") {
        showToast.info("Purchase cancelled.");
        router.replace("/usage");
    }
}, [status]);
```

**Next.js App Router requirement:** `useSearchParams()` must be wrapped in a `<Suspense>` boundary in Next.js 14+ App Router. Without it, the page will fail to build with a static rendering error. Either:
- Wrap the component using `useSearchParams()` in `<Suspense fallback={...}>`, or
- Export `const dynamic = "force-dynamic"` from the page (simpler but disables static optimization)

**Query key pattern:** Add credits-related keys to `frontend/src/lib/query-keys.ts` following the existing object-based pattern:

```typescript
// Add to queryKeys object in frontend/src/lib/query-keys.ts
balance: ["credits", "balance"] as const,
creditPacks: ["credits", "packs"] as const,
purchases: ["credits", "purchases"] as const,
```

**Toast pattern:** Use `showToast` from `frontend/src/lib/toast.ts` (wraps the `sonner` library with consistent durations). Do NOT use raw `toast` from sonner directly.

**Important:** The success toast is shown optimistically. The actual balance update happens asynchronously via webhook. In practice, Stripe sends the webhook within 1-2 seconds of checkout completion, so the balance is usually updated by the time the user sees the success page. If there's a delay, the balance will update on the next poll/navigation.

### 9.4 Navigation Update

The existing balance display in the nav bar (REQ-020 §9.1) links directly to `/usage` when clicked — no additional nav item needed.

---

## 10. Configuration

### 10.1 New Environment Variables

| Variable | Type | Default | Required | Notes |
|----------|------|---------|----------|-------|
| `STRIPE_SECRET_KEY` | SecretStr | — | Yes (if billing enabled) | Stripe secret key (`sk_test_...` or `sk_live_...`) |
| `STRIPE_WEBHOOK_SECRET` | SecretStr | — | Yes (if billing enabled) | Webhook signing secret (`whsec_...`) |
| `STRIPE_PUBLISHABLE_KEY` | str | — | Yes (if billing enabled) | Stripe publishable key (`pk_test_...` or `pk_live_...`). Exposed to frontend via API. |
| `CREDITS_ENABLED` | bool | `true` | No | Master switch. When `false`, checkout endpoint returns 503. Signup grant still works. |

**Removed from env vars (moved to admin UI):**
- ~~`STRIPE_PRICE_STARTER`~~, ~~`STRIPE_PRICE_STANDARD`~~, ~~`STRIPE_PRICE_PRO`~~ — Stripe Price IDs now stored in `funding_packs` table (§4.3)
- ~~`CREDITS_SIGNUP_GRANT_USD`~~ — Grant amount now in `system_config` table as `signup_grant_cents` (REQ-022/REQ-023)

**Note:** `FRONTEND_URL` already exists in `backend/app/core/config.py` (as `frontend_url`, default `http://localhost:3000`). It is used to construct success/cancel redirect URLs for Stripe Checkout — no new env var needed.

### 10.2 Production Security Checks

Add to `Settings.check_production_security()`:

```python
if self.environment == "production" and self.credits_enabled:
    if not self.stripe_secret_key.get_secret_value():
        raise ValueError("STRIPE_SECRET_KEY required in production")
    if not self.stripe_webhook_secret.get_secret_value():
        raise ValueError("STRIPE_WEBHOOK_SECRET required in production")
    if self.stripe_secret_key.get_secret_value().startswith("sk_test_"):
        raise ValueError("STRIPE_SECRET_KEY must be a live key in production")
```

### 10.3 Local Development

For local development without Stripe:

```bash
CREDITS_ENABLED=false          # Disables checkout endpoint
METERING_ENABLED=false         # REQ-020: disables metering + gating
```

The signup grant still works in this mode if `system_config.signup_grant_cents > 0`, allowing balance display testing.

For local development with Stripe (testing the checkout flow):

1. Create a Stripe test account
2. Use test mode keys (`sk_test_...`, `pk_test_...`)
3. Use Stripe CLI to forward webhooks: `stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe`
4. The CLI provides a webhook signing secret for local testing
5. Configure credit packs in admin UI with test Price IDs

**Configuration matrix:**

| `METERING_ENABLED` | `CREDITS_ENABLED` | Behavior |
|--------------------|-------------------|----------|
| `false` | `false` | Local dev: no metering, no gating, no checkout. LLM calls are free and untracked. |
| `false` | `true` | Invalid combination — credits have no purpose without metering. Log warning on startup. |
| `true` | `false` | Admin-grant only: metering and gating active, but users cannot self-purchase. Balance managed via `admin_grant` transactions or signup grants. |
| `true` | `true` | Production: full metering, gating, and self-service credit purchases via Stripe. |

---

## 11. Security Considerations

### 11.1 PCI Compliance

Stripe Checkout (hosted redirect) is **PCI DSS Level 1 compliant**. Card data never touches our servers. No SAQ (Self-Assessment Questionnaire) required beyond SAQ A (the simplest level). Stripe handles:
- Card number collection and validation
- 3D Secure authentication
- Card storage and tokenization
- Fraud detection

### 11.2 Webhook Security

| Threat | Mitigation |
|--------|------------|
| Forged webhook | Signature verification via `stripe.Webhook.construct_event()` using HMAC-SHA256 |
| Replay attack | Stripe includes a timestamp in the signature; the SDK rejects events older than the default tolerance (300 seconds) |
| Double crediting | Unique constraint on `stripe_event_id` in `credit_transactions` |
| Information leakage | Webhook endpoint returns minimal response (`{"received": true}`). No Stripe details in error responses. |
| Denial of service | Webhook endpoint is **exempt from rate limiting** (see below) |

**Webhook rate limiting decision:** The webhook endpoint is exempt from the `slowapi` rate limiter. Rationale:
- Stripe may send bursts of webhooks (especially during batch refunds or catch-up retries after downtime)
- Too-strict rate limiting causes missed events — Stripe retries with increasing backoff (up to 3 days), but delays credit delivery
- Signature verification (`stripe.Webhook.construct_event()`) provides sufficient security — only Stripe can produce valid signatures
- The rate limiter's key function uses auth state; webhooks have no auth and would incorrectly share the `unauth:{ip}` bucket with other unauthenticated requests

**Implementation:** Skip the `@limiter.limit()` decorator on the webhook endpoint. Alternatively, add the webhook path to a limiter exemption list if the limiter is applied globally via middleware.

### 11.3 Secret Management

| Secret | Storage | Exposure |
|--------|---------|----------|
| `STRIPE_SECRET_KEY` | Env var (SecretStr) | Never logged, never in API responses |
| `STRIPE_WEBHOOK_SECRET` | Env var (SecretStr) | Never logged, never in API responses |
| `STRIPE_PUBLISHABLE_KEY` | Env var (str) | Safe to expose to frontend (designed for client-side use) |

### 11.4 Metadata Integrity

The webhook handler trusts metadata from verified Stripe events. Since signature verification proves the event came from Stripe, and metadata was set by our backend during session creation, the metadata is trustworthy. However:

- **Always validate `user_id`** — Confirm the user exists in our database
- **Always validate `pack_id`** — Confirm the pack exists and was active at session creation time
- **Use `metadata.grant_cents`** for the actual credit grant (not the current pack definition, which may have changed)

---

## 12. Error Handling

### 12.1 Error Codes

| Code | HTTP Status | When |
|------|-------------|------|
| `INVALID_PACK_ID` | 400 | Request contains an unknown or inactive pack_id |
| `STRIPE_ERROR` | 502 | Stripe API returned an error (card declined, rate limit, etc.) |
| `INVALID_PAYLOAD` | 400 | Webhook payload is malformed |
| `INVALID_SIGNATURE` | 401 | Webhook signature verification failed |
| `CREDITS_UNAVAILABLE` | 503 | Credits system is disabled (`CREDITS_ENABLED=false`) or Stripe is unreachable |

### 12.2 Stripe Error Mapping

When Stripe returns an error during checkout session creation, map it to a user-friendly message:

| Stripe Error | User Message |
|--------------|-------------|
| `stripe.error.RateLimitError` | "Payment service is busy. Please try again in a moment." |
| `stripe.error.AuthenticationError` | (Internal — log and alert) "Payment service temporarily unavailable." |
| `stripe.error.APIConnectionError` | "Payment service temporarily unavailable. Please try again." |
| `stripe.error.InvalidRequestError` | (Internal — log and alert) "Payment service error. Please try again." |
| Any other `stripe.error.StripeError` | "Payment service error. Please try again." |

**Important:** Never expose Stripe error details (error codes, messages, request IDs) to the user. Log them server-side for debugging.

---

## 13. Testing Requirements

### 13.1 Unit Tests

| Test Area | Key Scenarios |
|-----------|---------------|
| StripeService.create_checkout_session | Valid pack creates session; inactive pack raises error; Stripe customer created on first purchase; existing customer reused |
| StripeService.handle_checkout_completed | Credits USD balance correctly; idempotent (same event_id skipped); missing metadata logged and skipped; user not found logged and skipped |
| StripeService.handle_charge_refunded | Debits balance correctly; partial refund handled proportionally; idempotent |
| StripeService.grant_signup_balance | Grants on first call; skips on duplicate; reads `signup_grant_cents` from system_config; zero amount disables grant; converts cents to USD correctly |
| Webhook signature verification | Valid signature accepted; invalid signature rejected (401); expired timestamp rejected |
| Packs endpoint | Returns active packs with correct pricing and USD display strings; no auth required |
| Checkout endpoint | Requires auth; valid pack returns URL; invalid/inactive pack returns 400 |

### 13.2 Integration Tests

| Test Area | Key Scenarios |
|-----------|---------------|
| End-to-end purchase | Checkout session created → webhook received → USD balance credited → visible in API |
| Duplicate webhook | Same event sent twice → balance credited only once |
| Signup grant + purchase | New user → signup grant → purchase → balance_usd = grant + purchase amount |
| Refund | Purchase → refund webhook → balance reduced proportionally → transaction history shows both |

### 13.3 Mocking Strategy

- **Stripe SDK:** Mock `stripe.checkout.Session.create_async`, `stripe.Customer.create_async`, `stripe.Webhook.construct_event` in unit tests
- **Webhook payloads:** Use Stripe's example event payloads from their documentation
- **No real Stripe calls** in automated tests — all Stripe interactions are mocked
- **system_config:** Mock `system_config` reads for signup grant amount in unit tests

---

## 14. Dependency

### 14.1 New Python Dependency

```
stripe>=14.0.0,<15.0.0
```

Add to `backend/pyproject.toml` in the `[project.dependencies]` section.

The `stripe` package provides:
- Async API methods (`create_async`, `list_async`)
- Webhook signature verification (`stripe.Webhook.construct_event`)
- Typed event objects
- Automatic retries with exponential backoff

### 14.2 Frontend Dependencies

No new frontend dependencies. The hosted redirect flow uses `window.location.href` — no Stripe client-side library needed.

---

## 15. Resolved Questions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Should the webhook endpoint be rate-limited differently than other API endpoints? | **Exempt from rate limiting.** | Stripe may send bursts of webhooks. Signature verification provides sufficient security. See §11.2 for full rationale. |
| 2 | Should we track Stripe Checkout Session IDs in a separate table for status polling? | **Defer — no session table for MVP.** | Webhook processing is near-instant in practice (1-2 seconds). Adding a `checkout_sessions` table and polling logic adds complexity without clear benefit. If webhook delays become a user issue, add session tracking as a follow-up. |
| 3 | Should the publishable key be exposed via an API endpoint or baked into the frontend build? | **Build-time env var (`NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`).** | Standard Next.js pattern. Simpler than an API endpoint. The publishable key is safe to embed in client-side code (Stripe designs it for this). Different environments (dev/prod) use different builds anyway. Note: the hosted redirect flow does not actually require the publishable key on the frontend (the redirect URL comes from the backend). This is only needed if we add embedded checkout in the future. |
| 4 | Should credits be denominated in USD or abstract units? | **USD-direct.** *(Changed in v0.4)* | Abstract credits were rejected due to denomination dilemma, redenomination risk, and existing USD infrastructure. See REQ-023 §2.1 for full rationale. Backlog PBI #19 documents the design review. |
| 5 | Should funding pack pricing be hardcoded or admin-configurable? | **Admin-configurable via DB.** | Pack definitions live in `funding_packs` table, managed through Admin Pricing Dashboard (REQ-022 / backlog #16). Allows changing packs, prices, and grant amounts without code deploys. Stripe Price IDs are also stored per-pack in DB. |
| 6 | Should the signup grant amount be an env var or admin-configurable? | **Admin-configurable via `system_config`.** | Allows adjusting the grant amount based on real usage data without code deploys. Stored as `signup_grant_cents` key in `system_config` table (REQ-022, renamed by REQ-023). |

---

## 16. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-27 | 0.1 | Initial draft |
| 2026-02-27 | 0.2 | Audit fixes: corrected signup grant integration points (OAuth uses `account_linking.py`, email+password is `auth.py` not `auth_register.py`), amended REQ-020 `reference_id` from `UUID` to `VARCHAR(255)` for Stripe ID compatibility, noted `FRONTEND_URL` already exists in config, resolved webhook rate limiting (exempt), added query key pattern following existing `query-keys.ts` convention, added Stripe API version pinning, documented `{CHECKOUT_SESSION_ID}` as Stripe template variable, clarified refund negative amount semantics, added Stripe fee impact analysis on pack pricing, added `Suspense` requirement for `useSearchParams`, added configuration matrix for `METERING_ENABLED` × `CREDITS_ENABLED`, added toast pattern note, resolved all 3 open questions |
| 2026-03-01 | 0.3 | **Major revision for abstract credits and admin-configurable pricing.** Changes driven by pricing/billing architecture decisions captured in backlog items #16 (Admin Pricing Dashboard & Model Registry), #19 (Credit Denomination & Display Configuration). Key changes: (1) Replaced all USD-denominated references with abstract credits throughout. (2) Credit pack definitions moved from hardcoded Python dict to admin-configurable `credit_packs` DB table. (3) Signup grant amount moved from `CREDITS_SIGNUP_GRANT_USD` env var to `system_config` table (`signup_grant_credits`). (4) Added explicit dependencies on REQs for backlog #16 and #19. (5) Added §3.3 prerequisite implementation order. (6) Added §4.3 `credit_packs` table reference (owned by #16, consumed by this REQ). (7) Stripe Price IDs moved from env vars to `credit_packs` table. (8) API responses now include server-rendered display strings via credit denomination formatting utility (#19). (9) Refund logic updated for proportional credit debit calculation. (10) Removed 3 Stripe Price env vars (now in DB). (11) Added 3 resolved questions (#4–#6) for architecture decisions. (12) Narrowed scope: pricing config, model registry, and credit denomination are explicitly out of scope (owned by #16 and #19). |
| 2026-03-02 | 0.4 | **Errata: USD-direct billing replaces abstract credits.** Design review (documented in backlog PBI #19 and REQ-023) rejected abstract credits in favor of USD-direct billing. Key changes: (1) All "abstract credits" references replaced with USD amounts throughout. (2) Pack definitions updated from $5/50K, $15/175K, $40/500K with volume bonuses to $5/$10/$15 dollar-for-dollar with volume-based descriptions. (3) `signup_grant_credits` → `signup_grant_cents` (10 = $0.10 default). (4) Display strings changed from "50,000 credits" to "$5.00". (5) Column renames cancelled — `balance_usd` and `amount_usd` are correct as-is. (6) Dependencies updated: backlog #19 now provides corrected seed data and config key (REQ-023), not `credits_per_dollar` and formatting utility. (7) Resolved question #4 changed from "Abstract credits" to "USD-direct." (8) Added errata notice to §1. See REQ-023 §6.1 for full change map. |
| 2026-03-10 | 0.6 | **REQ-029 supersession + errata.** (1) Added supersession notice — REQ-029 supersedes Stripe SDK/implementation sections; REQ-021 remains authoritative for design rationale, signup grant integration points, frontend UX patterns, webhook rate limiting rationale, and resolved questions. (2) Added `**Backlog Item:** #13` header field. (3) Fixed `funding_packs.stripe_price_id` from `NOT NULL` to nullable — matches actual schema (column is nullable until admin configures Stripe). (4) Marked REQ-023 as ✅ in §3.3 prerequisite order. (5) Fixed all frontend page routes from `/credits` to `/usage` — the actual page lives at `frontend/src/app/(main)/usage/page.tsx`, not `/credits`. Affects §7.2 redirect URLs, §9.1 route, §9.2 redirect flows, §9.3 `router.replace()` calls, §9.4 nav link. API routes (`/api/v1/credits/*`) are unchanged. |
| 2026-03-02 | 0.5 | **Naming alignment with REQ-023.** All table/column/metadata references updated to match REQ-023's rename migration (§4.1, §2.3): (1) `credit_packs` → `funding_packs` throughout (§2.2, §3.1, §3.3, §4.3, §5.2, §6.2, §10.1, §15). (2) `credit_amount` → `grant_cents` throughout (§4.3 CREATE TABLE, §5.1 pack definitions, §6.2 service pseudocode, §6.3 metadata, §6.7 SQL, §7.1 JSON responses, §11.4). (3) §4.3 section header renamed "Credit Packs Table" → "Funding Packs Table" with naming history note. (4) Updated errata notice to cover both v0.4 and v0.5. (5) §3.3 prerequisite order now notes REQ-023 handles the rename migration. (6) §5 section header renamed "Credit Packs" → "Funding Packs". |
| 2026-03-29 | 0.7 | Errata: `stripe_service.py` → `services/billing/stripe_service.py` per REQ-031 (Services Reorganization). See REQ-031 §5 for complete mapping. |
