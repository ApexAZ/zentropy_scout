# REQ-018: Ghostwriter Service Layer Redesign

**Status:** Draft
**Version:** 0.1
**Supersedes:** REQ-007 §8 (Ghostwriter Agent), §15.5 (Ghostwriter Agent Graph)
**PRD Reference:** §4.4 Ghostwriter
**Last Updated:** 2026-02-23

---

## §1 Overview & Motivation

### 1.1 What This Document Does

This document specifies the redesign of Zentropy Scout's Ghostwriter from a LangGraph `StateGraph` agent into a `ContentGenerationService`. It replaces REQ-007 §8 (Ghostwriter Agent) and §15.5 (Ghostwriter Agent Graph) in their entirety.

### 1.2 Why the Redesign Is Needed

The Ghostwriter is implemented across three files: `ghostwriter_graph.py` (687L), `ghostwriter.py` (212L), and `ghostwriter_prompts.py` (405L). Code review (2026-02-23) found a **two-tier reality**:

**Tier 1 — The graph is mostly placeholder:**
- 7 of 9 graph nodes are stubs that return empty/default state
- Only `present_for_review_node()` and `handle_duplicate_node()` have real implementation
- `check_existing_variant_node()` returns None, `select_base_resume_node()` returns None, `evaluate_tailoring_need_node()` receives empty data, `create_job_variant_node()` returns None, `select_achievement_stories_node()` receives empty data, `generate_cover_letter_node()` receives empty prompt fields, `check_job_still_active_node()` returns True
- HITL "pause/resume" is not actually implemented — `requires_human_input` flag is set before `END`, but the graph never truly pauses mid-execution

**Tier 2 — The services are production-ready:**
- `cover_letter_generation.py` (173L) — real LLM integration with XML parsing
- `cover_letter_validation.py` (382L) — 5-rule validator
- `cover_letter_structure.py` (129L) — section specifications
- `cover_letter_output.py` (129L) — output schema
- `cover_letter_pdf_generation.py` (286L) — PDF rendering via ReportLab
- `cover_letter_pdf_storage.py` (224L) — BYTEA storage
- `cover_letter_editing.py` — draft editing
- `tailoring_decision.py` (269L) — keyword gap + bullet relevance analysis
- `modification_limits.py` (175L) — variant guardrails (3 checks)
- `story_selection.py` (522L) — 5-factor scoring with diversification
- `regeneration.py` (118L) — feedback categories
- `generation_outcome.py` (181L) — outcome tracking
- `explanation_generation.py` (427L) — strength/gap/stretch analysis

The graph adds LangGraph overhead (state schema, checkpoint config, routing functions) to orchestrate calls to services that are independently testable and production-ready. The orchestration is a simple 8-step pipeline.

### 1.3 What Changes

| Aspect | Before | After |
|--------|--------|-------|
| Architecture | LangGraph `StateGraph` with 9 nodes | Single `ContentGenerationService` class |
| Entry point | `ghostwriter_graph.ainvoke(state)` / `generate_materials()` | `ContentGenerationService.generate()` |
| State management | `GhostwriterState` TypedDict (20+ fields) | Function parameters and return values |
| Checkpoint/HITL | Flag-based (not true pause/resume) | None at MVP; true revision workflow deferred to post-MVP |
| Dependency | `langgraph` package | None (plain `async/await`) |
| Prompts | `agents/ghostwriter_prompts.py` | `prompts/ghostwriter.py` (relocated) |

### 1.4 What Does NOT Change

All 15 service files listed in §4.2 are **completely untouched**. They are the production-ready business logic. The redesign only removes the LangGraph orchestration layer that wraps them.

---

## §2 Dependencies & Prerequisites

### 2.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-002 Resume Schema v0.7 | Entity definitions | BaseResume, JobVariant |
| REQ-002b Cover Letter Schema v0.5 | Entity definitions | CoverLetter, achievement story selection |
| REQ-005 Database Schema v0.10 | Schema | `job_variants`, `cover_letters` tables |
| REQ-006 API Contract v0.8 | Integration | `/job-variants`, `/cover-letters` endpoints |
| REQ-009 Provider Abstraction v0.3 | Integration | LLM provider for content generation |
| REQ-010 Content Generation v0.2 | Specification | Generation pipeline behavior |
| REQ-017 Strategist Service Layer | Integration | Scoring must exist before drafting is triggered |

### 2.2 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-007 §15.5 | Superseded | This document replaces §15.5 entirely |

### 2.3 Cross-REQ Implementation Order

```
REQ-016 (Scouter) ──┐
                     ├──→ REQ-017 (Strategist) ──→ REQ-018 (Ghostwriter)
REQ-019 (Onboarding)┘
```

**This document (REQ-018) must be implemented last** (after REQ-017). The auto-draft trigger in the Strategist calls the Ghostwriter — `ContentGenerationService` must exist before `JobScoringService._check_auto_draft()` can reference it. Note: auto-draft is deferred to post-MVP (§3.2), but the service interface must exist.

---

## §3 Design Decisions

### 3.1 Replacement Architecture: Single Orchestrator Service

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Single `ContentGenerationService` orchestrating existing services | ✅ | The 13 service files are already independently implemented and tested (492 unit tests). What's missing is the orchestrator that wires them together with real data. One new class calls them in sequence — no framework needed. |
| Multiple orchestrator services (resume vs cover letter) | — | Resume tailoring and cover letter generation are always done together for a job. Splitting them creates coordination overhead and a partial-generation failure state. |
| Keep LangGraph with real node implementations | — | The graph adds state schema management, routing functions, and checkpoint infrastructure for a pipeline that has no branching decisions and no human interaction points. |

### 3.2 Auto-Draft: Explicitly Deferred to Post-MVP

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| User-initiated only (MVP) | ✅ | If the system spends user credits generating materials without explicit user action, trust is destroyed. Users must click "Draft Materials" to trigger generation. `TriggerType.AUTO_DRAFT` exists in the enum but is never called at MVP. |
| Auto-draft above threshold | Deferred | Post-MVP, when credit system and user preferences are established. Requires opt-in consent flow. |

### 3.3 Prompt Relocation: `prompts/ghostwriter.py`

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Move to `backend/app/prompts/ghostwriter.py` | ✅ | Consistent with REQ-017 §3.3 pattern. `agents/` directory is being emptied. Prompts are reusable assets. |
| Keep in `backend/app/agents/ghostwriter_prompts.py` | — | Misleading location after graph deletion. |

### 3.4 True Revision Workflow: Deferred to Post-MVP

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Re-invocation pattern (current) | ✅ for MVP | User reviews draft → provides feedback → system generates new draft. This is two separate `generate()` calls, not a paused graph. Simple, works, no checkpoint infrastructure needed. |
| True pause/resume revision (LangGraph) | Deferred | Post-MVP. When implemented, this would be the one genuine LangGraph use case — multi-turn revision within a single session. Documented for future reference so the naive re-invocation pattern isn't repeated. |

---

## §4 Current State Inventory

### 4.1 Files to Modify or Delete

| File | Lines | Role | Action |
|------|-------|------|--------|
| `backend/app/agents/ghostwriter_graph.py` | 687 | LangGraph graph: 9 nodes (7 placeholders), routing | **DELETE** |
| `backend/app/agents/ghostwriter.py` | 212 | Trigger helpers, state factory, pattern detection | **KEEP** (refactor — remove state factory, keep trigger helpers) |
| `backend/app/agents/ghostwriter_prompts.py` | 405 | Cover letter + summary tailoring prompts | **RELOCATE** to `backend/app/prompts/ghostwriter.py` |
| `backend/app/agents/state.py` | 404 | Contains `GhostwriterState` TypedDict (~65 lines) | **MODIFY** (remove `GhostwriterState` and related TypedDicts) |
| `backend/app/agents/__init__.py` | 196 | Re-exports Ghostwriter graph | **MODIFY** (remove Ghostwriter graph exports) |

### 4.2 Service Files That Stay Unchanged (15 files)

| File | Lines | Tests | Role |
|------|-------|-------|------|
| `services/cover_letter_generation.py` | 173 | 13 | LLM integration, XML parsing |
| `services/cover_letter_structure.py` | 129 | 10 | Section specifications |
| `services/cover_letter_validation.py` | 382 | 58 | 5-rule validator |
| `services/cover_letter_output.py` | 129 | 20 | Output schema |
| `services/cover_letter_pdf_generation.py` | 286 | 14 | PDF rendering |
| `services/cover_letter_pdf_storage.py` | 224 | 18 | BYTEA storage |
| `services/cover_letter_editing.py` | ~150 | 11 | Draft editing |
| `services/tailoring_decision.py` | 269 | 30 | Keyword gap + bullet relevance |
| `services/modification_limits.py` | 175 | 37 | Variant guardrails |
| `services/story_selection.py` | 522 | 35 | 5-factor scoring + diversification |
| `services/regeneration.py` | 118 | 24 | Feedback categories |
| `services/generation_outcome.py` | 181 | 53 | Outcome tracking |
| `services/explanation_generation.py` | 427 | 30 | Strength/gap/stretch analysis |
| `services/reasoning_explanation.py` | ~100 | 35 | Agent reasoning output formatting (REQ-010 §9) |
| `services/duplicate_story.py` | ~100 | 31 | Duplicate story selection edge cases (REQ-010 §8.4) |

**Total: ~3,365 lines of production code, 419 tests — all untouched.**

### 4.3 What to Keep in `ghostwriter.py`

| Function | Lines | Why Keep |
|----------|-------|----------|
| `TriggerType` enum | 20–30 | Used by API to distinguish manual vs regeneration requests |
| `should_auto_draft()` | ~15 | Used by Strategist (post-MVP auto-draft trigger) |
| `is_draft_request()` | ~15 | Used by Chat Agent for intent classification |
| `is_regeneration_request()` | ~15 | Used by Chat Agent for intent classification |

**Remove from `ghostwriter.py`:**

| Function | Lines | Why Remove |
|----------|-------|------------|
| `create_ghostwriter_state()` | ~30 | Creates `GhostwriterState` TypedDict — no longer needed |

### 4.4 What Moves from `ghostwriter_graph.py` to Service

| Function in `ghostwriter_graph.py` | Status | Destination |
|-------------------------------|--------|-------------|
| `check_existing_variant_node()` | Placeholder | `ContentGenerationService._check_existing()` (implement for real) |
| `handle_duplicate_node()` | Real | `ContentGenerationService._handle_duplicate()` |
| `select_base_resume_node()` | Placeholder | `ContentGenerationService._select_base_resume()` (implement for real) |
| `evaluate_tailoring_need_node()` | Placeholder | `ContentGenerationService._evaluate_tailoring()` → delegates to `tailoring_decision.py` |
| `create_job_variant_node()` | Placeholder | `ContentGenerationService._create_variant()` (implement LLM call) |
| `select_achievement_stories_node()` | Placeholder | `ContentGenerationService._select_stories()` → delegates to `story_selection.py` |
| `generate_cover_letter_node()` | Placeholder | `ContentGenerationService._generate_cover_letter()` → delegates to `cover_letter_generation.py` |
| `check_job_still_active_node()` | Placeholder | `ContentGenerationService._check_job_active()` (implement DB query) |
| `present_for_review_node()` | Real | `ContentGenerationService._build_review_response()` |
| Routing functions (3) | Real | Inline `if/else` in `generate()` |
| `generate_materials()` convenience | Real | `ContentGenerationService.generate()` |
| Graph construction | Real | **DELETE** (no replacement) |

---

## §5 Deletion Plan

### 5.1 Files to Delete

| File | Lines | Reason |
|------|-------|--------|
| `backend/app/agents/ghostwriter_graph.py` | 687 | Entire LangGraph graph. 7 of 9 nodes are placeholders. Orchestration moves to `ContentGenerationService`. |

### 5.2 Files to Relocate

| From | To | Lines | Reason |
|------|----|-------|--------|
| `backend/app/agents/ghostwriter_prompts.py` | `backend/app/prompts/ghostwriter.py` | 405 | Prompts survive; `agents/` directory is being emptied. |

### 5.3 Code to Remove from Existing Files

| File | What to Remove | Reason |
|------|---------------|--------|
| `backend/app/agents/state.py` | `GhostwriterState`, `TailoringAnalysis`, `GeneratedContent`, `ScoredStoryDetail` TypedDicts (~65 lines) | Replaced by function parameters and existing service types |
| `backend/app/agents/ghostwriter.py` | `create_ghostwriter_state()` factory (~30 lines) | No more `GhostwriterState` to construct |
| `backend/app/agents/__init__.py` | Ghostwriter graph imports/re-exports | No longer exists |

---

## §6 New Architecture

### 6.1 Service Overview

```
ContentGenerationService
  generate(db, user_id, persona_id, job_posting_id, trigger_type)
      │
      ├── [Step 1] Check existing variant (duplicate prevention)
      ├── [Step 2] Select base resume (role_type matching)
      ├── [Step 3] Evaluate tailoring need → tailoring_decision.py
      ├── [Step 4] Create job variant (LLM) → modification_limits.py
      ├── [Step 5] Select achievement stories → story_selection.py
      ├── [Step 6] Generate cover letter (LLM) → cover_letter_generation.py
      │                                        → cover_letter_validation.py
      ├── [Step 7] Check job still active
      └── [Step 8] Build review response → explanation_generation.py
```

### 6.2 `ContentGenerationService` (`backend/app/services/content_generation_service.py`)

**Responsibility:** Orchestrate the 8-step content generation pipeline.

```python
class ContentGenerationService:
    """Generates tailored application materials for a job posting."""

    async def generate(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        persona_id: uuid.UUID,
        job_posting_id: uuid.UUID,
        trigger_type: TriggerType = TriggerType.MANUAL,
    ) -> GenerationResult:
        """Generate tailored resume variant + cover letter for a job.

        8-step pipeline:
        1. Check for existing JobVariant (duplicate prevention)
        2. Select best-matching BaseResume
        3. Evaluate tailoring need (keyword gaps, bullet relevance)
        4. Create JobVariant if tailoring needed (LLM call)
        5. Select achievement stories for cover letter
        6. Generate cover letter (LLM call)
        7. Check job is still active (warn if expired)
        8. Build review response with reasoning explanation

        Returns:
            GenerationResult with variant, cover_letter, explanation,
            and optional warning if job expired mid-generation.
        """

    async def regenerate(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        persona_id: uuid.UUID,
        job_posting_id: uuid.UUID,
        feedback: str,
        feedback_category: FeedbackCategory,
    ) -> GenerationResult:
        """Regenerate materials based on user feedback.

        Archives old draft, creates new draft incorporating feedback.
        Uses RegenerationConfig from regeneration.py to adjust prompts.
        """
```

**Key design notes:**
- `generate()` is the single entry point replacing `ghostwriter_graph.ainvoke()` / `generate_materials()`
- Duplicate prevention: check for existing Draft/Approved variant before starting
- Orchestrates 13 existing service files — no new business logic
- `regenerate()` handles user feedback loop (re-invocation, not true pause/resume)
- Returns a `GenerationResult` dataclass, not a mutated state dict

---

## §7 Behavioral Specification

### 7.1 Generation Pipeline

```
Input: user_id + persona_id + job_posting_id + trigger_type
    │
    ▼
1. Check existing variant
    ├── Draft exists → return existing draft
    ├── Approved exists → return "already approved" message
    └── None → continue
    │
    ▼
2. Select base resume
    │  Match role_type to job title
    │  Fall back to is_primary
    │
    ▼
3. Evaluate tailoring need
    ├── No tailoring → use BaseResume as-is for variant
    └── Tailoring needed → continue to step 4
    │
    ▼
4. Create job variant (LLM)
    │  Reorder bullets, adjust summary
    │  Validate against modification_limits.py
    │  Save as Draft
    │
    ▼
5. Select achievement stories
    │  5-factor scoring: skill match, recency, metrics, diversity, usage
    │  Return top 2 stories
    │
    ▼
6. Generate cover letter (LLM)
    │  Apply voice profile
    │  Reference selected stories
    │  Validate against 5-rule validator
    │  Save as Draft
    │
    ▼
7. Check job still active
    ├── Active → continue
    └── Expired → add warning to response
    │
    ▼
8. Build review response
    │  Explanation of tailoring decisions
    │  Story selection reasoning
    │  Return GenerationResult
```

### 7.2 Duplicate Prevention (from REQ-007 §10.4.2)

| Scenario | Behavior |
|----------|----------|
| No existing variant | Proceed with generation |
| Draft variant exists | Return existing draft with message |
| Approved variant exists | Block with message: "You already have approved materials for this job" |
| User explicitly requests regeneration | Archive old draft, create new one |

### 7.3 Modification Limits (from REQ-002 §11.3)

| Allowed | Forbidden |
|---------|-----------|
| Reorder bullets within jobs | Add content not in Persona |
| Adjust summary wording | Rewrite summary completely |
| Highlight different skills from BaseResume | Change job history |
| | Fabricate skills or experiences |

---

## §8 Prompt Specifications

### 8.1 Cover Letter Prompt (relocated from `ghostwriter_prompts.py`)

The full `COVER_LETTER_SYSTEM_PROMPT` and `build_cover_letter_prompt()` function relocate unchanged to `prompts/ghostwriter.py`. See `ghostwriter_prompts.py` lines 1–200 for current implementation.

### 8.2 Summary Tailoring Prompt (relocated from `ghostwriter_prompts.py`)

The full `SUMMARY_TAILORING_SYSTEM_PROMPT` and `build_summary_tailoring_prompt()` function relocate unchanged. See `ghostwriter_prompts.py` lines 200–350.

### 8.3 Regeneration Context (relocated from `ghostwriter_prompts.py`)

The `build_regeneration_context()` function relocates unchanged. See `ghostwriter_prompts.py` lines 350–405.

**Model for all generation:** Gemini 2.5 Flash (via provider abstraction layer). Writing quality is adequate for draft generation; users review and edit before submission.

---

## §9 Configuration & Environment

No new environment variables required. Uses existing configuration:

| Variable | Used For |
|----------|----------|
| `LLM_PROVIDER` | Content generation model selection |

---

## §10 Migration Path

### 10.1 Implementation Order

| Step | Action | Depends On |
|------|--------|------------|
| 1 | Relocate `ghostwriter_prompts.py` → `prompts/ghostwriter.py` | `prompts/` directory exists (created in REQ-017 step 1) |
| 2 | Create `ContentGenerationService` orchestrating existing services | Step 1 |
| 3 | Update API endpoints to call `ContentGenerationService` instead of `ghostwriter_graph` | Step 2 |
| 4 | Write new unit tests for `ContentGenerationService` | Step 2 |
| 5 | Delete `ghostwriter_graph.py` | Steps 3 + 4 passing |
| 6 | Remove `GhostwriterState` and related TypedDicts from `state.py` | Step 5 |
| 7 | Remove `create_ghostwriter_state()` from `ghostwriter.py` | Step 5 |
| 8 | Update `__init__.py` exports | Step 5 |

### 10.2 Rollback Strategy

Code-only changes. No database schema modifications. Git revert restores previous state.

---

## §11 Test Impact Analysis

### 11.1 Backend Tests

| Test File | Tests | Action | Reason |
|-----------|-------|--------|--------|
| `tests/unit/test_ghostwriter_graph.py` | 57 | **DELETE** | Tests LangGraph graph topology, placeholder node behavior, routing. All orchestration moves to service test. |
| `tests/unit/test_ghostwriter.py` | 18 | **KEEP** (minor update) | Tests trigger detection (`is_draft_request`, `is_regeneration_request`, `should_auto_draft`). Remove test for `create_ghostwriter_state()`. |
| `tests/unit/test_ghostwriter_prompts.py` | 73 | **KEEP** (update imports) | Tests prompt building and sanitization. Update import path from `agents.ghostwriter_prompts` to `prompts.ghostwriter`. |
| `tests/unit/test_cover_letter_generation.py` | 13 | **KEEP** | Framework-independent |
| `tests/unit/test_cover_letter_structure.py` | 10 | **KEEP** | Framework-independent |
| `tests/unit/test_cover_letter_validation.py` | 58 | **KEEP** | Framework-independent |
| `tests/unit/test_cover_letter_output.py` | 20 | **KEEP** | Framework-independent |
| `tests/unit/test_cover_letter_pdf_generation.py` | 14 | **KEEP** | Framework-independent |
| `tests/unit/test_cover_letter_pdf_storage.py` | 18 | **KEEP** | Framework-independent |
| `tests/unit/test_cover_letter_editing.py` | 11 | **KEEP** | Framework-independent |
| `tests/unit/test_tailoring_decision.py` | 30 | **KEEP** | Framework-independent |
| `tests/unit/test_story_selection.py` | 35 | **KEEP** | Framework-independent |
| `tests/unit/test_modification_limits.py` | 37 | **KEEP** | Framework-independent |
| `tests/unit/test_regeneration.py` | 24 | **KEEP** | Framework-independent |
| `tests/unit/test_generation_outcome.py` | 53 | **KEEP** | Framework-independent |
| `tests/unit/test_explanation_generation.py` | 30 | **KEEP** | Framework-independent |
| `tests/unit/test_reasoning_explanation.py` | ~35 | **KEEP** | Tests `reasoning_explanation.py` (REQ-010 §9 agent reasoning output). Framework-independent. |
| `tests/unit/test_duplicate_story.py` | ~31 | **KEEP** | Tests `duplicate_story.py` (REQ-010 §8.4 edge cases). Framework-independent. |

**Summary:** DELETE 57 tests (graph topology), KEEP ~501 tests (services + triggers + prompts), MODIFY 2 test files (import path updates), CREATE ~25 new service tests.

### 11.2 New Tests to Create

| Test File | Est. Tests | Coverage |
|-----------|-----------|----------|
| `tests/unit/test_content_generation_service.py` | ~25 | `generate()` 8-step pipeline, `regenerate()`, duplicate prevention, base resume selection, job active check, error handling |

### 11.3 Test Migration Notes

- Graph topology tests → **deleted** (no graph)
- Placeholder node tests → **replaced** by real pipeline tests in `test_content_generation_service.py`
- `present_for_review_node` tests → migrate to `_build_review_response()` tests
- `handle_duplicate_node` tests → migrate to `_check_existing()` tests
- Routing function tests → **replaced** by inline `if/else` coverage in service tests

---

## §12 E2E Test Impact

| Spec File | Tests | Action | Reason |
|-----------|-------|--------|--------|
| `frontend/tests/e2e/ghostwriter-review.spec.ts` | 6 | **KEEP** (minor mock updates) | Tests ghostwriter review UI flow. May need mock path updates. |
| `frontend/tests/e2e/cover-letter-review.spec.ts` | 8 | **KEEP** | Tests cover letter review and edit UI. API mocks unchanged. |
| `frontend/tests/e2e/variant-review.spec.ts` | 8 | **KEEP** | Tests resume variant review UI. API mocks unchanged. |
| `frontend/tests/e2e/resume.spec.ts` | 8 | **KEEP** | Tests resume list and selection. Not affected. |
| `frontend/tests/e2e/resume-detail.spec.ts` | 6 | **KEEP** | Tests resume detail view. Not affected. |

**E2E impact is minimal.** The frontend calls the same API endpoints regardless of backend architecture. Mock setup may need minor updates if endpoint behavior changes.

---

## §13 Frontend Impact

**No frontend changes required.** Content generation results are written to `job_variants` and `cover_letters` tables and returned via existing API endpoints. The response shapes are unchanged.

---

## §14 Open Questions & Future Considerations

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | Should the 15 service files be reorganized into a `ghostwriter/` subdirectory? | Deferred | Currently scattered across `services/`. Could group as `services/ghostwriter/cover_letter_generation.py`, etc. Low priority — current flat structure works. |
| 2 | When should true pause/resume revision be implemented? | Post-MVP | The one genuine LangGraph use case for Ghostwriter. Requires real checkpoint/resume infrastructure. Only justified when multi-turn revision within a single session is needed. |
| 3 | Should auto-draft be wired? | **No (MVP)** | See §3.2. User trust concern. `TriggerType.AUTO_DRAFT` exists in enum but is never called. Post-MVP: requires opt-in consent, credit system, and user preference toggle. |

---

## §15 Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-23 | 0.2 | Audit fixes: added 2 missing service files to §4.2 (reasoning_explanation, duplicate_story), added 2 missing test files to §11, updated totals (15 service files, 501 tests kept), added cross-REQ implementation order to §2. |
| 2026-02-23 | 0.1 | Initial draft. Specifies replacement of LangGraph Ghostwriter with `ContentGenerationService` orchestrating 13 existing service files. |
