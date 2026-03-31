# Zentropy Scout — REQ-032 Frontend JSDoc & Import Hygiene Plan

**Created:** 2026-03-30
**Last Updated:** 2026-03-30
**Status:** ⬜ Not Started
**Branch:** (TBD — will branch from main)
**REQ:** REQ-032

---

## Context

The `frontend/src/` tree has two documentation and dependency hygiene issues identified during a comprehensive analysis of all 266 non-test source files:

1. **Inverted import direction.** Five `lib/*-helpers.ts` files import FormData types (and one runtime function) from `components/onboarding/steps/`. This violates the intended dependency direction: `components/ → lib/ → types/`. The Zod schemas, inferred FormData types, `toMonthValue` utility, and skill category constants must move into the corresponding `lib/*-helpers.ts` files.

2. **Missing coordination context in JSDoc.** ~55 files in `lib/`, `hooks/`, and `types/` have JSDoc that answers *what* but not *which other files they coordinate with*. 3 files are missing JSDoc entirely. The `@coordinates-with` tag must be added per the three-axis standard.

**What changes:** 5 Zod schemas + 5 FormData types + 1 runtime function + 2 constants extracted from component files into lib/ helpers. ~55 `@coordinates-with` tags added. 3 complete JSDoc headers written. All import paths updated.

**What does NOT change:** Component behavior, API contracts, test logic, database, backend. No new files created.

---

## How to Use This Document

1. Find the first 🟡 or ⬜ task — that's where to start
2. Load REQ-032 via `req-reader` subagent before each task (load the §sections listed)
3. Each task = one commit, sized ≤ 150k tokens of context
4. **Subtask workflow:** Extract/edit → run affected tests → linters → commit → STOP and ask user (NO push)
5. **Phase-end workflow:** Run full test suite (backend + frontend) → push → STOP and ask user
6. After each task: update status (⬜ → ✅), commit, STOP and ask user

---

## Dependency Chain

```
Phase 1: Import Direction Fix (REQ-032 §4)
    │     Extract schemas/types/functions from 5 component files
    │     into 5 lib/*-helpers.ts files. Update all consumer imports.
    │     Actual code movement — needs full test verification.
    ▼
Phase 2: JSDoc Standardization (REQ-032 §5)
          Add @coordinates-with to ~55 files in lib/, hooks/, types/.
          Add complete headers to 3 files. Pure documentation —
          no behavior change.
```

**Ordering rationale:** Phase 1 changes file contents and import graphs. Phase 2 documents the *final* state — must come after extraction so `@coordinates-with` tags reflect post-move import paths.

---

## Phase 1: Import Direction Fix

**Status:** ✅ Complete

*Extract Zod schemas, FormData types, `toMonthValue()`, and skill category constants from 5 component files into their corresponding `lib/*-helpers.ts` files. Update all import paths so components import FROM lib/ (correct direction). Verify zero `from.*@/components` imports remain in `lib/` (except `onboarding-provider.tsx` which imports step metadata, not FormData — out of scope).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 §4 (extraction inventory, target state, verification) |
| 🔧 **Extract** | Move schemas/types/functions from component → lib/ helper |
| 🔄 **Update** | Fix all consumer import paths (step components, persona editors) |
| ✅ **Verify** | `npm test -- --run`, `npm run typecheck`, `npm run lint`, `grep -r "from.*@/components" frontend/src/lib/` |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` (parallel, foreground) |
| 📝 **Commit** | One commit per subtask, follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). Verdicts: CLEAR → proceed. VULNERABLE → fix immediately. FALSE POSITIVE → full prosecution protocol. NEEDS INVESTIGATION → escalate via AskUserQuestion. | `plan, security` | ✅ |
| 2 | **Extract work-history schema, type, and toMonthValue into lib/** — From `work-history-form.tsx`, extract `workHistoryFormSchema` (Zod), `WorkHistoryFormData` (inferred type), `toMonthValue()` (runtime function), and schema-only constants (`MAX_TEXT_LENGTH`, `MONTH_PATTERN`, etc.) into `lib/work-history-helpers.ts`. Update component to import FROM helpers. Update consumers: `work-history-step.tsx`, `work-history-editor.tsx`. Verify: grep confirms no `@/components` imports in helpers, all work-history tests pass. | `plan, tdd, lint, docs` | ✅ |
| 3 | **Extract certification + education schemas/types into lib/** — From `certification-form.tsx`, extract `certificationFormSchema` + `CertificationFormData` + schema constants into `lib/certification-helpers.ts`. From `education-form.tsx`, extract `educationFormSchema` + `EducationFormData` + schema constants into `lib/education-helpers.ts`. Update both components to import FROM helpers. Update consumers: `{certification,education}-step.tsx`, `{certification,education}-editor.tsx`. Verify: all certification + education tests pass. | `plan, tdd, lint, docs` | ✅ |
| 4 | **Extract skills + story schemas/types into lib/** — From `skills-form.tsx`, extract `skillFormSchema` + `SkillFormData` + `HARD_SKILL_CATEGORIES` + `SOFT_SKILL_CATEGORIES` + schema constants into `lib/skills-helpers.ts`. From `story-form.tsx`, extract `storyFormSchema` + `StoryFormData` + schema constants into `lib/achievement-stories-helpers.ts`. Update consumers. Final verification: `grep -r "from.*@/components" frontend/src/lib/` returns only `onboarding-provider.tsx` (step metadata import — out of scope). | `plan, tdd, lint, docs` | ✅ |
| 5 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + lint + typecheck). Verify import direction fix is complete. Fix regressions, commit, push. | `plan, commands` | ✅ |

#### Notes
- **Constants that live in BOTH schema and JSX:** If a constant like `MAX_TEXT_LENGTH` is used in both the Zod schema refinement AND the component template (e.g., character count display), export it from the helper file and import it in the component. If used only in the schema, it moves silently.
- **`DEFAULT_VALUES` stay in components** — these are presentation defaults, not validation logic.
- **`onboarding-provider.tsx`** imports from `@/components/onboarding/onboarding-steps` (step metadata/routing, not FormData types). This is a legitimate config-style import and out of scope for REQ-032.
- **Each extraction follows the same pattern:** (1) Move schema + type + utilities to helpers, (2) Add `import { z } from "zod"` to helpers, (3) Remove old `import type { ...FormData } from "@/components/..."` from helpers, (4) Update component to `import { schema } from "@/lib/...-helpers"`, (5) Update step/editor consumers.

---

## Phase 2: JSDoc Standardization

**Status:** ⬜ Incomplete

*Add three-axis JSDoc headers (`@coordinates-with` tags) to ~55 files in `lib/`, `hooks/`, and `types/`. Add complete headers to 3 files missing all JSDoc. Pure documentation additions — no behavior changes.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 §5 (three-axis standard, format template, flagged file list) |
| 📝 **Add** | Append `@coordinates-with` block below existing JSDoc, or write complete header for files missing JSDoc |
| ✅ **Verify** | `npm run typecheck`, `npm run lint` |
| 🔍 **Review** | `code-reviewer` (verify @coordinates-with paths reference real files) |
| 📝 **Commit** | One commit per subtask, follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 6 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). Same verdicts as §1. | `plan, security` | ✅ |
| 7 | **JSDoc — lib/ providers + API + SSE (14 files)** — Add `@coordinates-with` to 12 files with existing JSDoc: `api-client.ts`, `query-keys.ts`, `query-client.ts`, `query-provider.tsx`, `auth-provider.tsx`, `onboarding-provider.tsx`, `sse-client.ts`, `sse-query-bridge.ts`, `sse-provider.tsx`, `chat-provider.tsx`, `chat-panel-provider.tsx`, `embedding-staleness.ts`. Add complete three-axis headers to 2 files missing all JSDoc: `utils.ts`, `toast.ts`. | `plan, docs, lint` | ✅ |
| 8 | **JSDoc — lib/ utilities + form infrastructure (11 files)** — Add/strengthen JSDoc for: `form-errors.ts`, `map-server-errors.ts`, `basic-info-schema.ts`, `format-utils.ts`, `job-formatters.ts`, `score-formatters.ts`, `diff-utils.ts`, `url-utils.ts`, `resume-helpers.ts`, `api/admin.ts`, `api/credits.ts`. | `plan, docs, lint` | ✅ |
| 9 | **JSDoc — lib/ persona helpers (9 files)** — Strengthen where + add `@coordinates-with` for all 9 persona CRUD helpers: `work-history-helpers.ts`, `certification-helpers.ts`, `education-helpers.ts`, `skills-helpers.ts`, `achievement-stories-helpers.ts`, `voice-profile-helpers.ts`, `non-negotiables-helpers.ts`, `growth-targets-helpers.ts`, `discovery-preferences-helpers.ts`. All follow the same template pattern (toFormValues/toRequestBody). | `plan, docs, lint` | ✅ |
| 10 | **JSDoc — hooks/ (10 files)** — Add `@coordinates-with` to all 10 hooks: `use-is-mobile.ts`, `use-media-query.ts`, `use-chat-scroll.ts`, `use-delete-with-references.ts`, `use-persona-status.ts`, `use-crud-step.ts`, `use-resume-content-selection.ts`, `use-balance.ts`, `use-auto-save.ts`, `use-resume-detail.ts`. | `plan, docs, lint` | ✅ |
| 11 | **JSDoc — types/ (14 files)** — Add complete header to `index.ts` (missing all JSDoc). Add `@coordinates-with` to 13 domain type files: `persona.ts`, `job.ts`, `application.ts`, `resume.ts`, `resume-generation.ts`, `api.ts`, `chat.ts`, `sse.ts`, `deletion.ts`, `source.ts`, `ingest.ts`, `admin.ts`, `usage.ts`. | `plan, docs, lint` | ⬜ |
| 12 | **Phase gate — full test suite + push** — Run test-runner in Full mode (pytest + Vitest + lint + typecheck). Spot-check 5 random files to verify three-axis headers. Fix any issues, commit, push. | `plan, commands` | ⬜ |

#### Notes
- JSDoc changes are pure documentation — they cannot break tests. Primary risk is stale file references in `@coordinates-with` tags. Verify named paths exist before committing.
- For widely-used files (`utils.ts` with 63 consumers, `api-client.ts` with 30+), name the *category* of consumers rather than listing every file.
- Files that already have substantial JSDoc (most lib/ files): **append** the `@coordinates-with` block below existing content. Do not rewrite existing headers.
- The 3 files needing complete headers (`utils.ts`, `toast.ts`, `types/index.ts`) should follow the zentropy-docs skill template.
- Draft replacement headers for all 66 files were produced during the REQ-032 analysis and are available in the conversation that created this plan. Use them as starting points but verify `@coordinates-with` paths against current codebase state.

---

## Task Count Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| Phase 1 | 5 | Security gate (§1) + 3 extraction tasks (§2–§4) + phase gate (§5) |
| Phase 2 | 7 | Security gate (§6) + 5 JSDoc tasks (§7–§11) + phase gate (§12) |
| **Total** | **12** | |

---

## Critical Files Reference

| File | Role in Plan |
|------|-------------|
| `docs/requirements/REQ-032_frontend_jsdoc_import_hygiene.md` | Authoritative spec — flagged file lists, verification criteria |
| `frontend/src/lib/work-history-helpers.ts` | Most complex extraction (runtime function + schema + type) |
| `frontend/src/components/onboarding/steps/work-history-form.tsx` | Source of most complex extraction |
| `frontend/src/lib/skills-helpers.ts` | Extraction includes category constants + schema + type |
| `frontend/src/components/onboarding/steps/skills-form.tsx` | Source of skills extraction |
| `.claude/skills/zentropy-docs/SKILL.md` | Three-axis JSDoc template definition |

---

## Change Log

| Date | Change |
|------|--------|
| 2026-03-30 | Initial plan created |
