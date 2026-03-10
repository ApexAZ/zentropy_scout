# Frontend Test Suite Audit & Cleanup Plan

**Created:** 2026-03-09
**Status:** Ready for implementation

---

## Context

The frontend has 3,704 tests across 205 files and 71,813 lines of test code. *(Original scan estimated 3,843; verified baseline at origin/main is 3,704.)* This audit ensures tests target user-visible behavior over implementation details, per the project's testing philosophy in CLAUDE.md and the zentropy-tdd skill.

**Four exploration agents completed initial analysis:**
1. **Structure scan** — Mapped all 205 test files across 5 directory groups: types (7 files, 189 tests), lib (~15 files, 469 tests), hooks (9 files, 106 tests), components (~120+ files, 2,856 tests), app (~25 files, 204 tests).
2. **toBeInTheDocument scan** — Found 2,605 total calls across 161 files, with ~1,096 sole-assertion instances (42.1%). 15 files have 100% sole assertions.
3. **Mock assertion scan** — Found 766 mock-call assertions across 104 files (511 `toHaveBeenCalledWith`, 181 `toHaveBeenCalled`, 74 `toHaveBeenCalledTimes`).
4. **Implementation-detail scan** — Found 120 `toHaveClass` (32 files), 23 `data-state` (5 files), 4 `toHaveStyle` (1 file). Semantic-to-testId query ratio is 1.68:1 (2,871 vs 1,708).
5. **Types deep analysis** — Classified all 189 type tests: ~85 constructor mirrors, ~36 enum echoes, ~68 validation/behavioral tests. `api.test.ts` is 100% bloat (all 9 tests).

**Priority target:** `types/*.test.ts` (7 files, 189 tests, 2,853 lines). These test TypeScript interfaces by constructing conforming objects and asserting field values. `tsc --noEmit` already enforces type conformance at compile time — constructor mirrors and enum echoes are redundant.

**Critical nuance:** Most `toBeInTheDocument()` sole assertions are **legitimate conditional render tests** (element appears when state changes). The primary work is **triage** — classifying each finding before touching any code. Only delete when a companion test covers the same element with richer assertions, or when the test is a pure render-only smoke test subsumed by other tests.

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
Phase 2: Cleanup — Priority Targets (types + 100% sole files)
    ↓
Phase 3: Cleanup — Component Tests (scope TBD from triage)
    ↓
Phase 4: Quality Gate (verification + documentation)
```

---

## Classification Rules

| Pattern | ANTIPATTERN | REDUNDANT | LEGITIMATE |
|---------|-------------|-----------|------------|
| **Constructor mirror** (`obj = {x: 1}` → `expect(obj.x).toBe(1)`) | Sole test for that type; `tsc` enforces | Companion test uses the type with richer assertions | Object is constructed via factory with transform/validation logic |
| **Enum echo** (`expect(LEVELS).toEqual([...])`) | Duplicates source literal | — | Value is computed, not a literal copy |
| **toBeInTheDocument sole** | Render-only smoke test with no state variation | Companion test asserts on same element's text/attributes/interactions | Conditional render test (element appears/disappears based on props/state) |
| **Mock-only assertion** (`expect(mock).toHaveBeenCalledWith(...)` sole) | No rendered output or return value checked | Companion test checks rendered result of the action | Tests critical wiring (wrong API endpoint URL = silent data loss) |
| **toHaveClass** (`expect(el).toHaveClass("bg-red-500")`) | Tests Tailwind implementation detail | Companion test checks aria-*/text for the same state | Tests accessibility-related class (sr-only, focus-visible) |
| **Click-then-assert-mock** (render → click → `expect(mock).toHaveBeenCalled()` sole) | No rendered state change checked | — | Test also asserts on UI state change after click |

**Decision criterion:** "Would this test still pass if I completely rewrote the component's internal structure but preserved the same rendered output and interaction behavior?"

**TypeScript criterion:** "Does `tsc --noEmit` already catch this?" If yes, the runtime test is redundant.

---

## Phase 1: Triage & Classification

**Status:** ✅ Complete

*Read-only analysis. Classify findings as LEGITIMATE, ANTIPATTERN, or REDUNDANT. Output drives Phase 2-3 scope.*

| # | Task | Scope | Status |
|---|------|-------|--------|
| 1.1 | **Triage types/*.test.ts** — Read all 7 files. Classify every test as CONSTRUCTOR_MIRROR, ENUM_ECHO, VALIDATION, or BEHAVIORAL. Record in triage table appended to this plan. | 7 files, 189 tests | ✅ |
| 1.2 | **Triage toBeInTheDocument — 100% sole files** — Read the 15 files where every `toBeInTheDocument()` is a sole assertion. For each test, check: (a) is there a companion test asserting on the same element with text/attributes/interactions? (b) is it testing conditional rendering (element appears only under certain props/state)? Classify as DELETE, REFACTOR, or KEEP. | 15 files, ~94 sole assertions | ✅ |
| 1.3 | **Triage toBeInTheDocument — heavy files** — Sample top 10 files by sole-assertion count: opportunities-table (44), resume-detail (30), message-bubble (27), application-detail (25), applications-list (22), change-flags-resolver (22), status-transition-dropdown (20), cover-letter-review (19), add-timeline-event-dialog (16), login page (15). Derive mechanical rule for remaining files. | 10 files, ~240 sole assertions | ✅ |
| 1.4 | **Triage mock-only + CSS assertions** — Sample top 10 mock-heavy files (api-client 27, sse-client 25, application-detail 24, sse-query-bridge 22, admin 22, resume-detail 17, bullet-editor 16, work-history-editor 15, certification-step 15, review-step 14). Read all 32 `toHaveClass` files + 5 `data-state` files. Classify each. | ~45 files | ✅ |
| 1.5 | **Compile triage report** — Summarize: total findings by classification, files requiring changes, estimated deletion count, cleanup task list for Phase 2-3. Refine Phase 3 tasks based on results. | Synthesis | ✅ |

**Notes:**
- Triage is read-only — no code changes
- Expected outcome: types/*.test.ts ~121 DELETE (constructor mirrors + enum echoes), ~68 KEEP. toBeInTheDocument findings TBD — most conditional render tests will be LEGITIMATE. Mock and CSS findings TBD.
- For toBeInTheDocument, the key question per test: "Does a companion test in the same file already assert on this element's text, attributes, or interactions?"

---

## Phase 2: Cleanup — Priority Targets

**Status:** ✅ Complete

*Highest-confidence deletions. Clean wins with minimal ambiguity.*

| # | Task | Scope | Status |
|---|------|-------|--------|
| 2.1 | **Delete type test bloat** — Remove CONSTRUCTOR_MIRROR and ENUM_ECHO tests from types/*.test.ts based on triage classifications. Delete entire files if 100% bloat (expected: `api.test.ts`). Keep VALIDATION and BEHAVIORAL tests. | 7 files, ~100-120 test deletions | ✅ |
| 2.2 | **Clean 100% sole-assertion files** — Delete or refactor tests in the 15 files where every `toBeInTheDocument()` is sole, applying triage dispositions. For DELETE: remove the test. For REFACTOR: add meaningful assertion (text content, attributes, interaction). | 15 files, ~50-94 tests affected | ✅ |
| 2.3 | **Phase gate — full test suite + push** — Run Vitest full suite. Compare test count to baseline (3,704). Fix regressions, commit, push. | Full frontend suite | ✅ |

**Notes:**
- Each subtask: run affected tests → full lint → commit
- 2.2 may split into 2 subtasks if triage reveals large REFACTOR scope
- Reviews: `code-reviewer` + `qa-reviewer` before commit

---

## Phase 3: Cleanup — Component Tests

**Status:** ✅ Complete

*Apply triage findings to the broader component test suite. Exact scope determined by Phase 1 triage report.*

| # | Task | Scope | Status |
|---|------|-------|--------|
| 3.1 | **Clean toBeInTheDocument sole assertions — heavy files batch A** — Top 5 files by sole count from triage (opportunities-table, resume-detail, message-bubble, application-detail, applications-list). Apply dispositions. | 5 files, 47 deletions | ✅ |
| 3.2 | **Clean toBeInTheDocument sole assertions — heavy files batch B** — Next 5 files by sole count from triage (change-flags-resolver, status-transition-dropdown, cover-letter-review, add-timeline-event-dialog, login page). Apply dispositions. | 5 files, 12 deletions | ✅ |
| 3.3 | **Clean mock-only + CSS assertion files** — Files identified in triage as having ANTIPATTERN mock-only or CSS-class-as-sole-assertion tests. | 3 files, 15 deletions + 16 assertions removed + 2 refactored | ✅ |
| 3.4 | **Clean remaining files** — Applied data-state tab assertions from resume-content-view (-2 tests, 2 refactored) and ghostwriter-review (-1 test, 1 assertion removed). Checkbox/switch data-state assertions classified LEGITIMATE. | 2 files, 3 deletions + 3 refactored | ✅ |
| 3.5 | **Phase gate — full test suite + push** — 3,437 tests pass (198 files), lint clean, typecheck clean. Pushed 4 commits (§3.1–§3.4). | Full frontend suite | ✅ |

**Notes:**
- Exact scope determined by Phase 1 triage report (task 1.5)
- Task count may increase if triage reveals more ANTIPATTERN findings
- May decrease if most findings are LEGITIMATE (likely for conditional render tests)
- 3.4 may be "zero work" — this is intentional, it's a catch-all

---

## Phase 4: Quality Gate

**Status:** ⬜ Incomplete

| # | Task | Scope | Status |
|---|------|-------|--------|
| 4.1 | **Full test suite + test count comparison** — Run full Vitest suite. Compare test count to baseline (3,704). Verify no legitimate test coverage was lost. Run `npm run lint` and `npm run typecheck`. | Full suite + lint + types | ⬜ |
| 4.2 | **Update documentation** — Update zentropy-tdd skill with frontend-specific bloat patterns learned during audit. Document which patterns were most/least impactful. | TDD skill file | ⬜ |

---

## Task Count Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 1: Triage | 5 | Classify all findings (read-only) |
| 2: Priority Cleanup | 3 | types/*.test.ts + 100% sole files |
| 3: Component Cleanup | 5 | Broader component test fixes (TBD scope) |
| 4: Quality Gate | 2 | Verify + document |
| **Total** | **15** | |

---

## Antipattern Findings Summary (from initial scan)

| Pattern | Raw Count | Files | Expected Outcome |
|---------|-----------|-------|------------------|
| Constructor mirrors (types/*.test.ts) | ~85 | 7 | ~85 DELETE |
| Enum echoes (types/*.test.ts) | ~36 | 6 | ~36 DELETE |
| toBeInTheDocument sole assertion | ~1,096 | 134 | TBD — many LEGITIMATE (conditional render) |
| Mock-call assertions (total) | 766 | 104 | TBD — many LEGITIMATE (API wiring) |
| toHaveClass assertions | 120 | 32 | TBD — mix of fragile and legitimate |
| data-state assertions | 23 | 5 | ~23 REFACTOR to aria-* |
| **Total raw findings** | **~2,126** | | |

---

## Critical Files Reference

| File | Role |
|------|------|
| `types/api.test.ts` | 9 tests, expected 100% DELETE (all constructor mirrors) |
| `types/persona.test.ts` | 31 tests, ~85% DELETE (constructor mirrors + enum echoes) |
| `types/job.test.ts` | 33 tests, ~33% DELETE (keep scoring/behavioral tests) |
| `types/application.test.ts` | 41 tests, ~60% DELETE (keep factory-based scenarios) |
| `types/resume.test.ts` | 32 tests, ~25% DELETE (keep snapshot/guardrail logic) |
| `types/sse.test.ts` | 33 tests, ~25% DELETE (keep parsing/validation guards) |
| `types/ingest.test.ts` | 10 tests, ~60% DELETE (keep optional field handling) |
| `components/ui/error-states.test.tsx` | 14 tests, 100% sole assertions |
| `components/persona/discovery-preferences-editor.test.tsx` | 14 tests, 100% sole assertions |
| `components/chat/chat-input.test.tsx` | 12 tests, 100% sole assertions |
| `components/chat/chat-confirm-card.test.tsx` | 11 tests, 100% sole assertions |
| `components/dashboard/opportunities-table.test.tsx` | 60 tests, 44 sole assertions (highest count) |
| `components/resume/resume-detail.test.tsx` | 73 tests, 30 sole assertions |
| `components/ui/status-badge.test.tsx` | 17 toHaveClass (highest CSS offender) |

### 15 Files with 100% Sole Assertions (Phase 2.2 targets)

1. `components/persona/discovery-preferences-editor.test.tsx` — 14 sole
2. `components/ui/error-states.test.tsx` — 14 sole
3. `components/chat/chat-input.test.tsx` — 12 sole
4. `components/chat/chat-confirm-card.test.tsx` — 11 sole
5. `components/persona/basic-info-editor.test.tsx` — 7 sole
6. `app/(main)/resumes/[id]/variants/[variantId]/edit/page.test.tsx` — 6 sole
7. `components/chat/chat-score-card.test.tsx` — 6 sole
8. `components/usage/usage-page.test.tsx` — 6 sole
9. `components/chat/typing-indicator.test.tsx` — 4 sole
10. `components/editor/generation-options-panel.test.tsx` — 4 sole
11. `components/form/form-select-field.test.tsx` — 4 sole
12. `components/form/form-textarea-field.test.tsx` — 4 sole
13. `components/form/submit-button.test.tsx` — 4 sole
14. `app/(public)/components/hero-section.test.tsx` — 3 sole
15. `app/(public)/components/landing-footer.test.tsx` — 2 sole

---

## Verification

After each phase gate:
1. Run `cd frontend && npm run test:run` — all tests must pass
2. Compare test count to baseline (3,704) — document delta
3. Run `npm run lint && npm run typecheck` — must pass
4. No legitimate test coverage should be lost (conditional render tests, validation tests preserved)

After full audit:
1. Final test count documented in change log
2. TDD skill updated with frontend-specific patterns

---

## Change Log

| Date | Change |
|------|--------|
| 2026-03-09 | Plan created from initial scan by 5 exploration agents |
| 2026-03-09 | §1.1 complete — types triage (see Appendix A) |
| 2026-03-09 | §1.2 complete — 100% sole files triage: 22 DELETE, 0 REFACTOR, 71 KEEP (see Appendix B) |
| 2026-03-09 | §1.3 complete — heavy files triage: ~50 DELETE across 8 files + mechanical rule (see Appendix C) |
| 2026-03-09 | §1.4 complete — mock/CSS/data-state triage: sse-query-bridge ~22 DELETE, status-badge 15 DELETE, 4 data-state DELETE (see Appendix D) |
| 2026-03-09 | §1.5 complete — Phase 1 done. Consolidated report: ~281 estimated deletions (see Appendix E). Phase 3 tasks refined. |
| 2026-03-09 | §2.1 complete — Deleted 168 type test bloat (6 files deleted, 1 trimmed). Test count: 3,704 → 3,537. |
| 2026-03-09 | §2.2 complete — Deleted 22 sole-assertion smoke tests across 9 files (1 file deleted, 8 trimmed). Fixed Appendix B triage miscount for usage-page (was 7 total, actual 6). Test count: 3,537 → 3,515. |
| 2026-03-09 | §2.3 complete — Phase 2 gate passed. 3,515 tests pass (198 files), lint clean, typecheck clean. Corrected baseline from 3,843 to 3,704 (verified at origin/main). Total Phase 2 delta: -189 tests. |
| 2026-03-09 | §3.1 complete — Deleted 47 sole-assertion smoke tests across 5 files: opportunities-table (-12), resume-detail (-8), message-bubble (-9), application-detail (-9), applications-list (-9). Also removed 5 unused constants + 1 unused helper. Test count: 3,515 → 3,468. |
| 2026-03-09 | §3.2 complete — Deleted 12 sole-assertion smoke tests across 5 files: add-timeline-event-dialog (-5), login page (-3), change-flags-resolver (-2), status-transition-dropdown (-1), cover-letter-review (-1). Also removed 1 unused constant. Test count: 3,468 → 3,455. |
| 2026-03-09 | §3.3 complete — 3 files: sse-query-bridge (-13 tests: 9 constant echoes, 2 redundant CalledTimes, 1 structural, 1 duplicate), status-badge (0 tests deleted, 16 Tailwind toHaveClass assertions removed, 3 unused constants removed), resume-detail (-2 data-state tests, 2 refactored data-state→data-editable). Test count: 3,455 → 3,440. |
| 2026-03-09 | §3.4 complete — 2 files: resume-content-view (-2 data-state tab tests, 2 refactored to data-editable), ghostwriter-review (-1 data-state tab test, 1 data-state assertion removed from tab-switch test). Remaining data-state assertions (checkbox/switch in ~4 files) classified LEGITIMATE. Test count: 3,440 → 3,437. |
| 2026-03-09 | §3.5 complete — Phase 3 gate passed. 3,437 tests (198 files), lint clean, typecheck clean. Pushed 4 commits (§3.1–§3.4). Phase 3 delta: -78 tests. |

---

## Appendix A: Triage — types/*.test.ts

### Summary

| File | Total | CONSTRUCTOR_MIRROR | ENUM_ECHO | BEHAVIORAL | DELETE | KEEP |
|------|-------|-------------------|-----------|------------|--------|------|
| api.test.ts | 9 | 9 | 0 | 0 | 9 | 0 |
| persona.test.ts | 31 | 20 | 11 | 0 | 31 | 0 |
| sse.test.ts | 33 | 12 | 0 | 21 | 12 | 21 |
| application.test.ts | 41 | 31 | 10 | 0 | 41 | 0 |
| job.test.ts | 33 | 19 | 14 | 0 | 33 | 0 |
| ingest.test.ts | 10 | 6 | 4 | 0 | 10 | 0 |
| resume.test.ts | 32 | 22 | 10 | 0 | 32 | 0 |
| **TOTAL** | **189** | **119** | **49** | **21** | **168** | **21** |

**Key finding:** Plan estimated ~121 DELETE. Actual is **168 DELETE** — higher than expected because:
- `job.test.ts` scoring tests (FitScoreResult, StretchScoreResult, etc.) use no production functions — just construct objects and read fields back
- `resume.test.ts` guardrail/snapshot tests similarly just construct objects via factories with no transform logic
- `application.test.ts` factory functions (makeApplication, etc.) only spread defaults + overrides, no validation

**Only survivor: `sse.test.ts`** — 21 tests exercise `parseSSEEvent()` and `isSSEEvent()`, which are actual runtime functions with JSON parsing, field validation, and type guard logic.

### Disposition

| File | Action |
|------|--------|
| `api.test.ts` | DELETE entire file (100% constructor mirrors) |
| `persona.test.ts` | DELETE entire file (100% constructor mirrors + enum echoes) |
| `sse.test.ts` | DELETE 12 constructor mirror tests, KEEP 21 behavioral tests (parseSSEEvent + isSSEEvent) |
| `application.test.ts` | DELETE entire file (100% constructor mirrors + enum echoes) |
| `job.test.ts` | DELETE entire file (100% constructor mirrors + enum echoes) |
| `ingest.test.ts` | DELETE entire file (100% constructor mirrors + enum echoes) |
| `resume.test.ts` | DELETE entire file (100% constructor mirrors + enum echoes) |

### Detailed Classifications

#### api.test.ts (9 tests → 9 DELETE)

| # | Test | Classification | Reason |
|---|------|---------------|--------|
| 1 | ApiResponse: wraps a single resource | CONSTRUCTOR_MIRROR | Creates typed obj, asserts same fields back |
| 2 | ApiResponse: accepts any data type | CONSTRUCTOR_MIRROR | Two typed objects, asserts .data |
| 3 | PaginationMeta: contains all pagination fields | CONSTRUCTOR_MIRROR | Creates obj with 4 fields, asserts all 4 |
| 4 | PaginationMeta: represents an empty collection | CONSTRUCTOR_MIRROR | Zero-value variant |
| 5 | ApiListResponse: wraps a collection with meta | CONSTRUCTOR_MIRROR | Asserts length + meta fields |
| 6 | ApiListResponse: represents an empty collection | CONSTRUCTOR_MIRROR | Empty array variant |
| 7 | ErrorDetail: contains code and message | CONSTRUCTOR_MIRROR | Creates obj, asserts 3 fields |
| 8 | ErrorDetail: optionally includes field-level details | CONSTRUCTOR_MIRROR | Nested array variant |
| 9 | ErrorResponse: wraps ErrorDetail in error envelope | CONSTRUCTOR_MIRROR | Nested obj, asserts 2 fields |

#### persona.test.ts (31 tests → 31 DELETE)

| # | Test | Classification | Reason |
|---|------|---------------|--------|
| 1-2 | WorkHistory: current + past job | CONSTRUCTOR_MIRROR | Field readback |
| 3-4 | Bullet: with metrics + null metrics | CONSTRUCTOR_MIRROR | Field readback |
| 5-6 | Skill: hard + soft | CONSTRUCTOR_MIRROR | Field readback |
| 7-8 | Education: with optional + null | CONSTRUCTOR_MIRROR | Field readback |
| 9-10 | Certification: with expiration + null | CONSTRUCTOR_MIRROR | Field readback |
| 11-12 | AchievementStory: linked + unlinked | CONSTRUCTOR_MIRROR | Field readback |
| 13-14 | VoiceProfile: all fields + null optional | CONSTRUCTOR_MIRROR | Field readback |
| 15-16 | CustomNonNegotiable: exclude + require | CONSTRUCTOR_MIRROR | Field readback |
| 17-18 | PersonaChangeFlag: pending + resolved | CONSTRUCTOR_MIRROR | Field readback |
| 19-20 | Persona: full + minimal | CONSTRUCTOR_MIRROR | Field readback |
| 21-31 | Enum value arrays (11 tests) | ENUM_ECHO | Duplicate source literals (WORK_MODELS, PROFICIENCIES, etc.) |

#### sse.test.ts (33 tests → 12 DELETE, 21 KEEP)

| # | Test | Classification | Action |
|---|------|---------------|--------|
| 1-12 | ChatTokenEvent, ChatDoneEvent, ToolStartEvent, ToolResultEvent, DataChangedEvent, HeartbeatEvent, SSEEvent union narrowing (12 tests) | CONSTRUCTOR_MIRROR | DELETE |
| 13-18 | parseSSEEvent: valid parsing + error cases (6 tests) | BEHAVIORAL | KEEP — exercises runtime JSON parser |
| 19-29 | isSSEEvent: type guard validation (11 tests) | BEHAVIORAL | KEEP — exercises runtime type guard |
| 30-33 | parseSSEEvent field validation (4 tests) | BEHAVIORAL | KEEP — exercises field-level validation |

#### application.test.ts (41 tests → 41 DELETE)

| # | Test | Classification | Reason |
|---|------|---------------|--------|
| 1-5 | Union type tests (ApplicationStatus, etc.) | ENUM_ECHO | Creates literal array, asserts length |
| 6-10 | Value array tests (APPLICATION_STATUSES, etc.) | ENUM_ECHO | .toEqual against source literal |
| 11-20 | Sub-entity interfaces (JobSnapshot, OfferDetails, etc.) | CONSTRUCTOR_MIRROR | Factories with no transform logic |
| 21-28 | Application main entity (8 tests) | CONSTRUCTOR_MIRROR | makeApplication spreads defaults |
| 29-33 | TimelineEvent (5 tests, incl. immutability check) | CONSTRUCTOR_MIRROR | Field readback; `"updated_at" in event` tests factory output, not production code |
| 34-41 | CoverLetter + SubmittedCoverLetterPDF (8 tests) | CONSTRUCTOR_MIRROR | Factory readback |

#### job.test.ts (33 tests → 33 DELETE)

| # | Test | Classification | Reason |
|---|------|---------------|--------|
| 1-14 | Enum value arrays (SENIORITY_LEVELS, etc.) | ENUM_ECHO | 7 .toEqual + 7 type-satisfies |
| 15-19 | FailedNonNegotiable + ExtractedSkill | CONSTRUCTOR_MIRROR | Field readback |
| 20-26 | Scoring types (FitScoreResult, StretchScoreResult, etc.) | CONSTRUCTOR_MIRROR | No production functions — objects constructed and fields read back |
| 27-28 | JobPostingResponse (minimal + full) | CONSTRUCTOR_MIRROR | Factory readback |
| 29-33 | PersonaJobResponse (5 tests) | CONSTRUCTOR_MIRROR | Factory readback, including discovery method loop |

#### ingest.test.ts (10 tests → 10 DELETE)

| # | Test | Classification | Reason |
|---|------|---------------|--------|
| 1-3 | INGEST_SOURCE_NAMES (length, contains, isArray) | ENUM_ECHO | Tests const array content |
| 4-6 | Request/Response shapes | CONSTRUCTOR_MIRROR | Field readback |
| 7 | IngestSourceName assignability | ENUM_ECHO | typeof check on array element |
| 8-10 | Type compatibility (ExtractedSkillPreview, IngestConfirmRequest, IngestPreview) | CONSTRUCTOR_MIRROR | Field readback |

#### resume.test.ts (32 tests → 32 DELETE)

| # | Test | Classification | Reason |
|---|------|---------------|--------|
| 1-5 | Union types (ResumeFileType, etc.) | ENUM_ECHO | Assigns literal to type variable |
| 6-10 | Value arrays (RESUME_FILE_TYPES, etc.) | ENUM_ECHO | .toEqual against source literal |
| 11-13 | ResumeFile (3 tests) | CONSTRUCTOR_MIRROR | Factory readback |
| 14-20 | BaseResume (7 tests) | CONSTRUCTOR_MIRROR | Factory readback, including bullet selections/order |
| 21-25 | JobVariant (5 tests) | CONSTRUCTOR_MIRROR | Factory readback, snapshots are just field assignments |
| 26-28 | SubmittedResumePDF (3 tests) | CONSTRUCTOR_MIRROR | Factory readback |
| 29-32 | GuardrailViolation + GuardrailResult (4 tests) | CONSTRUCTOR_MIRROR | Object construction, filter+count on self-constructed data |

---

## Appendix B: Triage — 100% Sole `toBeInTheDocument()` Files

### Summary

| File | Total Tests | Sole Assertions | DELETE | KEEP |
|------|-------------|----------------|--------|------|
| discovery-preferences-editor.test.tsx | 27 | 9 | 1 | 8 |
| error-states.test.tsx | 17 | 11 | 0 | 11 |
| chat-input.test.tsx | 26 | 11 | 5 | 6 |
| chat-confirm-card.test.tsx | 20 | 6 | 2 | 4 |
| basic-info-editor.test.tsx | 39 | 6 | 1 | 5 |
| page.test.tsx (VariantEditPage) | 7 | 7 | 0 | 7 |
| chat-score-card.test.tsx | 21 | 12 | 1 | 11 |
| usage-page.test.tsx | 6 | 6 | 6 | 0 |
| typing-indicator.test.tsx | 8 | 5 | 1 | 4 |
| generation-options-panel.test.tsx | 21 | 3 | 0 | 3 |
| form-select-field.test.tsx | 6 | 4 | 0 | 4 |
| form-textarea-field.test.tsx | 8 | 3 | 0 | 3 |
| submit-button.test.tsx | 8 | 3 | 0 | 3 |
| hero-section.test.tsx | 6 | 4 | 3 | 1 |
| landing-footer.test.tsx | 6 | 3 | 2 | 1 |
| **TOTAL** | **226** | **92** | **22** | **70** |

**Key finding:** Most sole `toBeInTheDocument()` assertions are LEGITIMATE conditional render tests (element appears/disappears based on props/state). Only 22 are pure smoke tests with no state variation and duplicate element coverage.

### DELETE Tests by File

**usage-page.test.tsx** (6 DELETE — 86% bloat): All components render unconditionally. Tests just verify mocked child components are present.
- renders page container with testid
- renders Usage & Billing heading
- renders BalanceCard component
- renders UsageSummary component
- renders UsageTable component
- renders TransactionTable component

**chat-input.test.tsx** (5 DELETE): Structure data-slot duplicates + disabled state negation pairs.
- renders the chat input wrapper (pure smoke)
- has data-slot on textarea (duplicate of "renders a textarea")
- has data-slot on send button (duplicate of "renders a send button")
- does not disable textarea by default (negation of positive test)
- marks wrapper with data-disabled false by default (negation of positive test)

**hero-section.test.tsx** (3 DELETE): All elements render unconditionally.
- renders h1 headline (pure smoke)
- has hero-section test id (pure smoke)
- renders hero graphic placeholder (pure smoke)

**chat-confirm-card.test.tsx** (2 DELETE):
- has data-slot attribute (duplicate of structure tests)
- does not have destructive border for non-destructive variant (negation of positive test)

**landing-footer.test.tsx** (2 DELETE):
- renders copyright text (pure smoke, unconditional)
- has landing-footer test id (pure smoke)

**discovery-preferences-editor.test.tsx** (1 DELETE):
- has correct form testid (pure smoke, form always renders)

**basic-info-editor.test.tsx** (1 DELETE):
- has correct form testid (pure smoke, form always renders)

**chat-score-card.test.tsx** (1 DELETE):
- has data-slot attribute (duplicate of structure tests)

**typing-indicator.test.tsx** (1 DELETE):
- has data-slot attribute (duplicate of structure tests)

---

## Appendix C: Triage — Heavy `toBeInTheDocument()` Files

### Summary

| File | Total Tests | Sole Assertions | DELETE | KEEP |
|------|-------------|----------------|--------|------|
| opportunities-table.test.tsx | 60 | 44 | ~18 | ~26 |
| resume-detail.test.tsx | 73 | 30 | ~8 | ~22 |
| message-bubble.test.tsx | ~27 | ~27 | ~4 | ~23 |
| application-detail.test.tsx | ~40 | ~25 | ~6 | ~19 |
| applications-list.test.tsx | ~50 | ~22 | ~5 | ~17 |
| change-flags-resolver.test.tsx | ~50 | ~22 | ~3 | ~19 |
| status-transition-dropdown.test.tsx | ~45 | ~20 | ~4 | ~16 |
| add-timeline-event-dialog.test.tsx | ~40 | ~16 | ~2 | ~14 |
| **TOTAL** | | **~206** | **~50** | **~156** |

*Note: cover-letter-review and login page not fully analyzed; expected similar ~15-20% DELETE rate.*

### Mechanical Rule (for remaining files)

```
DELETE a sole-assertion toBeInTheDocument() test if ALL of:
1. Uses ONLY .toBeInTheDocument() as its assertion (no other expect() calls)
2. Element renders UNCONDITIONALLY (same props/state → always visible)
3. A companion test in the same file already covers the element with
   richer assertions (interaction, text content, attributes)

KEEP if ANY of:
- Tests CONDITIONAL rendering (element appears/disappears based on props/state)
- Is the ONLY test verifying that element's presence
- Has multiple assertions (even if one is toBeInTheDocument)
- Tests error/empty/loading states that are unique (not repeated elsewhere)
```

### Common DELETE Patterns
- **"shows loading spinner initially"** — appears in 5+ files, pure smoke test
- **"renders [element] in toolbar"** — smoke test when companion tests verify interaction
- **data-slot attribute checks** — duplicate of structure tests
- **Negation pairs** (e.g., "does not disable by default" alongside "disables when disabled=true")

---

## Appendix D: Triage — Mock-Only + CSS + data-state Assertions

### Mock-Only Assertions

| File | Mock Assertions | Classification | Reason |
|------|----------------|---------------|--------|
| api-client.test.ts | 27 | **KEEP** | Critical API wiring (wrong method/headers = silent data loss); paired with behavioral assertions |
| sse-client.test.ts | 25 | **KEEP** | State machine transitions + reconnection logic; paired with status checks |
| sse-query-bridge.test.ts | 22 | **DELETE ~22** | Pure mock assertions on internal invalidation wiring; no side-effect checks |
| application-detail.test.tsx | 24 | **KEEP** | Paired with rendered output assertions |
| admin page.test.tsx | 22 | **KEEP** | Paired with rendered output assertions |
| Other 5 files | ~60 | **KEEP** | Expected to be paired with behavioral assertions (not fully analyzed) |

**Key finding:** Only `sse-query-bridge.test.ts` has pure mock-only tests. All other mock-heavy files pair mocks with behavioral assertions.

### CSS Assertions (toHaveClass)

| File | toHaveClass Count | DELETE | KEEP | Notes |
|------|------------------|--------|------|-------|
| status-badge.test.tsx | 17 | 15 | 2 | DELETE: Tailwind utility classes (bg-primary, bg-warning, etc.). KEEP: aria-label assertions |

**Other 31 files:** 103 remaining `toHaveClass` across 31 files. Not fully analyzed — recommend applying during Phase 3.3 only for tests where `toHaveClass` is the SOLE assertion.

### data-state Assertions

| File | Assertions | Classification | Notes |
|------|-----------|---------------|-------|
| resume-detail.test.tsx | 4 | **DELETE** | Radix UI internal; should test content visibility instead |
| certification-step.test.tsx | 0 | **GOOD** | Pre-emptively mocked Checkbox to avoid data-state |
| Other 7 files | ~19 | **TBD** | Likely similar to resume-detail |

**Recommendation:** Replace `data-state` assertions with content/visibility checks during Phase 3.3.

---

## Appendix E: Consolidated Triage Report (§1.5)

### Estimated Deletions by Category

| Category | Source | Estimated DELETE | Confidence |
|----------|--------|-----------------|------------|
| Type test bloat (constructor mirrors + enum echoes) | §1.1 | **168** | High — every test classified |
| 100% sole-assertion files | §1.2 | **22** | High — every test classified |
| Heavy toBeInTheDocument files | §1.3 | **~50** | Medium — 8 of 10 files analyzed |
| sse-query-bridge mock-only | §1.4 | **~22** | Medium — file analyzed |
| status-badge CSS utilities | §1.4 | **15** | High — file analyzed |
| data-state assertions | §1.4 | **~4** | High for resume-detail; others TBD |
| **TOTAL ESTIMATED** | | **~281** | |

### Estimated Test Count After Audit

- Baseline: 3,704 tests (corrected from initial estimate of 3,843)
- Estimated deletions: ~281
- Estimated final: ~3,423 tests (~7.6% reduction)

### Phase 2-3 Refinement

Phase 2 (types + 100% sole files) will be the largest impact: 168 + 22 = **190 deletions**.
Phase 3 (heavy files + mock + CSS) is smaller: ~91 deletions across more files, more judgment required.

### Revised Phase 3 Tasks (based on triage)

| # | Revised Task | Scope |
|---|-------------|-------|
| 3.1 | Heavy files batch A — opportunities-table (~18), resume-detail (~8), message-bubble (~4), application-detail (~6), applications-list (~5) | ~41 deletions |
| 3.2 | Heavy files batch B — change-flags-resolver (~3), status-transition-dropdown (~4), add-timeline-event-dialog (~2), cover-letter-review (TBD), login page (TBD) | ~15 deletions |
| 3.3 | sse-query-bridge mock-only + status-badge CSS + resume-detail data-state | ~41 deletions |
| 3.4 | Remaining files — apply mechanical rule | Likely minimal |
| 3.5 | Phase gate | Full suite |

### Files NOT Requiring Changes (confirmed LEGITIMATE)

- `api-client.test.ts` — all mock assertions paired with behavioral checks
- `sse-client.test.ts` — all mock assertions paired with status checks
- `page.test.tsx` (VariantEditPage) — all conditional render tests
- `form-select-field.test.tsx` — all conditional/behavioral
- `form-textarea-field.test.tsx` — all conditional/behavioral
- `submit-button.test.tsx` — all conditional/behavioral
- `generation-options-panel.test.tsx` — all conditional/behavioral
- `error-states.test.tsx` — all conditional render + accessibility tests
