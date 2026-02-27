# Zentropy Scout — LLM Agent Redesign Implementation Plan

**Created:** 2026-02-23
**Last Updated:** 2026-02-27
**Status:** ✅ Complete
**Destination:** `docs/plan/llm_redesign_plan.md`

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Load the relevant REQ section via `req-reader` subagent before each task
3. Each task = one commit, sized ≤ 50k tokens of context (TDD + review + fixes included)
4. **Subtask workflow:** Run affected tests → linters → commit → compact (NO push)
5. **Phase-end workflow:** Run full test suite (backend + frontend + E2E) → push → compact
6. After each task: update status (⬜ → ✅), commit, STOP and ask user

**Workflow pattern (differs from previous plans):**

| Action | Subtask (§1–§17, §19) | Phase Gate (§4, §8, §12, §18, §20) |
|--------|----------------------|-------------------------------------|
| Tests | Affected files only | Full backend + frontend + E2E |
| Linters | Pre-commit hooks (~25-40s) | Pre-commit + pre-push hooks |
| Git | `git commit` only | `git push` |
| Context | Compact after commit | Compact after push |

**Why:** Pushes trigger pre-push hooks (full pytest + vitest, ~90-135s). By deferring pushes to phase boundaries, we save ~90-135s per subtask while maintaining quality gates.

**Context management for fresh sessions:** Each subtask is self-contained. A fresh context window needs:
1. This plan (find current task by status icon)
2. The relevant REQ document (via `req-reader` — REQ number listed in task)
3. The specific files listed in the task description
4. No prior conversation history required

---

## Pre-Implementation Setup (Phase 0)

**Status:** ⬜ Incomplete

*Local-only changes to .claude/ workflow infrastructure (gitignored). Complete before Phase 1. These are OPTIONAL quality-of-life tweaks — the plan works without them since the workflow tables in each phase already specify the test/commit pattern.*

#### Changes Required (Optional)

1. **`zentropy-planner` SKILL.md** (`.claude/skills/zentropy-planner/SKILL.md`) — Modify the 8-step workflow:
   - Step 3: "Run full test suite" → "Run affected tests only (files listed in task description)"
   - Step 7 (COMPLETE): Commit only (remove push option from this step)
   - Step 8 (STOP): Options become "Continue to next subtask" / "Compact first" / "Stop" (no "Push" for subtasks)
   - Add: "Phase Gate" task type — runs full test suite → push → compact

2. **`test-runner` agent** (`.claude/agents/test-runner.md`) — Add explicit modes:
   - **Fast mode** (subtasks): `pytest <specific_files> -v` — runs only the test files listed in the task
   - **Full mode** (phase gates): `pytest tests/ -v && npm run test:run && npx playwright test`

3. **No changes needed:** Pre-commit hooks (already correct: commit = linters, push = full tests), settings.json, other agents

**Skip condition:** If you'd rather dive straight into Phase 1, these changes can be deferred — the per-task workflow tables already specify the correct test/commit pattern.

---

## Dependency Chain

```
Phase 1: Scouter (REQ-016)
    │
    ↓
Phase 2: Strategist (REQ-017)  ← Scouter invokes scoring after saving jobs
    │
    ↓
Phase 3: Ghostwriter (REQ-018) ← auto-draft trigger from scoring (deferred to post-MVP)
    │
    ↓
Phase 4: Onboarding (REQ-019)  ← independent, done last (most complex, frontend changes)
    │
    ↓
Phase 5: Cross-Agent Verification
```

**Ordering rationale:** Phases 1–3 are backend-only with an identical pattern (delete graph → create service → wire API). Phase 4 is fundamentally different (frontend changes, new dependency, E2E rewrites). Completing the simpler phases first establishes a proven pattern. REQ-019 has no dependency on the other 3 REQs.

---

## Phase 1: Scouter Service Layer (REQ-016)

**Status:** ✅ Complete

*Replace `scouter_graph.py` (895L, 10-node LangGraph StateGraph) with 3 plain async services + 1 repository. All 10 nodes use deterministic if/elif logic — no LLM routing. API contract unchanged (no frontend impact).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-016 §5–§7 for current task |
| 🧪 **TDD** | Write tests first → code → run affected tests only |
| ✅ **Verify** | `ruff check <modified_files>`, `bandit <modified_files>` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `qa-reviewer` (parallel) |
| 📝 **Commit** | `git commit` (pre-commit hooks: linters + type checks ~25-40s) |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Create JobPoolRepository + JobEnrichmentService (TDD)** — Two new files extracting logic from scouter_graph.py. **Read:** REQ-016 §6.2–§6.3, `backend/app/agents/scouter_graph.py` (lines 102-137 extraction, 301-456 pool ops, 525-578 ghost scoring), `backend/app/repositories/job_posting_repository.py` (pattern reference). **Create:** `backend/app/repositories/job_pool_repository.py` (~200L) — methods: `check_job_in_pool()`, `resolve_source_id()`, `save_job_to_pool()`, `link_existing_job()`. **Create:** `backend/app/services/job_enrichment_service.py` (~150L) — method: `enrich_jobs()` (skill extraction via provider abstraction layer — uses `get_provider()` from `app/providers/`, same as existing scouter_graph.py extract_skills_node; + ghost scoring). **Create:** `backend/tests/unit/test_job_pool_repository.py` (~25 tests). **Create:** `backend/tests/unit/test_job_enrichment_service.py` (~15 tests). **Run:** `pytest tests/unit/test_job_pool_repository.py tests/unit/test_job_enrichment_service.py -v`. **Done when:** Both new files pass all tests, follow existing repository/service patterns. | `tdd, db, plan` | ✅ |
| 2 | **Create JobFetchService + wire discovery_workflow (TDD)** — Orchestrator service that calls source adapters → merge → pool check → enrich → update poll state. **Read:** REQ-016 §6.1, `backend/app/agents/scouter_graph.py` (lines 75-94 get_source_adapter, 206-277 fetch_sources_node), `backend/app/services/discovery_workflow.py`, `backend/app/agents/scouter.py` (merge_results, poll state helpers). **Create:** `backend/app/services/job_fetch_service.py` (~150L) — method: `run_poll(user_id, persona_id)`. **Create:** `backend/tests/unit/test_job_fetch_service.py` (~20 tests). **Modify:** `backend/app/services/discovery_workflow.py` — replace `get_scouter_graph()` call with `JobFetchService.run_poll()`. **Modify:** `backend/tests/unit/test_discovery_workflow.py` (~22 tests) — update mocks from graph invocation to service calls. **Run:** `pytest tests/unit/test_job_fetch_service.py tests/unit/test_discovery_workflow.py -v`. **Done when:** discovery_workflow calls new service, all 22 existing tests pass with updated mocks. | `tdd, api, plan` | ✅ |
| 3 | **Delete scouter_graph.py + ScouterState + cleanup** — Remove the LangGraph graph and all references. **Read:** REQ-016 §5. **Delete:** `backend/app/agents/scouter_graph.py` (895L). **Delete:** `backend/tests/unit/test_scouter_graph.py` (17 tests). **Modify:** `backend/app/agents/state.py` — remove `ScouterState` TypedDict (~35L). **Modify:** `backend/app/agents/scouter.py` — remove `create_scouter_state()` (~25L). **Modify:** `backend/app/agents/__init__.py` — remove `ScouterState` export (note: only `ScouterState` is exported, no graph function exports exist). **Verify:** `grep -r "scouter_graph" backend/` returns zero hits. **Run:** `pytest tests/unit/test_scouter_agent.py tests/unit/test_scouter_error_handling.py tests/unit/test_discovery_workflow.py tests/unit/test_job_deduplication.py tests/unit/test_global_dedup_service.py tests/unit/test_pool_scoring.py -v`. **Done when:** All kept tests pass (~216 tests), no imports reference deleted files. | `plan` | ✅ |
| 4 | **Phase gate — full test suite + push** — Run complete backend + frontend + E2E test suites, fix any regressions. **Run:** `pytest tests/ -v` (all backend), `npm run test:run` (all frontend), `npx playwright test` (all E2E). **Also:** `ruff check .`, `npm run lint`, `npm run typecheck`. **Push:** `git push` (pre-push hooks verify). **Done when:** All tests green, pushed to remote. | `plan, commands` | ✅ |

#### Phase 1 Notes

**Files unchanged (verify pass in §3):** `ghost_detection.py` (508L), `global_dedup_service.py` (428L), `job_deduplication.py` (880L), source adapters (Adzuna, etc.).

**E2E impact:** `job-discovery.spec.ts` (25 tests), `add-job.spec.ts` (6 tests) — API contract preserved, should pass unchanged. Verified at phase gate (§4).

---

## Phase 2: Strategist Service Layer (REQ-017)

**Status:** ✅ Complete

*Replace `strategist_graph.py` (662L, 10-node graph where 9 nodes are placeholders) with a single `JobScoringService`. Also relocate prompt templates to new `prompts/` package and move `ScoreResult` TypedDict to `score_types.py`. Depends on Phase 1 (Scouter's `JobFetchService` will call `JobScoringService` after saving jobs).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-017 §5–§7 for current task |
| 🧪 **TDD** | Write tests first → code → run affected tests only |
| ✅ **Verify** | `ruff check <modified_files>`, `bandit <modified_files>` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `qa-reviewer` (parallel) |
| 📝 **Commit** | `git commit` (pre-commit hooks) |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 5 | **Create prompts/ package + relocate strategist_prompts + move ScoreResult** — Infrastructure: create new prompts package, move prompt templates, relocate ScoreResult. **Read:** REQ-017 §5.2–§5.3, §8. **Create:** `backend/app/prompts/__init__.py`. **Move:** `backend/app/agents/strategist_prompts.py` (157L) → `backend/app/prompts/strategist.py`. **Move:** `ScoreResult` TypedDict from `backend/app/agents/state.py` → `backend/app/services/score_types.py` (already exists, ~182L). **Update imports:** grep for all `from app.agents.strategist_prompts import` and `from app.agents.state import ScoreResult` — update to new paths. Files likely affected: `scoring_flow.py`, `__init__.py`, multiple test files. **Add backward-compat re-export** in `state.py`: `from app.services.score_types import ScoreResult` (removed in §7). **Run:** `pytest tests/ -v` (full suite — exception to "affected tests only" rule because import path changes are cross-cutting and can break any file that imports ScoreResult or strategist_prompts). **Done when:** All tests pass with new import paths, prompts/ directory exists. | `plan` | ✅ |
| 6 | **Create JobScoringService + wire API (TDD)** — Single orchestrator wrapping all existing scoring services. **Read:** REQ-017 §6, `backend/app/agents/strategist_graph.py` (lines 601-662 score_jobs pattern), `backend/app/services/scoring_flow.py` (272L), `backend/app/services/fit_score.py`, `backend/app/services/non_negotiables_filter.py`. **Create:** `backend/app/services/job_scoring_service.py` (~200L) — methods: `score_job()`, `score_batch()`. Pipeline: embedding check → non-negotiables filter → fit/stretch score → rationale (if fit ≥ 65) → save. **Key constant:** `RATIONALE_SCORE_THRESHOLD = 65` (define in `job_scoring_service.py` — matches existing threshold in `strategist_graph.py` line ~635). **Create:** `backend/tests/unit/test_job_scoring_service.py` (~30 tests). **Wire:** Update `JobFetchService` (from Phase 1) to call `JobScoringService.score_batch()` after pool save. **Run:** `pytest tests/unit/test_job_scoring_service.py tests/unit/test_job_fetch_service.py -v`. **Done when:** Scoring pipeline exercised end-to-end via mocks, JobFetchService integrates scoring. | `tdd, api, provider, plan` | ✅ |
| 7 | **Delete strategist_graph.py + StrategistState + cleanup** — Remove the LangGraph graph and all references. **Read:** REQ-017 §5. **Delete:** `backend/app/agents/strategist_graph.py` (662L). **Delete:** `backend/tests/unit/test_strategist_graph.py` (85 tests). **Delete:** `backend/app/agents/strategist_prompts.py` (if not already removed by move in §5 — verify). **Modify:** `backend/app/agents/state.py` — remove `StrategistState` (~55L), remove backward-compat `ScoreResult` re-export (added in §5). **Modify:** `backend/app/agents/__init__.py` — remove strategist graph imports/exports. **Verify:** `grep -r "strategist_graph" backend/` returns zero hits. **Run:** `pytest tests/unit/test_scoring_flow.py tests/unit/test_fit_score_aggregation.py tests/unit/test_stretch_score_aggregation.py tests/unit/test_non_negotiables_filter.py tests/unit/test_batch_scoring.py tests/unit/test_score_correlation.py -v`. **Done when:** All ~220 kept scoring tests pass, no imports reference deleted files. | `plan` | ✅ |
| 8 | **Phase gate — full test suite + push** — Run complete test suites, fix regressions. **Run:** `pytest tests/ -v`, `npm run test:run`, `npx playwright test`. **Also:** `ruff check .`, `npm run lint`, `npm run typecheck`. **Push:** `git push`. **Done when:** All tests green, pushed to remote. | `plan, commands` | ✅ |

#### Phase 2 Notes

**ScoreResult import risk (§5):** `ScoreResult` is imported by 3 files (`scoring_flow.py`, `score_types.py` itself, and one test file). The backward-compat re-export in `state.py` provides a safety net — any file still importing from `state` will work until the re-export is cleaned up in §7. Grep to confirm before updating: `grep -rn "from app.agents.state import.*ScoreResult" backend/`.

**Scoring services unchanged (verify in §7):** `fit_score.py` (373L), `stretch_score.py` (612L), `non_negotiables_filter.py` (342L), `scoring_flow.py` (272L), `score_types.py` (182L), `score_explanation.py` (50L), `score_correlation.py` (244L).

---

## Phase 3: Ghostwriter Service Layer (REQ-018)

**Status:** ✅ Complete

*Replace `ghostwriter_graph.py` (687L, 9-node graph where 4 are placeholders) with `ContentGenerationService` orchestrating 15 existing production-ready service files. The real Ghostwriter code is already in services — the graph is just a shell. API contract unchanged (no frontend impact).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-018 §5–§7 for current task |
| 🧪 **TDD** | Write tests first → code → run affected tests only |
| ✅ **Verify** | `ruff check <modified_files>`, `bandit <modified_files>` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `qa-reviewer` (parallel) |
| 📝 **Commit** | `git commit` (pre-commit hooks) |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 9 | **Relocate ghostwriter_prompts.py + trim ghostwriter.py** — Move prompts to new package, remove state factory from trigger file. **Read:** REQ-018 §5.2, §8. **Move:** `backend/app/agents/ghostwriter_prompts.py` (405L) → `backend/app/prompts/ghostwriter.py`. **Update imports:** `backend/app/services/cover_letter_generation.py` (line ~20) — change `from app.agents.ghostwriter_prompts import` → `from app.prompts.ghostwriter import`. **Update:** `backend/tests/unit/test_ghostwriter_prompts.py` (73 tests) — update import path. **Modify:** `backend/app/agents/ghostwriter.py` — remove `create_ghostwriter_state()` (~30L). Keep: `TriggerType` enum, `is_draft_request()`, `is_regeneration_request()`, `should_auto_draft()` (~60L). **Modify:** `backend/tests/unit/test_ghostwriter.py` (18 tests) — remove test for `create_ghostwriter_state()`. **Run:** `pytest tests/unit/test_ghostwriter_prompts.py tests/unit/test_ghostwriter.py tests/unit/test_cover_letter_generation.py -v`. **Done when:** All prompt tests pass with new path, trigger helpers still work. | `plan` | ✅ |
| 10 | **Create ContentGenerationService + wire API + update chat.py (TDD)** — Orchestrator implementing 8-step content generation pipeline. **Read:** REQ-018 §6–§7, `backend/app/agents/ghostwriter_graph.py` (lines 626-687 generate_materials), `backend/app/services/tailoring_decision.py`, `backend/app/services/story_selection.py`, `backend/app/services/cover_letter_generation.py`. **Create:** `backend/app/services/content_generation_service.py` (~250L) — method: `generate_materials(user_id, persona_id, job_posting_id, trigger_type)`. **Pipeline:** check existing → select resume → evaluate tailoring → create variant → select stories → generate cover letter → check active → build review. **Create:** `backend/tests/unit/test_content_generation_service.py` (~25 tests). **Modify:** `backend/app/agents/chat.py` — update `delegate_ghostwriter()` (~lines 682-736): change `from app.agents.ghostwriter_graph import generate_materials` → `from app.services.content_generation_service import ContentGenerationService` and update the call site accordingly. **Run:** `pytest tests/unit/test_content_generation_service.py tests/unit/test_chat*.py -v`. **Done when:** 8-step pipeline passes all tests, chat.py delegates correctly. | `tdd, api, provider, plan` | ✅ |
| 11 | **Delete ghostwriter_graph.py + GhostwriterState + cleanup** — Remove the LangGraph graph and all references. **Read:** REQ-018 §5. **Delete:** `backend/app/agents/ghostwriter_graph.py` (687L). **Delete:** `backend/tests/unit/test_ghostwriter_graph.py` (57 tests). **Delete:** `backend/app/agents/ghostwriter_prompts.py` (if not already removed by move in §9 — verify). **Modify:** `backend/app/agents/state.py` — remove `GhostwriterState`, `TailoringAnalysis`, `GeneratedContent`, `ScoredStoryDetail` (~65L). **Verify:** grep for `GeneratedContent` and `ScoredStoryDetail` in services — update imports if referenced. **Modify:** `backend/app/agents/__init__.py` — remove ghostwriter graph imports/exports. **Verify:** `grep -r "ghostwriter_graph" backend/` returns zero. **Verify:** `state.py` now ~77L (only `CheckpointReason`, `BaseAgentState`, `ClassifiedIntent`, `ChatAgentState`). **Run:** `pytest tests/unit/test_ghostwriter*.py tests/unit/test_cover_letter*.py tests/unit/test_tailoring*.py tests/unit/test_story_selection*.py tests/unit/test_reasoning*.py tests/unit/test_duplicate_story*.py -v`. **Done when:** All ~407 kept service tests pass, state.py is ~77L, no orphan imports. | `plan` | ✅ |
| 12 | **Phase gate — full test suite + push** — Run complete test suites, fix regressions. **Run:** `pytest tests/ -v`, `npm run test:run`, `npx playwright test`. **Also:** `ruff check .`, `npm run lint`, `npm run typecheck`. **Push:** `git push`. **Done when:** All tests green, pushed to remote. | `plan, commands` | ✅ |

#### Phase 3 Notes

**15 service files unchanged (all KEEP, ~407 tests):** `cover_letter_generation.py`, `cover_letter_structure.py`, `cover_letter_validation.py`, `cover_letter_output.py`, `cover_letter_pdf_generation.py`, `cover_letter_pdf_storage.py`, `cover_letter_editing.py`, `tailoring_decision.py`, `modification_limits.py`, `story_selection.py`, `regeneration.py`, `generation_outcome.py`, `explanation_generation.py`, `reasoning_explanation.py`, `duplicate_story.py`.

**E2E impact:** `ghostwriter-review.spec.ts` (6), `cover-letter-review.spec.ts` (8), `variant-review.spec.ts` (8) — API contract preserved. Verified at phase gate (§12).

---

## Phase 4: Onboarding Service Layer (REQ-019)

**Status:** ✅ Complete

*The most significant redesign. Replace `onboarding.py` graph/state-machine code (2490L total, ~1784L to delete, ~706L to keep — keyword matching, zero LLM calls) with ResumeParsingService (pdfplumber + Gemini 2.5 Flash). Frontend: 12→11 steps (remove base-resume step), resume upload calls new parse endpoint. Independent of Phases 1–3.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-019 §5–§7, §13 for current task |
| 🧪 **TDD** | Write tests first → code → run affected tests only |
| 🗃️ **API** | Use `zentropy-api` for endpoint patterns |
| 🔒 **Security** | File upload validation, PDF size limit (10MB max) |
| ✅ **Verify** | `ruff check <modified_files>`, `bandit <modified_files>` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` + `qa-reviewer` (parallel) |
| 📝 **Commit** | `git commit` (pre-commit hooks) |
| ⏸️ **Compact** | Compact context — do NOT push |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 13 | **Add pdfplumber + create ResumeParsingService (TDD)** — New dependency and service for PDF resume extraction. **Read:** REQ-019 §6–§7. **Modify:** `backend/pyproject.toml` — add `pdfplumber>=0.11.0` (ASK USER before installing). **Create:** `backend/app/services/resume_parsing_service.py` (~200L) — method: `parse_resume(file_content: bytes, filename: str) -> ResumeParseResult`. Uses pdfplumber for text extraction + Gemini 2.5 Flash for structured parsing. **Output schema:** `{ basic_info, work_history, education, skills, certifications, voice_suggestions: { writing_style, vocabulary_level, personality_markers, confidence } }`. **Validation:** 10MB file size limit, PDF-only. **Create:** `backend/tests/unit/test_resume_parsing_service.py` (~20 tests) — mock LLM, test extraction, structured parsing, voice confidence threshold (≥0.7), error handling. **Run:** `pytest tests/unit/test_resume_parsing_service.py -v`. **Done when:** Service extracts structured data from PDF with mocked LLM, handles errors gracefully. | `tdd, provider, security, plan` | ✅ |
| 14 | **Create resume-parse API endpoint (TDD)** — New endpoint for frontend resume upload. **Read:** REQ-019 §7, existing routers for pattern reference (grep for `router` in `backend/app/api/`). **Create:** new onboarding router with `POST /api/v1/onboarding/resume-parse` endpoint (no existing onboarding router — create one) — accepts multipart file upload, calls ResumeParsingService, returns structured parse result. **Pydantic models:** `ResumeParseResponse` (structured data matching service output). **Create:** endpoint tests (~15 tests) — success, invalid file type, oversized file, parse failure. **Run:** `pytest tests/api/test_onboarding*.py -v` (or wherever endpoint tests live). **Done when:** Endpoint accepts PDF upload, returns structured data, rejects invalid files. | `tdd, api, security, plan` | ✅ |
| 15 | **Delete onboarding graph code + update chat.py + create utility tests** — Remove ~1784L of graph/state-machine code (lines 793–2490), keep ~706L of post-onboarding utilities (lines 1–792). **Read:** REQ-019 §5, `backend/app/agents/onboarding.py` (2490L total — keep lines 1–792, delete lines 793–2490), `backend/app/agents/chat.py` (`delegate_onboarding` function — note: chat.py was already modified in §10 for ghostwriter delegation; read the current version). **Delete from onboarding.py (~1784L, lines 793–2490):** All gather_* step handlers, check_step_complete, wait_for_input, handle_skip, setup_base_resume, complete_onboarding, create_onboarding_graph, get_onboarding_graph. **Keep in onboarding.py (~706L, lines 1–792):** UPDATE_REQUEST_PATTERNS, SECTION_DETECTION_PATTERNS, is_update_request(), detect_update_section(), SECTIONS_REQUIRING_RESCORE, get_affected_embeddings(), post-onboarding formatters, prompt templates. **Modify:** `backend/app/agents/chat.py` — update `delegate_onboarding()` to remove `get_onboarding_graph` import, replace with redirect or simplified logic. **Modify:** `backend/app/agents/state.py` — remove `OnboardingState` (~30L). **Modify:** `backend/app/agents/__init__.py` — remove onboarding graph exports. **Delete:** Most of `backend/tests/unit/test_onboarding_agent.py` (~164 tests on graph nodes). Keep tests for utility functions. **Create:** `backend/tests/unit/test_onboarding_utilities.py` (~15 tests for update detection, section detection, rescore triggering). **Run:** `pytest tests/unit/test_onboarding*.py tests/unit/test_chat*.py -v`. **Done when:** onboarding.py is ~706L (utilities only), chat.py compiles, utility tests pass. | `tdd, plan` | ✅ |
| 16 | **Update frontend onboarding to 11 steps + frontend tests** — Remove base-resume step (12→11), wire resume upload to parse endpoint. **Read:** REQ-019 §13. **Modify:** `frontend/src/components/onboarding/onboarding-steps.ts` — `TOTAL_STEPS` 12→11, remove `base-resume` step definition. **Modify:** `frontend/src/app/onboarding/page.tsx` — remove step 12 case from StepRouter. **Modify:** `frontend/src/components/onboarding/resume-upload-step.tsx` — call `POST /api/v1/onboarding/resume-parse`, populate later steps with parsed data. **Modify:** `frontend/src/lib/onboarding-provider.tsx` — adjust navigation/validation for 11 steps. **Retain:** `base-resume-step.tsx` — keep file but remove from routing (may reuse in Resume Management). **Update tests:** `onboarding-steps.test.ts` (step count), `onboarding-shell.test.tsx` (progress bar), `onboarding-provider.test.tsx` (navigation). **Run:** `npm test -- onboarding`. **Done when:** Wizard has 11 steps, resume upload calls parse endpoint, all frontend tests pass. | `tdd, plan` | ✅ |
| 17 | **Update E2E tests (onboarding.spec.ts)** — Rewrite for 11-step wizard flow. **Read:** REQ-019 §12, `frontend/tests/e2e/onboarding.spec.ts` (496L, 18 tests). **Modify:** Update "Step X of 12" assertions → "X of 11". Add assertion for `POST /onboarding/resume-parse` mock. Delete tests for step 12 (base resume setup). Update progress bar percentage calculations. **Run:** `npx playwright test onboarding.spec.ts`. **Done when:** All E2E onboarding tests pass with 11-step flow. | `playwright, e2e, plan` | ✅ |
| 18 | **Phase gate — full test suite + push** — Run complete test suites, fix regressions. **Run:** `pytest tests/ -v`, `npm run test:run`, `npx playwright test`. **Also:** `ruff check .`, `npm run lint`, `npm run typecheck`. **Push:** `git push`. **Done when:** All tests green, pushed to remote. | `plan, commands` | ✅ |

#### Phase 4 Notes

**New dependency (§13):** `pdfplumber>=0.11.0` — Pure Python PDF text extraction. MIT license, 10M+ monthly downloads, no system dependencies (unlike poppler). Ask user before adding.

**Voice profile inference (§13):** LLM call includes voice suggestions. If `confidence ≥ 0.7`, voice fields pre-populate step 10. Otherwise manual entry.

**base-resume removal rationale:** Users can't make meaningful resume selections at onboarding with no job data. Auto-create BaseResume using all persona data; users edit later from Resume Management.

**chat.py risk (§15):** `chat.py` delegates to `get_onboarding_graph()`. After deletion, the onboarding path in chat may redirect to the onboarding page rather than processing chat messages (onboarding is now form-based, not chat-based).

---

## Phase 5: Cross-Agent Verification

**Status:** ✅ Complete

*Final verification that all 4 redesigns work together. Check shared file end-states, run codebase-wide import verification, full regression.*

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 19 | **Verify shared file end-states** — Confirm all shared files match expected final state. **Verify `state.py`:** ~77L containing only `CheckpointReason`, `BaseAgentState`, `ClassifiedIntent`, `ChatAgentState`. No: ScouterState, StrategistState, GhostwriterState, OnboardingState, ScoreResult, TailoringAnalysis, GeneratedContent, ScoredStoryDetail. **Verify `__init__.py`:** Only Chat Agent + base utility exports. No graph references. **Verify orphan imports:** `grep -r "scouter_graph\|strategist_graph\|ghostwriter_graph\|get_onboarding_graph" backend/` → zero hits. **Verify `agents/` directory:** ~7 files, ~3K lines: `__init__.py`, `base.py` (1042L), `chat.py` (856L), `checkpoint.py` (211L), `state.py` (~77L), `scouter.py` (237L), `ghostwriter.py` (~60L), `onboarding.py` (~706L). **Verify `prompts/` directory:** `__init__.py`, `strategist.py` (157L), `ghostwriter.py` (405L). **Fix:** Any discrepancies found. **Run:** `pytest tests/ -v`. **Done when:** All end-states match REQ specs, no orphan imports. | `plan` | ✅ |
| 20 | **Final gate — full test suite + push** — Complete regression and final push. **Run:** `pytest tests/ -v`, `npm run test:run`, `npx playwright test`. **Also:** `ruff check .`, `npm run lint`, `npm run typecheck`. **Push:** `git push`. **Done when:** All tests green, all 4 agent redesigns verified, pushed to remote. | `plan, commands` | ✅ |

---

## Status Legend

| Icon | Meaning |
|------|---------|
| ⬜ | Incomplete |
| 🟡 | In Progress |
| ✅ | Complete |

---

## Task Count Summary

| Phase | REQ | Code Tasks | Gate | Total | Lines Deleted | Lines Created |
|-------|-----|------------|------|-------|---------------|---------------|
| 0 | — | Setup | — | Local-only | — | — |
| 1 | REQ-016 (Scouter) | 3 | 1 | 4 | ~960 | ~500 |
| 2 | REQ-017 (Strategist) | 3 | 1 | 4 | ~800 | ~210 |
| 3 | REQ-018 (Ghostwriter) | 3 | 1 | 4 | ~820 | ~260 |
| 4 | REQ-019 (Onboarding) | 5 | 1 | 6 | ~2,000 | ~480 |
| 5 | Verification | 1 | 1 | 2 | ~0 | ~0 |
| **Total** | | **15** | **5** | **20** | **~4,580** | **~1,450** |

**Net reduction:** ~3,130 lines deleted (mostly LangGraph graph boilerplate and structural tests).

---

## Critical Files (Cross-Phase)

| File | Phases | Impact |
|------|--------|--------|
| `backend/app/agents/state.py` | 1, 2, 3, 4 | Each phase removes its agent's TypedDict(s). 404L → ~77L. |
| `backend/app/agents/__init__.py` | 1, 2, 3, 4 | Each phase removes graph exports. Ends with Chat Agent + base only. |
| `backend/app/agents/chat.py` | 3, 4 | §10: update delegate_ghostwriter(). §15: update delegate_onboarding(). |
| `backend/app/prompts/` | 2, 3 | §5: create directory + strategist.py. §9: add ghostwriter.py. |
| `backend/app/services/score_types.py` | 2 | §5: receives ScoreResult from state.py. |
| `backend/app/services/discovery_workflow.py` | 1 | §2: rewire from scouter_graph to JobFetchService. |

---

## Implementation Notes for Coding Agent

### Pattern: Delete Graph → Create Service

Every phase follows the same 3-step pattern:
1. **Create new service(s)** — Extract logic from graph nodes into plain async service methods (TDD)
2. **Wire API** — Update callers to use new service instead of graph (update mocks in tests)
3. **Delete graph** — Remove graph file, graph tests, state TypedDict, __init__.py exports

### Service Layer Conventions

```python
# All new services follow this pattern
class JobFetchService:
    """Fetches jobs from configured sources, enriches, and saves to pool."""

    def __init__(self, db: AsyncSession, user_id: UUID, persona_id: UUID):
        self.db = db
        self.user_id = user_id
        self.persona_id = persona_id

    async def run_poll(self) -> PollResult:
        """Entry point — replaces the entire scouter graph invocation."""
        ...
```

### Import Update Strategy (for relocating files)

1. Move the file/class to its new location
2. Add backward-compat re-export at old location: `from app.new_location import Thing`
3. Update all known importers to the new path
4. Remove the backward-compat re-export when the old module is deleted in the cleanup subtask

### Testing Strategy

```bash
# Subtask — affected tests only (fast, ~5-15s)
pytest tests/unit/test_job_pool_repository.py tests/unit/test_job_enrichment_service.py -v

# Phase gate — full suite (thorough, ~90-135s)
pytest tests/ -v && npm run test:run && npx playwright test
```

### Shared File Editing Protocol

When editing `state.py` or `__init__.py` (modified by multiple phases):
1. **Read the file FIRST** — it changes across phases
2. Remove only YOUR phase's code (don't touch other agents' types/exports)
3. Verify remaining code still compiles: `python -c "from app.agents.state import *"`
4. Run tests that depend on the remaining types/exports

### Key REQ Sections by Phase

| Phase | Primary REQ Sections | Key Decisions |
|-------|---------------------|---------------|
| 1 | REQ-016 §5–§7 | 3 services + 1 repo replaces 10-node graph |
| 2 | REQ-017 §5–§8 | Single service wraps all scoring; ScoreResult relocates to score_types.py |
| 3 | REQ-018 §5–§8 | ContentGenerationService orchestrates 15 existing services |
| 4 | REQ-019 §5–§7, §13 | ResumeParsingService (pdfplumber + Gemini); 12→11 frontend steps |

### Rollback Guidance

If a subtask leaves the codebase in a broken state:
- **Before commit:** `git checkout -- <files>` to revert changes
- **After commit:** `git revert HEAD` to undo the last commit
- **Service creation tasks (§1, §2, §6, §10, §13, §14):** Safe — only add new files and modify callers. Revert = delete new files + restore callers.
- **Deletion tasks (§3, §7, §11, §15):** Higher risk — removes code other tasks depend on. Only attempt after all tests pass in the preceding creation tasks. Revert = `git revert HEAD`.
- **Frontend tasks (§16, §17):** Isolated to `frontend/` — no backend risk. Revert = `git checkout -- frontend/`.
