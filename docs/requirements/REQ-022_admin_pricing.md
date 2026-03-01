# REQ-022: Admin Pricing Dashboard & Model Registry

**Status:** Not Started
**Version:** 0.1
**PRD Reference:** §6 Technical Architecture
**Last Updated:** 2026-03-01
**Backlog Item:** #16

---

## 1. Overview

This document specifies the Admin Pricing Dashboard and Model Registry — the system for managing LLM pricing, model registration, task routing, credit packs, and system configuration through a database-backed admin interface. It replaces all hardcoded pricing dicts, routing tables, and margin multipliers with admin-configurable database tables.

### 1.1 Problem Statement

Zentropy Scout currently hardcodes critical business configuration in Python source files:

1. **LLM pricing** — An 8-entry `_LLM_PRICING` dict in `metering_service.py` (lines 27–64) maps `(provider, model)` to per-1K-token costs. When providers change prices, a code deploy is required.
2. **Task routing** — Three `DEFAULT_*_ROUTING` dicts in the LLM adapters (Claude lines 49–62, OpenAI lines 49–62, Gemini lines 51–64) map `TaskType` → model. Changing which model handles a task type requires a code deploy.
3. **Margin multiplier** — A single `METERING_MARGIN_MULTIPLIER` env var (default 1.30) applies uniformly to all models. Cheap models that warrant higher margins (3–4×) and expensive models that should have thin margins (1.1–1.5×) cannot be priced differently.
4. **No model registry** — Any model string can be passed to a provider. If a provider releases a new model and code routes to it before pricing is configured, usage goes unmetered.
5. **No credit packs** — The Credits & Billing system (REQ-021) needs admin-configurable credit pack definitions that do not exist yet.
6. **No system configuration** — Global settings like signup grant amount have no database-backed store.

### 1.2 Solution

A set of five database tables and an admin interface that:

1. **Registers** all available models in a canonical `model_registry` — calls to unregistered models are blocked
2. **Prices** each model individually with per-model margins and effective dates via `pricing_config`
3. **Routes** task types to models per provider via `task_routing_config` — admin can reroute without code deploys
4. **Defines** credit packs (name, price, credit amount) via `credit_packs` — consumed by the Stripe integration (REQ-021)
5. **Stores** global settings in `system_config` — key-value store for signup grants, denomination, etc.
6. **Exposes** admin CRUD API endpoints protected by an `is_admin` gate
7. **Provides** a single-page admin UI with tabbed navigation

### 1.3 Scope

| In Scope | Out of Scope |
|----------|-------------|
| 5 new DB tables (pricing_config, model_registry, task_routing_config, credit_packs, system_config) | Stripe integration (REQ-021) |
| `is_admin` column on users table | Full RBAC / role system |
| Admin auth via `ADMIN_EMAILS` env var + UI promotion | OAuth scopes / API key auth |
| Migrate metering service from hardcoded → DB pricing | Credit denomination / display formatting (backlog #19) |
| Migrate LLM adapters from hardcoded → DB routing | Column renames (`balance_usd` → `balance_credits`) (backlog #19) |
| Block unregistered models | Real-time pricing API from providers |
| Admin CRUD API for all 5 tables | Usage analytics / cost forecasting |
| Single-page admin UI with tabs | Multi-page admin dashboard |
| Seed migration with current hardcoded values | Automated provider price monitoring |
| Effective dates on pricing changes | |
| Per-model margin multipliers | |

---

## 2. Design Decisions

### 2.1 Pricing Storage

**Where should LLM pricing live?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Hardcoded Python dict | — | Current approach (REQ-020 §2.4). Simple but requires code deploys for price changes. Uniform margin prevents granular pricing. |
| B. Database table with per-model margins | ✅ | Admin-configurable. Per-model margins allow cheap models (Haiku, Flash, 4o-mini) to carry 3–4× margin while expensive models (Sonnet, GPT-4o) carry 1.1–1.5×. Effective dates allow scheduling future price changes. |
| C. External pricing service / API | — | Over-engineering. No standard pricing API exists across providers. Adds latency and a new failure mode. |

**Chosen: Option B — Database table with per-model margins**

Each `(provider, model)` pair gets its own row in `pricing_config` with individual `input_cost_per_1k`, `output_cost_per_1k`, and `margin_multiplier`. An `effective_date` column enables scheduling price changes for the future.

### 2.2 Model Registration Strategy

**How should unknown models be handled?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Fallback pricing (current behavior) | — | REQ-020 uses highest-tier pricing as fallback for unknown models. Risk: new models can run unmetered or underpriced if the fallback doesn't match actual costs. |
| B. Block unregistered models | ✅ | An LLM call to an unregistered `(provider, model)` pair returns an error immediately. Forces admin to register and price a model before it can be used. Prevents unmetered usage. |

**Chosen: Option B — Block unregistered models**

A `model_registry` table is the canonical list of available models. When the metering service encounters a `(provider, model)` not in the registry, it raises an error (503 `UNREGISTERED_MODEL`). The admin must add the model to the registry and create a pricing entry before it can be used.

**Migration note:** The seed migration registers all 8 LLM models currently in `_LLM_PRICING` plus the 3 embedding models from `embedding_cost.py`. No disruption on deploy.

### 2.3 Task Routing Storage

**How should task-to-model routing be managed?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Hardcoded Python dicts per adapter | — | Current approach. Three separate dicts (Claude, OpenAI, Gemini) with 11 entries each. Requires code deploy to change routing. |
| B. Database table with admin UI | ✅ | Admin can reroute task types to different models without code changes. Enables quick response to model quality changes or price increases. |

**Chosen: Option B — Database table**

A `task_routing_config` table maps `(provider, task_type)` → model. The adapter's `get_model_for_task()` reads from this table (via the metered provider wrapper) instead of hardcoded dicts.

### 2.4 System Configuration Storage

**How should global settings be stored?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Environment variables | — | Current approach for `METERING_MARGIN_MULTIPLIER`. Requires restart to change. No audit trail. |
| B. Key-value table in database | ✅ | Admin-configurable without restarts. Each key has a value (TEXT), description, and timestamps. Application layer provides typed accessors with defaults. |
| C. Typed columns table | — | Requires a migration for every new setting. Over-constrained for a general-purpose config store. |

**Chosen: Option B — Key-value table**

A `system_config` table with `key` (PK), `value` (TEXT), `description`, and timestamps. The application layer provides typed accessor methods with defaults (e.g., `get_int("signup_grant_credits", default=0)`).

### 2.5 Admin Authentication

**How should admin access be controlled?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Full RBAC with roles table | — | Over-engineering for MVP. Only need admin vs non-admin. |
| B. `is_admin` flag on users + env var bootstrap | ✅ | Simple boolean flag. `ADMIN_EMAILS` env var bootstraps initial admin(s). Existing admins promote others via UI. |

**Chosen: Option B — is_admin flag + env var bootstrap**

- `ADMIN_EMAILS` env var (comma-separated) is checked on every login. Matching users get `is_admin = true` automatically. This is the **bootstrap mechanism** — how the first admin gets created (solves the chicken-and-egg problem).
- Existing admins can promote/demote other users via the admin UI. This is the **ongoing management** mechanism.
- Env-var-listed admins cannot be demoted via UI (re-promoted on next login). This prevents lockout.
- The `adm` claim (admin indicator) is included in the JWT so frontend middleware can gate admin routes without an API call.

### 2.6 Routing Lookup Architecture

**How should DB-backed routing be integrated with the existing adapter pattern?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Modify adapters to query DB directly | — | Adapters are singletons without DB sessions. Would require injecting DB access into the adapter layer. |
| B. MeteredLLMProvider resolves routing before delegating | ✅ | The metered wrapper already has DB access (via MeteringService). It looks up routing, resolves the model, and passes `model_override` to the inner adapter. When metering is disabled (dev mode), the adapter falls back to its hardcoded defaults. |

**Chosen: Option B — Routing in MeteredLLMProvider**

The `MeteredLLMProvider.complete()` method:
1. Looks up `task_routing_config` for `(provider, task_type)`
2. Resolves the model name
3. Passes `model_override=resolved_model` to the inner adapter's `complete()` method
4. The adapter uses `model_override` if provided, otherwise falls back to its own routing

This requires a small change to the adapter `complete()` signature: accept an optional `model_override` kwarg.

### 2.7 Caching Strategy

**Should pricing and routing be cached?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. No caching — query DB on every LLM call | ✅ | Simple. The metering pipeline already does 3 DB operations per LLM call (INSERT usage, INSERT transaction, UPDATE balance). One additional SELECT for pricing and one for routing add negligible overhead on indexed single-row lookups. Avoids cache invalidation complexity. |
| B. In-memory cache with TTL | — | Premature optimization. Can be added later if profiling shows DB lookups are a bottleneck. |

**Chosen: Option A — No caching for MVP**

Direct DB queries for pricing and routing on each LLM call. A cache layer can be added later without changing any interfaces.

**Admin refresh endpoint:** Still provided (`POST /api/v1/admin/cache/refresh`) as a no-op placeholder. When caching is added later, this endpoint triggers cache invalidation. Including it now establishes the API contract.

---

## 3. Dependencies

### 3.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-005 Database Schema | Schema | `users` table to extend with `is_admin` |
| REQ-006 API Contract | Integration | Response envelope, error codes, endpoint conventions |
| REQ-009 Provider Abstraction | Integration | `TaskType` enum, adapter pattern, `get_model_for_task()` |
| REQ-013 Authentication | Integration | JWT claims, `get_current_user_id()`, login flow |
| REQ-020 Token Metering | Foundation | `MeteringService`, `MeteredLLMProvider`, pricing lookup interface, `_LLM_PRICING` dict to replace |

### 3.2 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-021 Credits & Billing | Foundation | `credit_packs` table, `system_config` table, admin auth gate |
| Backlog #19 (Credit Denomination) | Foundation | `system_config` table, denomination keys (`credits_per_dollar`, etc.) |

### 3.3 Prerequisite Order

```
REQ-020 (Token Metering) [✅ Implemented]
    ↓
REQ-022 (Admin Pricing — THIS DOCUMENT)
    ↓
Backlog #19 (Credit Denomination)
    ↓
REQ-021 (Stripe Credits & Billing)
```

---

## 4. Database Schema

### 4.1 Users Table Extension

Add one column to the existing `users` table:

```sql
ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE;
```

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `is_admin` | `BOOLEAN` | NOT NULL | `FALSE` | Admin flag. Included in JWT claims for frontend route gating. |

### 4.2 Model Registry

Canonical list of available LLM and embedding models. Calls to models not in this table are blocked.

```sql
CREATE TABLE model_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        VARCHAR(20) NOT NULL,
    model           VARCHAR(100) NOT NULL,
    display_name    VARCHAR(100) NOT NULL,
    model_type      VARCHAR(20) NOT NULL DEFAULT 'llm',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, model)
);
```

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | Primary key |
| `provider` | `VARCHAR(20)` | Provider identifier: `claude`, `openai`, `gemini` |
| `model` | `VARCHAR(100)` | Exact model identifier (e.g., `claude-3-5-haiku-20241022`) |
| `display_name` | `VARCHAR(100)` | Human-friendly name for admin UI (e.g., `Claude 3.5 Haiku`) |
| `model_type` | `VARCHAR(20)` | `'llm'` for completion models, `'embedding'` for embedding models |
| `is_active` | `BOOLEAN` | Soft-disable. Inactive models are blocked like unregistered ones. |
| `created_at` | `TIMESTAMPTZ` | Row creation time |
| `updated_at` | `TIMESTAMPTZ` | Last modification time |

**Unique constraint:** `(provider, model)` — one registry entry per model per provider.

### 4.3 Pricing Config

Per-model pricing with individual margins and effective dates.

```sql
CREATE TABLE pricing_config (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider            VARCHAR(20) NOT NULL,
    model               VARCHAR(100) NOT NULL,
    input_cost_per_1k   NUMERIC(10,6) NOT NULL,
    output_cost_per_1k  NUMERIC(10,6) NOT NULL,
    margin_multiplier   NUMERIC(4,2) NOT NULL,
    effective_date      DATE NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, model, effective_date)
);
```

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | Primary key |
| `provider` | `VARCHAR(20)` | Provider identifier |
| `model` | `VARCHAR(100)` | Model identifier (matches `model_registry.model`) |
| `input_cost_per_1k` | `NUMERIC(10,6)` | Raw provider cost per 1,000 input tokens (USD) |
| `output_cost_per_1k` | `NUMERIC(10,6)` | Raw provider cost per 1,000 output tokens (USD) |
| `margin_multiplier` | `NUMERIC(4,2)` | Per-model margin. Cheap models: 3.00–4.00. Expensive models: 1.10–1.50. |
| `effective_date` | `DATE` | Date this pricing becomes active. Allows scheduling future changes. |
| `created_at` | `TIMESTAMPTZ` | Row creation time |
| `updated_at` | `TIMESTAMPTZ` | Last modification time |

**Unique constraint:** `(provider, model, effective_date)` — one pricing entry per model per date.

**Effective date query:** Get the pricing in effect for a model:

```sql
SELECT * FROM pricing_config
WHERE provider = :provider
  AND model = :model
  AND effective_date <= CURRENT_DATE
ORDER BY effective_date DESC
LIMIT 1;
```

**Why no FK to model_registry?** Pricing uses `(provider, model)` strings directly instead of a FK to `model_registry.id`. This allows pricing entries to be created before the model is registered (or kept after deactivation for historical reference). The application layer validates that the model exists in the registry when creating new pricing entries.

### 4.4 Task Routing Config

Maps task types to models per provider. Replaces the hardcoded `DEFAULT_*_ROUTING` dicts.

```sql
CREATE TABLE task_routing_config (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        VARCHAR(20) NOT NULL,
    task_type       VARCHAR(50) NOT NULL,
    model           VARCHAR(100) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, task_type)
);
```

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | Primary key |
| `provider` | `VARCHAR(20)` | Provider identifier |
| `task_type` | `VARCHAR(50)` | `TaskType` enum value (e.g., `extraction`, `cover_letter`) or `_default` for fallback |
| `model` | `VARCHAR(100)` | Target model identifier |
| `created_at` | `TIMESTAMPTZ` | Row creation time |
| `updated_at` | `TIMESTAMPTZ` | Last modification time |

**Unique constraint:** `(provider, task_type)` — one routing per task per provider.

**Fallback lookup order:**
1. Exact match: `(provider, task_type)` → model
2. Fallback: `(provider, '_default')` → model
3. Neither: error (should not happen with seed data)

### 4.5 Credit Packs

Admin-configurable credit pack definitions. Consumed by the Stripe integration (REQ-021) for checkout sessions.

```sql
CREATE TABLE credit_packs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(50) NOT NULL,
    price_cents     INTEGER NOT NULL,
    credit_amount   BIGINT NOT NULL,
    stripe_price_id VARCHAR(255),
    display_order   INTEGER NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    description     VARCHAR(255),
    highlight_label VARCHAR(50),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | Primary key |
| `name` | `VARCHAR(50)` | Pack display name (e.g., `Starter`, `Standard`, `Pro`) |
| `price_cents` | `INTEGER` | USD price in cents (e.g., 500 = $5.00). Follows Stripe convention — integers avoid floating-point rounding. |
| `credit_amount` | `BIGINT` | Abstract credits granted. BIGINT for large denominations (e.g., 10,000 credits/dollar × $40 = 400,000). |
| `stripe_price_id` | `VARCHAR(255)` | Stripe Price ID. **Nullable** until REQ-021 adds Stripe integration. REQ-021 migration adds `NOT NULL` + `UNIQUE` constraints. |
| `display_order` | `INTEGER` | Sort order in frontend purchase UI |
| `is_active` | `BOOLEAN` | Soft-disable without deleting |
| `description` | `VARCHAR(255)` | Short description for UI |
| `highlight_label` | `VARCHAR(50)` | Optional badge: `Most Popular`, `Best Value` |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | Timestamps |

### 4.6 System Config

Key-value store for global settings.

```sql
CREATE TABLE system_config (
    key             VARCHAR(100) PRIMARY KEY,
    value           TEXT NOT NULL,
    description     VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

| Column | Type | Notes |
|--------|------|-------|
| `key` | `VARCHAR(100)` | Setting key (PK). Convention: `snake_case`. |
| `value` | `TEXT` | Setting value as string. Application layer parses to typed values. |
| `description` | `VARCHAR(255)` | Human-readable description for admin UI |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | Timestamps |

**Initial keys (seeded by this REQ):**

| Key | Value | Type | Description |
|-----|-------|------|-------------|
| `signup_grant_credits` | `0` | int | Credits granted to new users on signup. 0 = no grant. Set by admin once credit denomination (backlog #19) is configured. |

**Future keys (added by backlog #19):**

| Key | Value | Type | Description |
|-----|-------|------|-------------|
| `credits_per_dollar` | `10000` | int | Abstract credits per USD dollar |
| `credit_display_name` | `credits` | string | Unit label in UI |
| `display_precision` | `0` | int | Decimal places in credit display |
| `rounding_mode` | `up` | string | Rounding: `up`, `nearest`, `down` |

### 4.7 Indexes

```sql
-- Pricing lookup: effective pricing for a model
CREATE INDEX ix_pricing_config_lookup
    ON pricing_config (provider, model, effective_date DESC);

-- Routing lookup: model for a task
CREATE INDEX ix_task_routing_config_lookup
    ON task_routing_config (provider, task_type);

-- Credit packs: active packs sorted by display order
CREATE INDEX ix_credit_packs_active
    ON credit_packs (is_active, display_order) WHERE is_active = TRUE;
```

### 4.8 Migration Notes

**Migration number:** `021_admin_pricing.py`

**Upgrade:**
1. Add `is_admin` column to `users` table (`BOOLEAN`, `NOT NULL`, `DEFAULT FALSE`)
2. Create `model_registry` table
3. Create `pricing_config` table
4. Create `task_routing_config` table
5. Create `credit_packs` table
6. Create `system_config` table
7. Create indexes (§4.7)
8. Seed model registry with current models (§12.1)
9. Seed pricing config with current pricing (§12.2)
10. Seed task routing with current routing (§12.3)
11. Seed system config with initial values (§12.4)
12. Seed credit packs with starter packs (§12.5)

**Downgrade:**
1. Drop all 5 new tables and indexes
2. Remove `is_admin` column from `users`

---

## 5. Admin Authentication & Authorization

### 5.1 Bootstrap: ADMIN_EMAILS Environment Variable

```bash
# .env
ADMIN_EMAILS=brianhusk@gmail.com
```

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `ADMIN_EMAILS` | comma-separated string | `""` (empty) | Email addresses that are auto-promoted to admin on login |

**Behavior on login:**
1. After successful authentication (JWT issuance), check if the user's email is in the `ADMIN_EMAILS` list (case-insensitive comparison)
2. If yes, set `users.is_admin = true` (idempotent — no-op if already admin)
3. If no, do NOT change `is_admin` (user may have been promoted via admin UI)

**Lockout prevention:** Env-var-listed admins are re-promoted on every login, even if their `is_admin` was set to `false` via the admin UI. This ensures at least one admin always exists.

**Where to hook:** The admin email check runs inside the existing login flow (token issuance endpoint in `backend/app/api/v1/auth.py`), after the user is authenticated but before the JWT is returned. This is a 3-line addition: parse `settings.admin_emails`, check membership, update `is_admin` if needed.

### 5.2 JWT Claims Extension

Add `is_admin` to the JWT payload:

```python
# Current JWT claims (REQ-013)
{
    "sub": "user-uuid",
    "aud": "zentropy-scout",
    "iss": "zentropy-scout",
    "iat": 1709000000,
    "exp": 1709086400
}

# Extended claims
{
    "sub": "user-uuid",
    "aud": "zentropy-scout",
    "iss": "zentropy-scout",
    "iat": 1709000000,
    "exp": 1709086400,
    "adm": true              # NEW: is_admin claim
}
```

**Claim name:** `adm` (short, following JWT conventions for compact payloads).

**When `is_admin` changes:** The admin who toggles another user's `is_admin` flag also updates `token_invalidated_before` for that user. This forces JWT refresh, ensuring the `adm` claim is updated. The toggled user's next request receives a 401, they re-authenticate, and get a new JWT with the correct `adm` claim.

### 5.3 Backend Admin Gate

A FastAPI dependency that requires admin access:

```python
# backend/app/api/deps.py
async def require_admin(
    user_id: CurrentUserId,
    db: DbSession,
) -> UUID:
    """FastAPI dependency. Raises 403 if user is not admin."""
    user = await user_repo.get_by_id(db, user_id)
    if not user or not user.is_admin:
        raise AdminRequiredError()
    return user_id

AdminUser = Annotated[UUID, Depends(require_admin)]
```

All admin endpoints use `AdminUser` instead of `CurrentUserId`.

### 5.4 Frontend Admin Gate

Next.js middleware checks the `adm` claim in the JWT cookie:

```typescript
// frontend/src/middleware.ts (extension)
const adminPaths = ["/admin"];

if (adminPaths.some((p) => pathname.startsWith(p))) {
    const token = request.cookies.get("zentropy.session-token");
    const payload = decodeJwtPayload(token);
    if (!payload?.adm) {
        return NextResponse.redirect(new URL("/", request.url));
    }
}
```

**Note:** The frontend gate is a UX convenience only. The backend `require_admin` dependency is the authoritative security check. If someone bypasses the frontend gate, the backend rejects the request with 403.

### 5.5 Admin User Management

Existing admins can promote/demote other users via the admin UI:

- `GET /api/v1/admin/users` — List all users with `is_admin` status
- `PATCH /api/v1/admin/users/:id` — Toggle `is_admin` (except for `ADMIN_EMAILS` users)

**ADMIN_EMAILS protection:** The PATCH endpoint checks if the target user's email is in `ADMIN_EMAILS`. If so, the `is_admin` flag cannot be set to `false`. Returns 409 `ADMIN_EMAILS_PROTECTED`.

---

## 6. Admin Config Service

### 6.1 New File

`backend/app/services/admin_config_service.py`

### 6.2 Interface

```python
@dataclass(frozen=True)
class PricingResult:
    """Effective pricing for a model."""
    input_cost_per_1k: Decimal
    output_cost_per_1k: Decimal
    margin_multiplier: Decimal
    effective_date: date


class AdminConfigService:
    """Reads admin-managed configuration from database."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_pricing(
        self, provider: str, model: str
    ) -> PricingResult | None:
        """Get effective pricing for a model.

        Returns the pricing_config row with the latest effective_date
        that is <= today for the given (provider, model).
        Returns None if no pricing exists.
        """
        ...

    async def get_model_for_task(
        self, provider: str, task_type: str
    ) -> str | None:
        """Get the routed model for a task type.

        Lookup order:
        1. Exact match: (provider, task_type)
        2. Fallback: (provider, '_default')
        Returns None if no routing exists.
        """
        ...

    async def is_model_registered(
        self, provider: str, model: str
    ) -> bool:
        """Check if model is in registry and active."""
        ...

    async def get_system_config(
        self, key: str, default: str | None = None
    ) -> str | None:
        """Get a system config value by key."""
        ...

    async def get_system_config_int(
        self, key: str, default: int = 0
    ) -> int:
        """Get a system config value as integer."""
        value = await self.get_system_config(key)
        return int(value) if value is not None else default
```

### 6.3 Dependency Injection

```python
# backend/app/api/deps.py
async def get_admin_config_service(db: DbSession) -> AdminConfigService:
    return AdminConfigService(db)

AdminConfig = Annotated[AdminConfigService, Depends(get_admin_config_service)]
```

---

## 7. Metering Service Migration

### 7.1 What Changes

The `MeteringService` currently reads pricing from the hardcoded `_LLM_PRICING` dict (lines 27–64) and `_FALLBACK_PRICING` dict (lines 68–81) in `metering_service.py`. After migration, it reads from the `pricing_config` table via `AdminConfigService`.

### 7.2 Current Code (to be replaced)

```python
# metering_service.py lines 27-81 — REMOVE after migration
_LLM_PRICING: dict[tuple[str, str], dict[str, Decimal]] = { ... }
_FALLBACK_PRICING: dict[str, dict[str, Decimal]] = { ... }
```

### 7.3 New Pricing Lookup

```python
class MeteringService:
    def __init__(
        self,
        db: AsyncSession,
        admin_config: AdminConfigService,    # NEW dependency
    ) -> None:
        self._db = db
        self._admin_config = admin_config
        # REMOVED: margin_multiplier parameter (now per-model)

    async def _get_pricing(
        self, provider: str, model: str
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Get (input_per_1k, output_per_1k, margin) from DB.

        Raises UnregisteredModelError if model not in registry.
        Raises NoPricingConfigError if no pricing exists.
        """
        # 1. Check model registry
        if not await self._admin_config.is_model_registered(provider, model):
            raise UnregisteredModelError(provider=provider, model=model)

        # 2. Get effective pricing
        pricing = await self._admin_config.get_pricing(provider, model)
        if pricing is None:
            raise NoPricingConfigError(provider=provider, model=model)

        return (
            pricing.input_cost_per_1k,
            pricing.output_cost_per_1k,
            pricing.margin_multiplier,
        )
```

### 7.4 record_and_debit Changes

The existing `record_and_debit` method changes its pricing lookup:

**Before:**
```python
pricing = _LLM_PRICING.get((provider, model))
if pricing is None:
    pricing = _FALLBACK_PRICING[provider]     # Fallback
raw_cost = ...
billed_cost = raw_cost * self._margin         # Uniform margin
```

**After:**
```python
input_per_1k, output_per_1k, margin = await self._get_pricing(provider, model)
raw_cost = (Decimal(input_tokens) / 1000 * input_per_1k) + \
           (Decimal(output_tokens) / 1000 * output_per_1k)
billed_cost = raw_cost * margin               # Per-model margin
```

The cost formula is identical; only the source of pricing data and margin changes.

### 7.5 Dependency Injection Update

```python
# backend/app/api/deps.py — update get_metered_provider
# NOTE: stays sync (def, not async) — only constructs objects, no awaits needed.
def get_metered_provider(
    user_id: CurrentUserId,
    db: DbSession,
) -> LLMProvider:
    if not settings.metering_enabled:
        return get_llm_provider()
    inner = get_llm_provider()
    admin_config = AdminConfigService(db)
    metering_service = MeteringService(db, admin_config)     # Pass admin_config
    return MeteredLLMProvider(inner, metering_service, admin_config, user_id)

# backend/app/api/deps.py — update get_metered_embedding_provider (same pattern)
def get_metered_embedding_provider(
    user_id: CurrentUserId,
    db: DbSession,
) -> EmbeddingProvider:
    if not settings.metering_enabled:
        return get_embedding_provider()
    inner = get_embedding_provider()
    admin_config = AdminConfigService(db)
    metering_service = MeteringService(db, admin_config)     # Pass admin_config
    return MeteredEmbeddingProvider(inner, metering_service, admin_config, user_id)
```

### 7.6 Embedding Pricing Migration

The `embedding_cost.py` `EMBEDDING_MODELS` dict (lines 31–44) contains embedding pricing. After migration, embedding pricing lives in `pricing_config` alongside LLM pricing (with `output_cost_per_1k = 0` for embeddings).

The `MeteredEmbeddingProvider` receives the same `AdminConfigService` and uses it for pricing lookups instead of the hardcoded dict.

**`embedding_cost.py` disposition:** Keep the `EMBEDDING_MODELS` dict as a dev-mode fallback (same pattern as the LLM routing dicts — §8.4). Add a docstring noting production pricing comes from the `pricing_config` table. Do NOT delete the file.

### 7.7 Environment Variable Deprecation

| Variable | Action | Notes |
|----------|--------|-------|
| `METERING_MARGIN_MULTIPLIER` | **Deprecate** | No longer read at runtime. Seed migration uses 1.30 as the initial margin for all models. Admin adjusts per-model margins via UI. Remove from `config.py` and `.env.example`. |
| `METERING_ENABLED` | **Keep** | Still controls whether metering is active |
| `METERING_MINIMUM_BALANCE` | **Keep** | Still controls balance gating threshold |

---

## 8. LLM Adapter Migration

### 8.1 What Changes

The three LLM adapters currently load routing from hardcoded dicts at construction time. After migration, routing is resolved by the `MeteredLLMProvider` from the `task_routing_config` table and passed to the adapter via `model_override`.

### 8.2 Adapter complete() Signature Change

Add `model_override` support to the base class and all three adapters:

```python
# Base class change (backend/app/providers/llm/base.py)
class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        task: TaskType,
        max_tokens: int | None = None,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
        tools: list[ToolDefinition] | None = None,
        json_mode: bool = False,
        model_override: str | None = None,    # NEW
    ) -> LLMResponse: ...
```

**Important:** Preserve all existing parameters. Do NOT switch to `**kwargs` — the explicit signature serves as documentation and enables IDE autocomplete. Only add `model_override` at the end.

Each adapter's `complete()` method:

```python
# Before (in each adapter):
model = self.get_model_for_task(task)

# After:
model = model_override or self.get_model_for_task(task)
```

**Backward compatibility:** The `model_override` parameter is optional with default `None`. When not provided (e.g., metering disabled, tests), the adapter uses its existing hardcoded routing. No existing call sites break.

### 8.3 MeteredLLMProvider Routing

```python
class MeteredLLMProvider(LLMProvider):
    def __init__(
        self,
        inner: LLMProvider,
        metering_service: MeteringService,
        admin_config: AdminConfigService,      # NEW
        user_id: UUID,
    ) -> None:
        self._inner = inner
        self._metering_service = metering_service
        self._admin_config = admin_config
        self._user_id = user_id

    async def complete(
        self,
        messages: list[LLMMessage],
        task: TaskType,
        max_tokens: int | None = None,
        temperature: float | None = None,
        stop_sequences: list[str] | None = None,
        tools: list[ToolDefinition] | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        # NOTE: MeteredLLMProvider does NOT accept model_override from callers.
        # It resolves routing internally and passes model_override to the inner adapter.

        # 1. Resolve model from DB routing
        resolved_model = await self._admin_config.get_model_for_task(
            provider=self._inner.provider_name,
            task_type=task.value,
        )

        # 2. Delegate to inner adapter with model override
        response = await self._inner.complete(
            messages=messages,
            task=task,
            max_tokens=max_tokens,
            temperature=temperature,
            stop_sequences=stop_sequences,
            tools=tools,
            json_mode=json_mode,
            model_override=resolved_model,      # NEW — resolved from DB
        )

        # 3. Record usage (existing logic — now uses DB pricing)
        await self._metering_service.record_and_debit(
            user_id=self._user_id,
            provider=self._inner.provider_name,
            model=response.model,
            task_type=task,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
        return response
```

### 8.4 Hardcoded Routing Dicts: Keep as Fallback

The `DEFAULT_CLAUDE_ROUTING`, `DEFAULT_OPENAI_ROUTING`, and `DEFAULT_GEMINI_ROUTING` dicts remain in the adapter files. They serve as:

1. **Dev mode fallback** — When `METERING_ENABLED=false`, adapters use hardcoded routing
2. **Seed data source** — The migration reads these values to populate `task_routing_config`

Do NOT delete the hardcoded dicts. Add a docstring noting they are fallback values:

```python
DEFAULT_CLAUDE_ROUTING: dict[str, str] = {
    # Fallback routing used when METERING_ENABLED=false (dev mode).
    # Production routing is configured in task_routing_config table.
    # See REQ-022 §8.4.
    ...
}
```

### 8.5 Embedding Provider: No Routing Change

Embedding providers don't have task-based routing — they use a single model configured via `EMBEDDING_MODEL` env var. No changes to embedding adapters or `MeteredEmbeddingProvider` routing. Only the pricing lookup changes (§7.6).

---

## 9. Unknown Model Blocking

### 9.1 When Blocking Occurs

When `MeteringService._get_pricing()` encounters a model not in `model_registry`:

1. Log error: `"Unregistered model: provider={provider}, model={model}"`
2. Raise `UnregisteredModelError`
3. The `MeteredLLMProvider` catches this and returns 503 to the caller

### 9.2 Error Responses

**Unregistered model:**
```json
{
    "error": {
        "code": "UNREGISTERED_MODEL",
        "message": "Model 'claude-4-opus' is not registered. Contact admin to add it to the model registry."
    }
}
```

**No pricing configured:**
```json
{
    "error": {
        "code": "NO_PRICING_CONFIG",
        "message": "No pricing configured for model 'claude-3-5-haiku-20241022'. Contact admin."
    }
}
```

HTTP Status: `503 Service Unavailable` for both (same as `METERING_UNAVAILABLE` — the system cannot safely meter this request).

### 9.3 Inactive Models

A model can be registered but set to `is_active = false`. Inactive models are treated the same as unregistered — calls are blocked with `UNREGISTERED_MODEL`. This allows the admin to temporarily disable a model without deleting it.

### 9.4 Fail-Closed Policy

This extends REQ-020 §10.2's fail-closed policy: if the admin config tables are unreachable (DB error), LLM calls are blocked with 503 `METERING_UNAVAILABLE`. The system never allows unmetered usage.

---

## 10. Admin API Endpoints

All endpoints require `AdminUser` dependency (§5.3). All follow REQ-006 response envelope pattern.

**Router registration:**
```python
# backend/app/api/v1/router.py
from app.api.v1 import admin
router.include_router(admin.router, prefix="/admin", tags=["admin"])
```

### 10.1 Model Registry

#### `GET /api/v1/admin/models`

List all registered models.

**Query Parameters:**

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `provider` | string | — | Optional filter |
| `model_type` | string | — | Optional filter: `llm`, `embedding` |
| `is_active` | boolean | — | Optional filter |

**Response 200:**
```json
{
    "data": [
        {
            "id": "uuid",
            "provider": "claude",
            "model": "claude-3-5-haiku-20241022",
            "display_name": "Claude 3.5 Haiku",
            "model_type": "llm",
            "is_active": true,
            "created_at": "2026-03-01T00:00:00Z",
            "updated_at": "2026-03-01T00:00:00Z"
        }
    ]
}
```

#### `POST /api/v1/admin/models`

Register a new model.

**Request Body:**
```json
{
    "provider": "claude",
    "model": "claude-4-opus-20260301",
    "display_name": "Claude 4 Opus",
    "model_type": "llm"
}
```

**Validation:**
- `provider` must be one of: `claude`, `openai`, `gemini`
- `model` max 100 chars
- `(provider, model)` must be unique (409 `DUPLICATE_MODEL` if exists)
- `display_name` required, max 100 chars
- `model_type` must be `llm` or `embedding`

**Response 201:** Created model object.

#### `PATCH /api/v1/admin/models/:id`

Update model properties.

**Request Body (partial):**
```json
{
    "display_name": "Claude 4 Opus (Latest)",
    "is_active": false
}
```

**Response 200:** Updated model object.

#### `DELETE /api/v1/admin/models/:id`

Remove a model from the registry.

**Validation:**
- Cannot delete if referenced by `task_routing_config` (409 `MODEL_IN_USE`)
- Recommend deactivating (`is_active = false`) instead of deleting

**Response 204:** No content.

### 10.2 Pricing Config

#### `GET /api/v1/admin/pricing`

List all pricing entries.

**Query Parameters:**

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `provider` | string | — | Optional filter |
| `model` | string | — | Optional filter |

**Response 200:**
```json
{
    "data": [
        {
            "id": "uuid",
            "provider": "claude",
            "model": "claude-3-5-haiku-20241022",
            "input_cost_per_1k": "0.000800",
            "output_cost_per_1k": "0.004000",
            "margin_multiplier": "1.30",
            "effective_date": "2026-03-01",
            "is_current": true,
            "created_at": "2026-03-01T00:00:00Z"
        }
    ]
}
```

**`is_current`:** Computed field (not stored). `true` if this is the effective pricing for the model (latest `effective_date <= today`).

#### `POST /api/v1/admin/pricing`

Add a pricing entry.

**Request Body:**
```json
{
    "provider": "claude",
    "model": "claude-3-5-haiku-20241022",
    "input_cost_per_1k": "0.000800",
    "output_cost_per_1k": "0.004000",
    "margin_multiplier": "3.00",
    "effective_date": "2026-04-01"
}
```

**Validation:**
- Model must exist in `model_registry` (404 `MODEL_NOT_FOUND`)
- `margin_multiplier` must be > 0
- `input_cost_per_1k` and `output_cost_per_1k` must be >= 0
- `(provider, model, effective_date)` must be unique (409 `DUPLICATE_PRICING`)

**Response 201:** Created pricing object.

#### `PATCH /api/v1/admin/pricing/:id`

Update a pricing entry.

**Response 200:** Updated pricing object.

#### `DELETE /api/v1/admin/pricing/:id`

Remove a pricing entry.

**Validation:**
- Cannot delete the only current pricing for a registered active model (409 `LAST_PRICING`)

**Response 204:** No content.

### 10.3 Task Routing

#### `GET /api/v1/admin/routing`

List all routing entries.

**Query Parameters:**

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `provider` | string | — | Optional filter |

**Response 200:**
```json
{
    "data": [
        {
            "id": "uuid",
            "provider": "claude",
            "task_type": "extraction",
            "model": "claude-3-5-haiku-20241022",
            "model_display_name": "Claude 3.5 Haiku",
            "created_at": "2026-03-01T00:00:00Z"
        }
    ]
}
```

**`model_display_name`:** Computed by joining on `model_registry`. Convenience for admin UI display.

#### `POST /api/v1/admin/routing`

Add a routing entry.

**Request Body:**
```json
{
    "provider": "claude",
    "task_type": "extraction",
    "model": "claude-3-5-haiku-20241022"
}
```

**Validation:**
- Model must exist in `model_registry` and be active
- `task_type` must be a valid `TaskType` enum value or `_default`
- `(provider, task_type)` must be unique (409 `DUPLICATE_ROUTING`)

**Response 201:** Created routing object.

#### `PATCH /api/v1/admin/routing/:id`

Update routing (change the target model).

**Response 200:** Updated routing object.

#### `DELETE /api/v1/admin/routing/:id`

Remove a routing entry.

**Response 204:** No content.

### 10.4 Credit Packs

#### `GET /api/v1/admin/credit-packs`

List all credit packs.

**Response 200:**
```json
{
    "data": [
        {
            "id": "uuid",
            "name": "Starter",
            "price_cents": 500,
            "price_display": "$5.00",
            "credit_amount": 50000,
            "stripe_price_id": null,
            "display_order": 1,
            "is_active": true,
            "description": "Get started with Zentropy Scout",
            "highlight_label": null,
            "created_at": "2026-03-01T00:00:00Z"
        }
    ]
}
```

**`price_display`:** Computed. Formats `price_cents` as `$X.XX` for convenience.

#### `POST /api/v1/admin/credit-packs`

Add a credit pack.

**Request Body:**
```json
{
    "name": "Starter",
    "price_cents": 500,
    "credit_amount": 50000,
    "display_order": 1,
    "description": "Get started with Zentropy Scout"
}
```

**Validation:**
- `price_cents` must be > 0
- `credit_amount` must be > 0
- `name` required, max 50 chars

**Response 201:** Created pack object.

#### `PATCH /api/v1/admin/credit-packs/:id`

Update a credit pack.

**Response 200:** Updated pack object.

#### `DELETE /api/v1/admin/credit-packs/:id`

Remove a credit pack.

**Response 204:** No content.

### 10.5 System Config

#### `GET /api/v1/admin/config`

List all config entries.

**Response 200:**
```json
{
    "data": [
        {
            "key": "signup_grant_credits",
            "value": "0",
            "description": "Credits granted to new users on signup",
            "updated_at": "2026-03-01T00:00:00Z"
        }
    ]
}
```

#### `PUT /api/v1/admin/config/:key`

Set a config value (upsert — creates if key doesn't exist, updates if it does).

**Request Body:**
```json
{
    "value": "10000",
    "description": "Credits granted to new users on signup"
}
```

**Response 200:** Updated config entry.

#### `DELETE /api/v1/admin/config/:key`

Remove a config entry.

**Response 204:** No content.

### 10.6 Admin Users

#### `GET /api/v1/admin/users`

List all users (admin view).

**Query Parameters:**

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `page` | integer | 1 | Pagination |
| `per_page` | integer | 50 | Max 100 |
| `is_admin` | boolean | — | Optional filter |

**Response 200:**
```json
{
    "data": [
        {
            "id": "uuid",
            "email": "user@example.com",
            "name": "User Name",
            "is_admin": true,
            "is_env_protected": true,
            "balance_usd": "4.230000",
            "created_at": "2026-03-01T00:00:00Z"
        }
    ],
    "meta": {
        "page": 1,
        "per_page": 50,
        "total": 1,
        "total_pages": 1
    }
}
```

**`is_env_protected`:** Computed (not stored). `true` if the user's email is in `ADMIN_EMAILS`. These users cannot be demoted via API.

#### `PATCH /api/v1/admin/users/:id`

Toggle admin status.

**Request Body:**
```json
{
    "is_admin": true
}
```

**Validation:**
- Cannot demote env-protected admins (409 `ADMIN_EMAILS_PROTECTED`)
- Cannot demote yourself (409 `CANNOT_DEMOTE_SELF`)

**Side effect:** When `is_admin` changes, sets `token_invalidated_before = now()` for the target user to force JWT refresh.

**Response 200:** Updated user object.

### 10.7 Cache Refresh (Placeholder)

#### `POST /api/v1/admin/cache/refresh`

No-op for MVP (no caching — §2.7). Establishes the API contract for future caching.

**Response 200:**
```json
{
    "data": {
        "message": "Cache refresh triggered",
        "caching_enabled": false
    }
}
```

---

## 11. Admin Frontend

### 11.1 Page Structure

A single admin config page with tabbed navigation.

**Route:** `/admin/config`

**Layout:** Reuses the existing `(main)` layout with nav bar. No separate admin layout needed.

**Gate:** Next.js middleware redirects non-admin users to `/` (§5.4).

### 11.2 Tabs

| Tab | Content | Data Source |
|-----|---------|-------------|
| **Models** | Table of registered models. Add/edit/deactivate controls. | `GET /api/v1/admin/models` |
| **Pricing** | Table of pricing entries with effective dates. "Current" badge on active pricing. Add/edit/delete. Live cost preview on add/edit. | `GET /api/v1/admin/pricing` |
| **Routing** | Per-provider routing table. Task type → model dropdown. | `GET /api/v1/admin/routing` |
| **Packs** | Credit pack definitions. Price and credit amount fields. Stripe Price ID field (nullable). | `GET /api/v1/admin/credit-packs` |
| **System** | Key-value config entries. Edit values inline. | `GET /api/v1/admin/config` |
| **Users** | User list with admin toggle. Env-protected badge. | `GET /api/v1/admin/users` |

### 11.3 New Files

| File | Purpose |
|------|---------|
| `frontend/src/app/(main)/admin/config/page.tsx` | Admin config page with tab navigation |
| `frontend/src/components/admin/models-tab.tsx` | Model registry management |
| `frontend/src/components/admin/pricing-tab.tsx` | Pricing config management |
| `frontend/src/components/admin/routing-tab.tsx` | Task routing management |
| `frontend/src/components/admin/packs-tab.tsx` | Credit pack management |
| `frontend/src/components/admin/system-tab.tsx` | System config management |
| `frontend/src/components/admin/users-tab.tsx` | User admin management |
| `frontend/src/lib/api/admin.ts` | Admin API client functions |

### 11.4 Nav Bar Extension

Add an "Admin" link in the nav bar, visible only when the `adm` claim is present in the JWT cookie. This link navigates to `/admin/config`.

### 11.5 UI Components

Use existing component patterns from the codebase (Tailwind CSS, consistent with the rest of the app). Each tab contains:

- A data table with sortable columns
- Add/Edit forms (modal or inline)
- Delete confirmation dialog
- Toast notifications for success/error

**Pricing tab special feature — live cost preview:** When adding/editing a pricing entry, show a calculated cost preview:

```
Example: 1,000 input + 500 output tokens
  Raw cost:    $0.001050
  Billed cost: $0.003150 (×3.00 margin)
```

This helps the admin understand the impact of their pricing decisions before saving.

### 11.6 Expansion Path

This single-page tab design is intentionally built for easy expansion:

- Each tab is an isolated React component
- To promote a tab to a full page later: move the component to a new route under `/admin/`, add a sidebar nav
- The API client (`admin.ts`) and all data fetching hooks work unchanged
- Estimated effort to expand: 1–2 hours per tab (mostly layout/routing changes, zero logic changes)

---

## 12. Seed Data

The seed migration populates all admin tables with the current hardcoded values. This ensures **zero disruption on deploy** — the system works identically before and after migration.

### 12.1 Model Registry Seed

9 models (6 LLM + 2 active embedding + 1 legacy embedding):

| Provider | Model | Display Name | Type | Active |
|----------|-------|-------------|------|--------|
| claude | claude-3-5-haiku-20241022 | Claude 3.5 Haiku | llm | true |
| claude | claude-3-5-sonnet-20241022 | Claude 3.5 Sonnet | llm | true |
| openai | gpt-4o-mini | GPT-4o Mini | llm | true |
| openai | gpt-4o | GPT-4o | llm | true |
| gemini | gemini-2.0-flash | Gemini 2.0 Flash | llm | true |
| gemini | gemini-2.5-flash | Gemini 2.5 Flash | llm | true |
| openai | text-embedding-3-small | Embedding 3 Small | embedding | true |
| openai | text-embedding-3-large | Embedding 3 Large | embedding | true |
| openai | text-embedding-ada-002 | Embedding Ada 002 (Legacy) | embedding | false |

### 12.2 Pricing Config Seed

All pricing from the current `_LLM_PRICING` dict and `embedding_cost.py`. Effective date = migration date. Initial margin = 1.30 for all models (preserves current uniform margin for zero-disruption deploy — admin adjusts per-model margins post-deploy).

| Provider | Model | Input/1K | Output/1K | Margin | Effective |
|----------|-------|----------|-----------|--------|-----------|
| claude | claude-3-5-haiku-20241022 | 0.000800 | 0.004000 | 1.30 | migration date |
| claude | claude-3-5-sonnet-20241022 | 0.003000 | 0.015000 | 1.30 | migration date |
| openai | gpt-4o-mini | 0.000150 | 0.000600 | 1.30 | migration date |
| openai | gpt-4o | 0.002500 | 0.010000 | 1.30 | migration date |
| gemini | gemini-2.0-flash | 0.000100 | 0.000400 | 1.30 | migration date |
| gemini | gemini-2.5-flash | 0.000150 | 0.003500 | 1.30 | migration date |
| openai | text-embedding-3-small | 0.000020 | 0.000000 | 1.30 | migration date |
| openai | text-embedding-3-large | 0.000130 | 0.000000 | 1.30 | migration date |

**Post-deploy recommended margins** (admin adjusts via UI):

| Model Category | Recommended Margin | Rationale |
|---------------|-------------------|-----------|
| Cheap (Haiku, Flash, 4o-mini) | 3.00–4.00 | Low base cost, higher multiplier needed for meaningful revenue |
| Mid-tier (Gemini 2.5 Flash) | 2.00 | Moderate cost |
| Expensive (Sonnet, GPT-4o) | 1.10–1.50 | High base cost, thin margin still produces significant revenue |
| Embeddings | 1.30 | Negligible cost, not worth granular tuning |

### 12.3 Task Routing Seed

All entries from the three `DEFAULT_*_ROUTING` dicts, plus `_default` entries:

**Claude (12 entries):**

| Task Type | Model |
|-----------|-------|
| skill_extraction | claude-3-5-haiku-20241022 |
| extraction | claude-3-5-haiku-20241022 |
| ghost_detection | claude-3-5-haiku-20241022 |
| resume_parsing | claude-3-5-haiku-20241022 |
| chat_response | claude-3-5-sonnet-20241022 |
| onboarding | claude-3-5-sonnet-20241022 |
| score_rationale | claude-3-5-sonnet-20241022 |
| cover_letter | claude-3-5-sonnet-20241022 |
| resume_tailoring | claude-3-5-sonnet-20241022 |
| story_selection | claude-3-5-sonnet-20241022 |
| _default | claude-3-5-sonnet-20241022 |

**OpenAI (12 entries):**

| Task Type | Model |
|-----------|-------|
| skill_extraction | gpt-4o-mini |
| extraction | gpt-4o-mini |
| ghost_detection | gpt-4o-mini |
| resume_parsing | gpt-4o-mini |
| chat_response | gpt-4o |
| onboarding | gpt-4o |
| score_rationale | gpt-4o |
| cover_letter | gpt-4o |
| resume_tailoring | gpt-4o |
| story_selection | gpt-4o |
| _default | gpt-4o |

**Gemini (12 entries):**

| Task Type | Model |
|-----------|-------|
| skill_extraction | gemini-2.0-flash |
| extraction | gemini-2.0-flash |
| ghost_detection | gemini-2.0-flash |
| chat_response | gemini-2.0-flash |
| onboarding | gemini-2.0-flash |
| score_rationale | gemini-2.0-flash |
| cover_letter | gemini-2.0-flash |
| resume_tailoring | gemini-2.0-flash |
| story_selection | gemini-2.0-flash |
| resume_parsing | gemini-2.5-flash |
| _default | gemini-2.0-flash |

**Total:** 33 routing entries (10 task types + 1 _default × 3 providers).

### 12.4 System Config Seed

| Key | Value | Description |
|-----|-------|-------------|
| signup_grant_credits | 0 | Credits granted to new users on signup. Set to > 0 once denomination is configured (backlog #19). |

### 12.5 Credit Packs Seed

Initial packs (illustrative — admin should adjust after denomination is configured in #19):

| Name | Price | Credits | Order | Active | Description | Highlight |
|------|-------|---------|-------|--------|-------------|-----------|
| Starter | 500 ($5.00) | 50000 | 1 | true | Get started with Zentropy Scout | — |
| Standard | 1500 ($15.00) | 175000 | 2 | true | For regular users | Most Popular |
| Pro | 4000 ($40.00) | 500000 | 3 | true | For power users | Best Value |

These credit amounts use a base rate of `credits_per_dollar = 10,000` (to be confirmed in #19) with volume bonuses on larger packs: Starter = base rate, Standard = ~17% bonus (11,667 credits/dollar), Pro = ~25% bonus (12,500 credits/dollar). Admin can adjust via UI after #19 is implemented.

---

## 13. Environment Variables

### 13.1 New Variables

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `ADMIN_EMAILS` | comma-separated string | `""` | Email addresses auto-promoted to admin on login. Case-insensitive. |

### 13.2 Deprecated Variables

| Variable | Action | Notes |
|----------|--------|-------|
| `METERING_MARGIN_MULTIPLIER` | **Remove** | Replaced by per-model `margin_multiplier` in `pricing_config` table. Seed uses 1.30 as initial value for all models. |

### 13.3 Unchanged Variables

| Variable | Notes |
|----------|-------|
| `METERING_ENABLED` | Still controls metering on/off. When off, hardcoded routing is used as fallback. |
| `METERING_MINIMUM_BALANCE` | Still controls balance gating threshold. |

### 13.4 .env.example Update

```bash
# Admin (REQ-022)
ADMIN_EMAILS=brianhusk@gmail.com       # Comma-separated admin emails (bootstrap)

# Metering (REQ-020, updated REQ-022)
METERING_ENABLED=true
METERING_MINIMUM_BALANCE=0.00
# METERING_MARGIN_MULTIPLIER — REMOVED: now per-model in pricing_config table (REQ-022)
```

---

## 14. Error Codes

New error codes added to the API:

| Code | HTTP Status | When |
|------|-------------|------|
| `UNREGISTERED_MODEL` | 503 | LLM call to a model not in `model_registry` (or inactive) |
| `NO_PRICING_CONFIG` | 503 | Model is registered but has no effective pricing entry |
| `ADMIN_REQUIRED` | 403 | Non-admin user accesses admin endpoint |
| `ADMIN_EMAILS_PROTECTED` | 409 | Attempt to demote an env-var-protected admin |
| `CANNOT_DEMOTE_SELF` | 409 | Admin attempts to remove their own admin status |
| `DUPLICATE_MODEL` | 409 | Model already exists in registry for this provider |
| `DUPLICATE_PRICING` | 409 | Pricing for same (provider, model, effective_date) already exists |
| `DUPLICATE_ROUTING` | 409 | Routing for same (provider, task_type) already exists |
| `MODEL_IN_USE` | 409 | Cannot delete model referenced by task_routing_config |
| `LAST_PRICING` | 409 | Cannot delete the only current pricing for a registered active model |
| `MODEL_NOT_FOUND` | 404 | Model not in registry (when creating pricing or routing) |

---

## 15. Testing Strategy

### 15.1 Unit Tests

| Component | Test Focus | File |
|-----------|-----------|------|
| `AdminConfigService` | Pricing lookup (effective dates, fallback), routing lookup (exact + _default), model registration check, system config typed accessors | `tests/unit/test_admin_config_service.py` |
| `AdminManagementService` | CRUD operations for all 5 tables + user admin toggle, validation rules (duplicate checks, FK constraints, env-protected admin), cascade behavior | `tests/unit/test_admin_management_service.py` |
| `MeteringService` (updated) | DB-backed pricing lookup, unregistered model blocking, no-pricing blocking, per-model margin calculation | `tests/unit/test_metering_service.py` (update existing) |
| Admin API endpoints | HTTP-level tests: status codes, auth gate (403 for non-admin), request validation, response shapes, env-protected admin check | `tests/unit/test_admin_api.py` |
| Adapter `model_override` | Override used when provided, fallback when None | `tests/unit/test_claude_adapter.py` etc. (update existing) |
| `create_jwt` (updated) | `adm` claim included when `is_admin=True`, omitted when `False` | `tests/unit/test_auth.py` (update existing) |

### 15.2 Key Test Scenarios

**Pricing effective dates:**
```
test_effective_date_picks_latest_before_today
  Given pricing entries for Jan 1 and Mar 1, today = Feb 15 → use Jan 1 pricing.

test_future_effective_date_not_used
  Given pricing with future effective_date only → returns None (no current pricing).

test_effective_date_exact_match_today
  Given pricing effective today → it is used.

test_multiple_effective_dates_picks_most_recent
  Given 3 pricing entries (Jan, Feb, Mar), today = Mar 15 → use Mar pricing.
```

**Unknown model blocking:**
```
test_unregistered_model_raises_error
  LLM call to model not in registry → UnregisteredModelError.

test_inactive_model_raises_error
  LLM call to deactivated model → UnregisteredModelError.

test_registered_model_without_pricing_raises_error
  Model in registry but no pricing → NoPricingConfigError.

test_registered_model_with_pricing_succeeds
  Model in registry with current pricing → succeeds, returns correct billed cost.
```

**Per-model margins:**
```
test_cheap_model_high_margin
  Haiku with 3.0× margin → billed_cost = raw_cost * 3.0.

test_expensive_model_low_margin
  Sonnet with 1.1× margin → billed_cost = raw_cost * 1.1.
```

**Admin auth:**
```
test_admin_endpoint_rejects_non_admin
  Non-admin user → 403 ADMIN_REQUIRED.

test_admin_endpoint_allows_admin
  Admin user → 200 success.

test_admin_emails_bootstrap_on_login
  User with email in ADMIN_EMAILS logs in → is_admin=true.

test_admin_emails_case_insensitive
  ADMIN_EMAILS=User@Example.com, login as user@example.com → is_admin=true.

test_env_protected_admin_cannot_be_demoted
  PATCH is_admin=false on env-listed admin → 409 ADMIN_EMAILS_PROTECTED.

test_cannot_demote_self
  Admin PATCHes own is_admin=false → 409 CANNOT_DEMOTE_SELF.

test_admin_toggle_invalidates_target_jwt
  PATCH is_admin on user → token_invalidated_before is set.
```

**Task routing:**
```
test_routing_exact_match
  Specific (provider, task_type) routing → correct model returned.

test_routing_fallback_to_default
  No specific routing for task_type → _default routing used.

test_routing_returns_none_when_no_entries
  No routing at all for provider → None returned.

test_model_override_in_adapter
  Adapter complete() with model_override → uses override model.

test_adapter_fallback_without_override
  Adapter complete() with model_override=None → uses hardcoded routing.
```

### 15.3 Integration Tests

- Full flow: admin creates model → creates pricing → creates routing → LLM call uses DB-backed config and bills at per-model margin
- Admin promotes user → user accesses admin endpoints successfully
- Effective date transition: create future pricing → mock date → verify new pricing takes effect
- Seed data: fresh migration → all tables populated → LLM calls work with seeded config

### 15.4 Frontend Tests

- Admin page renders all tabs
- Non-admin redirect works (middleware gate)
- CRUD operations in each tab (add, edit, delete)
- Admin badge in nav bar (visible for admin, hidden for non-admin)
- Env-protected badge on protected admins in Users tab
- Pricing live cost preview updates on input change

---

## 16. New Files Summary

### Backend

| File | Purpose |
|------|---------|
| `backend/app/models/admin_config.py` | SQLAlchemy models: `ModelRegistry`, `PricingConfig`, `TaskRoutingConfig`, `CreditPack`, `SystemConfig` |
| `backend/app/schemas/admin.py` | Pydantic schemas for admin API request/response |
| `backend/app/repositories/admin_config_repository.py` | DB access for all admin config tables |
| `backend/app/services/admin_config_service.py` | Business logic: pricing lookup, routing lookup, model registration check |
| `backend/app/services/admin_management_service.py` | Admin CRUD operations: model registry, pricing, routing, packs, config, users |
| `backend/app/api/v1/admin.py` | Admin API endpoints |
| `backend/migrations/versions/021_admin_pricing.py` | Database migration + seed data |
| `backend/tests/unit/test_admin_config_service.py` | Unit tests for config service |
| `backend/tests/unit/test_admin_management_service.py` | Unit tests for CRUD service |
| `backend/tests/unit/test_admin_api.py` | Unit tests for admin endpoints |

### Frontend

| File | Purpose |
|------|---------|
| `frontend/src/app/(main)/admin/config/page.tsx` | Admin config page |
| `frontend/src/components/admin/models-tab.tsx` | Model registry tab |
| `frontend/src/components/admin/pricing-tab.tsx` | Pricing config tab |
| `frontend/src/components/admin/routing-tab.tsx` | Task routing tab |
| `frontend/src/components/admin/packs-tab.tsx` | Credit pack tab |
| `frontend/src/components/admin/system-tab.tsx` | System config tab |
| `frontend/src/components/admin/users-tab.tsx` | User admin tab |
| `frontend/src/lib/api/admin.ts` | Admin API client |

### Modified Files

| File | Change |
|------|--------|
| `backend/app/models/user.py` | Add `is_admin` column |
| `backend/app/api/deps.py` | Add `require_admin` dependency, `AdminUser` type alias, `AdminConfig` type alias, update `get_metered_provider` and `get_metered_embedding_provider` |
| `backend/app/services/metering_service.py` | Replace `_LLM_PRICING` and `_FALLBACK_PRICING` with `AdminConfigService` lookups, remove `margin_multiplier` constructor parameter |
| `backend/app/providers/llm/base.py` | Add `model_override` to `complete()` signature |
| `backend/app/providers/llm/claude_adapter.py` | Accept `model_override` in `complete()`, add fallback docstring to `DEFAULT_CLAUDE_ROUTING` |
| `backend/app/providers/llm/openai_adapter.py` | Accept `model_override` in `complete()`, add fallback docstring to `DEFAULT_OPENAI_ROUTING` |
| `backend/app/providers/llm/gemini_adapter.py` | Accept `model_override` in `complete()`, add fallback docstring to `DEFAULT_GEMINI_ROUTING` |
| `backend/app/providers/metered_provider.py` | Add routing lookup via `AdminConfigService`, accept `admin_config` in constructor (both `MeteredLLMProvider` and `MeteredEmbeddingProvider`) |
| `backend/app/services/embedding_cost.py` | Add fallback docstring to `EMBEDDING_MODELS` dict (production pricing from `pricing_config` table) |
| `backend/app/core/config.py` | Add `admin_emails: str`, remove `metering_margin_multiplier` |
| `backend/app/api/v1/router.py` | Register admin router |
| `backend/app/api/v1/auth.py` | Add `ADMIN_EMAILS` check on login (auto-promote) |
| `frontend/src/middleware.ts` | Add admin route gate checking `adm` JWT claim |
| `frontend/src/components/layout/top-nav.tsx` | Add conditional "Admin" link (visible when `adm` JWT claim is present) |
| `backend/app/core/auth.py` | Add `is_admin` parameter to `create_jwt()` to include `adm` claim in JWT payload |

---

## 17. Resolved Questions

| # | Question | Answer | Rationale |
|---|----------|--------|-----------|
| 1 | How does the first admin get created? | `ADMIN_EMAILS` env var, checked on every login. | Bootstrap mechanism — no DB access needed to create first admin. Solves chicken-and-egg problem. |
| 2 | Can env-var admins be demoted? | No. Re-promoted on every login. | Prevents lockout scenario where all admins are accidentally removed. |
| 3 | Can admins promote others via the site? | Yes. Admin Users tab toggles `is_admin` on other users. | Ongoing management after bootstrap. |
| 4 | Should pricing and routing be cached? | No for MVP. Direct DB queries. | One indexed SELECT per LLM call adds negligible overhead to the existing 3-operation metering pipeline. Cache can be added later. |
| 5 | Should `credit_packs.stripe_price_id` be nullable? | Yes. `NOT NULL` + `UNIQUE` constraints added by REQ-021 migration. | Decouples pack creation from Stripe setup. Packs can exist before Stripe is integrated. |
| 6 | Should column renames (`balance_usd` → `balance_credits`) happen here? | No. Deferred to backlog #19. | Clean separation: this REQ adds new tables, #19 handles denomination and renames. |
| 7 | Where should routing lookup happen? | In `MeteredLLMProvider`, passed as `model_override` to adapter. | Adapter stays singleton-compatible. DB access already available in metered wrapper. |
| 8 | Should `credit_packs` be in this REQ or #19? | This REQ (#16). | Pack definitions are admin config. #19 adds denomination display settings only. |
| 9 | What about the existing `embedding_cost.py` pricing? | Migrated to `pricing_config` table alongside LLM pricing. | Single source of truth for all model pricing. |
| 10 | Should `task_routing_config` have effective dates? | No. Routing changes are immediate. | Routing changes are less frequent and less risky than pricing changes. Simplicity wins. |

---

## 18. Open Questions

| # | Question | Impact | Recommendation |
|---|----------|--------|----------------|
| 1 | What per-model margins should we use? | Seed data uses uniform 1.30 for zero-disruption deploy. Admin adjusts post-deploy. | Cheap models (Haiku, Flash, 4o-mini): 3.00–4.00. Expensive (Sonnet, GPT-4o): 1.10–1.50. Decide before first margin adjustment. |
| 2 | Should embedding models have per-model margins? | Embedding costs are negligible ($0.00002/1K). Higher margins produce trivial revenue. | Keep uniform 1.30 for embeddings. Not worth the complexity. |

---

## 19. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-03-01 | Initial draft |
