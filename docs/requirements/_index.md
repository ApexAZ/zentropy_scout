# Zentropy Scout — Requirements Index

This document maps PRD sections to Requirements documents and defines the implementation order.

---

## Document Hierarchy

```
PRD Section (Why) → Requirement (What) → Implementation (GitHub Issues)
```

- **PRD:** High-level vision and goals (`/docs/prd/zentropy_scout_prd.md`)
- **REQ:** Detailed specifications — source of truth for implementation
- **GitHub Issues:** Atomic work items for coding agent

---

## Requirements Matrix

| PRD Section | Requirement | Status |
|-------------|-------------|--------|
| §3 Persona Framework | [REQ-001](./REQ-001_persona_schema.md) Persona Schema v0.8 | 🟢 Complete |
| §8 Document Management | [REQ-002](./REQ-002_resume_schema.md) Resume Schema v0.7 | 🟢 Complete |
| §8 Document Management | [REQ-002b](./REQ-002b_cover_letter_schema.md) Cover Letter Schema v0.5 | 🟢 Complete |
| §4.2 Scouter | [REQ-003](./REQ-003_job_posting_schema.md) Job Posting Schema v0.4 | 🟢 Complete |
| §9 Application Lifecycle | [REQ-004](./REQ-004_application_schema.md) Application Schema v0.5 | 🟢 Complete |
| §6 Data Strategy | [REQ-005](./REQ-005_database_schema.md) Database Schema v0.10 | 🟢 Complete |
| §5 Architecture | [REQ-006](./REQ-006_api_contract.md) API Contract v0.8 | 🟢 Complete |
| §4 Agentic Capabilities | [REQ-007](./REQ-007_agent_behavior.md) Agent Behavior v0.5 | 🟢 Complete |
| §4.3 Strategist | [REQ-008](./REQ-008_scoring_algorithm.md) Scoring Algorithm v0.2 | 🟢 Complete |
| §5 Architecture | [REQ-009](./REQ-009_provider_abstraction.md) Provider Abstraction v0.2 | 🟢 Complete |
| §4.4 Ghostwriter | [REQ-010](./REQ-010_content_generation.md) Content Generation v0.1 | 🟢 Complete |
| §4.2 Scouter (Manual) | [REQ-011](./REQ-011_chrome_extension.md) Chrome Extension v0.1 | 🟢 Complete |
| §7 Frontend Application | [REQ-012](./REQ-012_frontend_application.md) Frontend Application v0.1 | 🟢 Complete |
| §5 Architecture | [REQ-013](./REQ-013_authentication.md) Authentication & Account Management v0.1 | 🔴 Not Started |
| §5 Architecture, §6 Data Strategy | [REQ-014](./REQ-014_multi_tenant.md) Multi-Tenant Data Isolation v0.1 | 🔴 Not Started |
| §4.2 Scouter, §6 Data Strategy | [REQ-015](./REQ-015_shared_job_pool.md) Shared Job Pool v0.1 | 🔴 Not Started |
| §7 Frontend Application | [REQ-033](./REQ-033_ui_design_system.md) UI Design System & Visual Redesign v0.1 | 🟡 In Progress |

---

## Requirement Dependencies

```
REQ-001 Persona Schema
    │
    ├── REQ-002 Resume Schema
    │       └── REQ-002b Cover Letter Schema
    │
    ├── REQ-003 Job Posting Schema (matched against Persona)
    │       └── REQ-008 Scoring Algorithm
    │
    └── REQ-004 Application Schema (links Resume + Cover Letter + Job)

REQ-005 Database Schema (consolidates all entity definitions)
    └── depends on: REQ-001, REQ-002, REQ-002b, REQ-003, REQ-004

REQ-006 API Contract
    └── depends on: REQ-005 (entity definitions)

REQ-007 Agent Behavior
    └── depends on: REQ-006 (API endpoints), REQ-008 (scoring), REQ-009 (providers)

REQ-009 Provider Abstraction
    └── standalone (infrastructure)

REQ-010 Content Generation
    └── depends on: REQ-001 (Voice Profile), REQ-002 (Resume), REQ-007 (Ghostwriter flow)

REQ-011 Chrome Extension
    └── depends on: REQ-006 (ingest endpoint), REQ-003 (JobPosting schema)

REQ-012 Frontend Application
    └── depends on: REQ-001 through REQ-010 (all backend specs)

REQ-013 Authentication & Account Management
    └── depends on: REQ-005 (users table), REQ-006 (API auth pattern §6.2)

REQ-014 Multi-Tenant Data Isolation
    └── depends on: REQ-005 (entity relationships), REQ-006 (endpoint inventory),
                     REQ-007 (agent state), REQ-013 (authenticated user_id)

REQ-015 Shared Job Pool
    └── depends on: REQ-003 (job posting schema), REQ-005 (entity relationships),
                     REQ-007 (Scouter agent), REQ-008 (scoring), REQ-014 (tier classification)
```

---

## Implementation Order

**Phase 1: Foundation**
1. **REQ-005** → Database migrations (PostgreSQL + pgvector)
2. **REQ-009** → Provider abstraction layer
3. **REQ-006** → FastAPI scaffold with basic CRUD

**Phase 2: Core Logic**
4. **REQ-007** → Agent orchestration (LangGraph)
5. **REQ-008** → Scoring engine (embeddings)
6. **REQ-003** → Job ingestion pipeline

**Phase 3: Content & UI**
7. **REQ-010** → Ghostwriter prompts
8. **REQ-002/002b** → Resume & cover letter generation
9. **REQ-011** → Chrome extension

---

## Implementation Notes for Coding Agent

1. **TaskType enum (REQ-009):** Add generic `EXTRACTION` value to support utility functions in REQ-010. The spec defines `SKILL_EXTRACTION` but REQ-010 references `TaskType.EXTRACTION` for keyword/metrics extraction.

2. **Shared extraction service (REQ-007 §6.4):** The `extract_job_data()` function must be callable by both the Scouter polling loop AND the `/job-postings/ingest` API endpoint.

3. **All code examples are prescriptive:** Python code in REQ-007, REQ-008, REQ-009, REQ-010 should be implemented as written (including `# WHY` comments).

---

## Status Legend

| Icon | Meaning |
|------|---------|
| 🔴 | Not Started |
| 🟡 | In Progress |
| 🟢 | Complete |

---

## Next Actions

**Requirements Phase: ✅ COMPLETE**

All 16 requirement documents drafted and reviewed (REQ-001 through REQ-015).

**Backend Implementation Phase: ✅ COMPLETE**

Phases 1.1–3.2 implemented. Phase 4.1 (Chrome Extension) postponed.

**Frontend Implementation Phase: ✅ COMPLETE**

Phases 1–15 implemented. See `docs/plan/frontend_implementation_plan.md`.

**Authentication & Multi-Tenant Phase: 🔴 NOT STARTED**

1. **REQ-013** → Authentication (Auth.js v5, Google/LinkedIn OAuth, Magic Link)
2. **REQ-014** → Multi-tenant data isolation (ownership enforcement, cross-tenant tests)
3. **REQ-015** → Shared job pool (schema split, global dedup, cross-user surfacing)
