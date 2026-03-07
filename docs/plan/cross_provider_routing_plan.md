# Cross-Provider Task Routing & Gemini Embeddings — Implementation Plan

**Backlog Item:** #27 — Cross-Provider Task Routing (Admin-Configured)
**REQ:** REQ-028
**Created:** 2026-03-07
**Status:** In Progress

---

## Context

The admin needs to experiment with different LLM models across providers (Claude, OpenAI, Gemini) per task type to optimize cost and quality. Currently `LLM_PROVIDER` env var picks ONE provider — changing it requires a restart. The admin routing table (`task_routing_config`) already has `provider` + `task_type` columns, but the factory only instantiates one adapter, so cross-provider routing doesn't work. Additionally, switching embeddings from OpenAI to Gemini eliminates the need for an OpenAI API key when using Claude + Gemini as primary providers.

## How to Use This Plan

1. Find the first task with status marker unfilled
2. Load relevant skill(s) listed in Hints
3. Read the referenced REQ section(s)
4. Implement using TDD (zentropy-tdd skill)
5. After each subtask: commit, update this plan, AskUserQuestion

## Dependency Chain

```
Phase 1: Provider Registry & Cross-Provider Dispatch (backend) <- foundation
    |-- Phase 2: Admin UI Routing Tab Redesign (frontend)
    |-- Phase 3: BYOK Removal (docs only)
    +-- Phase 4: Gemini Embedding Adapter (backend + migration)
```

Phase 1 must complete first. Phases 2, 3, 4 can proceed in any order after Phase 1.

---

## Phase 1: Provider Registry & Cross-Provider Dispatch

**Focus:** Backend foundation — registry factory, routing lookup, cross-provider dispatch, test endpoint
**Workflow:** `zentropy-tdd`, `zentropy-api`, `zentropy-provider`

| # | Task | Hints | Status |
|---|------|-------|--------|
| 0 | Security triage gate | `security-triage` subagent | done 2026-03-07 |
| 1 | Write REQ-028 to disk | Must be FIRST action per learned lesson | done 2026-03-07 |
| 2 | Provider registry factory — `get_llm_registry()` in `factory.py` | Creates all adapters with valid API keys, dict return | pending |
| 3 | New `get_routing_for_task()` in `admin_config_service.py` | Returns `(provider, model)` tuple, no provider param | pending |
| 4 | MeteredLLMProvider cross-provider dispatch | Accept registry, look up routing, dispatch to correct adapter | pending |
| 5 | DI wiring update in `deps.py` | Pass registry to MeteredLLMProvider | pending |
| 6 | Routing test endpoint `POST /admin/routing/test` | Admin-only, no user metering, rate limited | pending |
| 7 | Phase 1 quality gate — full test suite + push | `test-runner` Full mode | pending |

**Notes:**
- `get_llm_registry()` should create all adapters whose API keys are present, skipping providers without keys
- `get_routing_for_task()` queries the `task_routing_config` table for the task type, returns `(provider, model)`
- MeteredLLMProvider's `complete()` and `stream()` should look up routing, select the correct adapter from registry, then dispatch
- Fallback: if no DB routing exists, use `LLM_PROVIDER` env var + adapter's hardcoded routing (existing behavior)
- Test endpoint should not meter usage (admin testing), but should be rate limited

---

## Phase 2: Admin UI Routing Tab Redesign

**Focus:** Frontend — fixed editable routing table, test button, validation
**Workflow:** `zentropy-tdd`, `zentropy-playwright`

| # | Task | Hints | Status |
|---|------|-------|--------|
| 0 | Security triage gate | `security-triage` subagent | pending |
| 1 | Update routing types + add TASK_TYPES constant | `types/admin.ts`, new constants file | pending |
| 2 | Rewrite RoutingTab as fixed editable table | 10 rows, inline dropdowns, delete add-routing-dialog | pending |
| 3 | Add test button + API client function | Per-row test, inline result display | pending |
| 4 | Validation — warn if provider has no API key | Test button failure = visual warning | pending |
| 5 | Phase 2 quality gate — vitest + lint + push | `test-runner` Full mode | pending |

**Notes:**
- Fixed 10-row table (one per task type), all pre-populated, editable inline (no add/delete)
- Provider + model as inline dropdowns
- Test button per row sends test prompt to `POST /admin/routing/test`
- Visual warning if provider has no API key (test failure = warning)
- Delete `add-routing-dialog.tsx` (no longer needed)

---

## Phase 3: BYOK Removal

**Focus:** Documentation only — mark BYOK as superseded
**Workflow:** Docs-only, no code changes

| # | Task | Hints | Status |
|---|------|-------|--------|
| 0 | Security triage gate | Can combine with 3.1 (docs-only phase) | pending |
| 1 | Update REQ-009 section 10 + section 1.3 + changelog | Mark BYOK "Not Planned — Superseded by REQ-028" | pending |

**Notes:**
- REQ-009 section 10 covers BYOK — mark as "Not Planned"
- REQ-009 section 1.3 references BYOK in scope — update
- Add changelog entry explaining supersession by REQ-023 centralized billing + REQ-028

---

## Phase 4: Gemini Embedding Adapter

**Focus:** Backend — Gemini embedding adapter, vector dimension migration, re-embedding script
**Workflow:** `zentropy-tdd`, `zentropy-db`, `zentropy-provider`

| # | Task | Hints | Status |
|---|------|-------|--------|
| 0 | Security triage gate | `security-triage` subagent | pending |
| 1 | GeminiEmbeddingAdapter implementation | `google.genai` SDK, `text-embedding-004`, 768 dims | pending |
| 2 | Update embedding factory — add `"gemini"` case | `factory.py`, `__init__.py` exports | pending |
| 3 | Update ProviderConfig defaults + `.env.example` | `openai` to `gemini`, `1536` to `768` | pending |
| 4 | Alembic migration — truncate + alter vector columns | `persona_embeddings`, `job_embeddings` to Vector(768) | pending |
| 5 | Update EmbeddingColumnsMixin + MockEmbeddingProvider | `base.py` Vector(1536) to 768, mock dims | pending |
| 6 | Re-embedding script `backend/scripts/reembed_all.py` | One-time script, not migration step | pending |
| 7 | Phase 4 quality gate — full test suite + push | `test-runner` Full mode | pending |

**Notes:**
- `google.genai` SDK for Gemini embeddings (same SDK as LLM adapter)
- `text-embedding-004` model, 768 dimensions
- Migration truncates `persona_embeddings` + `job_embeddings` (derived data, regenerable)
- Re-embedding is a standalone script, NOT a migration step (external API calls don't belong in migrations)
- During transition window (after migration, before re-embed): similarity searches return no results, job scores default to zero
- Rollback: downgrade migration restores 1536, re-run re-embed with OpenAI

---

## Task Count Summary

| Phase | Tasks | Status |
|-------|-------|--------|
| Phase 1 | 8 (0-7) | pending |
| Phase 2 | 6 (0-5) | pending |
| Phase 3 | 2 (0-1) | pending |
| Phase 4 | 8 (0-7) | pending |
| **Total** | **24** | **0/24 complete** |

---

## Critical Files Reference

| File | Change |
|------|--------|
| `backend/app/providers/factory.py` | Add `get_llm_registry()`, keep `get_llm_provider()` for compat |
| `backend/app/providers/metered_provider.py` | Accept registry, cross-provider dispatch in `complete()` + `stream()` |
| `backend/app/services/admin_config_service.py` | Add `get_routing_for_task(task_type)` to `(provider, model)` |
| `backend/app/api/deps.py` | Pass registry to MeteredLLMProvider |
| `backend/app/api/v1/admin.py` | Add `POST /admin/routing/test` |
| `frontend/src/components/admin/routing-tab.tsx` | Rewrite to fixed editable table |
| `frontend/src/components/admin/add-routing-dialog.tsx` | DELETE (no longer needed) |
| `backend/app/providers/embedding/gemini_adapter.py` | NEW — GeminiEmbeddingAdapter |
| `backend/app/providers/config.py` | Change embedding defaults |
| `backend/app/models/base.py` | Vector(1536) to Vector(768) |

## Files NOT Changed

- All 20+ service files (use `TaskType` abstraction)
- All 3 LLM adapters (claude, openai, gemini) — already implement same interface
- All prompts (provider-agnostic)
- All non-admin frontend pages
- Admin DB tables (already have `provider` column)
- Admin API endpoints (already have CRUD for routing)

---

## Change Log

| Date | Change |
|------|--------|
| 2026-03-07 | Plan created |
