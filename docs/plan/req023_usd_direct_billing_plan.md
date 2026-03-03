# Zentropy Scout — REQ-023 USD-Direct Billing Implementation Plan

**Created:** 2026-03-02
**Last Updated:** 2026-03-02
**Status:** ⬜ Not Started
**Destination:** `docs/plan/req023_usd_direct_billing_plan.md`

---

## Context

REQ-022 (Admin Pricing Dashboard) created the `credit_packs` table and seeded it with abstract credit values (50,000 credits for $5). A design review (2026-03-02, documented in backlog PBI #19 and REQ-023) rejected abstract credits in favor of USD-direct billing. This plan corrects the naming, seed data, and adds a usage bar before REQ-021 (Stripe) builds on top.

**What changes:** `credit_packs` table → `funding_packs`, `credit_amount` column → `grant_cents`, `CreditPack` model/schemas/types → `FundingPack*`, `/admin/credit-packs` routes → `/admin/funding-packs`, `signup_grant_credits` config key → `signup_grant_cents`, seed data updated to USD cents (dollar-for-dollar), usage bar added to balance card.

**What does NOT change:** `credit_transactions` table (accounting term, not abstract credits), `balance_usd`/`amount_usd` columns (already correct), metering pipeline, frontend formatting utilities.

**Scope:** 1 Alembic migration, 10 backend file renames, 10 frontend file renames, 1 new UI component, 1 documentation errata. No new tables, no new endpoints, no new business logic.

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Load REQ-023 via `req-reader` subagent before each task
3. Each task = one commit, sized ≤ 40k tokens of context (TDD + review + fixes included)
4. **Subtask workflow:** Run affected tests → linters → commit → compact (NO push)
5. **Phase-end workflow:** Run full test suite (backend + frontend + E2E) → push → compact
6. After each task: update status (⬜ → ✅), commit, STOP and ask user

**Workflow pattern:**

| Action | Subtask (§1, §3, §5, §7, §9) | Phase Gate (§2, §4, §6, §8, §10) |
|--------|--------------------------|------------------------------|
| Tests | Affected files only | Full backend + frontend + E2E |
| Linters | Pre-commit hooks (~25-40s) | Pre-commit + pre-push hooks |
| Git | `git commit` only | `git push` |
| Context | Compact after commit | Compact after push |

**Why:** Pushes trigger pre-push hooks (full pytest + vitest, ~90-135s). By deferring pushes to phase boundaries, we save ~90-135s per subtask while maintaining quality gates.

**Context management for fresh sessions:** Each subtask is self-contained. A fresh context window needs:
1. This plan (find current task by status icon)
2. REQ-023 (via `req-reader` — load the §section listed in the task)
3. The specific files listed in the task description
4. No prior conversation history required

---

## Dependency Chain

```
Phase 1: Database Migration (REQ-023 §4.1, §7.6)
    │
    ▼
Phase 2: Backend Renames (REQ-023 §4.2–§4.5)
    │
    ▼
Phase 3: Frontend Renames (REQ-023 §2.5, §5.2, §7.3–§7.4)
    │
    ▼
Phase 4: Usage Bar (REQ-023 §5.1, §7.5)
    │
    ▼
Phase 5: Documentation Errata (REQ-023 §6.1, §8.3)
```

**Ordering rationale:** Phases are strictly sequential. Migration must run before code references new names. Backend renames must complete before frontend (API routes must match). Usage bar is independent of renames but placed after to keep rename phases contiguous. Documentation errata is last because it has no code impact.

---

## Phase 1: Database Migration (REQ-023 §4.1, §7.6)

**Status:** ⬜

*Alembic migration to rename table/column/constraints/index, update seed data, rename system config key. Fix raw SQL tests. Write integration tests for config key rename.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-023 §4.1, §7.6. Read `021_admin_pricing.py` for format/revision chain. `alembic heads` to confirm current state. Read `test_admin_config_models.py` lines 361–381 (raw SQL tests to fix). |
| 🔧 **Create** | Write `022_usd_direct_billing.py` with upgrade + downgrade. Fix 2 raw SQL tests. Write 2 integration tests. |
| ✅ **Verify** | `alembic upgrade head` → `alembic downgrade -1` → `alembic upgrade head`. Verify via SQL queries. Run affected tests. |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` (parallel) |
| 📝 **Commit** | `feat(db): rename credit_packs to funding_packs and update seed data` |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Write Alembic migration + fix raw SQL tests + integration tests** | | ⬜ |
| | **Read:** REQ-023 §4.1 (full SQL for upgrade + downgrade), §7.6 (integration test scenarios). Reference: `backend/migrations/versions/021_admin_pricing.py` (revision chain, format). `backend/tests/unit/test_admin_config_models.py` lines 350–381 (raw SQL tests). `backend/app/services/admin_config_service.py` lines 148–163 (docstring referencing `signup_grant_credits`). | `req-reader, db` | |
| | | | |
| | **Create:** `backend/migrations/versions/022_usd_direct_billing.py` | | |
| | — `revision = "022_usd_direct_billing"`, `down_revision = "021_admin_pricing"` | | |
| | — **Upgrade (in order):** | | |
| | (1) `ALTER TABLE credit_packs RENAME TO funding_packs` | | |
| | (2) `ALTER TABLE funding_packs RENAME COLUMN credit_amount TO grant_cents` | | |
| | (3) Rename check constraints: `ck_credit_packs_price_positive` → `ck_funding_packs_price_positive`, `ck_credit_packs_amount_positive` → `ck_funding_packs_amount_positive` | | |
| | (4) Rename index: `ix_credit_packs_active` → `ix_funding_packs_active` | | |
| | (5) `DELETE FROM funding_packs WHERE name IN ('Starter','Standard','Pro')` then INSERT 3 new packs: | | |
| | — Starter: 500 price_cents, 500 grant_cents, order 1, 'Analyze ~250 jobs and generate tailored materials', NULL highlight | | |
| | — Standard: 1000 price_cents, 1000 grant_cents, order 2, 'Analyze ~500 jobs and generate tailored materials', 'Most Popular' | | |
| | — Pro: 1500 price_cents, 1500 grant_cents, order 3, 'Analyze ~750 jobs and generate tailored materials', 'Best Value' | | |
| | (6) `UPDATE system_config SET key='signup_grant_cents', value='10', description='USD cents granted to new users on signup (0 = disabled)' WHERE key='signup_grant_credits'` | | |
| | — **Downgrade (reverse order):** | | |
| | (1) Restore config key: `UPDATE system_config SET key='signup_grant_credits', value='0', description='Credits granted to new users on signup' WHERE key='signup_grant_cents'` | | |
| | (2) Restore seed data: DELETE new packs, INSERT originals (Starter 500/50000, Standard 1500/175000, Pro 4000/500000 with original descriptions) | | |
| | (3) Rename index back: `ix_funding_packs_active` → `ix_credit_packs_active` | | |
| | (4) Rename constraints back: `ck_funding_packs_*` → `ck_credit_packs_*` | | |
| | (5) Rename column back: `grant_cents` → `credit_amount` | | |
| | (6) Rename table back: `funding_packs` → `credit_packs` | | |
| | | | |
| | **Fix 2 raw SQL tests in `test_admin_config_models.py`** (Option B — fix alongside migration): | | |
| | — Line 366: `INSERT INTO credit_packs (...credit_amount...)` → `INSERT INTO funding_packs (...grant_cents...)` | | |
| | — Line 376: `INSERT INTO credit_packs (...credit_amount...)` → `INSERT INTO funding_packs (...grant_cents...)` | | |
| | — Update test names: `test_credit_pack_rejects_zero_price` → `test_funding_pack_rejects_zero_price`, `test_credit_pack_rejects_zero_credit_amount` → `test_funding_pack_rejects_zero_grant_cents` | | |
| | — Update raw SQL column names in VALUES clause | | |
| | | | |
| | **Write 2 integration tests (REQ-023 §7.6):** Add to `test_admin_config_models.py` or a new test file: | | |
| | — `test_signup_grant_cents_key_exists` — After migration, `AdminConfigService.get_system_config_int("signup_grant_cents")` returns `10` | | |
| | — `test_signup_grant_credits_key_absent` — After migration, `AdminConfigService.get_system_config("signup_grant_credits")` returns default (None) | | |
| | | | |
| | **Run:** `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head`. | | |
| | **Verify:** `SELECT name, price_cents, grant_cents FROM funding_packs ORDER BY display_order;` — 3 rows, `grant_cents == price_cents`. | | |
| | **Verify:** `SELECT key, value FROM system_config WHERE key = 'signup_grant_cents';` — returns `10`. | | |
| | **Run:** `pytest tests/unit/test_admin_config_models.py -v` | | |
| | **Done when:** Migration runs cleanly in both directions. No `credit_packs` table exists after upgrade. `funding_packs` has correct data. Raw SQL tests pass. Integration tests pass. | | |
| 2 | **Phase 1 Gate** — Full backend test suite + push | `phase-gate` | ⬜ |
| | **Run:** `cd backend && python -m pytest tests/ -v`. Run pre-push hooks. Push with SSH keep-alive: `GIT_SSH_COMMAND="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=10" git push`. | | |
| | **Note:** Some tests still reference old model/table names (ORM tests use `CreditPack` class which still has `__tablename__ = "credit_packs"` until Phase 2). The migration renamed the DB table but the ORM model isn't updated yet — **this works** because SQLAlchemy resolves via the model class, and the raw SQL tests were already fixed in §1. | | |
| | **Done when:** All backend tests pass. Pushed to remote. | | |

#### Phase 1 Notes

The migration renames the physical DB table before the ORM model is updated. This works because:
- ORM tests use the `CreditPack` class (SQLAlchemy resolves via the class, not the table name string at query time)
- The 2 raw SQL tests that use `INSERT INTO credit_packs` are fixed in §1 alongside the migration (Option B from plan review)
- No other tests use raw SQL against this table

The integration tests (§7.6) verify the migration's config key rename is consumable by the existing `AdminConfigService`. These are tiny (2 tests) and belong with the migration rather than the backend renames.

---

## Phase 2: Backend Renames (REQ-023 §4.2–§4.5, §7.2)

**Status:** ⬜

*Rename CreditPack → FundingPack, credit_amount → grant_cents, /credit-packs → /funding-packs across all backend source and test files.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-023 §4.2–§4.4 and §7.2. |
| 🔧 **Rename** | Mechanical find-and-replace across 10 files per checklist. |
| ✅ **Verify** | `cd backend && python -m pytest tests/ -v` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` (parallel) |
| 📝 **Commit** | `refactor(backend): rename CreditPack to FundingPack` |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 3 | **Backend source + test renames (10 files)** | | ⬜ |
| | **Read:** REQ-023 §4.2–§4.4, §7.2. Read relevant sections of all files below. | `req-reader` | |
| | | | |
| | **Source file 1: `backend/app/models/admin_config.py`** (~293 lines) | `rename` | |
| | — Class: `CreditPack` → `FundingPack` | | |
| | — `__tablename__`: `"credit_packs"` → `"funding_packs"` | | |
| | — Column: `credit_amount: Mapped[int]` → `grant_cents: Mapped[int]` | | |
| | — Check constraint string: `"credit_amount > 0"` → `"grant_cents > 0"` | | |
| | — Constraint names: `ck_credit_packs_*` → `ck_funding_packs_*` | | |
| | — Docstring: "Abstract credits granted" → "USD cents granted to user's balance" | | |
| | | | |
| | **Source file 2: `backend/app/models/__init__.py`** (~116 lines) | `rename` | |
| | — Import: `CreditPack` → `FundingPack` | | |
| | — `__all__`: `"CreditPack"` → `"FundingPack"` | | |
| | — Module docstring: update `CreditPack` mention | | |
| | | | |
| | **Source file 3: `backend/app/schemas/admin.py`** (~713 lines, pack section ~lines 397–610) | `rename` | |
| | — Section comment: `# Credit Packs` → `# Funding Packs` | | |
| | — Helper: `_check_credit_amount()` → `_check_grant_cents()`, update error messages | | |
| | — 3 class renames: `CreditPackCreate/Update/Response` → `FundingPackCreate/Update/Response` | | |
| | — All `credit_amount` fields → `grant_cents` (3 field decls + 2 validator decorators + docstrings) | | |
| | | | |
| | **Source file 4: `backend/app/services/admin_management_service.py`** (~842 lines, pack section ~lines 565–691) | `rename` | |
| | — Import: `CreditPack` → `FundingPack` | | |
| | — ~10 `CreditPack` type refs (return types, instantiation, `select()`, `db.get()`) | | |
| | — ~7 `credit_amount` refs (params, assignments, docstrings) → `grant_cents` | | |
| | | | |
| | **Source file 5: `backend/app/api/v1/admin.py`** (~664 lines, pack section ~lines 451–523) | `rename` | |
| | — Imports: `CreditPack`, `CreditPackCreate`, `CreditPackResponse`, `CreditPackUpdate` → `FundingPack*` | | |
| | — 4 route paths: `"/credit-packs"` → `"/funding-packs"` (lines ~455, 469, 492, 510) | | |
| | — `_pack_response()` helper: type annotation + `credit_amount=row.credit_amount` → `grant_cents=row.grant_cents` | | |
| | — Body params and return type annotations | | |
| | — Docstrings: update REQ refs and path names | | |
| | | | |
| | **Source file 6: `backend/app/services/admin_config_service.py`** (~164 lines) | `rename` | |
| | — Docstring only: `signup_grant_credits` → `signup_grant_cents` (line ~154) | | |
| | | | |
| | **Test file 1: `backend/tests/unit/test_admin_config_models.py`** (~416 lines, 7 pack tests) | `rename` | |
| | — Import: `CreditPack` → `FundingPack` | | |
| | — Factory: `_make_credit_pack()` → `_make_funding_pack()`, `credit_amount` default → `grant_cents` | | |
| | — Class: `TestCreditPack` → `TestFundingPack` | | |
| | — All `credit_amount` refs → `grant_cents` in assertions and constructors | | |
| | — ⚠️ Raw SQL tests already fixed in §1 — no further changes needed for those 2 tests | | |
| | | | |
| | **Test file 2: `backend/tests/unit/test_admin_schemas.py`** (~655 lines, 12 pack tests) | `rename` | |
| | — Imports: `CreditPackCreate/Update/Response` → `FundingPack*` | | |
| | — 3 class renames: `TestCreditPackCreate/Update/Response` → `TestFundingPack*` | | |
| | — All `credit_amount` refs → `grant_cents` (~11 occurrences in fields, assertions, error match strings) | | |
| | | | |
| | **Test file 3: `backend/tests/unit/test_admin_management_service.py`** (~938 lines, 8 pack tests) | `rename` | |
| | — Import: `CreditPack` → `FundingPack` | | |
| | — Factory: `_make_pack()` — `credit_amount` param → `grant_cents` | | |
| | — Class: `TestCreditPacks` → `TestFundingPacks` | | |
| | — All `credit_amount` refs → `grant_cents` in calls and assertions | | |
| | | | |
| | **Test file 4: `backend/tests/unit/test_admin_api.py`** (~653 lines, 5 pack tests) | `rename` | |
| | — Helper: `_seed_pack()` — `credit_amount` param → `grant_cents`, URL `/credit-packs` → `/funding-packs` | | |
| | — Class: `TestCreditPackEndpoints` → `TestFundingPackEndpoints` | | |
| | — Auth test: `GET /admin/credit-packs` → `/admin/funding-packs` | | |
| | — All URL strings and `credit_amount` json keys → `grant_cents` | | |
| | | | |
| | **⚠️ DO NOT rename `credit_amount` in `test_metering_integration.py`** — it's a local `Decimal` variable for USD amounts, unrelated to `CreditPack`. | `caution` | |
| | | | |
| | **Run:** `cd backend && python -m pytest tests/ -v` — all tests must pass. | `commands` | |
| | **Done when:** Zero references to `CreditPack`, `credit_amount` (in pack context), or `/credit-packs` in backend source or test files. All tests pass. | | |
| 4 | **Phase 2 Gate** — Full backend + frontend tests, push | `phase-gate` | ⬜ |
| | **Run:** `cd backend && python -m pytest tests/ -v`. Then `cd frontend && npm test -- --run && npm run typecheck`. Frontend should still pass (hasn't changed yet — it hits mocked routes, not real backend). Push with SSH keep-alive: `GIT_SSH_COMMAND="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=10" git push`. | | |
| | **Done when:** All backend + frontend tests pass. Pushed to remote. | | |

#### Phase 2 Notes

**Why 10 files in one subtask:** The renames are purely mechanical (find-and-replace, no logic changes). Splitting into source-then-tests would create a broken intermediate state where source uses new names but tests reference old names — tests cannot pass between the two halves. Prior plan precedent: admin pricing Phase 5 §17 touched 8 files in one subtask at 40k budget.

**Caution on `credit_amount` in metering tests:** `test_metering_integration.py` uses `credit_amount` as a local `Decimal` variable for USD cost calculations. This is the accounting sense of "credit" and must NOT be renamed.

---

## Phase 3: Frontend Renames (REQ-023 §2.5, §5.2, §7.3–§7.4)

**Status:** ⬜

*Rename CreditPack* → FundingPack*, credit_amount → grant_cents, /credit-packs → /funding-packs across all frontend source, test, and E2E files.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-023 §2.5, §5.2, §7.3–§7.4. |
| 🔧 **Rename** | Mechanical find-and-replace across 10 files per checklist. |
| ✅ **Verify** | `cd frontend && npm test -- --run && npm run typecheck` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` (parallel) |
| 📝 **Commit** | `refactor(frontend): rename CreditPack to FundingPack` |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 5 | **Frontend source + test renames (10 files)** | | ⬜ |
| | **Read:** REQ-023 §2.5, §5.2, §7.3–§7.4. Read relevant sections of all files below. | `req-reader` | |
| | | | |
| | **Source file 1: `frontend/src/types/admin.ts`** (~171 lines) | `rename` | |
| | — Section comment: `// Credit Packs` → `// Funding Packs` | | |
| | — 3 interface renames: `CreditPackItem/CreateRequest/UpdateRequest` → `FundingPackItem/CreateRequest/UpdateRequest` | | |
| | — 3 field renames: `credit_amount` → `grant_cents` (in all 3 interfaces) | | |
| | | | |
| | **Source file 2: `frontend/src/types/index.ts`** (~187 lines) | `rename` | |
| | — 3 re-export names in `export type { ... } from "./admin"` block (~lines 173–175) | | |
| | | | |
| | **Source file 3: `frontend/src/lib/api/admin.ts`** (~182 lines) | `rename` | |
| | — 3 type imports: `CreditPack*` → `FundingPack*` | | |
| | — Section comment: `// Credit Packs` → `// Funding Packs` | | |
| | — 3 return type annotations using `CreditPackItem` → `FundingPackItem` | | |
| | — 4 URL strings: `"/admin/credit-packs"` → `"/admin/funding-packs"` (~lines 119, 125, 132, 136) | | |
| | — Function names `fetchPacks`/`createPack`/`updatePack`/`deletePack` are generic — no change needed | | |
| | | | |
| | **Source file 4: `frontend/src/components/admin/packs-tab.tsx`** (~204 lines) | `rename` | |
| | — JSDoc: "Credit pack" → "Funding pack" | | |
| | — Import: `CreditPackCreateRequest, CreditPackItem` → `FundingPackCreateRequest, FundingPackItem` | | |
| | — 2 type annotations using `CreditPackItem` → `FundingPackItem` | | |
| | — Field access: `item.credit_amount.toLocaleString()` → `item.grant_cents.toLocaleString()` | | |
| | — Column header: `<TableHead>Credits</TableHead>` → `<TableHead>Grant (¢)</TableHead>` | | |
| | | | |
| | **Source file 5: `frontend/src/components/admin/add-pack-dialog.tsx`** (~152 lines) | `rename` | |
| | — JSDoc: "credit pack" → "funding pack" | | |
| | — Prop type: `credit_amount: number` → `grant_cents: number` (in onSubmit signature) | | |
| | — State: `creditAmount`/`setCreditAmount` → `grantCents`/`setGrantCents` (~5 occurrences) | | |
| | — Submit payload: `credit_amount: credits` → `grant_cents: credits` | | |
| | — Deps array: `creditAmount` → `grantCents` | | |
| | — Label: `"Credit Amount"` → `"Grant Amount (cents)"` | | |
| | — Input id: `"add-pack-credits"` → `"add-pack-grant-cents"` | | |
| | | | |
| | **Test file 1: `frontend/src/lib/api/admin.test.ts`** (~310 lines) | `rename` | |
| | — Describe label: `"Credit Packs"` → `"Funding Packs"` | | |
| | — ~7 URL strings: `/admin/credit-packs` → `/admin/funding-packs` | | |
| | — 1 body key: `credit_amount: 100000` → `grant_cents: 100000` | | |
| | | | |
| | **Test file 2: `frontend/src/components/admin/packs-tab.test.tsx`** (~224 lines) | `rename` | |
| | — Import: `CreditPackItem` → `FundingPackItem` | | |
| | — Type annotation: `CreditPackItem[]` → `FundingPackItem[]` | | |
| | — 2 mock data fields: `credit_amount` → `grant_cents` | | |
| | — Label query: `getByLabelText(/credit amount/i)` → match new label text (`/grant amount/i`) | | |
| | | | |
| | **Test file 3: `frontend/tests/fixtures/admin-mock-data.ts`** (~293 lines) | `rename` | |
| | — Import: `CreditPackItem` → `FundingPackItem` | | |
| | — Type annotation: `CreditPackItem[]` → `FundingPackItem[]` | | |
| | — Section comment: `// Credit Packs` → `// Funding Packs` | | |
| | — 2 mock data fields: `credit_amount` → `grant_cents` | | |
| | — JSDoc: `GET /admin/credit-packs` → `/admin/funding-packs` | | |
| | | | |
| | **Test file 4: `frontend/tests/utils/admin-api-mocks.ts`** (~281 lines) | `rename` | |
| | — Section comment: `// --- Credit Packs ---` → `// --- Funding Packs ---` | | |
| | — 2 regex patterns: `/\/admin\/credit-packs$/` → `/\/admin\/funding-packs$/` and with `/[^/]+$` | | |
| | | | |
| | **Test file 5: `frontend/tests/e2e/admin.spec.ts`** (~427 lines) | `rename` | |
| | — Test description: `"renders credit pack table"` → `"renders funding pack table"` | | |
| | | | |
| | **Run:** `cd frontend && npm test -- --run && npm run typecheck` — all tests pass, no type errors. | `commands` | |
| | **Done when:** Zero references to `CreditPack`, `credit_amount` (in pack context), or `credit-packs` in frontend source or test files. All tests + typecheck pass. | | |
| 6 | **Phase 3 Gate** — Full backend + frontend + E2E tests, push | `phase-gate` | ⬜ |
| | **Run:** `cd backend && python -m pytest tests/ -v`. Then `cd frontend && npm test -- --run && npm run typecheck`. Then E2E: `cd frontend && npx playwright test tests/e2e/admin.spec.ts`. Push with SSH keep-alive: `GIT_SSH_COMMAND="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=10" git push`. | | |
| | **Done when:** All backend + frontend + E2E tests pass. Pushed to remote. | | |

#### Phase 3 Notes

**Same rationale as Phase 2 for 10 files in one subtask.** TS types are exported from `types/admin.ts` and imported by components and tests. Renaming types without updating tests creates a broken intermediate state.

---

## Phase 4: Usage Bar (REQ-023 §5.1, §7.5)

**Status:** ⬜

*Add visual usage depletion bar to the balance card component.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-023 §5.1 (requirements, visual examples, $15 cap) and §7.5 (6 test scenarios). Read `balance-card.tsx` (~56 lines) and `balance-card.test.tsx` (~73 lines, 8 existing tests). |
| 🧪 **TDD** | Write 6 new tests for color thresholds and width scaling. Then implement. |
| ✅ **Verify** | `cd frontend && npm test -- --run balance-card && npm run typecheck` |
| 🔍 **Review** | `code-reviewer` + `ui-reviewer` (parallel) |
| 📝 **Commit** | `feat(frontend): add usage bar to balance card` |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 7 | **Usage bar component + tests (TDD)** | | ⬜ |
| | **Read:** REQ-023 §5.1 (color thresholds, visual examples, $15 cap), §7.5 (6 test scenarios). `frontend/src/components/usage/balance-card.tsx` (~56 lines). `frontend/src/components/usage/balance-card.test.tsx` (~73 lines, 8 existing tests). | `req-reader, tdd` | |
| | | | |
| | **TDD — write 6 new tests in `balance-card.test.tsx`:** | `tdd` | |
| | — `"renders usage bar"` — bar element exists below balance amount (`data-testid="usage-bar"`) | | |
| | — `"usage bar is green when balance > $1.00"` — e.g., balance="5.000000" → green background class (`bg-success`) | | |
| | — `"usage bar is amber when balance $0.10–$1.00"` — e.g., balance="0.500000" → amber/primary class (`bg-primary`) | | |
| | — `"usage bar is red when balance < $0.10"` — e.g., balance="0.050000" → destructive class (`bg-destructive`) | | |
| | — `"usage bar width scales with balance"` — balance="7.500000" → 50% width (7.50/15.00). balance="15.000000" → 100%. balance="20.000000" → capped at 100%. | | |
| | — `"usage bar has accessible label"` — `aria-label` contains the formatted balance | | |
| | | | |
| | **Implement in `balance-card.tsx`:** | `frontend` | |
| | — Add horizontal bar below the `$X.XX` display (inside `CardContent`, below the flex row) | | |
| | — Outer container: `div` with gray background, rounded corners, fixed height (~8px), full width | | |
| | — Inner fill: `div` with inline `style={{ width: \`${pct}%\` }}` where `pct = Math.min(100, (balance / 15) * 100)` | | |
| | — Color thresholds (same as existing `getBalanceColorClass()`): | | |
| | — Green (`bg-success`): balance > $1.00 | | |
| | — Amber (`bg-primary`): balance $0.10–$1.00 | | |
| | — Red (`bg-destructive`): balance < $0.10 | | |
| | — `aria-label` on outer div: e.g., `"Balance: $7.42"` | | |
| | — `data-testid="usage-bar"` for test targeting | | |
| | — Cap constant: `$15.00` hardcoded (largest default pack) | | |
| | | | |
| | **Run:** `cd frontend && npm test -- --run balance-card && npm run typecheck` | `commands` | |
| | **Done when:** All 14 tests pass (8 existing + 6 new). Bar renders with correct colors and width scaling. TypeScript clean. | | |
| 8 | **Phase 4 Gate** — Full backend + frontend + E2E tests, push | `phase-gate` | ⬜ |
| | **Run:** `cd backend && python -m pytest tests/ -v`. `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. `cd frontend && npx playwright test`. Push with SSH keep-alive: `GIT_SSH_COMMAND="ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=10" git push`. | | |
| | **Done when:** All tests pass. Pushed to remote. | | |

#### Phase 4 Notes

**Color reuse:** The balance card already has `getBalanceColorClass()` with green/amber/red thresholds. The usage bar should reuse this same function rather than duplicating the threshold logic.

**Cap value:** $15.00 is hardcoded to match the largest default pack. If a future admin creates a $25 pack, the bar would show >100% for balances between $15 and $25. This is acceptable for now — a dynamic cap (from packs API) is a future enhancement noted in REQ-023 §5.1.

---

## Phase 5: Documentation Errata (REQ-023 §6.1, §8.3)

**Status:** ⬜

*Apply v0.4 errata to REQ-021 per REQ-023 §6.1 table. Update plan status, CLAUDE.md, and backlog PBI #19.*

#### Workflow

| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-023 §6.1 (errata table with 12 changes). Read `docs/requirements/REQ-021_credits_billing.md`. |
| 🔧 **Edit** | Apply 12 text changes per §6.1 table. Update version header. |
| ✅ **Verify** | Review diff for accuracy. |
| 📝 **Commit** | `docs: apply USD-direct errata to REQ-021 and update plan status` |

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 9 | **Apply REQ-021 v0.4 errata + update plan/backlog** | | ⬜ |
| | **Read:** REQ-023 §6.1 (errata table — 12 section-level changes). `docs/requirements/REQ-021_credits_billing.md`. | `req-reader` | |
| | | | |
| | **Edit `docs/requirements/REQ-021_credits_billing.md`:** | | |
| | Apply all 12 changes from REQ-023 §6.1 table: | | |
| | — §1, §1.2: "Abstract credits" → "USD-direct" | | |
| | — §2.2: "Packs grant abstract credits" → "Packs grant USD balance (dollar-for-dollar)" | | |
| | — §2.5: "10,000 credits" → "$0.10 (signup_grant_cents)" | | |
| | — §3.1, §3.3: Update dependency on #19 | | |
| | — §4.3: `credit_packs.credit_amount` → `funding_packs.grant_cents`, `CreditPack*` → `FundingPack*` | | |
| | — §5.1: Pack definitions $5/50K, $15/175K, $40/500K → $5/$10/$15 dollar-for-dollar | | |
| | — §6.7, §6.3: "Abstract credits", column renames pending → USD cents via `grant_cents` | | |
| | — §7.1: GET /packs response `credit_display` → `amount_display`, `grant_cents` field | | |
| | — §7.3: GET /purchases response `credit_display` → `amount_display` | | |
| | — §9.1: Credits page "125,430 credits" → "$12.54" | | |
| | — §15 Q#4: "Abstract credits" → "USD-direct (see REQ-023 §2.1)" | | |
| | — Update version header to v0.4, add change log entry | | |
| | | | |
| | **Update `docs/plan/req023_usd_direct_billing_plan.md`:** Status → ✅ Complete | | |
| | **Update `CLAUDE.md`:** Current Status section — note REQ-023 complete | | |
| | **Update `docs/backlog/feature-backlog.md`:** PBI #19 → completed | | |
| | | | |
| | **Done when:** REQ-021 reflects USD-direct billing terminology. Plan, CLAUDE.md, and backlog updated. | | |
| 10 | **Phase 5 Gate (Final)** — Full suite verification + push | `phase-gate` | ⬜ |
| | **Run:** `cd backend && python -m pytest tests/ -v`. `cd frontend && npm test -- --run && npm run typecheck && npm run lint`. `cd frontend && npx playwright test`. Push with SSH keep-alive (docs-only changes can use `--no-verify` per memory lesson). | | |
| | **Done when:** All tests still pass (no regressions from doc changes). Pushed to remote. | | |

---

## Verification Checklist (after all phases)

1. ✅ `alembic upgrade head` runs cleanly — `funding_packs` table with `grant_cents` column
2. ✅ `alembic downgrade -1` then `upgrade head` — round-trip clean
3. ✅ `cd backend && python -m pytest tests/ -v` — all pass
4. ✅ `cd frontend && npm test -- --run` — all pass
5. ✅ `cd frontend && npm run typecheck` — zero errors
6. ✅ `cd frontend && npm run lint` — zero errors
7. ✅ E2E admin tests pass with `/funding-packs` routes
8. ✅ Balance card shows usage bar with green/amber/red thresholds
9. ✅ `grep -rn "CreditPack\|credit-packs" backend/app/ frontend/src/` — zero results
10. ✅ `grep -rn "credit_amount" backend/app/ frontend/src/` — zero results (excluding `credit_transactions`-related code and `test_metering_integration.py`)
11. ✅ REQ-021 updated with USD-direct errata (v0.4)

---

## Task Count Summary

| Phase | REQ Sections | Code Tasks | Gates | Total |
|-------|-------------|------------|-------|-------|
| 1 — Database Migration | §4.1, §7.6 | 1 | 1 | 2 |
| 2 — Backend Renames | §4.2–§4.5, §7.2 | 1 | 1 | 2 |
| 3 — Frontend Renames | §2.5, §5.2, §7.3–§7.4 | 1 | 1 | 2 |
| 4 — Usage Bar | §5.1, §7.5 | 1 | 1 | 2 |
| 5 — Documentation Errata | §6.1, §8.3 | 1 | 1 | 2 |
| **Total** | | **5** | **5** | **10** |

---

## Critical Files Reference

| File | Role |
|------|------|
| `docs/requirements/REQ-023_usd_direct_billing.md` | Full specification (9 sections, ~476 lines) |
| `backend/migrations/versions/021_admin_pricing.py` | Previous migration (revision chain reference) |
| `backend/app/models/admin_config.py` | `CreditPack` → `FundingPack` ORM model |
| `backend/app/schemas/admin.py` | `CreditPack*` → `FundingPack*` Pydantic schemas |
| `backend/app/services/admin_management_service.py` | Pack CRUD service |
| `backend/app/api/v1/admin.py` | `/credit-packs` → `/funding-packs` routes |
| `backend/app/services/admin_config_service.py` | Config key docstring update |
| `frontend/src/types/admin.ts` | `CreditPack*` → `FundingPack*` TS types |
| `frontend/src/lib/api/admin.ts` | Frontend API client URL updates |
| `frontend/src/components/usage/balance-card.tsx` | Usage bar addition |
| `docs/requirements/REQ-021_credits_billing.md` | Errata target (12 changes) |

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-02 | 0.1 | Initial draft — inline plan from user message |
| 2026-03-02 | 0.2 | Corrected plan after 3-way audit (REQ cross-reference, file spot-check, prior plan pattern comparison). Changes: (1) Added Phase 5 for REQ-021 errata (REQ-023 §8.3, §6.1) — 12 text changes missing from original plan. (2) Added 2 integration tests (REQ-023 §7.6) to Phase 1 §1. (3) Raised context budget from ≤35k to ≤40k to match prior plan precedent for 10-file subtasks. (4) Added explicit "How to Use" rationale for 10-file subtask sizing. (5) Added change log, critical files reference, and task count summary for template consistency. (6) Clarified raw SQL test fix scope (test names + column names + table names). |
