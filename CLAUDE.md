# Zentropy Scout — Claude Code Project Memory

## What Is This Project?

Zentropy Scout is an AI-powered job application assistant that helps users:
1. Build a comprehensive professional persona (skills, experiences, preferences)
2. Analyze job postings to extract requirements and culture signals
3. Generate tailored resumes and cover letters
4. Track applications and provide strategic recommendations

**Target:** SaaS application intended for public deployment. Currently in active development with security hardening. Hosting planned for Railway (to be scoped when ready).

---

## Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| **Backend** | FastAPI (Python 3.11+) | Async, Pydantic v2 |
| **Frontend** | Next.js 14+ (TypeScript) | App Router, Tailwind CSS |
| **Database** | PostgreSQL 16 + pgvector | Vector similarity for job matching |
| **Agent Framework** | LangGraph | State machine graphs with checkpointing |
| **LLM Providers** | Claude, OpenAI, Gemini | Swappable via provider abstraction layer |
| **Embeddings** | OpenAI text-embedding-3-small | 1536 dimensions |
| **PDF Generation** | ReportLab + Platypus | Pure Python, no system deps |
| **Browser Extension** | Chrome Extension (Manifest V3) | Job posting capture |

---

## Project Structure

```
zentropy_scout/
├── CLAUDE.md                    # THIS FILE
├── docker-compose.yml           # PostgreSQL + pgvector
├── .env.example                 # Environment template
├── .pre-commit-config.yaml      # Pre-commit/pre-push hooks
├── .github/
│   ├── workflows/               # CI: Semgrep, SonarCloud, ZAP DAST, pip-audit
│   ├── dependabot.yml           # Dependency scanning (pip, npm, GitHub Actions)
│   └── zap-rules.tsv            # ZAP alert suppressions
├── docs/
│   ├── prd/                     # Product requirements
│   ├── requirements/            # DETAILED SPECS (REQ-001 to REQ-012)
│   ├── plan/                    # Implementation plans (backend + frontend)
│   └── backlog/                 # Feature backlog (future work)
├── backend/                     # FastAPI app
└── frontend/                    # Next.js app
```

---

## Implementation Phases

### Backend (all ✅ complete)

| Phase | Focus | Key REQs |
|-------|-------|----------|
| **1.1** | Database Schema | REQ-005 |
| **1.2** | Provider Abstraction | REQ-009 |
| **1.3** | API Scaffold | REQ-006 |
| **2.x** | Agent Framework | REQ-007 (8 sub-phases) |
| **3.x** | Document Generation | REQ-002, REQ-002b, REQ-010 |

### Frontend (all ✅ complete)

| Phase | Focus | Key REQs |
|-------|-------|----------|
| **1–3** | Scaffold, Foundation, Shared Components | REQ-012 §4, §13 |
| **4** | Chat Interface | REQ-012 §5 |
| **5** | Onboarding Flow (12-step wizard) | REQ-012 §6 |
| **6** | Persona Management | REQ-012 §7 |
| **7** | Job Dashboard & Scoring | REQ-012 §8 |
| **8** | Resume Management | REQ-012 §9 |
| **9** | Cover Letter Management | REQ-012 §10 |
| **10** | Application Tracking | REQ-012 §11 |
| **11** | Settings & Configuration | REQ-012 §12 |
| **12** | Integration, Polish & E2E Tests | REQ-012 |
| **13** | Security Audit & Hardening | OWASP, DAST, SonarCloud |

### Postponed

| Phase | Focus | Key REQs |
|-------|-------|----------|
| **4.1** | Chrome Extension | REQ-011 |

**Plans:** See `docs/plan/` for all implementation plans (backend, frontend, and feature-specific).

**Rule:** Complete each phase before starting the next. Dependencies are strict.

---

## Critical Rules (Always Apply)

### Code Patterns
1. **Async everywhere** — All DB and LLM calls use `async/await`
2. **Pydantic for validation** — Input/output models for all endpoints
3. **Repository pattern** — `backend/repositories/` for DB access
4. **Service layer** — `backend/services/` for business logic
5. **Type hints required** — No `Any` without justification
6. **One class per file** — Exceptions: small related classes
7. **Files under 300 lines** — Split if larger
8. **No `utils.py` dumping ground** — Be specific (`text_utils.py`, `date_utils.py`)

### File Storage (CRITICAL)
**All files stored as BYTEA in PostgreSQL.** No S3, no filesystem paths.

```python
# CORRECT
class ResumeVersion(Base):
    pdf_content: Mapped[bytes]  # BYTEA column

# WRONG — never do this
pdf_path: str  # No filesystem paths
s3_key: str    # No S3 references
```

### Naming Conventions

| Entity | Convention | Example |
|--------|------------|---------|
| Python files | snake_case | `persona_repository.py` |
| Python classes | PascalCase | `PersonaRepository` |
| DB tables | snake_case, plural | `personas`, `job_postings` |
| API routes | kebab-case | `/api/v1/job-postings` |
| TypeScript files | kebab-case | `use-persona.ts` |
| React components | kebab-case (PascalCase export) | `basic-info-editor.tsx` |

### Error Handling

```python
class ZentropyError(Exception): ...
class NotFoundError(ZentropyError): ...
class ValidationError(ZentropyError): ...

# API returns consistent error shape
{"error": {"code": "PERSONA_NOT_FOUND", "message": "..."}}
```

---

## Environment Variables

See `.env.example` for all variables with documentation. Key ones:

```bash
# Database (split vars, not a monolithic URL)
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=zentropy_scout
DATABASE_USER=zentropy_user
DATABASE_PASSWORD=zentropy_dev_password

# LLM Providers
LLM_PROVIDER=claude              # claude | openai | gemini
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...            # Also used for embeddings
GOOGLE_API_KEY=...

# Embedding
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small

# Auth (local-first mode)
AUTH_ENABLED=false
DEFAULT_USER_ID=                 # Set to your user UUID

# Rate Limiting
RATE_LIMIT_LLM=10/minute
RATE_LIMIT_ENABLED=true
```

---

## Working with Requirements

1. **Start with the active plan** — each task references the REQ sections needed
2. **Use `req-reader`** to load specific REQ sections (discovers documents dynamically via `docs/requirements/`)
3. **Reference sections like "REQ-005 §4.2"**
4. **For ad-hoc work** (no active plan), search `docs/requirements/` by topic using `req-reader`

---

## Session Start Checklist

Run these checks at the start of every session (before any implementation work):

1. **Docker/PostgreSQL** — Run `docker compose ps` to verify the database container is running and healthy. If not running, start it with `docker compose up -d` and wait for the healthcheck to pass.
2. **Security scanners** — Check all persistent scanners for new findings. Run these queries in parallel, then report a summary table. If any **new or unexpected** findings exist, **pause and ask the user** whether to address them now or continue to the plan.
   - **GitHub code scanning** (ZAP + Trivy): `gh api repos/ApexAZ/zentropy_scout/code-scanning/alerts?state=open --jq 'length'`
   - **SonarCloud**: WebFetch `https://sonarcloud.io/api/issues/search?componentKeys=ApexAZ_zentropy_scout&resolved=false` — check `total` field
   - **Dependabot**: `gh api repos/ApexAZ/zentropy_scout/dependabot/alerts?state=open --jq 'length'`
   - **Semgrep CI**: `gh run list --workflow=semgrep.yml --limit=1 --json conclusion --jq '.[0].conclusion'`
   - **Dependency audits** (pip-audit + npm audit): `gh run list --workflow=pip-audit.yml --limit=1 --json conclusion --jq '.[0].conclusion'`
   - **Known/expected findings** (do NOT pause for these — only pause if count changes):
     - 1 Semgrep supply chain finding (dev-only transitive dep, zero production risk):
       - ajv@6.12.6 ReDoS (CVE-2025-69873, GHSA-2g4f-4pwh-qvx6) — via ESLint. ESLint doesn't use the `$data` option that triggers the CVE. Issue [#20508](https://github.com/eslint/eslint/issues/20508) open/triaging, no fix planned. ESLint stance: "security issues like this don't usually affect ESLint" ([#14863](https://github.com/eslint/eslint/issues/14863)). Also accepted in npm audit (`pip-audit.yml:90`).
     - 1 SonarCloud finding (accepted — framework constraint):
       - chat.py:636 S7503 (async without await) — `delegate_onboarding` must be async for LangGraph `ainvoke()`. Suppressed via `# noqa: RUF029` for ruff. SonarCloud doesn't support inline suppression for Python.
3. **Implementation plan** — Discover the active plan: `Glob "docs/plan/*_plan.md"`, read each to find plans with 🟡 or ⬜ tasks, or ask the user which plan is in scope. The plan references the relevant REQ documents per task.
4. **Announce** — Tell the user: "Resuming at Phase X.Y, Task §Z" and confirm Docker + scanner status.

---

## DO / DON'T

### DO:
- **Update the active plan file after EVERY subtask** — see `zentropy-planner` skill
- **Commit after EVERY subtask** — do NOT batch commits
- **Ask before pushing** — never auto-push to remote
- Follow TDD (Red-Green-Refactor) — see `zentropy-tdd` skill
- Read relevant REQ document before implementing
- Run tests before claiming task complete
- Keep changes focused — one logical change per commit
- Ask before adding new dependencies
- Follow existing patterns in the codebase

### DON'T:
- Write implementation code without a failing test first
- Refactor unrelated code while implementing a feature
- Create new architectural patterns without discussing first
- Add "TODO" comments — either fix it or create an issue
- Leave commented-out code
- Change file/folder structure without justification
- Implement features not in requirements

---

## Definition of Done

A task is complete when:
1. ✅ Code implements the requirement (reference REQ section)
2. ✅ **All tests pass (100% pass rate, no skips)** — `pytest -v` / `npm test`
3. ✅ Linter passes (`ruff check .` / `npm run lint`)
4. ✅ Types check (`pyright` / `npm run typecheck`)
5. ✅ Migration tested (upgrade AND downgrade)
6. ✅ Docstrings on public interfaces
7. ✅ No `# TODO` left behind
8. ✅ Committed with conventional commit message
9. ✅ Plan updated (status → ✅)
10. ✅ **STOP: Use AskUserQuestion** — offer "Continue", "Compact first", or "Stop"

---

## Testing Philosophy

### Core Principle: Behavior Over Implementation

**Test WHAT code does, not HOW it does it.** Tests should verify observable behavior from the perspective of the code's users (callers, API consumers), not internal implementation details.

```python
# GOOD: Tests behavior - what the caller cares about
def test_extraction_tasks_use_cheaper_model():
    """Extraction should route to a cost-effective model."""
    adapter = ClaudeAdapter(config)
    model = adapter.get_model_for_task(TaskType.EXTRACTION)
    assert "haiku" in model.lower()  # Behavior: cheaper model selected

# BAD: Tests implementation - brittle, will break on refactor
def test_routing_dict_has_nine_entries():
    """Don't test internal data structure sizes."""
    assert len(DEFAULT_ROUTING) == 9  # Ties test to implementation detail
```

### When Tests Should Change

- ✅ **Change tests when**: Behavior requirements change
- ❌ **Don't change tests when**: Refactoring internals (tests should still pass)

If refactoring breaks tests, the tests were likely testing implementation, not behavior.

### When to Run Tests

| Phase | What to Run | Command | Why |
|-------|-------------|---------|-----|
| **While coding** | Affected tests | `pytest tests/unit/test_file.py -v` | Fast TDD feedback loop |
| **Before commit** (subtask) | Affected tests + lint | Pre-commit hooks (~25-40s) | Quick quality check |
| **Before push** (phase gate) | Full suite + lint + types | test-runner Full mode (~90-135s) | Comprehensive quality gate |
| **CI/CD** | Everything + coverage | GitHub Actions | Final quality gate |

### Test Quality Checklist

Before considering a test complete:

1. **Does it test behavior?** — Would a user/caller care about this assertion?
2. **Is it meaningful?** — Does it catch real bugs, not just "make coverage go up"?
3. **Is it readable?** — Can someone understand the intent without reading implementation?
4. **Is it independent?** — Does it pass/fail regardless of test execution order?
5. **Does it have a clear name?** — `test_<behavior>_when_<condition>` format preferred

### Test Antipatterns to Avoid

These patterns test implementation details rather than behavior. They break on refactors that don't change functionality. **Never write tests that use these patterns:**

| Banned Pattern | Why It's Wrong | What to Do Instead |
|----------------|----------------|-------------------|
| `isinstance(result, SomeType)` | Tests return type, not behavior | Assert on the result's value or properties |
| `issubclass(Foo, Bar)` | Tests inheritance chain | Test that `Foo` exhibits `Bar`'s behavioral contract |
| `hasattr(obj, "field")` | Tests attribute existence | Call the attribute and assert on its behavior |
| `"method" in Cls.__abstractmethods__` | Tests ABC internals | Test that concrete subclasses implement the method |
| `dataclasses.fields(Cls)` / `get_type_hints(Cls)` | Tests schema shape | Construct instances and assert on behavior |
| `CONSTANT == 42` / `enum.value == "literal"` | Duplicates the source code | Test behavior that depends on the constant's value |
| `len(some_enum) == N` | Breaks when enum grows | Test specific members that matter for behavior |
| `callable(obj)` | Tests callable status, not behavior | Call the function and assert on its return value |

**Decision criterion:** Ask "Would this test still pass if I rewrote the implementation using a completely different internal structure but preserved the same external behavior?" If yes, the test is behavioral (good). If no, the test is structural (bad).

**Automated detection:** The conftest.py hook scans test functions via AST analysis and reports violations in the pytest terminal summary (warning-only, does not fail the build).

**Frozen-test pattern (approved alternative for immutability):** When you need to verify a data structure hasn't changed (e.g., migration mappings), test the behavioral contract: "new names follow the naming convention" rather than "there are exactly 49 entries."

```python
# Approved: Test immutability through public API
def test_result_preserves_original_on_copy():
    result = SomeResult(field="value")
    updated = replace(result, field="new")
    assert result.field == "value"   # Original unchanged
    assert updated.field == "new"    # Copy has new value
```

### Pre-commit Hooks

This project uses `pre-commit` to enforce quality before commits. Configuration lives in `.pre-commit-config.yaml`.

```bash
# Install hooks (one-time setup)
pre-commit install --hook-type pre-commit --hook-type pre-push

# Run manually
pre-commit run --all-files
```

**On commit:** ruff (lint + format), bandit, gitleaks, mypy (backend type check), trailing whitespace, ESLint, Prettier, TypeScript type check.
**On push:** Full pytest suite (backend) + Vitest suite (frontend). See `.pre-commit-config.yaml` for details.

**IMPORTANT:** Never use `--no-verify` to bypass hooks. If tests fail, fix them before committing/pushing. "Pre-existing" failures are still your responsibility to fix.

---

## Security Tooling Stack

Layered security scanning across local development and CI:

| Layer | Tool | What It Catches | When It Runs |
|-------|------|-----------------|--------------|
| **SAST (deep)** | Semgrep Team | Cross-file taint analysis, FastAPI-native injection detection | CI (GitHub Actions) |
| **SAST (fast)** | Bandit | Python security patterns (injection, secrets, weak crypto) | Pre-commit hook |
| **DAST** | OWASP ZAP | Runtime API vulnerabilities (injection, auth, headers) | CI (push to main) |
| **Code quality** | SonarCloud | Code smells, duplication, security hotspots, complexity | CI (post-push) |
| **Frontend lint** | ESLint + Prettier + TypeScript | React/TS lint, formatting, type safety | Pre-commit hook |
| **Dependencies (Python)** | pip-audit | Known CVEs in Python packages (OSV database) | CI (GitHub Actions) |
| **Dependencies (npm)** | npm audit | Known CVEs in Node.js packages (GitHub Advisory DB) | CI (GitHub Actions) |
| **Dependencies (all)** | Dependabot alerts | Vulnerability alerts for pip, npm, and GitHub Actions deps | GitHub (continuous) |
| **Dependencies (all)** | Dependabot version updates | Automated weekly PRs to bump dependency versions | GitHub (weekly) |
| **Secrets** | gitleaks | Leaked API keys, passwords, tokens in commits | Pre-commit hook |
| **Fuzz testing** | Hypothesis | Property-based testing for sanitization pipeline invariants | pytest (local + CI) |

**Semgrep Team** is free for ≤10 contributors and provides cross-function, cross-file taint tracking with FastAPI-native understanding. Requires `SEMGREP_APP_TOKEN` secret in GitHub repo settings.

**OWASP ZAP** runs API scans against the FastAPI OpenAPI spec in CI. All alerts flow unfiltered to Security tab. False positives dismissed individually via `gh api` — see `zentropy-security-alerts` skill. Results uploaded to GitHub Security tab (SARIF) and as workflow artifacts (30-day retention).

**Dependabot** provides two services: (1) **vulnerability alerts** — continuous monitoring of the dependency graph for known CVEs, surfaced in the repo's Security tab (private, not visible in Issues); (2) **version updates** — weekly PRs to bump pip, npm, and GitHub Actions dependencies. Configured in `.github/dependabot.yml`.

**pip-audit + npm audit** both run in the "Dependency Audit" CI workflow (`.github/workflows/pip-audit.yml`). pip-audit uses Google's OSV database; npm audit uses the GitHub Advisory Database. Both run on every PR and push to main with retry logic and accepted-advisory filtering.

For detailed security review patterns, see `.claude/agents/security-references.md` `[TOOLS]` section.

---

## Skills Available

These skills auto-load when relevant. Ask about specific topics to trigger them:

| Skill | Triggers | Content |
|-------|----------|---------|
| `zentropy-api` | endpoint, router, REST, response, API | FastAPI patterns, response envelopes, error handling |
| `zentropy-agents` | agent, LangGraph, graph, state, HITL | Graph structure, state schemas, checkpointing |
| `zentropy-db` | database, migration, postgres, SQL | pgvector, BYTEA, Alembic patterns |
| `zentropy-provider` | LLM, Claude, API, extract, generate | Provider abstraction, adapter pattern, task-based model routing |
| `zentropy-tdd` | test, pytest, mock, fixture, coverage, hypothesis, TDD, implement, create, build | TDD enforcement, testing patterns, mocks, Hypothesis fuzz testing |
| `zentropy-playwright` | playwright, e2e, end-to-end, UI testing | E2E tests, mocking, selectors |
| `zentropy-lint` | lint, ruff, eslint, mypy, prettier | Linting stack, common errors |
| `zentropy-security-alerts` | security alert, ZAP, dismiss, false positive, triage | Alert triage protocol, dismissal commands |
| `zentropy-imports` | imports, import order | Python/TypeScript ordering |
| `zentropy-git` | commit, branch, git | Conventional commits, workflow |
| `zentropy-commands` | how do I start, run migrations | Docker, alembic, npm commands |
| `zentropy-docs` | docstring, documentation, comments | Google-style docstrings |
| `reflect` | remember this, add lesson, mistake, never again | Self-improvement, captures lessons |
| `config-sync` | update documentation, sync config, changed .claude/ | Keeps CLAUDE_TOOLS.md in sync |
| `zentropy-planner` | plan, progress, status, resume, complete, phase, create a plan | Plan creation (format, hints, sizing) + progress tracking |

---

## Subagents Available

| Agent | Use For |
|-------|---------|
| `req-reader` | Look up requirement specs |
| `code-reviewer` | Review code against conventions |
| `security-reviewer` | Review code for security vulnerabilities (OWASP Top 10, injection, auth) |
| `qa-reviewer` | Assess whether changes need new Playwright E2E tests |
| `test-runner` | Run and analyze test results |

### Proactive Subagent Usage

**BEFORE starting any implementation task:**
- **`req-reader`**: Always read the relevant REQ section first to get full spec context
- **`Explore`**: If unfamiliar with the code area, explore the codebase first

**AFTER completing code (run in parallel):**
- **`code-reviewer`** + **`security-reviewer`** + **`qa-reviewer`**: Launch ALL THREE simultaneously before commit
- All are read-only — parallel execution is safe and faster

**For open-ended questions:**
- **`Explore`**: Use for "Where is X?", "How does Y work?", "Find all Z" queries instead of manual Glob/Grep

---

## Learned Lessons

Rules discovered through mistakes. Format: `[category] Always/Never [action] because [reason]`

- `[db]` Always check REQ-005 before generating database migrations because schema definitions and field specifications live there.
- `[workflow]` Always commit after each subtask completes because small commits enable easier rollback and progress tracking.
- `[workflow]` Never auto-push to remote; always ask first because user may want to review or batch pushes.
- `[workflow]` Always use `req-reader` subagent before implementing a task because it ensures you have the full spec context.
- `[workflow]` Always use `code-reviewer` subagent after implementing code because it catches convention violations before commit.
- `[workflow]` Always fix ALL code review findings (regardless of severity) before committing because low-severity issues accumulate into technical debt and inconsistent code.
- `[workflow]` Never acknowledge review findings without immediately fixing them because stating intent ("let me address...") without action leads to skipped fixes; use structured findings/resolution tables to enforce follow-through.
- `[workflow]` Always use `Explore` subagent for open-ended codebase questions because it's more thorough than manual Glob/Grep.
- `[workflow]` Never combine multiple subtasks into one because tasks are sized to complete within the ~150k context window, preventing auto-compaction mid-implementation and ensuring progress is captured even if context resets.
- `[git]` Never attempt to commit `.claude/` directory or `CLAUDE_TOOLS.md` because they are gitignored and local-only; these files exist only on the user's machine.
- `[testing]` Never use `--no-verify` to bypass failing tests because even "pre-existing" failures represent technical debt that compounds over time; fix the tests before pushing.
- `[testing]` Always verify Docker/PostgreSQL is running at session start (`docker compose ps`) and before investigating test failures because the container may not be started; skipped tests violate the "100% pass rate, no skips" Definition of Done.
- `[workflow]` After completing a subtask, always follow this exact order: (1) commit (no push — pushes happen at phase gates only), (2) use AskUserQuestion tool (not prose) to offer "Continue to next subtask"/"Compact first"/"Stop", (3) if "Compact first" is selected, immediately provide a detailed summary for compaction. At phase gates: run full quality gate (test-runner Full mode) → fix regressions → commit → push → AskUserQuestion. The checklist exists to prevent shortcuts at the finish line when you feel "done."

- `[security]` Never filter or suppress security scanner alerts from reporting output (SARIF, Security tab) because DAST/SAST findings are meant for manual human review — the protocol is: review each alert, determine if genuine or false positive, then dismiss via `gh api` with reason and comment if false positive.

<!-- Add new lessons above this line -->

---

## Current Status

**Phase:** All phases complete. No active phase.
**Backend:** All phases complete (1.1–3.2). Chrome Extension (4.1) postponed.
**Frontend:** Phases 1–15 complete.
**Code quality:** SonarCloud at 0 issues, 0 duplication, 0 hotspots.

**IMPORTANT:** After completing ANY subtask, update the active plan file status (⬜ → ✅). See `zentropy-planner` skill. Discover plan files via `Glob "docs/plan/*_plan.md"` or ask the user which plan is in scope.

**Feature backlog:** `docs/backlog/feature-backlog.md` — 7 items (OpenRouter, auth, multi-tenant, tiered fetch, content TTL, Railway deployment, Socket.dev).

---

*Last updated: 2026-02-19*
