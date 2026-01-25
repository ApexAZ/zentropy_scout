# Zentropy Scout — Traceability Index

This document maps PRD sections to Requirements to Features to Tasks, enabling Claude Code to build incrementally while maintaining full traceability.

---

## Document Hierarchy

```
PRD Section (Why) → Requirement (What) → Feature (How) → Task (Do)
```

- **PRD:** High-level vision and goals
- **REQ:** Detailed specifications that must be true for the system to work
- **FEAT:** Implementable chunks of functionality
- **TASK:** Atomic work items for Claude Code (tracked in GitHub Issues)

---

## Traceability Matrix

| PRD Section | Requirement | Features | Status |
|-------------|-------------|----------|--------|
| §3 Persona Framework | [REQ-001](./REQ-001_persona_schema.md) Persona Schema v0.8 | FEAT-001, FEAT-002 | 🟡 Draft |
| §8 Document Management | [REQ-002](./REQ-002_resume_schema.md) Resume Schema v0.6 | FEAT-010, FEAT-012 | 🟡 Draft |
| §8 Document Management | [REQ-002b](./REQ-002b_cover_letter_schema.md) Cover Letter Schema v0.5 | FEAT-011, FEAT-015 | 🟡 Draft |
| §4.2 Scouter | [REQ-003](./REQ-003_job_posting_schema.md) Job Posting Schema v0.3 | FEAT-003, FEAT-004 | 🟡 Draft |
| §9 Application Lifecycle | [REQ-004](./REQ-004_application_schema.md) Application Schema v0.4 | FEAT-013, FEAT-014 | 🟡 Draft |
| §6 Data Strategy | [REQ-005](./REQ-005_database_schema.md) Database Schema (ERD) v0.7 | FEAT-005 | 🟡 Draft |
| §5 Architecture | [REQ-006](./REQ-006_api_contract.md) API Contract | FEAT-006, FEAT-007 | 🔴 Not Started |
| §3.2 Discovery Interview | [REQ-007](./REQ-007_onboarding_flow.md) Onboarding Flow | FEAT-001 | 🔴 Not Started |
| §4.3 Strategist | [REQ-008](./REQ-008_scoring_algorithm.md) Scoring Algorithm | FEAT-008 | 🔴 Not Started |
| §5 Architecture | [REQ-009](./REQ-009_provider_abstraction.md) Provider Abstraction | FEAT-009 | 🔴 Not Started |
| §4.4 Ghostwriter | [REQ-010](./REQ-010_content_generation.md) Content Generation | FEAT-010, FEAT-011 | 🔴 Not Started |

---

## Requirement Dependencies

```
REQ-001 Persona Schema ✅ v0.8
    │
    ├── REQ-002 Resume Schema ✅ v0.6
    │       │
    │       └── REQ-002b Cover Letter Schema ✅ v0.5
    │
    ├── REQ-003 Job Posting Schema ✅ v0.3 (matched against Persona)
    │
    └── REQ-004 Application Schema ✅ v0.4 (links Resume + Cover Letter + Job)
            │
            └── REQ-005 Database Schema ✅ v0.7 (ERD combining all)
```

**Build Order:**
1. REQ-001 Persona Schema ✅ Draft complete (v0.8)
2. REQ-002 Resume Schema ✅ Draft complete (v0.6)
3. REQ-002b Cover Letter Schema ✅ Draft complete (v0.5)
4. REQ-003 Job Posting Schema ✅ Draft complete (v0.3)
5. REQ-004 Application Schema ✅ Draft complete (v0.4)
6. REQ-005 Database Schema (ERD) ✅ Draft complete (v0.7)

---

## Feature Registry

| Feature ID | Name | Requirements | Phase | Status |
|------------|------|--------------|-------|--------|
| FEAT-001 | Onboarding Interview Chat | REQ-001, REQ-007 | 1 | 🔴 Not Started |
| FEAT-002 | Persona CRUD API | REQ-001, REQ-005 | 1 | 🔴 Not Started |
| FEAT-003 | Job Ingestion Pipeline | REQ-003, REQ-005 | 2 | 🔴 Not Started |
| FEAT-004 | Ghost Job Detection | REQ-003 | 2 | 🔴 Not Started |
| FEAT-005 | Database Migrations | REQ-005 | 1 | 🔴 Not Started |
| FEAT-006 | FastAPI Scaffold | REQ-006 | 1 | 🔴 Not Started |
| FEAT-007 | Authentication Layer | REQ-006 | 1 | 🔴 Not Started |
| FEAT-008 | Vector Scoring Engine | REQ-008, REQ-005 | 2 | 🔴 Not Started |
| FEAT-009 | LLM Provider Router | REQ-009 | 1 | 🔴 Not Started |
| FEAT-010 | Resume Redlining | REQ-002, REQ-010 | 3 | 🔴 Not Started |
| FEAT-011 | Cover Letter Generation | REQ-002b, REQ-010 | 3 | 🔴 Not Started |
| FEAT-012 | Resume Version Control | REQ-002, REQ-005 | 2 | 🔴 Not Started |
| FEAT-013 | Application Tracking | REQ-004, REQ-005 | 3 | 🔴 Not Started |
| FEAT-014 | Status Pipeline UI | REQ-004 | 3 | 🔴 Not Started |
| FEAT-015 | Cover Letter Version Control | REQ-002b, REQ-005 | 2 | 🔴 Not Started |

---

## Phase 1 (Foundation) Critical Path

```
REQ-001 Persona Schema ✅
    └── REQ-002 Resume Schema ✅
            └── REQ-002b Cover Letter Schema ✅
                    └── REQ-003 Job Posting Schema ✅
                            └── REQ-004 Application Schema ✅
                                    └── REQ-005 Database Schema ✅
                                            └── FEAT-005 Database Migrations ← NEXT
                                                    │
                                                    ├── FEAT-002 Persona CRUD API
                                                    │
                                                    └── FEAT-006 FastAPI Scaffold
                                                            └── FEAT-001 Onboarding Interview Chat
```

---

## Status Legend

| Icon | Meaning |
|------|---------|
| 🔴 | Not Started |
| 🟡 | In Progress |
| 🟢 | Complete |
| 🔵 | Blocked |

---

## Next Actions

1. ~~**Draft REQ-001** — Persona Schema~~ ✅ Complete
2. ~~**Draft REQ-002** — Resume Schema~~ ✅ Complete
3. ~~**Draft REQ-002b** — Cover Letter Schema~~ ✅ Complete
4. ~~**Draft REQ-003** — Job Posting Schema~~ ✅ Complete
5. ~~**Draft REQ-004** — Application Schema~~ ✅ Complete
6. ~~**Draft REQ-005** — Database Schema (ERD)~~ ✅ Complete
7. **Review & Begin Implementation** ← NEXT
