# Zentropy Scout — Test Antipattern Cleanup Plan

**Created:** 2026-02-22
**Last Updated:** 2026-02-22
**Status:** Ready for Implementation
**Audit report:** `docs/tmp/test-audit-report.md`

---

## Context

The test antipattern audit identified **~306 antipattern tests** across **~53 backend test files**. These tests verify internal structure (field names, type hints, inheritance chains, enum member counts) rather than observable behavior, making them fragile to refactoring while providing minimal safety value.

**Actions:** ~279 DELETE (remove entirely) + ~27 REWRITE (preserve immutability invariant with behavioral approach).

**Starting test count:** ~4,389 tests. **Expected after cleanup:** ~4,110 tests.

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Each task = one commit, sized to stay under ~60k variable tokens
3. After each task: update status (⬜ → ✅), commit, STOP and ask user
4. Reference the audit report (`docs/tmp/test-audit-report.md`) for per-test classifications
5. After each phase: run full test suite as gate before proceeding

**Review scope (every subtask):**
- `code-reviewer` — verify only flagged tests were removed, no behavioral tests lost
- `qa-reviewer` — flag if any deleted tests were the sole coverage for a code path

---

## Phase 1: Delete Entire Files (~72 tests, 8 files)

**Status:** ✅ Complete

*Remove 8 test files where 100% of tests are antipatterns. No behavioral tests exist in these files. Simplest, highest-impact cleanup. Depends on: nothing.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read audit Section B for per-test classifications of files being deleted |
| 🗑️ **Delete** | `git rm` entire test file |
| 🧪 **Verify** | `pytest tests/ -v` + `ruff check .` — all pass, 0 skips |
| ✅ **Review** | `code-reviewer` + `qa-reviewer` |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Delete 4 structural-only files (agent/provider)** — delete `test_agent_state.py` (~20 tests, 255 lines), `test_agent_checkpoint.py` (~4 tests, 248 lines), `test_provider_fixtures.py` (~6 tests, 140 lines), `test_mock_provider.py` (~7 tests, 270 lines). All tests are STRUCTURAL or TAUTOLOGICAL per audit Section B. Run full test suite to confirm no imports or fixtures depend on these files. | `tdd, commands, plan` | ✅ |
| 2 | **Delete 4 structural-only files (interface/prompts/voice)** — delete `test_voice_profile_fields.py` (~18 tests, 247 lines), `test_llm_interface.py` (~3 tests, 556 lines), `test_embedding_interface.py` (~5 tests, 227 lines), `test_strategist_prompts.py` (~9 tests, 447 lines). All tests are STRUCTURAL per audit Sections B and D. Run full test suite. | `tdd, commands, plan` | ✅ |

---

## Phase 2: Delete Subsets & Rewrite Frozen Tests (~234 antipatterns, ~53 files)

**Status:** ⬜ Incomplete

*Remove flagged DELETE tests from mixed files (files that also contain good behavioral tests). Co-locate REWRITE work for frozen tests in the same subtask so no file is revisited twice. Organized by domain. Depends on: Phase 1 (full file deletions complete, baseline green).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read audit Section D for per-test classifications of the domain being cleaned |
| 🗑️ **Delete** | Remove individual test functions/classes flagged DELETE |
| 🧪 **Rewrite** | For REWRITE: read source implementation, write behavioral immutability test using `dataclasses.replace()` pattern (see Implementation Notes §2) |
| ✅ **Verify** | `pytest tests/ -v` + `ruff check .` — all pass, 0 skips |
| 🔍 **Review** | `code-reviewer` + `qa-reviewer` |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Domain 1a: Scoring weights & aggregation** — delete flagged tests from `test_fit_score_weights.py` (7 DEL), `test_stretch_score_weights.py` (5 DEL), `test_fit_score_aggregation.py` (3 DEL), `test_stretch_score_aggregation.py` (3 DEL), `test_score_types.py` (7 DEL). Pure DELETE, no rewrites. 5 files, 25 deletions. | `tdd, commands, plan` | ✅ |
| 2 | **Domain 1b: Scoring metrics & interpretation** — delete and rewrite flagged tests from `test_quality_metrics.py` (29 DEL + 1 RW), `test_fit_score_interpretation.py` (2 DEL + 3 RW), `test_stretch_score_interpretation.py` (2 DEL + 3 RW). Read source files to write behavioral immutability replacements. 3 files, 33 DEL + 7 REWRITE. | `tdd, commands, plan` | ✅ |
| 3 | **Domain 2: Embedding** — delete flagged tests from `test_embedding_types.py` (8 DEL), `test_embedding_storage.py` (4 DEL), `test_embedding_cost.py` (3 DEL). Note: `test_embedding_interface.py` already deleted in Phase 1. Pure DELETE. 3 files, 15 deletions. | `tdd, commands, plan` | ✅ |
| 4 | **Domain 3: Cover letter** — delete and rewrite flagged tests from `test_cover_letter_output.py` (7 DEL + 1 RW), `test_cover_letter_structure.py` (17 DEL + 1 RW), `test_cover_letter_validation.py` (1 DEL + 2 RW). Read source files for frozen test rewrites. 3 files, 25 DEL + 4 REWRITE. | `tdd, commands, plan` | ✅ |
| 5 | **Domain 4a: Agent & graph (delete-only)** — delete flagged tests from `test_scouter_error_handling.py` (3 DEL), `test_ghostwriter_graph.py` (4 DEL), `test_onboarding_agent.py` (3 DEL). Note: `test_strategist_prompts.py` deleted in Phase 1; `test_strategist_graph.py` had 0 antipatterns (audit misattributed to scouter file). 3 files, 10 deletions. | `tdd, commands, plan` | ✅ |
| 6 | **Domain 4b: Agent session guard + first-pass agent files** — delete and rewrite flagged tests from `test_agent_session_guard.py` (5 DEL), `test_agent_message.py` (5 DEL + 2 RW), `test_agent_handoff.py` (4 DEL + 1 RW). Read source files for frozen test rewrites. 3 files, 14 DEL + 3 REWRITE. | `tdd, commands, plan` | ✅ |
| 7 | **Domain 5: Provider & adapter** — delete flagged tests from `test_provider_errors.py` (7 DEL), `test_rate_limiting.py` (8 DEL), `test_ghostwriter.py` (3 DEL). Audit listed 3 for test_claude_adapter.py but those TriggerType tests only exist in test_ghostwriter.py. Actual: 3 files, 18 deletions. | `tdd, commands, plan` | ✅ |
| 8 | **Domain 6: API layer** — delete flagged tests from `test_api_responses.py` (6 DEL), `test_api_chat.py` (1 test DEL + 5 tautological type assertions removed from schema tests), `test_api_pagination.py` (3 DEL), `test_api_filtering.py` (2 DEL). Audit listed 8 DEL for test_api_chat.py but actual tests are named differently (e.g. `test_chat_token_event_schema` not `test_chat_token_event_type`); schema tests contain behavioral assertions alongside tautological type checks, so type assertions were surgically removed rather than deleting entire tests. 4 files. | `tdd, commands, plan` | ✅ |
| 9 | **Domain 7a: Data structure (heavy rewrite files)** — delete and rewrite flagged tests from `test_job_expiry.py` (6 DEL + 1 RW), `test_duplicate_story.py` (6 DEL + 1 RW), `test_regeneration.py` (6 DEL + 2 RW), `test_persona_change.py` (3 DEL + 1 RW), `test_score_explanation.py` (0 DEL + 5 RW). Read source files for 10 frozen rewrites. 5 files, 21 DEL + 10 REWRITE. | `tdd, commands, plan` | ✅ |
| 10 | **Domain 7b: Data structure (delete-only) + first-pass workflow files** — delete flagged tests from `test_ghost_detection.py` (1 DEL), `test_job_deduplication.py` (5 DEL), `test_user_review.py` (3 DEL), `test_file_validation.py` (3 DEL), `test_auto_draft_threshold.py` (2 DEL), `test_generation_outcome.py` (4 DEL + 1 RW), `test_data_availability.py` (4 DEL + 1 RW), `test_job_status_transitions.py` (4 DEL). 8 files, 26 DEL + 2 REWRITE. | `tdd, commands, plan` | ✅ |
| 11 | **Domain 8 + remaining first-pass scattered files** — delete single-antipattern tests from ~16 files: `test_golden_set_fixture.py` (1), `test_golden_set.py` (2), `test_scouter_agent.py` (1), `test_story_selection.py` (1), `test_discovery_workflow.py` (1), `test_bullet_reordering.py` (1), `test_reasoning_explanation.py` (1), `test_migration_011_rename_indexes.py` (3), `test_modification_limits.py` (1), `test_persona_embedding_generation.py` (1), `test_pool_surfacing_worker.py` (1), `test_auth_helpers.py` (1), `test_oauth_helpers.py` (2), `test_content_utils.py` (5), `test_voice_validation.py` (1), `test_voice_prompt_block.py` (1), `test_source_adapters.py` (25 — largest single-file cleanup). Pure DELETE. ~17 files, ~50 deletions. | `tdd, commands, plan` | ⬜ |
| 12 | **Phase 2 gate** — run full backend test suite: `pytest tests/ -v`, `ruff check .`. All tests must pass, 0 skips. Compare test count before vs after (expect ~4,389 → ~4,110). | `plan, commands` | ⬜ |

---

## Phase 3: Coverage Assessment & Gap Tests

**Status:** ⬜ Incomplete

*Run coverage analysis after cleanup to identify any genuine behavioral gaps created by deletions. Write replacement behavioral tests only where coverage drops reveal untested code paths. Depends on: Phase 2 (all deletions and rewrites complete, suite green).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Review Phase 2 diffs to understand what was removed |
| 🧪 **Measure** | `pytest --cov=app --cov-report=term-missing tests/` |
| ✅ **Fill gaps** | Write behavioral tests only for genuine coverage drops (>5% per module) |
| 🔍 **Review** | `code-reviewer` + `qa-reviewer` |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Coverage baseline measurement** — run `pytest --cov=app --cov-report=term-missing tests/` before and after. Identify modules where coverage dropped. Produce a gap analysis table: module, before %, after %, lines now uncovered. Only flag modules with >5% coverage drop. Expected: most deleted tests were redundant with behavioral tests in adjacent files, so coverage drop should be minimal. | `tdd, commands, plan` | ⬜ |
| 2 | **Write behavioral gap tests (if needed)** — for each module with >5% coverage drop, write behavioral tests that exercise uncovered code paths through observable behavior (function calls, return values, side effects, error handling). Do NOT recreate structural/tautological tests. Focus areas likely to need gaps filled: agent state (if state transition tests don't exist elsewhere), voice profile (if generation behavior tests don't exist elsewhere), embedding interface (if adapter behavioral tests don't cover abstract contract). | `tdd, commands, plan` | ⬜ |
| 3 | **Phase 3 gate** — run full test suite with coverage: `pytest --cov=app tests/ -v`, `ruff check .`. All tests pass. No module has >5% coverage drop without documented justification. | `plan, commands` | ⬜ |

---

## Phase 4: Regression Prevention

**Status:** ⬜ Incomplete

*Add guardrails to prevent antipattern tests from being reintroduced. Depends on: Phase 3 (coverage gaps addressed, suite green).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Review audit Section H (Priority 5) for banned patterns |
| 📝 **Document** | Add rules to CLAUDE.md Testing Philosophy section |
| ✅ **Verify** | Rules documented, optional tooling evaluated |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Add test quality rules to CLAUDE.md** — add "Test Antipatterns to Avoid" section under Testing Philosophy with banned patterns: no `isinstance()` assertions in tests, no `get_type_hints()` / `dataclasses.fields()` in tests, no `hasattr()` assertions, no `__abstractmethods__` assertions, no `enum.value == "literal"` assertions. Include the "implementation rewrite" lens question as the decision criterion. Add the behavioral frozen-test pattern as the approved alternative. | `plan` | ⬜ |
| 2 | **Evaluate automated enforcement (optional)** — investigate whether `ruff` custom rules or a lightweight pytest plugin can flag banned patterns automatically. If straightforward (<30 min), implement. If complex, document as a future backlog item. This is a nice-to-have, not a blocker. | `lint, plan` | ⬜ |

---

## Status Legend

| Icon | Meaning |
|------|---------|
| ⬜ | Incomplete |
| 🟡 | In Progress |
| ✅ | Complete |

---

## Dependency Chain

```
Phase 1: Delete Entire Files (8 files, ~72 tests)
    │   Remove 100%-antipattern test files
    ↓
Phase 2: Delete Subsets & Rewrite Frozen Tests (~53 files, ~234 antipatterns)
    │   Remove flagged tests from mixed files, rewrite frozen tests
    ↓
Phase 3: Coverage Assessment & Gap Tests
    │   Measure coverage impact, fill genuine gaps only
    ↓
Phase 4: Regression Prevention
        Document rules, optional tooling
```

---

## Implementation Notes

1. **One commit per subtask** — matches existing plan convention. Do NOT batch deletions across subtasks.

2. **Frozen test rewrite pattern** — all REWRITE tests follow this behavioral approach:
   ```python
   # BEFORE (antipattern): Tests Python's frozen mechanism
   def test_result_is_frozen():
       result = SomeResult(field="value")
       with pytest.raises(FrozenInstanceError):
           result.field = "new"

   # AFTER (behavioral): Tests immutability through public API
   def test_result_preserves_original_value():
       result = SomeResult(field="value")
       updated = replace(result, field="new")
       assert result.field == "value"  # Original unchanged
       assert updated.field == "new"   # New copy has new value
   ```

3. **Domain grouping** — Phase 2 subtasks follow the audit's 8 domains, keeping related files together for context efficiency.

4. **First-pass files distributed** — the 9 files from the first-pass audit are merged into their appropriate domain subtasks (P2-§6 for agent files, P2-§10 for workflow files, P2-§11 for scattered single-test files) to avoid revisiting files.

5. **Large file reads** — for large test files in Domain 4a (P2-§5), use offset/limit to target only the specific test classes being deleted rather than reading the entire file.

6. **No duplication across phases** — `test_strategist_prompts.py` and `test_embedding_interface.py` are deleted in Phase 1 and explicitly excluded from their respective domain subtasks in Phase 2.

7. **Test count validation** — starting count ~4,389. After cleanup: ~4,389 - ~279 (deleted) + ~27 (rewritten as behavioral tests) = ~4,110. Phase 2 gate (§12) should verify this via before/after test count comparison.

8. **Per-subtask counts are approximate** — the audit uses `~` approximations throughout, and some files were counted in both the first-pass (Section B) and second-pass domain tables (Section D). The per-subtask DELETE/REWRITE counts are sourced from per-file audit tables and will sum to slightly more than the deduplicated totals (~279 DELETE, ~27 REWRITE). The Phase 2 gate (§12) should rely on the actual before/after test count difference rather than trying to match a precise per-subtask sum.

9. **Classification rules** — the audit uses these patterns to identify antipatterns:

   | Pattern | Category | Action |
   |---------|----------|--------|
   | `enum.value == "string"` | TAUTOLOGICAL | DELETE |
   | `CONSTANT == 42` | TAUTOLOGICAL | DELETE |
   | `len(enum) == N` | TAUTOLOGICAL | DELETE |
   | `isinstance(x, Class)` | STRUCTURAL | DELETE |
   | `issubclass(X, Y)` | STRUCTURAL | DELETE |
   | `get_type_hints()` field checks | STRUCTURAL | DELETE |
   | `hasattr(x, "field")` | STRUCTURAL | DELETE |
   | `__abstractmethods__` checks | STRUCTURAL | DELETE |
   | `frozen=True` via `FrozenInstanceError` | FROZEN | REWRITE |

---

## Task Count Summary

| Phase | Subtasks | DELETE | REWRITE | Focus |
|-------|----------|--------|---------|-------|
| Phase 1 | 2 | ~72 | 0 | Delete entire antipattern-only files |
| Phase 2 | 12 | ~207 | ~27 | Delete subsets + rewrite frozen tests |
| Phase 3 | 3 | 0 | TBD | Coverage gap assessment + fill |
| Phase 4 | 2 | 0 | 0 | Documentation + optional tooling |
| **Total** | **19** | **~279** | **~27** | |
