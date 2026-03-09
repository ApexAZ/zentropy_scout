# Backend Test Suite Deep Audit — Plan

**Created:** 2026-03-09
**Status:** ✅ Complete
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

**Status:** ✅ Complete

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
| 1.4 | **Delete constructor mirror tests in `test_admin_config_models.py`** — Delete: `TestModelRegistry::test_attributes_set_when_constructed_with_valid_data` (lines 83-96), `TestModelRegistry::test_embedding_model_type_accepted` (lines 98-106), `TestPricingConfig::test_attributes_set_when_constructed_with_valid_data` (lines 117-130), `TestPricingConfig::test_decimal_precision_preserved` (lines 132-143), `TestTaskRoutingConfig::test_attributes_set_when_constructed_with_valid_data` (lines 154-163), `TestTaskRoutingConfig::test_default_fallback_task_type_accepted` (lines 165-172), `TestFundingPack::test_attributes_set_when_constructed_with_valid_data` (lines 183-196), `TestSystemConfig::test_attributes_set_when_constructed_with_valid_data` (lines 218-228). All are mirror tests: construct ORM model with values, assert values == same values. DB integration tests in `TestAdminConfigModelsDB` already cover persistence, defaults, and constraints. **Keep:** `TestFundingPack::test_stripe_price_id_nullable`, `test_highlight_label_set_when_provided`, `test_description_nullable` (test nullable defaults — behavioral). **Keep:** `TestSystemConfig::test_description_nullable`. **Keep:** `TestUserIsAdmin` (2 tests). **Keep:** all `TestAdminConfigModelsDB` tests. Net: -8 tests. Clean up empty classes, unused imports. | `plan, test` | ✅ |
| 1.5 | **Delete `test_api_pagination.py` mirror tests** — Delete: `test_limit_equals_per_page` (line 27-30, `limit` is literally `per_page`), `test_limit_different_per_page` (line 32-35, same pattern). **Keep:** `test_offset_page_one`, `test_offset_page_two`, `test_offset_calculation` (test computed property with non-trivial formula), `TestPaginationParamsDependency::test_offset_and_limit_work_on_result` (tests function return). Net: -2 tests. | `plan, test` | ✅ |
| 1.6 | **Phase gate — full test suite + push** — Run test-runner in Full mode. Fix regressions, commit, push. | `plan, commands` | ✅ |

**Phase 1 Actual:** -43 tests (4,608 → 4,565). -25 agent client, -6 weight, -2 provider name consolidation, -8 admin config, -2 pagination.

---

## Phase 2: Tier 2 Deep Analysis

**Status:** ✅ Complete

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
| 2.1 | **Trace: Error message string assertions** — Read 5 representative files (`test_core_config.py`, `test_api_errors.py`, `test_cover_letter_validation.py`, `test_modification_limits.py`, `test_metering_service.py`). For each `assert "text" in error.message` or `assert "text" in str(exc)`: trace to the source function, determine if the message is user-facing (API response, UI display) or internal (log, developer exception). Classify each as BEHAVIORAL (message is part of the public contract) or IMPLEMENTATION (message is an internal detail). Record in Appendix A. | `plan` | ✅ |
| 2.2 | **Trace: Mock `.call_args` / `.assert_called_once_with()` patterns** — Read 5 representative files (`test_metered_provider.py`, `test_openai_embedding_adapter.py`, `test_resume_parsing_service.py`, `test_cover_letter_generation.py`, `test_admin_pricing_pipeline.py`). For each call-assertion test: trace the mock boundary — is the mock replacing an external dependency (API client, DB) or an internal collaborator (helper function, sibling service)? External boundary mocks verify integration contracts (BEHAVIORAL). Internal mocks verify wiring (IMPLEMENTATION). Record in Appendix B. | `plan` | ✅ |
| 2.3 | **Trace: Call count assertions** — Read 4 files (`test_openai_embedding_adapter.py`, `test_gemini_embedding_adapter.py`, `test_job_embedding_generation.py`, `test_retry_strategy.py`). For each `call_count == N` assertion: determine what behavior the count represents. Batching call counts test cost optimization (arguable behavioral). Retry counts test resilience policy (behavioral). Record in Appendix C. | `plan` | ✅ |
| 2.4 | **Trace: Logging assertions (caplog)** — Read 4 files (`test_metered_provider.py`, `test_cover_letter_validation.py`, `test_metering_service.py`, `test_modification_limits.py`). For each `assert "text" in caplog.text`: determine if logging is an observability contract (ops team depends on these logs for alerting/debugging) or a pure implementation detail. Record in Appendix D. | `plan` | ✅ |
| 2.5 | **Compile Tier 2 report** — Synthesize Appendices A-D into a summary with per-category recommendations: KEEP (legitimate), REFACTOR (partially valuable), or DELETE (pure implementation). Include decision criteria and examples for each recommendation. This becomes input for a future cleanup plan if desired. | `plan` | ✅ |

---

## Phase 3: Quality Gate

**Status:** ✅ Complete

| § | Task | Hints | Status |
|---|------|-------|--------|
| 3.1 | **Verify test count and update CLAUDE.md** — Run full pytest, compare to post-Phase-1 baseline. Update any CLAUDE.md references if needed (test count, scanner documentation). Commit. | `plan` | ✅ |

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
| 2026-03-09 | Phase 1 complete: -43 tests (4,608 → 4,565), 5 commits |
| 2026-03-09 | §2.1 complete: Appendix A — error message assertion trace |
| 2026-03-09 | §2.2 complete: Appendix B — mock call_args trace |
| 2026-03-09 | §2.3 complete: Appendix C — call count assertion trace |
| 2026-03-09 | §2.4 complete: Appendix D — logging/caplog assertion trace |
| 2026-03-09 | §2.5 complete: Tier 2 synthesis report |
| 2026-03-09 | Phase 2 complete |
| 2026-03-09 | §3.1 complete: 4,565 tests passing, no CLAUDE.md changes needed |
| 2026-03-09 | Phase 3 complete — plan finished |

---

## Appendix A: Error Message String Assertions (§2.1)

**37 assertions traced across 5 files.**

### Classification Summary

| Category | Count | User-Facing? | Contract Type |
|----------|-------|--------------|---------------|
| Configuration startup errors | 6 | NO — dev only | N/A |
| API error codes (`error.code`) | 2 | YES | **FULL** — frontend depends on code |
| API error default messages | 6 | YES | **PARTIAL** — message is human-readable detail, code is the contract |
| Validation issue messages | 9 | YES | **PARTIAL** — info must appear, wording is variable |
| Violation messages | 9 | YES | **PARTIAL** — info must appear, wording is variable |
| Debug logging assertions | 5 | NO — dev only | N/A |

### Per-File Breakdown

**`test_core_config.py` (6 assertions)** — All INTERNAL. Pydantic ValidationError messages during startup. Never reach API. Tests verify that specific misconfiguration is caught, but exact wording is an implementation detail. **Recommendation: KEEP** — these are the only way to verify the right validation rule fired (without wording, `pytest.raises(ValidationError)` alone would pass for any validation failure).

**`test_api_errors.py` (13 assertions)** — All USER-FACING. Error classes are serialized to JSON API responses. The `error.code` + `status_code` are the behavioral contract (frontend switches on these). The `error.message` is informational. However, default messages like "Authentication required" serve as documentation of the error class contract. **Recommendation: KEEP** — message assertions on default errors document the contract. Custom message assertions are lower value but harmless.

**`test_cover_letter_validation.py` (5 msg + 2 log assertions)** — Message assertions check ValidationIssue.message field (returned to UI). Tests verify that specific values appear (e.g., "100" for word count, "synergy" for buzzword). This is partially behavioral — the info must be in the message. Log assertions are internal. **Recommendation: KEEP message assertions, CONSIDER removing log assertions** (the 2 caplog assertions in `test_logs_issue_count_on_pass/fail`).

**`test_modification_limits.py` (9 msg + 1 log assertion)** — Violation messages are user-facing (shown in Ghostwriter diff view). Tests verify specific data appears (bullet ID, skill name, word counts). **Recommendation: KEEP message assertions** — they ensure required info is present. The 1 log assertion is removable.

**`test_metering_service.py` (2 code + 1 log assertion)** — The 2 error code assertions are fully behavioral. The 1 caplog assertion is internal. **Recommendation: KEEP code assertions, CONSIDER removing log assertion.**

### Verdict

**Overall: KEEP the vast majority.** Error message assertions in this codebase are mostly legitimate:
- Config startup messages → only way to verify which validation rule fired
- API error messages → document the error contract
- Validation messages → verify required information is present

**Small opportunity:** 5 caplog/logging assertions across 3 files could be removed as pure implementation details. These test log message wording, not behavior. However, this is low-value cleanup (~5 lines) and may not be worth a dedicated task.

---

## Appendix B: Mock `.call_args` / `.assert_called_once_with()` Patterns (§2.2)

**~25 mock call assertions traced across 5 files.**

### Classification Framework

| Mock Boundary | What It Tests | Verdict |
|---------------|---------------|---------|
| External dependency (OpenAI/Anthropic/Gemini API client) | Integration contract — correct API parameters | BEHAVIORAL if paired with result assertions; IMPLEMENTATION if sole assertion |
| Internal collaborator (MeteringService, AdminConfigService) | Service-to-service contract | ACCEPTABLE — documents integration boundaries |
| Internal helper (sanitize, prompt builder) | Internal wiring | IMPLEMENTATION — should assert on output instead |

### Per-File Breakdown

**`test_metered_provider.py` (~10 mock assertions)** — Mocks MeteringService and AdminConfigService (internal collaborators). Mix of behavioral and implementation:
- `test_records_correct_arguments` — Verifies metering receives correct provider/model/tokens. **ACCEPTABLE** — documents the metering contract.
- `test_does_not_record_on_provider_error` — `.assert_not_called()` paired with error propagation check. **GOOD** — behavioral.
- `test_dispatches_to_claude_adapter` — Checks which adapter was called via `len(adapter.calls)`. **GOOD** — verifies dispatch behavior.
- `test_routing_lookup_passes_task_value` — Pure `.call_args` on AdminConfigService. **IMPLEMENTATION** — should assert on routing outcome instead.
- `test_routing_used_for_different_task_types` — Inspects `.call_args_list`. **IMPLEMENTATION** — should verify different models were used.

**`test_openai_embedding_adapter.py` (~4 mock assertions)** — Mocks OpenAI API client (external dependency):
- `test_embed_calls_api_with_correct_parameters` — Pure `.assert_called_once_with()`. **IMPLEMENTATION** — should assert on returned EmbeddingResult instead.
- `test_small_batch_uses_single_api_call` — `.call_count == 1` paired with result assertions. **MIXED** — behavioral assertions are sufficient; call_count is redundant.
- `test_large_batch_chunks_into_multiple_calls` — `.call_count == 2` paired with result length check. **MIXED** — same pattern.

**`test_resume_parsing_service.py` (~5 mock assertions)** — Mocks LLMProvider (external) and sanitize helper (internal):
- `test_sends_resume_parsing_task_type` — `.call_args` to verify TaskType. **IMPLEMENTATION** — should assert on parsed result.
- `test_includes_system_prompt` — `.call_args` to verify message structure. **IMPLEMENTATION** — should assert on parsed result.
- `test_sanitizes_extracted_text` — `.assert_called_once()` plus behavioral content check. **MIXED** — behavioral assertion is sufficient.
- `test_parses_full_response_into_result` — Pure behavioral. **IDEAL PATTERN.**

**`test_cover_letter_generation.py` (~2 mock assertions)** — Mocks LLMProvider (external):
- `test_calls_provider_with_cover_letter_task_type` — `.call_args` for TaskType. **IMPLEMENTATION.**
- `test_builds_system_and_user_messages` — `.call_args` for message structure. **IMPLEMENTATION.**
- `test_result_contains_content_field` — Pure behavioral. **IDEAL PATTERN.**

**`test_admin_pricing_pipeline.py` (~3 mock assertions)** — Integration tests with real DB + mocked adapters:
- `test_routing_exact_match_passes_model_override` — `.call_args` to verify model_override. **ACCEPTABLE** — proves routing resolved from real DB.
- `test_metered_provider_full_pipeline` — Mix of `.call_args` + DB record assertions + balance check. **GOOD** — comprehensive integration test.

### Verdict

**Three categories of mock call assertions exist in this codebase:**

1. **KEEP (~15 assertions):** Internal service contract assertions (metering args, routing model_override) and integration tests with real DB. These document important boundaries and would be expensive to replace with purely behavioral alternatives.

2. **REFACTOR CANDIDATE (~8 assertions):** Tests where `.call_args` is the SOLE assertion and a behavioral assertion on the return value would be both more robust and more meaningful. Concentrated in:
   - `test_openai_embedding_adapter.py::test_embed_calls_api_with_correct_parameters`
   - `test_resume_parsing_service.py::test_sends_resume_parsing_task_type`, `test_includes_system_prompt`
   - `test_cover_letter_generation.py::test_calls_provider_with_cover_letter_task_type`, `test_builds_system_and_user_messages`

3. **REDUNDANT (~2 assertions):** Mock assertions that duplicate a behavioral assertion in the same test. E.g., `test_sanitizes_extracted_text` has both `.assert_called_once()` AND a content assertion — the mock check adds nothing.

**Recommendation:** The ~8 "sole assertion" tests are the highest-value refactor targets. Each could be improved by asserting on the function's return value instead of inspecting mock internals. However, this is a moderate-effort change (each test needs a behavioral assertion designed) and the existing tests DO catch real bugs (wrong TaskType, missing messages). **Priority: LOW-MEDIUM.**

---

## Appendix C: Call Count Assertions (§2.3)

**17 assertions traced across 4 files.**

### Classification Framework

| Call Count Type | What It Tests | Verdict |
|----------------|---------------|---------|
| Batching strategy (N calls for M inputs) | Cost optimization — fewer API calls = lower cost | BEHAVIORAL if paired with result assertions |
| Retry count (N calls after errors) | Resilience policy — retry budget enforcement | BEHAVIORAL — directly verifies the retry contract |
| Short-circuit (0 or 1 call) | Optimization — skip unnecessary work | BEHAVIORAL if paired with result assertions |
| Call verification (assert_called_once) | "Function was invoked" | SUPPLEMENTARY if result assertion exists alongside |

### Per-File Breakdown

**`test_openai_embedding_adapter.py` (3 assertions)**

| Line | Test | Count | Paired Assertions | Classification |
|------|------|-------|--------------------|----------------|
| 182 | `test_small_batch_uses_single_api_call` | `== 1` | `len(result.vectors) == 100`, `total_tokens == 500` | **BEHAVIORAL** — verifies no unnecessary chunking |
| 210 | `test_large_batch_chunks_into_multiple_calls` | `== 2` | `len(result.vectors) == 3000` | **BEHAVIORAL** — verifies chunking at 2048 boundary |
| 253 | `test_exactly_2048_uses_single_call` | `== 1` | `len(result.vectors) == 2048`, `total_tokens` | **BEHAVIORAL** — boundary check |

Brittleness: The count `== 2` on line 210 depends on the batch constant (2048). Changing the constant would break this test. However, the test is correctly testing the batching behavior — if the constant changes, the test *should* be updated to reflect new expected behavior.

**`test_gemini_embedding_adapter.py` (5 assertions)**

| Line | Test | Count | Paired Assertions | Classification |
|------|------|-------|--------------------|----------------|
| 118 | `test_embed_calls_api_with_correct_parameters` | `assert_called_once()` | `.call_args` inspection | **IMPLEMENTATION** — paired only with call_args (no result assertion) |
| 179 | `test_embed_empty_list_returns_empty_result` | `assert_not_called()` | `vectors == []`, `total_tokens == 0`, `model`, `dimensions` | **BEHAVIORAL** — verifies API is skipped for empty input |
| 197 | `test_small_batch_uses_single_api_call` | `== 1` | `len(result.vectors) == 50`, `total_tokens == 62` | **BEHAVIORAL** |
| 218 | `test_large_batch_chunks_into_multiple_calls` | `== 3` | `len(result.vectors) == 250` | **BEHAVIORAL** — 250/100 = 3 chunks |
| 251 | `test_exactly_100_uses_single_call` | `== 1` | `len(result.vectors) == 100`, `total_tokens == 125` | **BEHAVIORAL** — boundary |

Brittleness: Line 218 depends on batch constant (100). Same rationale as OpenAI — intentional coupling to the batching policy.

**`test_job_embedding_generation.py` (2 assertions)**

| Line | Test | Count | Paired Assertions | Classification |
|------|------|-------|--------------------|----------------|
| 328 | `test_generates_both_embedding_types` | `== 2` | `result.requirements is not None`, `result.culture is not None` | **BEHAVIORAL** — verifies two separate embeddings generated |
| 436 | `test_uses_neutral_embedding_for_missing_culture` | `== 1` | `all(v == 0.0 for v in result.culture.vector)`, `source_text == ""` | **BEHAVIORAL** — verifies culture embedding skipped when missing |

Brittleness: LOW — count is inherent to the domain (requirements + culture = 2 types).

**`test_retry_strategy.py` (6 assertions)**

| Line | Test | Count | Paired Assertions | Classification |
|------|------|-------|--------------------|----------------|
| 44 | `test_returns_result_on_success` | `assert_called_once()` | `result == "success"` | **SUPPLEMENTARY** — result assertion already proves success |
| 55 | `test_succeeds_after_transient_error` | `== 2` | `result == "success"` | **BEHAVIORAL** — verifies exactly 1 retry occurred |
| 66 | `test_succeeds_after_rate_limit_error` | `== 2` | `result == "success"` | **BEHAVIORAL** — same pattern |
| 85 | `test_raises_after_max_retries_exceeded` | `== 4` | `pytest.raises(TransientError)` | **BEHAVIORAL** — verifies max retry budget (1 initial + 3 retries) |
| 96 | `test_non_retryable_error_fails_immediately` | `assert_called_once()` | `pytest.raises(AuthenticationError)` | **BEHAVIORAL** — verifies no retry for non-retryable errors |
| 246 | `test_custom_retryable_errors` | `== 2` | `result == "success"` | **BEHAVIORAL** — verifies custom error type was retried |

Brittleness: LOW — retry counts are the core behavioral contract of a retry strategy.

### Verdict

| Classification | Count | Details |
|---------------|-------|---------|
| BEHAVIORAL | 14 | Paired with result/outcome assertions; count IS the behavior being tested |
| SUPPLEMENTARY | 2 | Result assertion already proves the point (retry L44, Gemini L118 is IMPL) |
| IMPLEMENTATION | 1 | Gemini L118 — paired only with `.call_args`, no result assertion |

**Overall: KEEP all.** Call count assertions in this codebase overwhelmingly test real behavioral contracts:
- **Batching tests** (7) verify cost optimization — "don't make unnecessary API calls"
- **Retry tests** (6) verify resilience policy — "retry exactly N times"
- **Short-circuit tests** (2) verify optimization — "skip work when input is empty/missing"

The 1 IMPLEMENTATION assertion (Gemini L118) is part of a test already flagged in Appendix B as a call_args inspection pattern. The 2 SUPPLEMENTARY assertions are harmless — they redundantly confirm what the result assertion already proves.

**No cleanup recommended.** The batching tests are brittle to constant changes (batch size), but this is intentional coupling to the batching policy — if the batch size changes, the tests should be updated.

---

## Appendix D: Logging Assertions (caplog) (§2.4)

**9 assertions traced across 4 files, spanning 9 test functions.**

### Classification Framework

| Log Assertion Context | Contract Type | Verdict |
|----------------------|---------------|---------|
| Sole assertion in test (only thing tested is log output) | Developer convenience | REMOVABLE — behavioral contract tested elsewhere |
| Supplementary to behavioral assertion (logging + no-raise) | Mixed | LOW VALUE — no-raise is the real contract |
| Audit/compliance logging | Operational contract | KEEP — ops team depends on these |

### Per-File Breakdown

**`test_metered_provider.py` (2 tests, 3 assertions)**

| Line | Test | Log Assertion | Behavioral Companion? | Classification |
|------|------|---------------|----------------------|----------------|
| 205-206 | `test_logs_when_recording_fails` | `str(TEST_USER_ID) in caplog.text` + `"Failed to record" in caplog.text` | YES — `test_response_returned_when_recording_fails` (L191-194) verifies response still returned | **SOLE ASSERTION** — entire test is about logging; behavioral contract covered separately |
| 349 | `test_fallback_logs_warning` | `"No routing" in caplog.text` | PARTIAL — no explicit companion, but the test implicitly verifies complete() doesn't raise | **SOLE ASSERTION** — logging is the only explicit assertion |

**`test_cover_letter_validation.py` (2 tests, 4 assertions)**

| Line | Test | Log Assertion | Behavioral Companion? | Classification |
|------|------|---------------|----------------------|----------------|
| 475-476 | `test_logs_issue_count_on_pass` | `"0 issue(s)" in caplog.text` + `"passed=True" in caplog.text` | YES — dozens of other tests verify pass/fail behavior | **SOLE ASSERTION** — dedicated logging test |
| 481-482 | `test_logs_issue_count_on_fail` | `"1 issue(s)" in caplog.text` + `"passed=False" in caplog.text` | YES — same companion set | **SOLE ASSERTION** — dedicated logging test |

**`test_metering_service.py` (3 tests, 3 assertions)**

| Line | Test | Log Assertion | Behavioral Companion? | Classification |
|------|------|---------------|----------------------|----------------|
| 286 | `test_insufficient_balance_logs_warning` | `"insufficient" in caplog.text.lower()` | YES — `test_insufficient_balance_does_not_raise` (L288-300) tests the no-raise contract | **SOLE ASSERTION** — logging is the only explicit check |
| 316 | `test_db_error_logs_and_does_not_raise` | `"failed to record usage" in caplog.text.lower()` | SELF — test name implies no-raise (implicit assertion), logging is explicit | **MIXED** — implicit no-raise + explicit logging |
| 388 | `test_unregistered_model_in_record_and_debit_logs_error` | `"failed to record usage" in caplog.text.lower()` | SELF — same pattern as above | **MIXED** — implicit no-raise + explicit logging |

**`test_modification_limits.py` (2 tests, 2 assertions)**

| Line | Test | Log Assertion | Behavioral Companion? | Classification |
|------|------|---------------|----------------------|----------------|
| 438 | `test_logs_validation_result` | `any("0 violation" in r.message for r in caplog.records)` | YES — many other tests verify validation behavior | **SOLE ASSERTION** — dedicated logging test |
| 448 | `test_logs_violation_count` | `any("1 violation" in r.message for r in caplog.records)` | YES — same companion set | **SOLE ASSERTION** — dedicated logging test |

### Fragility Analysis

All 9 assertions match on exact substrings in log messages:
- `"Failed to record"`, `"No routing"`, `"0 issue(s)"`, `"passed=True"`, `"insufficient"`, `"failed to record usage"`, `"0 violation"`, `"1 violation"`

Any rewording of these log messages (even minor changes like "Failed to record" → "Recording failed") breaks the test. Since these are DEBUG/WARNING/ERROR messages with no API or UI contract, they are free to be reworded during refactoring.

### Verdict

| Classification | Count | Details |
|---------------|-------|---------|
| SOLE ASSERTION (logging only) | 7 | Entire test exists to verify log output; behavioral contract covered by companion tests |
| MIXED (implicit no-raise + logging) | 2 | test_metering_service L316, L388 — no-raise is the real contract |

**Overall: All 9 are REMOVABLE without losing behavioral coverage.**

- None are audit/compliance logs (no regulatory or operational contract)
- All are DEBUG or WARNING or ERROR level developer convenience logging
- Every test has a companion test that verifies the same behavioral contract without logging
- All are fragile to message rewording

**Recommendation: LOW PRIORITY cleanup.** Removing these 9 assertions (and their 7 dedicated test functions) would eliminate ~9 fragile assertions and reduce test count by 7. However, the effort-to-value ratio is poor — these tests don't actively harm anything, they just don't add protection. **Consider removing only when touching these files for other reasons.**

---

## Tier 2 Synthesis Report (§2.5)

### Executive Summary

**83 Tier 2 assertions traced across 18 files, classified into 4 categories.**

| Category | Assertions | KEEP | REFACTOR | REMOVE |
|----------|-----------|------|----------|--------|
| A. Error message strings | 37 | 32 | 0 | 5 (caplog) |
| B. Mock call_args | ~25 | ~15 | ~8 | ~2 |
| C. Call counts | 17 | 14 | 0 | 0 |
| D. Logging (caplog) | 9 | 0 | 0 | 9 |
| **Total** | **~88** | **~61** | **~8** | **~16** |

### Per-Category Recommendations

#### A. Error Message String Assertions — KEEP (86%)

**Decision:** Error messages in this codebase are overwhelmingly part of behavioral contracts. Config startup messages are the only way to verify which validation rule fired. API error codes/messages document the frontend contract. Validation messages verify required information is surfaced to users.

**Exception:** 5 caplog-based assertions in error message tests (covered in Category D below).

**Action required:** None.

#### B. Mock `.call_args` Assertions — MIXED

**Decision:** Three tiers emerged from the trace:

1. **KEEP (~15):** Service contract assertions (metering receives correct provider/model/tokens, routing passes model_override) and integration tests with real DB. These document important boundaries where the mock replaces an external dependency or service integration point.

2. **REFACTOR CANDIDATE (~8):** Tests where `.call_args` is the SOLE meaningful assertion. A behavioral assertion on the function's return value would be more robust. Concentrated in:
   - `test_openai_embedding_adapter.py::test_embed_calls_api_with_correct_parameters`
   - `test_gemini_embedding_adapter.py::test_embed_calls_api_with_correct_parameters`
   - `test_resume_parsing_service.py::test_sends_resume_parsing_task_type`, `test_includes_system_prompt`
   - `test_cover_letter_generation.py::test_calls_provider_with_cover_letter_task_type`, `test_builds_system_and_user_messages`
   - `test_metered_provider.py::test_routing_lookup_passes_task_value`, `test_routing_used_for_different_task_types`

3. **REDUNDANT (~2):** Mock assertions that duplicate a behavioral assertion in the same test. Safe to remove.

**Action required:** LOW-MEDIUM priority. The ~8 refactor candidates are real improvements but each needs a behavioral assertion designed. Consider addressing when touching these files for other reasons.

#### C. Call Count Assertions — KEEP (100%)

**Decision:** Call counts in this codebase test real behavioral contracts, not implementation details:
- **Batching tests (7):** "Don't make more API calls than necessary" — cost optimization is observable behavior from the user's perspective (billing).
- **Retry tests (6):** "Retry exactly N times before giving up" — retry budget is a documented resilience policy.
- **Short-circuit tests (2):** "Skip unnecessary work when input is empty/missing."
- 14/17 are paired with result assertions. The remaining 3 (2 supplementary, 1 implementation) are harmless.

**Action required:** None.

#### D. Logging Assertions (caplog) — REMOVE (100%)

**Decision:** All 9 caplog assertions are developer convenience logging with no operational or compliance contract. Every test has a companion test that verifies the same behavioral contract without relying on log output. All are fragile to message rewording.

**Specific tests removable:**
1. `test_metered_provider.py::test_logs_when_recording_fails` (L196-206) — 3 assertions, companion: `test_response_returned_when_recording_fails`
2. `test_metered_provider.py::test_fallback_logs_warning` (L340-349) — 1 assertion, companion: implicit no-raise
3. `test_cover_letter_validation.py::test_logs_issue_count_on_pass` (L472-476) — 2 assertions
4. `test_cover_letter_validation.py::test_logs_issue_count_on_fail` (L478-482) — 2 assertions
5. `test_metering_service.py::test_insufficient_balance_logs_warning` (L270-286) — 1 assertion, companion: `test_insufficient_balance_does_not_raise`
6. `test_metering_service.py::test_db_error_logs_and_does_not_raise` (L302-316) — 1 assertion (MIXED: implicit no-raise is behavioral)
7. `test_metering_service.py::test_unregistered_model_in_record_and_debit_logs_error` (L375-388) — 1 assertion
8. `test_modification_limits.py::test_logs_validation_result` (L433-438) — 1 assertion
9. `test_modification_limits.py::test_logs_violation_count` (L440-448) — 1 assertion

**Impact:** -7 tests, -9 fragile assertions. Note: tests #6 and #7 have implicit no-raise behavior — if removing, ensure a companion test explicitly verifies no-raise (test #5 has `test_insufficient_balance_does_not_raise` as companion; tests #6 and #7 may need a no-raise companion added).

**Action required:** LOW priority. ~7 test deletions, ~2 require companion test verification. Consider addressing when touching these files for other reasons.

### Overall Tier 2 Assessment

The backend test suite's Tier 2 patterns are **overwhelmingly legitimate**. The "behavior > implementation" philosophy is well-followed:

- **Error messages** (Category A) are mostly user-facing contracts, not internal details
- **Call counts** (Category C) test real behavioral policies (batching, retry, short-circuit)
- **Mock call_args** (Category B) are mixed — ~60% legitimate service contracts, ~30% refactor candidates
- **Logging** (Category D) is the weakest category — all removable without behavioral coverage loss

**If a future cleanup task is created**, the highest-value work is:
1. **Delete 7 caplog-only tests** (Category D) — easiest wins, ~30 min
2. **Refactor 8 sole-assertion call_args tests** (Category B) — moderate effort, higher value

**Total potential cleanup:** -7 tests (caplog) + -0 to -2 tests (redundant call_args) = **-7 to -9 tests.** The 8 refactor candidates would improve test quality without reducing count.
