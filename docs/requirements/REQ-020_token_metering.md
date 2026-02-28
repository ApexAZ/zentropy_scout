# REQ-020: Token Metering & Usage Tracking

**Status:** Not Started
**Version:** 0.2
**PRD Reference:** §6 Technical Architecture
**Last Updated:** 2026-02-27

---

## 1. Overview

This document specifies the system for metering every LLM and embedding API call, calculating costs with a configurable margin, maintaining per-user dollar balances, and gating access when a user's balance is exhausted.

### 1.1 Problem Statement

Zentropy Scout makes LLM calls (Claude, OpenAI, Gemini) and embedding calls (OpenAI) on behalf of users. Each call has a real cost to the provider. Without metering:

1. **No cost visibility** — No way to know how much each user consumes
2. **No billing foundation** — Cannot charge users without usage data
3. **No abuse protection** — A single user could run up unlimited provider costs
4. **No cost optimization** — Cannot identify expensive operations or optimize routing
5. **No margin enforcement** — Cannot layer business margin on top of raw provider costs

The provider abstraction layer (REQ-009) already returns `input_tokens` and `output_tokens` on every `LLMResponse`, but this data is currently discarded after each call.

### 1.2 Solution

A metering layer that:
1. **Records** every LLM/embedding call with token counts, model, provider, task type, and calculated cost
2. **Calculates** the user-facing cost by applying a margin multiplier to the raw provider cost
3. **Maintains** a per-user USD balance via an append-only credit ledger
4. **Gates** LLM access by checking the user's balance before each call (402 Payment Required when exhausted)
5. **Exposes** usage data and balance via API endpoints and a frontend display

### 1.3 Scope

| In Scope | Out of Scope |
|----------|-------------|
| LLM call metering (all 3 providers) | Stripe integration (see REQ-021) |
| Embedding call metering | Subscription/recurring billing |
| Per-call cost calculation with margin | Admin dashboard |
| Append-only credit ledger | Usage-based pricing tiers |
| Cached balance on users table | Per-model rate limiting (separate from balance gating) |
| Balance check before LLM calls (402) | Real-time cost alerts / push notifications |
| Usage API endpoints (balance, summary, history) | Usage export (CSV/PDF) |
| Frontend balance display in nav bar | Cost forecasting / projections |
| Frontend usage breakdown page | |

---

## 2. Design Decisions

### 2.1 Metering Hook Placement

**Where should usage be recorded?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Inside each service (scatter calls) | — | Requires every service to remember to record. Easy to miss a call site. |
| B. Metered provider wrapper (proxy pattern) | ✅ | Single point of interception. Wraps `LLMProvider.complete()` and `stream()`. Every call automatically recorded regardless of which service initiates it. |
| C. Middleware / event hook | — | LLM calls happen deep in services, not at HTTP boundary. Middleware can't intercept them. |

**Chosen: Option B — Metered Provider Wrapper**

A `MeteredLLMProvider` class wraps the real provider. The factory returns the metered wrapper instead of the raw adapter. Recording happens after a successful call returns, using the token counts from `LLMResponse`.

```python
# Conceptual — not final implementation
class MeteredLLMProvider(LLMProvider):
    """Wraps a real provider, records usage after each call."""

    def __init__(self, inner: LLMProvider, db: AsyncSession, user_id: UUID):
        self._inner = inner
        self._db = db
        self._user_id = user_id

    async def complete(self, *, messages, task, **kwargs) -> LLMResponse:
        response = await self._inner.complete(messages=messages, task=task, **kwargs)
        await self._record_usage(task, response)
        return response
```

**Prerequisites:**
- The `LLMProvider` base class must expose a `provider_name` abstract property returning `"claude"`, `"openai"`, or `"gemini"`. Each adapter must implement it. The `EmbeddingProvider` base class must similarly expose `provider_name`. This is required because the metering wrapper needs to record which provider handled each call, and there is currently no attribute on the provider interface for this.

```python
# Add to LLMProvider base class (backend/app/providers/llm/base.py)
@property
@abstractmethod
def provider_name(self) -> str:
    """Return the provider identifier ('claude', 'openai', 'gemini')."""
    ...

# Each adapter implements it:
# ClaudeAdapter:  provider_name -> "claude"
# OpenAIAdapter:  provider_name -> "openai"
# GeminiAdapter:  provider_name -> "gemini"
```

**Factory Change:** The factory function `get_llm_provider()` currently returns a singleton provider with no user context. With metering, it needs access to the user ID and a DB session. The approach:

1. The existing `get_llm_provider()` remains unchanged — it returns the raw singleton adapter.
2. A new FastAPI dependency `get_metered_provider` wraps the singleton with `MeteredLLMProvider`:

```python
# backend/app/api/deps.py — new dependency
async def get_metered_provider(
    user_id: CurrentUserId,
    db: DbSession,
) -> LLMProvider:
    """Return a metered LLM provider scoped to the current user."""
    if not settings.metering_enabled:
        return get_llm_provider()
    inner = get_llm_provider()
    metering_service = MeteringService(db)
    return MeteredLLMProvider(inner, metering_service, user_id)

MeteredProvider = Annotated[LLMProvider, Depends(get_metered_provider)]
```

3. Endpoints that trigger LLM calls inject `MeteredProvider` and pass it to their service functions.
4. Services that currently call `factory.get_llm_provider()` directly must be refactored to accept an `LLMProvider` parameter instead. This decouples them from the factory and makes them testable with either raw or metered providers.

**Call sites requiring refactoring** (7 total):
- `backend/app/services/job_extraction.py` — `extract_job_data()`
- `backend/app/services/cover_letter_generation.py` — `generate_cover_letter()`
- `backend/app/services/job_scoring_service.py` — `generate_score_rationale()`
- `backend/app/services/ghost_detection.py` — `assess_vagueness()`
- `backend/app/services/content_utils.py` — `extract_keywords()`, `extract_skills_from_text()`
- `backend/app/services/resume_parsing_service.py` — `parse_resume()`
- `backend/app/api/v1/onboarding.py` — resume parsing endpoint

### 2.2 Balance Tracking Strategy

**How should the user's balance be tracked?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Compute from ledger on every request | — | Accurate but slow at scale (full SUM on every LLM call). Becomes a bottleneck. |
| B. Cached balance column + append-only ledger | ✅ | Fast reads from `users.balance_usd`. Ledger is the source of truth for audit/reconciliation. Atomic debit prevents overdraft. |
| C. Separate balance table | — | Adds a join. No advantage over a column on `users` for a single balance value. |

**Chosen: Option B — Cached Balance + Ledger**

- `users.balance_usd` — `NUMERIC(10,6)` column. Fast reads. Updated atomically on every transaction.
- `credit_transactions` — Append-only ledger. Every credit (purchase, admin grant, refund) and debit (LLM usage) is a row. Signs: positive = credit, negative = debit.
- **Atomic debit:** `UPDATE users SET balance_usd = balance_usd - :cost WHERE id = :user_id AND balance_usd >= :cost`. Returns 0 rows updated if insufficient balance — no overdraft possible.
- **Reconciliation:** `SUM(credit_transactions.amount) WHERE user_id = :id` should equal `users.balance_usd`. A background check can detect drift.

### 2.3 Usage Gating

**How should access be denied when balance is exhausted?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. FastAPI dependency (like auth) | ✅ | Clean separation. Endpoints that trigger LLM calls declare the dependency. Returns 402 before any work starts. |
| B. Check inside metered provider wrapper | — | Too late — request processing has already started. Wastes compute. |
| C. Middleware on all requests | — | Most requests don't trigger LLM calls. Unnecessary overhead. |

**Chosen: Option A — FastAPI Dependency**

A `require_sufficient_balance` dependency checks `users.balance_usd > 0` (or a configurable minimum threshold). Injected on endpoints that trigger LLM calls. Returns `402 Payment Required` with a structured error response.

Endpoints that currently exist and trigger LLM calls:
- `POST /api/v1/onboarding/resume-parse` (resume parsing via LLM)
- `POST /api/v1/job-postings/ingest` (job extraction via LLM)

Planned endpoints (apply balance check when implemented):
- `POST /api/v1/resumes/generate` (resume tailoring via LLM — not yet implemented)
- `POST /api/v1/cover-letters/generate` (cover letter generation via LLM — not yet implemented)
- `POST /api/v1/chat/messages` (chat agent via LLM — not yet implemented)

**Note:** `POST /api/v1/job-postings/ingest/confirm` does NOT trigger LLM calls — it creates the job posting from a preview token. The LLM call happens during `/ingest`, not `/ingest/confirm`.

### 2.4 Pricing Model

**How should costs be calculated?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. Hardcoded pricing table in code | ✅ | Simple, explicit, version-controlled. Provider pricing changes rarely. Margin multiplier is configurable via env var. |
| B. Pricing table in database | — | Over-engineering for MVP. No admin UI to manage it. Adds complexity without benefit. |
| C. Real-time pricing API | — | Providers don't offer real-time pricing APIs. Not feasible. |

**Chosen: Option A — Hardcoded Pricing Table**

A Python dict maps `(provider, model)` → `price_per_1k_input_tokens` and `price_per_1k_output_tokens`. Updated when providers change pricing (requires code deploy). Follows the existing pattern in `embedding_cost.py`.

The margin multiplier is a single env var (`METERING_MARGIN_MULTIPLIER`, default `1.3` = 30% margin) applied to the raw cost to produce the user-facing cost.

### 2.5 Credit Unit

**What unit does the user see?**

| Option | Chosen? | Rationale |
|--------|---------|-----------|
| A. US Dollars (USD) | ✅ | Transparent, intuitive, no conversion math. Users see "$4.23 remaining". |
| B. Abstract credits | — | Adds indirection. Users don't know what a "credit" costs. |
| C. Tokens | — | Confusing for non-technical users. Different models have different token costs. |

**Chosen: Option A — USD**

All balances, costs, and transactions are denominated in US Dollars. The `balance_usd` column and all API responses show dollar amounts with 6 decimal places (e.g., `4.230000`). Six decimal places accommodate sub-cent costs per LLM call (e.g., a Haiku extraction costs ~$0.000200) and ensure no rounding mismatches between tables. The frontend displays 2 decimal places (`$4.23`) for user readability.

---

## 3. Dependencies

### 3.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-005 Database Schema v0.10 | Schema | `users` table to extend with `balance_usd` |
| REQ-006 API Contract v0.8 | Integration | Response envelope pattern (§7), error codes (§8), endpoint conventions (§5) |
| REQ-009 Provider Abstraction v0.2 | Integration | `LLMResponse` (§4.3), `TaskType` enum (§4.2), factory pattern (§5), embedding provider interface |
| REQ-013 Authentication v0.1 | Integration | `get_current_user_id()` dependency for user identification |
| REQ-014 Multi-Tenant v0.1 | Integration | Row-level isolation via `user_id` FK |

### 3.2 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-021 Credits & Billing | Foundation | Stripe purchases credit the ledger defined here |
| REQ-012 Frontend Application | Integration | Balance display, usage page |

---

## 4. Database Schema

### 4.1 Users Table Extension

Add one column to the existing `users` table:

```sql
ALTER TABLE users ADD COLUMN balance_usd NUMERIC(10,6) NOT NULL DEFAULT 0.000000;
```

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `balance_usd` | `NUMERIC(10,6)` | NOT NULL | `0.000000` | Cached balance in USD. Source of truth is `credit_transactions`. |

**Why 6 decimal places?** All three monetary columns (`llm_usage_records.billed_cost_usd`, `credit_transactions.amount_usd`, `users.balance_usd`) use `NUMERIC(10,6)` for consistency. Sub-cent precision is needed because individual LLM calls can cost fractions of a cent (e.g., a Haiku extraction costs ~$0.000200). Using the same precision everywhere eliminates rounding mismatches between the ledger and cached balance.

### 4.2 LLM Usage Records

Records every individual LLM and embedding API call.

```sql
CREATE TABLE llm_usage_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider        VARCHAR(20) NOT NULL,   -- 'claude', 'openai', 'gemini'
    model           VARCHAR(100) NOT NULL,  -- 'claude-3-5-haiku-20241022', etc.
    task_type       VARCHAR(50) NOT NULL,   -- TaskType enum value
    input_tokens    INTEGER NOT NULL,
    output_tokens   INTEGER NOT NULL,
    raw_cost_usd    NUMERIC(10,6) NOT NULL, -- Provider cost before margin
    billed_cost_usd NUMERIC(10,6) NOT NULL, -- User-facing cost after margin
    margin_multiplier NUMERIC(4,2) NOT NULL, -- Margin at time of call (e.g., 1.30)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | Primary key |
| `user_id` | `UUID FK → users` | Who made the call |
| `provider` | `VARCHAR(20)` | Provider name (claude, openai, gemini) |
| `model` | `VARCHAR(100)` | Exact model identifier used |
| `task_type` | `VARCHAR(50)` | `TaskType` enum value (extraction, cover_letter, etc.) |
| `input_tokens` | `INTEGER` | Input/prompt tokens consumed |
| `output_tokens` | `INTEGER` | Output/completion tokens consumed |
| `raw_cost_usd` | `NUMERIC(10,6)` | Raw provider cost (6 decimal places for sub-cent precision) |
| `billed_cost_usd` | `NUMERIC(10,6)` | Cost charged to user (raw × margin) |
| `margin_multiplier` | `NUMERIC(4,2)` | Margin multiplier at time of recording (immutable snapshot) |
| `created_at` | `TIMESTAMPTZ` | When the call was made |

**Why snapshot the margin multiplier?** If the margin changes (env var update), historical records should reflect what was actually charged, not the current margin. This makes the ledger reconcilable.

**Immutability:** Both `llm_usage_records` and `credit_transactions` are append-only. Records are never updated or deleted. Neither table uses `TimestampMixin` (no `updated_at` column needed). Only `created_at` is present, set once on insert.

### 4.3 Credit Transactions (Ledger)

Append-only ledger of all balance changes. Positive amounts = credits, negative amounts = debits.

```sql
CREATE TABLE credit_transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount_usd      NUMERIC(10,6) NOT NULL, -- Positive = credit, negative = debit
    transaction_type VARCHAR(20) NOT NULL,  -- 'purchase', 'usage_debit', 'admin_grant', 'refund'
    reference_id    UUID,                   -- FK to llm_usage_records (for debits) or Stripe session (for purchases)
    description     VARCHAR(255),           -- Human-readable (e.g., "Stripe purchase: Standard Pack")
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID` | Primary key |
| `user_id` | `UUID FK → users` | Account owner |
| `amount_usd` | `NUMERIC(10,6)` | Signed amount. `+15.000000` for purchase, `-0.003315` for usage |
| `transaction_type` | `VARCHAR(20)` | Enum: `purchase`, `usage_debit`, `admin_grant`, `refund` |
| `reference_id` | `UUID` | Links to source: `llm_usage_records.id` for debits, Stripe checkout session ID for purchases |
| `description` | `VARCHAR(255)` | Human-readable description |
| `created_at` | `TIMESTAMPTZ` | Transaction timestamp |

**Invariant:** `SUM(credit_transactions.amount_usd) WHERE user_id = X` should equal `users.balance_usd` for user X. A reconciliation query can verify this. All three monetary columns use `NUMERIC(10,6)` — no rounding mismatch is possible.

### 4.4 Indexes

```sql
-- Usage records: query by user, ordered by time (dashboard)
CREATE INDEX ix_llm_usage_records_user_created
    ON llm_usage_records (user_id, created_at DESC);

-- Usage records: aggregate by task type (cost breakdown)
CREATE INDEX ix_llm_usage_records_user_task
    ON llm_usage_records (user_id, task_type);

-- Credit transactions: query by user, ordered by time (transaction history)
CREATE INDEX ix_credit_transactions_user_created
    ON credit_transactions (user_id, created_at DESC);

-- Credit transactions: reconciliation by type
CREATE INDEX ix_credit_transactions_user_type
    ON credit_transactions (user_id, transaction_type);
```

### 4.5 Migration Notes

- **Upgrade:** Create `llm_usage_records` and `credit_transactions` tables, add `balance_usd` column to `users`.
- **Downgrade:** Drop both tables, remove `balance_usd` column from `users`.
- Existing users will have `balance_usd = 0.000000` after migration (no free credits by default).

---

## 5. Cost Calculation

### 5.1 LLM Pricing Table

Prices as of 2026-02-27 (USD per 1,000 tokens):

| Provider | Model | Input / 1K | Output / 1K | Typical Task |
|----------|-------|-----------|-------------|--------------|
| Claude | claude-3-5-haiku-20241022 | $0.0008 | $0.004 | Extraction, ghost detection |
| Claude | claude-3-5-sonnet-20241022 | $0.003 | $0.015 | Cover letters, resume tailoring |
| OpenAI | gpt-4o-mini | $0.00015 | $0.0006 | Extraction |
| OpenAI | gpt-4o | $0.0025 | $0.01 | Quality tasks |
| Gemini | gemini-2.0-flash | $0.0001 | $0.0004 | Extraction, quality |
| Gemini | gemini-2.5-flash | $0.00015 | $0.0035 | Resume parsing |

### 5.2 Embedding Pricing Table

Reuse existing table from `embedding_cost.py`:

| Provider | Model | Price / 1K Tokens |
|----------|-------|--------------------|
| OpenAI | text-embedding-3-small | $0.00002 |
| OpenAI | text-embedding-3-large | $0.00013 |

### 5.3 Margin Multiplier

```bash
# Environment variable (default: 1.30 = 30% margin)
METERING_MARGIN_MULTIPLIER=1.30
```

The margin multiplier is applied uniformly to all providers and models. Per-model margins add complexity without clear benefit at MVP scale.

### 5.4 Cost Formula

```
raw_cost = (input_tokens / 1000 × input_price_per_1k) + (output_tokens / 1000 × output_price_per_1k)
billed_cost = raw_cost × margin_multiplier
```

**Example:** A cover letter generation call using Claude Sonnet:
- Input: 2,500 tokens × ($0.003 / 1K) = $0.0075
- Output: 1,200 tokens × ($0.015 / 1K) = $0.0180
- Raw cost: $0.0255
- Billed cost: $0.0255 × 1.30 = $0.03315

---

## 6. Metered Provider Wrapper

### 6.1 New Files

| File | Purpose |
|------|---------|
| `backend/app/providers/metered_provider.py` | `MeteredLLMProvider` and `MeteredEmbeddingProvider` wrapper classes |
| `backend/app/services/metering_service.py` | Cost calculation, usage recording, balance operations |
| `backend/app/repositories/usage_repository.py` | DB access for `llm_usage_records` |
| `backend/app/repositories/credit_repository.py` | DB access for `credit_transactions` and balance operations |
| `backend/app/models/usage.py` | SQLAlchemy models: `LLMUsageRecord`, `CreditTransaction` |
| `backend/app/schemas/usage.py` | Pydantic schemas for API request/response |
| `backend/app/api/v1/usage.py` | API endpoints |

**Router registration:** Add to `backend/app/api/v1/router.py`:
```python
from app.api.v1 import usage
router.include_router(usage.router, prefix="/usage", tags=["usage"])
```

### 6.2 MeteredLLMProvider Interface

```python
class MeteredLLMProvider(LLMProvider):
    """Proxy that records token usage and debits the user's balance."""

    def __init__(
        self,
        inner: LLMProvider,
        metering_service: MeteringService,
        user_id: UUID,
    ) -> None: ...

    async def complete(
        self,
        *,
        messages: list[LLMMessage],
        task: TaskType,
        **kwargs,
    ) -> LLMResponse:
        """Call inner provider, then record usage and debit balance."""
        response = await self._inner.complete(messages=messages, task=task, **kwargs)
        await self._metering_service.record_and_debit(
            user_id=self._user_id,
            provider=self._inner.provider_name,
            model=response.model,
            task_type=task,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
        return response

    async def stream(self, *, messages, task, **kwargs):
        """Stream from inner provider. Record usage from final accumulated counts.

        NOTE: As of 2026-02-27, stream() is not called anywhere in production
        code. All LLM calls use complete(). Streaming metering is deferred
        until an endpoint actually uses it (likely the chat agent). When
        implemented, the approach will be:

        1. Yield text chunks from the inner provider's stream unchanged.
        2. After the stream completes, retrieve final token counts from the
           provider's stream context (e.g., Claude's stream.get_final_message(),
           OpenAI's stream_options={"include_usage": True}).
        3. Record usage and debit balance using the same logic as complete().

        This will require changes to the base LLMProvider.stream() signature
        to return a richer object that exposes final token counts after
        iteration completes. That change is deferred to avoid modifying
        an interface that is not yet used.
        """
        async for chunk in self._inner.stream(messages=messages, task=task, **kwargs):
            yield chunk
        # TODO: capture final token counts and call self._metering_service.record_and_debit()
        # when stream() is first used in production.

    def get_model_for_task(self, task: TaskType) -> str:
        return self._inner.get_model_for_task(task)
```

### 6.3 Recording Logic

After a successful LLM call:

1. Look up pricing for `(provider, model)` in the pricing table
2. Calculate `raw_cost_usd` using the cost formula (§5.4)
3. Apply `margin_multiplier` to get `billed_cost_usd`
4. Insert row into `llm_usage_records`
5. Insert debit row into `credit_transactions` (amount = `-billed_cost_usd`, type = `usage_debit`, reference = usage record ID)
6. Atomically debit `users.balance_usd`: `UPDATE users SET balance_usd = balance_usd - :billed_cost WHERE id = :user_id AND balance_usd >= :billed_cost`
7. If the atomic debit returns 0 rows (insufficient balance after the call completed), log a warning but do NOT fail the request — the user already received the response. The balance will go slightly negative. The gating dependency (§7) prevents this in normal flow; this is a race condition safeguard.

### 6.4 Internal (Non-Endpoint) LLM Calls

Several services make LLM calls that are not directly exposed as HTTP endpoints:

| Service | Method | Task Type | Triggered By |
|---------|--------|-----------|-------------|
| `job_scoring_service.py` | `generate_score_rationale()` | `SCORE_RATIONALE` | Job scoring pipeline (internal) |
| `ghost_detection.py` | `assess_vagueness()` | `GHOST_DETECTION` | Ghost detection pipeline (internal) |
| `content_utils.py` | `extract_keywords()` | `EXTRACTION` | Cover letter / resume generation |
| `content_utils.py` | `extract_skills_from_text()` | `SKILL_EXTRACTION` | Cover letter / resume generation |

**Metering behavior:** These calls ARE metered (recorded and debited) because they flow through the `MeteredLLMProvider` wrapper like any other call. The wrapper intercepts all `complete()` calls regardless of whether they originate from an HTTP endpoint or an internal pipeline.

**Gating behavior:** These calls are NOT gated by the `require_sufficient_balance` dependency because they don't have their own HTTP endpoints. Instead, gating happens at the endpoint that initiates the pipeline. For example:
- `POST /api/v1/job-postings/ingest` → triggers extraction → which may trigger scoring → which may trigger ghost detection. The balance check at `/ingest` gates the entire chain.
- If a user's balance is exhausted mid-pipeline (multiple LLM calls in one request), subsequent calls within the same request are still allowed to complete. The atomic debit (§6.3 step 7) handles this edge case by allowing a slight negative balance.

### 6.5 Metered Embedding Provider

Embedding calls use a separate interface (`EmbeddingProvider.embed()`) and require their own metered wrapper.

```python
class MeteredEmbeddingProvider(EmbeddingProvider):
    """Proxy that records embedding usage and debits the user's balance."""

    def __init__(
        self,
        inner: EmbeddingProvider,
        metering_service: MeteringService,
        user_id: UUID,
    ) -> None: ...

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Call inner provider, then record usage and debit balance."""
        result = await self._inner.embed(texts=texts)
        await self._metering_service.record_and_debit(
            user_id=self._user_id,
            provider=self._inner.provider_name,
            model=result.model,
            task_type="embedding",
            input_tokens=result.total_tokens,
            output_tokens=0,  # Embeddings have no output tokens
        )
        return result
```

**Recording in `llm_usage_records`:** Embedding calls are stored in the same table as LLM calls:
- `task_type` = `"embedding"`
- `output_tokens` = `0`
- `input_tokens` = `EmbeddingResult.total_tokens`
- Pricing uses the embedding pricing table (§5.2)

**Chunked batch edge case:** The OpenAI embedding adapter returns `total_tokens = -1` when requests exceed 2048 texts and are chunked into multiple batches. The metered wrapper must handle this:
- If `total_tokens == -1`, estimate tokens using `len(text) / 4` per text (rough approximation) and log a warning.
- Alternatively, the embedding adapter should be fixed to sum token counts across batches (preferred — this is a provider-layer bug).

**Dependency injection:** Follows the same pattern as the LLM provider:

```python
# backend/app/api/deps.py
async def get_metered_embedding_provider(
    user_id: CurrentUserId,
    db: DbSession,
) -> EmbeddingProvider:
    if not settings.metering_enabled:
        return get_embedding_provider()
    inner = get_embedding_provider()
    metering_service = MeteringService(db)
    return MeteredEmbeddingProvider(inner, metering_service, user_id)

MeteredEmbedding = Annotated[EmbeddingProvider, Depends(get_metered_embedding_provider)]
```

**Embedding call sites requiring refactoring:**
- `backend/app/services/job_scoring_service.py` — `compute_embedding_scores()`
- `backend/app/services/batch_scoring.py` — batch embedding generation

### 6.6 Error Handling

| Scenario | Behavior |
|----------|----------|
| LLM call succeeds | Record usage, debit balance |
| LLM call fails (provider error) | Do NOT record usage (no tokens consumed) |
| LLM call succeeds but recording fails (DB error) | Log error, return response to user. Usage is lost but user isn't impacted. Reconciliation will detect drift. |
| Unknown model in pricing table | Use a fallback "unknown model" price (highest tier for the provider). Log warning. |

---

## 7. Usage Gating

### 7.1 Balance Check Dependency

```python
async def require_sufficient_balance(
    user_id: CurrentUserId,
    db: DbSession,
) -> None:
    """FastAPI dependency. Raises 402 if user has insufficient balance."""
    balance = await get_user_balance(db, user_id)
    if balance <= Decimal("0.000000"):
        raise InsufficientBalanceError(balance=balance)
```

### 7.2 Insufficient Balance Response

HTTP 402 Payment Required:

```json
{
    "error": {
        "code": "INSUFFICIENT_BALANCE",
        "message": "Your balance is $0.00. Please add funds to continue.",
        "details": [
            {
                "balance_usd": "0.000000",
                "minimum_required": "0.000001"
            }
        ]
    }
}
```

### 7.3 Minimum Balance Threshold

```bash
# Environment variable (default: 0.00 — any positive balance allows calls)
METERING_MINIMUM_BALANCE=0.00
```

The gating check is `balance_usd > METERING_MINIMUM_BALANCE`. Setting this to e.g., `0.05` would require users to maintain at least $0.05 before making calls, providing a buffer against concurrent request race conditions.

### 7.4 Endpoints Requiring Balance Check

These endpoints trigger LLM calls and must declare the `require_sufficient_balance` dependency:

**Currently implemented:**

| Endpoint | LLM Call |
|----------|----------|
| `POST /api/v1/onboarding/resume-parse` | Resume parsing (Gemini 2.5 Flash) |
| `POST /api/v1/job-postings/ingest` | Job extraction (task-routed model) |

**Planned (apply when implemented):**

| Endpoint | LLM Call |
|----------|----------|
| `POST /api/v1/resumes/generate` | Resume tailoring |
| `POST /api/v1/cover-letters/generate` | Cover letter generation |
| `POST /api/v1/chat/messages` | Chat agent |

---

## 8. API Endpoints

All endpoints require authentication (`CurrentUserId` dependency). All follow REQ-006 response envelope conventions.

### 8.1 GET /api/v1/usage/balance

Returns the user's current balance.

**Response:** `200 OK`
```json
{
    "data": {
        "balance_usd": "4.230000",
        "as_of": "2026-02-27T15:30:00Z"
    }
}
```

### 8.2 GET /api/v1/usage/summary

Returns aggregated usage for a time period. Default: current calendar month.

**Query Parameters:**
| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `period_start` | ISO 8601 date | First of current month | Start of period |
| `period_end` | ISO 8601 date | Today | End of period |

**Response:** `200 OK`
```json
{
    "data": {
        "period_start": "2026-02-01",
        "period_end": "2026-02-27",
        "total_calls": 142,
        "total_input_tokens": 385000,
        "total_output_tokens": 127000,
        "total_raw_cost_usd": "1.845000",
        "total_billed_cost_usd": "2.398500",
        "by_task_type": [
            {
                "task_type": "extraction",
                "call_count": 95,
                "input_tokens": 190000,
                "output_tokens": 47500,
                "billed_cost_usd": "0.312000"
            },
            {
                "task_type": "cover_letter",
                "call_count": 12,
                "input_tokens": 30000,
                "output_tokens": 14400,
                "billed_cost_usd": "0.858000"
            }
        ],
        "by_provider": [
            {
                "provider": "claude",
                "call_count": 120,
                "billed_cost_usd": "2.100000"
            },
            {
                "provider": "gemini",
                "call_count": 22,
                "billed_cost_usd": "0.298500"
            }
        ]
    }
}
```

### 8.3 GET /api/v1/usage/history

Returns paginated list of individual usage records.

**Query Parameters:**
| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 50 | Items per page (max 100) |
| `task_type` | string | — | Filter by task type |
| `provider` | string | — | Filter by provider |

**Response:** `200 OK`
```json
{
    "data": [
        {
            "id": "a1b2c3d4-...",
            "provider": "claude",
            "model": "claude-3-5-haiku-20241022",
            "task_type": "extraction",
            "input_tokens": 1200,
            "output_tokens": 450,
            "billed_cost_usd": "0.003100",
            "created_at": "2026-02-27T14:22:00Z"
        }
    ],
    "meta": {
        "page": 1,
        "per_page": 50,
        "total": 142,
        "total_pages": 3
    }
}
```

### 8.4 GET /api/v1/usage/transactions

Returns paginated credit transaction history (purchases, debits, grants, refunds).

**Query Parameters:**
| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `page` | integer | 1 | Page number |
| `per_page` | integer | 50 | Items per page (max 100) |
| `type` | string | — | Filter: `purchase`, `usage_debit`, `admin_grant`, `refund` |

**Response:** `200 OK`
```json
{
    "data": [
        {
            "id": "e5f6g7h8-...",
            "amount_usd": "15.000000",
            "transaction_type": "purchase",
            "description": "Standard Credit Pack",
            "created_at": "2026-02-25T10:00:00Z"
        },
        {
            "id": "i9j0k1l2-...",
            "amount_usd": "-0.033150",
            "transaction_type": "usage_debit",
            "description": "Cover letter generation (Claude Sonnet)",
            "created_at": "2026-02-27T14:22:00Z"
        }
    ],
    "meta": {
        "page": 1,
        "per_page": 50,
        "total": 87,
        "total_pages": 2
    }
}
```

---

## 9. Frontend

### 9.1 Balance Display (Navigation Bar)

A persistent balance indicator in the top navigation bar showing the user's current balance:

- **Format:** `$X.XX` (2 decimal places for display, even though backend stores 4)
- **Color coding:** Green when > $1.00, yellow when $0.10–$1.00, red when < $0.10
- **Click action:** Navigate to usage/credits page
- **Refresh:** Refetch balance after any LLM-triggering action completes (via TanStack Query invalidation of the `["usage", "balance"]` query key)

### 9.2 Usage Dashboard Page

**Route:** `/usage`

**Sections:**
1. **Current Balance** — large display, with "Add Funds" button (links to credits page, defined in REQ-021)
2. **Period Summary** — current month's total cost, call count, token usage
3. **Cost Breakdown by Task** — bar chart or table showing cost per task type
4. **Cost Breakdown by Provider** — pie chart or table showing cost per provider
5. **Recent Activity** — paginated table of individual usage records
6. **Transaction History** — paginated table of all credit transactions

### 9.3 Insufficient Balance State

When a 402 response is received:
- Show a toast/alert: "Insufficient balance. Please add funds to continue."
- Include a direct link to the credits/purchase page
- Do NOT retry the failed request automatically

---

## 10. Error Handling

### 10.1 Error Codes

| Code | HTTP Status | When |
|------|-------------|------|
| `INSUFFICIENT_BALANCE` | 402 | User's balance is too low to make LLM calls |
| `METERING_UNAVAILABLE` | 503 | Metering service is down (DB unreachable). Fail closed — do NOT allow unmetered calls. |
| `UNKNOWN_MODEL_PRICING` | 500 (internal, logged) | LLM returned a model not in the pricing table. Uses fallback price. |

### 10.2 Fail-Closed Policy

If the metering system is unavailable (DB connection error, etc.), LLM calls are **blocked**, not allowed through unmetered. This prevents unbilled usage. The 503 response tells the user to try again later.

---

## 11. Configuration

New environment variables:

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `METERING_ENABLED` | bool | `true` | Master switch. When `false`, no metering, no gating (for local dev). |
| `METERING_MARGIN_MULTIPLIER` | float | `1.30` | Applied to raw provider cost. 1.30 = 30% margin. |
| `METERING_MINIMUM_BALANCE` | float | `0.00` | Minimum balance required to make LLM calls. |

---

## 12. Testing Requirements

### 12.1 Unit Tests

| Test Area | Key Scenarios |
|-----------|---------------|
| Cost calculation | Correct cost for each (provider, model) pair; margin applied correctly; 0-token edge case |
| MeteredLLMProvider | Records usage after successful call; does NOT record on provider error; passes through kwargs correctly |
| Balance check dependency | Allows call when balance > 0; returns 402 when balance = 0; respects minimum threshold |
| Atomic debit | Debit succeeds when balance sufficient; debit fails (no overdraft) when insufficient |
| Usage repository | CRUD operations; pagination; filtering by task_type and provider |
| Credit transactions | Correct signs; reference_id links; description formatting |

### 12.2 Integration Tests

| Test Area | Key Scenarios |
|-----------|---------------|
| End-to-end metering | LLM call → usage recorded → balance debited → visible in API |
| Concurrent requests | Two simultaneous LLM calls don't overdraft via race condition |
| Reconciliation | `SUM(transactions)` matches `users.balance_usd` after multiple operations |

---

## 13. Open Questions

### Resolved Questions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Should embedding calls be metered identically to LLM calls, or tracked separately? | **Same table.** Use `llm_usage_records` with `task_type = 'embedding'` and `output_tokens = 0`. | Avoids a separate table for minimal cost data. See §6.5 for `MeteredEmbeddingProvider`. |
| 3 | Should the metering system support multiple currencies? | **USD only for MVP.** | Currency conversion is a post-MVP concern. No user-facing demand yet. |
| 4 | Should admin users bypass metering? | **Yes, via `METERING_ENABLED=false` env var.** No role-based bypass. | Admin/dev workflows use local environments where metering is disabled. Production has no admin role yet — adding one is out of scope. |
| 5 | Pricing table update cadence? | **Manual update via code deploy.** | Providers change pricing ~1-2x/year. An automated system is unnecessary at MVP scale. |
| 6 | Should streaming calls be metered differently? | **Deferred.** `stream()` is not used in production. | See §6.2 for the deferred approach. When streaming is used, the wrapper will capture final token counts from the provider's stream context. |

### Open Questions (Deferred to REQ-021)

| # | Question | Impact | Notes |
|---|----------|--------|-------|
| 2 | Should there be a free trial grant (e.g., $1.00 on signup)? | User experience | Belongs in REQ-021 (Credits & Billing). Metering itself doesn't define how credits are granted. |

---

## 14. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-27 | 0.1 | Initial draft |
| 2026-02-27 | 0.2 | Audit fixes: added `provider_name` prerequisite, specified factory injection pattern with 7 call sites, deferred streaming metering (unused), corrected endpoint list (2 exist, 3 planned, removed `/confirm`), added §6.4 internal LLM calls, added §6.5 `MeteredEmbeddingProvider`, aligned all monetary columns to `NUMERIC(10,6)`, resolved 5 of 6 open questions, split repositories, added router registration |
