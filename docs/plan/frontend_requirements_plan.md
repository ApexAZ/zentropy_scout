# Zentropy Scout — Frontend Requirements Plan

**Created:** 2026-02-07
**Last Updated:** 2026-02-07
**Status:** Ready to Begin

---

## How to Use This Document

**Purpose:** This plan guides the writing of frontend requirement documents (REQ-012+). Each phase produces a committed artifact so progress survives compaction and session boundaries.

**Tracking:** Each phase has a status, and each subtask has its own status. When resuming after compaction or a new session, find the first 🟡 (In Progress) or ⬜ (Incomplete) item.

**Context Management:** Each subtask is sized to fit within ~50-100k tokens. Load only the backend REQ(s) listed in the "References" column — do NOT load all REQs at once.

**Order:** Phases are sequential. Complete each phase before starting the next.

**Output location:** `docs/requirements/`

---

## Phase 0: Backend Surface Area Audit

**Status:** ⬜ Incomplete

*Sweep all existing REQ docs to extract everything the frontend needs to expose. Produces a reference doc that drives all subsequent phases.*

### Workflow
| Step | Action |
|------|--------|
| 📖 **Research** | Use `req-reader` agent to sweep each REQ doc for frontend-facing items |
| 📝 **Output** | Create `docs/plan/frontend_surface_area.md` — the consolidated reference |
| ✅ **Verify** | Every API endpoint, SSE event, HITL checkpoint, and user decision is captured |
| 📝 **Commit** | Commit the surface area doc |

### Tasks
| § | Task | References | Status |
|---|------|------------|--------|
| 0.1 | Extract persona-facing UI from REQ-001 (Persona Schema) — include discovery preferences (§3.10), non-negotiables (§3.8), growth targets (§3.9), deletion handling (§7b) | REQ-001 | ⬜ |
| 0.2 | Extract resume workflow UI from REQ-002 (Resume Schema) — include creation wizard, render/approve cycle, variant approval/snapshot | REQ-002 | ⬜ |
| 0.3 | Extract cover letter workflow UI from REQ-002b (Cover Letter Schema) — include agent reasoning display | REQ-002b | ⬜ |
| 0.4 | Extract job posting UI from REQ-003 (Job Posting Schema) — include repost history (§8), cross-source display (§9.2), expiration notifications (§12.2) | REQ-003 | ⬜ |
| 0.5 | Extract application tracking UI from REQ-004 (Application Schema) — include offer/rejection capture forms, interview stages, job snapshots, follow-up suggestions | REQ-004 | ⬜ |
| 0.6 | Extract all API endpoints and response shapes from REQ-006 (API Contract) — include bulk operations (§2.6), two-step ingest (§5.6), SSE reconnection (§2.5) | REQ-006 | ⬜ |
| 0.7 | Extract all user-facing agent flows and HITL checkpoints from REQ-007 (Agent Behavior) — include ambiguity resolution (§4.4), tool execution visualization (§9.3), Scouter progress (§9.1) | REQ-007 | ⬜ |
| 0.8 | Extract scoring display requirements from REQ-008 (Scoring Algorithm) — include component drill-down (§4.7, §5.5), explanation fields (§8), independent score presentation (§7.3 cancellation) | REQ-008 | ⬜ |
| 0.9 | Extract content generation UI from REQ-010 (Content Generation) — include validation issue display (§5.4), modification limits explanation (§4.4), quality metrics (§10) | REQ-010 | ⬜ |
| 0.10 | Consolidate all findings into `docs/plan/frontend_surface_area.md` | All above | ⬜ |

### Notes
- REQ-005 (Database Schema) and REQ-009 (Provider Abstraction) are backend-internal — no direct frontend surface area, skip these.
- REQ-011 (Chrome Extension) is postponed — skip for now.
- §0.1–0.9 can run in parallel via req-reader subagents if context allows.
- §0.10 is the synthesis step — organize by UI area, not by source REQ.

---

## Phase 1: Information Architecture & Frontend Decisions

**Status:** ⬜ Incomplete

*Organize the surface area into pages, flows, and shared components. Make foundational frontend architecture decisions. Produces the frontend REQ skeleton.*

### Workflow
| Step | Action |
|------|--------|
| 📖 **Input** | Read `docs/plan/frontend_surface_area.md` |
| 🏗️ **Design** | Group endpoints/flows into logical pages and navigation |
| 📝 **Output** | Create `docs/plan/frontend_req_skeleton.md` — section outline with one-line descriptions |
| ✅ **Verify** | Every item from surface area doc has a home in the skeleton |
| 📝 **Commit** | Commit the skeleton |

### Tasks
| § | Task | References | Status |
|---|------|------------|--------|
| 1.1 | Define page inventory (list of all screens/views) | Surface area doc | ⬜ |
| 1.2 | Define navigation structure and routing | Surface area doc | ⬜ |
| 1.3 | Identify shared/reusable components (modals, forms, tables, PDF viewer) | Surface area doc | ⬜ |
| 1.4 | Map user flows across pages (e.g., onboarding → persona → job search → application) | Surface area doc, REQ-007 | ⬜ |
| 1.5 | Identify real-time requirements (SSE events → UI updates, reconnection strategy) | Surface area doc, REQ-006 §2.5, REQ-007 | ⬜ |
| 1.6 | Frontend architecture decisions — state management (React Query vs SWR vs server actions), SSE client, API client / data fetching patterns, auth approach (MVP single-user) | Surface area doc | ⬜ |
| 1.7 | Responsive/mobile strategy — breakpoints, mobile-first vs desktop-first, which views support mobile | — | ⬜ |
| 1.8 | Draft frontend REQ skeleton with section numbers | All above | ⬜ |
| 1.9 | Gap analysis — backend capabilities without a clear UI home, or UI needs requiring new backend support | All above | ⬜ |

---

## Phase 2: Chat & Onboarding UI (REQ-012 §1-2)

**Status:** ⬜ Incomplete

*Write detailed requirements for the chat interface and onboarding flow. These are the entry point for new users and the primary interaction model.*

### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-007 §4 (Chat Agent) and §5 (Onboarding Agent) |
| 📝 **Write** | Draft REQ-012 sections for Chat UI and Onboarding Flow |
| ✅ **Verify** | All HITL checkpoints from REQ-007 §5 have corresponding UI states |
| 📝 **Commit** | Commit the REQ-012 sections |

### Tasks
| § | Task | References | Status |
|---|------|------------|--------|
| 2.1 | Chat interface — layout, message types, input handling | REQ-007 §4, REQ-006 §2.4-2.5 | ⬜ |
| 2.2 | Chat — SSE streaming display (typing indicators, progress, reconnection on tab return) | REQ-007 §9, REQ-006 §2.5 | ⬜ |
| 2.3 | Chat — agent status indicators, tool execution visualization, and error display | REQ-007 §9.3, §10 | ⬜ |
| 2.4 | Chat — ambiguity resolution UI (clickable option choices vs free text) | REQ-007 §4.4 | ⬜ |
| 2.5 | Onboarding flow — step-by-step interview UI | REQ-007 §5 | ⬜ |
| 2.6 | Onboarding — resume upload step (drag-and-drop, progress, file size validation) | REQ-007 §5.3, REQ-006 §2.7 | ⬜ |
| 2.7 | Onboarding — checkpoint resume/restore UX | REQ-007 §5.4 | ⬜ |
| 2.8 | Onboarding — completion and persona review | REQ-007 §5.5, REQ-001 | ⬜ |

---

## Phase 3: Persona Management UI (REQ-012 §3)

**Status:** ⬜ Incomplete

*Write requirements for viewing and editing the user's professional persona. REQ-001 is the largest schema doc — tasks are split by domain area to fit context windows.*

### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-001 (Persona Schema) and REQ-006 persona endpoints |
| 📝 **Write** | Draft REQ-012 sections for Persona views and editors |
| ✅ **Verify** | All persona fields from REQ-001 are editable; change flags (REQ-006 §5.4) trigger UI feedback |
| 📝 **Commit** | Commit the REQ-012 sections |

### Tasks
| § | Task | References | Status |
|---|------|------------|--------|
| 3.1 | Persona overview/dashboard — summary of skills, experience, preferences, completeness | REQ-001 | ⬜ |
| 3.2 | Basic info and professional overview editors — name, contact, professional_summary, years_experience, current_role | REQ-001 §3.1, §3.1b | ⬜ |
| 3.3 | Work history and bullet editors — nested job entries with display ordering | REQ-001 §3.2, REQ-006 | ⬜ |
| 3.4 | Education and certifications editors | REQ-001 §3.4-3.5, REQ-006 | ⬜ |
| 3.5 | Skills editor — hard/soft skills with proficiency scales and categories | REQ-001 §3.3, REQ-006 | ⬜ |
| 3.6 | Achievement stories — CRUD, display, story detail view | REQ-001, REQ-010 §5.2 | ⬜ |
| 3.7 | Voice profile editor — tone, style, vocabulary, blacklist, writing sample | REQ-001, REQ-010 §3 | ⬜ |
| 3.8 | Non-negotiables editor — location, compensation, work type, custom filters CRUD | REQ-001 §3.8, REQ-006 (custom-non-negotiables endpoint) | ⬜ |
| 3.9 | Growth targets editor — target roles, target skills, stretch appetite | REQ-001 §3.9 | ⬜ |
| 3.10 | Discovery preferences — minimum fit threshold, auto-draft threshold, polling frequency | REQ-001 §3.10 | ⬜ |
| 3.11 | Persona change flags — stale resume/score warnings and refresh actions | REQ-006 §5.4 | ⬜ |
| 3.12 | Deletion handling — reference checks, confirmation dialogs, "Review each" flow | REQ-001 §7b | ⬜ |

---

## Phase 4: Job Dashboard & Scoring UI (REQ-012 §4)

**Status:** ⬜ Incomplete

*Write requirements for job posting views, scoring display, filtering, and bulk operations.*

### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-003, REQ-008, REQ-007 §6-7 |
| 📝 **Write** | Draft REQ-012 sections for Job Dashboard |
| ✅ **Verify** | Fit/Stretch scores, non-negotiables, ghost detection, bulk ops all have UI representation |
| 📝 **Commit** | Commit the REQ-012 sections |

### Tasks
| § | Task | References | Status |
|---|------|------------|--------|
| 4.1 | Job list view — sortable, filterable table/cards with "show filtered jobs" toggle | REQ-006 §5.5, REQ-003, REQ-003 §10.4-10.5 | ⬜ |
| 4.2 | Job detail view — posting metadata, extracted skills, culture text | REQ-003, REQ-007 §6.4 | ⬜ |
| 4.3 | Scoring display — Fit/Stretch scores presented independently, with expandable component breakdown drill-down | REQ-008 §4-5, §7-8 | ⬜ |
| 4.4 | Score explanation display — strengths, gaps, stretch opportunities, warnings | REQ-008 §8 | ⬜ |
| 4.5 | Non-negotiables filter indicators | REQ-008 §3 | ⬜ |
| 4.6 | Ghost detection indicators and warnings | REQ-003 §7 | ⬜ |
| 4.7 | Repost history and cross-source display ("Also found on: ...") | REQ-003 §8-9 | ⬜ |
| 4.8 | Job status transitions and user actions (favorite, dismiss, archive) | REQ-003 §6 | ⬜ |
| 4.9 | Multi-select and bulk operations (bulk dismiss, bulk favorite) | REQ-006 §2.6 | ⬜ |
| 4.10 | Manual job ingest — two-step flow (paste URL/text → preview/modify → confirm) | REQ-006 §5.6 | ⬜ |
| 4.11 | Scouter progress notifications and manual refresh trigger | REQ-007 §9.1, REQ-006 (refresh endpoint) | ⬜ |
| 4.12 | Job expiration notifications | REQ-003 §12.2 | ⬜ |

---

## Phase 5: Resume Management UI (REQ-012 §5)

**Status:** ⬜ Incomplete

*Write requirements for base resume management, job variants, and PDF preview/download.*

### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-002 and REQ-010 §4, §9 |
| 📝 **Write** | Draft REQ-012 sections for Resume Management |
| ✅ **Verify** | Upload, creation wizard, variant comparison, PDF preview/download, approval flow all covered |
| 📝 **Commit** | Commit the REQ-012 sections |

### Tasks
| § | Task | References | Status |
|---|------|------------|--------|
| 5.1 | Base resume list and management | REQ-002 §4.1-4.2 | ⬜ |
| 5.2 | Base resume creation wizard — select persona items (jobs, bullets, skills, education, certifications) | REQ-002 §4.2, §6.1 | ⬜ |
| 5.3 | Base resume render/approve workflow — PDF anchor review and approval | REQ-002 §4.2 (rendering) | ⬜ |
| 5.4 | Job variant view — diff/comparison with base resume | REQ-002 §4.3 | ⬜ |
| 5.5 | Job variant approval — snapshot creation, immutability messaging, "Pending Review" state | REQ-002 §4.3.2, REQ-004 §7.0 | ⬜ |
| 5.6 | PDF preview and download (resumes and submitted PDFs) | REQ-002 §4.4, REQ-006 §2.7 | ⬜ |
| 5.7 | Auto-draft notification and review flow | REQ-002 §6.2, REQ-007 §8 | ⬜ |
| 5.8 | Tailoring explanation display (agent reasoning) | REQ-010 §9, REQ-007 §8.7 | ⬜ |
| 5.9 | Modification limits explanation — guardrails feedback when validation fails | REQ-010 §4.4 | ⬜ |

---

## Phase 6: Cover Letter Management UI (REQ-012 §6)

**Status:** ⬜ Incomplete

*Write requirements for cover letter generation, editing, and regeneration. Note: Ghostwriter produces resume variant + cover letter together — this phase must coordinate with Phase 5 for a unified review experience.*

### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-002b and REQ-010 §5, §7 |
| 📝 **Write** | Draft REQ-012 sections for Cover Letter Management |
| ✅ **Verify** | Generation, editing, regeneration feedback, validation display, PDF preview all covered |
| 📝 **Commit** | Commit the REQ-012 sections |

### Tasks
| § | Task | References | Status |
|---|------|------------|--------|
| 6.1 | Cover letter list and status display | REQ-002b §4 | ⬜ |
| 6.2 | Cover letter editor (inline editing) | REQ-002b §7.3 | ⬜ |
| 6.3 | Regeneration feedback UI (categories, tone, length) | REQ-010 §7 | ⬜ |
| 6.4 | Story selection display, agent reasoning, and override | REQ-010 §5.2, REQ-002b §4.1, REQ-007 §8.6 | ⬜ |
| 6.5 | Cover letter validation issue display (length, blacklist, story accuracy) | REQ-010 §5.4 | ⬜ |
| 6.6 | Cover letter PDF preview and download | REQ-002b §4.2, REQ-006 §2.7 | ⬜ |
| 6.7 | Approval and submission flow | REQ-002b §7.4 | ⬜ |
| 6.8 | Unified Ghostwriter review experience — combined resume variant + cover letter presentation | REQ-007 §8, Phases 5-6 | ⬜ |

---

## Phase 7: Application Tracking UI (REQ-012 §7)

**Status:** ⬜ Incomplete

*Write requirements for the application lifecycle dashboard. REQ-004 defines a rich status pipeline with structured data capture at each transition.*

### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-004 |
| 📝 **Write** | Draft REQ-012 sections for Application Tracking |
| ✅ **Verify** | All status transitions, structured capture forms, timeline, and bulk ops have UI representation |
| 📝 **Commit** | Commit the REQ-012 sections |

### Tasks
| § | Task | References | Status |
|---|------|------------|--------|
| 7.1 | Application list — visualization pattern (kanban vs table), status pipeline display | REQ-004 | ⬜ |
| 7.2 | Application detail — linked resume, cover letter, job posting, job snapshot | REQ-004 §4.1, §4.1a | ⬜ |
| 7.3 | "Mark as Applied" flow — download PDFs, apply externally, return to confirm | REQ-004 §7.1 | ⬜ |
| 7.4 | Status transitions — user-driven state changes with validation | REQ-004 | ⬜ |
| 7.5 | Interview stage tracking — stage indicators within Interviewing status | REQ-004 §4.1, §5.1 | ⬜ |
| 7.6 | Offer details capture form — salary, bonus, equity, benefits, deadline | REQ-004 §4.3 | ⬜ |
| 7.7 | Rejection details capture — stage and optional reason/feedback | REQ-004 §4.4 | ⬜ |
| 7.8 | Application notes and timeline visualization | REQ-004 | ⬜ |
| 7.9 | Follow-up suggestion display — agent-driven reminders based on timeline gaps | REQ-004 §8.1 | ⬜ |
| 7.10 | Pin, archive, restore actions and bulk archive | REQ-004 §10, REQ-006 §2.6 | ⬜ |

---

## Phase 8: Settings & Configuration UI (REQ-012 §8)

**Status:** ⬜ Incomplete

*Write requirements for user settings, source preferences, and system configuration.*

### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` to load REQ-003 §4.2b (source preferences), REQ-007 §11 (agent config) |
| 📝 **Write** | Draft REQ-012 sections for Settings |
| ✅ **Verify** | Source preferences, polling config, agent config, auth approach all covered |
| 📝 **Commit** | Commit the REQ-012 sections |

### Tasks
| § | Task | References | Status |
|---|------|------------|--------|
| 8.1 | Job source preferences (enable/disable, priority) | REQ-003 §4.2b | ⬜ |
| 8.2 | Polling configuration | REQ-003 §4.4 | ⬜ |
| 8.3 | Agent configuration (model routing, thresholds) | REQ-007 §11 | ⬜ |
| 8.4 | User profile and authentication — MVP single-user approach, future multi-user notes | REQ-006 §6 | ⬜ |

### Notes
- Discovery preferences (`minimum_fit_threshold`, `auto_draft_threshold`) live on the Persona and are covered in Phase 3 (§3.10), not here.

---

## Phase 9: Shared Components & Design System (REQ-012 §9)

**Status:** ⬜ Incomplete

*Write requirements for reusable UI components, design tokens, and cross-cutting UX patterns. Consider writing §9.1 (design tokens) and §9.2 (form patterns) early — during or right after Phase 1 — so Phases 2-8 can reference them.*

### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Review all prior REQ-012 sections for repeated UI patterns |
| 📝 **Write** | Draft REQ-012 sections for shared components |
| ✅ **Verify** | All repeated patterns across phases 2-8 are captured |
| 📝 **Commit** | Commit the REQ-012 sections |

### Tasks
| § | Task | References | Status |
|---|------|------------|--------|
| 9.1 | Design tokens (colors, typography, spacing) | — | ⬜ |
| 9.2 | Common form patterns (validation, error display, optimistic updates) | All prior phases | ⬜ |
| 9.3 | Table/list components (sorting, filtering, pagination, multi-select) | REQ-006 §7.3, §5.5, §2.6 | ⬜ |
| 9.4 | PDF viewer/preview component | Phases 5-6 | ⬜ |
| 9.5 | Notification/toast patterns (SSE `data_changed` events as trigger source) | REQ-007 §9, REQ-006 §2.5 | ⬜ |
| 9.6 | Loading states, skeleton screens, and long-running operation UX (LLM calls 5-30s) | — | ⬜ |
| 9.7 | Error states and empty states catalog (no data yet, loading failed, partial data) | All prior phases | ⬜ |
| 9.8 | Accessibility requirements — keyboard navigation, screen reader, ARIA, color contrast | — | ⬜ |
| 9.9 | Offline/reconnection handling — SSE disconnect/reconnect, tab inactive > 5 min | REQ-006 §2.5 | ⬜ |

---

## Phase 10: Integration & Review

**Status:** ⬜ Incomplete

*Final pass across all REQ-012 sections for consistency, completeness, and cross-references.*

### Tasks
| § | Task | References | Status |
|---|------|------------|--------|
| 10.1 | Cross-reference audit — verify all sections use consistent terminology | All REQ-012 | ⬜ |
| 10.2 | Navigation flow audit — verify all user journeys are connected | REQ-012 §1-8 | ⬜ |
| 10.3 | Unified Ghostwriter review audit — resume variant + cover letter presented coherently | REQ-012 §5-6 | ⬜ |
| 10.4 | Gap analysis — any backend capability without frontend coverage? | Surface area doc, all REQ-012 | ⬜ |
| 10.5 | Update `docs/requirements/_index.md` with REQ-012 entry | _index.md | ⬜ |

---

## Status Legend

| Icon | Meaning |
|------|---------|
| ⬜ | Incomplete |
| 🟡 | In Progress |
| ✅ | Complete |

---

## Quick Reference: Phase Dependencies

```
Phase 0: Audit ──► Phase 1: Information Architecture & Decisions
                        │
                        ├─► (Optional) Phase 9.1-9.2 early: design tokens + form patterns
                        │
                        ▼
                   Phases 2-8: Write REQ sections (sequential)
                        │
                        ▼
                   Phase 9: Shared Components (remainder)
                        │
                        ▼
                   Phase 10: Integration & Review
```

---

## Task Count Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 0 | 10 | Backend audit |
| 1 | 9 | Information architecture & frontend decisions |
| 2 | 8 | Chat & Onboarding |
| 3 | 12 | Persona Management |
| 4 | 12 | Job Dashboard & Scoring |
| 5 | 9 | Resume Management |
| 6 | 8 | Cover Letter Management |
| 7 | 10 | Application Tracking |
| 8 | 4 | Settings & Configuration |
| 9 | 9 | Shared Components & Design System |
| 10 | 5 | Integration & Review |
| **Total** | **96** | |
