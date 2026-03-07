# REQ-028: Cross-Provider Task Routing & Gemini Embeddings

**Status:** Draft
**Version:** 0.1
**PRD Reference:** Backlog #27 — Cross-Provider Task Routing (Admin-Configured)
**Last Updated:** 2026-03-07

---

## 1. Overview

### 1.1 Problem

The current LLM provider architecture (REQ-009) instantiates a **single provider** determined by the `LLM_PROVIDER` environment variable. The admin routing table (`task_routing_config`, REQ-022) already stores `provider` + `task_type` + `model` per row, but the factory only creates one adapter — so cross-provider routing does not work. Changing the active provider requires an application restart.

Additionally, embeddings are hardcoded to OpenAI (`text-embedding-3-small`, 1536 dimensions), requiring an OpenAI API key even when the admin uses Claude + Gemini as primary providers.

### 1.2 Solution

1. **Provider Registry** — A factory function creates adapters for **all providers with valid API keys**, returning a `dict[str, LLMProvider]` registry.
2. **Cross-Provider Dispatch** — `MeteredLLMProvider` accepts the registry and routes each task to the correct provider+model based on the DB routing table.
3. **Gemini Embeddings** — A new `GeminiEmbeddingAdapter` using `text-embedding-004` (768 dimensions) replaces OpenAI embeddings as default.
4. **BYOK Removal** — REQ-009 section 10 (BYOK Support) is marked "Not Planned" — superseded by REQ-023 centralized billing.

### 1.3 Scope

| In Scope | Out of Scope |
|----------|-------------|
| Provider registry factory (`get_llm_registry()`) | Changes to the 3 LLM adapter implementations |
| Cross-provider dispatch in MeteredLLMProvider | Changes to the 20+ service files (use TaskType abstraction) |
| Routing test endpoint (`POST /admin/routing/test`) | Changes to prompts (provider-agnostic) |
| Admin UI fixed routing table (10 rows) | Non-admin frontend pages |
| GeminiEmbeddingAdapter | Real-time provider hot-swapping (requires restart for new keys) |
| Vector dimension migration (1536 to 768) | Automatic failover between providers |
| Re-embedding script | BYOK (Bring Your Own Key) |
| BYOK removal (docs update) | |

### 1.4 Goals

| Goal | Description | Priority |
|------|-------------|----------|
| **Cross-provider routing** | Route different task types to different providers without restart | P0 |
| **Admin experimentation** | Admin can test routing configs with a test button | P0 |
| **Eliminate OpenAI dependency** | Switch default embeddings to Gemini, removing mandatory OpenAI key | P1 |
| **Usage visibility** | Track provider+model per request for cost/quality comparison | P0 |
| **Backward compatible** | Existing single-provider setups continue to work unchanged | P0 |

### 1.5 Non-Goals

| Non-Goal | Rationale |
|----------|-----------|
| BYOK (Bring Your Own Key) | Superseded by REQ-023 centralized billing; admin manages all keys |
| Automatic failover | Out of scope — admin can manually reroute if a provider is down |
| Provider priority/weighting | Simple 1:1 task-to-provider mapping; no load balancing |
| Hot-swapping API keys | Adding a new provider key requires restart to create the adapter |

---

## 2. Dependencies

### 2.1 This Document Depends On

| REQ | Section | What |
|-----|---------|------|
| REQ-009 | section 4.1, 4.3, 6.3 | LLMProvider interface, TaskType enum, singleton factory |
| REQ-020 | section 6.2, 6.5 | MeteredLLMProvider/MeteredEmbeddingProvider wrappers |
| REQ-022 | section 1.2, 2.2, 4.4 | Admin routing tables, model registry, routing lookup |
| REQ-023 | all | USD-direct billing (makes BYOK unnecessary) |

### 2.2 Others Depend On This

| REQ | Section | What |
|-----|---------|------|
| REQ-009 | section 10 | BYOK marked "Not Planned — Superseded by REQ-028" |

---

## 3. Provider Registry

### 3.1 Registry Factory

A new `get_llm_registry()` function in `factory.py` creates adapters for all providers with valid API keys and returns them as a dictionary.

```python
# LLM registry: provider name -> adapter instance
_llm_registry: dict[str, LLMProvider] | None = None

def get_llm_registry(config: ProviderConfig | None = None) -> dict[str, LLMProvider]:
    """Create adapters for all providers with valid API keys.

    Returns:
        dict mapping provider name to LLMProvider instance.
        Only providers with non-None API keys are included.

    Example:
        {"claude": ClaudeAdapter(...), "gemini": GeminiAdapter(...)}
        # OpenAI omitted if OPENAI_API_KEY not set
    """
    global _llm_registry
    if _llm_registry is None:
        if config is None:
            config = ProviderConfig.from_env()

        _llm_registry = {}
        if config.anthropic_api_key:
            _llm_registry["claude"] = ClaudeAdapter(config)
        if config.openai_api_key:
            _llm_registry["openai"] = OpenAIAdapter(config)
        if config.google_api_key:
            _llm_registry["gemini"] = GeminiAdapter(config)

    return _llm_registry
```

### 3.2 Backward Compatibility

`get_llm_provider()` continues to work unchanged — it creates the singleton for the `LLM_PROVIDER` env var. Non-metered paths (when `METERING_ENABLED=false`) still use the singleton directly.

### 3.3 Reset for Testing

`reset_providers()` must also clear `_llm_registry`.

---

## 4. Cross-Provider Dispatch

### 4.1 Routing Lookup

A new method on `AdminConfigService`:

```python
async def get_routing_for_task(
    self, task_type: str
) -> tuple[str, str] | None:
    """Get (provider, model) for a task type.

    Queries task_routing_config for the given task_type.
    Unlike get_model_for_task(), this returns the provider too,
    enabling cross-provider dispatch.

    Returns:
        (provider, model) tuple, or None if no routing configured.
    """
```

### 4.2 MeteredLLMProvider Changes

`MeteredLLMProvider.__init__()` accepts a `registry: dict[str, LLMProvider]` instead of relying solely on `self._inner`. The dispatch logic in `complete()` becomes:

1. Call `get_routing_for_task(task.value)` to get `(provider, model)`.
2. If routing exists, look up `registry[provider]` and call `complete()` with `model_override=model`.
3. If routing exists but provider is not in registry (no API key), raise `ProviderError`.
4. If no routing exists in DB, fall back to `self._inner` with existing behavior (adapter's hardcoded routing).
5. Log fallbacks at WARNING level.

The same pattern applies to `stream()`.

### 4.3 Fallback Chain

| Priority | Condition | Behavior |
|----------|-----------|----------|
| 1 | DB has routing for task | Use `(provider, model)` from DB. If provider not in registry, raise error |
| 2 | No DB routing for task | Fall back to `LLM_PROVIDER` env var + adapter hardcoded routing |
| 3 | Metering disabled | Skip MeteredLLMProvider entirely, use singleton (unchanged) |

### 4.4 Usage Tracking

`record_and_debit()` already records `provider` and `model` per request. With cross-provider dispatch, different tasks will naturally record different providers, enabling cost/quality comparison in the usage table.

---

## 5. Routing Test Endpoint

### 5.1 Endpoint Design

```
POST /api/v1/admin/routing/test
```

**Request body:**

```json
{
    "task_type": "extraction",
    "prompt": "Test prompt for extraction task"
}
```

**Response body:**

```json
{
    "data": {
        "provider": "claude",
        "model": "claude-3-5-haiku-20241022",
        "response": "...",
        "latency_ms": 342.5,
        "input_tokens": 15,
        "output_tokens": 28
    }
}
```

### 5.2 Constraints

- **Admin-only** — uses `AdminUser` dependency.
- **No user metering** — test calls are not debited from any user's balance.
- **Rate limited** — max 5 requests per minute per admin (prevent abuse).
- **Timeout** — 30-second hard timeout on the LLM call.

---

## 6. Admin UI Routing Tab

### 6.1 Design

The routing tab displays a **fixed 10-row table** (one row per `TaskType` enum value), all pre-populated. No add/delete — only inline editing of provider and model.

| Column | Type | Editable |
|--------|------|----------|
| Task Type | Display name | No |
| Provider | Dropdown (claude/openai/gemini) | Yes |
| Model | Dropdown (filtered by provider) | Yes |
| Test | Button | N/A |
| Status | Badge (pass/fail/untested) | No |

### 6.2 Test Button

Each row has a test button that sends a test prompt to `POST /admin/routing/test` with the row's task type. The result displays inline:
- Green badge with latency on success
- Red badge with error message on failure (e.g., "Provider not configured")

### 6.3 Deletions

- `add-routing-dialog.tsx` — deleted (no longer needed with fixed table)
- Add/delete routing API calls removed from the UI (backend endpoints remain for API consumers)

---

## 7. Gemini Embedding Adapter

### 7.1 Implementation

```python
class GeminiEmbeddingAdapter(EmbeddingProvider):
    """Gemini embedding provider using google.genai SDK.

    Uses text-embedding-004 model with 768 dimensions.
    """

    provider_name = "gemini"

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings via Gemini."""
        ...

    @property
    def dimensions(self) -> int:
        return 768
```

### 7.2 SDK

Uses `google.genai` (same SDK as the Gemini LLM adapter). The `embed_content` method supports batch embedding.

### 7.3 Model

`text-embedding-004` — Google's latest embedding model. 768 dimensions (vs OpenAI's 1536). Competitive quality at lower dimensionality.

---

## 8. Vector Dimension Migration

### 8.1 Strategy

1. **Truncate** `persona_embeddings` and `job_embeddings` tables (derived data, fully regenerable from source text).
2. **ALTER** vector columns from `Vector(1536)` to `Vector(768)`.
3. **Re-embed** via standalone script (not in migration — external API calls do not belong in Alembic migrations).

### 8.2 Affected Tables

| Table | Column | Before | After |
|-------|--------|--------|-------|
| `persona_embeddings` | `embedding` | `Vector(1536)` | `Vector(768)` |
| `job_embeddings` | `embedding` | `Vector(1536)` | `Vector(768)` |

### 8.3 Transition Window

After migration but before re-embedding:
- Similarity searches return no results (empty tables)
- Job scores default to zero
- This is acceptable for the brief operational window

### 8.4 Rollback

Downgrade migration restores `Vector(1536)`. Re-run re-embedding with OpenAI adapter to restore previous state.

---

## 9. BYOK Removal

### 9.1 Rationale

REQ-023 introduced centralized USD-direct billing where the admin manages all API keys. Users pay for usage through funding packs, not their own API keys. This makes BYOK unnecessary and architecturally contradictory.

### 9.2 Changes to REQ-009

| Section | Change |
|---------|--------|
| section 1.3 Goals | "BYOK ready" goal marked "Not Planned" |
| section 10 | Title updated to "BYOK Support (Not Planned — Superseded by REQ-028)" |
| section 10.1-10.3 | Content preserved for historical context, prefixed with supersession note |
| Change Log | Entry documenting the change |

---

## 10. Environment Variable Changes

| Variable | Before | After | Notes |
|----------|--------|-------|-------|
| `EMBEDDING_PROVIDER` | Default `openai` | Default `gemini` | Existing `openai` values still work |
| `EMBEDDING_MODEL` | Default `text-embedding-3-small` | Default `text-embedding-004` | |
| `EMBEDDING_DIMENSIONS` | Default `1536` | Default `768` | Must match vector column size |

---

## 11. What Does NOT Change

These components are intentionally left unchanged:

| Component | Count | Why Unchanged |
|-----------|-------|---------------|
| Service files | 20+ | Use `TaskType` abstraction, never reference providers directly |
| LLM adapters | 3 | Already implement `LLMProvider` interface correctly |
| Prompts | All | Provider-agnostic text |
| Non-admin frontend | All pages | Only admin settings page changes |
| Admin DB tables | 4 | Already have `provider` column in routing table |
| Admin CRUD endpoints | Existing | Create/update/delete routing still work |
| Mock adapter | 1 | Testing interface unchanged |

---

## 12. Design Decisions & Rationale

| Decision | Options Considered | Chosen | Rationale |
|----------|--------------------|--------|-----------|
| Registry vs. multi-singleton | (a) Dict registry, (b) named singletons, (c) DI container | Dict registry | Simplest, no new deps, easy to test |
| Fixed vs. dynamic routing rows | (a) Fixed 10 rows, (b) add/delete | Fixed 10 | TaskType enum is fixed; prevents orphan/duplicate rows |
| Gemini vs. Cohere for embeddings | (a) Gemini, (b) Cohere, (c) keep OpenAI | Gemini | Same SDK as LLM adapter, eliminates OpenAI key dependency |
| 768 vs. 1536 dimensions | (a) Gemini native 768, (b) pad to 1536 | Native 768 | Smaller vectors, faster similarity, adequate quality |
| BYOK removal vs. deferral | (a) Remove, (b) keep as future | Remove | REQ-023 billing model makes BYOK architecturally contradictory |

---

## 13. Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-07 | 0.1 | Initial draft |
