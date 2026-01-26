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

All 12 requirement documents drafted and reviewed.

**Implementation Phase: 🔴 NOT STARTED**

1. **Cross-document audit** (optional) — Verify field name consistency across REQ-001↔REQ-005↔REQ-006
2. **Begin implementation** — Start with REQ-005 (Database Schema)
