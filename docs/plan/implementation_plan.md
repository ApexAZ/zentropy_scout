# Zentropy Scout — Implementation Plan

**Created:** 2026-01-25  
**Last Updated:** 2026-01-25  
**Status:** Ready for Implementation

---

## How to Use This Document

**Tracking:** Each requirement has a status, and each subsection has its own status. When resuming after compaction or a new session, find the first 🟡 (In Progress) or ⬜ (Incomplete) item.

**Context Management:** Load only the REQ section being worked on, not the entire document. Each subsection is designed to be a single unit of work.  Coding agent should pick up the very first task in Progress, or TO DO.  Coding agent should mark the task complete as soon as it's complete.  TRACKING IS VERY IMPORTANT FOR CONTEXT CONTINUITY.

**Order:** Sections are ordered by implementation dependency, not document number. Follow top-to-bottom.

Requirements location: `docs/requirements/`

---

## Phase 1: Foundation

### 1.1 Database Schema (REQ-005)
**Status:** ⬜ Incomplete

*Creates all tables. Must complete before any other implementation.*

| § | Task | Status |
|---|------|--------|
| 8 | Extensions Required (pgvector) | ⬜ |
| 9.1 | Migration Order | ⬜ |
| 9.2 | Circular Reference Note | ⬜ |
| 4.0 | User (Auth Foundation) | ⬜ |
| 4.1 | Persona Domain Tables | ⬜ |
| 4.2 | Resume Domain Tables | ⬜ |
| 4.3 | Cover Letter Domain Tables | ⬜ |
| 4.4 | Job Posting Domain Tables | ⬜ |
| 4.5 | Application Domain Tables | ⬜ |
| 5.1 | JSONB Schema — Persona Domain | ⬜ |
| 5.2 | JSONB Schema — Resume Domain | ⬜ |
| 5.3 | JSONB Schema — Job Posting Domain | ⬜ |
| 5.4 | JSONB Schema — Application Domain | ⬜ |
| 6 | Archive Implementation | ⬜ |
| 7 | Cleanup Jobs | ⬜ |
| 3 | Entity Relationship Diagram (validation) | ⬜ |

---

### 1.2 Provider Abstraction (REQ-009)
**Status:** ⬜ Incomplete

*LLM and embedding interfaces. Required before any agent implementation.*

| § | Task | Status |
|---|------|--------|
| 3.1 | Layer Diagram | ⬜ |
| 3.2 | Key Components | ⬜ |
| 6.1 | ProviderConfig Class | ⬜ |
| 6.2 | Environment Variables | ⬜ |
| 6.3 | Provider Factory | ⬜ |
| 4.1 | LLM Abstract Interface | ⬜ |
| 4.2 | Provider-Specific Adapters (Claude, OpenAI, Gemini) | ⬜ |
| 4.3 | Model Routing Table | ⬜ |
| 4.4 | Cost Estimates by Task | ⬜ |
| 4.5 | Tool Calling Patterns | ⬜ |
| 4.6 | JSON Mode Patterns | ⬜ |
| 5.1 | Embedding Abstract Interface | ⬜ |
| 5.2 | OpenAI Embedding Adapter | ⬜ |
| 5.3 | Embedding Model Comparison | ⬜ |
| 7.1 | Error Taxonomy | ⬜ |
| 7.2 | Retry Strategy | ⬜ |
| 7.3 | Error Mapping | ⬜ |
| 8.1 | Logging | ⬜ |
| 9.1 | Mock Provider | ⬜ |
| 9.2 | Test Fixtures | ⬜ |
| 8.2 | Metrics (Future) | ⬜ |
| 8.3 | Cost Tracking (Future) | ⬜ |
| 10 | BYOK Support (Future) | ⬜ |

---

### 1.3 API Scaffold (REQ-006)
**Status:** ⬜ Incomplete

*REST endpoints and auth. Required before agent tools can call the API.*

| § | Task | Status |
|---|------|--------|
| 2.1 | API Style: REST | ⬜ |
| 2.2 | Deployment Model: Local-First | ⬜ |
| 6.1 | Authentication | ⬜ |
| 6.2 | Authorization | ⬜ |
| 7.1 | Content Type | ⬜ |
| 7.2 | Response Envelope | ⬜ |
| 7.3 | Pagination | ⬜ |
| 8.1 | HTTP Status Codes | ⬜ |
| 8.2 | Error Codes | ⬜ |
| 5.1 | URL Structure | ⬜ |
| 5.2 | Resource Mapping | ⬜ |
| 5.3 | Standard HTTP Methods | ⬜ |
| 5.5 | Standard Filtering & Sorting | ⬜ |
| 2.3 | Architecture: API-Mediated Agents | ⬜ |
| 2.6 | Bulk Operations | ⬜ |
| 2.7 | File Upload & Download | ⬜ |
| 5.4 | Persona Change Flags (HITL Sync) | ⬜ |
| 2.5 | Real-Time Communication: SSE | ⬜ |
| 2.4 | Chat Agent with Tools | ⬜ |
| 5.6 | Job Posting Ingest Endpoint | ⬜ |

---

## Phase 2: Agent Framework

### 2.1 LangGraph Foundation (REQ-007 §3)
**Status:** ⬜ Incomplete

*Shared agent infrastructure. Required before any specific agent.*

| § | Task | Status |
|---|------|--------|
| 3.1 | Why LangGraph | ⬜ |
| 3.2 | State Schema | ⬜ |
| 3.3 | Checkpointing & HITL | ⬜ |

---

### 2.2 Chat Agent (REQ-007 §4)
**Status:** ⬜ Incomplete

*User-facing conversational interface. Orchestrates other agents.*

| § | Task | Status |
|---|------|--------|
| 4.1 | Chat Agent — Responsibilities | ⬜ |
| 4.2 | Chat Agent — Tool Categories | ⬜ |
| 4.3 | Chat Agent — Intent Recognition | ⬜ |
| 4.4 | Chat Agent — Ambiguity Resolution | ⬜ |
| 4.5 | Chat Agent — Response Formatting | ⬜ |
| 15.1 | Graph Spec — Chat Agent | ⬜ |

---

### 2.3 Onboarding Agent (REQ-007 §5)
**Status:** ⬜ Incomplete

*Creates Persona from user interview. Required before job matching works.*

| § | Task | Status |
|---|------|--------|
| 5.1 | Onboarding Agent — Trigger Conditions | ⬜ |
| 5.2 | Onboarding Agent — Interview Flow | ⬜ |
| 5.3 | Onboarding Agent — Step Behaviors | ⬜ |
| 5.4 | Onboarding Agent — Checkpoint Handling | ⬜ |
| 5.5 | Onboarding Agent — Post-Onboarding Updates | ⬜ |
| 5.6 | Onboarding Agent — Prompt Templates | ⬜ |
| 15.2 | Graph Spec — Onboarding Agent | ⬜ |

---

### 2.4 Scouter Agent (REQ-007 §6 + REQ-003)
**Status:** ⬜ Incomplete

*Discovers and ingests jobs. Combines REQ-007 §6 (behavior) and REQ-003 (job schema logic).*

**From REQ-007 §6:**

| § | Task | Status |
|---|------|--------|
| 6.1 | Scouter Agent — Trigger Conditions | ⬜ |
| 6.2 | Scouter Agent — Polling Flow | ⬜ |
| 6.3 | Scouter Agent — Source Adapters | ⬜ |
| 6.4 | Scouter Agent — Skill & Culture Extraction | ⬜ |
| 6.5 | Scouter Agent — Ghost Detection | ⬜ |
| 6.6 | Scouter Agent — Deduplication Logic | ⬜ |
| 6.7 | Scouter Agent — Error Handling | ⬜ |
| 15.3 | Graph Spec — Scouter Agent | ⬜ |

**From REQ-003 (Job Posting Schema):**

| § | Task | Status |
|---|------|--------|
| 4.1 | MVP Sources | ⬜ |
| 4.2 | Source Registry (Global) | ⬜ |
| 4.2b | User Source Preferences | ⬜ |
| 4.3 | Agent Source Selection | ⬜ |
| 4.4 | Polling Configuration | ⬜ |
| 6.1 | Status Transitions | ⬜ |
| 7.1 | Ghost Detection — Purpose | ⬜ |
| 7.2 | Ghost Detection — Signals | ⬜ |
| 7.3 | Ghost Detection — Score Interpretation | ⬜ |
| 7.4 | Ghost Detection — Agent Communication | ⬜ |
| 7.5 | Ghost Detection — JSONB Structure | ⬜ |
| 8.1 | Repost Detection — Criteria | ⬜ |
| 8.2 | Repost Detection — Handling | ⬜ |
| 8.3 | Repost Detection — Agent Context | ⬜ |
| 9.1 | Deduplication — Within Same Source | ⬜ |
| 9.2 | Deduplication — Across Sources | ⬜ |
| 9.3 | Deduplication — Priority | ⬜ |
| 12.1 | Retention — Favorites Override | ⬜ |
| 12.2 | Retention — Expiration Detection | ⬜ |
| 13.1 | Workflow — Discovery Flow | ⬜ |
| 13.2 | Workflow — User Review Flow | ⬜ |

---

### 2.5 Scoring Engine (REQ-008)
**Status:** ⬜ Incomplete

*Calculates Fit/Stretch scores. Required BEFORE Strategist agent.*

| § | Task | Status |
|---|------|--------|
| 1.1 | Score Types | ⬜ |
| 1.2 | Scoring Philosophy | ⬜ |
| 6.1 | Embeddings — What Gets Embedded | ⬜ |
| 6.2 | Embeddings — Model | ⬜ |
| 6.3 | Embeddings — Persona Generation | ⬜ |
| 6.4 | Embeddings — Job Generation | ⬜ |
| 6.5 | Embeddings — Storage | ⬜ |
| 6.6 | Embeddings — Freshness Check | ⬜ |
| 3.1 | Non-Negotiables — Filter Rules | ⬜ |
| 3.2 | Non-Negotiables — Undisclosed Data Handling | ⬜ |
| 3.3 | Non-Negotiables — Filter Output | ⬜ |
| 4.1 | Fit Score — Component Weights | ⬜ |
| 4.2 | Fit Score — Hard Skills Match (40%) | ⬜ |
| 4.3 | Fit Score — Soft Skills Match (15%) | ⬜ |
| 4.4 | Fit Score — Experience Level (25%) | ⬜ |
| 4.5 | Fit Score — Role Title Match (10%) | ⬜ |
| 4.6 | Fit Score — Location/Logistics (10%) | ⬜ |
| 4.7 | Fit Score — Aggregation | ⬜ |
| 5.1 | Stretch Score — Component Weights | ⬜ |
| 5.2 | Stretch Score — Target Role Alignment (50%) | ⬜ |
| 5.3 | Stretch Score — Target Skills Exposure (40%) | ⬜ |
| 5.4 | Stretch Score — Growth Trajectory (10%) | ⬜ |
| 5.5 | Stretch Score — Aggregation | ⬜ |
| 7.1 | Interpretation — Fit Score Thresholds | ⬜ |
| 7.2 | Interpretation — Stretch Score Thresholds | ⬜ |
| 7.3 | Interpretation — Combined | ⬜ |
| 7.4 | Interpretation — Auto-Draft Threshold | ⬜ |
| 8.1 | Explanation — Components | ⬜ |
| 8.2 | Explanation — Generation Logic | ⬜ |
| 9.1 | Edge Cases — Missing Data | ⬜ |
| 9.2 | Edge Cases — Career Changers | ⬜ |
| 9.3 | Edge Cases — Entry-Level Users | ⬜ |
| 9.4 | Edge Cases — Executive Roles | ⬜ |
| 10.1 | Performance — Batch Scoring | ⬜ |
| 10.2 | Performance — Caching | ⬜ |
| 10.3 | Performance — Embedding Costs | ⬜ |
| 11.1 | Testing — Test Cases | ⬜ |
| 11.2 | Testing — Validation Approach | ⬜ |

---

### 2.6 Strategist Agent (REQ-007 §7)
**Status:** ⬜ Incomplete

*Applies scoring to jobs. Depends on REQ-008 (Scoring Engine).*

| § | Task | Status |
|---|------|--------|
| 7.1 | Strategist Agent — Trigger Conditions | ⬜ |
| 7.2 | Strategist Agent — Scoring Flow | ⬜ |
| 7.3 | Strategist Agent — Non-Negotiables Filtering | ⬜ |
| 7.4 | Strategist Agent — Embedding-Based Matching | ⬜ |
| 7.5 | Strategist Agent — Stretch Score | ⬜ |
| 7.6 | Strategist Agent — Prompt Templates | ⬜ |
| 15.4 | Graph Spec — Strategist Agent | ⬜ |

---

### 2.7 Ghostwriter Agent (REQ-007 §8 + REQ-010)
**Status:** ⬜ Incomplete

*Generates tailored content. Combines REQ-007 §8 (behavior) and REQ-010 (prompts).*

**From REQ-007 §8:**

| § | Task | Status |
|---|------|--------|
| 8.1 | Ghostwriter Agent — Trigger Conditions | ⬜ |
| 8.2 | Ghostwriter Agent — Generation Flow | ⬜ |
| 8.3 | Ghostwriter Agent — Base Resume Selection | ⬜ |
| 8.4 | Ghostwriter Agent — Tailoring Decision | ⬜ |
| 8.5 | Ghostwriter Agent — Cover Letter Generation | ⬜ |
| 8.6 | Ghostwriter Agent — Story Selection Logic | ⬜ |
| 8.7 | Ghostwriter Agent — Reasoning Explanation | ⬜ |
| 15.5 | Graph Spec — Ghostwriter Agent | ⬜ |

**From REQ-010 (Content Generation):**

| § | Task | Status |
|---|------|--------|
| 3.1 | Voice Profile Fields | ⬜ |
| 3.2 | Voice Application Rules | ⬜ |
| 3.3 | Voice Profile System Prompt Block | ⬜ |
| 4.1 | Resume — Tailoring Decision Logic | ⬜ |
| 4.2 | Resume — Summary Tailoring Prompt | ⬜ |
| 4.3 | Resume — Bullet Reordering Logic | ⬜ |
| 4.4 | Resume — Modification Limits (Guardrails) | ⬜ |
| 5.1 | Cover Letter — Structure | ⬜ |
| 5.2 | Cover Letter — Achievement Story Selection | ⬜ |
| 5.3 | Cover Letter — Generation Prompt | ⬜ |
| 5.4 | Cover Letter — Validation | ⬜ |
| 5.5 | Cover Letter — Output Schema | ⬜ |
| 6.1 | Utility Functions — Implementation Strategy | ⬜ |
| 6.2 | Utility Functions — extract_keywords | ⬜ |
| 6.3 | Utility Functions — extract_skills_from_text | ⬜ |
| 6.4 | Utility Functions — has_metrics/extract_metrics | ⬜ |
| 6.5 | Utility Functions — Caching Strategy | ⬜ |
| 7.1 | Regeneration — Feedback Categories | ⬜ |
| 7.2 | Regeneration — Feedback Sanitization | ⬜ |
| 7.3 | Regeneration — Prompt Modifier | ⬜ |
| 8.1 | Edge Cases — Insufficient Data | ⬜ |
| 8.2 | Edge Cases — Expired Job | ⬜ |
| 8.3 | Edge Cases — Persona Changed | ⬜ |
| 8.4 | Edge Cases — Duplicate Story Selection | ⬜ |
| 9.1 | Agent Reasoning — Template | ⬜ |
| 9.2 | Agent Reasoning — Example Output | ⬜ |
| 10.1 | Quality Metrics — Tracking | ⬜ |
| 10.2 | Quality Metrics — Feedback Loop | ⬜ |

---

### 2.8 Agent Communication (REQ-007 §9-11)
**Status:** ⬜ Incomplete

*Cross-cutting concerns for all agents.*

| § | Task | Status |
|---|------|--------|
| 9.1 | Communication — Agent-to-User | ⬜ |
| 9.2 | Communication — Agent-to-Agent | ⬜ |
| 9.3 | Communication — SSE Event Types | ⬜ |
| 10.1 | Error Handling — Transient Errors | ⬜ |
| 10.2 | Error Handling — Permanent Errors | ⬜ |
| 10.3 | Error Handling — Graceful Degradation | ⬜ |
| 10.4 | Error Handling — Concurrency & Race Conditions | ⬜ |
| 11.1 | Configuration — Environment Variables | ⬜ |
| 11.2 | Configuration — Model Routing | ⬜ |
| 15.6 | Graph Spec — Invocation Patterns | ⬜ |

---

## Phase 3: Document Generation

### 3.1 Resume Generation (REQ-002)
**Status:** ⬜ Incomplete

*PDF rendering and workflow. Depends on Ghostwriter for content.*

| § | Task | Status |
|---|------|--------|
| 4.1 | Resume File — Upload Handling | ⬜ |
| 4.2 | Base Resume — Rendered Document Storage | ⬜ |
| 4.3 | Job Variant — Snapshot Logic | ⬜ |
| 4.4 | Submitted PDF — Immutable Storage | ⬜ |
| 4.5 | Persona Change Flag — HITL Sync | ⬜ |
| 5.1 | Retention Rules | ⬜ |
| 5.4 | User Actions (Archive/Restore) | ⬜ |
| 6.1 | Workflow — Onboarding Flow | ⬜ |
| 6.2 | Workflow — Application Flow (Auto-Draft) | ⬜ |
| 6.3 | Workflow — Persona → Base Resume Sync | ⬜ |
| 6.4 | Workflow — PDF Generation (ReportLab) | ⬜ |
| 7.1 | Agent — Base Resume Selection | ⬜ |
| 7.2 | Agent — Tailoring Decision | ⬜ |
| 7.3 | Agent — Modification Limits | ⬜ |

---

### 3.2 Cover Letter Generation (REQ-002b)
**Status:** ⬜ Incomplete

*PDF rendering and workflow. Depends on Ghostwriter for content.*

| § | Task | Status |
|---|------|--------|
| 4.1 | Cover Letter — Field Implementation | ⬜ |
| 4.2 | Submitted Cover Letter PDF — Immutable Storage | ⬜ |
| 7.1 | Workflow — Generation Flow (Auto-Draft) | ⬜ |
| 7.2 | Workflow — Agent Story Selection | ⬜ |
| 7.3 | Workflow — User Editing | ⬜ |
| 7.4 | Workflow — Approval & PDF Generation | ⬜ |
| 8.1 | Agent — Cover Letter Structure | ⬜ |
| 8.2 | Agent — Voice Profile Application | ⬜ |
| 8.3 | Agent — Modification Limits | ⬜ |

---

## Phase 4: Extension

### 4.1 Chrome Extension (REQ-011)
**Status:** ⬜ Incomplete

*Browser-based job capture. Can be built in parallel after API is ready.*

| § | Task | Status |
|---|------|--------|
| 3.1 | Architecture — Component Overview | ⬜ |
| 3.2 | Architecture — Data Flow | ⬜ |
| 4.1 | UI — Extension States | ⬜ |
| 4.2 | UI — Popup Layout | ⬜ |
| 4.3 | UI — URL Badge System | ⬜ |
| 5.1 | Extraction — Text Extraction Strategy | ⬜ |
| 5.2 | Extraction — Page Detection Heuristics | ⬜ |
| 6.1 | API — Ingest Flow | ⬜ |
| 6.2 | API — Duplicate Detection | ⬜ |
| 6.3 | API — Error Handling | ⬜ |
| 7.1 | Auth — Local Mode (MVP) | ⬜ |
| 7.2 | Auth — Future Hosted Mode | ⬜ |
| 8.1 | Permissions — Required | ⬜ |
| 8.2 | Permissions — Optional | ⬜ |
| 9.1 | Edge Cases — Content Extraction Failures | ⬜ |
| 9.2 | Edge Cases — Network Issues | ⬜ |
| 9.3 | Edge Cases — Duplicate Handling | ⬜ |

---

## Implementation Notes for Coding Agent

### Critical: File Storage (REQ-005)

**Strict adherence required:** Files (resumes, PDFs) MUST be stored in PostgreSQL `BYTEA` columns. Do NOT refactor to filesystem paths or S3/object storage.

**Rationale:** Local-first MVP requires self-contained database. Backup/restore is just `pg_dump`. No external dependencies.

### Critical: Culture Text Flow (REQ-007 + REQ-008)

When implementing the Strategist (REQ-008), always pair with REQ-007 context. The soft skills matching flow is:

```
Raw Job Description
    ↓ Scouter extracts (REQ-007 §6.4)
culture_text field (stored on JobPosting)
    ↓ Strategist embeds (REQ-008 §6)
job_culture embedding (vector)
    ↓ compared against
persona_soft_skills embedding
```

Do NOT match soft skills against raw job description or general job embedding.

### Critical: pgvector ORM (REQ-005)

Use the `pgvector-python` library for SQLAlchemy/SQLModel integration. Key patterns:
- Vector columns: `from pgvector.sqlalchemy import Vector`
- Insertion: Pass Python lists directly (library handles formatting)
- Queries: Use `<=>` operator for cosine distance

Always run `CREATE EXTENSION vector` in Migration 000 (see REQ-005 §9.1).

### Shared Extraction Service (REQ-007)

Abstract the extraction logic in REQ-007 §6.3-6.4 into a shared service function callable by both the Scouter polling loop and the `/job-postings/ingest` API endpoint (REQ-006 §5.6).

### Raw Text Truncation (REQ-007)

Job posting `raw_text` can be massive (50k+ chars). Store full text in database for audit, but truncate to **15,000 characters** before sending to LLM extraction step (REQ-007 §6.3).

### Code Examples Are Prescriptive

All Python code in REQ-007, REQ-008, REQ-009, and REQ-010 should be implemented as written, including `# WHY` comments.

---

## Status Legend

| Icon | Meaning |
|------|---------|
| ⬜ | Incomplete |
| 🟡 | In Progress |
| ✅ | DONE |

---

## Quick Reference: Dependency Chain

```
Phase 1: Foundation
  REQ-005 Database ─┬─► REQ-009 Providers ─┬─► REQ-006 API
                    │                       │
Phase 2: Agents     │                       │
  REQ-007 §3 LangGraph Foundation ◄─────────┘
      │
      ├─► REQ-007 §4 Chat Agent
      │
      ├─► REQ-007 §5 Onboarding Agent
      │
      ├─► REQ-007 §6 Scouter + REQ-003
      │
      ├─► REQ-008 Scoring Engine
      │       │
      │       ▼
      ├─► REQ-007 §7 Strategist Agent
      │
      └─► REQ-007 §8 Ghostwriter + REQ-010
                │
Phase 3: Docs   │
      ┌─────────┘
      ├─► REQ-002 Resume Generation
      └─► REQ-002b Cover Letter Generation

Phase 4: Extension (parallel after REQ-006)
      └─► REQ-011 Chrome Extension
```
