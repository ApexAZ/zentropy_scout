# Zentropy Scout — Audit Remediation Plan

**Created:** 2026-02-26
**Last Updated:** 2026-02-26
**Status:** Ready for Implementation
**Source:** Deep-dive audit by code-reviewer, security-reviewer, security-triage, and qa-reviewer subagents

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Each task = one commit, sized ≤ 50k tokens of context (TDD + review + fixes included)
3. **Subtask workflow:** Run affected tests → linters → commit → compact (NO push)
4. **Phase-end workflow:** Run full test suite (backend + frontend + E2E) → push → compact
5. After each task: update status (⬜ → ✅), commit, STOP and ask user

**Context management for fresh sessions:** Each subtask is self-contained. A fresh context window needs:
1. This plan (find current task by status icon)
2. The specific files listed in the task description
3. No prior conversation history required

---

## Scope & Exclusions

### In Scope (this plan)

Findings from the 4-agent deep audit that are **immediately actionable** — security
defense-in-depth, test coverage gaps, error handling, code quality, and dead code cleanup.

### Deferred to Feature Backlog

The following findings are **incomplete feature wiring** from the LLM redesign — they represent
larger scoped work that should be planned separately with their own REQ sections:

| Finding | Reviewer | Why Deferred |
|---------|----------|--------------|
| `execute_tools` is a no-op (chat.py:580) | Code | Requires implementing tool execution pipeline — new feature scope |
| `LocalAgentClient._request` raises NotImplementedError (base.py:918) | Code | Requires routing implementation — new feature scope |
| Chat `/messages` endpoint is a no-op (chat.py:33) | Code | Requires wiring graph invocation — new feature scope |
| Hardcoded `["software", "engineer"]` keywords (job_fetch_service.py:205) | Code | Requires persona-based search — new feature scope |
| `feedback` param silently discarded (content_generation_service.py:92) | Code | Requires regeneration pipeline — new feature scope |
| `/rescore` endpoint is a stub (job_postings.py:781) | Code | Requires wiring JobScoringService — new feature scope |
| `/refresh` endpoint is a stub (refresh.py:14) | Code | Requires wiring DiscoveryWorkflow — new feature scope |
| `ContentGenerationService` no db session + sync methods | Code | Placeholder service — will be addressed when wiring real implementations |
| `base.py` exceeds 300-line limit (1043 lines) | Code | File split is refactoring — lower priority than security/correctness |
| HITL approval flow lost after redesign | Code | Requires new design — feature scope |
| Conversation persistence lost (MemorySaver) | Code | Requires persistent checkpointer — feature scope |

---

## Phase 1: Security Hardening

**Status:** ✅ Complete

*Defense-in-depth fixes for multi-tenant deployment. These are not currently exploitable
(single-user local mode) but become significant when auth is enabled. All 3 security reviewers
agreed on these findings.*

#### Workflow
| Step | Action |
|------|--------|
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| ✅ **Verify** | `pytest -v` (affected files), lint, typecheck |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Add user_id filter to `_load_jobs()`** — Add `user_id: UUID` parameter to `_load_jobs()` in `job_scoring_service.py:103`. Add JOIN through `persona_jobs` → `personas` to filter by `Persona.user_id == user_id`. Update all callers (`score_batch`, `rescore_all_discovered`). Update existing tests. **Files:** `backend/app/services/job_scoring_service.py`, `backend/tests/unit/test_job_scoring_service.py` | `tdd, security, plan` | ✅ |
| 2 | **Add user_id to `finalize_onboarding()` or remove dead code** — `finalize_onboarding()` in `onboarding_workflow.py:473` accepts `persona_id` without ownership check. It is currently **dead code** (no API endpoint calls it, only tests). Decision: add `user_id: UUID` parameter + `Persona.user_id == user_id` in SELECT query for defense-in-depth, since tests exercise it. Update test callers. **Files:** `backend/app/services/onboarding_workflow.py`, `backend/tests/unit/test_onboarding_workflow.py`, `backend/tests/unit/test_race_conditions.py` | `tdd, security, plan` | ✅ |
| 3 | **Add user_id to PersonaEmbeddingCache key** — Change cache key from `persona_id` to `(user_id, persona_id)` tuple in `embedding_cache.py`. Add `user_id` parameter to `get()`, `set()`, `invalidate()`. Update all callers in `job_scoring_service.py`. Update existing tests. Note: cache is NOT a singleton (per-instance), but the key change prevents cross-tenant reads if a global singleton is ever introduced. **Files:** `backend/app/services/embedding_cache.py`, `backend/app/services/job_scoring_service.py`, `backend/tests/unit/test_embedding_cache.py`, `backend/tests/unit/test_job_scoring_service.py` | `tdd, security, plan` | ✅ |
| 4 | **IngestTokenStore: max capacity + auto-cleanup + full test suite** — (a) Add `_MAX_STORE_SIZE` constant (e.g., 1000) to `ingest_token_store.py`. Reject new tokens when capacity exceeded (raise appropriate error). Call `cleanup_expired()` inside `create()` before checking capacity. Add per-user cap constant. (b) Create `backend/tests/unit/test_ingest_token_store.py` with full test suite: all 5 public methods (`create`, `get`, `consume`, `cleanup_expired`, `clear`), tenant isolation (wrong `user_id` returns `None`), token expiration, one-time use via `consume`, capacity limits, singleton lifecycle (`get_token_store`, `reset_token_store`). Source file is only ~180 lines so both fit in one task. **Files:** `backend/app/services/ingest_token_store.py`, `backend/tests/unit/test_ingest_token_store.py` (NEW) | `tdd, security, plan` | ✅ |
| 5 | **Truncate messages before regex matching** — Add `message = message[:2000]` at the top of `classify_intent()` in `chat.py:165` and similarly in `is_update_request()`, `detect_update_section()` in `onboarding.py`, and `is_draft_request()`, `is_regeneration_request()` in `ghostwriter.py`. Add tests verifying truncation behavior. Mechanical one-liner per function. **Files:** `backend/app/agents/chat.py`, `backend/app/agents/onboarding.py`, `backend/app/prompts/ghostwriter.py`, `backend/tests/unit/test_chat_agent.py`, `backend/tests/unit/test_onboarding.py` | `tdd, security, plan` | ✅ |
| 6 | **SSE connection timeout** — Add max connection duration (30 min) and idle timeout to the SSE `/stream` endpoint in `chat.py:69`. Replace infinite `while True` loop with bounded loop using `asyncio.timeout()` or similar. Add tests for timeout behavior. **Files:** `backend/app/api/v1/chat.py`, `backend/tests/unit/test_chat_api.py` (or appropriate test file) | `tdd, security, plan` | ✅ |
| 7 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright + lint + typecheck). Fix regressions, commit, push. | `plan, commands` | ✅ |

---

## Phase 2: Test Coverage Gaps

**Status:** ✅ Complete

*Fill test coverage gaps identified by the QA reviewer. Focus on missing test files and
untested user-facing behavioral changes.*

#### Workflow
| Step | Action |
|------|--------|
| 🧪 **TDD** | Write tests that verify behavior, not implementation |
| ✅ **Verify** | `pytest -v` (affected files), lint |
| 🔍 **Review** | Use `code-reviewer` agent |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 8 | **`delegate_onboarding` unit tests** — Add `TestDelegateOnboarding` class to `backend/tests/unit/test_chat_agent.py`. Test: (a) update request with specific section (e.g., "update my skills") returns message mentioning that section + Persona Management page, (b) update request without specific section returns generic redirect, (c) non-update onboarding request returns wizard redirect. **Files:** `backend/tests/unit/test_chat_agent.py`, `backend/app/agents/chat.py` | `tdd, plan` | ✅ |
| 9 | **Refactor implementation-coupled tests to behavioral assertions** — Fix tests identified by QA reviewer: (a) `test_pipeline_calls_steps_in_order` → assert on `GenerationResult` fields instead of `assert_called_once()` on 7 private methods, (b) `test_skips_variant_creation_when_no_tailoring` → assert `tailoring_action == "use_base"` instead of `_create_variant.assert_not_called()`, (c) `test_generation_error_is_exception` → remove `isinstance` check, (d) `test_loads_persona_embeddings_once_for_batch` → add comment justifying call-count check as performance optimization test. **Files:** `backend/tests/unit/test_content_generation_service.py`, `backend/tests/unit/test_cover_letter_generation.py`, `backend/tests/unit/test_job_scoring_service.py` | `tdd, plan` | ✅ |
| 10 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright + lint + typecheck). Fix regressions, commit, push. | `plan, commands` | ✅ |

---

## Phase 3: Error Handling & Code Quality

**Status:** ⬜ Incomplete

*Fix exception hierarchy violations, dataclass mutability, and LLM output validation gaps.*

#### Workflow
| Step | Action |
|------|--------|
| 🧪 **TDD** | Write tests first — follow `zentropy-tdd` |
| ✅ **Verify** | `pytest -v` (affected files), lint, typecheck |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 11 | **Fix exception hierarchy** — Make 7 bare-`Exception` subclasses inherit from `APIError` instead: `CoverLetterGenerationError`, `GoldenSetValidationError`, `ProviderError`, `InvalidStatusTransitionError`, `CleanupError`, `SourceError`, `AccountLinkingBlockedError`. Add appropriate `status_code` and `code` attributes to each. Changes are mechanical (change parent class + add 2 attributes) but span 7 files. Update any tests that assert on exception types. **Files:** `backend/app/services/cover_letter_generation.py`, `backend/app/services/golden_set.py`, `backend/app/providers/errors.py`, `backend/app/services/job_status.py`, `backend/app/services/retention_cleanup.py`, `backend/app/services/scouter_errors.py`, `backend/app/core/account_linking.py`, `backend/app/core/errors.py`, affected test files | `tdd, plan` | ✅ |
| 12 | **Differentiated exception handling in `delegate_ghostwriter`** — In `delegate_ghostwriter` (chat.py:728), replace bare `except Exception` with differentiated handling: catch `NotFoundError` → "persona/job not found" message, catch `ValidationError` → specific validation message, catch `APIError` → forward error message, catch `Exception` → generic "try again". Add tests for each exception path. **Files:** `backend/app/agents/chat.py`, `backend/tests/unit/test_chat_agent.py` | `tdd, plan` | ⬜ |
| 13 | **Freeze dataclasses + LLM output validation** — (a) Make `CoverLetterResult` frozen with `tuple[str, ...]` for `stories_used`. (b) Make `DiscoveryTrigger` frozen with `tuple[str, ...] | None` for list fields. (c) In `job_extraction.py:143`, replace `cast(ExtractedJobData, data)` with Pydantic model validation. (d) In `resume_parsing_service.py:234`, add size bounds on parsed JSON before constructing `ResumeParseResult`. Update tests for frozen behavior. **Files:** `backend/app/services/cover_letter_generation.py`, `backend/app/services/discovery_workflow.py`, `backend/app/services/job_extraction.py`, `backend/app/services/resume_parsing_service.py`, affected test files | `tdd, security, plan` | ⬜ |
| 14 | **Dead code + docstring cleanup** — (a) Update `state.py` docstring to reflect current architecture (LangGraph only used for Chat Agent, other agents replaced by services). (b) Remove or mark as deprecated: unused `checkpoint.py` utilities (`request_human_input`, `resume_from_checkpoint`), unused `onboarding.py` graph state functions (`create_update_state`, `is_post_onboarding_update`). (c) Update `onboarding.py` module docstring. Verify no callers exist before removing (search codebase). Update affected tests. **Files:** `backend/app/agents/state.py`, `backend/app/agents/checkpoint.py`, `backend/app/agents/onboarding.py`, affected test files | `plan` | ⬜ |
| 15 | **Final gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + Playwright + lint + typecheck). Fix regressions, commit, push. | `plan, commands` | ⬜ |

---

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 1 | §1–§7 | Security hardening (defense-in-depth for multi-tenant) |
| 2 | §8–§10 | Test coverage gaps (missing tests, behavioral violations) |
| 3 | §11–§15 | Error handling, code quality, dead code cleanup |
| **Total** | **15 tasks** | 12 implementation + 3 phase gates |

### Audit Finding → Task Mapping

| Audit Finding | Source(s) | Task |
|---------------|-----------|------|
| `_load_jobs()` no user_id filter | Security, Triage | §1 |
| `finalize_onboarding()` no user_id | Security, Triage | §2 |
| Embedding cache no user_id in key | Security, Triage | §3 |
| IngestTokenStore unbounded memory + no test file | Security, Triage, QA | §4 |
| Chat regex on unbounded input | Security | §5 |
| SSE no connection timeout | Security | §6 |
| `delegate_onboarding` untested | QA | §8 |
| Tests use `assert_called_once` pattern | QA | §9 |
| `CoverLetterGenerationError` bare Exception (+ 6 others) | Code | §11 |
| `delegate_ghostwriter` catches bare Exception | Code | §12 |
| `CoverLetterResult` mutable dataclass | Code, Security | §13 |
| `DiscoveryTrigger` mutable dataclass | Code | §13 |
| LLM output not validated (cast instead of Pydantic) | Security, Triage | §13 |
| `state.py` misleading docstring | Code | §14 |
| Dead code (checkpoint.py, onboarding.py) | Code | §14 |
