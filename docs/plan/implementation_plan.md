# Zentropy Scout — Implementation Plan

**Created:** 2026-01-25
**Last Updated:** 2026-01-29
**Status:** Ready for Implementation

---

## How to Use This Document

**Tracking:** Each requirement has a status, and each subsection has its own status. When resuming after compaction or a new session, find the first 🟡 (In Progress) or ⬜ (Incomplete) item.

**Context Management:** Load only the REQ section being worked on, not the entire document. Each subsection is designed to be a single unit of work.  Coding agent should pick up the very first task in Progress, or TO DO.  Coding agent should mark the task complete as soon as it's complete.  TRACKING IS VERY IMPORTANT FOR CONTEXT CONTINUITY.

**Order:** Sections are ordered by implementation dependency, not document number. Follow top-to-bottom.

Requirements location: `docs/requirements/`

---

## Phase 0: Project Bootstrap

**Status:** ✅ Complete

*One-time setup. Creates folder structure, installs dependencies, initializes database tooling.*

### 0.1 Manual Prerequisites (User)
**Status:** ✅ Complete

These steps require user action outside Claude Code:

| Task | Command / Action | Status |
|------|------------------|--------|
| Enable Docker in WSL | Docker Desktop → Settings → Resources → WSL Integration → Enable Ubuntu | ✅ |
| Start Docker Desktop | Launch Docker Desktop application | ✅ |
| Copy environment file | `cp .env.example .env, plan` | ✅ |

### 0.2 Project Scaffold (Agent)
**Status:** ✅ Complete

*Creates backend folder structure and configuration files.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read `zentropy-structure` skill for folder layout and `pyproject.toml` template |
| 📂 **Create** | Create all folders per `zentropy-structure` skill |
| 📝 **Config** | Create `pyproject.toml`, `alembic.ini` from skill templates |
| ▶️ **Commands** | See `zentropy-commands` for alembic init |
| ✅ **Verify** | Folder structure matches skill diagram |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 0.2.1 | Create `backend/` folder structure | `structure, commands, plan` | ✅ |
| 0.2.2 | Create `backend/pyproject.toml` | `structure, plan` | ✅ |
| 0.2.3 | Create `backend/alembic.ini` | `db, commands, plan` | ✅ |
| 0.2.4 | Initialize alembic (`alembic init migrations`) | `db, commands, plan` | ✅ |
| 0.2.5 | Create `backend/app/__init__.py` (empty) | `structure, plan` | ✅ |
| 0.2.6 | Create `backend/app/core/__init__.py` | `structure, plan` | ✅ |
| 0.2.7 | Create `backend/app/core/config.py` (Settings class) | `structure, tdd, plan` | ✅ |
| 0.2.8 | Create `backend/app/core/database.py` (engine, session) | `db, structure, tdd, plan` | ✅ |
| 0.2.9 | Create `backend/app/models/__init__.py` | `structure, plan` | ✅ |
| 0.2.10 | Create `backend/app/models/base.py` (Base class, mixins) | `db, structure, tdd, plan` | ✅ |
| 0.2.11 | Create `backend/tests/conftest.py` | `test, structure, plan` | ✅ |

### 0.3 Dependency Installation (Agent)
**Status:** ✅ Complete

*Installs Python packages and verifies environment.*

#### Workflow
| Step | Action |
|------|--------|
| ▶️ **Commands** | See `zentropy-commands` for venv and pip commands |
| ✅ **Verify** | `pip list` shows all required packages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 0.3.1 | Create virtual environment (`python -m venv .venv`) | `commands, plan` | ✅ |
| 0.3.2 | Install dependencies (`pip install -e ".[dev]"`) | `commands, plan` | ✅ |
| 0.3.3 | Verify ruff installed (`ruff --version`) | `commands, plan` | ✅ |
| 0.3.4 | Verify pytest installed (`pytest --version`) | `commands, plan` | ✅ |

### 0.4 Database Setup (Agent)
**Status:** ✅ Complete

*Starts PostgreSQL and verifies connection.*

#### Workflow
| Step | Action |
|------|--------|
| ▶️ **Commands** | See `zentropy-commands` for docker compose |
| ✅ **Verify** | Can connect to database with psql |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 0.4.1 | Start PostgreSQL (`docker compose up -d`) | `commands, plan` | ✅ |
| 0.4.2 | Verify PostgreSQL running (`docker compose ps`) | `commands, plan` | ✅ |
| 0.4.3 | Test connection (`docker compose exec postgres psql ...`) | `db, commands, plan` | ✅ |
| 0.4.4 | Verify pgvector extension available | `db, commands, plan` | ✅ |

### 0.5 Smoke Test (Agent)
**Status:** ✅ Complete

*Verifies everything works together.*

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 0.5.1 | Run `alembic current` (should show no migrations) | `db, commands, plan` | ✅ |
| 0.5.2 | Run `pytest` (should pass with 0 tests collected) | `test, commands, plan` | ✅ |
| 0.5.3 | Run `ruff check backend/` (should pass) | `commands, plan` | ✅ |

---

## Phase 1: Foundation

### 1.1 Database Schema (REQ-005)
**Status:** ✅ Complete

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
| 8 | Extensions Required (pgvector) | `db, commands, tdd, plan` | ✅ |
| 9.1 | Migration Order | `db, tdd, plan` | ✅ |
| 9.2 | Circular Reference Note | `db, tdd, plan` | ✅ |
| 4.0 | User (Auth Foundation) | `db, tdd, plan` | ✅ |
| 4.1 | Persona Domain Tables | `db, tdd, plan` | ✅ |
| 4.2 | Resume Domain Tables | `db, tdd, plan` | ✅ |
| 4.3 | Cover Letter Domain Tables | `db, tdd, plan` | ✅ |
| 4.4 | Job Posting Domain Tables | `db, tdd, plan` | ✅ |
| 4.5 | Application Domain Tables | `db, tdd, plan` | ✅ |
| 5.1 | JSONB Schema — Persona Domain | `db, plan` | ✅ |
| 5.2 | JSONB Schema — Resume Domain | `db, plan` | ✅ |
| 5.3 | JSONB Schema — Job Posting Domain | `db, plan` | ✅ |
| 5.4 | JSONB Schema — Application Domain | `db, plan` | ✅ |
| 6 | Archive Implementation | `db, tdd, plan` | ✅ |
| 7 | Cleanup Jobs | `db, tdd, test, plan` | ✅ |
| 3 | Entity Relationship Diagram (validation) | `db, plan` | ✅ |

---

### 1.2 Provider Abstraction (REQ-009)
**Status:** 🟡 In Progress (17/20 tasks complete, 3 Future)

*LLM and embedding interfaces. Required before any agent implementation.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-009 section for current task |
| 🧪 **TDD** | Write interface test first, then implement — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Patterns** | Use `zentropy-provider` for Claude SDK, provider abstraction, embeddings; `zentropy-structure` for ABC folder organization |
| 🧪 **Mocking** | Use `zentropy-test` for mock providers and pytest fixtures |
| ✅ **Verify** | Use `test-runner` agent to run provider tests with mocked responses |
| 🔍 **Review** | Use `code-reviewer` agent to check interface consistency |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 3.1 | Layer Diagram | `structure, plan` | ✅ |
| 3.2 | Key Components | `structure, plan` | ✅ |
| 6.1 | ProviderConfig Class | `provider, tdd, plan` | ✅ |
| 6.2 | Environment Variables | `provider, tdd, plan` | ✅ |
| 6.3 | Provider Factory | `provider, structure, tdd, plan` | ✅ |
| 4.1 | LLM Abstract Interface | `provider, tdd, plan` | ✅ |
| 4.2 | Provider-Specific Adapters (Claude, OpenAI, Gemini) | `provider, tdd, plan` | ✅ |
| 4.3 | Model Routing Table | `provider, plan` | ✅ |
| 4.4 | Cost Estimates by Task | `provider, plan` | ✅ |
| 4.5 | Tool Calling Patterns | `provider, tdd, plan` | ✅ |
| 4.6 | JSON Mode Patterns | `provider, tdd, plan` | ✅ |
| 5.1 | Embedding Abstract Interface | `provider, db, tdd, plan` | ✅ |
| 5.2 | OpenAI Embedding Adapter | `provider, tdd, plan` | ✅ |
| 5.3 | Embedding Model Comparison | `provider, plan` | ✅ |
| 7.1 | Error Taxonomy | `provider, structure, tdd, plan` | ✅ |
| 7.2 | Retry Strategy | `provider, test, tdd, plan` | ✅ |
| 7.3 | Error Mapping | `provider, tdd, plan` | ✅ |
| 8.1 | Logging | `provider, structure, plan` | ✅ |
| 9.1 | Mock Provider | `provider, test, tdd, plan` | ✅ |
| 9.2 | Test Fixtures | `test, tdd, plan` | ✅ |
| 8.2 | Metrics (Future) | `provider, plan` | ⬜ |
| 8.3 | Cost Tracking (Future) | `provider, plan` | ⬜ |
| 10 | BYOK Support (Future) | `provider, plan` | ⬜ |

---

### 1.3 API Scaffold (REQ-006)
**Status:** ✅ Complete (20/20 tasks)

*REST endpoints and auth. Required before agent tools can call the API.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-006 section for current task |
| 🧪 **TDD** | Write endpoint test first, then implement — follow `zentropy-tdd` (red-green-refactor) |
| 📂 **Structure** | Use `zentropy-structure` for module organization (routers, services, repositories) |
| 🌐 **API** | Use `zentropy-api` for FastAPI patterns, response envelopes, error handling |
| 📝 **Docs** | Use `zentropy-docs` for docstrings on all public endpoints |
| ✅ **Verify** | Use `test-runner` agent to run API tests with httpx AsyncClient |
| 🔍 **Review** | Use `code-reviewer` agent to check REST conventions and response shapes |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 2.1 | API Style: REST | `structure, docs, plan` | ✅ |
| 2.2 | Deployment Model: Local-First | `structure, plan` | ✅ |
| 6.1 | Authentication | `structure, tdd, plan` | ✅ |
| 6.2 | Authorization | `structure, tdd, plan` | ✅ |
| 7.1 | Content Type | `structure, tdd, plan` | ✅ |
| 7.2 | Response Envelope | `structure, tdd, plan` | ✅ |
| 7.3 | Pagination | `structure, tdd, plan` | ✅ |
| 8.1 | HTTP Status Codes | `structure, tdd, plan` | ✅ |
| 8.2 | Error Codes | `structure, tdd, plan` | ✅ |
| 5.1 | URL Structure | `structure, tdd, plan` | ✅ |
| 5.2 | Resource Mapping | `structure, tdd, docs, plan` | ✅ |
| 5.3 | Standard HTTP Methods | `structure, tdd, plan` | ✅ |
| 5.5 | Standard Filtering & Sorting | `structure, tdd, plan` | ✅ |
| 2.3 | Architecture: API-Mediated Agents | `api, structure, docs, plan` | ✅ |
| 2.6 | Bulk Operations | `api, structure, tdd, plan` | ✅ |
| 2.7 | File Upload & Download | `api, structure, tdd, db, plan` | ✅ |
| 5.4 | Persona Change Flags (HITL Sync) | `api, structure, tdd, db, plan` | ✅ |
| 2.5 | Real-Time Communication: SSE | `api, structure, tdd, provider, plan` | ✅ |
| 2.4 | Chat Agent with Tools | `api, agents, structure, tdd, provider, plan` | ✅ |
| 5.6 | Job Posting Ingest Endpoint | `api, structure, tdd, db, plan` | ✅ |

---

## Phase 2: Agent Framework

### 2.1 LangGraph Foundation (REQ-007 §3)
**Status:** ✅ Complete

*Shared agent infrastructure. Required before any specific agent.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §3 for LangGraph patterns |
| 🧪 **TDD** | Write state schema tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Agents** | Use `zentropy-agents` for LangGraph graph structure, state schemas, HITL patterns |
| 🤖 **Patterns** | Use `zentropy-provider` for LLM integration patterns |
| 🧪 **Mocking** | Use `zentropy-test` for mock checkpointing and state fixtures |
| ✅ **Verify** | Use `test-runner` agent to verify state transitions |
| 🔍 **Review** | Use `code-reviewer` agent to check graph structure |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 3.1 | Why LangGraph | `agents, docs, plan` | ✅ |
| 3.2 | State Schema | `agents, provider, structure, tdd, plan` | ✅ |
| 3.3 | Checkpointing & HITL | `agents, provider, db, tdd, plan` | ✅ |

---

### 2.2 Chat Agent (REQ-007 §4)
**Status:** ✅ Complete

*User-facing conversational interface. Orchestrates other agents.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §4 for chat agent spec |
| 🧪 **TDD** | Write intent recognition tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Agents** | Use `zentropy-agents` for graph structure, routing, tool calling patterns |
| 🤖 **Patterns** | Use `zentropy-provider` for Claude SDK conversation patterns |
| 📝 **Docs** | Use `zentropy-docs` for tool docstrings (agents read these) |
| 🧪 **Mocking** | Use `zentropy-test` for mock tool responses |
| ✅ **Verify** | Use `test-runner` agent to verify tool routing |
| 🔍 **Review** | Use `code-reviewer` agent to check response formatting |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 4.1 | Chat Agent — Responsibilities | `agents, provider, docs, plan` | ✅ |
| 4.2 | Chat Agent — Tool Categories | `agents, api, provider, structure, tdd, plan` | ✅ |
| 4.3 | Chat Agent — Intent Recognition | `agents, provider, tdd, plan` | ✅ |
| 4.4 | Chat Agent — Ambiguity Resolution | `agents, provider, tdd, plan` | ✅ |
| 4.5 | Chat Agent — Response Formatting | `agents, provider, tdd, plan` | ✅ |
| 15.1 | Graph Spec — Chat Agent | `agents, provider, structure, tdd, plan` | ✅ |

---

### 2.3 Onboarding Agent (REQ-007 §5)
**Status:** 🟡 In Progress

*Creates Persona from user interview. Required before job matching works.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §5 for onboarding flow |
| 🧪 **TDD** | Write interview step tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Agents** | Use `zentropy-agents` for HITL checkpointing, state persistence patterns |
| 🤖 **Patterns** | Use `zentropy-provider` for conversational extraction prompts |
| 🗃️ **Storage** | Use `zentropy-db` for persona creation and checkpoint persistence |
| 🧪 **Mocking** | Use `zentropy-test` for mock user responses |
| ✅ **Verify** | Use `test-runner` agent to verify persona completeness |
| 🔍 **Review** | Use `code-reviewer` agent to check prompt templates |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 5.1 | Onboarding Agent — Trigger Conditions | `agents, provider, tdd, plan` | ✅ |
| 5.2 | Onboarding Agent — Interview Flow | `agents, provider, tdd, plan` | ✅ |
| 5.3a | Step Behaviors — resume_upload + work_history | `agents, provider, db, tdd, plan` | ✅ |
| 5.3b | Step Behaviors — education + certifications | `agents, provider, db, tdd, plan` | ✅ |
| 5.3c | Step Behaviors — skills + stories | `agents, provider, db, tdd, plan` | ✅ |
| 5.3d | Step Behaviors — non_negotiables + growth_targets | `agents, provider, db, tdd, plan` | ✅ |
| 5.3e | Step Behaviors — voice_profile + base_resume | `agents, provider, db, tdd, plan` | ✅ |
| 5.4 | Onboarding Agent — Checkpoint Handling | `agents, provider, db, tdd, plan` | ✅ |
| 5.5 | Onboarding Agent — Post-Onboarding Updates | `agents, provider, db, tdd, plan` | ⬜ |
| 5.6 | Onboarding Agent — Prompt Templates | `agents, provider, docs, tdd, plan` | ⬜ |
| 15.2 | Graph Spec — Onboarding Agent | `agents, provider, structure, tdd, plan` | ✅ |

---

### 2.4 Scouter Agent (REQ-007 §6 + REQ-003)
**Status:** ⬜ Incomplete

*Discovers and ingests jobs. Combines REQ-007 §6 (behavior) and REQ-003 (job schema logic).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §6 AND REQ-003 for full context |
| 🧪 **TDD** | Write extraction tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Agents** | Use `zentropy-agents` for parallel fan-out/fan-in, sub-graph invocation |
| 🤖 **Patterns** | Use `zentropy-provider` for skill/culture extraction prompts |
| 🗃️ **Storage** | Use `zentropy-db` for job posting storage and deduplication queries |
| 🧪 **Mocking** | Use `zentropy-test` for mock job board responses |
| ✅ **Verify** | Use `test-runner` agent to verify ghost detection and dedup logic |
| 🔍 **Review** | Use `code-reviewer` agent to check source adapter patterns |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

**From REQ-007 §6:**

| § | Task | Hints | Status |
|---|------|-------|--------|
| 6.1 | Scouter Agent — Trigger Conditions | `agents, provider, tdd, plan` | ⬜ |
| 6.2 | Scouter Agent — Polling Flow | `agents, provider, db, tdd, plan` | ⬜ |
| 6.3 | Scouter Agent — Source Adapters | `agents, provider, structure, tdd, plan` | ⬜ |
| 6.4 | Scouter Agent — Skill & Culture Extraction | `agents, provider, tdd, plan` | ⬜ |
| 6.5 | Scouter Agent — Ghost Detection | `agents, db, test, tdd, plan` | ⬜ |
| 6.6 | Scouter Agent — Deduplication Logic | `agents, db, test, tdd, plan` | ⬜ |
| 6.7 | Scouter Agent — Error Handling | `agents, provider, test, tdd, plan` | ⬜ |
| 15.3 | Graph Spec — Scouter Agent | `agents, provider, structure, tdd, plan` | ⬜ |

**From REQ-003 (Job Posting Schema):**

| § | Task | Hints | Status |
|---|------|-------|--------|
| 4.1 | MVP Sources | `provider, docs, plan` | ⬜ |
| 4.2 | Source Registry (Global) | `db, tdd, plan` | ⬜ |
| 4.2b | User Source Preferences | `db, tdd, plan` | ⬜ |
| 4.3 | Agent Source Selection | `provider, db, tdd, plan` | ⬜ |
| 4.4 | Polling Configuration | `db, tdd, plan` | ⬜ |
| 6.1 | Status Transitions | `db, tdd, plan` | ⬜ |
| 7.1 | Ghost Detection — Purpose | `docs, plan` | ⬜ |
| 7.2 | Ghost Detection — Signals | `provider, tdd, plan` | ⬜ |
| 7.3 | Ghost Detection — Score Interpretation | `provider, tdd, plan` | ⬜ |
| 7.4 | Ghost Detection — Agent Communication | `provider, tdd, plan` | ⬜ |
| 7.5 | Ghost Detection — JSONB Structure | `db, tdd, plan` | ⬜ |
| 8.1 | Repost Detection — Criteria | `db, tdd, plan` | ⬜ |
| 8.2 | Repost Detection — Handling | `db, tdd, plan` | ⬜ |
| 8.3 | Repost Detection — Agent Context | `provider, tdd, plan` | ⬜ |
| 9.1 | Deduplication — Within Same Source | `db, test, tdd, plan` | ⬜ |
| 9.2 | Deduplication — Across Sources | `db, test, tdd, plan` | ⬜ |
| 9.3 | Deduplication — Priority | `db, tdd, plan` | ⬜ |
| 12.1 | Retention — Favorites Override | `db, tdd, plan` | ⬜ |
| 12.2 | Retention — Expiration Detection | `db, tdd, plan` | ⬜ |
| 13.1 | Workflow — Discovery Flow | `provider, structure, tdd, plan` | ⬜ |
| 13.2 | Workflow — User Review Flow | `structure, tdd, plan` | ⬜ |

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
| 1.1 | Score Types | `docs, plan` | ⬜ |
| 1.2 | Scoring Philosophy | `docs, plan` | ⬜ |
| 6.1 | Embeddings — What Gets Embedded | `db, docs, plan` | ⬜ |
| 6.2 | Embeddings — Model | `provider, docs, plan` | ⬜ |
| 6.3 | Embeddings — Persona Generation | `provider, db, tdd, plan` | ⬜ |
| 6.4 | Embeddings — Job Generation | `provider, db, tdd, plan` | ⬜ |
| 6.5 | Embeddings — Storage | `db, tdd, plan` | ⬜ |
| 6.6 | Embeddings — Freshness Check | `db, tdd, plan` | ⬜ |
| 3.1 | Non-Negotiables — Filter Rules | `db, tdd, plan` | ⬜ |
| 3.2 | Non-Negotiables — Undisclosed Data Handling | `tdd, plan` | ⬜ |
| 3.3 | Non-Negotiables — Filter Output | `structure, tdd, plan` | ⬜ |
| 4.1 | Fit Score — Component Weights | `docs, plan` | ⬜ |
| 4.2 | Fit Score — Hard Skills Match (40%) | `db, tdd, plan` | ⬜ |
| 4.3 | Fit Score — Soft Skills Match (15%) | `db, tdd, plan` | ⬜ |
| 4.4 | Fit Score — Experience Level (25%) | `tdd, plan` | ⬜ |
| 4.5 | Fit Score — Role Title Match (10%) | `db, tdd, plan` | ⬜ |
| 4.6 | Fit Score — Location/Logistics (10%) | `tdd, plan` | ⬜ |
| 4.7 | Fit Score — Aggregation | `tdd, plan` | ⬜ |
| 5.1 | Stretch Score — Component Weights | `docs, plan` | ⬜ |
| 5.2 | Stretch Score — Target Role Alignment (50%) | `provider, db, tdd, plan` | ⬜ |
| 5.3 | Stretch Score — Target Skills Exposure (40%) | `provider, db, tdd, plan` | ⬜ |
| 5.4 | Stretch Score — Growth Trajectory (10%) | `provider, tdd, plan` | ⬜ |
| 5.5 | Stretch Score — Aggregation | `tdd, plan` | ⬜ |
| 7.1 | Interpretation — Fit Score Thresholds | `tdd, plan` | ⬜ |
| 7.2 | Interpretation — Stretch Score Thresholds | `tdd, plan` | ⬜ |
| 7.3 | Interpretation — Combined | `tdd, plan` | ⬜ |
| 7.4 | Interpretation — Auto-Draft Threshold | `tdd, plan` | ⬜ |
| 8.1 | Explanation — Components | `provider, tdd, plan` | ⬜ |
| 8.2 | Explanation — Generation Logic | `provider, tdd, plan` | ⬜ |
| 9.1 | Edge Cases — Missing Data | `test, tdd, plan` | ⬜ |
| 9.2 | Edge Cases — Career Changers | `test, tdd, plan` | ⬜ |
| 9.3 | Edge Cases — Entry-Level Users | `test, tdd, plan` | ⬜ |
| 9.4 | Edge Cases — Executive Roles | `test, tdd, plan` | ⬜ |
| 10.1 | Performance — Batch Scoring | `db, test, tdd, plan` | ⬜ |
| 10.2 | Performance — Caching | `db, tdd, plan` | ⬜ |
| 10.3 | Performance — Embedding Costs | `provider, docs, plan` | ⬜ |
| 11.1 | Testing — Test Cases | `test, tdd, plan` | ⬜ |
| 11.2 | Testing — Validation Approach | `test, docs, plan` | ⬜ |

---

### 2.6 Strategist Agent (REQ-007 §7)
**Status:** ⬜ Incomplete

*Applies scoring to jobs. Depends on REQ-008 (Scoring Engine).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §7 AND REQ-008 for scoring context |
| 🧪 **TDD** | Write filtering/scoring tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Agents** | Use `zentropy-agents` for embedding freshness checks, auto-trigger patterns |
| 🗃️ **Queries** | Use `zentropy-db` for embedding similarity and non-negotiables filtering |
| 🤖 **Patterns** | Use `zentropy-provider` for stretch score prompts |
| 🧪 **Mocking** | Use `zentropy-test` for mock scoring engine responses |
| ✅ **Verify** | Use `test-runner` agent to verify non-negotiables filter correctly |
| 🔍 **Review** | Use `code-reviewer` agent to check score thresholds |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 7.1 | Strategist Agent — Trigger Conditions | `agents, provider, tdd, plan` | ⬜ |
| 7.2 | Strategist Agent — Scoring Flow | `agents, provider, structure, tdd, plan` | ⬜ |
| 7.3 | Strategist Agent — Non-Negotiables Filtering | `agents, db, tdd, plan` | ⬜ |
| 7.4 | Strategist Agent — Embedding-Based Matching | `agents, db, provider, tdd, plan` | ⬜ |
| 7.5 | Strategist Agent — Stretch Score | `agents, provider, tdd, plan` | ⬜ |
| 7.6 | Strategist Agent — Prompt Templates | `agents, provider, docs, tdd, plan` | ⬜ |
| 15.4 | Graph Spec — Strategist Agent | `agents, provider, structure, tdd, plan` | ⬜ |

---

### 2.7 Ghostwriter Agent (REQ-007 §8 + REQ-010)
**Status:** ⬜ Incomplete

*Generates tailored content. Combines REQ-007 §8 (behavior) and REQ-010 (prompts).*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §8 AND REQ-010 for full context |
| 🧪 **TDD** | Write content generation tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Agents** | Use `zentropy-agents` for duplicate prevention, race condition handling |
| 🤖 **Patterns** | Use `zentropy-provider` for generation prompts with voice profiles |
| 📝 **Docs** | Use `zentropy-docs` for prompt template documentation |
| 🧪 **Mocking** | Use `zentropy-test` for mock LLM responses |
| ✅ **Verify** | Use `test-runner` agent to verify guardrails (no fabrication) |
| 🔍 **Review** | Use `code-reviewer` agent to check prompt structure |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

**From REQ-007 §8:**

| § | Task | Hints | Status |
|---|------|-------|--------|
| 8.1 | Ghostwriter Agent — Trigger Conditions | `agents, provider, tdd, plan` | ⬜ |
| 8.2 | Ghostwriter Agent — Generation Flow | `agents, provider, structure, tdd, plan` | ⬜ |
| 8.3 | Ghostwriter Agent — Base Resume Selection | `agents, db, tdd, plan` | ⬜ |
| 8.4 | Ghostwriter Agent — Tailoring Decision | `agents, provider, tdd, plan` | ⬜ |
| 8.5 | Ghostwriter Agent — Cover Letter Generation | `agents, provider, tdd, plan` | ⬜ |
| 8.6 | Ghostwriter Agent — Story Selection Logic | `agents, db, provider, tdd, plan` | ⬜ |
| 8.7 | Ghostwriter Agent — Reasoning Explanation | `agents, provider, tdd, plan` | ⬜ |
| 15.5 | Graph Spec — Ghostwriter Agent | `agents, provider, structure, tdd, plan` | ⬜ |

**From REQ-010 (Content Generation):**

| § | Task | Hints | Status |
|---|------|-------|--------|
| 3.1 | Voice Profile Fields | `db, docs, plan` | ⬜ |
| 3.2 | Voice Application Rules | `provider, tdd, plan` | ⬜ |
| 3.3 | Voice Profile System Prompt Block | `provider, docs, tdd, plan` | ⬜ |
| 4.1 | Resume — Tailoring Decision Logic | `provider, tdd, plan` | ⬜ |
| 4.2 | Resume — Summary Tailoring Prompt | `provider, docs, tdd, plan` | ⬜ |
| 4.3 | Resume — Bullet Reordering Logic | `tdd, plan` | ⬜ |
| 4.4 | Resume — Modification Limits (Guardrails) | `provider, test, tdd, plan` | ⬜ |
| 5.1 | Cover Letter — Structure | `docs, plan` | ⬜ |
| 5.2 | Cover Letter — Achievement Story Selection | `db, provider, tdd, plan` | ⬜ |
| 5.3 | Cover Letter — Generation Prompt | `provider, docs, tdd, plan` | ⬜ |
| 5.4 | Cover Letter — Validation | `provider, test, tdd, plan` | ⬜ |
| 5.5 | Cover Letter — Output Schema | `structure, tdd, plan` | ⬜ |
| 6.1 | Utility Functions — Implementation Strategy | `structure, docs, plan` | ⬜ |
| 6.2 | Utility Functions — extract_keywords | `provider, tdd, plan` | ⬜ |
| 6.3 | Utility Functions — extract_skills_from_text | `provider, tdd, plan` | ⬜ |
| 6.4 | Utility Functions — has_metrics/extract_metrics | `tdd, plan` | ⬜ |
| 6.5 | Utility Functions — Caching Strategy | `db, tdd, plan` | ⬜ |
| 7.1 | Regeneration — Feedback Categories | `docs, plan` | ⬜ |
| 7.2 | Regeneration — Feedback Sanitization | `provider, tdd, plan` | ⬜ |
| 7.3 | Regeneration — Prompt Modifier | `provider, tdd, plan` | ⬜ |
| 8.1 | Edge Cases — Insufficient Data | `test, tdd, plan` | ⬜ |
| 8.2 | Edge Cases — Expired Job | `test, tdd, plan` | ⬜ |
| 8.3 | Edge Cases — Persona Changed | `db, test, tdd, plan` | ⬜ |
| 8.4 | Edge Cases — Duplicate Story Selection | `test, tdd, plan` | ⬜ |
| 9.1 | Agent Reasoning — Template | `provider, docs, tdd, plan` | ⬜ |
| 9.2 | Agent Reasoning — Example Output | `docs, plan` | ⬜ |
| 10.1 | Quality Metrics — Tracking | `db, tdd, plan` | ⬜ |
| 10.2 | Quality Metrics — Feedback Loop | `db, structure, tdd, plan` | ⬜ |

---

### 2.8 Agent Communication (REQ-007 §9-11)
**Status:** ⬜ Incomplete

*Cross-cutting concerns for all agents.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Use `req-reader` agent to load REQ-007 §9-11 for communication patterns |
| 🧪 **TDD** | Write SSE event tests first — follow `zentropy-tdd` (red-green-refactor) |
| 🤖 **Agents** | Use `zentropy-agents` for agent-to-agent communication, sub-graph invocation |
| 📂 **Structure** | Use `zentropy-structure` for shared module organization |
| 🤖 **Patterns** | Use `zentropy-provider` for model routing configuration |
| 🧪 **Mocking** | Use `zentropy-test` for mock event streams |
| ✅ **Verify** | Use `test-runner` agent to verify error handling and retries |
| 🔍 **Review** | Use `code-reviewer` agent to check event type consistency |
| 📝 **Commit** | Follow `zentropy-git` for conventional commit messages |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 9.1 | Communication — Agent-to-User | `agents, api, provider, structure, tdd, plan` | ⬜ |
| 9.2 | Communication — Agent-to-Agent | `agents, provider, structure, tdd, plan` | ⬜ |
| 9.3 | Communication — SSE Event Types | `agents, api, structure, tdd, plan` | ⬜ |
| 10.1 | Error Handling — Transient Errors | `agents, provider, test, tdd, plan` | ⬜ |
| 10.2 | Error Handling — Permanent Errors | `agents, provider, test, tdd, plan` | ⬜ |
| 10.3 | Error Handling — Graceful Degradation | `agents, provider, test, tdd, plan` | ⬜ |
| 10.4 | Error Handling — Concurrency & Race Conditions | `agents, db, test, tdd, plan` | ⬜ |
| 11.1 | Configuration — Environment Variables | `agents, structure, docs, plan` | ⬜ |
| 11.2 | Configuration — Model Routing | `agents, provider, tdd, plan` | ⬜ |
| 15.6 | Graph Spec — Invocation Patterns | `agents, provider, structure, tdd, plan` | ⬜ |

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
| 4.1 | Resume File — Upload Handling | `db, structure, tdd, plan` | ⬜ |
| 4.2 | Base Resume — Rendered Document Storage | `db, tdd, plan` | ⬜ |
| 4.3 | Job Variant — Snapshot Logic | `db, tdd, plan` | ⬜ |
| 4.4 | Submitted PDF — Immutable Storage | `db, tdd, plan` | ⬜ |
| 4.5 | Persona Change Flag — HITL Sync | `db, tdd, plan` | ⬜ |
| 5.1 | Retention Rules | `db, tdd, plan` | ⬜ |
| 5.4 | User Actions (Archive/Restore) | `db, tdd, plan` | ⬜ |
| 6.1 | Workflow — Onboarding Flow | `structure, tdd, plan` | ⬜ |
| 6.2 | Workflow — Application Flow (Auto-Draft) | `structure, tdd, plan` | ⬜ |
| 6.3 | Workflow — Persona → Base Resume Sync | `db, tdd, plan` | ⬜ |
| 6.4 | Workflow — PDF Generation (ReportLab) | `structure, test, tdd, plan` | ⬜ |
| 7.1 | Agent — Base Resume Selection | `provider, db, tdd, plan` | ⬜ |
| 7.2 | Agent — Tailoring Decision | `provider, tdd, plan` | ⬜ |
| 7.3 | Agent — Modification Limits | `provider, test, tdd, plan` | ⬜ |

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
| 4.1 | Cover Letter — Field Implementation | `db, tdd, plan` | ⬜ |
| 4.2 | Submitted Cover Letter PDF — Immutable Storage | `db, tdd, plan` | ⬜ |
| 7.1 | Workflow — Generation Flow (Auto-Draft) | `structure, tdd, plan` | ⬜ |
| 7.2 | Workflow — Agent Story Selection | `provider, db, tdd, plan` | ⬜ |
| 7.3 | Workflow — User Editing | `structure, tdd, plan` | ⬜ |
| 7.4 | Workflow — Approval & PDF Generation | `structure, test, tdd, plan` | ⬜ |
| 8.1 | Agent — Cover Letter Structure | `provider, docs, tdd, plan` | ⬜ |
| 8.2 | Agent — Voice Profile Application | `provider, tdd, plan` | ⬜ |
| 8.3 | Agent — Modification Limits | `provider, test, tdd, plan` | ⬜ |

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
| 3.1 | Architecture — Component Overview | `structure, docs, plan` | ⬜ |
| 3.2 | Architecture — Data Flow | `structure, docs, plan` | ⬜ |
| 4.1 | UI — Extension States | `playwright, tdd, plan` | ⬜ |
| 4.2 | UI — Popup Layout | `playwright, tdd, plan` | ⬜ |
| 4.3 | UI — URL Badge System | `playwright, tdd, plan` | ⬜ |
| 5.1 | Extraction — Text Extraction Strategy | `test, tdd, plan` | ⬜ |
| 5.2 | Extraction — Page Detection Heuristics | `test, tdd, plan` | ⬜ |
| 6.1 | API — Ingest Flow | `structure, tdd, plan` | ⬜ |
| 6.2 | API — Duplicate Detection | `db, tdd, plan` | ⬜ |
| 6.3 | API — Error Handling | `test, tdd, plan` | ⬜ |
| 7.1 | Auth — Local Mode (MVP) | `structure, tdd, plan` | ⬜ |
| 7.2 | Auth — Future Hosted Mode | `docs, plan` | ⬜ |
| 8.1 | Permissions — Required | `docs, plan` | ⬜ |
| 8.2 | Permissions — Optional | `docs, plan` | ⬜ |
| 9.1 | Edge Cases — Content Extraction Failures | `test, tdd, plan` | ⬜ |
| 9.2 | Edge Cases — Network Issues | `test, tdd, plan` | ⬜ |
| 9.3 | Edge Cases — Duplicate Handling | `db, test, tdd, plan` | ⬜ |

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
