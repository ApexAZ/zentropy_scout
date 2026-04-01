# Pyright Post-Mortem Analysis

**Date:** 2026-04-01
**Investigator:** Claude Code (post-mortem analysis for pyright compliance plan)

---

## Executive Summary

The 539 pyright errors visible on `HEAD` were **NOT introduced by REQ-031 (services reorganization) or REQ-032 (JSDoc audit)**. They accumulated gradually across the project's development history, invisible because the project's pre-commit hooks run **mypy** (not pyright) with `--ignore-missing-imports`.

REQ-031 and REQ-032 added **zero** new pyright errors. They only moved files (preserving import structures) and added docstrings (no type-affecting changes).

---

## Investigation Method

Ran `npx pyright` (v1.1.408) at three historical commits to establish a timeline:

| Commit | Date | Era | Errors |
|--------|------|-----|--------|
| `cb1928b` | ~March 2026 | Pre-billing (before Stripe/REQ-029) | **498** |
| `705c689` | March 29, 2026 | Pre-refactor (before REQ-031) | **539** |
| `HEAD` | April 1, 2026 | Current (after REQ-031 + REQ-032) | **539** |

---

## Error Delta Analysis

### cb1928b → 705c689: +41 errors (Stripe/billing work, REQ-029)

| Category | Pre-billing | Pre-refactor | Delta | Likely Source |
|----------|------------|--------------|-------|---------------|
| reportArgumentType | 140 | 158 | +18 | New Stripe test files with untyped mocks |
| reportAttributeAccessIssue | 125 | 140 | +15 | `from datetime import UTC` in new billing files |
| reportMissingImports | 49 | 57 | +8 | `import stripe` in new Stripe service files |
| reportCallIssue | 27 | 23 | -4 | Some calls fixed during Stripe implementation |
| reportOptionalMemberAccess | 18 | 19 | +1 | New optional access in Stripe repo tests |
| Others | 139 | 142 | +3 | Minor additions |

### 705c689 → HEAD: +0 errors (REQ-031 + REQ-032)

**Zero change.** Every error category has identical counts before and after the services reorganization and JSDoc audit. This confirms:

1. **REQ-031** moved ~80 service files between directories but preserved all import paths (using `app.services.<subdirectory>.<module>` pattern). Pyright tracked the moves correctly.
2. **REQ-032** only added/modified docstrings and JSDoc headers. No type-affecting code changes were made.

---

## Root Cause: Why Were These Errors Invisible?

### 1. Mypy is the configured type checker, not pyright

The project's `.pre-commit-config.yaml` runs:
```yaml
- id: backend-mypy
  entry: bash -c 'cd backend && .venv/bin/python -m mypy app/ --ignore-missing-imports'
```

Key differences:
- **`--ignore-missing-imports`** suppresses the entire `reportMissingImports` category (57 errors)
- Mypy does not flag `TypedDict` optional key access the way pyright does (115 errors)
- Mypy's argument type checking is less strict than pyright's `reportArgumentType` (158 errors)

### 2. No pyrightconfig.json exists

Without configuration, pyright:
- May resolve against the **system Python (3.10.12)** instead of venv Python (3.11.15)
- Cannot find installed packages in `backend/.venv/` (no `venvPath` set)
- Uses `off` type checking mode by default (or default basic depending on version)

This causes ~170 errors that would likely resolve with proper configuration:
- ~96 `from datetime import UTC` errors (valid in Python 3.11+, but pyright may use 3.10 typeshed)
- ~57 `import stripe` / `import google.genai` errors (`stripe` ships `py.typed`; needs `venvPath`)
- ~16 `reportMissingModuleSource` (would resolve with venvPath)
- ~1 `asyncio.timeout` (added in Python 3.11)

### 3. The "typecheck all green" claims referred to mypy

Commit `b9b7893` (REQ-032 completion) states: "typecheck + lint all green." The "typecheck" here means mypy, which has always passed. Pyright was never part of the quality gate.

---

## Findings Summary

1. **The "cascade" hypothesis is disproven.** REQ-031 and REQ-032 introduced zero new pyright errors.
2. **Errors accumulated gradually** since the project began. The Stripe/billing work (REQ-029) added +41 errors, and ~498 existed before that.
3. **~170 errors (~32%) are likely configuration artifacts** that will resolve by creating `pyrightconfig.json` with proper `pythonVersion` and `venvPath`.
4. **~370 errors (~68%) are genuine type issues** — primarily in test files where untyped dicts are passed to typed functions, and TypedDict fields are accessed without optional guards.
5. **Pyright and mypy are complementary.** Adding pyright alongside mypy would catch type issues that mypy's `--ignore-missing-imports` and less strict TypedDict checking miss.

---

## Recommendations

1. **Create `backend/pyrightconfig.json`** with proper Python version and venv resolution → Phase 1 §2
2. **Fix remaining ~370 genuine type errors** → Phases 2-3
3. **Add pyright to pre-commit hooks** alongside mypy → Phase 4
4. **Keep mypy** — it has SQLAlchemy/Pydantic plugin support that pyright lacks

---

## Config Win Results (§2 — validated 2026-04-01)

**pyrightconfig.json:** `pythonVersion: "3.11"`, `venvPath: "."`, `venv: ".venv"`, `include: ["app", "tests"]`, `typeCheckingMode: "basic"`

**Result:** 539 → 385 errors (154 resolved, but 42 new errors surfaced from better type resolution). Net: -154.

### Category Comparison

| Category | Before Config | After Config | Delta | Notes |
|----------|--------------|-------------|-------|-------|
| reportArgumentType | 158 | 182 | +24 | Better type resolution exposed more mismatches |
| reportAttributeAccessIssue | 140 | 19 | **-121** | UTC imports + asyncio.timeout resolved |
| reportTypedDictNotRequiredAccess | 115 | 115 | 0 | Unchanged — code fix needed |
| reportMissingImports | 57 | 1 | **-56** | venvPath resolved stripe/genai/etc. |
| reportCallIssue | 23 | 36 | +13 | Better resolution exposed more call issues |
| reportOptionalMemberAccess | 19 | 23 | +4 | More found with proper types |
| reportMissingModuleSource | 16 | 0 | **-16** | All resolved by venvPath |
| reportIncompatibleMethodOverride | 10 | 0 | **-10** | Resolved by proper type resolution |
| reportIncompatibleVariableOverride | 6 | 0 | **-6** | Resolved by proper type resolution |
| reportOptionalSubscript | 6 | 5 | -1 | |
| reportOptionalOperand | 1 | 0 | -1 | |
| reportInvalidTypeForm | 1 | 0 | -1 | |
| reportGeneralTypeIssues | 0 | 1 | +1 | New |
| Others (unchanged) | 3 | 3 | 0 | |

### Key Insight

Config didn't just remove errors — it **shifted** them. With proper venv/Python resolution, pyright can now see the actual types of stripe, openai, and google-genai objects. This revealed 42 NEW type mismatches that were previously hidden behind "missing import" errors.

### Error Distribution After Config

- **Production code (`app/`):** 14 errors across 5 files
- **Test code (`tests/`):** 371 errors across ~40 files
- Production errors are in: `openai_adapter.py` (7), `pdf_generation.py` (3), `chat.py` (2), `cover_letter_pdf_generation.py` (1), `job_scoring_service.py` (1)

### Plan Impact

The `reportIncompatibleMethodOverride` category (§5 in original plan) is now **fully resolved** by config — no code changes needed for that task. Phase 2 can focus on the 14 remaining production code errors. Phase 3 scope stays similar (~370 test errors).
