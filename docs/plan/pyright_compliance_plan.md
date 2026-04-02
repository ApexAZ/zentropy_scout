# Pyright Type-Checking Compliance Plan

## Context

**Problem:** Running `npx pyright` against the backend reveals **539 errors** across ~90 files. These errors were invisible because the project's pre-commit hooks run **mypy** (with `--ignore-missing-imports`), not pyright. No `pyrightconfig.json` exists, so pyright runs with defaults — critically, it may resolve the system Python (3.10.12) instead of the venv Python (3.11.15), and it cannot find installed packages (stripe, google-genai) without `venvPath` configuration.

**User's hypothesis:** The REQ-031 services reorganization or REQ-032 JSDoc audit "triggered a cascade." Phase 1 will test this by running pyright at pre-REQ-031 commits to establish whether these errors pre-date the reorganization or were introduced by it.

**Goal:** Zero pyright errors, with pyright added to pre-commit hooks alongside mypy for ongoing protection.

**Requirement:** No dedicated REQ document exists for type checking. If the post-mortem reveals structural gaps worth documenting, we'll create one.

---

## How to Use This Plan

1. **Start at Phase 1** — the post-mortem determines true scope
2. **Each § = one commit** — sized for ~150k context window
3. **Phase gates push to remote** — subtasks commit only
4. **After each subtask** — update this plan, then AskUserQuestion

---

## Dependency Chain

```
Phase 1: Post-Mortem & Configuration
    │  Creates pyrightconfig.json. Determines how many of the 539
    │  errors resolve from config alone (estimated ~170).
    │  Must complete first — all subsequent phases need accurate counts.
    v
Phase 2: Production Code Fixes
    │  Fix real type bugs in app/ (~30-50 errors).
    │  Must precede test fixes — prod type changes affect test annotations.
    v
Phase 3: Test Code Fixes (bulk — ~270 errors)
    │  TypedDict access, argument types, call signatures in tests.
    │  4 subtasks to keep context manageable.
    v
Phase 4: Stragglers, CI Integration & Documentation
       Zero-error verification. Add pyright to pre-commit.
       Update CLAUDE.md.
```

---

## Phase 1: Post-Mortem Analysis & Pyright Configuration

**Status:** ✅ Complete

*Determine when pyright errors first appeared, create configuration, and establish the true fix scope.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read pyright docs for pyrightconfig.json options |
| 🔍 **Investigate** | Git checkout pre-REQ-031 commit, run pyright, compare |
| ⚙️ **Configure** | Create `backend/pyrightconfig.json` |
| ✅ **Verify** | Run pyright before/after config, capture deltas |
| 📝 **Commit** | `chore(types): add pyrightconfig.json and post-mortem` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Post-mortem analysis** — (a) Identify the commit just before REQ-031 started (pre `d0751e5`, ~March 29). (b) Run `npx pyright` at that commit in a worktree to establish baseline error count. (c) Compare with current 539 errors — categorize which errors are new vs pre-existing. (d) Check if any REQ-031 import path changes introduced errors (moved modules breaking pyright resolution). (e) Document findings: was the "cascade" real, or were errors always there but invisible because mypy was the configured checker? (f) Write findings to `docs/plan/pyright_postmortem.md`. | `plan, lint, commands` | ✅ |
| 2 | **Create pyrightconfig.json & measure config wins** — (a) Create `backend/pyrightconfig.json` with: `pythonVersion: "3.11"`, `venvPath: "."`, `venv: ".venv"`, `include: ["app", "tests"]`, `typeCheckingMode: "basic"`. (b) Run pyright, capture new error count. (c) Document which categories resolved (expected: ~96 UTC imports via pythonVersion, ~57 missing imports via venvPath, ~16 missing module source, ~1 asyncio.timeout = ~170 config wins). (d) Update postmortem with actual vs expected. (e) Commit config + postmortem. **Actual: 539 → 385 (-154 resolved, +42 newly surfaced). reportIncompatibleMethodOverride fully resolved by config.** | `plan, lint, commands` | ✅ |
| 3 | **Phase gate — push** — Run full test suite (pytest + vitest + lint). Fix regressions. Push. | `plan, commands` | ✅ |

#### Notes
- **Key investigation question:** Did `from datetime import UTC` always fail with pyright, or only after some change? Python 3.11 added `datetime.UTC` — pyright's typeshed should know about it if pythonVersion is set correctly.
- **stripe has `py.typed`** — confirmed at `backend/.venv/lib/python3.11/site-packages/stripe/py.typed`. With venvPath, import errors should resolve.
- **Estimated error reduction from config: ~170 errors → ~370 remaining** — but Phase 1 will give us actuals.

---

## Phase 2: Production Code Type Fixes

**Status:** ⬜ Incomplete

*Fix all pyright errors in `backend/app/` (production code). Higher priority than tests because type errors here can mask runtime bugs.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Run `pyright` filtered to `app/` to get precise error list |
| 🧪 **TDD** | Write tests first where behavior changes (e.g., parameter renames) |
| ✅ **Verify** | `pyright` on `app/`, `pytest -v`, `ruff check .` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 4 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). | `plan, security` | ⬜ |
| 5 | **~~Fix reportIncompatibleMethodOverride in providers~~** — Resolved by pyrightconfig.json (pythonVersion + venvPath). All 10 errors in this category disappeared with proper type resolution. No code changes needed. | `plan, tdd, provider` | ✅ (config) |
| 6 | **Fix remaining production code errors** — (a) `reportOptionalMemberAccess`: add None-guards before accessing attributes on optional values in services/api code. (b) `reportCallIssue`: fix function call signatures with wrong/missing params. (c) `reportArgumentType`: fix type mismatches in production code. (d) Any `reportAttributeAccessIssue` remaining after config. Files: `app/services/`, `app/api/v1/`, `app/schemas/`, `app/providers/`. ~20-40 errors. | `plan, tdd, api` | ⬜ |
| 7 | **Phase gate — pyright zero on `app/`, full test suite, push** | `plan, commands` | ⬜ |

#### Notes
- **§5 resolved by config** — `reportIncompatibleMethodOverride` (10 errors) fully resolved by pyrightconfig.json. No code changes needed.
- **Production code has 14 errors** after config — in `openai_adapter.py` (7), `pdf_generation.py` (3), `chat.py` (2), `cover_letter_pdf_generation.py` (1), `job_scoring_service.py` (1).

---

## Phase 3: Test Code Type Fixes

**Status:** ⬜ Incomplete

*Fix the bulk of errors (~270) in `backend/tests/`. These are primarily TypedDict access violations and untyped dict literals passed to typed functions.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Run `pyright` filtered to `tests/` to get precise list per subtask |
| 🧪 **Fix** | Add type annotations to test variables; use `.get()` where needed |
| ✅ **Verify** | `pyright` on modified files, `pytest -v` on affected tests |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 8 | **Security triage gate** — Spawn `security-triage` subagent. | `plan, security` | ⬜ |
| 9 | **Fix scoring test files (TypedDict + ArgumentType)** — Add type annotations to variables holding `ScoreResult` dicts. Add typed annotations to dict literals passed to scoring functions (`calculate_hard_skills_score`, etc.). Files: `test_scoring_flow.py` (18), `test_batch_scoring.py` (22), `test_hard_skills_match.py` (24), `test_job_scoring_service.py` (20), `test_score_correlation.py` (19), `test_score_scenarios.py` (9), `test_golden_set.py` (13). ~125 errors. | `plan, tdd` | ⬜ |
| 10 | **Fix extraction & chat test files** — Add type annotations for `ExtractedJobData` access in `test_job_extraction.py` (40 errors). Add `ChatAgentState` annotations in `test_chat_agent.py` (27 errors). Fix `ClassifiedIntent` access patterns. ~67 errors. | `plan, tdd` | ⬜ |
| 11 | **Fix embedding, persona, and remaining test files** — Fix errors in: `test_job_embedding_generation.py` (17), `test_persona_embedding_generation.py` (14), `test_persona_sync.py` (19), `test_credit_schemas.py` (14), `test_base_resume_selection.py` (9), `test_claude_adapter.py` (10), `test_openai_adapter.py` (9), plus any stragglers. ~90 errors. | `plan, tdd` | ⬜ |
| 12 | **Phase gate — pyright zero on `tests/`, full test suite, push** | `plan, commands` | ⬜ |

#### Notes
- **Fix strategy for TypedDict access (115 errors):** `ScoreResult(TypedDict, total=False)` makes all fields optional. Tests create dicts with all fields present, so pyright's complaint is technically correct but practically false. Fix by annotating test variables with explicit types or using `cast()`. Do NOT change `total=False` — it's intentional per the domain contract (partial results are valid).
- **Fix strategy for argument types (158 errors):** Tests pass plain `dict` or `list[dict]` where functions expect `PersonaSkillInput`, `JobSkillInput`, etc. Fix by annotating dict literals with the expected TypedDict type.
- **Sizing:** These are the highest-volume tasks. Each subtask touches 5-8 test files with mechanical, repetitive changes. Fits within context if focused on annotation-only changes.

---

## Phase 4: Verification, CI Integration & Documentation

**Status:** ⬜ Incomplete

*Zero-error verification, add pyright to pre-commit, update project docs.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Run `pyright` with no filters — should be zero |
| ⚙️ **CI** | Add pyright hook to `.pre-commit-config.yaml` |
| ✅ **Verify** | `pre-commit run --all-files` passes |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 13 | **Zero-error verification & straggler fixes** — (a) Run `pyright` with no filters — must show 0 errors. (b) Fix any stragglers found. (c) Run full pytest + vitest suite. (d) Update `docs/plan/pyright_postmortem.md` with final resolution summary. | `plan, lint, commands` | ⬜ |
| 14 | **Add pyright to pre-commit hooks** — (a) Add `pyright` to dev dependencies in `backend/pyproject.toml`. (b) Add local hook to `.pre-commit-config.yaml`: runs `cd backend && .venv/bin/python -m pyright app/` at commit stage (scoped to `app/` for speed; full `app/ + tests/` at push stage). (c) Run `pre-commit run --all-files` to verify both mypy and pyright pass. (d) Keep mypy alongside pyright — complementary coverage (mypy has SQLAlchemy/Pydantic plugin support). | `plan, lint, commands` | ⬜ |
| 15 | **Update documentation** — (a) Add pyright to "Security Tooling Stack" table in CLAUDE.md (or create "Type Checking" row). (b) Update CLAUDE.md "Current Status" section. (c) Archive this plan to `docs/plan/Archive/`. (d) Archive REQ-032 plan if not already archived. | `plan, docs` | ⬜ |
| 16 | **Phase gate — full quality gate + push** | `plan, commands` | ⬜ |

---

## Task Count Summary

| Phase | Tasks | Errors Addressed |
|-------|-------|-----------------|
| 1: Post-Mortem & Config | 3 (§1-§3) | 154 resolved by config (539 → 385) |
| 2: Production Code | 4 (§4-§7) | 14 errors (§5 resolved by config) |
| 3: Test Code | 5 (§8-§12) | ~371 errors |
| 4: CI & Docs | 4 (§13-§16) | Stragglers + prevention |
| **Total** | **16 tasks** | **539 errors → 0** |

---

## Critical Files Reference

| File | Role in Plan |
|------|-------------|
| `backend/pyrightconfig.json` | NEW — core pyright configuration |
| `backend/pyproject.toml` | Add pyright dev dependency |
| `.pre-commit-config.yaml` | Add pyright hook |
| `backend/app/providers/metered_provider.py` | `_model_override` → `model_override` rename |
| `backend/app/providers/llm/base.py` | Base class — reference for override signatures |
| `backend/app/services/scoring/score_types.py` | `ScoreResult(TypedDict, total=False)` — root of 115 errors |
| `docs/plan/pyright_postmortem.md` | NEW — post-mortem findings |
| 89 files with `from datetime import UTC` | May resolve from config; if not, bulk import fix |

---

## Decision Record

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pyright mode | `basic` | Catches real errors without strict-mode noise. Can upgrade to `standard` later. |
| Mypy fate | Keep alongside pyright | Complementary: mypy has SQLAlchemy/Pydantic plugins; pyright catches TypedDict/argument errors mypy misses. ~5s added to pre-commit. |
| Missing stubs | Resolve via `venvPath` config | `stripe` and `google-genai` both ship `py.typed`. Just point pyright at the venv. |
| Test fix strategy | Type-annotate variables | Adding `result: ScoreResult = ...` is non-invasive, preserves test readability. |
| Pre-commit scope | `app/` on commit, `app/ + tests/` on push | Keeps commit fast (~10s) while ensuring full coverage at push gates. |
| `ScoreResult total=False` | Keep as-is | Intentional domain design — partial results are valid. Fix test code, not the TypedDict. |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-04-01 | Plan created — 4 phases, 16 tasks |
| 2026-04-01 | §1 complete — post-mortem disproved cascade hypothesis (errors pre-date REQ-031/032) |
| 2026-04-01 | §2 complete — pyrightconfig.json reduces 539 → 385. §5 resolved by config (method overrides). |
