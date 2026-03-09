# Backend Test Suite Deep Audit — Plan

**Created:** 2026-03-09
**Status:** Ready for implementation
**Baseline:** 4,608 tests across 195 files

---

## Context

Follow-up to the initial Backend Test Suite Audit (§28, complete). That audit addressed isinstance, len(), and constant antipatterns. This second pass goes deeper — identifying tests that provide no real protection against bugs, and analyzing ambiguous Tier 2 patterns to inform future policy.

**Philosophy:** Test behavior > implementation, except when implementation testing is truly useful for maintainability or finding severe bugs/risk.

---

## How to Use This Document

1. Find the first ⬜ task — that's where to start
2. Each task = one commit, sized for ~60k variable tokens
3. After each task: update status → commit → STOP and ask user
4. Phase 2 is read-only analysis — no code changes, output is an appendix to this plan

---

## Dependency Chain

```
Phase 1: Tier 1 Cleanup (delete/refactor low-value tests)
    ↓
Phase 2: Tier 2 Deep Analysis (read-only code tracing)
    ↓
Phase 3: Quality Gate (verify + document findings)
```

---

## Phase 1: Tier 1 Cleanup

**Status:** ⬜ Incomplete

*Delete or consolidate tests that provide no protection against real bugs. These are clear-cut — no judgment calls needed.*

#### Workflow
| Step | Action |
|------|--------|
| 🧪 **Verify** | Run affected test file before AND after changes |
| 🔍 **Review** | `code-reviewer` + `qa-reviewer` |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1.1 | **Delete `test_agent_client.py` delegation tests** — All 25 async tests in classes `TestJobPostingMethods`, `TestApplicationMethods`, `TestBaseResumeMethods`, `TestJobVariantMethods`, `TestCoverLetterMethods`, `TestPersonaMethods`, `TestPersonaChangeFlagMethods`, `TestRefreshMethods` are pure `.assert_called_once_with()` on a mocked `_request`. Zero behavioral assertions. **Keep:** `TestGetAgentClient` (2 tests — singleton/reset behavior). **Keep:** `MockAgentClient` class + fixtures (used by kept tests). Delete `MockAgentClient._request` method definition (lines 37-48) since it's only needed for the delegation tests. Clean up unused imports (`Any`, `uuid4`). | `plan, test` | ✅ |
| 1.2 | **Delete frozen/tautological weight tests** — In `test_fit_score_weights.py`: delete `TestFitScoreWeightSum::test_weights_sum_to_100_percent` (re-adds constants — can never fail independently of source), `TestGetFitComponentWeights::test_values_match_constants` (mirror: dict values == constants), `TestFitNeutralScore::test_neutral_score_is_reasonable` (range check on hardcoded constant). **Keep:** `test_dict_values_sum_to_100_percent` (calls accessor function, sums dynamically — actual behavior test). Same pattern in `test_stretch_score_weights.py`: delete `test_weights_sum_to_100_percent`, `test_values_match_constants`, `test_neutral_score_is_reasonable`. **Keep:** `test_dict_values_sum_to_100_percent`. Net: -6 tests, keep 2. Clean up unused imports. | `plan, test` | ✅ |
| 1.3 | **Consolidate provider name tests** — Replace 8 one-test classes in `test_provider_name.py` (lines 37-89) with a single `@pytest.mark.parametrize` test covering all 6 adapters. **Keep** `TestAbstractEnforcement` (2 tests — behavioral: verifies ABC contract). Delete `test_gemini_embedding_adapter.py::TestGeminiEmbeddingAdapterInitialization::test_provider_name_returns_gemini` (line 72-75, duplicate — covered by parametrized test) and `test_dimensions_property_returns_configured_value` (line 77-80, pass-through of config value). Net: -8 tests, +1 parametrized test = -7 tests. | `plan, test` | ✅ |
| 1.4 | **Delete constructor mirror tests in `test_admin_config_models.py`** — Delete: `TestModelRegistry::test_attributes_set_when_constructed_with_valid_data` (lines 83-96), `TestModelRegistry::test_embedding_model_type_accepted` (lines 98-106), `TestPricingConfig::test_attributes_set_when_constructed_with_valid_data` (lines 117-130), `TestPricingConfig::test_decimal_precision_preserved` (lines 132-143), `TestTaskRoutingConfig::test_attributes_set_when_constructed_with_valid_data` (lines 154-163), `TestTaskRoutingConfig::test_default_fallback_task_type_accepted` (lines 165-172), `TestFundingPack::test_attributes_set_when_constructed_with_valid_data` (lines 183-196), `TestSystemConfig::test_attributes_set_when_constructed_with_valid_data` (lines 218-228). All are mirror tests: construct ORM model with values, assert values == same values. DB integration tests in `TestAdminConfigModelsDB` already cover persistence, defaults, and constraints. **Keep:** `TestFundingPack::test_stripe_price_id_nullable`, `test_highlight_label_set_when_provided`, `test_description_nullable` (test nullable defaults — behavioral). **Keep:** `TestSystemConfig::test_description_nullable`. **Keep:** `TestUserIsAdmin` (2 tests). **Keep:** all `TestAdminConfigModelsDB` tests. Net: -8 tests. Clean up empty classes, unused imports. | `plan, test` | ⬜ |
| 1.5 | **Delete `test_api_pagination.py` mirror tests** — Delete: `test_limit_equals_per_page` (line 27-30, `limit` is literally `per_page`), `test_limit_different_per_page` (line 32-35, same pattern). **Keep:** `test_offset_page_one`, `test_offset_page_two`, `test_offset_calculation` (test computed property with non-trivial formula), `TestPaginationParamsDependency::test_offset_and_limit_work_on_result` (tests function return). Net: -2 tests. | `plan, test` | ⬜ |
| 1.6 | **Phase gate — full test suite + push** — Run test-runner in Full mode. Fix regressions, commit, push. | `plan, commands` | ⬜ |

**Phase 1 Summary:** -48 tests estimated (-25 agent client, -6 weight, -7 provider name, -8 admin config, -2 pagination)

---

## Phase 2: Tier 2 Deep Analysis

**Status:** ⬜ Incomplete

*Read-only code tracing. No code changes. For each Tier 2 category, trace representative examples from test → source to classify as "legitimate integration contract" vs "pure implementation detail." Output is Appendix A-D of this plan.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Trace** | For each category, read 3-5 representative test files + their source modules |
| 🔍 **Classify** | Apply decision criterion: "Would this test still pass if implementation changed but behavior stayed the same?" |
| 📝 **Document** | Append findings to this plan as appendices |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 2.1 | **Trace: Error message string assertions** — Read 5 representative files (`test_core_config.py`, `test_api_errors.py`, `test_cover_letter_validation.py`, `test_modification_limits.py`, `test_metering_service.py`). For each `assert "text" in error.message` or `assert "text" in str(exc)`: trace to the source function, determine if the message is user-facing (API response, UI display) or internal (log, developer exception). Classify each as BEHAVIORAL (message is part of the public contract) or IMPLEMENTATION (message is an internal detail). Record in Appendix A. | `plan` | ⬜ |
| 2.2 | **Trace: Mock `.call_args` / `.assert_called_once_with()` patterns** — Read 5 representative files (`test_metered_provider.py`, `test_openai_embedding_adapter.py`, `test_resume_parsing_service.py`, `test_cover_letter_generation.py`, `test_admin_pricing_pipeline.py`). For each call-assertion test: trace the mock boundary — is the mock replacing an external dependency (API client, DB) or an internal collaborator (helper function, sibling service)? External boundary mocks verify integration contracts (BEHAVIORAL). Internal mocks verify wiring (IMPLEMENTATION). Record in Appendix B. | `plan` | ⬜ |
| 2.3 | **Trace: Call count assertions** — Read 4 files (`test_openai_embedding_adapter.py`, `test_gemini_embedding_adapter.py`, `test_job_embedding_generation.py`, `test_retry_strategy.py`). For each `call_count == N` assertion: determine what behavior the count represents. Batching call counts test cost optimization (arguable behavioral). Retry counts test resilience policy (behavioral). Record in Appendix C. | `plan` | ⬜ |
| 2.4 | **Trace: Logging assertions (caplog)** — Read 4 files (`test_metered_provider.py`, `test_cover_letter_validation.py`, `test_metering_service.py`, `test_modification_limits.py`). For each `assert "text" in caplog.text`: determine if logging is an observability contract (ops team depends on these logs for alerting/debugging) or a pure implementation detail. Record in Appendix D. | `plan` | ⬜ |
| 2.5 | **Compile Tier 2 report** — Synthesize Appendices A-D into a summary with per-category recommendations: KEEP (legitimate), REFACTOR (partially valuable), or DELETE (pure implementation). Include decision criteria and examples for each recommendation. This becomes input for a future cleanup plan if desired. | `plan` | ⬜ |

---

## Phase 3: Quality Gate

**Status:** ⬜ Incomplete

| § | Task | Hints | Status |
|---|------|-------|--------|
| 3.1 | **Verify test count and update CLAUDE.md** — Run full pytest, compare to post-Phase-1 baseline. Update any CLAUDE.md references if needed (test count, scanner documentation). Commit. | `plan` | ⬜ |

---

## Task Count Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 1: Tier 1 Cleanup | 6 | Delete/consolidate low-value tests |
| 2: Tier 2 Analysis | 5 | Read-only code tracing |
| 3: Quality Gate | 1 | Verify + document |
| **Total** | **12** | |

---

## Critical Files Reference

| File | Role | Phase |
|------|------|-------|
| `backend/tests/unit/test_agent_client.py` | 25 delegation tests to delete | 1.1 |
| `backend/tests/unit/test_fit_score_weights.py` | 3 frozen/tautological tests to delete | 1.2 |
| `backend/tests/unit/test_stretch_score_weights.py` | 3 frozen/tautological tests to delete | 1.2 |
| `backend/tests/unit/test_provider_name.py` | 8 tests → 1 parametrized test | 1.3 |
| `backend/tests/unit/test_gemini_embedding_adapter.py` | 2 pass-through tests to delete | 1.3 |
| `backend/tests/unit/test_admin_config_models.py` | 8 constructor mirror tests to delete | 1.4 |
| `backend/tests/unit/test_api_pagination.py` | 2 mirror tests to delete | 1.5 |
| `backend/tests/unit/test_metered_provider.py` | Tier 2 analysis target | 2.2, 2.3, 2.4 |
| `backend/tests/unit/test_core_config.py` | Tier 2 analysis target | 2.1 |
| `backend/tests/unit/test_api_errors.py` | Tier 2 analysis target | 2.1 |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-03-09 | Plan created |
