# REQ-017: Strategist Service Layer Redesign

**Status:** Draft
**Version:** 0.1
**Supersedes:** REQ-007 §7 (Strategist Agent), §15.4 (Strategist Agent Graph)
**PRD Reference:** §4.3 Strategist
**Last Updated:** 2026-02-23

---

## §1 Overview & Motivation

### 1.1 What This Document Does

This document specifies the redesign of Zentropy Scout's Strategist from a LangGraph `StateGraph` agent into a single `JobScoringService`. It replaces REQ-007 §7 (Strategist Agent) and §15.4 (Strategist Agent Graph) in their entirety.

### 1.2 Why the Redesign Is Needed

The Strategist is implemented as a 10-node LangGraph `StateGraph` in `strategist_graph.py` (662 lines). Code review (2026-02-23) found:

1. **9 of 10 nodes are placeholders** — Only `save_scores_node()` has real implementation. `load_persona_embeddings_node()`, `check_embedding_freshness_node()`, `regenerate_embeddings_node()`, `filter_non_negotiables_node()`, `generate_job_embeddings_node()`, `calculate_fit_score_node()`, `calculate_stretch_score_node()`, `generate_rationale_node()`, and `trigger_ghostwriter_node()` all return empty/default state.
2. **All conditional edges are deterministic** — `is_embedding_stale()` checks a version counter, `check_non_negotiables_pass()` checks a boolean, `check_auto_draft_threshold()` compares a score to a threshold. No LLM makes routing decisions.
3. **HITL checkpointing is never triggered** — Scoring is a batch computation with no human interaction point.
4. **The real scoring logic exists outside the graph** — Production-ready services in `fit_score.py` (373L), `stretch_score.py` (612L), `non_negotiables_filter.py` (342L), `scoring_flow.py` (272L), `score_types.py` (182L), `score_explanation.py` (50L), and `score_correlation.py` (244L). The graph just wraps placeholder calls to these services.

The Strategist is a **scoring pipeline**: filter non-negotiables → generate embeddings → calculate fit → calculate stretch → generate rationale → save. The real work is already in services; the graph adds wrapper overhead for zero benefit.

### 1.3 What Changes

| Aspect | Before | After |
|--------|--------|-------|
| Architecture | LangGraph `StateGraph` with 10 nodes | Single `JobScoringService` class |
| Entry point | `strategist_graph.ainvoke(state)` / `score_jobs()` | `JobScoringService.score_job()` / `.score_batch()` |
| State management | `StrategistState` TypedDict (18 fields) | Function parameters and return values |
| Checkpoint/HITL | `MemorySaver` configuration | None (pure computation, no human interaction) |
| Dependency | `langgraph` package | None (plain `async/await`) |
| Scoring services | Called via placeholder graph nodes | Called directly |

### 1.4 What Does NOT Change

- `fit_score.py` — complete scoring implementation, untouched
- `stretch_score.py` — complete scoring implementation, untouched
- `non_negotiables_filter.py` — complete filtering implementation, untouched
- `scoring_flow.py` — filter batching and result building, untouched
- `score_types.py` — type definitions and interpretation, untouched
- `score_explanation.py` — explanation data structure, untouched
- `score_correlation.py` — validation utilities, untouched
- `strategist_prompts.py` — prompt templates, relocated (see §5)
- All 9 scoring test files (189+ tests) — untouched
- Frontend scoring display — untouched

---

## §2 Dependencies & Prerequisites

### 2.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-008 Scoring Algorithm v0.2 | Core logic | Fit/stretch scoring algorithm specification |
| REQ-005 Database Schema v0.10 | Schema | `persona_jobs.fit_score`, `stretch_score`, `score_details` |
| REQ-009 Provider Abstraction v0.3 | Integration | LLM provider for rationale generation |
| REQ-015 Shared Job Pool v0.1 | Architecture | Scoring writes to `persona_jobs`, not `job_postings` |
| REQ-016 Scouter Service Layer | Integration | Scouter invokes scoring after saving jobs |

### 2.2 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-018 Ghostwriter Service Layer | Integration | Auto-draft trigger when score exceeds threshold |
| REQ-007 §15.4 | Superseded | This document replaces §15.4 entirely |

### 2.3 Cross-REQ Implementation Order

```
REQ-016 (Scouter) ──┐
                     ├──→ REQ-017 (Strategist) ──→ REQ-018 (Ghostwriter)
REQ-019 (Onboarding)┘
```

**This document (REQ-017) must be implemented after REQ-016.** The Scouter invokes scoring after saving jobs — the `JobScoringService` must exist before `JobFetchService.run_poll()` can call it. REQ-019 is independent and can be done in parallel with REQ-016.

---

## §3 Design Decisions

### 3.1 Replacement Architecture: Single Service

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Single `JobScoringService` | ✅ | The scoring pipeline is a linear sequence with one branch (non-negotiables pass/fail). A single class with `score_job()` and `score_batch()` methods is the natural expression. All component services (`fit_score`, `stretch_score`, `non_negotiables_filter`) already exist and are independently tested. |
| Multiple services (one per score type) | — | Over-splitting. Fit and stretch scores are always calculated together. Separating them creates coordination overhead without benefit. |
| Keep LangGraph with real node implementations | — | The graph adds framework overhead (state schemas, routing functions, singleton management) for a linear pipeline. The conditional edges are trivial `if/else` statements, not LLM-driven decisions. |

### 3.2 Rationale Generation: Gemini 2.5 Flash (Above Threshold Only)

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Generate rationale only for jobs scoring ≥ 65 | ✅ | LLM calls cost money. Low-scoring jobs are unlikely to be reviewed by users. Threshold of 65 covers "Good" and "Excellent" fit scores (REQ-008 §3). Jobs below threshold get a generic "Low match" message. |
| Generate rationale for all jobs | — | Wastes tokens on jobs users will never look at. At 100 jobs/poll, this could be $0.10–0.50 per poll cycle. |
| No rationale (scores only) | — | Users need to understand *why* a score is what it is. Numbers without explanation erode trust. |

**Constant:** `RATIONALE_SCORE_THRESHOLD = 65`

### 3.3 Prompt Relocation: `prompts/strategist.py`

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Move to `backend/app/prompts/strategist.py` | ✅ | Prompts are reusable assets. A `prompts/` directory mirrors the pattern being established across all redesigned agents (REQ-018 §3.3). Keeps service files focused on orchestration, not string templates. |
| Keep in `backend/app/agents/strategist_prompts.py` | — | The `agents/` directory is being emptied. Leaving prompts there creates a misleading association with the deleted graph. |
| Inline in service | — | Makes the service file harder to read. Prompt templates are 50+ lines each. |

---

## §4 Current State Inventory

### 4.1 Files to Modify or Delete

| File | Lines | Role | Action |
|------|-------|------|--------|
| `backend/app/agents/strategist_graph.py` | 662 | LangGraph graph: 10 nodes (9 placeholders), routing, singleton | **DELETE** |
| `backend/app/agents/strategist_prompts.py` | 157 | Prompt templates for rationale and non-negotiables explanation | **RELOCATE** to `backend/app/prompts/strategist.py` |
| `backend/app/agents/state.py` | 404 | Contains `StrategistState` TypedDict (~55 lines) | **MODIFY** (remove `StrategistState`) |
| `backend/app/agents/__init__.py` | 196 | Re-exports Strategist graph | **MODIFY** (remove Strategist exports) |

### 4.2 Files That Stay Unchanged

| File | Lines | Role | Why Unchanged |
|------|-------|------|---------------|
| `backend/app/services/fit_score.py` | 373 | Fit score calculation + interpretation | Production-ready, framework-independent |
| `backend/app/services/stretch_score.py` | 612 | Stretch score calculation + interpretation | Production-ready, framework-independent |
| `backend/app/services/non_negotiables_filter.py` | 342 | Non-negotiables filtering (5 checks) | Production-ready, framework-independent |
| `backend/app/services/scoring_flow.py` | 272 | Filter batching + result building | Production-ready, framework-independent |
| `backend/app/services/score_types.py` | 182 | Score type enums + interpretation functions | Type definitions, no framework dependency |
| `backend/app/services/score_explanation.py` | 50 | Explanation data structure | Data class, no framework dependency |
| `backend/app/services/score_correlation.py` | 244 | Score validation utilities | Validation tooling, no framework dependency |

### 4.3 What Moves from `strategist_graph.py` to Service

| Function in `strategist_graph.py` | Status | Destination |
|-------------------------------|--------|-------------|
| `load_persona_embeddings_node()` | Placeholder | `JobScoringService._load_embeddings()` (implement for real) |
| `check_embedding_freshness_node()` | Placeholder | `JobScoringService._check_freshness()` (implement for real) |
| `regenerate_embeddings_node()` | Placeholder | `JobScoringService._regenerate_embeddings()` (implement for real) |
| `filter_non_negotiables_node()` | Placeholder | `JobScoringService._filter_non_negotiables()` → delegates to `non_negotiables_filter.py` |
| `generate_job_embeddings_node()` | Placeholder | `JobScoringService._generate_job_embeddings()` (implement for real) |
| `calculate_fit_score_node()` | Placeholder | `JobScoringService._calculate_fit()` → delegates to `fit_score.py` |
| `calculate_stretch_score_node()` | Placeholder | `JobScoringService._calculate_stretch()` → delegates to `stretch_score.py` |
| `generate_rationale_node()` | Placeholder | `JobScoringService._generate_rationale()` (implement LLM call) |
| `save_scores_node()` | **Real** | `JobScoringService._save_scores()` (logic migrates directly) |
| `trigger_ghostwriter_node()` | Placeholder | `JobScoringService._check_auto_draft()` → invokes Ghostwriter (REQ-018) |
| `is_embedding_stale()` | Real routing | Inline `if` in `score_job()` |
| `check_non_negotiables_pass()` | Real routing | Inline `if` in `score_job()` |
| `check_auto_draft_threshold()` | Real routing | Inline `if` in `score_job()` |
| `score_jobs()` convenience | Real | `JobScoringService.score_batch()` |
| `_build_score_details()` | Real | `JobScoringService._build_score_details()` |
| Graph construction (lines 500+) | Real | **DELETE** (no replacement needed) |

---

## §5 Deletion Plan

### 5.1 Files to Delete

| File | Lines | Reason |
|------|-------|--------|
| `backend/app/agents/strategist_graph.py` | 662 | Entire LangGraph graph. 9 of 10 nodes are placeholders. Real logic migrates to `JobScoringService`. |

### 5.2 Files to Relocate

| From | To | Lines | Reason |
|------|----|-------|--------|
| `backend/app/agents/strategist_prompts.py` | `backend/app/prompts/strategist.py` | 157 | Prompts survive; `agents/` directory is being emptied. Create `prompts/` directory if it doesn't exist. |

### 5.3 Code to Remove from Existing Files

| File | What to Remove | Reason |
|------|---------------|--------|
| `backend/app/agents/state.py` | `StrategistState` TypedDict, `ScoreResult` TypedDict (~55 lines) | Replaced by function parameters. `ScoreResult` moves to `backend/app/services/score_types.py` (co-located with other score type definitions). Update imports across codebase. |
| `backend/app/agents/__init__.py` | Strategist graph imports/re-exports | No longer exists |

---

## §6 New Architecture

### 6.1 Service Overview

```
JobScoringService
  score_job(db, persona_id, job_posting_id)
  score_batch(db, persona_id, job_posting_ids)
      │
      ├── non_negotiables_filter.py  (existing, unchanged)
      ├── fit_score.py               (existing, unchanged)
      ├── stretch_score.py           (existing, unchanged)
      ├── scoring_flow.py            (existing, unchanged)
      └── prompts/strategist.py      (relocated from agents/)
```

### 6.2 `JobScoringService` (`backend/app/services/job_scoring_service.py`)

**Responsibility:** Orchestrate the scoring pipeline for a single job or batch.

```python
RATIONALE_SCORE_THRESHOLD = 65

class JobScoringService:
    """Scores job postings against a user's persona."""

    async def score_job(
        self,
        db: AsyncSession,
        persona_id: uuid.UUID,
        job_posting_id: uuid.UUID,
    ) -> ScoreResult:
        """Score a single job against a persona.

        Pipeline:
        1. Load persona data + embeddings
        2. Check embedding freshness → regenerate if stale
        3. Filter non-negotiables → early exit if failed
        4. Generate job embeddings (if not cached)
        5. Calculate fit score (5 components, weighted)
        6. Calculate stretch score (3 components, weighted)
        7. Generate LLM rationale (only if fit_score >= RATIONALE_SCORE_THRESHOLD)
        8. Build score_details JSONB payload
        9. Save to persona_jobs

        Returns:
            ScoreResult with fit_score, stretch_score, explanation,
            filtered_reason, and score_details.
        """

    async def score_batch(
        self,
        db: AsyncSession,
        persona_id: uuid.UUID,
        job_posting_ids: list[uuid.UUID],
    ) -> list[ScoreResult]:
        """Score multiple jobs. Loads persona embeddings once, reuses for all."""

    async def rescore_all_discovered(
        self,
        db: AsyncSession,
        persona_id: uuid.UUID,
    ) -> list[ScoreResult]:
        """Re-score all Discovered jobs for a persona.

        Called after persona update (new skill, changed non-negotiables).
        Regenerates persona embeddings first, then rescores all active jobs.
        """
```

**Key design notes:**
- `score_batch()` loads persona embeddings once, then loops `_score_single()` for each job
- `rescore_all_discovered()` is the entry point for persona-update-triggered rescoring
- Embedding freshness check uses `persona_embedding_version` counter
- Rationale generation is conditional on `fit_score >= RATIONALE_SCORE_THRESHOLD` (65)
- Auto-draft trigger calls Ghostwriter (REQ-018) when `fit_score >= auto_draft_threshold` (90)

---

## §7 Behavioral Specification

### 7.1 Single Job Scoring Pipeline

```
Input: persona_id + job_posting_id
    │
    ▼
1. Load persona data + embeddings
    │
    ▼
2. Embedding freshness check
    ├── Stale → regenerate embeddings, then continue
    └── Fresh → continue
    │
    ▼
3. Non-negotiables filter
    ├── FAIL → save with filtered_reason, return early
    └── PASS → continue
    │
    ▼
4. Generate job embeddings (if not cached on job_postings)
    │
    ▼
5. Calculate fit score (0–100)
    │  Components: hard_skills (40%), soft_skills (15%),
    │  experience (25%), role_title (10%), logistics (10%)
    │
    ▼
6. Calculate stretch score (0–100)
    │  Components: target_role (50%), target_skills (40%),
    │  growth_trajectory (10%)
    │
    ▼
7. Generate rationale (LLM, only if fit_score ≥ 65)
    │  Below threshold: generic "Low match" message
    │
    ▼
8. Build score_details JSONB
    │
    ▼
9. Save to persona_jobs
    │
    ▼
10. Check auto-draft threshold
    ├── fit_score ≥ 90 → invoke Ghostwriter (REQ-018)
    └── Below → done
```

### 7.2 Embedding Freshness (Cold Start Prevention)

When persona data changes (new skill, updated work history, changed non-negotiables):

1. `persona_embedding_version` is incremented on the persona record
2. `rescore_all_discovered()` is called
3. Method detects version mismatch → regenerates persona embeddings
4. All active jobs are rescored with fresh embeddings

This prevents the "cold start" problem (REQ-007 §10.4.1) where new skills don't appear in job matching.

### 7.3 Non-Negotiables Filtering

Delegates to existing `non_negotiables_filter.py`. Five checks:

| Check | Rule |
|-------|------|
| Remote preference | Remote Only → must be Remote; Hybrid OK → not Onsite |
| Minimum salary | `job.salary_max >= persona.minimum_base_salary` (pass if undisclosed) |
| Commutable cities | `job.location in persona.commutable_cities` OR Remote |
| Industry exclusions | `job.company_industry not in persona.industry_exclusions` |
| Visa sponsorship | Pass if offered or undisclosed; fail only if explicitly "No" |

Jobs that fail are saved with `filtered_reason` but no fit/stretch scores.

---

## §8 Prompt Specifications

### 8.1 Score Rationale Prompt (relocated from `strategist_prompts.py`)

**System prompt:**
```
You are a career match analyst explaining job fit to a job seeker.

Your task: Given the match data, write a 2-3 sentence rationale that:
1. Highlights the strongest alignment (what makes this a good/poor fit)
2. Notes any significant gaps or stretch opportunities
3. Uses specific skill names, not vague language

Tone: Direct, helpful, specific. Avoid generic phrases like "great opportunity"
or "good match."

Output format: Plain text, 2-3 sentences max.
```

**User prompt template:** See REQ-007 §7.6.1 (unchanged).

**Model:** Gemini 2.5 Flash (cost-optimized for high-volume generation)

### 8.2 Non-Negotiables Explanation Prompt (relocated from `strategist_prompts.py`)

**System prompt:**
```
You explain why a job posting failed the user's non-negotiable requirements.

Be direct and factual. Don't apologize or soften the message.
One sentence per failed requirement.
```

**User prompt template:** See REQ-007 §7.6.2 (unchanged).

---

## §9 Configuration & Environment

No new environment variables required. Uses existing configuration:

| Variable | Used For |
|----------|----------|
| `LLM_PROVIDER` | Rationale generation model selection |
| `EMBEDDING_MODEL` | Persona and job embedding generation |
| `EMBEDDING_PROVIDER` | Embedding provider (OpenAI) |

New constant (code-level, not env var):

| Constant | Value | Purpose |
|----------|-------|---------|
| `RATIONALE_SCORE_THRESHOLD` | 65 | Only generate LLM rationale for jobs scoring ≥ this |

---

## §10 Migration Path

### 10.1 Implementation Order

| Step | Action | Depends On |
|------|--------|------------|
| 1 | Create `backend/app/prompts/` directory and `__init__.py` | Nothing |
| 2 | Move `strategist_prompts.py` → `prompts/strategist.py` | Step 1 |
| 3 | Create `JobScoringService` with `score_job()`, `score_batch()`, `rescore_all_discovered()` | Step 2 + existing scoring services |
| 4 | Update API endpoints (`/job-postings/rescore`, Scouter integration) to call `JobScoringService` | Step 3 |
| 5 | Write new unit tests for `JobScoringService` | Step 3 |
| 6 | Delete `strategist_graph.py` | Steps 4 + 5 passing |
| 7 | Remove `StrategistState` from `state.py` | Step 6 |
| 8 | Update `__init__.py` exports | Step 6 |

### 10.2 Rollback Strategy

Code-only changes. No database schema modifications. Git revert restores previous state.

---

## §11 Test Impact Analysis

### 11.1 Backend Tests

| Test File | Tests | Action | Reason |
|-----------|-------|--------|--------|
| `tests/unit/test_strategist_graph.py` | 85 | **DELETE** | Tests LangGraph graph topology, placeholder node behavior, routing functions. All logic migrates to service test. |
| `tests/unit/test_scoring_flow.py` | 26 | **KEEP** | Tests `scoring_flow.py` (filter batching, result building). Framework-independent. |
| `tests/unit/test_fit_score_aggregation.py` | 26 | **KEEP** | Tests fit score weighted aggregation. Framework-independent. |
| `tests/unit/test_fit_score_interpretation.py` | 32 | **KEEP** | Tests fit score label mapping. Framework-independent. |
| `tests/unit/test_fit_score_weights.py` | 4 | **KEEP** | Tests weight sum validation. Framework-independent. |
| `tests/unit/test_stretch_score_aggregation.py` | 25 | **KEEP** | Tests stretch score weighted aggregation. Framework-independent. |
| `tests/unit/test_stretch_score_interpretation.py` | 32 | **KEEP** | Tests stretch score label mapping. Framework-independent. |
| `tests/unit/test_stretch_score_weights.py` | 4 | **KEEP** | Tests weight sum validation. Framework-independent. |
| `tests/unit/test_non_negotiables_filter.py` | 40 | **KEEP** | Tests all 5 filter checks. Framework-independent. |
| `tests/unit/test_batch_scoring.py` | ~9 | **KEEP** | Tests batch scoring optimization (REQ-008 §10.1). Framework-independent. |
| `tests/unit/test_score_correlation.py` | ~22 | **KEEP** | Tests score validation utilities (REQ-008). Framework-independent. |

**Summary:** DELETE 85 tests (graph topology), KEEP ~220 tests (scoring logic), CREATE ~30 new service tests.

### 11.2 New Tests to Create

| Test File | Est. Tests | Coverage |
|-----------|-----------|----------|
| `tests/unit/test_job_scoring_service.py` | ~30 | `score_job()` pipeline, `score_batch()` optimization, `rescore_all_discovered()`, embedding freshness check, rationale threshold gating, auto-draft trigger, error handling |

### 11.3 Test Migration Notes

- Graph topology tests → **deleted** (no graph)
- Placeholder node tests → **replaced** by real integration tests in `test_job_scoring_service.py`
- Routing function tests → **replaced** by inline `if/else` coverage in service tests
- `_build_score_details()` tests → migrate to `test_job_scoring_service.py`
- `score_jobs()` convenience tests → replaced by `score_batch()` tests

---

## §12 E2E Test Impact

| Spec File | Tests | Action | Reason |
|-----------|-------|--------|--------|
| `frontend/tests/e2e/job-discovery.spec.ts` | 25 | **KEEP** | Tests score display in job dashboard UI. API mocks unchanged. |
| `frontend/tests/e2e/persona-update.spec.ts` | 16 | **KEEP** | Tests rescore trigger after persona edit. API contract unchanged. |

**E2E impact is zero** because the frontend has no knowledge of whether scoring happens in a LangGraph graph or a plain service. All API contracts are preserved.

---

## §13 Frontend Impact

**No frontend changes required.** Scoring results are written to `persona_jobs` and returned via existing API endpoints. The `score_details` JSONB structure is unchanged.

---

## §14 Open Questions & Future Considerations

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | Should embedding generation be a separate service? | Deferred | Currently inline in `JobScoringService`. If embedding generation becomes complex (multiple providers, caching strategies), extract to `EmbeddingService`. |
| 2 | Should rationale generation be batched? | Deferred | Currently one LLM call per job. If batch sizes grow (100+ jobs), batch rationale generation could reduce latency. |
| 3 | Should auto-draft be wired at MVP? | **No** | REQ-018 §3.2 explicitly defers auto-draft to post-MVP. `_check_auto_draft()` is a no-op at MVP. The enum value `TriggerType.AUTO_DRAFT` exists but is never called. |

---

## §15 Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-23 | 0.2 | Audit fixes: added 2 missing test files to §11 (test_batch_scoring, test_score_correlation), fixed ScoreResult destination to score_types.py, fixed E2E test counts, added cross-REQ implementation order to §2. |
| 2026-02-23 | 0.1 | Initial draft. Specifies replacement of LangGraph Strategist with `JobScoringService`. |
