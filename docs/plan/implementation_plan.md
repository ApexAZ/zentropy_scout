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

*Creates all database tables and migrations. Must complete before any other implementation.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-005 section for current task |
| 🧪 **TDD** | Write migration test first, then implement — follow `zentropy-tdd` (red-green-refactor) |
| 🗃️ **Patterns** | Use `zentropy-db` for postgres migrations, pgvector setup, BYTEA storage |
| ▶️ **Commands** | Run `alembic upgrade` / `alembic downgrade` — see `zentropy-commands` |
| ✅ **Verify** | Use `test-runner` agent to run migration tests (upgrade AND downgrade) |
| 🔍 **Review** | Use `code-reviewer` agent to check naming conventions before commit |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 8 | Extensions Required (pgvector) | `db, commands, tdd` | ⬜ |
| 9.1 | Migration Order | `db, tdd` | ⬜ |
| 9.2 | Circular Reference Note | `db, tdd` | ⬜ |
| 4.0 | User (Auth Foundation) | `db, tdd` | ⬜ |
| 4.1 | Persona Domain Tables | `db, tdd` | ⬜ |
| 4.2 | Resume Domain Tables | `db, tdd` | ⬜ |
| 4.3 | Cover Letter Domain Tables | `db, tdd` | ⬜ |
| 4.4 | Job Posting Domain Tables | `db, tdd` | ⬜ |
| 4.5 | Application Domain Tables | `db, tdd` | ⬜ |
| 5.1 | JSONB Schema — Persona Domain | `db` | ⬜ |
| 5.2 | JSONB Schema — Resume Domain | `db` | ⬜ |
| 5.3 | JSONB Schema — Job Posting Domain | `db` | ⬜ |
| 5.4 | JSONB Schema — Application Domain | `db` | ⬜ |
| 6 | Archive Implementation | `db, tdd` | ⬜ |
| 7 | Cleanup Jobs | `db, tdd, test` | ⬜ |
| 3 | Entity Relationship Diagram (validation) | `db` | ⬜ |

---

### 1.2 Provider Abstraction (REQ-009)
**Status:** ⬜ Incomplete

*LLM and embedding interfaces. Required before any agent implementation.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-009 section for current task |
| 🧪 **TDD** | Write interface test first, then implement — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Patterns** | Use `zentropy-provider` for Claude SDK, provider abstraction, embeddings |
| 🧪 **Mocking** | Use `zentropy-test` for mock providers and pytest fixtures |
| ✅ **Verify** | Use `test-runner` agent to run provider tests with mocked responses |
| 🔍 **Review** | Use `code-reviewer` agent to check interface consistency |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 3.1 | Layer Diagram | `structure` | ⬜ |
| 3.2 | Key Components | `structure` | ⬜ |
| 6.1 | ProviderConfig Class | `provider, tdd` | ⬜ |
| 6.2 | Environment Variables | `provider, tdd` | ⬜ |
| 6.3 | Provider Factory | `provider, structure, tdd` | ⬜ |
| 4.1 | LLM Abstract Interface | `provider, tdd` | ⬜ |
| 4.2 | Provider-Specific Adapters (Claude, OpenAI, Gemini) | `provider, tdd` | ⬜ |
| 4.3 | Model Routing Table | `provider` | ⬜ |
| 4.4 | Cost Estimates by Task | `provider` | ⬜ |
| 4.5 | Tool Calling Patterns | `provider, tdd` | ⬜ |
| 4.6 | JSON Mode Patterns | `provider, tdd` | ⬜ |
| 5.1 | Embedding Abstract Interface | `provider, db, tdd` | ⬜ |
| 5.2 | OpenAI Embedding Adapter | `provider, tdd` | ⬜ |
| 5.3 | Embedding Model Comparison | `provider` | ⬜ |
| 7.1 | Error Taxonomy | `provider, structure, tdd` | ⬜ |
| 7.2 | Retry Strategy | `provider, test, tdd` | ⬜ |
| 7.3 | Error Mapping | `provider, tdd` | ⬜ |
| 8.1 | Logging | `provider, structure` | ⬜ |
| 9.1 | Mock Provider | `provider, test, tdd` | ⬜ |
| 9.2 | Test Fixtures | `test, tdd` | ⬜ |
| 8.2 | Metrics (Future) | `provider` | ⬜ |
| 8.3 | Cost Tracking (Future) | `provider` | ⬜ |
| 10 | BYOK Support (Future) | `provider` | ⬜ |

---

### 1.3 API Scaffold (REQ-006)
**Status:** ⬜ Incomplete

*REST endpoints and auth. Required before agent tools can call the API.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-006 section for current task |
| 🧪 **TDD** | Write endpoint test first, then implement — follow `zentropy-tdd` (red-green-refactor) |
| 📂 **Structure** | Use `zentropy-structure` for module organization (routers, services, repositories) |
| 📝 **Docs** | Use `zentropy-docs` for docstrings on all public endpoints |
| ✅ **Verify** | Use `test-runner` agent to run API tests with httpx AsyncClient |
| 🔍 **Review** | Use `code-reviewer` agent to check REST conventions and response shapes |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 2.1 | API Style: REST | `structure, docs` | ⬜ |
| 2.2 | Deployment Model: Local-First | `structure` | ⬜ |
| 6.1 | Authentication | `structure, tdd` | ⬜ |
| 6.2 | Authorization | `structure, tdd` | ⬜ |
| 7.1 | Content Type | `structure, tdd` | ⬜ |
| 7.2 | Response Envelope | `structure, tdd` | ⬜ |
| 7.3 | Pagination | `structure, tdd` | ⬜ |
| 8.1 | HTTP Status Codes | `structure, tdd` | ⬜ |
| 8.2 | Error Codes | `structure, tdd` | ⬜ |
| 5.1 | URL Structure | `structure, tdd` | ⬜ |
| 5.2 | Resource Mapping | `structure, tdd, docs` | ⬜ |
| 5.3 | Standard HTTP Methods | `structure, tdd` | ⬜ |
| 5.5 | Standard Filtering & Sorting | `structure, tdd` | ⬜ |
| 2.3 | Architecture: API-Mediated Agents | `structure, docs` | ⬜ |
| 2.6 | Bulk Operations | `structure, tdd` | ⬜ |
| 2.7 | File Upload & Download | `structure, tdd, db` | ⬜ |
| 5.4 | Persona Change Flags (HITL Sync) | `structure, tdd, db` | ⬜ |
| 2.5 | Real-Time Communication: SSE | `structure, tdd, provider` | ⬜ |
| 2.4 | Chat Agent with Tools | `structure, tdd, provider` | ⬜ |
| 5.6 | Job Posting Ingest Endpoint | `structure, tdd, db` | ⬜ |

---

## Phase 2: Agent Framework

### 2.1 LangGraph Foundation (REQ-007 §3)
**Status:** ⬜ Incomplete

*Shared agent infrastructure. Required before any specific agent.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §3 for LangGraph patterns |
| 🧪 **TDD** | Write state schema tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Patterns** | Use `zentropy-provider` for LLM integration patterns |
| 🧪 **Mocking** | Use `zentropy-test` for mock checkpointing and state fixtures |
| ✅ **Verify** | Use `test-runner` agent to verify state transitions |
| 🔍 **Review** | Use `code-reviewer` agent to check graph structure |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 3.1 | Why LangGraph | `docs` | ⬜ |
| 3.2 | State Schema | `provider, structure, tdd` | ⬜ |
| 3.3 | Checkpointing & HITL | `provider, db, tdd` | ⬜ |

---

### 2.2 Chat Agent (REQ-007 §4)
**Status:** ⬜ Incomplete

*User-facing conversational interface. Orchestrates other agents.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §4 for chat agent spec |
| 🧪 **TDD** | Write intent recognition tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Patterns** | Use `zentropy-provider` for Claude SDK conversation patterns |
| 📝 **Docs** | Use `zentropy-docs` for tool docstrings (agents read these) |
| 🧪 **Mocking** | Use `zentropy-test` for mock tool responses |
| ✅ **Verify** | Use `test-runner` agent to verify tool routing |
| 🔍 **Review** | Use `code-reviewer` agent to check response formatting |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 4.1 | Chat Agent — Responsibilities | `provider, docs` | ⬜ |
| 4.2 | Chat Agent — Tool Categories | `provider, structure, tdd` | ⬜ |
| 4.3 | Chat Agent — Intent Recognition | `provider, tdd` | ⬜ |
| 4.4 | Chat Agent — Ambiguity Resolution | `provider, tdd` | ⬜ |
| 4.5 | Chat Agent — Response Formatting | `provider, tdd` | ⬜ |
| 15.1 | Graph Spec — Chat Agent | `provider, structure, tdd` | ⬜ |

---

### 2.3 Onboarding Agent (REQ-007 §5)
**Status:** ⬜ Incomplete

*Creates Persona from user interview. Required before job matching works.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §5 for onboarding flow |
| 🧪 **TDD** | Write interview step tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Patterns** | Use `zentropy-provider` for conversational extraction prompts |
| 🗃️ **Storage** | Use `zentropy-db` for persona creation and checkpoint persistence |
| 🧪 **Mocking** | Use `zentropy-test` for mock user responses |
| ✅ **Verify** | Use `test-runner` agent to verify persona completeness |
| 🔍 **Review** | Use `code-reviewer` agent to check prompt templates |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 5.1 | Onboarding Agent — Trigger Conditions | `provider, tdd` | ⬜ |
| 5.2 | Onboarding Agent — Interview Flow | `provider, tdd` | ⬜ |
| 5.3 | Onboarding Agent — Step Behaviors | `provider, db, tdd` | ⬜ |
| 5.4 | Onboarding Agent — Checkpoint Handling | `provider, db, tdd` | ⬜ |
| 5.5 | Onboarding Agent — Post-Onboarding Updates | `provider, db, tdd` | ⬜ |
| 5.6 | Onboarding Agent — Prompt Templates | `provider, docs, tdd` | ⬜ |
| 15.2 | Graph Spec — Onboarding Agent | `provider, structure, tdd` | ⬜ |

---

### 2.4 Scouter Agent (REQ-007 §6 + REQ-003)
**Status:** ⬜ Incomplete

*Discovers and ingests jobs. Combines REQ-007 §6 (behavior) and REQ-003 (job schema logic).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §6 AND REQ-003 for full context |
| 🧪 **TDD** | Write extraction tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Patterns** | Use `zentropy-provider` for skill/culture extraction prompts |
| 🗃️ **Storage** | Use `zentropy-db` for job posting storage and deduplication queries |
| 🧪 **Mocking** | Use `zentropy-test` for mock job board responses |
| ✅ **Verify** | Use `test-runner` agent to verify ghost detection and dedup logic |
| 🔍 **Review** | Use `code-reviewer` agent to check source adapter patterns |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

**From REQ-007 §6:**

| § | Task | Hints | Status |
|---|------|-------|--------|
| 6.1 | Scouter Agent — Trigger Conditions | `provider, tdd` | ⬜ |
| 6.2 | Scouter Agent — Polling Flow | `provider, db, tdd` | ⬜ |
| 6.3 | Scouter Agent — Source Adapters | `provider, structure, tdd` | ⬜ |
| 6.4 | Scouter Agent — Skill & Culture Extraction | `provider, tdd` | ⬜ |
| 6.5 | Scouter Agent — Ghost Detection | `db, test, tdd` | ⬜ |
| 6.6 | Scouter Agent — Deduplication Logic | `db, test, tdd` | ⬜ |
| 6.7 | Scouter Agent — Error Handling | `provider, test, tdd` | ⬜ |
| 15.3 | Graph Spec — Scouter Agent | `provider, structure, tdd` | ⬜ |

**From REQ-003 (Job Posting Schema):**

| § | Task | Hints | Status |
|---|------|-------|--------|
| 4.1 | MVP Sources | `provider, docs` | ⬜ |
| 4.2 | Source Registry (Global) | `db, tdd` | ⬜ |
| 4.2b | User Source Preferences | `db, tdd` | ⬜ |
| 4.3 | Agent Source Selection | `provider, db, tdd` | ⬜ |
| 4.4 | Polling Configuration | `db, tdd` | ⬜ |
| 6.1 | Status Transitions | `db, tdd` | ⬜ |
| 7.1 | Ghost Detection — Purpose | `docs` | ⬜ |
| 7.2 | Ghost Detection — Signals | `provider, tdd` | ⬜ |
| 7.3 | Ghost Detection — Score Interpretation | `provider, tdd` | ⬜ |
| 7.4 | Ghost Detection — Agent Communication | `provider, tdd` | ⬜ |
| 7.5 | Ghost Detection — JSONB Structure | `db, tdd` | ⬜ |
| 8.1 | Repost Detection — Criteria | `db, tdd` | ⬜ |
| 8.2 | Repost Detection — Handling | `db, tdd` | ⬜ |
| 8.3 | Repost Detection — Agent Context | `provider, tdd` | ⬜ |
| 9.1 | Deduplication — Within Same Source | `db, test, tdd` | ⬜ |
| 9.2 | Deduplication — Across Sources | `db, test, tdd` | ⬜ |
| 9.3 | Deduplication — Priority | `db, tdd` | ⬜ |
| 12.1 | Retention — Favorites Override | `db, tdd` | ⬜ |
| 12.2 | Retention — Expiration Detection | `db, tdd` | ⬜ |
| 13.1 | Workflow — Discovery Flow | `provider, structure, tdd` | ⬜ |
| 13.2 | Workflow — User Review Flow | `structure, tdd` | ⬜ |

---

### 2.5 Scoring Engine (REQ-008)
**Status:** ⬜ Incomplete

*Calculates Fit/Stretch scores. Required BEFORE Strategist agent.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-008 for scoring algorithms |
| 🧪 **TDD** | Write score calculation tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🗃️ **Embeddings** | Use `zentropy-db` for pgvector storage and cosine similarity queries |
| 🤖 **Patterns** | Use `zentropy-provider` for embedding generation (OpenAI) |
| 🧪 **Mocking** | Use `zentropy-test` for mock embeddings and score fixtures |
| ✅ **Verify** | Use `test-runner` agent to verify edge cases (missing data, career changers) |
| 🔍 **Review** | Use `code-reviewer` agent to check weight calculations |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1.1 | Score Types | `docs` | ⬜ |
| 1.2 | Scoring Philosophy | `docs` | ⬜ |
| 6.1 | Embeddings — What Gets Embedded | `db, docs` | ⬜ |
| 6.2 | Embeddings — Model | `provider, docs` | ⬜ |
| 6.3 | Embeddings — Persona Generation | `provider, db, tdd` | ⬜ |
| 6.4 | Embeddings — Job Generation | `provider, db, tdd` | ⬜ |
| 6.5 | Embeddings — Storage | `db, tdd` | ⬜ |
| 6.6 | Embeddings — Freshness Check | `db, tdd` | ⬜ |
| 3.1 | Non-Negotiables — Filter Rules | `db, tdd` | ⬜ |
| 3.2 | Non-Negotiables — Undisclosed Data Handling | `tdd` | ⬜ |
| 3.3 | Non-Negotiables — Filter Output | `structure, tdd` | ⬜ |
| 4.1 | Fit Score — Component Weights | `docs` | ⬜ |
| 4.2 | Fit Score — Hard Skills Match (40%) | `db, tdd` | ⬜ |
| 4.3 | Fit Score — Soft Skills Match (15%) | `db, tdd` | ⬜ |
| 4.4 | Fit Score — Experience Level (25%) | `tdd` | ⬜ |
| 4.5 | Fit Score — Role Title Match (10%) | `db, tdd` | ⬜ |
| 4.6 | Fit Score — Location/Logistics (10%) | `tdd` | ⬜ |
| 4.7 | Fit Score — Aggregation | `tdd` | ⬜ |
| 5.1 | Stretch Score — Component Weights | `docs` | ⬜ |
| 5.2 | Stretch Score — Target Role Alignment (50%) | `provider, db, tdd` | ⬜ |
| 5.3 | Stretch Score — Target Skills Exposure (40%) | `provider, db, tdd` | ⬜ |
| 5.4 | Stretch Score — Growth Trajectory (10%) | `provider, tdd` | ⬜ |
| 5.5 | Stretch Score — Aggregation | `tdd` | ⬜ |
| 7.1 | Interpretation — Fit Score Thresholds | `tdd` | ⬜ |
| 7.2 | Interpretation — Stretch Score Thresholds | `tdd` | ⬜ |
| 7.3 | Interpretation — Combined | `tdd` | ⬜ |
| 7.4 | Interpretation — Auto-Draft Threshold | `tdd` | ⬜ |
| 8.1 | Explanation — Components | `provider, tdd` | ⬜ |
| 8.2 | Explanation — Generation Logic | `provider, tdd` | ⬜ |
| 9.1 | Edge Cases — Missing Data | `test, tdd` | ⬜ |
| 9.2 | Edge Cases — Career Changers | `test, tdd` | ⬜ |
| 9.3 | Edge Cases — Entry-Level Users | `test, tdd` | ⬜ |
| 9.4 | Edge Cases — Executive Roles | `test, tdd` | ⬜ |
| 10.1 | Performance — Batch Scoring | `db, test, tdd` | ⬜ |
| 10.2 | Performance — Caching | `db, tdd` | ⬜ |
| 10.3 | Performance — Embedding Costs | `provider, docs` | ⬜ |
| 11.1 | Testing — Test Cases | `test, tdd` | ⬜ |
| 11.2 | Testing — Validation Approach | `test, docs` | ⬜ |

---

### 2.6 Strategist Agent (REQ-007 §7)
**Status:** ⬜ Incomplete

*Applies scoring to jobs. Depends on REQ-008 (Scoring Engine).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §7 AND REQ-008 for scoring context |
| 🧪 **TDD** | Write filtering/scoring tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🗃️ **Queries** | Use `zentropy-db` for embedding similarity and non-negotiables filtering |
| 🤖 **Patterns** | Use `zentropy-provider` for stretch score prompts |
| 🧪 **Mocking** | Use `zentropy-test` for mock scoring engine responses |
| ✅ **Verify** | Use `test-runner` agent to verify non-negotiables filter correctly |
| 🔍 **Review** | Use `code-reviewer` agent to check score thresholds |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 7.1 | Strategist Agent — Trigger Conditions | `provider, tdd` | ⬜ |
| 7.2 | Strategist Agent — Scoring Flow | `provider, structure, tdd` | ⬜ |
| 7.3 | Strategist Agent — Non-Negotiables Filtering | `db, tdd` | ⬜ |
| 7.4 | Strategist Agent — Embedding-Based Matching | `db, provider, tdd` | ⬜ |
| 7.5 | Strategist Agent — Stretch Score | `provider, tdd` | ⬜ |
| 7.6 | Strategist Agent — Prompt Templates | `provider, docs, tdd` | ⬜ |
| 15.4 | Graph Spec — Strategist Agent | `provider, structure, tdd` | ⬜ |

---

### 2.7 Ghostwriter Agent (REQ-007 §8 + REQ-010)
**Status:** ⬜ Incomplete

*Generates tailored content. Combines REQ-007 §8 (behavior) and REQ-010 (prompts).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §8 AND REQ-010 for full context |
| 🧪 **TDD** | Write content generation tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Patterns** | Use `zentropy-provider` for generation prompts with voice profiles |
| 📝 **Docs** | Use `zentropy-docs` for prompt template documentation |
| 🧪 **Mocking** | Use `zentropy-test` for mock LLM responses |
| ✅ **Verify** | Use `test-runner` agent to verify guardrails (no fabrication) |
| 🔍 **Review** | Use `code-reviewer` agent to check prompt structure |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

**From REQ-007 §8:**

| § | Task | Hints | Status |
|---|------|-------|--------|
| 8.1 | Ghostwriter Agent — Trigger Conditions | `provider, tdd` | ⬜ |
| 8.2 | Ghostwriter Agent — Generation Flow | `provider, structure, tdd` | ⬜ |
| 8.3 | Ghostwriter Agent — Base Resume Selection | `db, tdd` | ⬜ |
| 8.4 | Ghostwriter Agent — Tailoring Decision | `provider, tdd` | ⬜ |
| 8.5 | Ghostwriter Agent — Cover Letter Generation | `provider, tdd` | ⬜ |
| 8.6 | Ghostwriter Agent — Story Selection Logic | `db, provider, tdd` | ⬜ |
| 8.7 | Ghostwriter Agent — Reasoning Explanation | `provider, tdd` | ⬜ |
| 15.5 | Graph Spec — Ghostwriter Agent | `provider, structure, tdd` | ⬜ |

**From REQ-010 (Content Generation):**

| § | Task | Hints | Status |
|---|------|-------|--------|
| 3.1 | Voice Profile Fields | `db, docs` | ⬜ |
| 3.2 | Voice Application Rules | `provider, tdd` | ⬜ |
| 3.3 | Voice Profile System Prompt Block | `provider, docs, tdd` | ⬜ |
| 4.1 | Resume — Tailoring Decision Logic | `provider, tdd` | ⬜ |
| 4.2 | Resume — Summary Tailoring Prompt | `provider, docs, tdd` | ⬜ |
| 4.3 | Resume — Bullet Reordering Logic | `tdd` | ⬜ |
| 4.4 | Resume — Modification Limits (Guardrails) | `provider, test, tdd` | ⬜ |
| 5.1 | Cover Letter — Structure | `docs` | ⬜ |
| 5.2 | Cover Letter — Achievement Story Selection | `db, provider, tdd` | ⬜ |
| 5.3 | Cover Letter — Generation Prompt | `provider, docs, tdd` | ⬜ |
| 5.4 | Cover Letter — Validation | `provider, test, tdd` | ⬜ |
| 5.5 | Cover Letter — Output Schema | `structure, tdd` | ⬜ |
| 6.1 | Utility Functions — Implementation Strategy | `structure, docs` | ⬜ |
| 6.2 | Utility Functions — extract_keywords | `provider, tdd` | ⬜ |
| 6.3 | Utility Functions — extract_skills_from_text | `provider, tdd` | ⬜ |
| 6.4 | Utility Functions — has_metrics/extract_metrics | `tdd` | ⬜ |
| 6.5 | Utility Functions — Caching Strategy | `db, tdd` | ⬜ |
| 7.1 | Regeneration — Feedback Categories | `docs` | ⬜ |
| 7.2 | Regeneration — Feedback Sanitization | `provider, tdd` | ⬜ |
| 7.3 | Regeneration — Prompt Modifier | `provider, tdd` | ⬜ |
| 8.1 | Edge Cases — Insufficient Data | `test, tdd` | ⬜ |
| 8.2 | Edge Cases — Expired Job | `test, tdd` | ⬜ |
| 8.3 | Edge Cases — Persona Changed | `db, test, tdd` | ⬜ |
| 8.4 | Edge Cases — Duplicate Story Selection | `test, tdd` | ⬜ |
| 9.1 | Agent Reasoning — Template | `provider, docs, tdd` | ⬜ |
| 9.2 | Agent Reasoning — Example Output | `docs` | ⬜ |
| 10.1 | Quality Metrics — Tracking | `db, tdd` | ⬜ |
| 10.2 | Quality Metrics — Feedback Loop | `db, structure, tdd` | ⬜ |

---

### 2.8 Agent Communication (REQ-007 §9-11)
**Status:** ⬜ Incomplete

*Cross-cutting concerns for all agents.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §9-11 for communication patterns |
| 🧪 **TDD** | Write SSE event tests first — follow `zentropy-tdd` (red-green-refactor) |
| 📂 **Structure** | Use `zentropy-structure` for shared module organization |
| 🤖 **Patterns** | Use `zentropy-provider` for model routing configuration |
| 🧪 **Mocking** | Use `zentropy-test` for mock event streams |
| ✅ **Verify** | Use `test-runner` agent to verify error handling and retries |
| 🔍 **Review** | Use `code-reviewer` agent to check event type consistency |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 9.1 | Communication — Agent-to-User | `provider, structure, tdd` | ⬜ |
| 9.2 | Communication — Agent-to-Agent | `provider, structure, tdd` | ⬜ |
| 9.3 | Communication — SSE Event Types | `structure, tdd` | ⬜ |
| 10.1 | Error Handling — Transient Errors | `provider, test, tdd` | ⬜ |
| 10.2 | Error Handling — Permanent Errors | `provider, test, tdd` | ⬜ |
| 10.3 | Error Handling — Graceful Degradation | `provider, test, tdd` | ⬜ |
| 10.4 | Error Handling — Concurrency & Race Conditions | `db, test, tdd` | ⬜ |
| 11.1 | Configuration — Environment Variables | `structure, docs` | ⬜ |
| 11.2 | Configuration — Model Routing | `provider, tdd` | ⬜ |
| 15.6 | Graph Spec — Invocation Patterns | `provider, structure, tdd` | ⬜ |

---

## Phase 3: Document Generation

### 3.1 Resume Generation (REQ-002)
**Status:** ⬜ Incomplete

*PDF rendering and workflow. Depends on Ghostwriter for content.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-002 for resume workflow |
| 🧪 **TDD** | Write PDF generation tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🗃️ **Storage** | Use `zentropy-db` for BYTEA storage (PDFs stored in database, NOT filesystem) |
| 📂 **Structure** | Use `zentropy-structure` for ReportLab service organization |
| 🧪 **Mocking** | Use `zentropy-test` for mock persona/job data |
| ✅ **Verify** | Use `test-runner` agent to verify PDF renders correctly |
| 🔍 **Review** | Use `code-reviewer` agent to check BYTEA storage patterns |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 4.1 | Resume File — Upload Handling | `db, structure, tdd` | ⬜ |
| 4.2 | Base Resume — Rendered Document Storage | `db, tdd` | ⬜ |
| 4.3 | Job Variant — Snapshot Logic | `db, tdd` | ⬜ |
| 4.4 | Submitted PDF — Immutable Storage | `db, tdd` | ⬜ |
| 4.5 | Persona Change Flag — HITL Sync | `db, tdd` | ⬜ |
| 5.1 | Retention Rules | `db, tdd` | ⬜ |
| 5.4 | User Actions (Archive/Restore) | `db, tdd` | ⬜ |
| 6.1 | Workflow — Onboarding Flow | `structure, tdd` | ⬜ |
| 6.2 | Workflow — Application Flow (Auto-Draft) | `structure, tdd` | ⬜ |
| 6.3 | Workflow — Persona → Base Resume Sync | `db, tdd` | ⬜ |
| 6.4 | Workflow — PDF Generation (ReportLab) | `structure, test, tdd` | ⬜ |
| 7.1 | Agent — Base Resume Selection | `provider, db, tdd` | ⬜ |
| 7.2 | Agent — Tailoring Decision | `provider, tdd` | ⬜ |
| 7.3 | Agent — Modification Limits | `provider, test, tdd` | ⬜ |

---

### 3.2 Cover Letter Generation (REQ-002b)
**Status:** ⬜ Incomplete

*PDF rendering and workflow. Depends on Ghostwriter for content.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-002b for cover letter workflow |
| 🧪 **TDD** | Write PDF generation tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🗃️ **Storage** | Use `zentropy-db` for BYTEA storage (PDFs stored in database, NOT filesystem) |
| 📂 **Structure** | Use `zentropy-structure` for ReportLab service organization |
| 🧪 **Mocking** | Use `zentropy-test` for mock story/job data |
| ✅ **Verify** | Use `test-runner` agent to verify PDF renders correctly |
| 🔍 **Review** | Use `code-reviewer` agent to check voice profile application |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 4.1 | Cover Letter — Field Implementation | `db, tdd` | ⬜ |
| 4.2 | Submitted Cover Letter PDF — Immutable Storage | `db, tdd` | ⬜ |
| 7.1 | Workflow — Generation Flow (Auto-Draft) | `structure, tdd` | ⬜ |
| 7.2 | Workflow — Agent Story Selection | `provider, db, tdd` | ⬜ |
| 7.3 | Workflow — User Editing | `structure, tdd` | ⬜ |
| 7.4 | Workflow — Approval & PDF Generation | `structure, test, tdd` | ⬜ |
| 8.1 | Agent — Cover Letter Structure | `provider, docs, tdd` | ⬜ |
| 8.2 | Agent — Voice Profile Application | `provider, tdd` | ⬜ |
| 8.3 | Agent — Modification Limits | `provider, test, tdd` | ⬜ |

---

## Phase 4: Extension

### 4.1 Chrome Extension (REQ-011)
**Status:** ⬜ Incomplete

*Browser-based job capture. Can be built in parallel after API is ready.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-011 for extension spec |
| 🧪 **TDD** | Write extraction tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🎭 **E2E** | Use `zentropy-playwright` for extension UI testing (mock API responses) |
| 📂 **Structure** | Use `zentropy-structure` for Manifest V3 component organization |
| 🧪 **Mocking** | Use `zentropy-test` for mock job page HTML |
| ✅ **Verify** | Use `test-runner` agent to verify extraction accuracy |
| 🔍 **Review** | Use `code-reviewer` agent to check permission scope |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 3.1 | Architecture — Component Overview | `structure, docs` | ⬜ |
| 3.2 | Architecture — Data Flow | `structure, docs` | ⬜ |
| 4.1 | UI — Extension States | `playwright, tdd` | ⬜ |
| 4.2 | UI — Popup Layout | `playwright, tdd` | ⬜ |
| 4.3 | UI — URL Badge System | `playwright, tdd` | ⬜ |
| 5.1 | Extraction — Text Extraction Strategy | `test, tdd` | ⬜ |
| 5.2 | Extraction — Page Detection Heuristics | `test, tdd` | ⬜ |
| 6.1 | API — Ingest Flow | `structure, tdd` | ⬜ |
| 6.2 | API — Duplicate Detection | `db, tdd` | ⬜ |
| 6.3 | API — Error Handling | `test, tdd` | ⬜ |
| 7.1 | Auth — Local Mode (MVP) | `structure, tdd` | ⬜ |
| 7.2 | Auth — Future Hosted Mode | `docs` | ⬜ |
| 8.1 | Permissions — Required | `docs` | ⬜ |
| 8.2 | Permissions — Optional | `docs` | ⬜ |
| 9.1 | Edge Cases — Content Extraction Failures | `test, tdd` | ⬜ |
| 9.2 | Edge Cases — Network Issues | `test, tdd` | ⬜ |
| 9.3 | Edge Cases — Duplicate Handling | `db, test, tdd` | ⬜ |

---

## Implementation Notes for Coding Agent

### Critical: Claude Agent SDK for Local Mode (REQ-009 §1.5)

**MVP uses Claude Agent SDK, not direct API calls.** The SDK wraps the user's Claude subscription.

**Package:** `pip install claude-agent-sdk`

**Key documentation (read before implementing REQ-009):**
- Overview: https://platform.claude.com/docs/en/agent-sdk/overview
- Python SDK: https://platform.claude.com/docs/en/agent-sdk/python
- Structured outputs: https://platform.claude.com/docs/en/agent-sdk/structured-outputs
- Custom tools (MCP): https://platform.claude.com/docs/en/agent-sdk/custom-tools

**Key patterns:**
```python
from claude_agent_sdk import query, ClaudeAgentOptions

# Structured output with Pydantic
async for message in query(
    prompt="...",
    options=ClaudeAgentOptions(
        system_prompt="...",
        max_turns=1,
        output_format={"type": "json_schema", "schema": MyModel.model_json_schema()}
    )
):
    if message.type == "result" and message.structured_output:
        result = MyModel.model_validate(message.structured_output)
```

**Note:** Embeddings still require OpenAI API key (`OPENAI_API_KEY`) even in local mode — there is no subscription-based embedding option.

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
