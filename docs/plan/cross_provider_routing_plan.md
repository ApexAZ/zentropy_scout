# Cross-Provider Task Routing & Gemini Embeddings — Implementation Plan

**Backlog Item:** #27 — Cross-Provider Task Routing (Admin-Configured)
**REQ:** REQ-028
**Created:** 2026-03-07
**Status:** In Progress

---

## Context

The admin needs to experiment with different LLM models across providers (Claude, OpenAI, Gemini) per task type to optimize cost and quality. Currently `LLM_PROVIDER` env var picks ONE provider — changing it requires a restart. The admin routing table (`task_routing_config`) already has `provider` + `task_type` columns, but the factory only instantiates one adapter, so cross-provider routing doesn't work. Additionally, switching embeddings from OpenAI to Gemini eliminates the need for an OpenAI API key when using Claude + Gemini as primary providers.

## How to Use This Plan

1. Find the first ⬜ task — that's where to start
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

**Status:** ✅ Complete
**Focus:** Backend foundation — registry factory, routing lookup, cross-provider dispatch, test endpoint

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-028 §3 (registry), §4 (dispatch), §5 (test endpoint) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-api` for endpoints, `zentropy-provider` for adapter patterns |
| ✅ **Verify** | `pytest -v`, `ruff check .`, `pyright` |
| 🔍 **Review** | Run `code-reviewer` + `security-reviewer` + `qa-reviewer` as foreground parallel agents |
| 📝 **Commit** | Follow `zentropy-git` — one commit per subtask, no push until phase gate |

#### Tasks
| # | Task | Hints | Status |
|---|------|-------|--------|
| 0 | Security triage gate | `plan, security` | ✅ |
| 1 | Write REQ-028 to disk | `plan` | ✅ |
| 2 | Provider registry factory — `get_llm_registry()` in `factory.py` | `plan, tdd, provider` | ✅ |
| 3 | New `get_routing_for_task()` in `admin_config_service.py` | `plan, tdd, api` | ✅ |
| 4 | MeteredLLMProvider cross-provider dispatch | `plan, tdd, provider` | ✅ |
| 5 | DI wiring update in `deps.py` | `plan, tdd, api` | ✅ |
| 6 | Routing test endpoint `POST /admin/routing/test` | `plan, tdd, api, security` | ✅ |
| 7 | Phase 1 quality gate — full test suite + push | `plan, commands` | ✅ |

**Notes:**
- `get_llm_registry()` should create all adapters whose API keys are present, skipping providers without keys
- `get_routing_for_task()` queries the `task_routing_config` table for the task type, returns `(provider, model)`
- MeteredLLMProvider's `complete()` and `stream()` should look up routing, select the correct adapter from registry, then dispatch
- Fallback: if no DB routing exists, use `LLM_PROVIDER` env var + adapter's hardcoded routing (existing behavior)
- Test endpoint should not meter usage (admin testing), but should be rate limited

---

## Phase 2: Admin UI Routing Tab Redesign

**Status:** ⬜ Incomplete
**Focus:** Frontend — fixed editable routing table, test button, validation

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-028 §6 (admin UI routing tab) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-playwright` for E2E, `zentropy-tdd` for Vitest |
| ✅ **Verify** | `npm run test:run`, `npm run lint`, `npm run typecheck` |
| 🔍 **Review** | Run `code-reviewer` + `security-reviewer` + `qa-reviewer` + `ui-reviewer` as foreground parallel agents |
| 📝 **Commit** | Follow `zentropy-git` — one commit per subtask, no push until phase gate |

#### Tasks
| # | Task | Hints | Status |
|---|------|-------|--------|
| 0 | Security triage gate | `plan, security` | ✅ |
| 1 | Update routing types + add TASK_TYPES constant | `plan, tdd` | ✅ |
| 2 | Rewrite RoutingTab as fixed editable table | `plan, tdd, ui` | ✅ |
| 3 | Add test button + API client function | `plan, tdd, api, ui` | ✅ |
| 4 | Validation — warn if provider has no API key | `plan, tdd, ui` | ✅ |
| 5 | Phase 2 quality gate — vitest + lint + push | `plan, commands` | ⬜ |

**Notes:**
- Fixed 10-row table (one per task type), all pre-populated, editable inline (no add/delete)
- Provider + model as inline dropdowns
- Test button per row sends test prompt to `POST /admin/routing/test`
- Visual warning if provider has no API key (test failure = warning)
- Delete `add-routing-dialog.tsx` (no longer needed)

---

## Phase 3: BYOK Removal

**Status:** ⬜ Incomplete
**Focus:** Documentation only — mark BYOK as superseded

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-009 §10 (BYOK), REQ-028 §9 (BYOK removal) |
| 🧪 **TDD** | N/A — docs-only phase |
| 🗃️ **Patterns** | N/A |
| ✅ **Verify** | Review updated REQ for consistency |
| 🔍 **Review** | Run `code-reviewer` as foreground agent (docs review) |
| 📝 **Commit** | Follow `zentropy-git` — one commit per subtask, no push until phase gate |

#### Tasks
| # | Task | Hints | Status |
|---|------|-------|--------|
| 0 | Security triage gate (combine with 3.1 — docs-only phase) | `plan, security` | ⬜ |
| 1 | Update REQ-009 section 10 + section 1.3 + changelog | `plan` | ⬜ |

**Notes:**
- REQ-009 section 10 covers BYOK — mark as "Not Planned"
- REQ-009 section 1.3 references BYOK in scope — update
- Add changelog entry explaining supersession by REQ-023 centralized billing + REQ-028

---

## Phase 4: Gemini Embedding Adapter

**Status:** ⬜ Incomplete
**Focus:** Backend — Gemini embedding adapter, vector dimension migration, re-embedding script

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-028 §7 (Gemini embedding), §8 (vector migration) |
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-db` for migrations, `zentropy-provider` for adapter patterns |
| ✅ **Verify** | `pytest -v`, `ruff check .`, `pyright` |
| 🔍 **Review** | Run `code-reviewer` + `security-reviewer` + `qa-reviewer` as foreground parallel agents |
| 📝 **Commit** | Follow `zentropy-git` — one commit per subtask, no push until phase gate |

#### Tasks
| # | Task | Hints | Status |
|---|------|-------|--------|
| 0 | Security triage gate | `plan, security` | ⬜ |
| 1 | GeminiEmbeddingAdapter implementation | `plan, tdd, provider` | ⬜ |
| 2 | Update embedding factory — add `"gemini"` case | `plan, tdd, provider` | ⬜ |
| 3 | Update ProviderConfig defaults + `.env.example` | `plan, tdd` | ⬜ |
| 4 | Alembic migration — truncate + alter vector columns | `plan, tdd, db` | ⬜ |
| 5 | Update EmbeddingColumnsMixin + MockEmbeddingProvider | `plan, tdd, provider` | ⬜ |
| 6 | Re-embedding script `backend/scripts/reembed_all.py` | `plan, tdd, provider, db` | ⬜ |
| 7 | Phase 4 quality gate — full test suite + push | `plan, commands` | ⬜ |

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
| Phase 1 | 8 (0-7) | 8/8 ✅ |
| Phase 2 | 6 (0-5) | ⬜ |
| Phase 3 | 2 (0-1) | ⬜ |
| Phase 4 | 8 (0-7) | ⬜ |
| **Total** | **24** | **8/24 complete** |

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
