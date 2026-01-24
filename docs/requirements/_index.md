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
| §3 Persona Framework | [REQ-001](./REQ-001_persona_schema.md) Persona Schema | FEAT-001, FEAT-002 | 🔴 Not Started |
| §4.1 Scouter | [REQ-002](./REQ-002_job_schema.md) Job Posting Schema | FEAT-003, FEAT-004 | 🔴 Not Started |
| §6 Data Strategy | [REQ-003](./REQ-003_database_schema.md) Database Schema | FEAT-005 | 🔴 Not Started |
| §5 Architecture | [REQ-004](./REQ-004_api_contract.md) API Contract | FEAT-006, FEAT-007 | 🔴 Not Started |
| §3.1 Discovery Interview | [REQ-005](./REQ-005_onboarding_flow.md) Onboarding Flow | FEAT-001 | 🔴 Not Started |
| §4.2 Strategist | [REQ-006](./REQ-006_scoring_algorithm.md) Scoring Algorithm | FEAT-008 | 🔴 Not Started |
| §5 Architecture | [REQ-007](./REQ-007_provider_abstraction.md) Provider Abstraction | FEAT-009 | 🔴 Not Started |
| §4.3 Ghostwriter | [REQ-008](./REQ-008_content_generation.md) Content Generation | FEAT-010, FEAT-011 | 🔴 Not Started |

---

## Feature Registry

| Feature ID | Name | Requirements | Phase | Status |
|------------|------|--------------|-------|--------|
| FEAT-001 | Onboarding Interview Chat | REQ-001, REQ-005 | 2 | 🔴 Not Started |
| FEAT-002 | Persona CRUD API | REQ-001, REQ-003 | 1 | 🔴 Not Started |
| FEAT-003 | Job Ingestion Pipeline | REQ-002, REQ-003 | 1 | 🔴 Not Started |
| FEAT-004 | Ghost Job Detection | REQ-002 | 1 | 🔴 Not Started |
| FEAT-005 | Database Migrations | REQ-003 | 1 | 🔴 Not Started |
| FEAT-006 | FastAPI Scaffold | REQ-004 | 1 | 🔴 Not Started |
| FEAT-007 | Authentication Layer | REQ-004 | 1 | 🔴 Not Started |
| FEAT-008 | Vector Scoring Engine | REQ-006, REQ-003 | 2 | 🔴 Not Started |
| FEAT-009 | LLM Provider Router | REQ-007 | 1 | 🔴 Not Started |
| FEAT-010 | Resume Redlining | REQ-008, REQ-001 | 3 | 🔴 Not Started |
| FEAT-011 | Cover Letter Generation | REQ-008, REQ-001 | 3 | 🔴 Not Started |

---

## Phase 1 (MVP) Dependency Graph

```
REQ-003 Database Schema
    └── FEAT-005 Database Migrations
            │
            ├── FEAT-002 Persona CRUD API
            │       └── (blocked until REQ-001 complete)
            │
            └── FEAT-003 Job Ingestion Pipeline
                    └── (blocked until REQ-002 complete)

REQ-007 Provider Abstraction
    └── FEAT-009 LLM Provider Router
            └── (independent, can start immediately)

REQ-004 API Contract
    └── FEAT-006 FastAPI Scaffold
            └── FEAT-007 Authentication Layer
```

**Critical Path for Phase 1:**
1. REQ-001 Persona Schema ← **START HERE**
2. REQ-002 Job Posting Schema
3. REQ-003 Database Schema (depends on 1 & 2)
4. FEAT-005 → FEAT-006 → FEAT-002 & FEAT-003

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

1. **Draft REQ-001** — Persona Schema (unblocks everything)
2. **Draft REQ-002** — Job Posting Schema
3. **Draft REQ-003** — Database Schema (ERD)
