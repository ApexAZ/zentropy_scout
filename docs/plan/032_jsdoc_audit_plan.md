# Zentropy Scout -- REQ-032 File-Level Docstring Header Audit Plan (Frontend & Backend)

**Created:** 2026-03-31
**Last Updated:** 2026-03-31
**Status:** Not Started
**Branch:** main
**REQ:** REQ-032 (v1.1)

---

## Context

Every non-test source file in `frontend/src/` and `backend/app/` must have a
three-axis file-level docstring header so an LLM reading any file cold can answer:
what it does, where it sits in the system, and what other files it coordinates
with -- without opening any other file.

**Current state — Frontend:**
- `lib/`, `hooks/`, `types/` (~55 files): Have JSDoc with `@module`/`@coordinates-with`
  tags from the v0.1 plan. These need reformatting to the `zentropy-docs` template
  (add `@fileoverview`, `Layer:`, `Feature:`, `Called by / Used by:`; reformat
  `Coordinates with:` to bullet-list style).
- `components/` (~176 files): Most have partial JSDoc (what + REQ refs) but no
  `Layer:`, `Feature:`, `Coordinates with:`, or `Called by:`. Need complete headers.
- `app/` (~38 files): Most have minimal or no JSDoc. Need complete headers.
- `proxy.ts` (1 file): Needs complete header.

**Current state — Backend:**
- `services/` (~86 files): Already have `Coordinates with:` / `Called by:` sections
  from REQ-031. Need verification that headers are accurate and complete.
- Non-service files (~108 files in `core/`, `models/`, `repositories/`, `schemas/`,
  `api/`, `providers/`, `adapters/`, `agents/`, `prompts/`, `scripts/`): Have
  Google-style docstrings with REQ refs but no `Coordinates with:` / `Called by:`.
  Need additions.

**What changes:** ~262 frontend files + ~194 backend files get three-axis docstring
headers. No functional code changes.

**What does NOT change:** Component behavior, API contracts, tests, database logic.

**Skipped — Frontend:** 14 thin shadcn/Radix wrappers in `components/ui/` (verify
each before skipping -- see REQ-032 SS3.1).

**Skipped — Backend:** Empty `__init__.py` files, Alembic migration files
(`alembic/versions/*.py`, `alembic/env.py`) -- see REQ-032 SS3.2.

---

## How to Use This Document

1. Find the first `🟡` or `⬜` task -- that's where to start
2. Load REQ-032 via `req-reader` subagent before each phase
3. Each task = one commit, sized <= 150k tokens of context
4. **Subtask workflow:** read -> trace -> write headers -> verify three-axis test -> `code-reviewer` -> commit -> STOP and ask user (NO push)
5. **Phase-end workflow (frontend):** `npm run lint && npm run typecheck` -> fix any issues -> commit -> push -> STOP and ask user
5b. **Phase-end workflow (backend):** `ruff check .` + `pyright` -> fix any issues -> commit -> push -> STOP and ask user
6. After each task: update status (`⬜` -> `✅`), commit, STOP and ask user
7. **No TDD cycle** -- docs-only changes have no test to write
8. **No security triage gates** -- no functional code changes, no new attack surface

---

## Dependency Chain

```
FRONTEND (Phases 1-11)
Phase 1-2: lib/ (core + helpers)
    |     These files are imported by everything else -- tracing
    |     components after lib headers exist is faster and more accurate.
    v
Phase 3: types/ + hooks/
    |     Type definitions and hooks consumed by all component layers.
    v
Phase 4: app/ pages and layouts
    |     Top-level routing and page components.
    v
Phase 5-11: components/ (by feature domain)
            Each phase covers one or two component directories.
            Order follows feature dependency: layout -> persona -> jobs ->
            resume -> chat -> applications -> settings -> onboarding -> ui

BACKEND (Phases 12-16)
Phase 12: core/ + app root
    |     Config, database, security, error handling -- imported by everything.
    v
Phase 13: models/ + schemas/
    |     Data model layer -- referenced by repositories, services, API.
    v
Phase 14: repositories/ + api/
    |     Data access + HTTP layer -- sits between models and services.
    v
Phase 15: providers/ + adapters/ + agents/ + prompts/ + scripts/
    |     External integrations and LLM infrastructure.
    v
Phase 16: services/ (verify/update existing)
          ~86 files already have Coordinates-with/Called-by from REQ-031.
          Lighter-weight verification pass.
```

**Ordering rationale:** Frontend first (lib/ -> types/ -> app/ -> components/),
then backend (core/ -> models/ -> repos/api/ -> providers/ -> services/).
Within each stack, foundation layers first because downstream tracing is faster
once upstream headers exist.

---

## Phase 1: lib/ Core Infrastructure

**Status:** ✅ Complete

*Reformat existing JSDoc headers on 15 core lib/ files to the zentropy-docs template.
These files are imported by nearly every component -- accurate headers here make all
subsequent phases faster to trace.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS2 + zentropy-docs skill SS TypeScript File-Level Headers |
| 📝 **Reformat** | Replace `@module`/`@coordinates-with` with `@fileoverview`, `Layer:`, `Feature:`, `Coordinates with:` (bullet list), `Called by / Used by:` |
| ✅ **Verify** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` (verify paths reference real files) |
| 📝 **Commit** | `docs(jsdoc): add file-level headers -- lib/ core infrastructure` |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **JSDoc -- lib/ core infrastructure (15 files)** -- Reformat headers: `api-client.ts`, `query-client.ts`, `query-provider.tsx`, `query-keys.ts`, `sse-client.ts`, `sse-provider.tsx`, `sse-query-bridge.ts`, `auth-provider.tsx`, `onboarding-provider.tsx`, `chat-provider.tsx`, `chat-panel-provider.tsx`, `map-server-errors.ts`, `form-errors.ts`, `utils.ts`, `toast.ts`. Use Explore subagent to trace import/export graphs for accurate `Coordinates with:` and `Called by:` entries. | `docs, plan` | ✅ |
| 2 | **Phase gate -- lint + typecheck + push** | `plan, commands` | ✅ |

---

## Phase 2: lib/ Helpers and Formatters

**Status:** ✅ Complete

*Reformat existing JSDoc headers on 19 helper/formatter files in lib/. These handle
persona CRUD transforms, API modules, and display formatting.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS2 |
| 📝 **Reformat** | Same template conversion as Phase 1 |
| ✅ **Verify** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | `docs(jsdoc): add file-level headers -- lib/ helpers and formatters` |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 3 | **JSDoc -- lib/ helpers and formatters (19 files)** -- Reformat headers: `api/admin.ts`, `api/credits.ts`, `format-utils.ts`, `url-utils.ts`, `diff-utils.ts`, `score-formatters.ts`, `job-formatters.ts`, `resume-helpers.ts`, `embedding-staleness.ts`, `basic-info-schema.ts`, `skills-helpers.ts`, `work-history-helpers.ts`, `education-helpers.ts`, `certification-helpers.ts`, `achievement-stories-helpers.ts`, `non-negotiables-helpers.ts`, `growth-targets-helpers.ts`, `voice-profile-helpers.ts`, `discovery-preferences-helpers.ts`. | `docs, plan` | ✅ |
| 4 | **Phase gate -- lint + typecheck + push** | `plan, commands` | ✅ |

---

## Phase 3: types/ and hooks/

**Status:** ✅ Complete

*Reformat existing JSDoc headers on all 14 type definition files and 10 hook files.
Types define the domain model; hooks encapsulate reusable stateful logic.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS2 |
| 📝 **Reformat** | Same template conversion as Phase 1 |
| ✅ **Verify** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 5 | **JSDoc -- types/ (14 files)** -- Reformat headers: `index.ts`, `persona.ts`, `job.ts`, `application.ts`, `resume.ts`, `resume-generation.ts`, `api.ts`, `chat.ts`, `sse.ts`, `deletion.ts`, `source.ts`, `ingest.ts`, `admin.ts`, `usage.ts`. | `docs, plan` | ✅ |
| 6 | **JSDoc -- hooks/ (10 files)** -- Reformat headers: `use-auto-save.ts`, `use-balance.ts`, `use-chat-scroll.ts`, `use-crud-step.ts`, `use-delete-with-references.ts`, `use-is-mobile.ts`, `use-media-query.ts`, `use-persona-status.ts`, `use-resume-content-selection.ts`, `use-resume-detail.ts`. | `docs, plan` | ✅ |
| 7 | **Phase gate -- lint + typecheck + push** | `plan, commands` | ✅ |

---

## Phase 4: app/ Pages and Layouts

**Status:** ✅ Complete

*Add three-axis JSDoc headers to all ~38 page and layout files in app/ plus proxy.ts.
Most have minimal or no existing JSDoc. Split into 3 subtasks by route group.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS4 (per-file process) |
| 📝 **Add** | Write complete three-axis headers from scratch |
| ✅ **Verify** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 8 | **JSDoc -- app/ root + (public) + proxy (12 files)** -- Add headers: `app/layout.tsx`, `app/login/page.tsx`, `app/register/page.tsx`, `app/onboarding/page.tsx`, `app/(public)/layout.tsx`, `app/(public)/page.tsx`, `app/(public)/components/feature-cards.tsx`, `app/(public)/components/hero-section.tsx`, `app/(public)/components/how-it-works.tsx`, `app/(public)/components/landing-footer.tsx`, `app/(public)/components/landing-nav.tsx`, `proxy.ts`. | `docs, plan` | ✅ |
| 9 | **JSDoc -- app/(main) persona pages (12 files)** -- Add headers: `app/(main)/layout.tsx`, `app/(main)/persona/page.tsx`, `app/(main)/persona/basic-info/page.tsx`, `app/(main)/persona/work-history/page.tsx`, `app/(main)/persona/education/page.tsx`, `app/(main)/persona/certifications/page.tsx`, `app/(main)/persona/skills/page.tsx`, `app/(main)/persona/achievement-stories/page.tsx`, `app/(main)/persona/voice-profile/page.tsx`, `app/(main)/persona/non-negotiables/page.tsx`, `app/(main)/persona/growth/page.tsx`, `app/(main)/persona/discovery/page.tsx`. | `docs, plan` | ✅ |
| 10 | **JSDoc -- app/(main) remaining pages (14 files)** -- Add headers: `app/(main)/persona/change-flags/page.tsx`, `app/(main)/dashboard/page.tsx`, `app/(main)/settings/page.tsx`, `app/(main)/usage/page.tsx`, `app/(main)/admin/config/page.tsx`, `app/(main)/applications/page.tsx`, `app/(main)/applications/[id]/page.tsx`, `app/(main)/jobs/[id]/page.tsx`, `app/(main)/jobs/[id]/review/page.tsx`, `app/(main)/resumes/page.tsx`, `app/(main)/resumes/[id]/page.tsx`, `app/(main)/resumes/new/page.tsx`, `app/(main)/resumes/[id]/variants/[variantId]/edit/page.tsx`, `app/(main)/resumes/[id]/variants/[variantId]/review/page.tsx`. | `docs, plan` | ✅ |
| 11 | **Phase gate -- lint + typecheck + push** | `plan, commands` | ✅ |

---

## Phase 5: components/layout/ and components/persona/

**Status:** ✅ Complete

*Add three-axis JSDoc headers to 4 layout components and 16 persona editor components.
Most have partial JSDoc (what + REQ refs) but lack Layer:/Feature:/Coordinates with:.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS4 |
| 📝 **Add** | Write complete three-axis headers (preserve existing REQ refs) |
| ✅ **Verify** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 12 | **JSDoc -- layout/ + persona/ first half (12 files)** -- Add headers: `layout/app-shell.tsx`, `layout/chat-sidebar.tsx`, `layout/onboarding-gate.tsx`, `layout/top-nav.tsx`, `persona/persona-overview.tsx`, `persona/basic-info-editor.tsx`, `persona/certification-editor.tsx`, `persona/education-editor.tsx`, `persona/skills-editor.tsx`, `persona/work-history-editor.tsx`, `persona/voice-profile-editor.tsx`, `persona/non-negotiables-editor.tsx`. | `docs, plan` | ✅ |
| 13 | **JSDoc -- persona/ second half (8 files)** -- Add headers: `persona/growth-targets-editor.tsx`, `persona/growth-targets-form-fields.tsx`, `persona/achievement-stories-editor.tsx`, `persona/change-flags-banner.tsx`, `persona/change-flags-resolver.tsx`, `persona/discovery-preferences-editor.tsx`, `persona/non-negotiables-form-fields.tsx`, `persona/voice-profile-form-fields.tsx`. | `docs, plan` | ✅ |
| 14 | **Phase gate -- lint + typecheck + push** | `plan, commands` | ✅ |

---

## Phase 6: components/jobs/ and components/dashboard/

**Status:** ✅ Complete

*Add three-axis JSDoc headers to 12 job detail components and 4 dashboard components.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS4 |
| 📝 **Add** | Write complete three-axis headers |
| ✅ **Verify** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | `docs(jsdoc): add file-level headers -- jobs/ and dashboard/` |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 15 | **JSDoc -- jobs/ + dashboard/ (16 files)** -- Add headers: `jobs/cover-letter-section.tsx`, `jobs/create-variant-card.tsx`, `jobs/culture-signals.tsx`, `jobs/draft-materials-card.tsx`, `jobs/extracted-skills-tags.tsx`, `jobs/job-description.tsx`, `jobs/job-detail-actions.tsx`, `jobs/job-detail-header.tsx`, `jobs/mark-as-applied-card.tsx`, `jobs/review-materials-link.tsx`, `jobs/score-breakdown.tsx`, `jobs/score-explanation.tsx`, `dashboard/add-job-modal.tsx`, `dashboard/applications-table.tsx`, `dashboard/dashboard-tabs.tsx`, `dashboard/opportunities-table.tsx`. | `docs, plan` | ✅ |
| 16 | **Phase gate -- lint + typecheck + push** | `plan, commands` | ✅ |

---

## Phase 7: components/resume/ and components/editor/

**Status:** ✅ Complete

*Add three-axis JSDoc headers to 11 resume management components and 8 TipTap editor
components.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS4 |
| 📝 **Add** | Write complete three-axis headers |
| ✅ **Verify** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | `docs(jsdoc): add file-level headers -- resume/ and editor/` |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 17 | **JSDoc -- resume/ + editor/ (19 files)** -- Add headers: `resume/creation-method-buttons.tsx`, `resume/diff-text.tsx`, `resume/export-buttons.tsx`, `resume/guardrail-violation-banner.tsx`, `resume/new-resume-wizard.tsx`, `resume/resume-content-checkboxes.tsx`, `resume/resume-content-view.tsx`, `resume/resume-detail.tsx`, `resume/resume-list.tsx`, `resume/variant-review.tsx`, `resume/variants-list.tsx`, `editor/diff-view.tsx`, `editor/editor-status-bar.tsx`, `editor/editor-toolbar.tsx`, `editor/generation-options-panel.tsx`, `editor/job-requirements-panel.tsx`, `editor/persona-reference-panel.tsx`, `editor/resume-editor.tsx`, `editor/template-picker.tsx`. | `docs, plan` | ✅ |
| 18 | **Phase gate -- lint + typecheck + push** | `plan, commands` | ✅ |

---

## Phase 8: components/chat/ and components/cover-letter/

**Status:** ✅ Complete

*Add three-axis JSDoc headers to 10 chat UI components and 3 cover letter components.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS4 |
| 📝 **Add** | Write complete three-axis headers |
| ✅ **Verify** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | `docs(jsdoc): add file-level headers -- chat/ and cover-letter/` |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 19 | **JSDoc -- chat/ + cover-letter/ (13 files)** -- Add headers: `chat/chat-confirm-card.tsx`, `chat/chat-input.tsx`, `chat/chat-job-card.tsx`, `chat/chat-message-list.tsx`, `chat/chat-option-list.tsx`, `chat/chat-score-card.tsx`, `chat/message-bubble.tsx`, `chat/streaming-cursor.tsx`, `chat/tool-execution-badge.tsx`, `chat/typing-indicator.tsx`, `cover-letter/cover-letter-review.tsx`, `cover-letter/regeneration-feedback-modal.tsx`, `cover-letter/story-override-modal.tsx`. | `docs, plan` | ✅ |
| 20 | **Phase gate -- lint + typecheck + push** | `plan, commands` | ✅ |

---

## Phase 9: components/applications/ and components/usage/

**Status:** ✅ Complete

*Add three-axis JSDoc headers to 12 application tracking components and 8 usage/billing
components.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS4 |
| 📝 **Add** | Write complete three-axis headers |
| ✅ **Verify** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | `docs(jsdoc): add file-level headers -- applications/ and usage/` |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 21 | **JSDoc -- applications/ + usage/ (20 files)** -- Add headers: `applications/add-timeline-event-dialog.tsx`, `applications/application-columns.tsx`, `applications/application-detail.tsx`, `applications/application-timeline.tsx`, `applications/applications-list.tsx`, `applications/interview-stage-dialog.tsx`, `applications/job-snapshot-section.tsx`, `applications/offer-details-card.tsx`, `applications/offer-details-dialog.tsx`, `applications/rejection-details-card.tsx`, `applications/rejection-details-dialog.tsx`, `applications/status-transition-dropdown.tsx`, `usage/balance-card.tsx`, `usage/funding-packs.tsx`, `usage/low-balance-warning.tsx`, `usage/purchase-table.tsx`, `usage/transaction-table.tsx`, `usage/usage-page.tsx`, `usage/usage-summary.tsx`, `usage/usage-table.tsx`. | `docs, plan` | ✅ |
| 22 | **Phase gate -- lint + typecheck + push** | `plan, commands` | ✅ |

---

## Phase 10: components/settings/, admin/, form/, data-table/

**Status:** ✅ Complete

*Add three-axis JSDoc headers to 4 settings components, 12 admin components, 8 form
helpers, and 7 data-table components.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS4 |
| 📝 **Add** | Write complete three-axis headers |
| ✅ **Verify** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 23 | **JSDoc -- settings/ + admin/ (16 files)** -- Add headers: `settings/account-section.tsx`, `settings/agent-configuration-section.tsx`, `settings/job-sources-section.tsx`, `settings/settings-page.tsx`, `admin/add-model-dialog.tsx`, `admin/add-pack-dialog.tsx`, `admin/add-pricing-dialog.tsx`, `admin/admin-config-page.tsx`, `admin/constants.ts`, `admin/models-tab.tsx`, `admin/packs-tab.tsx`, `admin/pricing-tab.tsx`, `admin/routing-tab.tsx`, `admin/routing-test-cell.tsx`, `admin/system-tab.tsx`, `admin/users-tab.tsx`. | `docs, plan` | ✅ |
| 24 | **JSDoc -- form/ + data-table/ (15 files)** -- Add headers: `form/form-action-footer.tsx`, `form/form-error-summary.tsx`, `form/form-input-field.tsx`, `form/form-select-field.tsx`, `form/form-tag-field.tsx`, `form/form-textarea-field.tsx`, `form/index.ts`, `form/submit-button.tsx`, `data-table/data-table.tsx`, `data-table/data-table-column-header.tsx`, `data-table/data-table-pagination.tsx`, `data-table/data-table-select-column.tsx`, `data-table/data-table-toolbar.tsx`, `data-table/index.ts`, `data-table/toolbar-select.tsx`. | `docs, plan` | ✅ |
| 25 | **Phase gate -- lint + typecheck + push** | `plan, commands` | ✅ |

---

## Phase 11: components/onboarding/, ghostwriter/, ui/ Non-Trivial

**Status:** ✅ Complete

*Add three-axis JSDoc headers to 31 onboarding components (including steps/), 1
ghostwriter component, and ~15 non-trivial ui/ components. For ui/ files: read each
before deciding to skip -- thin Radix wrappers (button, input, card, etc.) are skipped;
files with custom logic (connection-status, score-tier-badge, pdf-viewer, etc.) need
headers.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS3 (scope exclusions for ui/) + SS4 |
| 📝 **Add** | Write complete three-axis headers |
| ✅ **Verify** | Three-axis pass/fail test on each file; verify ui/ skip decisions |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 26 | **JSDoc -- onboarding/ main + steps/ first batch (16 files)** -- Add headers: `onboarding/onboarding-shell.tsx`, `onboarding/onboarding-steps.ts`, `onboarding/steps/crud-step-layout.tsx`, `onboarding/steps/basic-info-step.tsx`, `onboarding/steps/work-history-card.tsx`, `onboarding/steps/work-history-form.tsx`, `onboarding/steps/work-history-step.tsx`, `onboarding/steps/certification-card.tsx`, `onboarding/steps/certification-form.tsx`, `onboarding/steps/certification-step.tsx`, `onboarding/steps/education-card.tsx`, `onboarding/steps/education-form.tsx`, `onboarding/steps/education-step.tsx`, `onboarding/steps/skills-card.tsx`, `onboarding/steps/skills-form.tsx`, `onboarding/steps/skills-step.tsx`. | `docs, plan` | ✅ |
| 27 | **JSDoc -- onboarding/steps/ second batch (15 files)** -- Add headers: `onboarding/steps/story-card.tsx`, `onboarding/steps/story-form.tsx`, `onboarding/steps/story-step.tsx`, `onboarding/steps/non-negotiables-step.tsx`, `onboarding/steps/growth-targets-step.tsx`, `onboarding/steps/voice-profile-step.tsx`, `onboarding/steps/custom-filter-card.tsx`, `onboarding/steps/custom-filter-form.tsx`, `onboarding/steps/custom-filters-section.tsx`, `onboarding/steps/bullet-editor.tsx`, `onboarding/steps/bullet-form.tsx`, `onboarding/steps/bullet-item.tsx`, `onboarding/steps/resume-upload-step.tsx`, `onboarding/steps/base-resume-setup-step.tsx`, `onboarding/steps/review-step.tsx`. | `docs, plan` | ✅ |
| 28 | **JSDoc -- ghostwriter/ + ui/ non-trivial (~16 files)** -- Add headers: `ghostwriter/ghostwriter-review.tsx`. Then audit each `ui/` file: skip thin Radix wrappers (dialog, radio-group, textarea, skeleton, select, switch, checkbox, tooltip, card, tabs, input, label, button, table -- verify each); add headers to files with custom logic: `ui/connection-status.tsx`, `ui/score-tier-badge.tsx`, `ui/pdf-viewer.tsx`, `ui/reorderable-list.tsx`, `ui/agent-reasoning.tsx`, `ui/delete-reference-dialog.tsx`, `ui/confirmation-dialog.tsx`, `ui/error-states.tsx`, `ui/status-badge.tsx`, `ui/form-alert-dialog.tsx`, `ui/sonner.tsx`, `ui/form.tsx`, `ui/table-pagination.tsx`, `ui/sheet.tsx`, `ui/progress.tsx`. | `docs, plan` | ✅ |
| 29 | **Phase gate -- lint + typecheck + push** | `plan, commands` | ✅ |

---

## Phase 12: Backend core/ + app root

**Status:** ⬜ Incomplete

*Add `Coordinates with:` and `Called by:` sections to 18 core infrastructure files.
These files (config, database, auth, errors, etc.) are imported by nearly every backend
module -- accurate headers here make all subsequent backend phases faster to trace.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS2.2 (Python docstring template) |
| 📝 **Add** | Append `Coordinates with:` and `Called by:` sections to existing docstrings |
| ✅ **Verify** | Three-axis pass/fail test (what/where/with) on each file |
| 🔍 **Review** | `code-reviewer` (verify module paths reference real files) |
| 📝 **Commit** | `docs(docstring): add coordination headers -- core/ + app root` |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 30 | **Docstrings -- core/ + app root (18 files)** -- Add Coordinates-with/Called-by: `app/main.py`, `core/config.py`, `core/database.py`, `core/errors.py`, `core/auth.py`, `core/account_linking.py`, `core/email.py`, `core/file_validation.py`, `core/filtering.py`, `core/llm_sanitization.py`, `core/null_byte_middleware.py`, `core/oauth.py`, `core/oauth_client.py`, `core/pagination.py`, `core/rate_limiting.py`, `core/responses.py`, `core/stripe_client.py`, `core/tenant_session.py`. Use Explore subagent to trace import/export graphs. | `docs, plan` | ⬜ |
| 31 | **Phase gate -- ruff + pyright + push** | `plan, commands` | ⬜ |

---

## Phase 13: Backend models/ + schemas/

**Status:** ⬜ Incomplete

*Add `Coordinates with:` and `Called by:` sections to 19 SQLAlchemy model files and
10 Pydantic schema files. Models define the data layer; schemas define API contracts.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS2.2 |
| 📝 **Add** | Append `Coordinates with:` and `Called by:` sections to existing docstrings |
| ✅ **Verify** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 32 | **Docstrings -- models/ (19 files)** -- Add Coordinates-with/Called-by: `models/account.py`, `models/admin_config.py`, `models/application.py`, `models/base.py`, `models/cover_letter.py`, `models/job_posting.py`, `models/job_source.py`, `models/persona.py`, `models/persona_content.py`, `models/persona_job.py`, `models/persona_settings.py`, `models/resume.py`, `models/resume_template.py`, `models/session.py`, `models/stripe.py`, `models/usage.py`, `models/usage_reservation.py`, `models/user.py`, `models/verification_token.py`. | `docs, plan` | ⬜ |
| 33 | **Docstrings -- schemas/ (10 files)** -- Add Coordinates-with/Called-by: `schemas/admin.py`, `schemas/bulk.py`, `schemas/chat.py`, `schemas/credits.py`, `schemas/ingest.py`, `schemas/job_posting.py`, `schemas/prompt_params.py`, `schemas/resume.py`, `schemas/resume_template.py`, `schemas/usage.py`. | `docs, plan` | ⬜ |
| 34 | **Phase gate -- ruff + pyright + push** | `plan, commands` | ⬜ |

---

## Phase 14: Backend repositories/ + api/

**Status:** ⬜ Incomplete

*Add `Coordinates with:` and `Called by:` sections to 10 repository files and 23 API
router files. Repositories handle DB access; API routers define the HTTP layer.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS2.2 |
| 📝 **Add** | Append `Coordinates with:` and `Called by:` sections to existing docstrings |
| ✅ **Verify** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 35 | **Docstrings -- repositories/ + api/deps (11 files)** -- Add Coordinates-with/Called-by: `repositories/account_repository.py`, `repositories/credit_repository.py`, `repositories/job_pool_repository.py`, `repositories/job_posting_repository.py`, `repositories/persona_job_repository.py`, `repositories/resume_template_repository.py`, `repositories/stripe_repository.py`, `repositories/usage_repository.py`, `repositories/user_repository.py`, `repositories/verification_token_repository.py`, `api/deps.py`. | `docs, plan` | ⬜ |
| 36 | **Docstrings -- api/v1/ first half (12 files)** -- Add Coordinates-with/Called-by: `api/v1/router.py`, `api/v1/admin.py`, `api/v1/applications.py`, `api/v1/auth.py`, `api/v1/auth_magic_link.py`, `api/v1/auth_oauth.py`, `api/v1/base_resumes.py`, `api/v1/chat.py`, `api/v1/cover_letters.py`, `api/v1/credits.py`, `api/v1/files.py`, `api/v1/job_postings.py`. | `docs, plan` | ⬜ |
| 37 | **Docstrings -- api/v1/ second half (10 files)** -- Add Coordinates-with/Called-by: `api/v1/job_sources.py`, `api/v1/job_variants.py`, `api/v1/onboarding.py`, `api/v1/persona_change_flags.py`, `api/v1/personas.py`, `api/v1/refresh.py`, `api/v1/resume_templates.py`, `api/v1/usage.py`, `api/v1/user_source_preferences.py`, `api/v1/webhooks.py`. | `docs, plan` | ⬜ |
| 38 | **Phase gate -- ruff + pyright + push** | `plan, commands` | ⬜ |

---

## Phase 15: Backend providers/ + adapters/ + agents/ + prompts/ + scripts/

**Status:** ⬜ Incomplete

*Add `Coordinates with:` and `Called by:` sections to LLM provider adapters (15 files),
external source adapters (5 files), agent infrastructure (3 files), prompt templates
(3 files), and utility scripts (2 files).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS2.2 |
| 📝 **Add** | Append `Coordinates with:` and `Called by:` sections to existing docstrings |
| ✅ **Verify** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 39 | **Docstrings -- providers/ (15 files)** -- Add Coordinates-with/Called-by: `providers/config.py`, `providers/errors.py`, `providers/factory.py`, `providers/gemini_errors.py`, `providers/metered_provider.py`, `providers/retry.py`, `providers/llm/base.py`, `providers/llm/claude_adapter.py`, `providers/llm/gemini_adapter.py`, `providers/llm/mock_adapter.py`, `providers/llm/openai_adapter.py`, `providers/embedding/base.py`, `providers/embedding/gemini_adapter.py`, `providers/embedding/mock_adapter.py`, `providers/embedding/openai_adapter.py`. | `docs, plan` | ⬜ |
| 40 | **Docstrings -- adapters/ + agents/ + prompts/ + scripts/ (13 files)** -- Add Coordinates-with/Called-by: `adapters/sources/base.py`, `adapters/sources/adzuna.py`, `adapters/sources/remoteok.py`, `adapters/sources/themuse.py`, `adapters/sources/usajobs.py`, `agents/chat.py`, `agents/checkpoint.py`, `agents/state.py`, `prompts/ghostwriter.py`, `prompts/resume_generation.py`, `prompts/strategist.py`, `scripts/dedup_cross_persona.py`, `scripts/reembed_all.py`. | `docs, plan` | ⬜ |
| 41 | **Phase gate -- ruff + pyright + push** | `plan, commands` | ⬜ |

---

## Phase 16: Backend services/ — Verify/Update Existing

**Status:** ⬜ Incomplete

*Verify and update `Coordinates with:` / `Called by:` sections on ~86 service files.
These were standardized during REQ-031 but may have drifted or have inaccurate paths.
This is lighter-weight work than previous phases -- read each docstring, verify paths
still exist, update if needed. Larger batches are acceptable.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-032 SS2.2 + REQ-031 (original service docstring standard) |
| 🔍 **Verify** | Read each file's existing docstring; grep to verify named paths exist |
| 📝 **Update** | Fix stale paths, add missing Coordinates-with/Called-by if absent |
| ✅ **Check** | Three-axis pass/fail test on each file |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| SS | Task | Hints | Status |
|---|------|-------|--------|
| 42 | **Verify -- services/ top-level + scoring/ + embedding/ (30 files)** -- Verify/update: `services/agent_handoff.py`, `services/agent_message.py`, `services/application_workflow.py`, `services/ingest_token_store.py`, `services/persona_sync.py`, `services/retention_cleanup.py` (6 top-level) + `services/scoring/` (17 files: batch_scoring, experience_level, explanation_generation, fit_score, golden_set, hard_skills_match, job_scoring_service, location_logistics, non_negotiables_filter, pool_scoring, role_title_match, score_correlation, score_explanation, score_types, scoring_flow, soft_skills_match, stretch_score) + `services/embedding/` (7 files: cache, cost, job_generator, persona_generator, storage, types, utils). | `docs, plan` | ⬜ |
| 43 | **Verify -- services/generation/ (24 files)** -- Verify/update all 24 files: base_resume_selection, bullet_reordering, content_generation_service, content_utils, cover_letter_generation, cover_letter_output, cover_letter_structure, cover_letter_validation, data_availability, duplicate_story, generation_outcome, ghostwriter_triggers, job_expiry, modification_limits, persona_change, quality_metrics, reasoning_explanation, regeneration, resume_generation_service, resume_tailoring_service, story_selection, tailoring_decision, voice_prompt_block, voice_validation. | `docs, plan` | ⬜ |
| 44 | **Verify -- services/rendering/ + discovery/ + billing/ + admin/ + onboarding/ (32 files)** -- Verify/update: `services/rendering/` (8 files: cover_letter_editing, cover_letter_pdf_generation, cover_letter_pdf_storage, markdown_docx_renderer, markdown_pdf_renderer, pdf_generation, resume_parsing_service, resume_template_service) + `services/discovery/` (16 files: content_security, discovery_workflow, expiration_detection, ghost_detection, global_dedup_service, job_deduplication, job_enrichment_service, job_extraction, job_fetch_service, job_status, pool_surfacing_service, pool_surfacing_worker, scouter_errors, scouter_utils, source_selection, user_review) + `services/billing/` (4 files) + `services/admin/` (2 files) + `services/onboarding/` (2 files). | `docs, plan` | ⬜ |
| 45 | **Phase gate -- ruff + pyright + push** | `plan, commands` | ⬜ |

---

## Task Count Summary

| | Phase | Description | Subtasks | Gate | Total |
|-|-------|-------------|----------|------|-------|
| **Frontend** | | | | | |
| | Phase 1 | lib/ core infrastructure (15 files) | 1 | 1 | 2 |
| | Phase 2 | lib/ helpers and formatters (19 files) | 1 | 1 | 2 |
| | Phase 3 | types/ + hooks/ (24 files) | 2 | 1 | 3 |
| | Phase 4 | app/ pages and layouts (~38 files) | 3 | 1 | 4 |
| | Phase 5 | components/layout/ + persona/ (20 files) | 2 | 1 | 3 |
| | Phase 6 | components/jobs/ + dashboard/ (16 files) | 1 | 1 | 2 |
| | Phase 7 | components/resume/ + editor/ (19 files) | 1 | 1 | 2 |
| | Phase 8 | components/chat/ + cover-letter/ (13 files) | 1 | 1 | 2 |
| | Phase 9 | components/applications/ + usage/ (20 files) | 1 | 1 | 2 |
| | Phase 10 | components/settings/ + admin/ + form/ + data-table/ (31 files) | 2 | 1 | 3 |
| | Phase 11 | components/onboarding/ + ghostwriter/ + ui/ non-trivial (~47 files) | 3 | 1 | 4 |
| | *Subtotal* | *~262 frontend files* | *18* | *11* | *29* |
| **Backend** | | | | | |
| | Phase 12 | core/ + app root (18 files) | 1 | 1 | 2 |
| | Phase 13 | models/ + schemas/ (29 files) | 2 | 1 | 3 |
| | Phase 14 | repositories/ + api/ (33 files) | 3 | 1 | 4 |
| | Phase 15 | providers/ + adapters/ + agents/ + prompts/ + scripts/ (28 files) | 2 | 1 | 3 |
| | Phase 16 | services/ verify/update (86 files) | 3 | 1 | 4 |
| | *Subtotal* | *~194 backend files* | *11* | *5* | *16* |
| **Grand Total** | | **~456 in-scope files** | **29** | **16** | **45** |

---

## Critical Files Reference

| File | Role in Plan |
|------|-------------|
| `docs/requirements/REQ-032.md` | Authoritative spec -- scope, standard, DoD |
| `.claude/skills/zentropy-docs/SKILL.md` | Three-axis JSDoc template and pass/fail test (frontend) |
| `frontend/src/lib/api-client.ts` | Example of existing `@module`/`@coordinates-with` format (Phase 1 reformat) |
| `frontend/src/components/persona/persona-overview.tsx` | Example of existing partial JSDoc (Phase 5+ add headers) |
| `backend/app/services/scoring/fit_score.py` | Example of existing Coordinates-with/Called-by format (Phase 16 verify) |
| `backend/app/api/v1/applications.py` | Example of existing docstring without Coordinates-with (Phase 14 add) |
| `docs/plan/frontend_jsdoc_import_hygiene_plan.md` | Previous plan (v0.1, complete) -- reference only |

---

## Notes

### Frontend (Phases 1-11)
- **Phases 1-3 reformat existing headers.** These files already have `@module` + `@coordinates-with` JSDoc tags from the v0.1 plan. The work is converting them to the zentropy-docs template format (`@fileoverview`, `Layer:`, `Feature:`, `Coordinates with:` as bullet list, `Called by / Used by:`). Preserve existing content -- don't lose REQ references or coordination details.
- **Phases 4-11 add new headers.** Most of these files have minimal or no JSDoc. Write complete three-axis headers from scratch.
- **ui/ skip decisions must be verified.** Read each ui/ file before deciding to skip. Files like `connection-status.tsx`, `score-tier-badge.tsx`, `pdf-viewer.tsx` have significant custom logic beyond Radix wrapping.

### Backend (Phases 12-16)
- **Phases 12-15 add Coordinates-with/Called-by to existing docstrings.** These files already have Google-style docstrings with REQ references (what + where axes). The work is adding the `Coordinates with:` and `Called by:` sections (with axis). Preserve existing docstring content.
- **Phase 16 verifies existing headers.** Service files already have Coordinates-with/Called-by from REQ-031. Read each docstring, verify named paths still exist, update stale references. Larger batches (20-30 files) are acceptable since this is verification, not writing from scratch.
- **Skip empty `__init__.py` files.** Only include `__init__.py` files that have actual logic or meaningful re-exports.
- **Skip migration files.** Alembic migrations are auto-generated and don't benefit from coordination headers.

### Shared
- **Use Explore subagent for tracing.** For each subtask batch, use the Explore subagent to trace import/export relationships rather than manually grepping file by file. This is faster for volume work.
- **Coordinates with: entries must name actual paths.** Not generic descriptions. Verify each path exists before committing.
- **Called by / Used by: direction clarifies purpose.** If a file's purpose is ambiguous after reading it, trace its callers first -- the Called by direction often clarifies the summary more than the file body does.
- **No security triage gates.** No functional code changes means no new attack surface.
- **Commit message format:** `docs(jsdoc): add file-level headers -- [directory]` (frontend) / `docs(docstring): add coordination headers -- [directory]` (backend)
- **For docs-only pushes:** `git push --no-verify` is acceptable to skip pre-push hooks (pytest/vitest) since no code changes exist.

---

## Change Log

| Date | Change |
|------|--------|
| 2026-03-31 | Initial plan created (frontend only, 11 phases, 29 tasks) |
| 2026-03-31 | Added backend phases 12-16 (5 phases, 16 tasks). Total: 16 phases, 45 tasks |
