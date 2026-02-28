# REQ-021: Credits & Billing

**Status:** Not Started
**Version:** 0.2
**PRD Reference:** §6 Technical Architecture
**Last Updated:** 2026-02-27

---

## 1. Overview

This document specifies the system for purchasing credits via Stripe Checkout, crediting user balances, and displaying purchase history. It builds on the metering infrastructure defined in REQ-020 (Token Metering & Usage Tracking).

### 1.1 Problem Statement

REQ-020 defines a per-user USD balance (`users.balance_usd`) and an append-only credit ledger (`credit_transactions`), but provides no mechanism for users to add funds. Without a purchase flow:

1. **No revenue** — Users cannot pay for the service
2. **Zero balance on signup** — New users are immediately gated (402) on their first LLM call
3. **No self-service** — Balance can only be changed via manual database operations or admin grants

### 1.2 Solution

A Stripe Checkout integration that:
1. **Offers** predefined credit packs at fixed USD prices
2. **Redirects** users to Stripe's hosted checkout page for secure payment
3. **Processes** completed payments via Stripe webhooks
4. **Credits** the user's balance atomically via the `credit_transactions` ledger (REQ-020 §4.3)
5. **Displays** purchase history and current balance in the frontend
6. **Grants** a small free trial balance on signup so new users can try the service

### 1.3 Scope

| In Scope | Out of Scope |
|----------|-------------|
| Stripe Checkout (hosted redirect mode) | Stripe Elements / embedded card forms |
| Predefined credit packs (fixed pricing) | Custom amounts / pay-what-you-want |
| One-time purchases | Subscriptions / recurring billing |
| Stripe webhook handling (signature verified) | Stripe Connect / marketplace payouts |
| Idempotent webhook processing | Invoice generation / tax calculation |
| Free trial grant on signup | Referral / promo codes |
| Stripe Customer creation per user | Saved payment methods / card-on-file |
| Purchase history API + frontend | Admin refund UI (manual via Stripe Dashboard) |
| Frontend credits purchase page | Mobile payment (Apple Pay, Google Pay) |

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
1. User clicks "Buy" on a credit pack
2. Frontend calls `POST /api/v1/credits/checkout` with the pack ID
3. Backend creates a Stripe Checkout Session with the pack's price and the user's ID in metadata
4. Backend returns the Checkout Session URL
5. Frontend redirects the user to Stripe's hosted checkout page
6. User completes payment on Stripe's domain
7. Stripe redirects user back to our success/cancel URL
8. Stripe sends a `checkout.session.completed` webhook to our backend
9. Backend verifies webhook signature, credits the user's balance

### 2.2 Pricing Strategy

**How should credit packs be structured?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Fixed credit packs (3 tiers) | ✅ | Simple, clear pricing. Users pick a pack. No decision fatigue. Standard SaaS pattern. Easy to implement — just a dict mapping pack ID to price/credit amount. |
| B. Custom amount (pay-what-you-want) | — | More flexible but adds UI complexity (amount input, validation, dynamic Stripe price creation). No clear user demand. |
| C. Single fixed amount | — | Too restrictive. Users with different budgets want different options. |

**Chosen: Option A — Fixed Credit Packs (3 Tiers)**

See §5 for pack definitions.

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

The `credit_transactions` table (REQ-020 §4.3) gains a `stripe_event_id` column with a unique index. When a webhook arrives:
1. Verify signature
2. Check if a `credit_transactions` row exists with this `stripe_event_id`
3. If yes → return 200 (already processed, idempotent)
4. If no → process the event and insert the row

### 2.5 Free Trial Grant

**Should new users get free credits?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. $1.00 grant on signup | ✅ | Lets users explore all features before paying. At current pricing, $1.00 covers ~30 job extractions or ~3 cover letters — enough to evaluate the product. Creates a `credit_transactions` row with `type = 'signup_grant'`. Configurable via env var. |
| B. No free credits | — | New users hit 402 immediately. Terrible onboarding experience. Forces payment before users understand value. |
| C. Free tier (unlimited free usage up to N calls) | — | Requires separate gating logic. Harder to implement than a simple balance grant. Doesn't teach users about the credit model. |

**Chosen: Option A — $1.00 Signup Grant**

Granted once per user at account creation. The grant amount is configurable via `CREDITS_SIGNUP_GRANT_USD` env var (default: `1.00`). Creates a `credit_transactions` row with `transaction_type = 'signup_grant'`. This is a new transaction type added to the enum defined in REQ-020 §4.3.

**Updated `transaction_type` enum:** `purchase`, `usage_debit`, `admin_grant`, `refund`, `signup_grant`.

### 2.6 Refund Handling

**How should refunds work?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Manual via Stripe Dashboard only | ✅ | Refunds are rare at MVP scale. Stripe Dashboard provides full refund UI (partial, full, with reason). No custom admin UI needed. Webhook handles the balance adjustment automatically. |
| B. In-app refund UI | — | Requires admin role system (not implemented). Over-engineering for MVP. |

**Chosen: Option A — Manual via Stripe Dashboard**

When a refund is issued via Stripe Dashboard, the `charge.refunded` webhook fires. The backend creates a `credit_transactions` row with `transaction_type = 'refund'` and a **negative** `amount_usd`, then reduces `users.balance_usd` accordingly.

**Why negative?** A refund returns money to the user via Stripe, so we must remove the corresponding credits from their balance. The negative amount reflects credits being taken back — the money refund happens entirely on Stripe's side. If the user has already spent some or all of the refunded credits, their balance may go negative. This is expected and logged as a warning.

---

## 3. Dependencies

### 3.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-020 Token Metering v0.2 | Foundation | `credit_transactions` table, `users.balance_usd` column, balance API endpoints |
| REQ-005 Database Schema v0.10 | Schema | `users` table to extend with `stripe_customer_id` |
| REQ-006 API Contract v0.8 | Integration | Response envelope pattern (§7), error codes (§8) |
| REQ-013 Authentication v0.1 | Integration | `CurrentUserId` dependency, user creation flow (for signup grant) |

### 3.2 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-012 Frontend Application | Integration | Credits page, balance display |

---

## 4. Database Schema

### 4.1 Users Table Extension

Add one column to the existing `users` table (in addition to `balance_usd` from REQ-020):

```sql
ALTER TABLE users ADD COLUMN stripe_customer_id VARCHAR(255) UNIQUE;
```

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `stripe_customer_id` | `VARCHAR(255)` | NULL | NULL | Stripe Customer ID (e.g., `cus_abc123`). Created on first purchase. Unique constraint prevents duplicate customers. |

### 4.2 Credit Transactions Extension

Add one column to the `credit_transactions` table defined in REQ-020 §4.3:

```sql
ALTER TABLE credit_transactions ADD COLUMN stripe_event_id VARCHAR(255) UNIQUE;
```

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `stripe_event_id` | `VARCHAR(255)` | NULL | NULL | Stripe event ID (e.g., `evt_abc123`). Used for webhook idempotency. Unique constraint prevents double-crediting. Only populated for `purchase` and `refund` transaction types. |

**Migration note:** This column is added to the table created by REQ-020's migration. If both REQ-020 and REQ-021 are implemented together, a single migration can create the table with this column included. If REQ-020 is implemented first, REQ-021 adds the column in a separate migration.

### 4.3 Transaction Type Extension

REQ-020 §4.3 defines `transaction_type` as `VARCHAR(20)` with values: `purchase`, `usage_debit`, `admin_grant`, `refund`.

REQ-021 adds one new value:
- `signup_grant` — Free credits granted on account creation

No schema change needed — `VARCHAR(20)` accommodates the new value (12 characters).

### 4.4 Indexes

The unique index on `stripe_event_id` (§4.2) serves both lookup and idempotency purposes. No additional indexes needed beyond those defined in REQ-020 §4.4.

---

## 5. Credit Packs

### 5.1 Pack Definitions

Three fixed-price credit packs:

| Pack ID | Name | Price (USD) | Credits (USD) | Bonus | Stripe Product |
|---------|------|-------------|---------------|-------|----------------|
| `starter` | Starter | $5.00 | $5.00 | — | Created in Stripe Dashboard |
| `standard` | Standard | $15.00 | $16.50 | +10% ($1.50) | Created in Stripe Dashboard |
| `pro` | Pro | $40.00 | $46.00 | +15% ($6.00) | Created in Stripe Dashboard |

**Bonus rationale:** Higher tiers offer a bonus to incentivize larger purchases, reducing Stripe's per-transaction fixed fee ($0.30) as a percentage of revenue.

**Stripe fee impact:** Stripe charges 2.9% + $0.30 per domestic card transaction. At the Starter tier ($5.00), Stripe takes $0.445 (8.9%). At the Pro tier ($40.00), Stripe takes $1.46 (3.7%). The metering margin (REQ-020, default 30%) applied to LLM costs is the primary revenue source — pack pricing is designed to cover Stripe fees while keeping credit amounts intuitive. The Starter pack intentionally has no bonus because the per-transaction fee is proportionally highest; the bonus on higher tiers compensates users for making fewer, larger purchases.

**What the user gets:** The credit amount is added to their `balance_usd`. For example, purchasing the Standard pack adds $16.50 to their balance, which they can spend on LLM calls at the metered rates defined in REQ-020 §5.

### 5.2 Pack Configuration

Pack definitions are hardcoded in a Python dict:

```python
CREDIT_PACKS: dict[str, CreditPack] = {
    "starter": CreditPack(
        id="starter",
        name="Starter",
        price_usd=Decimal("5.00"),
        credit_usd=Decimal("5.00"),
        description="Get started with Zentropy Scout",
    ),
    "standard": CreditPack(
        id="standard",
        name="Standard",
        price_usd=Decimal("15.00"),
        credit_usd=Decimal("16.50"),
        description="Most popular — 10% bonus credits",
    ),
    "pro": CreditPack(
        id="pro",
        name="Pro",
        price_usd=Decimal("40.00"),
        credit_usd=Decimal("46.00"),
        description="Best value — 15% bonus credits",
    ),
}
```

**Why hardcoded?** Same rationale as REQ-020's pricing table — simple, version-controlled, no admin UI needed. Pack changes require a code deploy.

### 5.3 Stripe Product/Price Setup

Each credit pack corresponds to a Stripe Product with a one-time Price, created manually in the Stripe Dashboard:

1. Create a Product for each pack (e.g., "Starter Credit Pack")
2. Add a one-time Price to each Product (e.g., $5.00 USD)
3. Copy the Price ID (`price_abc123`) into the configuration

The Price IDs are stored as environment variables:

```bash
STRIPE_PRICE_STARTER=price_xxx
STRIPE_PRICE_STANDARD=price_yyy
STRIPE_PRICE_PRO=price_zzz
```

**Why env vars for Price IDs?** Test mode and live mode have different Price IDs. Environment variables allow the same code to work in both environments without code changes.

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
        pack_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a Stripe Checkout Session and return the URL.

        Steps:
        1. Validate pack_id exists in CREDIT_PACKS
        2. Look up or create Stripe Customer for this user
        3. Create Checkout Session with pack's Price ID
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
        3. Look up pack to determine credit_usd amount
        4. Check idempotency (stripe_event_id already processed?)
        5. Insert credit_transactions row (type='purchase', amount=+credit_usd)
        6. Atomically credit users.balance_usd
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
        3. Calculate refund amount (may be partial)
        4. Check idempotency
        5. Insert credit_transactions row (type='refund', amount=-refund_amount)
        6. Atomically debit users.balance_usd
        7. If balance goes negative after refund, log warning (user spent refunded credits)
        """
        ...

    async def grant_signup_credits(
        self,
        user_id: UUID,
    ) -> None:
        """Grant free trial credits to a new user.

        Steps:
        1. Check if user already has a signup_grant transaction (prevent double-grant)
        2. Insert credit_transactions row (type='signup_grant', amount=+grant_amount)
        3. Atomically credit users.balance_usd
        """
        ...
```

### 6.3 Checkout Session Metadata

The Checkout Session must include metadata so the webhook can identify the user and pack:

```python
session = await stripe.checkout.Session.create_async(
    customer=customer_id,
    line_items=[{"price": price_id, "quantity": 1}],
    mode="payment",
    success_url=success_url,
    cancel_url=cancel_url,
    metadata={
        "user_id": str(user_id),
        "pack_id": pack_id,
        "credit_usd": str(credit_usd),
    },
)
```

**Why store `credit_usd` in metadata?** If pack pricing changes between session creation and webhook processing, the metadata preserves the amount the user was promised at checkout time. The webhook uses `metadata.credit_usd`, not the current pack definition.

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
| Invalid pack_id in checkout request | 400 Bad Request with `INVALID_PACK_ID` error code |
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
INSERT INTO credit_transactions (user_id, amount_usd, transaction_type, reference_id, stripe_event_id, description)
VALUES (:user_id, :credit_usd, 'purchase', :stripe_session_id, :stripe_event_id, :description);

-- 2. Atomically credit balance
UPDATE users SET balance_usd = balance_usd + :credit_usd WHERE id = :user_id;
```

Both operations run in the same database transaction. If either fails, both roll back.

### 6.8 REQ-020 Amendment: `reference_id` Type Change

REQ-020 §4.3 defines `credit_transactions.reference_id` as `UUID`. This is incompatible with Stripe references — Checkout Session IDs (e.g., `cs_test_a1b2c3...`) and Stripe event IDs are opaque strings, not UUIDs.

**Required change to REQ-020 §4.3:**

```sql
-- BEFORE (REQ-020 v0.2)
reference_id    UUID,

-- AFTER (amended)
reference_id    VARCHAR(255),
```

The column stores:
- `llm_usage_records.id` (UUID cast to string) for `usage_debit` transactions
- Stripe Checkout Session ID (`cs_...`) for `purchase` transactions
- Stripe Refund ID (`re_...`) for `refund` transactions
- NULL for `signup_grant` and `admin_grant` transactions

This is a REQ-020 amendment, not a REQ-021-only change. The REQ-020 migration must use `VARCHAR(255)` instead of `UUID` for this column.

---

## 7. API Endpoints

All endpoints except the webhook require authentication (`CurrentUserId` dependency). All follow REQ-006 response envelope conventions.

### 7.1 GET /api/v1/credits/packs

Returns the available credit packs. No authentication required (public pricing page).

**Response:** `200 OK`
```json
{
    "data": [
        {
            "id": "starter",
            "name": "Starter",
            "price_usd": "5.00",
            "credit_usd": "5.00",
            "bonus_usd": "0.00",
            "description": "Get started with Zentropy Scout"
        },
        {
            "id": "standard",
            "name": "Standard",
            "price_usd": "15.00",
            "credit_usd": "16.50",
            "bonus_usd": "1.50",
            "description": "Most popular — 10% bonus credits"
        },
        {
            "id": "pro",
            "name": "Pro",
            "price_usd": "40.00",
            "credit_usd": "46.00",
            "bonus_usd": "6.00",
            "description": "Best value — 15% bonus credits"
        }
    ]
}
```

### 7.2 POST /api/v1/credits/checkout

Creates a Stripe Checkout Session and returns the redirect URL. Requires authentication.

**Request Body:**
```json
{
    "pack_id": "standard"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `pack_id` | string | Yes | Must be one of: `starter`, `standard`, `pro` |

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
- `400 Bad Request` — Invalid `pack_id`
- `502 Bad Gateway` — Stripe API error

**Success/Cancel URLs:** The backend constructs these from the existing `frontend_url` config value:
- Success: `{frontend_url}/credits?status=success&session_id={CHECKOUT_SESSION_ID}`
- Cancel: `{frontend_url}/credits?status=cancelled`

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
            "amount_usd": "16.500000",
            "transaction_type": "purchase",
            "description": "Standard Credit Pack",
            "created_at": "2026-02-27T15:30:00Z"
        },
        {
            "id": "e5f6g7h8-...",
            "amount_usd": "1.000000",
            "transaction_type": "signup_grant",
            "description": "Welcome bonus — free trial credits",
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
4. A `credit_transactions` row is inserted with `transaction_type = 'signup_grant'`
5. `users.balance_usd` is atomically incremented by the grant amount

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

    grant_amount = Decimal(str(settings.credits_signup_grant_usd))
    await self._credit_repo.create_transaction(
        user_id=user_id,
        amount_usd=grant_amount,
        transaction_type="signup_grant",
        description="Welcome bonus — free trial credits",
    )
    await self._user_repo.credit_balance(user_id, grant_amount)
```

### 8.4 Existing Users

Users who registered before REQ-021 is deployed will have `balance_usd = 0.000000` and no `signup_grant` transaction. Options:

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Data migration grants credits to existing users | ✅ | Fair to early adopters. One-time migration script. Idempotent (checks for existing grant). |
| B. No retroactive grant | — | Punishes early users. Creates support burden. |

**Chosen: Option A — Data migration**

The Alembic migration includes a data migration step that inserts a `signup_grant` transaction for every existing user who doesn't already have one, and credits their `balance_usd` accordingly.

---

## 9. Frontend

### 9.1 Credits Page

**Route:** `/credits`

**Sections:**

1. **Current Balance** — Large display showing `$X.XX` with color coding (same as nav bar, see REQ-020 §9.1)
2. **Credit Packs** — Three cards showing pack name, price, credit amount, bonus, and "Buy" button. The Standard pack is highlighted as "Most Popular".
3. **Purchase History** — Paginated table showing all credit transactions (purchases, grants, refunds). Each row shows date, type, amount, and description.

### 9.2 Checkout Flow (Frontend)

1. User clicks "Buy" on a credit pack card
2. Frontend calls `POST /api/v1/credits/checkout` with `{ pack_id: "standard" }`
3. Frontend receives `checkout_url` in response
4. Frontend redirects to `checkout_url` via `window.location.href = checkout_url`
5. User completes payment on Stripe's hosted page
6. Stripe redirects to `/credits?status=success&session_id=cs_test_...`
7. Frontend shows success toast: "Payment successful! Your credits have been added."
8. Frontend invalidates the balance query key to refresh the balance display (see query key pattern below)

**Cancel flow:** If the user cancels on Stripe's page, they're redirected to `/credits?status=cancelled`. Frontend shows an info toast: "Purchase cancelled." No balance change.

### 9.3 Success/Cancel Handling

The `/credits` page checks URL query parameters on mount:

```typescript
// Pseudocode — must be wrapped in <Suspense> (see note below)
const searchParams = useSearchParams();
const status = searchParams.get("status");

useEffect(() => {
    if (status === "success") {
        showToast.success("Payment successful! Your credits have been added.");
        queryClient.invalidateQueries({ queryKey: queryKeys.balance });
        // Clean up URL params
        router.replace("/credits");
    } else if (status === "cancelled") {
        showToast.info("Purchase cancelled.");
        router.replace("/credits");
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

Add a "Credits" link to the top navigation bar:

```typescript
// Add to PRIMARY_NAV_ITEMS or secondary nav
{ href: "/credits", label: "Credits", icon: CreditCard }
```

Alternatively, the balance display in the nav bar (REQ-020 §9.1) can link directly to `/credits` when clicked — avoiding an additional nav item.

---

## 10. Configuration

### 10.1 New Environment Variables

| Variable | Type | Default | Required | Notes |
|----------|------|---------|----------|-------|
| `STRIPE_SECRET_KEY` | SecretStr | — | Yes (if billing enabled) | Stripe secret key (`sk_test_...` or `sk_live_...`) |
| `STRIPE_WEBHOOK_SECRET` | SecretStr | — | Yes (if billing enabled) | Webhook signing secret (`whsec_...`) |
| `STRIPE_PUBLISHABLE_KEY` | str | — | Yes (if billing enabled) | Stripe publishable key (`pk_test_...` or `pk_live_...`). Exposed to frontend via API. |
| `STRIPE_PRICE_STARTER` | str | — | Yes (if billing enabled) | Stripe Price ID for Starter pack |
| `STRIPE_PRICE_STANDARD` | str | — | Yes (if billing enabled) | Stripe Price ID for Standard pack |
| `STRIPE_PRICE_PRO` | str | — | Yes (if billing enabled) | Stripe Price ID for Pro pack |
| `CREDITS_ENABLED` | bool | `true` | No | Master switch. When `false`, checkout endpoint returns 503. Signup grant still works. |
| `CREDITS_SIGNUP_GRANT_USD` | float | `1.00` | No | Amount of free credits granted on signup. Set to `0` to disable. |

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
CREDITS_SIGNUP_GRANT_USD=1.00  # Signup grant still works
METERING_ENABLED=false         # REQ-020: disables metering + gating
```

This allows local development without Stripe keys while still granting trial credits for testing the balance display.

**Configuration matrix:**

| `METERING_ENABLED` | `CREDITS_ENABLED` | Behavior |
|--------------------|-------------------|----------|
| `false` | `false` | Local dev: no metering, no gating, no checkout. LLM calls are free and untracked. |
| `false` | `true` | Invalid combination — credits have no purpose without metering. Log warning on startup. |
| `true` | `false` | Admin-grant only: metering and gating active, but users cannot self-purchase. Balance managed via `admin_grant` transactions or signup grants. |
| `true` | `true` | Production: full metering, gating, and self-service credit purchases via Stripe. |

For local development with Stripe (testing the checkout flow):

1. Create a Stripe test account
2. Use test mode keys (`sk_test_...`, `pk_test_...`)
3. Use Stripe CLI to forward webhooks: `stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe`
4. The CLI provides a webhook signing secret for local testing

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
- **Always validate `pack_id`** — Confirm the pack exists in our configuration
- **Use `metadata.credit_usd`** for the actual credit amount (not the current pack definition, which may have changed)

---

## 12. Error Handling

### 12.1 Error Codes

| Code | HTTP Status | When |
|------|-------------|------|
| `INVALID_PACK_ID` | 400 | Request contains an unknown pack_id |
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
| StripeService.create_checkout_session | Valid pack_id creates session; invalid pack_id raises error; Stripe customer created on first purchase; existing customer reused |
| StripeService.handle_checkout_completed | Credits balance correctly; idempotent (same event_id skipped); missing metadata logged and skipped; user not found logged and skipped |
| StripeService.handle_charge_refunded | Debits balance correctly; partial refund handled; idempotent |
| StripeService.grant_signup_credits | Grants on first call; skips on duplicate; configurable amount; zero amount disables grant |
| Webhook signature verification | Valid signature accepted; invalid signature rejected (401); expired timestamp rejected |
| Credit packs endpoint | Returns all packs with correct pricing; no auth required |
| Checkout endpoint | Requires auth; valid pack returns URL; invalid pack returns 400 |

### 13.2 Integration Tests

| Test Area | Key Scenarios |
|-----------|---------------|
| End-to-end purchase | Checkout session created → webhook received → balance credited → visible in API |
| Duplicate webhook | Same event sent twice → balance credited only once |
| Signup grant + purchase | New user → signup grant → purchase → balance = grant + purchase credits |
| Refund | Purchase → refund webhook → balance reduced → transaction history shows both |

### 13.3 Mocking Strategy

- **Stripe SDK:** Mock `stripe.checkout.Session.create_async`, `stripe.Customer.create_async`, `stripe.Webhook.construct_event` in unit tests
- **Webhook payloads:** Use Stripe's example event payloads from their documentation
- **No real Stripe calls** in automated tests — all Stripe interactions are mocked

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

---

## 16. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-27 | 0.1 | Initial draft |
| 2026-02-27 | 0.2 | Audit fixes: corrected signup grant integration points (OAuth uses `account_linking.py`, email+password is `auth.py` not `auth_register.py`), amended REQ-020 `reference_id` from `UUID` to `VARCHAR(255)` for Stripe ID compatibility, noted `FRONTEND_URL` already exists in config, resolved webhook rate limiting (exempt), added query key pattern following existing `query-keys.ts` convention, added Stripe API version pinning, documented `{CHECKOUT_SESSION_ID}` as Stripe template variable, clarified refund negative amount semantics, added Stripe fee impact analysis on pack pricing, added `Suspense` requirement for `useSearchParams`, added configuration matrix for `METERING_ENABLED` × `CREDITS_ENABLED`, added toast pattern note, resolved all 3 open questions |
