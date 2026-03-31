# REQ-032: Frontend JSDoc & Import Hygiene

**Status:** Not Started
**Version:** 0.1
**PRD Reference:** Internal -- Code Organization & Maintainability
**Backlog Item:** N/A
**Last Updated:** 2026-03-30

---

## 1. Overview

The `frontend/src/` tree has two documentation and dependency hygiene issues:

1. **Missing coordination context in JSDoc.** ~66 of ~266 non-test source files (lib/, hooks/, types/) have JSDoc that answers *what* the file does but not *which other files it coordinates with*. An LLM or developer reading a single file cannot reconstruct data flow without opening imports. Components (~176 files) already have ~95% three-axis JSDoc coverage and are excluded from this scope.
2. **Inverted import direction.** Five `lib/*-helpers.ts` files import from `components/onboarding/steps/` (FormData types and one runtime function). This violates the intended dependency direction: `components/ -> lib/ -> types/`.

### 1.1 Solution

1. **Fix the inverted imports** by extracting the 5 FormData type definitions and the `toMonthValue` runtime utility out of their component files and into lib/ or types/, then updating all import paths so that components import from lib/types rather than the reverse.
2. **Add three-axis JSDoc headers** (`@module`, what/where/coordinates-with) to all ~66 flagged files in `lib/`, `hooks/`, and `types/`. Files that already pass the three-axis test are left unchanged. Component files are out of scope (already covered).

### 1.2 Scope

| In Scope | Out of Scope |
|----------|-------------|
| Extract 5 FormData types + `toMonthValue` from component files into lib/ or types/ | lib/ subdirectory reorganization (deferred -- see Decision Log) |
| Update all import paths for the extracted types/functions | New business logic or behavior changes |
| Add/update JSDoc headers on ~66 files in lib/, hooks/, types/ | Component JSDoc (already ~95% covered) |
| Verify no remaining lib/ -> components/ imports | API contract changes |
| | Frontend test restructuring |
| | Database migrations |

### 1.3 Relationship to Existing REQs

REQ-032 **amends** JSDoc standards established in REQ-012 SS13 (frontend architecture) by adding the `@coordinates-with` axis requirement for lib/, hooks/, and types/ files. No behavioral specifications are changed.

---

## 2. Dependencies

### 2.1 This Document Depends On

| Dependency | Type | Notes |
|------------|------|-------|
| All source files in `frontend/src/lib/`, `hooks/`, `types/` | Source | Files being documented |
| REQ-012 SS13 | Context | Frontend architecture and JSDoc standards |
| REQ-031 | Precedent | Same pattern (docstring standardization) applied to backend services |

### 2.2 Other Documents Depend On This

| Document | Dependency | Notes |
|----------|------------|-------|
| Future frontend REQs | JSDoc conventions | New files should follow three-axis JSDoc |

---

## 3. Decision Log

| # | Decision | Rationale | Date |
|---|----------|-----------|------|
| D1 | Skip lib/ subdirectory reorganization | Naming conventions (`*-helpers.ts`, `*-provider.tsx`) already make groupings discoverable. Moving 29 files and updating ~120 import paths has high churn-to-benefit ratio. | 2026-03-30 |
| D2 | Skip API module pattern standardization | `api/admin.ts` and `api/credits.ts` exist as domain modules; most components call `apiGet`/`apiPost` directly. Inconsistent but functional. Document convention boundary rather than migrate. | 2026-03-30 |
| D3 | Scope JSDoc to lib/, hooks/, types/ only | Components already have ~95% three-axis coverage. The 66 flagged files are concentrated in the three utility/infrastructure directories. | 2026-03-30 |

---

## 4. Import Direction Fix Specification

### 4.1 Current State (Violated)

Five `lib/*-helpers.ts` files import types and one function from `components/onboarding/steps/`:

| lib/ File | Imports From | What | Import Kind |
|-----------|-------------|------|-------------|
| `work-history-helpers.ts` | `components/onboarding/steps/work-history-form.tsx` | `WorkHistoryFormData` | type-only |
| `work-history-helpers.ts` | `components/onboarding/steps/work-history-form.tsx` | `toMonthValue` | **runtime** |
| `certification-helpers.ts` | `components/onboarding/steps/certification-form.tsx` | `CertificationFormData` | type-only |
| `education-helpers.ts` | `components/onboarding/steps/education-form.tsx` | `EducationFormData` | type-only |
| `skills-helpers.ts` | `components/onboarding/steps/skills-form.tsx` | `SkillFormData` | type-only |
| `achievement-stories-helpers.ts` | `components/onboarding/steps/story-form.tsx` | `StoryFormData` | type-only |

### 4.2 Target State

All FormData types and `toMonthValue` are defined in the corresponding `lib/*-helpers.ts` file. The component files import the types FROM lib/ (correct direction). The Zod schemas that infer the FormData types move with them.

```
CORRECT DIRECTION:
  components/onboarding/steps/work-history-form.tsx
    --> imports WorkHistoryFormData, toMonthValue from @/lib/work-history-helpers

  lib/work-history-helpers.ts
    --> imports WorkHistory from @/types/persona (already does this)
    --> exports WorkHistoryFormData, toMonthValue, workHistoryFormSchema
```

### 4.3 Extraction Inventory

For each component, the following must move into the corresponding `lib/*-helpers.ts`:

| Component File | Extract | Destination |
|---------------|---------|-------------|
| `work-history-form.tsx` | `workHistoryFormSchema` (Zod), `WorkHistoryFormData` (inferred type), `toMonthValue()` (function) | `lib/work-history-helpers.ts` |
| `certification-form.tsx` | `certificationFormSchema` (Zod), `CertificationFormData` (inferred type) | `lib/certification-helpers.ts` |
| `education-form.tsx` | `educationFormSchema` (Zod), `EducationFormData` (inferred type) | `lib/education-helpers.ts` |
| `skills-form.tsx` | `skillFormSchema` (Zod), `SkillFormData` (inferred type), `HARD_SKILL_CATEGORIES`, `SOFT_SKILL_CATEGORIES` | `lib/skills-helpers.ts` |
| `story-form.tsx` | `storyFormSchema` (Zod), `StoryFormData` (inferred type) | `lib/achievement-stories-helpers.ts` |

### 4.4 Verification Criteria

After extraction:
1. `grep -r "from.*@/components" frontend/src/lib/` returns zero matches
2. All existing tests pass unchanged (behavior is identical)
3. TypeScript compilation succeeds (`npm run typecheck`)
4. Linting passes (`npm run lint`)

---

## 5. JSDoc Specification

### 5.1 Three-Axis Standard

Every non-test `.ts` / `.tsx` file in `lib/`, `hooks/`, and `types/` must have a file-level JSDoc header that passes the **three-axis test**:

| Axis | Question Answered | Required Element |
|------|-------------------|-----------------|
| **What** | What does this file do? | 1-3 sentence description of purpose |
| **Where** | Where does it sit in the system? | REQ reference, layer identification, or feature area |
| **Coordinates-with** | What other files does it work with? | `@coordinates-with` tag naming 2-5 specific file paths or modules |

### 5.2 Format Template

```typescript
/**
 * <One-line summary of what the file does.>
 *
 * <Optional 1-3 sentences of additional context, REQ references,
 * design rationale, or behavioral notes.>
 *
 * @module <directory/filename without extension>
 * @coordinates-with <file1> (<why>),
 *   <file2> (<why>),
 *   <file3> (<why>)
 */
```

### 5.3 Guidelines

- The `@coordinates-with` tag should name **direct** dependencies and consumers, not transitive ones. 2-5 entries is ideal; for widely-used files (e.g., `utils.ts` with 63 consumers), name the category rather than listing all files.
- For type barrel files (`types/index.ts`), list the re-exported modules.
- For hooks, name the primary consumer components and any lib/ files they depend on.
- Do not add `@coordinates-with` to files that genuinely have no coordination (pure leaf utilities with no project imports). These are rare.

### 5.4 Flagged Files

66 files require JSDoc additions or updates:

**lib/ (31 files):**

| File | Missing Axes | Action |
|------|-------------|--------|
| `utils.ts` | All three | Add complete header |
| `toast.ts` | All three | Add complete header |
| `api-client.ts` | Coordinates | Add `@coordinates-with` |
| `query-keys.ts` | Coordinates | Add `@coordinates-with` |
| `query-client.ts` | Coordinates | Add `@coordinates-with` |
| `query-provider.tsx` | Coordinates | Add `@coordinates-with` |
| `auth-provider.tsx` | Coordinates | Add `@coordinates-with` |
| `onboarding-provider.tsx` | Coordinates | Add `@coordinates-with` |
| `sse-client.ts` | Coordinates | Add `@coordinates-with` |
| `sse-query-bridge.ts` | Coordinates | Add `@coordinates-with` |
| `embedding-staleness.ts` | Coordinates | Add `@coordinates-with` |
| `form-errors.ts` | Where, Coordinates | Strengthen where + add `@coordinates-with` |
| `map-server-errors.ts` | Where, Coordinates | Strengthen where + add `@coordinates-with` |
| `basic-info-schema.ts` | Coordinates | Formalize `@coordinates-with` |
| `format-utils.ts` | Coordinates | Add `@coordinates-with` |
| `job-formatters.ts` | Where, Coordinates | Strengthen where + add `@coordinates-with` |
| `score-formatters.ts` | Coordinates | Formalize `@coordinates-with` |
| `diff-utils.ts` | Coordinates | Add `@coordinates-with` |
| `url-utils.ts` | Where, Coordinates | Add where + `@coordinates-with` |
| `resume-helpers.ts` | Coordinates | Add `@coordinates-with` |
| `api/admin.ts` | Coordinates | Add `@coordinates-with` |
| `api/credits.ts` | Coordinates | Add `@coordinates-with` |
| `work-history-helpers.ts` | Where, Coordinates | Strengthen where + add `@coordinates-with` |
| `certification-helpers.ts` | Where, Coordinates | Strengthen where + add `@coordinates-with` |
| `education-helpers.ts` | Where, Coordinates | Strengthen where + add `@coordinates-with` |
| `skills-helpers.ts` | Where, Coordinates | Strengthen where + add `@coordinates-with` |
| `achievement-stories-helpers.ts` | Where, Coordinates | Strengthen where + add `@coordinates-with` |
| `voice-profile-helpers.ts` | Where, Coordinates | Strengthen where + add `@coordinates-with` |
| `non-negotiables-helpers.ts` | Where, Coordinates | Strengthen where + add `@coordinates-with` |
| `growth-targets-helpers.ts` | Where, Coordinates | Strengthen where + add `@coordinates-with` |
| `discovery-preferences-helpers.ts` | Where, Coordinates | Strengthen where + add `@coordinates-with` |

**hooks/ (10 files):**

| File | Missing Axes | Action |
|------|-------------|--------|
| `use-is-mobile.ts` | Coordinates | Add `@coordinates-with` |
| `use-media-query.ts` | Coordinates | Add `@coordinates-with` |
| `use-chat-scroll.ts` | Coordinates | Add `@coordinates-with` |
| `use-delete-with-references.ts` | Coordinates | Add `@coordinates-with` |
| `use-persona-status.ts` | Coordinates | Add `@coordinates-with` |
| `use-crud-step.ts` | Coordinates | Formalize `@coordinates-with` |
| `use-resume-content-selection.ts` | Coordinates | Add `@coordinates-with` |
| `use-balance.ts` | Coordinates | Add `@coordinates-with` |
| `use-auto-save.ts` | Coordinates | Add `@coordinates-with` |
| `use-resume-detail.ts` | Where, Coordinates | Strengthen where + add `@coordinates-with` |

**types/ (14 files):**

| File | Missing Axes | Action |
|------|-------------|--------|
| `index.ts` | All three | Add complete header |
| `persona.ts` | Coordinates | Add `@coordinates-with` |
| `job.ts` | Coordinates | Add `@coordinates-with` |
| `application.ts` | Coordinates | Add `@coordinates-with` |
| `resume.ts` | Coordinates | Add `@coordinates-with` |
| `resume-generation.ts` | Coordinates | Add `@coordinates-with` |
| `api.ts` | Coordinates | Add `@coordinates-with` |
| `chat.ts` | Coordinates | Add `@coordinates-with` |
| `sse.ts` | Coordinates | Add `@coordinates-with` |
| `deletion.ts` | Coordinates | Add `@coordinates-with` |
| `source.ts` | Coordinates | Add `@coordinates-with` |
| `ingest.ts` | Coordinates | Add `@coordinates-with` |
| `admin.ts` | Coordinates | Add `@coordinates-with` |
| `usage.ts` | Coordinates | Add `@coordinates-with` |

### 5.5 Verification Criteria

1. Every non-test `.ts`/`.tsx` file in `lib/`, `hooks/`, `types/` has a file-level JSDoc with all three axes
2. No JSDoc contains stale file references (verify paths exist)
3. TypeScript compilation succeeds (JSDoc changes don't affect types)
4. ESLint passes

---

## 6. Changelog

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-03-30 | Claude + Brian | Initial draft |
