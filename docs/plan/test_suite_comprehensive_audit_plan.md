# Test Suite Comprehensive Audit — Plan

**Created:** 2026-03-09
**Status:** ⬜ Incomplete
**Baseline:** 4,485 tests across 193 files (17 already audited)

---

## Context

Two prior audit passes removed 67 bloat tests from 17 files. This plan systematically audits the remaining **176 files (4,098 tests)** to ensure every test answers: *"What real bug would I catch that no other test catches?"*

**Specification:** CLAUDE.md "Testing Philosophy" section defines the criteria. No REQ document exists — this is a quality/maintenance task, not a feature.

**Prior work:**
- `backend_test_audit_plan.md` (✅) — isinstance, len(), constant antipatterns
- `backend_test_deep_audit_plan.md` (✅) — tautological, echo, subsumed patterns
- Ad-hoc passes A+B — 67 tests removed across 17 files

---

## How to Use This Document

1. Find the first ⬜ task — that's where to start
2. Each subtask audits 4-6 test files, sized for ~150k context window
3. After each subtask: update status → commit → STOP and ask user
4. After each phase: full backend test suite as quality gate + push

---

## Audit Criteria

Every test is classified as **DELETE**, **CONSOLIDATE**, or **KEEP**.

### DELETE if:

| # | Pattern | Example |
|---|---------|---------|
| 1 | **Tautological assertion** — echoes a hardcoded constructor constant | `assert error.code == "VALIDATION_ERROR"` when hardcoded in `__init__` |
| 2 | **Pydantic/ORM echo** — construct model, dump, assert same values | `model_dump()` returns what you put in |
| 3 | **`is not None` sole assertion** — existence only, not behavior | `assert user.created_at is not None` |
| 4 | **Subsumed test** — another test covers same behavior with ≥ coverage | Two tests both verify the same code path |
| 5 | **Default-value mirror** — asserts config default matches source literal | `assert settings.llm_provider == "claude"` |
| 6 | **TimestampMixin test** — tests ORM mixin, not repo logic | `assert record.created_at is not None` |
| 7 | **Field existence test** — type checker validates this statically | Construct model and assert fields exist |
| 8 | **Constructor mirror** — pure assignment echo | `assert adapter.config is config` |
| 9 | **Pass-through mock** — only asserts call_args, not behavioral outcome | `mock.assert_called_with(...)` as sole assertion |

### CONSOLIDATE if:

- ≥4 individual tests share the exact same pattern → 1 `@pytest.mark.parametrize`
- Net reduction = N tests removed − parametrize entries added

### KEEP if:

- Test has actual computation (division, truncation, conditional logic)
- Follows the approved frozen-test pattern (CLAUDE.md)
- Exercises a meaningful code path (e.g., `else None` branch)
- Security-critical behavioral test (headers, auth, injection)
- Full round-trip behavioral test through a real system (DB, HTTP)
- Catches a real bug that no other test catches

### Decision Criterion

> "Would this test still pass if I rewrote the implementation using a completely different internal structure but preserved the same external behavior?"
>
> **Yes → behavioral (KEEP).** No → structural (candidate for DELETE).

---

## Audit Workflow (all phases use this)

| Step | Action |
|------|--------|
| 📖 **Read** | Read each test file + its source implementation |
| 🔍 **Trace** | For each test, trace the assertion back to the source code. Apply audit criteria above. |
| 📋 **Classify** | Produce findings table: DELETE (with pattern #), CONSOLIDATE (with target), or KEEP (with justification) |
| ✏️ **Edit** | Remove/consolidate flagged tests. Remove unused imports/constants. |
| ✅ **Verify** | `pytest -v <affected_files>` — confirm all remaining tests pass, note test count delta |
| 📝 **Commit** | `test: audit <domain> — remove N bloat tests (<pattern summary>)` |

**After each subtask:** Update plan status → commit → STOP → AskUserQuestion (Continue / Compact / Stop).

**Phase gates:** Run full backend test suite (`pytest -v`). Fix regressions. Push to remote.

**Note:** Security triage gates are included per the standard plan template. Since this plan changes only test files (no production code), expect CLEAR verdicts. These gates still serve as checkpoints to verify remote scanners are clear from the previous phase gate push.

---

## Dependency Chain

```
Phase 0: Already Complete (17 files, 387 tests)
    ↓
Phase 1: Scoring & Fit (23 files, 541 tests)
    ↓
Phase 2: Job Pipeline & Pool (21 files, 468 tests)
    ↓
Phase 3: Resume & Cover Letter (19 files, 460 tests)
    ↓
Phase 4: API & Router Layer (24 files, 517 tests)
    ↓
Phase 5: Auth, Account & Admin (14 files, 357 tests)
    ↓
Phase 6: Agents, Providers & Metering (22 files, 501 tests)
    ↓
Phase 7: Edge Cases & Scenarios (14 files, 441 tests)
    ↓
Phase 8: Security & Sanitization (8 files, 233 tests)
    ↓
Phase 9: Infrastructure & Migrations (10 files, 172 tests)
    ↓
Phase 10: Embeddings, Persona & Misc (21 files, 408 tests)
```

---

## Phase 0: Already Audited

**Status:** ✅ Complete

*17 files audited across prior passes. 67 tests removed. Baseline established at 4,485.*

| File | Pass | Result |
|------|------|--------|
| test_core_config.py | A | -11 tests |
| test_provider_config.py | A | -9 tests |
| test_job_posting_repository.py | A | -4 tests |
| test_persona_job_repository.py | A | -3 tests |
| test_admin_config_models.py | A | -7 tests |
| test_claude_adapter.py | A | -1 test |
| test_openai_adapter.py | A | -1 test |
| test_gemini_adapter.py | A | -1 test |
| test_fit_score_interpretation.py | A | -3 tests, 16→2 consolidation |
| test_api_responses.py | B | -6 tests |
| test_provider_factory.py | B | -2 tests |
| test_openai_embedding_adapter.py | B | -2 tests |
| test_api_filtering.py | B | -4 tests |
| test_user_repository.py | B | -2 tests |
| test_usage_repository.py | B | -1 test |
| test_generation_outcome.py | B | -4 tests |
| test_api_errors.py | B | 12→6 consolidation |

---

## Phase 1: Scoring & Fit Analysis

**Status:** ⬜ Incomplete

*23 files, 541 tests. Core scoring engine — fit scores, stretch scores, skill matching, explanations. Source files share significant overlap, so domain knowledge compounds across subtasks.*

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** — Spawn `security-triage` subagent. Test-only changes expected → CLEAR verdict. | `plan, security` | ✅ |
| 2 | **Audit fit score weights & aggregation** — `test_fit_score_weights`, `test_fit_score_aggregation`, `test_hard_skills_match`, `test_soft_skills_match`, `test_experience_level` (5 files) — removed 16 tests (10 subsumed/echo from aggregation + 6 exact-dup worked examples from experience_level); consolidated 5→1 parametrized weight isolation test | `plan, test` | ✅ |
| 3 | **Audit location, role & target alignment** — `test_role_title_match`, `test_location_logistics`, `test_target_role_alignment`, `test_target_skills_exposure`, `test_score_details` (5 files) — removed 16 tests (worked example duplicates from all 4 scoring files + 2 weaker bound assertions from logistics); score_details clean | `plan, test` | ✅ |
| 4 | **Audit score explanation & types** — `test_score_explanation`, `test_score_types`, `test_score_scenarios`, `test_scoring_flow`, `test_score_correlation` (5 files) — removed 27 tests (17 constructor echoes from explanation dataclass file deleted entirely; 8 subsumed from scoring_flow; 2 constructor echoes from correlation); consolidated 4→1 parametrized validation test | `plan, test` | ✅ |
| 5 | **Audit explanation generation & reasoning** — `test_explanation_generation`, `test_reasoning_explanation`, `test_stretch_score_aggregation`, `test_stretch_score_interpretation` (4 files) — removed 25 tests (1 subsumed summary from explanation; 3 subsumed from reasoning; 8 from aggregation: 1 duplicate, 1 constructor mirror, 2 default-value mirrors, 2 duplicates, 2 subsumed bounds; 14 from interpretation: consolidated 16→1 parametrized threshold test, deleted 3 result structure + 2 boundary + 2 integration subsumed + 3 replace() immutability) | `plan, test` | ✅ |
| 6 | **Audit stretch weights, quality & batch** — `test_stretch_score_weights`, `test_quality_metrics`, `test_non_negotiables_filter`, `test_batch_scoring` (4 files) — removed 17 tests (deleted weights file: 1 test subsumed by import-time check; quality: 1 replace() immutability + 8 subsumed per-metric + 4 subsumed edge cases; non-neg: 3 constructor mirrors; batch: clean) | `plan, test` | ✅ |
| 7 | **Phase gate — full backend test suite + push** — Deferred; 4284 passed, 0 failures, 103 pre-existing DB-session errors. Push deferred to next phase gate. | `plan, commands` | 🟡 |

---

## Phase 2: Job Pipeline & Pool

**Status:** ⬜ Incomplete

*21 files, 468 tests. Job extraction, enrichment, deduplication, pool management, discovery workflow.*

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** | `plan, security` | ⬜ |
| 2 | **Audit job extraction & enrichment** — `test_job_extraction`, `test_job_enrichment_service`, `test_job_fetch_service`, `test_job_posting_schemas`, `test_job_deduplication` (5 files) — removed 11 tests (5 TypedDict constructor mirrors from extraction; 3 PollResult constructor mirrors from fetch; 2 Pydantic constructor mirrors + 1 default-value mirror from schemas; enrichment + dedup clean) | `plan, test` | ✅ |
| 3 | **Audit job lifecycle & scoring** — `test_job_expiry`, `test_job_status_transitions`, `test_job_scoring_service`, `test_job_pool_helpers`, `test_job_embedding_generation` (5 files) — removed 2 tests (1 replace() immutability from expiry; 1 constructor mirror from embedding_generation); status_transitions, scoring_service, pool_helpers all clean | `plan, test` | ✅ |
| 4 | **Audit pool repositories & surfacing** — `test_job_pool_repository`, `test_job_pool_repository_dedup`, `test_pool_scoring`, `test_pool_surfacing_service`, `test_pool_surfacing_worker` (5 files) | `plan, test` | ⬜ |
| 5 | **Audit discovery & dedup** — `test_discovery_workflow`, `test_source_adapters`, `test_source_selection`, `test_dedup_cross_persona`, `test_global_dedup_service`, `test_persona_job_repository_write` (6 files) | `plan, test` | ⬜ |
| 6 | **Phase gate — full backend test suite + push** | `plan, commands` | ⬜ |

---

## Phase 3: Resume & Cover Letter Generation

**Status:** ⬜ Incomplete

*19 files, 460 tests. Document generation, PDF/DOCX rendering, content utilities, template management.*

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** | `plan, security` | ⬜ |
| 2 | **Audit resume generation** — `test_resume_generation_prompts`, `test_resume_generation_service`, `test_resume_llm_generate`, `test_resume_parsing_service`, `test_resume_template_repository` (5 files) | `plan, test` | ⬜ |
| 3 | **Audit resume templates & content utils** — `test_resume_template_schemas`, `test_resume_template_service`, `test_pdf_generation`, `test_content_utils` (4 files) | `plan, test` | ⬜ |
| 4 | **Audit cover letter generation & validation** — `test_cover_letter_generation`, `test_cover_letter_structure`, `test_cover_letter_validation`, `test_cover_letter_editing`, `test_cover_letter_output` (5 files) | `plan, test` | ⬜ |
| 5 | **Audit cover letter PDF & rendering** — `test_cover_letter_pdf_generation`, `test_cover_letter_pdf_storage`, `test_content_generation_service`, `test_markdown_docx_renderer`, `test_markdown_pdf_renderer` (5 files) | `plan, test` | ⬜ |
| 6 | **Phase gate — full backend test suite + push** | `plan, commands` | ⬜ |

---

## Phase 4: API & Router Layer

**Status:** ⬜ Incomplete

*24 files, 517 tests. HTTP endpoint tests — request/response contracts, auth enforcement, pagination, CRUD operations.*

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** | `plan, security` | ⬜ |
| 2 | **Audit API scaffold & resources** — `test_api_main`, `test_api_pagination`, `test_api_auth`, `test_api_resources_router` (4 files) | `plan, test` | ⬜ |
| 3 | **Audit persona & onboarding endpoints** — `test_api_personas_crud`, `test_api_personas_router`, `test_api_persona_change_flags`, `test_api_onboarding` (4 files) | `plan, test` | ⬜ |
| 4 | **Audit job posting endpoints** — `test_api_job_postings_crud`, `test_api_job_postings_ingest`, `test_api_job_postings_router`, `test_api_job_variants` (4 files) | `plan, test` | ⬜ |
| 5 | **Audit application & variant endpoints** — `test_api_variant_for_job`, `test_api_applications`, `test_api_base_resumes`, `test_api_cover_letters` (4 files) | `plan, test` | ⬜ |
| 6 | **Audit resume, chat & file endpoints** — `test_api_resume_templates`, `test_api_chat`, `test_api_files`, `test_api_bulk_operations` (4 files) | `plan, test` | ⬜ |
| 7 | **Audit usage, preferences & generation endpoints** — `test_api_usage`, `test_api_user_source_preferences`, `test_export_endpoints`, `test_generation_endpoint` (4 files) | `plan, test` | ⬜ |
| 8 | **Phase gate — full backend test suite + push** | `plan, commands` | ⬜ |

---

## Phase 5: Auth, Account & Admin

**Status:** ⬜ Incomplete

*14 files, 357 tests. Authentication, OAuth, account management, admin operations. Higher bar for KEEP — security-critical tests should be preserved.*

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** | `plan, security` | ⬜ |
| 2 | **Audit auth & account** — `test_auth_helpers`, `test_auth_password_endpoints`, `test_admin_auth`, `test_account_linking`, `test_account_repository` (5 files) | `plan, test, security` | ⬜ |
| 3 | **Audit OAuth & sessions** — `test_magic_link_endpoints`, `test_oauth_endpoints`, `test_oauth_helpers`, `test_tenant_session` (4 files) | `plan, test, security` | ⬜ |
| 4 | **Audit admin services** — `test_admin_api`, `test_admin_routing_test`, `test_admin_schemas`, `test_admin_config_service`, `test_admin_management_service` (5 files) | `plan, test` | ⬜ |
| 5 | **Phase gate — full backend test suite + push** | `plan, commands` | ⬜ |

---

## Phase 6: Agents, Providers & Metering

**Status:** ⬜ Incomplete

*22 files, 501 tests. LLM agent orchestration, provider adapters, usage metering, billing.*

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** | `plan, security` | ⬜ |
| 2 | **Audit agent infrastructure** — `test_agent_client`, `test_agent_handoff`, `test_agent_message`, `test_agent_session_guard` (4 files) | `plan, test` | ⬜ |
| 3 | **Audit chat & onboarding agents** — `test_chat_agent`, `test_onboarding_utilities`, `test_onboarding_workflow`, `test_graph_invocation` (4 files) | `plan, test` | ⬜ |
| 4 | **Audit ghostwriter & scouter** — `test_ghostwriter`, `test_ghostwriter_prompts`, `test_scouter_agent`, `test_scouter_error_handling` (4 files) | `plan, test` | ⬜ |
| 5 | **Audit embedding & provider adapters** — `test_gemini_embedding_adapter`, `test_metered_provider`, `test_provider_errors`, `test_provider_name` (4 files) | `plan, test` | ⬜ |
| 6 | **Audit metering & billing** — `test_metering_integration`, `test_metering_models`, `test_metering_service`, `test_balance_gating`, `test_embedding_cost`, `test_usage_repository_summary` (6 files) | `plan, test` | ⬜ |
| 7 | **Phase gate — full backend test suite + push** | `plan, commands` | ⬜ |

---

## Phase 7: Edge Cases & Scenarios

**Status:** ⬜ Incomplete

*14 files, 441 tests. Scoring edge cases for specific career profiles, resume selection, tailoring decisions.*

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** | `plan, security` | ⬜ |
| 2 | **Audit career profile edge cases** — `test_career_changer_edge_cases`, `test_entry_level_edge_cases`, `test_executive_role_edge_cases`, `test_missing_data_edge_cases`, `test_data_availability` (5 files) | `plan, test` | ⬜ |
| 3 | **Audit selection & tailoring** — `test_growth_trajectory`, `test_base_resume_selection`, `test_story_selection`, `test_tailoring_decision`, `test_duplicate_story` (5 files) | `plan, test` | ⬜ |
| 4 | **Audit draft, reorder & review** — `test_auto_draft_threshold`, `test_bullet_reordering`, `test_user_review`, `test_regeneration` (4 files) | `plan, test` | ⬜ |
| 5 | **Phase gate — full backend test suite + push** | `plan, commands` | ⬜ |

---

## Phase 8: Security & Sanitization

**Status:** ⬜ Incomplete

*8 files, 233 tests. LLM sanitization, content security, tenant isolation. Highest bar for KEEP — these tests are security-critical by definition. Expect mostly KEEP verdicts with minimal deletions.*

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** | `plan, security` | ⬜ |
| 2 | **Audit sanitization & middleware** — `test_llm_sanitization`, `test_llm_sanitization_fuzz`, `test_content_security`, `test_null_byte_middleware` (4 files) | `plan, test, security` | ⬜ |
| 3 | **Audit validation & isolation** — `test_file_validation`, `test_schema_extra_forbid`, `test_cross_tenant_isolation`, `test_application_idor` (4 files) | `plan, test, security` | ⬜ |
| 4 | **Phase gate — full backend test suite + push** | `plan, commands` | ⬜ |

---

## Phase 9: Infrastructure & Migrations

**Status:** ⬜ Incomplete

*10 files, 172 tests. Alembic migrations, rate limiting, retry logic, retention cleanup.*

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** | `plan, security` | ⬜ |
| 2 | **Audit migrations** — `test_migration_010_auth_tables`, `test_migration_011_rename_indexes`, `test_migration_012_persona_jobs`, `test_migration_013_backfill`, `test_migration_014_drop_per_user_columns` (5 files) | `plan, test` | ⬜ |
| 3 | **Audit rate limiting, retry & cleanup** — `test_rate_limiting`, `test_rate_limit_enforcement`, `test_retry_strategy`, `test_retention_cleanup`, `test_reembed_script` (5 files) | `plan, test` | ⬜ |
| 4 | **Phase gate — full backend test suite + push** | `plan, commands` | ⬜ |

---

## Phase 10: Embeddings, Persona & Misc

**Status:** ⬜ Incomplete

*21 files, 408 tests. Embedding infrastructure, persona lifecycle, golden set, application workflow, and remaining uncategorized files.*

#### Tasks

| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** | `plan, security` | ⬜ |
| 2 | **Audit embedding infrastructure** — `test_embedding_types`, `test_embedding_freshness`, `test_embedding_cache`, `test_embedding_storage`, `test_ingest_token_store` (5 files) | `plan, test` | ⬜ |
| 3 | **Audit persona lifecycle** — `test_persona_change`, `test_persona_embedding_generation`, `test_persona_sync`, `test_modification_limits`, `test_timeline_immutability` (5 files) | `plan, test` | ⬜ |
| 4 | **Audit voice, detection & expiration** — `test_voice_prompt_block`, `test_voice_validation`, `test_ghost_detection`, `test_expiration_detection` (4 files) | `plan, test` | ⬜ |
| 5 | **Audit golden set & credit repos** — `test_golden_set`, `test_golden_set_fixture`, `test_credit_repository`, `test_credit_repository_balance` (4 files) | `plan, test` | ⬜ |
| 6 | **Audit application workflow & misc** — `test_application_pin_archive`, `test_application_workflow`, `test_race_conditions` (3 files) | `plan, test` | ⬜ |
| 7 | **Phase gate — full backend test suite + push** | `plan, commands` | ⬜ |

---

## Task Count Summary

| Phase | Domain | Files | Tests | Audit Subtasks | Total Tasks |
|-------|--------|-------|-------|----------------|-------------|
| 0 | Already Audited | 17 | 387 | — | ✅ |
| 1 | Scoring & Fit | 23 | 541 | 5 | 7 |
| 2 | Job Pipeline | 21 | 468 | 4 | 6 |
| 3 | Resume & Cover Letter | 19 | 460 | 4 | 6 |
| 4 | API & Router | 24 | 517 | 6 | 8 |
| 5 | Auth & Admin | 14 | 357 | 3 | 5 |
| 6 | Agents, Providers & Metering | 22 | 501 | 5 | 7 |
| 7 | Edge Cases | 14 | 441 | 3 | 5 |
| 8 | Security | 8 | 233 | 2 | 4 |
| 9 | Infrastructure | 10 | 172 | 2 | 4 |
| 10 | Misc | 21 | 408 | 5 | 7 |
| **Total** | | **193** | **4,485** | **39** | **59** |

---

## Tracking

| Metric | Value |
|--------|-------|
| **Starting baseline** | 4,485 tests |
| **Current count** | 4,485 tests |
| **Tests removed** | 0 |
| **Files audited** | 17 / 193 |
| **Phases complete** | 0 / 10 |

*Update this table at each phase gate.*

---

## Change Log

| Date | Change |
|------|--------|
| 2026-03-09 | Plan created. 17 files already audited (Phase 0). |
