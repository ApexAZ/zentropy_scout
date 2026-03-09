# Backend Test Suite Audit & Cleanup Plan

**Created:** 2026-03-09
**Status:** Ready for implementation

---

## Context

The backend has 4,614 tests across 195 files and 197 source modules. This audit ensures no stale/orphaned tests exist and that tests target behavior over implementation, per the project's testing philosophy in CLAUDE.md.

**Three exploration agents completed initial analysis:**
1. **Orphan check** — Clean. All test imports reference existing modules. Historical LangGraph cleanup was done properly.
2. **Antipattern scan** — Found 72 `isinstance` assertions (30 files), 372+ `len()` assertions (50+ files), ~37 constant assertions (15 files). Zero findings for issubclass/hasattr/callable/etc.
3. **Quality patterns** — Excellent naming conventions, no duplicates, good mock density, proper isolation, well-sized files.

**Critical nuance:** Most raw findings are **legitimate behavioral assertions** (e.g., `assert len(errors) == 1` verifying "this input produces exactly 1 validation error"). The primary work is **triage** — classifying each finding before touching any code.

**Conftest detection gap:** The AST scanner (conftest.py lines 531-617) flags `isinstance()` anywhere in a test function body, not just in `assert` statements. It doesn't detect `len()` or constant patterns — and shouldn't, given the extreme false-positive rate.

---

## How to Use This Document

1. Find the first ⬜ task — that's where to start
2. Each task = one commit, sized for ~60k variable tokens
3. After each task: update status → commit → STOP and ask user
4. After each phase: full test suite as quality gate

---

## Dependency Chain

```
Phase 1: Triage & Classification (read-only analysis)
    ↓
Phase 2: Refactor Antipattern Tests (code changes)
    ↓
Phase 3: Conftest Hook Enhancement (tooling improvement)
    ↓
Phase 4: Quality Gate (verification + documentation)
```

---

## Classification Rules

| Pattern | ANTIPATTERN | REDUNDANT | LEGITIMATE |
|---------|-------------|-----------|------------|
| `assert isinstance(X, T)` | Sole assertion in test (or sole meaningful one) | Followed by value/property assertion on X | Verifying polymorphic dispatch (factory returns SubclassA vs SubclassB) |
| `assert len(X) == N` | X is an enum, type, or constant collection | — | X is a function return value or filtered result |
| `assert CONST == "value"` | Duplicates a source-code literal | — | Value is computed by function under test |

**Decision criterion:** "Would this test still pass if I rewrote the implementation using a completely different internal structure but preserved the same external behavior?"

---

## Phase 1: Triage & Classification

*Read-only analysis. Classify findings as LEGITIMATE, ANTIPATTERN, or REDUNDANT. Output drives Phase 2 scope.*

| # | Task | Scope | Status |
|---|------|-------|--------|
| 1.1 | **Triage isinstance assertions** — Read each of the ~30 files with `assert isinstance()`. Classify each using the table above. Record findings in a triage table appended to this plan. | 72 findings, ~30 files | ✅ |
| 1.2 | **Triage len() assertions via sampling** — Read the 7 heaviest files (test_cover_letter_validation 26, test_content_utils 46, test_modification_limits 18, test_non_negotiables_filter 12, test_score_explanation 8, test_explanation_generation 14, test_scoring_flow 15). Classify each. Derive mechanical rule for remaining files. | ~139 findings, 7 files | ⬜ |
| 1.3 | **Triage constant assertions** — Search for `assert X == "literal"` and `assert CONSTANT == value` patterns. Classify each. | ~37 findings, ~15 files | ⬜ |
| 1.4 | **Compile triage report** — Summarize: total findings, counts by classification, files requiring changes. This becomes Phase 2 input. | Synthesis | ⬜ |

**Notes:**
- Triage is read-only — no code changes
- Expected outcome: ~50 REDUNDANT isinstance (remove line), ~10 ANTIPATTERN isinstance (rewrite/delete), ~5 LEGITIMATE isinstance (keep). Nearly all len() expected LEGITIMATE. Constants TBD.

---

## Phase 2: Refactor Antipattern Tests

*Fix only ANTIPATTERN and REDUNDANT findings from triage. Exact tasks TBD after Phase 1.*

| # | Task | Scope | Status |
|---|------|-------|--------|
| 2.1 | **Remove REDUNDANT isinstance assertions** — Delete `assert isinstance(X, T)` lines where a behavioral assertion follows. Batch ~15 files per subtask. | ~50 line removals across ~25 files | ⬜ |
| 2.2 | **Rewrite ANTIPATTERN isinstance tests** — Add behavioral assertions or delete if covered elsewhere. | ~10 tests | ⬜ |
| 2.3 | **Fix ANTIPATTERN constant assertions** — Rewrite to test behavior dependent on the constant, not the constant's value. | TBD from triage | ⬜ |
| 2.4 | **Fix any ANTIPATTERN len() findings** — If triage reveals genuine antipatterns in len() usage. May be zero work. | TBD from triage | ⬜ |

**Notes:**
- Task count may change based on triage results
- Each subtask: run affected tests → full lint → commit
- Reviews: `code-reviewer` + `qa-reviewer` before commit

---

## Phase 3: Conftest Hook Enhancement

*Refine AST scanner based on triage learnings. Keep warning-only (no build failures).*

| # | Task | Scope | Status |
|---|------|-------|--------|
| 3.1 | **Narrow isinstance detection to assert-context only** — Currently flags `isinstance()` anywhere in function body (helpers, conditionals). Refine to only flag `assert isinstance(...)` statements. Reduces false positives. | conftest.py lines 531-617 | ⬜ |
| 3.2 | **Add isinstance-only-assertion warning** — New category: test functions where `assert isinstance(X, T)` is the sole assertion. These are almost always structural. Tag as "isinstance-only: no behavioral assertion". | conftest.py | ⬜ |

**Notes:**
- Do NOT add `len()` or constant detection — false-positive rate too high (95%+ legitimate)
- Hook remains warning-only, never fails the build

---

## Phase 4: Quality Gate

| # | Task | Scope | Status |
|---|------|-------|--------|
| 4.1 | **Full test suite + coverage comparison** — Run full pytest. Compare test count to baseline (4,614). No module should show >5% coverage drop. | Full suite | ⬜ |
| 4.2 | **Verify hook detects patterns correctly** — Check terminal summary output for refined isinstance detection. Confirm no false positives on conditional isinstance usage. | pytest output review | ⬜ |
| 4.3 | **Update CLAUDE.md** — Update "Automated detection" paragraph to document enhanced capabilities and which patterns are intentionally NOT detected. | CLAUDE.md | ⬜ |

---

## Task Count Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 1: Triage | 4 | Classify all findings (read-only) |
| 2: Refactoring | 3-4 | Fix ANTIPATTERN + REDUNDANT |
| 3: Hook Enhancement | 2 | Refine conftest scanner |
| 4: Quality Gate | 3 | Verify + document |
| **Total** | **12-13** | |

---

## Critical Files Reference

| File | Role |
|------|------|
| `backend/tests/conftest.py` (lines 531-617) | AST antipattern scanner |
| `backend/tests/unit/test_content_utils.py` | Heaviest isinstance file (7 findings — all REDUNDANT pattern: isinstance + equality check) |
| `backend/tests/unit/test_explanation_generation.py` | 6 isinstance (mix of REDUNDANT and ANTIPATTERN sole-assertion smoke tests) |
| `backend/tests/unit/test_cover_letter_validation.py` | Heaviest len file (26 findings — expected all LEGITIMATE) |
| `backend/tests/unit/test_source_adapters.py` | 4 isinstance findings |
| `CLAUDE.md` (Test Antipatterns section) | Documentation to update |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-03-09 | Plan created |
| 2026-03-09 | §1.1 complete — isinstance triage done (57 REDUNDANT, 5 ANTIPATTERN, 2 LEGITIMATE) |

---

## Appendix A: isinstance Triage Results (§1.1)

**Summary:** 64 findings across 30 files. 57 REDUNDANT, 5 ANTIPATTERN, 2 LEGITIMATE.

### ANTIPATTERN (5) — Sole assertion, no behavioral verification

| # | File:Line | Test Name | Action |
|---|-----------|-----------|--------|
| 9 | test_explanation_generation.py:596 | test_empty_extracted_skills | Add behavioral assertion (e.g., `explanation.summary is not None`) |
| 10 | test_explanation_generation.py:609 | test_empty_target_skills | Add behavioral assertion |
| 13 | test_explanation_generation.py:710 | test_large_skill_set | Add behavioral assertion (or convert to "does not raise" test) |
| 38 | test_pool_surfacing_service.py:306 | test_skills_are_loaded | Assert on list content (non-empty, contains expected skill) |

### LEGITIMATE (2) — Hypothesis fuzz "always returns str" property

| # | File:Line | Test Name | Reason |
|---|-----------|-----------|--------|
| 60 | test_llm_sanitization_fuzz.py:238 | test_returns_string | Fuzz invariant: sanitizer always returns str, never None |
| 61 | test_llm_sanitization_fuzz.py:406 | test_single_character_no_crash | Fuzz invariant: single-char input always returns str |

### REDUNDANT (57) — isinstance followed by behavioral assertions, remove isinstance line

| # | File:Line | Behavioral assertion that follows |
|---|-----------|-----------------------------------|
| 1 | test_content_utils.py:121 | `len(result) > 0` |
| 2 | test_content_utils.py:218 | `len(result) > 0` |
| 3 | test_content_utils.py:257 | `len(result) > 0` |
| 4 | test_content_utils.py:415 | `result == set()` |
| 5 | test_content_utils.py:461 | `result == set()` |
| 6 | test_content_utils.py:519 | `result == set()` |
| 7 | test_content_utils.py:833 | `len(result) == 16` |
| 8 | test_explanation_generation.py:581 | `len(explanation.strengths) >= 1` |
| 11 | test_explanation_generation.py:622 | `len(explanation.stretch_opportunities) >= 1` |
| 12 | test_explanation_generation.py:652 | `explanation.summary is not None` |
| 14 | test_source_adapters.py:65 | Field assertions (`external_id`, `title`, `company`) |
| 15 | test_source_adapters.py:131 | Field assertions (`external_id`, `title`, `company`) |
| 16 | test_source_adapters.py:168 | Field assertions (`external_id`, `title`, `company`, `location`) |
| 17 | test_source_adapters.py:217 | Field assertions (7 fields including salary) |
| 18 | test_application_workflow.py:353 | Field assertions (`job_variant_id`, `cover_letter_id`, `tailoring_applied`) |
| 19 | test_application_workflow.py:549 | Field assertions (`job_variant_status`, `cover_letter_status`, `approved_at`) |
| 20 | test_application_workflow.py:814 | Field assertions + DB validation |
| 21 | test_application_workflow.py:934 | Field assertions (`application_id`, `timeline_event_id`, `status`) |
| 22 | test_pdf_generation.py:665 | `pdf_bytes[:5] == b"%PDF-"` |
| 23 | test_pdf_generation.py:767 | Magic-bytes + `len(pdf_bytes) > 1000` |
| 24 | test_pdf_generation.py:797 | Magic-bytes + size assertion |
| 25 | test_pdf_generation.py:810 | Magic-bytes + size assertion |
| 26 | test_retention_cleanup.py:299 | `deleted_resume_pdfs >= 1` + DB validation |
| 27 | test_retention_cleanup.py:517 | `deleted_job_variants >= 1` + DB checks |
| 28 | test_retention_cleanup.py:832 | Multiple field assertions |
| 29 | test_ghostwriter_prompts.py:217 | `len(result) > 0` |
| 30 | test_ghostwriter_prompts.py:276 | Content substring checks |
| 31 | test_ghostwriter_prompts.py:551 | `"<job_posting>" in result` |
| 32 | test_cover_letter_validation.py:462 | Boundary validation (non-raising) |
| 33 | test_cover_letter_pdf_storage.py:230 | `result` exists with expected data |
| 34 | test_cover_letter_pdf_storage.py:231 | `result.already_existed is False` |
| 35 | test_cover_letter_pdf_generation.py:148 | `pdf_bytes[:5] == b"%PDF-"` |
| 36 | test_cover_letter_pdf_generation.py:315 | Magic-bytes + `len > 500` |
| 37 | test_cover_letter_pdf_generation.py:329 | `endswith(".pdf")` + name content |
| 39 | test_pool_surfacing_service.py:445 | `jobs_processed >= 2`, `links_created >= 1` |
| 40 | test_embedding_cost.py:73 | Field assertions (`total_tokens`, `price_per_1k_tokens`) |
| 41 | test_oauth_helpers.py:170 | URL + scope content assertions |
| 42 | test_oauth_helpers.py:183 | URL + scope content assertions |
| 43 | test_agent_handoff.py:274 | Field assertions (`handoff_type`, `source_agent`, `target_agent`) |
| 44 | test_api_filtering.py:161 | `result.fields` content assertion |
| 45 | test_job_posting_schemas.py:133 | Nested field assertions (`job_title`, `company_name`) |
| 46 | test_job_deduplication.py:1286 | `tzinfo is not None` |
| 47 | test_job_deduplication.py:1584 | `"T" in found_at` (ISO format check) |
| 48 | test_claude_adapter.py:662 | Content block assertions (text, tool_use) |
| 49 | test_job_status_transitions.py:183 | `dismissed_at.tzinfo is not None` |
| 50 | test_job_status_transitions.py:193 | `expired_at.tzinfo is not None` |
| 51 | test_api_errors.py:47 | `str(error) == "Test"` |
| 52 | test_batch_scoring.py:262 | `results[0].job_id` field assertion |
| 53 | test_batch_scoring.py:264 | Nested field assertions |
| 54 | test_batch_scoring.py:265 | Nested field assertions |
| 55 | test_bullet_reordering.py:328 | Content assertions (`"job-1" in result`, value checks) |
| 56 | test_base_resume_selection.py:200 | `result.base_resume_id == resume.id` |
| 57 | test_persona_sync.py:281 | `result.resolution`, `result.resumes_updated` |
| 58 | test_source_selection.py:39 | `set(result.prioritized_sources) == set(enabled_sources)` |
| 59 | test_cover_letter_output.py:195 | `record["achievement_stories_used"]`, `record["status"]` |
| 62 | test_agent_message.py:237 | `result["role"]`, `result["content"]` |
| 63 | test_ghost_detection.py:507 | Key presence + nested checks |
| 64 | test_ghost_detection.py:512 | Implicit content assertions |
| 65 | test_openai_embedding_adapter.py:89 | `len(result.vectors)`, `result.model`, `result.dimensions` |
