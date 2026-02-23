# REQ-016: Scouter Service Layer Redesign

**Status:** Draft
**Version:** 0.1
**Supersedes:** REQ-007 §6 (Scouter Agent), §15.3 (Scouter Agent Graph)
**PRD Reference:** §4.2 Scouter
**Last Updated:** 2026-02-23

---

## §1 Overview & Motivation

### 1.1 What This Document Does

This document specifies the redesign of Zentropy Scout's Scouter from a LangGraph `StateGraph` agent into plain async service functions. It replaces REQ-007 §6 (Scouter Agent) and §15.3 (Scouter Agent Graph) in their entirety.

### 1.2 Why the Redesign Is Needed

The Scouter is implemented as a 10-node LangGraph `StateGraph` in `scouter_graph.py` (895 lines). Code review (2026-02-23) found:

1. **All conditional edges are deterministic** — `check_new_jobs()` checks `len(state["processed_jobs"]) > 0`. No LLM decides routing.
2. **HITL checkpointing is configured but never triggered** — `checkpoint.py` provides `request_human_input()` and `resume_from_checkpoint()` but the Scouter never calls them.
3. **Three nodes are placeholders** — `extract_skills_and_culture()` returns empty dicts, `invoke_strategist_node()` logs and returns, `notify_surfacing_worker_node()` logs only.
4. **The graph adds overhead for zero benefit** — State schema management, checkpoint infrastructure, LangGraph dependency, and `MemorySaver` instantiation all serve no purpose for a batch data pipeline.

The Scouter is a **batch data pipeline**: fetch → normalize → deduplicate → enrich → save → score. This is a sequence of function calls, not a decision graph.

### 1.3 What Changes

| Aspect | Before | After |
|--------|--------|-------|
| Architecture | LangGraph `StateGraph` with 10 nodes | 3 async service classes + 1 repository |
| Entry point | `scouter_graph.ainvoke(state)` | `JobFetchService.run_poll(user_id, persona_id)` |
| State management | `ScouterState` TypedDict (12 fields) | Function parameters and return values |
| Checkpoint/HITL | `MemorySaver` + `checkpoint.py` | None (batch pipeline, no human interaction) |
| Dependency | `langgraph` package | None (plain `async/await`) |
| Error handling | `error_sources` in state dict | `Scouter errors` module (unchanged) |

### 1.4 What Does NOT Change

- Source adapters (Adzuna, RemoteOK, TheMuse, USAJobs) — untouched
- Ghost detection service — untouched
- Shared pool deduplication service — untouched
- Scouter error handling infrastructure (`scouter_errors.py`) — untouched
- API endpoints (`/job-postings/ingest`, `/refresh`) — untouched
- Frontend job discovery UI — untouched

---

## §2 Dependencies & Prerequisites

### 2.1 This Document Depends On

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-003 Job Posting Schema v0.4 | Entity definitions | Ghost detection, dedup rules |
| REQ-005 Database Schema v0.10 | Schema | `job_postings`, `persona_jobs`, `job_sources` tables |
| REQ-006 API Contract v0.8 | Integration | `/job-postings/ingest`, `/refresh` endpoints |
| REQ-008 Scoring Algorithm v0.2 | Integration | Strategist invocation after save |
| REQ-015 Shared Job Pool v0.1 | Architecture | Pool check, persona_jobs linking |

### 2.2 Other Documents Depend On This

| Document | Dependency Type | Notes |
|----------|----------------|-------|
| REQ-017 Strategist Service Layer | Integration | Scouter invokes scoring after saving new jobs |
| REQ-007 §15.3 | Superseded | This document replaces §15.3 entirely |

---

## §3 Design Decisions

### 3.1 Replacement Architecture: Three Services + One Repository

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Three focused services + repository | ✅ | Mirrors the natural pipeline stages: fetch → enrich → store. Each service has a single responsibility, is independently testable, and has no framework dependency. |
| Single monolithic service | — | Would create a 600+ line God service. Harder to test individual stages in isolation. |
| Keep LangGraph but simplify | — | LangGraph provides zero value for this pipeline. Keeping it means maintaining dependency, state schemas, and checkpoint infrastructure for a batch job that never needs them. |
| Event-driven with message queue | — | Over-engineering for MVP scale. Adding Celery/Redis for 4 sequential function calls is unnecessary. Can be added later if scaling demands it. |

### 3.2 Extraction Implementation: Gemini 2.5 Flash

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Gemini 2.5 Flash for extraction | ✅ | Cost-optimized for high-volume extraction (~$0.001/job). Currently placeholder — will be the first real LLM call in the Scouter pipeline. Provider abstraction layer (REQ-009) handles the adapter. |
| Claude Haiku | — | Higher cost per call. REQ-007 §11.2 originally specified Haiku, but Gemini Flash is cheaper for simple extraction tasks. |
| No extraction (manual entry only) | — | Defeats the purpose of automated job discovery. |

### 3.3 State Passing: Function Parameters Instead of TypedDict

| Options Considered | Chosen | Rationale |
|-------------------|--------|-----------|
| Function parameters + return values | ✅ | Type-safe, no runtime schema overhead, IDE autocomplete works naturally, no state mutation bugs. |
| Dataclass for pipeline context | — | Viable but adds indirection. The pipeline has 6 steps with clear input/output — explicit parameters are more readable. |
| Keep `ScouterState` TypedDict | — | Carries 12 fields through every function even when most are unused per step. TypedDict is a LangGraph convention, not a Python best practice for pipelines. |

---

## §4 Current State Inventory

### 4.1 Files to Modify or Delete

| File | Lines | Role | Action |
|------|-------|------|--------|
| `backend/app/agents/scouter_graph.py` | 895 | LangGraph graph: 10 nodes, conditional routing, singleton | **DELETE** |
| `backend/app/agents/scouter.py` | 237 | Trigger helpers, state factory, merge utility | **KEEP** (refactor) |
| `backend/app/agents/checkpoint.py` | 211 | `MemorySaver`, `create_graph_config`, HITL utilities | **DELETE** (shared with all agents — see §4.3) |
| `backend/app/agents/state.py` | 404 | `ScouterState`, `BaseAgentState`, other agent states | **MODIFY** (remove `ScouterState`) |
| `backend/app/agents/__init__.py` | 196 | Re-exports all agents | **MODIFY** (remove Scouter graph exports) |

### 4.2 Files That Stay Unchanged

| File | Lines | Role | Why Unchanged |
|------|-------|------|---------------|
| `backend/app/services/scouter_errors.py` | 393 | Error types, retry logic, processing metadata | Framework-independent error handling |
| `backend/app/services/ghost_detection.py` | ~200 | Ghost score calculation | Called by service instead of graph node |
| `backend/app/services/deduplication.py` | ~300 | Shared pool dedup | Called by repository instead of graph node |
| Source adapters (Adzuna, etc.) | ~800 | API clients for job sources | Called by fetch service instead of graph node |

### 4.3 Note on `checkpoint.py` Deletion

`checkpoint.py` is shared infrastructure used by all LangGraph agents. It should only be deleted when **all** agents have been redesigned (REQ-016 through REQ-019). Until then, the file remains. This document marks it for deletion; the last REQ to complete executes the deletion.

### 4.4 What Moves from `scouter_graph.py` to Services

| Function in `scouter_graph.py` | Lines | Destination |
|-------------------------------|-------|-------------|
| `get_source_adapter()` | 75–94 | `JobFetchService._get_adapter()` |
| `extract_skills_and_culture()` | 102–137 | `JobEnrichmentService.extract()` (implement for real) |
| `_compute_description_hash()` | 145–147 | `JobPoolRepository._compute_hash()` |
| `_build_dedup_job_data()` | 150–181 | `JobPoolRepository._build_dedup_data()` |
| `fetch_sources_node()` | 206–277 | `JobFetchService.fetch_from_sources()` |
| `merge_results_node()` | 280–298 | Keep `scouter.py:merge_results()` (already exists) |
| `_check_single_job_in_pool()` | 301–348 | `JobPoolRepository.check_pool()` |
| `check_shared_pool_node()` | 351–417 | `JobPoolRepository.partition_new_and_existing()` |
| `_resolve_source_id()` | 420–456 | `JobPoolRepository.resolve_source_id()` |
| `extract_skills_node()` | 474–522 | `JobEnrichmentService.enrich_batch()` |
| `calculate_ghost_score_node()` | 525–579 | `JobEnrichmentService.calculate_ghost_scores()` |
| `_save_single_job()` | 582–621 | `JobPoolRepository.save_job()` |
| `_link_existing_job()` | 624–665 | `JobPoolRepository.link_existing_job()` |
| `save_to_pool_node()` | 668–729 | `JobPoolRepository.save_batch()` |
| `update_poll_state_node()` | 780–799 | `JobFetchService.update_poll_state()` |
| Graph construction (807–895) | — | **DELETE** (no replacement needed) |

---

## §5 Deletion Plan

### 5.1 Files to Delete

| File | Lines | Reason |
|------|-------|--------|
| `backend/app/agents/scouter_graph.py` | 895 | Entire LangGraph graph. All logic migrates to 3 services + 1 repository. |

### 5.2 Code to Remove from Existing Files

| File | What to Remove | Reason |
|------|---------------|--------|
| `backend/app/agents/state.py` | `ScouterState` TypedDict (~35 lines) | Replaced by function parameters |
| `backend/app/agents/__init__.py` | Scouter graph imports/re-exports | No longer exists |
| `backend/app/agents/scouter.py` | `create_scouter_state()` factory (~25 lines) | No more `ScouterState` to construct |

### 5.3 What to Keep in `scouter.py`

After refactoring, `scouter.py` retains only trigger detection helpers:

| Function | Lines | Why Keep |
|----------|-------|----------|
| `MANUAL_REFRESH_PATTERNS` | 45–58 | Used by Chat Agent to detect "Find new jobs" intent |
| `should_poll()` | 66–83 | Used by scheduler to check if polling is due |
| `is_manual_refresh_request()` | 86–101 | Used by Chat Agent for intent classification |
| `is_source_added_trigger()` | 104–124 | Used by source preference API |
| `POLLING_FREQUENCY_INTERVALS` | 133–137 | Used by poll state update logic |
| `DEFAULT_POLLING_INTERVAL` | 140 | Used by poll state update logic |
| `merge_results()` | 143–168 | Used by `JobFetchService` (pure utility) |
| `calculate_next_poll_time()` | 171–184 | Used by poll state update logic |
| `record_source_error()` | 215–237 | Used by fetch error handling |

**Remove from `scouter.py`:**

| Function | Lines | Why Remove |
|----------|-------|------------|
| `create_scouter_state()` | 187–212 | Creates `ScouterState` TypedDict — no longer needed |

---

## §6 New Architecture

### 6.1 Service Overview

```
JobFetchService                    JobEnrichmentService
  fetch_from_sources()               extract_skills_and_culture()
  update_poll_state()                 calculate_ghost_scores()
         │                                    │
         └──── raw jobs ──────┬───────────────┘
                              │
                     JobPoolRepository
                       partition_new_and_existing()
                       save_batch()
                       link_existing_jobs()
                              │
                     [Invoke Strategist]
```

### 6.2 `JobFetchService` (`backend/app/services/job_fetch_service.py`)

**Responsibility:** Fetch jobs from enabled sources, merge results, update poll state.

```python
class JobFetchService:
    """Fetches job postings from configured external sources."""

    async def run_poll(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        persona_id: uuid.UUID,
        enabled_sources: list[str],
        polling_frequency: str = "daily",
    ) -> PollResult:
        """Execute a complete polling cycle.

        Steps:
        1. Fetch jobs from all enabled sources (parallel)
        2. Merge results into flat list
        3. Partition into new vs existing pool jobs
        4. Enrich new jobs (extraction + ghost scores)
        5. Save new jobs and link existing jobs
        6. Update poll state timestamps
        7. Invoke Strategist for scoring

        Returns:
            PollResult with counts of new, existing, and errored jobs.
        """

    async def fetch_from_sources(
        self,
        enabled_sources: list[str],
        search_params: dict,
    ) -> tuple[list[dict], list[str]]:
        """Fetch from all sources in parallel, return (jobs, error_sources)."""

    async def update_poll_state(
        self,
        db: AsyncSession,
        persona_id: uuid.UUID,
        polling_frequency: str,
    ) -> None:
        """Update last_polled_at and calculate next_poll_at."""
```

**Key design notes:**
- `run_poll()` is the single entry point replacing `scouter_graph.ainvoke()`
- Parallel source fetching via `asyncio.gather()` with `return_exceptions=True`
- Fail-forward: source errors are logged, other sources continue
- Returns a `PollResult` dataclass instead of mutating state

### 6.3 `JobEnrichmentService` (`backend/app/services/job_enrichment_service.py`)

**Responsibility:** Extract structured data from raw job text using LLM, calculate ghost scores.

```python
class JobEnrichmentService:
    """Enriches raw job postings with extracted skills and ghost detection."""

    async def extract_skills_and_culture(
        self,
        raw_text: str,
        provider: LLMProvider,
    ) -> ExtractionResult:
        """Extract skills and culture text from a single job posting.

        Uses Gemini 2.5 Flash (or configured extraction model) for
        structured extraction. Truncates input to 15,000 chars.

        Returns:
            ExtractionResult with skills list and culture_text string.
        """

    async def enrich_batch(
        self,
        jobs: list[dict],
        provider: LLMProvider,
    ) -> list[dict]:
        """Enrich a batch of jobs with extraction + ghost scores.

        Calls extract_skills_and_culture() for each job, then
        calculate_ghost_score() for each. Errors are recorded per-job
        but do not fail the batch.
        """

    async def calculate_ghost_scores(
        self,
        db: AsyncSession,
        jobs: list[dict],
    ) -> list[dict]:
        """Calculate ghost detection scores for a batch of jobs."""
```

**Key design notes:**
- `extract_skills_and_culture()` is the first real LLM call — currently a placeholder in `scouter_graph.py`
- Uses provider abstraction layer (REQ-009) for model selection
- Extraction prompt from REQ-007 §6.4 (skills + culture_text JSON)
- Ghost detection delegates to existing `ghost_detection.py` service
- Per-job error handling: extraction failure doesn't block the batch

### 6.4 `JobPoolRepository` (`backend/app/repositories/job_pool_repository.py`)

**Responsibility:** Shared pool operations — check, save, link, deduplicate.

```python
class JobPoolRepository:
    """Manages the shared job posting pool (REQ-015)."""

    async def partition_new_and_existing(
        self,
        db: AsyncSession,
        jobs: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        """Split jobs into new (not in pool) and existing (already in pool).

        Uses two-tier dedup:
        1. source_id + external_id (exact match)
        2. description_hash (cross-source dedup)

        Also deduplicates within the batch itself.
        """

    async def save_batch(
        self,
        db: AsyncSession,
        new_jobs: list[dict],
        persona_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """Save new jobs to pool and create persona_jobs links."""

    async def link_existing_jobs(
        self,
        db: AsyncSession,
        existing_jobs: list[dict],
        persona_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        """Create persona_jobs links for jobs already in pool."""

    async def resolve_source_id(
        self,
        db: AsyncSession,
        source_name: str,
    ) -> uuid.UUID:
        """Look up or auto-create a JobSource record. Allowlist enforced."""
```

**Key design notes:**
- Logic migrates directly from `scouter_graph.py` helper functions
- Transaction management: `save_batch()` commits once after all saves
- Allowlist: only known sources (Adzuna, RemoteOK, TheMuse, USAJobs) can be auto-created
- Description hash: SHA-256 of normalized text for cross-source dedup

---

## §7 Behavioral Specification

### 7.1 Poll Cycle Behavior

The `run_poll()` method executes these steps in order:

1. **Fetch** — Call all enabled source adapters in parallel. Record errors per-source.
2. **Merge** — Flatten multi-source results into a single list with `source_name` field added.
3. **Partition** — Check each job against shared pool. Split into `new_jobs` and `existing_pool_jobs`.
4. **Enrich new jobs** — For each new job: extract skills/culture (LLM), calculate ghost score.
5. **Save** — Save new jobs to pool via `deduplicate_and_save()`. Create `persona_jobs` links for existing jobs.
6. **Update poll state** — Set `last_polled_at = now()`, calculate `next_poll_at` from frequency.
7. **Invoke Strategist** — Call scoring service for all newly saved/linked job IDs (REQ-017).

### 7.2 Error Handling (unchanged from current)

| Error | Handling |
|-------|----------|
| Source API down | Log error, skip source, continue with others |
| Rate limit hit | Record `retry_after`, skip source, continue |
| Extraction fails per job | Record in `ProcessingMetadata`, save job without extraction |
| Ghost score fails per job | Record in `ProcessingMetadata`, save job with null ghost score |
| Pool save fails per job | Log error, skip job, continue with others |

### 7.3 Trigger Conditions (unchanged)

| Trigger | Source | Detection |
|---------|--------|-----------|
| Scheduled poll | Background worker | `should_poll(next_poll_at)` returns True |
| Manual refresh | User message | `is_manual_refresh_request(message)` matches |
| Source added | Settings change | `is_source_added_trigger(prev, curr)` detects new source |

---

## §8 Prompt Specifications

### 8.1 Extraction Prompt (from REQ-007 §6.4 — now implemented)

The extraction prompt moves from `scouter_graph.py:extract_skills_and_culture()` (currently a placeholder) to `JobEnrichmentService.extract_skills_and_culture()`:

```
Analyze this job posting and extract:

1. SKILLS: For each skill mentioned:
   - skill_name: The skill (normalize common variations)
   - skill_type: "Hard" (technical) or "Soft" (interpersonal)
   - is_required: true if explicitly required, false if nice-to-have
   - years_requested: number if specified, null otherwise

2. CULTURE_TEXT: Extract ONLY text about company culture, values, team environment,
   benefits, and "About Us" content. Do NOT include requirements, responsibilities,
   or technical skills in this section.

Job posting:
{description}

Return JSON:
{
  "skills": [...],
  "culture_text": "..."
}
```

**Model:** Gemini 2.5 Flash (via provider abstraction layer)
**Input truncation:** 15,000 characters at word boundary
**Input sanitization:** `sanitize_llm_input()` from `llm_sanitization.py`

---

## §9 Configuration & Environment

No new environment variables required. The Scouter uses existing configuration:

| Variable | Used For |
|----------|----------|
| `LLM_PROVIDER` | Extraction model selection (via provider abstraction) |
| `EMBEDDING_MODEL` | Not used by Scouter directly (used by Strategist) |
| Source API keys (Adzuna, etc.) | Source adapter authentication |

---

## §10 Migration Path

### 10.1 Implementation Order

| Step | Action | Depends On |
|------|--------|------------|
| 1 | Create `JobPoolRepository` with methods migrated from `scouter_graph.py` helpers | Nothing |
| 2 | Create `JobEnrichmentService` with real extraction implementation | Provider abstraction (REQ-009, already complete) |
| 3 | Create `JobFetchService` with `run_poll()` orchestrator | Steps 1 + 2 |
| 4 | Update API endpoints to call `JobFetchService` instead of `scouter_graph` | Step 3 |
| 5 | Write new unit tests for all 3 services + repository | Steps 1–3 |
| 6 | Delete `scouter_graph.py` | Steps 4 + 5 passing |
| 7 | Remove `ScouterState` from `state.py` | Step 6 |
| 8 | Remove `create_scouter_state()` from `scouter.py` | Step 6 |
| 9 | Update `__init__.py` exports | Step 6 |

### 10.2 Rollback Strategy

If issues are discovered after migration:
1. `scouter_graph.py` deletion is a single git commit — revert restores it
2. API endpoints switch is a single-line change per endpoint
3. No database schema changes — rollback is code-only

---

## §11 Test Impact Analysis

### 11.1 Backend Tests

| Test File | Tests | Action | Reason |
|-----------|-------|--------|--------|
| `tests/unit/test_scouter_graph.py` | 42 | **DELETE** | Tests LangGraph graph topology, node functions, routing. All logic migrates to service tests. |
| `tests/unit/test_scouter_agent.py` | 20 | **KEEP** | Tests trigger detection (`should_poll`, `is_manual_refresh_request`), `merge_results`, `calculate_next_poll_time`. These helpers remain in `scouter.py`. |
| `tests/unit/test_scouter_error_handling.py` | 25 | **KEEP** | Tests `scouter_errors.py` (error types, retry logic, processing metadata). Framework-independent. |

### 11.2 New Tests to Create

| Test File | Est. Tests | Coverage |
|-----------|-----------|----------|
| `tests/unit/test_job_fetch_service.py` | ~20 | `run_poll()`, `fetch_from_sources()`, parallel error handling, poll state update |
| `tests/unit/test_job_enrichment_service.py` | ~15 | `extract_skills_and_culture()` (real LLM mock), `enrich_batch()`, ghost score delegation |
| `tests/unit/test_job_pool_repository.py` | ~25 | `partition_new_and_existing()`, `save_batch()`, `link_existing_jobs()`, dedup logic, source resolution |

### 11.3 Test Migration Notes

Most test logic from `test_scouter_graph.py` migrates to the new service/repository tests:
- Graph topology tests → **deleted** (no graph)
- `fetch_sources_node` tests → `test_job_fetch_service.py`
- `check_shared_pool_node` tests → `test_job_pool_repository.py`
- `extract_skills_node` tests → `test_job_enrichment_service.py`
- `save_to_pool_node` tests → `test_job_pool_repository.py`
- Helper function tests → `test_job_pool_repository.py`

---

## §12 E2E Test Impact

| Spec File | Tests | Action | Reason |
|-----------|-------|--------|--------|
| `frontend/tests/e2e/job-discovery.spec.ts` | 20 | **KEEP** (minor mock updates) | Tests job dashboard UI, not backend implementation. API mocks may need path updates if endpoints change. |
| `frontend/tests/e2e/add-job.spec.ts` | ~10 | **KEEP** | Tests manual job ingest flow. Endpoint unchanged. |

**E2E impact is minimal** because E2E tests mock all API calls. The frontend has no knowledge of whether the backend uses LangGraph or plain services.

---

## §13 Frontend Impact

**No frontend changes required.** The Scouter redesign is entirely backend. All API endpoints retain their existing contracts:

| Endpoint | Contract Change |
|----------|----------------|
| `POST /api/v1/refresh` | None — still triggers a poll cycle |
| `POST /api/v1/job-postings/ingest` | None — still accepts manual job submission |
| `GET /api/v1/job-postings` | None — response shape unchanged |
| `GET /api/v1/job-postings/{id}` | None — response shape unchanged |

---

## §14 Open Questions & Future Considerations

| # | Question | Status | Notes |
|---|----------|--------|-------|
| 1 | Should `JobFetchService.run_poll()` be called from a background worker? | Deferred | Current implementation runs inline on API call. Background worker (Celery/ARQ) is a future optimization for Render deployment (backlog item #4). |
| 2 | Should extraction results be cached in the shared pool? | Yes (REQ-015) | A job enriched once should not be re-extracted when discovered by another user. `job_postings.extracted_skills` and `culture_text` are shared pool columns. |
| 3 | What happens to `checkpoint.py` when all 4 agents are redesigned? | Delete entirely | See §4.3. Last REQ to complete handles deletion. Chat Agent (backlog #11, deferred) may still need it if LangGraph is kept for chat. |

---

## §15 Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-23 | 0.1 | Initial draft. Specifies replacement of LangGraph Scouter with 3 services + 1 repository. |
