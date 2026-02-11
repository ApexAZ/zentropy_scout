# Zentropy Scout — Frontend Implementation Plan

**Created:** 2026-02-08
**Last Updated:** 2026-02-08
**Status:** Ready for Implementation

---

## Context

All backend implementation is complete (Phases 0–3.2). REQ-012 (Frontend Application) is written and approved. No frontend code exists yet — the `frontend/` directory needs to be created from scratch.

This plan breaks REQ-012 into atomic implementation tasks. Each task is sized to complete within ~100k tokens (including reading requirements, writing tests, implementing, and reviewing).

**Spec:** `docs/requirements/REQ-012_frontend_application.md`
**Surface area reference:** `docs/plan/frontend_surface_area.md`

---

## How to Use This Document

**Tracking:** Each task has a status (⬜/🟡/✅). Find the first 🟡 or ⬜ when resuming.

**Context Management:** Load ONLY the REQ-012 section referenced in each task. Each task = one unit of work = one commit.

**Order:** Phases are sequential. Complete each phase before starting the next.

**Testing:** Frontend uses Vitest (unit/component) + Playwright (E2E). TDD applies — write tests before implementation.

---

## Phase 0: Backend Prerequisites

**Status:** ✅ Complete

*Resolve backend gaps from REQ-012 Appendix A before dependent frontend phases.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-012 Appendix A and relevant backend REQ doc |
| 🧪 **TDD** | Write migration/endpoint tests first — follow `zentropy-tdd` |
| 🗃️ **Patterns** | Use `zentropy-db` for migration, `zentropy-api` for endpoint changes |
| ✅ **Verify** | `pytest -v`, `alembic upgrade head`, `alembic downgrade -1` |
| 🔍 **Review** | Use `code-reviewer` agent |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| A.1 | Add `is_pinned` and `archived_at` columns to `applications` table | `db, tdd, plan` | ✅ |
| A.2 | Remove or disable timeline event PATCH/DELETE stubs (return 405) | `api, tdd, plan` | ✅ |
| A.3 | Add `score_details` JSONB column to `job_postings` and store during scoring | `db, api, tdd, plan` | ✅ |

---

## Phase 1: Project Scaffold

**Status:** ✅ Complete

*Creates Next.js project, installs dependencies, configures tooling. REQ-012 §4.1.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-012 §4.1 for tech stack |
| 📂 **Create** | Create files per project structure |
| ▶️ **Commands** | Run setup commands (npx, npm install, etc.) |
| ✅ **Verify** | Dev server starts, linting passes, tests run |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1.1 | Initialize Next.js 14+ App Router project in `frontend/` with TypeScript | `structure, commands, plan` | ✅ |
| 1.2 | Configure Tailwind CSS 3.x with base design tokens (REQ-012 §13.1) | `structure, commands, plan` | ✅ |
| 1.3 | Initialize shadcn/ui and install base components (Button, Card, Input, Dialog, Select, Tabs) | `structure, commands, plan` | ✅ |
| 1.4 | Configure ESLint + Prettier for TypeScript/React | `lint, commands, plan` | ✅ |
| 1.5 | Configure Vitest for unit/component testing with React Testing Library | `test, commands, plan` | ✅ |
| 1.6 | Configure Playwright for E2E testing | `playwright, commands, plan` | ✅ |
| 1.7 | Create frontend `.env.example` with `NEXT_PUBLIC_API_URL` | `commands, plan` | ✅ |
| 1.8 | Update `.pre-commit-config.yaml` to add frontend lint hooks | `lint, git, plan` | ✅ |

---

## Phase 2: Foundation

**Status:** ✅ Complete

*Types, API client, SSE client, query configuration, layout shell. REQ-012 §4.2–4.4, §3.2–3.3.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-012 §4 for architecture spec |
| 🧪 **TDD** | Write Vitest tests first — follow `zentropy-tdd` |
| 📂 **Structure** | Place in `frontend/src/lib/`, `frontend/src/types/`, `frontend/src/hooks/` |
| ✅ **Verify** | `npm run test`, `npm run lint`, `npm run typecheck` |
| 🔍 **Review** | Use `code-reviewer` agent |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 2.1 | Create shared TypeScript types: API envelope, pagination, error shapes, SSE events | `tdd, structure, plan` | ✅ |
| 2.2 | Create Persona domain types (BasicInfo, WorkHistory, Skills, Stories, Voice, NonNegotiables, etc.) | `tdd, structure, plan` | ✅ |
| 2.3 | Create Job domain types (JobPosting, FitScore, StretchScore, ScoreExplanation, GhostDetection) | `tdd, structure, plan` | ✅ |
| 2.4 | Create Resume domain types (BaseResume, JobVariant, ResumeFile, GuardrailResult) | `tdd, structure, plan` | ✅ |
| 2.5 | Create Application & CoverLetter domain types (Application, TimelineEvent, OfferDetails, CoverLetter, ValidationResult) | `tdd, structure, plan` | ✅ |
| 2.6 | Create typed API client with fetch wrapper and response envelope parsing (REQ-012 §4.3) | `tdd, structure, plan` | ✅ |
| 2.7 | Create TanStack Query provider and query key factory (REQ-012 §4.2.1) | `tdd, structure, plan` | ✅ |
| 2.8 | Create SSE client wrapper with reconnection logic and tab visibility detection (REQ-012 §4.4) | `tdd, structure, plan` | ✅ |
| 2.9 | Create SSE-to-TanStack-Query bridge — `data_changed` events invalidate queries (REQ-012 §4.2.1) | `tdd, structure, plan` | ✅ |
| 2.10 | Create root layout with providers (QueryClientProvider, SSEProvider) and CSS | `structure, plan` | ✅ |
| 2.11 | Create app shell: top nav bar, page content area, chat sidebar slot (REQ-012 §3.2) | `tdd, structure, plan` | ✅ |
| 2.12 | Create onboarding gate: check persona status, redirect to `/onboarding` if needed (REQ-012 §3.3) | `tdd, structure, plan` | ✅ |

---

## Phase 3: Shared Components & Design System

**Status:** ⬜ Incomplete

*Reusable components used by all page phases. REQ-012 §13.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-012 §13 for component spec |
| 🧪 **TDD** | Write Vitest component tests first — follow `zentropy-tdd` |
| 📂 **Structure** | Place in `frontend/src/components/` |
| ✅ **Verify** | `npm run test`, `npm run lint`, `npm run typecheck` |
| 🔍 **Review** | Use `code-reviewer` agent |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 3.1 | Create form field components with React Hook Form + inline Zod error display (REQ-012 §13.2) | `tdd, structure, plan` | ✅ |
| 3.2 | Create tag/chip input component for JSONB string arrays (skills, cities, exclusions) | `tdd, structure, plan` | ✅ |
| 3.3 | Create DataTable — basic table with column definitions, row click, and responsive card fallback (REQ-012 §13.3) | `tdd, structure, plan` | ✅ |
| 3.4 | Create DataTable — sorting, column filters, and toolbar search (REQ-012 §13.3) | `tdd, structure, plan` | ✅ |
| 3.5 | Create DataTable — pagination with page size selector (20/50/100) (REQ-012 §13.3) | `tdd, structure, plan` | ✅ |
| 3.6 | Create DataTable — multi-select mode with checkbox column and bulk action toolbar (REQ-012 §13.3) | `tdd, structure, plan` | ✅ |
| 3.7 | Create toast notification system (success/error/warning/info) with ARIA live region (REQ-012 §13.5) | `tdd, structure, plan` | ✅ |
| 3.8 | Create skeleton loading components for page layouts (REQ-012 §13.6) | `tdd, structure, plan` | ✅ |
| 3.9 | Create error state components: empty, failed, not found, conflict (REQ-012 §13.7) | `tdd, structure, plan` | ✅ |
| 3.10 | Create PDF viewer component with iframe embed, zoom, download, fullscreen (REQ-012 §13.4) | `tdd, structure, plan` | ✅ |
| 3.11 | Create drag-and-drop reorder component with mobile up/down arrow fallback (REQ-012 §7.4) | `tdd, structure, plan` | ✅ |
| 3.12 | Create confirmation dialog with destructive variant (REQ-012 §7.5) | `tdd, structure, plan` | ⬜ |
| 3.13 | Create connection status indicator (connected/reconnecting/disconnected) (REQ-012 §5.5) | `tdd, structure, plan` | ⬜ |
| 3.14 | Create score tier badge component (numeric + label + color) for Fit and Stretch (REQ-012 §8.4) | `tdd, structure, plan` | ⬜ |
| 3.15 | Create status badge component with color-coded variants (Application statuses, Draft/Approved, etc.) | `tdd, structure, plan` | ⬜ |

---

## Phase 4: Chat Interface

**Status:** ⬜ Incomplete

*Persistent chat panel with SSE streaming. Cross-cutting — used by all pages. REQ-012 §5.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-012 §5 for chat spec |
| 🧪 **TDD** | Write Vitest component tests first — follow `zentropy-tdd` |
| 📂 **Structure** | Place in `frontend/src/components/chat/` and `frontend/src/hooks/` |
| ✅ **Verify** | `npm run test`, `npm run lint`, `npm run typecheck` |
| 🔍 **Review** | Use `code-reviewer` + `security-reviewer` agents |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 4.1 | Create chat panel layout: collapsible sidebar (desktop), drawer (mobile) (REQ-012 §5.1) | `tdd, structure, plan` | ⬜ |
| 4.2 | Create chat context provider: panel open/close, message list state, SSE connection ref | `tdd, structure, plan` | ⬜ |
| 4.3 | Create message bubble components: user (right), agent text (left), system notice (center) (REQ-012 §5.2) | `tdd, structure, plan` | ⬜ |
| 4.4 | Create streaming display: token-by-token append with blinking cursor (REQ-012 §5.4) | `tdd, structure, plan` | ⬜ |
| 4.5 | Create tool execution badge: spinner on tool_start → icon on tool_result (REQ-012 §5.4) | `tdd, structure, plan` | ⬜ |
| 4.6 | Create structured chat cards: job card, score summary card (REQ-012 §5.3) | `tdd, structure, plan` | ⬜ |
| 4.7 | Create ambiguity resolution UI: clickable option list, destructive confirm card (REQ-012 §5.6) | `tdd, structure, plan` | ⬜ |
| 4.8 | Create chat input: textarea, send button, Enter/Shift+Enter, disabled during streaming (REQ-012 §5.7) | `tdd, structure, plan` | ⬜ |
| 4.9 | Create chat history loading: REST fetch on mount, scroll-to-bottom, "Jump to latest" (REQ-012 §5.8) | `tdd, structure, plan` | ⬜ |

---

## Phase 5: Onboarding Flow

**Status:** ⬜ Incomplete

*12-step persona wizard. First user experience. REQ-012 §6. Depends on Chat (Phase 4) for conversational steps.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-012 §6 (specific step subsection) |
| 🧪 **TDD** | Write Vitest component tests first — follow `zentropy-tdd` |
| 📂 **Structure** | Place in `frontend/src/app/onboarding/` |
| 🌐 **API** | Use typed API client and TanStack Query hooks from Phase 2 |
| ✅ **Verify** | `npm run test`, `npm run lint`, `npm run typecheck` |
| 🔍 **Review** | Use `code-reviewer` agent |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 5.1 | Create onboarding layout: full-screen (no nav), progress bar, back/skip/next buttons (REQ-012 §6.2) | `tdd, structure, plan` | ⬜ |
| 5.2 | Create onboarding state management: current step, persisted step data, checkpoint resume (REQ-012 §6.4) | `tdd, structure, plan` | ⬜ |
| 5.3 | Step 1 — Resume upload: drag-drop, file validation, progress bar, skip option (REQ-012 §6.3.1) | `tdd, structure, plan` | ⬜ |
| 5.4 | Step 2 — Basic info form: 7 text fields with pre-fill from resume extraction (REQ-012 §6.3.2) | `tdd, structure, plan` | ⬜ |
| 5.5 | Step 3a — Work history: job card list with add/edit/delete and ordering (REQ-012 §6.3.3) | `tdd, structure, plan` | ⬜ |
| 5.6 | Step 3b — Bullet editor: nested bullet list within each job card with add/edit/reorder (REQ-012 §6.3.3) | `tdd, structure, plan` | ⬜ |
| 5.7 | Step 4 — Education form with skip option (REQ-012 §6.3.4) | `tdd, structure, plan` | ⬜ |
| 5.8 | Step 5 — Skills editor: chip list with proficiency selector and category dropdown (REQ-012 §6.3.5) | `tdd, structure, plan` | ⬜ |
| 5.9 | Step 6 — Certifications form with skip option and "Does not expire" toggle (REQ-012 §6.3.6) | `tdd, structure, plan` | ⬜ |
| 5.10 | Step 7 — Achievement stories: conversational capture (C/A/O) with review cards (REQ-012 §6.3.7) | `tdd, structure, plan` | ⬜ |
| 5.11 | Step 8a — Non-negotiables: location preferences section (REQ-012 §6.3.8) | `tdd, structure, plan` | ⬜ |
| 5.12 | Step 8b — Non-negotiables: compensation and work model sections (REQ-012 §6.3.8) | `tdd, structure, plan` | ⬜ |
| 5.13 | Step 8c — Non-negotiables: custom filters CRUD (add/edit/delete user-defined filters) (REQ-012 §6.3.8) | `tdd, structure, plan` | ⬜ |
| 5.14 | Step 9 — Growth targets: tag inputs for target roles/skills, stretch appetite radio (REQ-012 §6.3.9) | `tdd, structure, plan` | ⬜ |
| 5.15 | Step 10 — Voice profile: agent-derived review card with inline editing (REQ-012 §6.3.10) | `tdd, structure, plan` | ⬜ |
| 5.16 | Step 11 — Review: collapsible sections for all persona areas with edit links (REQ-012 §6.3.11) | `tdd, structure, plan` | ⬜ |
| 5.17 | Step 12 — Base resume setup: item selection checkboxes and PDF preview (REQ-012 §6.3.12) | `tdd, structure, plan` | ⬜ |
| 5.18 | Onboarding completion: mark `onboarding_complete`, trigger Scouter, redirect to dashboard (REQ-012 §6.5) | `tdd, structure, plan` | ⬜ |

---

## Phase 6: Persona Management

**Status:** ⬜ Incomplete

*Post-onboarding persona editing. Section editors, deletion flow, change flags. REQ-012 §7. Reuses form components from Phase 5.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-012 §7 (specific subsection) |
| 🧪 **TDD** | Write Vitest component tests first — follow `zentropy-tdd` |
| 📂 **Structure** | Place in `frontend/src/app/persona/` |
| 🌐 **API** | Use typed API client and TanStack Query hooks |
| ✅ **Verify** | `npm run test`, `npm run lint`, `npm run typecheck` |
| 🔍 **Review** | Use `code-reviewer` agent |
| 📝 **Commit** | Follow `zentropy-git` |

#### Phase 6 Notes
Many section editors reuse form components from Phase 5 (onboarding). Extract shared form components into `frontend/src/components/persona/` during this phase if not already done.

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 6.1 | Create persona overview page: section summary cards with edit links (REQ-012 §7.1) | `tdd, structure, plan` | ⬜ |
| 6.2 | Create PersonaChangeFlags banner with pending action count (REQ-012 §7.6) | `tdd, structure, plan` | ⬜ |
| 6.3 | Create basic info editor: two-column form with URL validation (REQ-012 §7.2.1) | `tdd, structure, plan` | ⬜ |
| 6.4 | Create work history editor: reorderable job cards with drag-drop (REQ-012 §7.2.2) | `tdd, structure, plan` | ⬜ |
| 6.5 | Create work history bullet editor: nested bullet list with add/edit/reorder per job (REQ-012 §7.2.2) | `tdd, structure, plan` | ⬜ |
| 6.6 | Create education and certifications editors (REQ-012 §7.2.3) | `tdd, structure, plan` | ⬜ |
| 6.7 | Create skills editor: Hard/Soft tabs, 6-field skill cards, category switching (REQ-012 §7.2.4) | `tdd, structure, plan` | ⬜ |
| 6.8 | Create achievement stories editor: C/A/O expand, skill links (REQ-012 §7.2.5) | `tdd, structure, plan` | ⬜ |
| 6.9 | Create voice profile editor: text fields + tag inputs for phrases and avoid-list (REQ-012 §7.2.6) | `tdd, structure, plan` | ⬜ |
| 6.10 | Create non-negotiables editor: conditional fields, custom filter CRUD (REQ-012 §7.2.7, §7.3) | `tdd, structure, plan` | ⬜ |
| 6.11 | Create growth targets and discovery preferences editors with validation (REQ-012 §7.2.8-9) | `tdd, structure, plan` | ⬜ |
| 6.12 | Create deletion handling: reference check, three-option dialog, immutable block (REQ-012 §7.5) | `tdd, structure, plan` | ⬜ |
| 6.13 | Create PersonaChangeFlags resolution UI: per-flag add-to-all/some/skip flow (REQ-012 §7.6) | `tdd, structure, plan` | ⬜ |
| 6.14 | Create embedding staleness indicator and score refresh notification (REQ-012 §7.7) | `tdd, structure, plan` | ⬜ |

---

## Phase 7: Job Dashboard & Scoring

**Status:** ⬜ Incomplete

*Three-tab dashboard, job detail, score breakdown, bulk actions. REQ-012 §8. Depends on Phase 0 §A.3 (score_details column).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-012 §8 (specific subsection) |
| 🧪 **TDD** | Write Vitest component tests first — follow `zentropy-tdd` |
| 📂 **Structure** | Place in `frontend/src/app/(dashboard)/` and `frontend/src/app/jobs/` |
| 🌐 **API** | Use typed API client and TanStack Query hooks |
| ✅ **Verify** | `npm run test`, `npm run lint`, `npm run typecheck` |
| 🔍 **Review** | Use `code-reviewer` agent |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 7.1 | Create dashboard page with three-tab layout, URL-persisted tab state (REQ-012 §8.1) | `tdd, structure, plan` | ⬜ |
| 7.2 | Create Opportunities tab: job table with favorite, title, location, salary, scores, ghost, date columns (REQ-012 §8.2) | `tdd, structure, plan` | ⬜ |
| 7.3 | Create job list toolbar: search, status filter, min-fit slider, sort dropdown (REQ-012 §8.2) | `tdd, structure, plan` | ⬜ |
| 7.4 | Create "Show filtered jobs" toggle with dimmed rows and failure reason badges (REQ-012 §8.5) | `tdd, structure, plan` | ⬜ |
| 7.5 | Create ghost detection icon with tooltip and severity-based styling (REQ-012 §8.6) | `tdd, structure, plan` | ⬜ |
| 7.6 | Create multi-select mode for jobs with bulk dismiss/favorite (REQ-012 §8.2) | `tdd, structure, plan` | ⬜ |
| 7.7 | Create job detail page header: metadata, cross-source links, repost history (REQ-012 §8.3) | `tdd, structure, plan` | ⬜ |
| 7.8 | Create Fit score breakdown: 5 components with expandable drill-down (REQ-012 §8.3) | `tdd, structure, plan` | ⬜ |
| 7.9 | Create Stretch score breakdown and score explanation display (REQ-012 §8.3) | `tdd, structure, plan` | ⬜ |
| 7.10 | Create job detail body: extracted skills tags, description, culture signals (REQ-012 §8.3) | `tdd, structure, plan` | ⬜ |
| 7.11 | Create manual job ingest two-step modal: submit raw → preview/modify → confirm (REQ-012 §8.7) | `tdd, structure, plan` | ⬜ |
| 7.12 | Create In Progress and History tabs reusing DataTable with application columns (REQ-012 §8.1) | `tdd, structure, plan` | ⬜ |

---

## Phase 8: Resume Management

**Status:** ⬜ Incomplete

*Base resume editor, job variants, diff display, PDF preview. REQ-012 §9.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-012 §9 (specific subsection) |
| 🧪 **TDD** | Write Vitest component tests first — follow `zentropy-tdd` |
| 📂 **Structure** | Place in `frontend/src/app/resumes/` |
| 🌐 **API** | Use typed API client and TanStack Query hooks |
| ✅ **Verify** | `npm run test`, `npm run lint`, `npm run typecheck` |
| 🔍 **Review** | Use `code-reviewer` agent |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 8.1 | Create resume list page with base resume cards (name, role, updated, variant count, primary badge) (REQ-012 §9.1) | `tdd, structure, plan` | ⬜ |
| 8.2 | Create base resume detail: summary editor and job inclusion checkboxes (REQ-012 §9.2) | `tdd, structure, plan` | ⬜ |
| 8.3 | Create base resume detail: bullet reordering, education/cert/skill checkboxes (REQ-012 §9.2) | `tdd, structure, plan` | ⬜ |
| 8.4 | Create "Re-render PDF" button, approval status display, and inline PDF preview (REQ-012 §9.2) | `tdd, structure, plan` | ⬜ |
| 8.5 | Create job variants list on resume detail: status badges, review/archive actions (REQ-012 §9.2) | `tdd, structure, plan` | ⬜ |
| 8.6 | Create variant review page: side-by-side diff with change highlighting (REQ-012 §9.3) | `tdd, structure, plan` | ⬜ |
| 8.7 | Create agent reasoning and guardrail violation displays for variant review (REQ-012 §9.3-9.4) | `tdd, structure, plan` | ⬜ |
| 8.8 | Create "New Resume" wizard with persona item selection (REQ-012 §9.2) | `tdd, structure, plan` | ⬜ |

---

## Phase 9: Cover Letter Management

**Status:** ⬜ Incomplete

*Cover letter review, regeneration, story override, validation. REQ-012 §10.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-012 §10 |
| 🧪 **TDD** | Write Vitest component tests first — follow `zentropy-tdd` |
| 📂 **Structure** | Place in `frontend/src/components/cover-letter/` (accessed from jobs/applications pages) |
| ✅ **Verify** | `npm run test`, `npm run lint`, `npm run typecheck` |
| 🔍 **Review** | Use `code-reviewer` agent |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 9.1 | Create cover letter review component: agent reasoning, stories used, editable textarea, word count (REQ-012 §10.2) | `tdd, structure, plan` | ⬜ |
| 9.2 | Create validation display: error/warning banners, voice check badge (REQ-012 §10.3) | `tdd, structure, plan` | ⬜ |
| 9.3 | Create regeneration feedback modal: text input, excluded stories, quick option chips (REQ-012 §10.4) | `tdd, structure, plan` | ⬜ |
| 9.4 | Create story override modal: selected/available stories with relevance scores (REQ-012 §10.5) | `tdd, structure, plan` | ⬜ |
| 9.5 | Create approval flow: approve button, read-only transition, PDF download (REQ-012 §10.6) | `tdd, structure, plan` | ⬜ |
| 9.6 | Create unified Ghostwriter review: tabbed resume + cover letter with "Approve Both" (REQ-012 §10.7) | `tdd, structure, plan` | ⬜ |

---

## Phase 10: Application Tracking

**Status:** ⬜ Incomplete

*Application pipeline, timeline, offer/rejection capture. REQ-012 §11. Depends on Phase 0 §A.1 (pin/archive columns).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-012 §11 (specific subsection) |
| 🧪 **TDD** | Write Vitest component tests first — follow `zentropy-tdd` |
| 📂 **Structure** | Place in `frontend/src/app/applications/` |
| 🌐 **API** | Use typed API client and TanStack Query hooks |
| ✅ **Verify** | `npm run test`, `npm run lint`, `npm run typecheck` |
| 🔍 **Review** | Use `code-reviewer` agent |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 10.1 | Create applications list page: status badges, interview stage, toolbar with filters (REQ-012 §11.1) | `tdd, structure, plan` | ⬜ |
| 10.2 | Create application detail: header, documents panel, notes section (REQ-012 §11.2) | `tdd, structure, plan` | ⬜ |
| 10.3 | Create status transition dropdown with conditional prompts per target status (REQ-012 §11.3) | `tdd, structure, plan` | ⬜ |
| 10.4 | Create "Mark as Applied" flow: download materials → apply externally → confirm (REQ-012 §11.4) | `tdd, structure, plan` | ⬜ |
| 10.5 | Create offer details capture form with optional fields and deadline countdown (REQ-012 §11.5) | `tdd, structure, plan` | ⬜ |
| 10.6 | Create rejection details capture form with pre-populated stage (REQ-012 §11.6) | `tdd, structure, plan` | ⬜ |
| 10.7 | Create timeline component: vertical chronological timeline with event icons (REQ-012 §11.7) | `tdd, structure, plan` | ⬜ |
| 10.8 | Create "Add Event" form for timeline (event type, description, conditional fields) (REQ-012 §11.7) | `tdd, structure, plan` | ⬜ |
| 10.9 | Create job snapshot display and pin/archive/bulk-archive actions (REQ-012 §11.9-10) | `tdd, structure, plan` | ⬜ |

---

## Phase 11: Settings & Configuration

**Status:** ⬜ Incomplete

*Job source preferences, agent config, about section. REQ-012 §12.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-012 §12 |
| 🧪 **TDD** | Write Vitest component tests first — follow `zentropy-tdd` |
| 📂 **Structure** | Place in `frontend/src/app/settings/` |
| ✅ **Verify** | `npm run test`, `npm run lint`, `npm run typecheck` |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 11.1 | Create settings page layout with sections (REQ-012 §12.1) | `tdd, structure, plan` | ⬜ |
| 11.2 | Create job source preferences: toggle switches, drag-reorder, tooltips (REQ-012 §12.2) | `tdd, structure, plan` | ⬜ |
| 11.3 | Create agent configuration display (read-only model routing table) (REQ-012 §12.3) | `tdd, structure, plan` | ⬜ |
| 11.4 | Create about section with version info and auth placeholder (REQ-012 §12.4) | `structure, plan` | ⬜ |

---

## Phase 12: Integration, Polish & E2E Tests

**Status:** ⬜ Incomplete

*Cross-page integration tests, E2E user flows, accessibility audit, CI configuration.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read REQ-012 §3.4 for user flow definitions, §13.8 for a11y |
| 🎭 **E2E** | Write Playwright tests per `zentropy-playwright` patterns |
| 🌐 **Mocking** | Mock all API/SSE endpoints — never call real LLM |
| ✅ **Verify** | `npx playwright test`, verify 3x pass locally |
| 🔍 **Review** | Use `code-reviewer` agent |
| 📝 **Commit** | Follow `zentropy-git` |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 12.1 | E2E: New user onboarding flow (12 steps with mocked agent responses) | `playwright, test, plan` | ⬜ |
| 12.2 | E2E: Job discovery flow (dashboard, job detail, draft materials) | `playwright, test, plan` | ⬜ |
| 12.3 | E2E: Application tracking flow (apply, update status, capture offer, timeline) | `playwright, test, plan` | ⬜ |
| 12.4 | E2E: Persona update flow (edit section, change flag resolution) | `playwright, test, plan` | ⬜ |
| 12.5 | E2E: Chat interaction flow (send message, SSE streaming, tool execution) | `playwright, test, plan` | ⬜ |
| 12.6 | Accessibility audit: keyboard nav, ARIA labels, color contrast, focus management (REQ-012 §13.8) | `test, lint, plan` | ⬜ |
| 12.7 | Responsive testing: verify all pages at sm/md/lg breakpoints (REQ-012 §4.5) | `playwright, test, plan` | ⬜ |
| 12.8 | Update CI config for combined backend + frontend test suite | `lint, git, commands, plan` | ⬜ |

---

## Task Count Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 0: Backend Prerequisites | 3 | Appendix A gaps |
| 1: Project Scaffold | 8 | Next.js, tooling, CI hooks |
| 2: Foundation | 12 | Types, API/SSE clients, layout |
| 3: Shared Components | 15 | Forms, tables, toasts, states |
| 4: Chat Interface | 9 | Streaming, badges, cards |
| 5: Onboarding Flow | 18 | 12-step wizard (Step 3 split into a/b, Step 8 into a/b/c) |
| 6: Persona Management | 14 | Section editors, deletion, flags |
| 7: Job Dashboard | 12 | Tabs, detail, scores, bulk |
| 8: Resume Management | 8 | Editor, variants, diff, PDF |
| 9: Cover Letter | 6 | Review, feedback, stories |
| 10: Application Tracking | 9 | Pipeline, timeline, offers |
| 11: Settings | 4 | Sources, config, about |
| 12: Integration & E2E | 8 | E2E tests, a11y, CI |
| **Total** | **126** | |

---

## Dependency Chain

```
Phase 0 (Backend Prerequisites)
  A.1 (pin/archive) ────────────────────► Phase 10 (Applications)
  A.3 (score_details) ──────────────────► Phase 7 (Jobs)

Phase 1 (Scaffold) ──► Phase 2 (Foundation)
                              │
                              ├──► Phase 3 (Shared Components)
                              │           │
                              │           ├──► Phase 4 (Chat)
                              │           │        │
                              │           │        └──► Phase 5 (Onboarding)
                              │           │
                              │           ├──► Phase 6 (Persona) [after Phase 5]
                              │           ├──► Phase 7 (Jobs) [after Phase 0.A3]
                              │           ├──► Phase 8 (Resumes)
                              │           ├──► Phase 9 (Cover Letters)
                              │           ├──► Phase 10 (Applications) [after Phase 0.A1]
                              │           └──► Phase 11 (Settings)
                              │
                              └──► Phase 12 (Integration) [after all above]
```

---

## Open Questions (from REQ-012 §15)

These will be resolved during implementation as encountered:

1. **Max resume upload size** → Proposed: 10MB (REQ-002 §10)
2. **Max application notes length** → Proposed: 10,000 chars (REQ-004 §12)
3. **Chat panel position** → Proposed: right sidebar (desktop), bottom drawer (mobile)
4. **Dark mode** → Deferred — OS preference via CSS variables only
5. **Offer comparison** → Inline on applications page (no dedicated page)
6. **PDF viewer** → Browser native iframe (zero bundle cost)

---

## Decision Points

These require user confirmation during implementation:

1. **Phase 1.3** — Which shadcn/ui components to install initially
2. **Phase 2.12** — Onboarding gate: Next.js middleware vs client-side check (proposed: client-side)
3. **Phase 3.11** — ✅ DECIDED: `@dnd-kit/core` + `@dnd-kit/sortable` for drag-and-drop
4. **Phase 5.10** — Conversational steps: embedded chat view vs persistent sidebar
5. **Phase 7.12** — Dashboard In Progress/History tabs: show applications inline or redirect

---

## Critical Files

- `docs/requirements/REQ-012_frontend_application.md` — Authoritative frontend spec
- `docs/plan/frontend_surface_area.md` — Consolidated API endpoints and data shapes
- `docs/plan/implementation_plan.md` — Backend plan (format reference)
- `backend/app/api/v1/router.py` — Backend API routes
- `backend/app/schemas/` — Backend Pydantic models (for frontend type alignment)

---

## Status Legend

| Icon | Meaning |
|------|---------|
| ⬜ | Incomplete |
| 🟡 | In Progress |
| ✅ | Complete |
| ❌ | Cancelled |
