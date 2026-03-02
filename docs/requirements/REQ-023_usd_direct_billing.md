# REQ-023: USD-Direct Billing & Pack Configuration

**Status:** Not Started
**Version:** 0.1
**PRD Reference:** §6 Technical Architecture
**Backlog Item:** #19
**Last Updated:** 2026-03-02

---

## 1. Overview

This document specifies the transition from abstract credit-based billing to USD-direct billing, and defines the "Add Funds" pack model used by the Stripe integration (REQ-021). It is a prerequisite for REQ-021 because the seed data and configuration established here determine what Stripe sells and what gets credited to user balances.

**Why this REQ exists:** REQ-022 (Admin Pricing Dashboard, backlog #16) created the `credit_packs` and `system_config` tables and seeded them with abstract credit values (e.g., 50,000 credits for a $5 pack at 10,000 credits/dollar). A design review (2026-03-02, documented in backlog PBI #19) rejected abstract credits in favor of USD-direct billing. This REQ corrects the seed data, renames the relevant config key, and adds a frontend usage bar. It also serves as the formal errata for REQ-021, which was written assuming abstract credits.

**Scope boundary:** This REQ covers table/column renames, seed data corrections, a config key rename, and a usage bar component. The Stripe payment flow itself is specified in REQ-021. The metering pipeline (`metering_service.py`, `credit_transactions` table, `balance_usd` column) is unchanged.

### 1.1 What Changes

| Change | From (REQ-022) | To (this REQ) |
|--------|-----------------|---------------|
| Table name | `credit_packs` | `funding_packs` |
| Column name | `credit_packs.credit_amount` | `funding_packs.grant_cents` |
| Model class | `CreditPack` | `FundingPack` |
| Schema classes | `CreditPackCreate/Update/Response` | `FundingPackCreate/Update/Response` |
| TS types | `CreditPackItem/CreateRequest/UpdateRequest` | `FundingPackItem/CreateRequest/UpdateRequest` |
| Seed values | Abstract credits (50000, 175000, 500000) | USD cents matching price (500, 1000, 1500) |
| Seed descriptions | Generic ("Get started with Zentropy Scout") | Volume-based ("Analyze ~250 jobs...") |
| Seed pricing | $5 / $15 / $40 | $5 / $10 / $15 |
| `system_config` key | `signup_grant_credits` (abstract credits) | `signup_grant_cents` (USD cents) |
| Frontend balance display | Number only (`$X.XX`) | Number + visual usage bar |

### 1.2 What Does NOT Change

- **`credit_transactions` table** — NOT renamed. "Credit" here is the accounting term (credits and debits to a ledger), not abstract credits. This table is part of the metering pipeline (REQ-020) and renaming it would touch the entire metering codebase for no semantic benefit.
- **`balance_usd`, `amount_usd` columns** — Already correct. USD-direct means these names match their meaning.
- **`system_config`, `users` table structures** — Unchanged (only seed data and a config key name change).
- **Metering pipeline** — `metering_service.py` is unchanged. It already operates in USD.
- **Frontend formatting** — `formatBalance()` and `formatCost()` in `format-utils.ts` already display `$X.XX`. No changes needed.

---

## 2. Design Decisions

Full decision rationale is documented in the backlog PBI (`docs/backlog/feature-backlog.md`, item #19, "Decision Record: USD-Direct Over Abstract Credits" and "Decision Record: Funding Model & Pack Structure"). Summary below for implementer context.

### 2.1 USD-Direct Over Abstract Credits

**Decision:** Users see dollar amounts everywhere. No `credits_per_dollar` conversion layer.

**Why abstract credits were rejected:**
1. **Denomination dilemma** — Every `credits_per_dollar` ratio has a fatal tradeoff. At 10,000:1, $20 shows "200,000 credits" (feels like a mobile game). At 100:1, most operations round to 0 credits.
2. **Redenomination risk** — Changing `credits_per_dollar` retroactively changes all existing user balances. Mitigation strategies add significant complexity.
3. **Margin flexibility already exists** — Per-model `margin_multiplier` in `pricing_config` (REQ-022) handles profit margins without a credit abstraction.
4. **Professional SaaS precedent** — Anthropic, OpenAI, Vercel, AWS all show USD directly. Transparent pricing builds trust for a productivity tool.
5. **System already works in USD** — `balance_usd`, `amount_usd`, `billed_cost_usd`, and the frontend `$X.XX` formatting are all USD end-to-end.

**What this eliminates** (originally planned for backlog #19):
- ~~`credits_per_dollar` system config key~~
- ~~`credit_display_name` system config key~~
- ~~`display_precision` system config key~~
- ~~`rounding_mode` system config key~~
- ~~Frontend credit formatting utility~~
- ~~Admin denomination preview UI~~
- ~~Column renames (`balance_usd` → `balance_credits`)~~

### 2.2 Pack Model: Quick-Select, Not Differentiated Tiers

**Decision:** Packs are suggested funding amounts with admin-controlled volume-based descriptions. Not tiers with differentiated value.

- **Dollar-for-dollar for MVP.** Pay $10, get $10.00 balance. No volume bonuses.
- **Volume bonuses deferred.** Infrastructure supports it (`grant_cents > price_cents`) but the business decision is deferred.
- **Volume-based labels, not time-based.** Users buy a service (job analysis, resume generation), not time in the job market.
- **Admin-editable.** Names, descriptions, amounts, highlight labels all changeable from admin Packs tab without code deploy.

### 2.3 Naming Clean-Up

**Decision:** Rename the `credit_packs` table, model, and column to eliminate confusion between "abstract credits" (rejected) and the accounting term "credit" (valid).

| Entity | Old Name | New Name | Rationale |
|--------|----------|----------|-----------|
| Table | `credit_packs` | `funding_packs` | "Credit packs" implies packs of credits (rejected concept). "Funding packs" matches the "Add Funds" UI concept. |
| Column | `credit_amount` | `grant_cents` | Clarifies both the action (grant to balance) and the unit (USD cents). "credit_amount" was ambiguous — abstract credits vs accounting credit. |
| Model | `CreditPack` | `FundingPack` | Matches table rename. |
| Schemas | `CreditPack*` | `FundingPack*` | Matches model rename. |
| TS types | `CreditPack*` | `FundingPack*` | Matches API schema rename. |

**Why `credit_transactions` is NOT renamed:** "Credit" in `credit_transactions` is standard accounting terminology — the table stores credits (positive) and debits (negative) to a balance ledger. This is not the same "credits" as the rejected abstract credit system. Renaming it would touch the entire metering pipeline (REQ-020) for no semantic benefit. The table name is accurate.

**Why `balance_usd` and `amount_usd` are NOT renamed:** The USD-direct decision means these column names are now perfectly accurate. They were always correct — the abstract credit proposal would have renamed them away from accuracy.

### 2.4 Signup Grant

**Decision:** `signup_grant_cents` defaults to `10` ($0.10). Enough for approximately 5 job extractions or 2 complete workflows (extract + score + resume + cover letter). Gives users a meaningful taste of the service before requiring payment.

Admin-adjustable from the admin System Config tab. Set to `0` to disable.

---

## 3. Dependencies

### 3.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-022 Admin Pricing v0.1 | Foundation | `credit_packs` table and `system_config` table (created by REQ-022 migration). This REQ renames the table/column and updates seed data. |
| REQ-020 Token Metering v0.3 | Foundation | `balance_usd` column, `credit_transactions` table, balance API endpoints, nav bar display |

### 3.2 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-021 Credits & Billing v0.4 | Prerequisite | Stripe integration consumes the corrected seed data and config established here. REQ-021 v0.4 errata aligns it with USD-direct billing. |

### 3.3 Prerequisite Implementation Order

```
REQ-020 (metering) ✅ → REQ-022 (admin pricing) ✅ → REQ-023 (this) → REQ-021 (Stripe)
```

This REQ must be implemented before REQ-021 because:
- Stripe checkout sessions reference `funding_packs` — the table, column, and seed data must be correct before Stripe code is written against them
- REQ-021's signup grant logic reads `signup_grant_cents` — the key must exist with the right name
- All model/schema/type names must be finalized before REQ-021 builds on them
- The usage bar provides visual context for the balance that Stripe purchases affect

---

## 4. Backend Changes

### 4.1 Alembic Migration

A new Alembic migration applies schema changes and updates seed data from migration `021_admin_pricing`.

**Schema changes (run first):**

```sql
-- 1. Rename table
ALTER TABLE credit_packs RENAME TO funding_packs;

-- 2. Rename column
ALTER TABLE funding_packs RENAME COLUMN credit_amount TO grant_cents;

-- 3. Rename constraints
ALTER TABLE funding_packs RENAME CONSTRAINT ck_credit_packs_price_positive TO ck_funding_packs_price_positive;
ALTER TABLE funding_packs RENAME CONSTRAINT ck_credit_packs_amount_positive TO ck_funding_packs_amount_positive;

-- 4. Rename index
ALTER INDEX ix_credit_packs_active RENAME TO ix_funding_packs_active;
```

**Seed data update:**

```sql
-- Delete old seed packs (abstract credit values)
DELETE FROM funding_packs WHERE name IN ('Starter', 'Standard', 'Pro');

-- Insert corrected packs (USD cents, dollar-for-dollar)
INSERT INTO funding_packs (name, price_cents, grant_cents, display_order, is_active, description, highlight_label)
VALUES
    ('Starter',  500,  500,  1, TRUE, 'Analyze ~250 jobs and generate tailored materials', NULL),
    ('Standard', 1000, 1000, 2, TRUE, 'Analyze ~500 jobs and generate tailored materials', 'Most Popular'),
    ('Pro',      1500, 1500, 3, TRUE, 'Analyze ~750 jobs and generate tailored materials', 'Best Value');
```

**System config key rename:**

```sql
UPDATE system_config
SET key = 'signup_grant_cents',
    value = '10',
    description = 'USD cents granted to new users on signup (0 = disabled)'
WHERE key = 'signup_grant_credits';
```

**Key points:**
- `grant_cents` equals `price_cents` for MVP — dollar-for-dollar, no bonuses
- Descriptions are volume-based (admin can edit later)
- `stripe_price_id` remains NULL (populated when Stripe is configured per REQ-021)
- Uses DELETE + INSERT (not UPDATE) because pack UUIDs are generated, not deterministic

**Downgrade:**

```sql
-- Restore original table/column names
ALTER INDEX ix_funding_packs_active RENAME TO ix_credit_packs_active;
ALTER TABLE funding_packs RENAME CONSTRAINT ck_funding_packs_amount_positive TO ck_credit_packs_amount_positive;
ALTER TABLE funding_packs RENAME CONSTRAINT ck_funding_packs_price_positive TO ck_credit_packs_price_positive;
ALTER TABLE funding_packs RENAME COLUMN grant_cents TO credit_amount;
ALTER TABLE funding_packs RENAME TO credit_packs;

-- Restore original seed data
DELETE FROM credit_packs WHERE name IN ('Starter', 'Standard', 'Pro');
INSERT INTO credit_packs (name, price_cents, credit_amount, display_order, is_active, description, highlight_label)
VALUES
    ('Starter',  500,  50000,  1, TRUE, 'Get started with Zentropy Scout', NULL),
    ('Standard', 1500, 175000, 2, TRUE, 'For regular users', 'Most Popular'),
    ('Pro',      4000, 500000, 3, TRUE, 'For power users', 'Best Value');

-- Restore original config key
UPDATE system_config
SET key = 'signup_grant_credits',
    value = '0',
    description = 'Credits granted to new users on signup'
WHERE key = 'signup_grant_cents';
```

### 4.2 Model & Schema Renames

All Python classes and their references must be renamed:

**`backend/app/models/admin_config.py`:**
- `CreditPack` → `FundingPack`
- `__tablename__ = "credit_packs"` → `__tablename__ = "funding_packs"`
- `credit_amount: Mapped[int]` → `grant_cents: Mapped[int]`
- Update check constraint names in `__table_args__`
- Update docstring: "Abstract credits granted" → "USD cents granted to user's balance"

**`backend/app/models/__init__.py`:**
- Update import and `__all__` export: `CreditPack` → `FundingPack`

**`backend/app/schemas/admin.py`:**
- `CreditPackCreate` → `FundingPackCreate`
- `CreditPackUpdate` → `FundingPackUpdate`
- `CreditPackResponse` → `FundingPackResponse`
- `_check_credit_amount()` → `_check_grant_cents()`
- All `credit_amount` fields → `grant_cents`

**`backend/app/services/admin_management_service.py`:**
- All `CreditPack` references → `FundingPack`
- All `credit_amount` parameter names → `grant_cents`

**`backend/app/api/v1/admin.py`:**
- All `CreditPack*` imports and references → `FundingPack*`
- `_pack_response()` helper: `credit_amount=row.credit_amount` → `grant_cents=row.grant_cents`

### 4.3 Service Layer: Config Key Update

**`admin_config_service.py`** — Update any `get_system_config` call referencing `signup_grant_credits` to use `signup_grant_cents`. The value is USD cents (integer). To convert to `NUMERIC(10,6)` for `balance_usd` / `amount_usd`:

```python
grant_cents = await admin_config_service.get_system_config_int("signup_grant_cents", default=0)
grant_usd = Decimal(grant_cents) / Decimal(100)  # 10 cents → 0.100000
```

### 4.4 Column Semantics

The renamed `funding_packs.grant_cents` column (BIGINT):

| Before (REQ-022) | After (REQ-023) |
|-------------------|-----------------|
| `credit_amount`: abstract credits (e.g., 50000) | `grant_cents`: USD cents (e.g., 500 = $5.00) |
| Derived from `credits_per_dollar × price` | Equals `price_cents` for MVP (dollar-for-dollar) |
| Could differ from `price_cents` via denomination | Can differ from `price_cents` via volume bonuses (future) |

---

## 5. Frontend Changes

### 5.1 Usage Bar Component

Add a visual balance indicator to the balance card (`frontend/src/components/usage/balance-card.tsx`).

**Requirements:**
- Horizontal bar below the `$X.XX` text display
- Color-coded using the same thresholds as the nav bar (REQ-020 §9.1):
  - Green: balance > $1.00
  - Amber: balance $0.10 – $1.00
  - Red: balance < $0.10
- Bar width proportional to balance on a linear scale, capped at $15.00 (the largest default pack). Balances above $15 show a full bar.
- Accessible: include `aria-label` with the current balance amount

**Visual example:**
```
Balance: $7.42
[████████████░░░░░░░░]  ← green, ~50% width ($7.42 / $15.00)

Balance: $0.45
[██░░░░░░░░░░░░░░░░░░]  ← amber, ~3% width

Balance: $0.03
[░░░░░░░░░░░░░░░░░░░░]  ← red, near-empty
```

**Implementation note:** The bar reference point ($15.00) can be hardcoded for now. If we need it to be dynamic (e.g., match the largest active pack), it can be derived from the packs API response in a future iteration.

### 5.2 Nav Bar (No Changes)

The existing nav bar balance indicator (`frontend/src/components/layout/top-nav.tsx`) already displays `$X.XX` with green/amber/red color coding. No changes needed from this REQ.

---

## 6. Impact on Other REQs

This REQ supersedes specific sections of REQ-021 and REQ-022. The following table documents what changed and where the authoritative version now lives.

### 6.1 REQ-021 (Credits & Billing) — Errata Applied in v0.4

| Section | What Changed | Old Value | New Value |
|---------|-------------|-----------|-----------|
| §1, §1.2 | Billing model | "Abstract credits" | "USD-direct" |
| §2.2 | Pricing strategy | "Packs grant abstract credits" | "Packs grant USD balance (dollar-for-dollar)" |
| §2.5 | Signup grant | "10,000 credits" | "$0.10 (signup_grant_cents)" |
| §3.1, §3.3 | Dependency on #19 | "credits_per_dollar, formatting utility" | "Corrected seed data, table/column renames, signup_grant_cents key" |
| §4.3 | Table/column names | `credit_packs.credit_amount` | `funding_packs.grant_cents` |
| §4.3 | Schema/type names | `CreditPack*` | `FundingPack*` |
| §5.1 | Pack definitions | $5/50K, $15/175K, $40/500K with bonuses | $5/$10/$15, dollar-for-dollar, volume descriptions |
| §6.7, §6.3 | Balance crediting | "Abstract credits", column renames pending | USD cents via `grant_cents`, existing balance columns correct |
| §7.1 | GET /packs response | `credit_display: "50,000 credits"` | `amount_display: "$5.00"`, `grant_cents` field |
| §7.3 | GET /purchases response | `credit_display: "175,000 credits"` | `amount_display: "$17.50"` |
| §9.1 | Credits page display | "125,430 credits" | "$12.54" |
| §15 Q#4 | Denomination decision | "Abstract credits" | "USD-direct (see REQ-023 §2.1)" |

### 6.2 REQ-022 (Admin Pricing) — Table Renamed, Seed Data Superseded

| Section | What Changed | Old Value | New Value |
|---------|-------------|-----------|-----------|
| §4.5 | Table name | `credit_packs` | `funding_packs` |
| §4.5 | Column name | `credit_amount` (BIGINT) | `grant_cents` (BIGINT) |
| §4.5 | Constraint names | `ck_credit_packs_*` | `ck_funding_packs_*` |
| §4.5 | Index name | `ix_credit_packs_active` | `ix_funding_packs_active` |
| §12.4 | system_config key | `signup_grant_credits = 0` | `signup_grant_cents = 10` |
| §12.5 | Seed data | 50000/175000/500000 at $5/$15/$40 | 500/1000/1500 at $5/$10/$15 |

REQ-022's other table schemas (§4.1–§4.4, §4.6) are unchanged.

---

## 7. Testing Requirements

### 7.1 Migration Tests

| Test | Scenario |
|------|----------|
| Upgrade applies cleanly | Migration runs without error on a database with existing seed data |
| Table renamed | `funding_packs` table exists; `credit_packs` does not |
| Column renamed | `funding_packs.grant_cents` exists; `credit_amount` does not |
| Constraints renamed | `ck_funding_packs_price_positive` and `ck_funding_packs_amount_positive` exist |
| Packs updated | 3 packs exist with `grant_cents == price_cents` and volume-based descriptions |
| Config key renamed | `signup_grant_cents` exists with value `10`; `signup_grant_credits` does not exist |
| Downgrade restores | After downgrade: original table/column names, seed data, and config key restored |

### 7.2 Backend Unit Tests

All existing tests for packs must be updated to use the new names and pass:

| Test File | Key Updates |
|-----------|------------|
| `test_admin_config_models.py` | `CreditPack` → `FundingPack`, `credit_amount` → `grant_cents`, table name in raw SQL |
| `test_admin_schemas.py` | `CreditPackCreate/Update/Response` → `FundingPack*`, `credit_amount` → `grant_cents` |
| `test_admin_management_service.py` | `CreditPack` → `FundingPack`, `credit_amount` → `grant_cents` |
| `test_admin_api.py` | `credit_amount` → `grant_cents` in request/response bodies |

### 7.3 Frontend Tests

| Test File | Key Updates |
|-----------|------------|
| `packs-tab.test.tsx` | `CreditPackItem` → `FundingPackItem`, `credit_amount` → `grant_cents` |
| `admin-mock-data.ts` | `CreditPackItem` → `FundingPackItem`, `credit_amount` → `grant_cents` |
| `admin.test.ts` | `credit_amount` → `grant_cents` in request bodies |

### 7.4 Usage Bar Tests

| Test | Scenario |
|------|----------|
| Usage bar renders | Balance card shows a horizontal bar below the dollar amount |
| Bar color green | When balance > $1.00, bar is green |
| Bar color amber | When balance $0.10–$1.00, bar is amber |
| Bar color red | When balance < $0.10, bar is red |
| Bar width scales | Bar width is proportional to balance (capped at $15.00 = 100%) |
| Bar accessible | `aria-label` includes the balance amount |

### 7.5 Integration Tests

| Test | Scenario |
|------|----------|
| Config key consumed | `admin_config_service.get_system_config_int("signup_grant_cents")` returns `10` |
| Old key absent | `admin_config_service.get_system_config("signup_grant_credits")` returns the default (not found) |

---

## 8. Files Modified

### 8.1 Backend

| File | Change |
|------|--------|
| `backend/migrations/versions/023_usd_direct_billing.py` | **New.** Rename table/column/constraints/index, update seed data, rename config key |
| `backend/app/models/admin_config.py` | `CreditPack` → `FundingPack`, `credit_amount` → `grant_cents`, update `__tablename__`, constraints, docstring |
| `backend/app/models/__init__.py` | Update import/export: `CreditPack` → `FundingPack` |
| `backend/app/schemas/admin.py` | `CreditPackCreate/Update/Response` → `FundingPackCreate/Update/Response`, `credit_amount` → `grant_cents`, rename validator |
| `backend/app/services/admin_management_service.py` | `CreditPack` → `FundingPack`, `credit_amount` → `grant_cents` throughout |
| `backend/app/api/v1/admin.py` | Update imports and all `CreditPack*` / `credit_amount` references |
| `backend/tests/unit/test_admin_config_models.py` | Update model refs, table name in SQL, column name |
| `backend/tests/unit/test_admin_schemas.py` | Update schema class names and field names |
| `backend/tests/unit/test_admin_management_service.py` | Update model refs and field names |
| `backend/tests/unit/test_admin_api.py` | Update field names in request/response assertions |

### 8.2 Frontend

| File | Change |
|------|--------|
| `frontend/src/types/admin.ts` | `CreditPackItem/CreateRequest/UpdateRequest` → `FundingPackItem/CreateRequest/UpdateRequest`, `credit_amount` → `grant_cents` |
| `frontend/src/types/index.ts` | Update re-exports |
| `frontend/src/lib/api/admin.ts` | Update type imports and function signatures |
| `frontend/src/lib/api/admin.test.ts` | Update `credit_amount` → `grant_cents` in test data |
| `frontend/src/components/admin/packs-tab.tsx` | Update type imports and `credit_amount` → `grant_cents` references |
| `frontend/src/components/admin/packs-tab.test.tsx` | Update type imports and mock data |
| `frontend/src/components/admin/add-pack-dialog.tsx` | Update `creditAmount` state/props and `credit_amount` field name |
| `frontend/tests/fixtures/admin-mock-data.ts` | Update type import and `credit_amount` → `grant_cents` in fixtures |
| `frontend/src/components/usage/balance-card.tsx` | **Modified.** Add usage bar component |

### 8.3 Documentation

| File | Change |
|------|--------|
| `docs/requirements/REQ-021_credits_billing.md` | Apply v0.4 errata (USD-direct, new table/column names) |

---

## 9. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-02 | 0.1 | Initial version. Documents USD-direct billing decision, seed data migration, config key rename, usage bar, and REQ-021 errata. Decision rationale references backlog PBI #19. |
| 2026-03-02 | 0.2 | Added table/column/constraint rename: `credit_packs` → `funding_packs`, `credit_amount` → `grant_cents`. Added comprehensive file inventory for all backend and frontend renames. Added §2.3 (Naming Clean-Up) design decision with rationale for what IS and IS NOT renamed. |
