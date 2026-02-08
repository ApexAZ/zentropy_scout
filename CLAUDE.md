# Zentropy Scout — Claude Code Project Memory

## What Is This Project?

Zentropy Scout is an AI-powered job application assistant that helps users:
1. Build a comprehensive professional persona (skills, experiences, preferences)
2. Analyze job postings to extract requirements and culture signals
3. Generate tailored resumes and cover letters
4. Track applications and provide strategic recommendations

**Target:** Local-first MVP for personal use, with future hosted/multi-tenant option.

---

## Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| **Backend** | FastAPI (Python 3.11+) | Async, Pydantic v2 |
| **Frontend** | Next.js 14+ (TypeScript) | App Router, Tailwind CSS |
| **Database** | PostgreSQL 16 + pgvector | Vector similarity for job matching |
| **LLM (Local)** | Claude Agent SDK | Uses user's Claude subscription |
| **LLM (Hosted)** | Anthropic API (BYOK) | Future: user provides API key |
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
├── docs/
│   ├── prd/                     # Product requirements
│   ├── requirements/            # DETAILED SPECS (REQ-001 to REQ-011)
│   └── plan/                    # Implementation plan
├── backend/                     # FastAPI app
├── frontend/                    # Next.js app
└── extension/                   # Chrome extension
```

**For detailed module organization, the `zentropy-structure` skill will auto-load.**

---

## Implementation Phases

| Phase | Focus | Key REQs |
|-------|-------|----------|
| **1.1** | Database Schema | REQ-005 |
| **1.2** | Provider Abstraction | REQ-009 |
| **1.3** | API Scaffold | REQ-006 |
| **2.x** | Agent Framework | REQ-007 (split into 8 sub-phases) |
| **3.x** | Document Generation | REQ-002, REQ-002b, REQ-010 |
| **4.1** | Chrome Extension | REQ-011 |

**Rule:** Complete each phase before starting the next. Dependencies are strict.

---

## Critical Rules (Always Apply)

### Code Patterns
1. **Async everywhere** — All DB and LLM calls use `async/await`
2. **Pydantic for validation** — Input/output models for all endpoints
3. **Repository pattern** — `backend/repositories/` for DB access
4. **Service layer** — `backend/services/` for business logic
5. **Type hints required** — No `Any` without justification

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
| TypeScript files | camelCase | `usePersona.ts` |
| React components | PascalCase | `PersonaForm.tsx` |

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

```bash
DATABASE_URL=postgresql+asyncpg://zentropy_user:zentropy_dev_password@localhost:5432/zentropy_scout
OPENAI_API_KEY=sk-...          # Required for embeddings
ANTHROPIC_API_KEY=sk-ant-...   # Only for hosted mode (future)
PROVIDER_MODE=local            # "local" or "hosted"
```

---

## Working with Requirements

1. **Start with `docs/plan/implementation_plan.md`** — shows phases and dependencies
2. **Load only the REQ document(s) needed for current task**
3. **Reference sections like "REQ-005 §4.2"**

| Topic | Primary Document |
|-------|------------------|
| Database schema | REQ-005 |
| API endpoints | REQ-006 |
| LLM providers | REQ-009 |
| Agents | REQ-007 |
| Scoring | REQ-008 |
| Content generation | REQ-010 |

---

## Session Start Checklist

Run these checks at the start of every session (before any implementation work):

1. **Docker/PostgreSQL** — Run `docker compose ps` to verify the database container is running and healthy. If not running, start it with `docker compose up -d` and wait for the healthcheck to pass.
2. **Implementation plan** — Read `docs/plan/implementation_plan.md` to find the current task (first 🟡 or ⬜).
3. **Announce** — Tell the user: "Resuming at Phase X.Y, Task §Z" and confirm Docker status.

---

## DO / DON'T

### DO:
- **Update `docs/plan/implementation_plan.md` after EVERY subtask** — see `plan-tracker` skill
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
| **Before commit** | Full test suite | `pytest tests/ -v` | Catch cross-module regressions |
| **Before push** | Full suite + lint + types | `pre-commit run --all-files` | Gate for shared code |
| **CI/CD** | Everything + coverage | GitHub Actions | Final quality gate |

### Test Quality Checklist

Before considering a test complete:

1. **Does it test behavior?** — Would a user/caller care about this assertion?
2. **Is it meaningful?** — Does it catch real bugs, not just "make coverage go up"?
3. **Is it readable?** — Can someone understand the intent without reading implementation?
4. **Is it independent?** — Does it pass/fail regardless of test execution order?
5. **Does it have a clear name?** — `test_<behavior>_when_<condition>` format preferred

### Pre-commit Hooks

This project uses `pre-commit` to enforce quality before commits. Configuration lives in `.pre-commit-config.yaml`.

```bash
# Install hooks (one-time setup)
pre-commit install --hook-type pre-commit --hook-type pre-push

# Run manually
pre-commit run --all-files
```

**Hooks run:** ruff, bandit, gitleaks, trailing whitespace (on commit); full pytest suite (on push). See `.pre-commit-config.yaml` for details.

**IMPORTANT:** Never use `--no-verify` to bypass hooks. If tests fail, fix them before committing/pushing. "Pre-existing" failures are still your responsibility to fix.

---

## Security Tooling Stack

Layered security scanning across local development and CI:

| Layer | Tool | What It Catches | When It Runs |
|-------|------|-----------------|--------------|
| **SAST (deep)** | Semgrep Team | Cross-file taint analysis, FastAPI-native injection detection | CI (GitHub Actions) |
| **SAST (fast)** | Bandit | Python security patterns (injection, secrets, weak crypto) | Pre-commit hook |
| **Code quality** | SonarCloud | Code smells, security hotspots, complexity | CI (post-push) |
| **Dependencies** | pip-audit | Known CVEs in Python packages (OSV database) | CI (GitHub Actions) |
| **Dependencies** | Dependabot | Automated vulnerability alerts + auto-PRs | GitHub (continuous) |
| **Secrets** | gitleaks | Leaked API keys, passwords, tokens in commits | Pre-commit hook |

**Semgrep Team** is free for ≤10 contributors and provides cross-function, cross-file taint tracking with FastAPI-native understanding. Requires `SEMGREP_APP_TOKEN` secret in GitHub repo settings.

**Dependabot** scans pip (backend) and GitHub Actions dependencies weekly. Configured in `.github/dependabot.yml`.

**pip-audit** uses Google's OSV database for broadest CVE coverage. Runs on every PR and push to main.

For detailed security review patterns, see `.claude/agents/security-references.md` `[TOOLS]` section.

---

## Skills Available

These skills auto-load when relevant. Ask about specific topics to trigger them:

| Skill | Triggers | Content |
|-------|----------|---------|
| `zentropy-api` | endpoint, router, REST, response, API | FastAPI patterns, response envelopes, error handling |
| `zentropy-agents` | agent, LangGraph, graph, state, HITL | Graph structure, state schemas, checkpointing |
| `zentropy-db` | database, migration, postgres, SQL | pgvector, BYTEA, Alembic patterns |
| `zentropy-provider` | LLM, Claude, API, extract, generate | Claude Agent SDK, provider abstraction |
| `zentropy-test` | test, pytest, mock, fixture, coverage | Testing patterns, mock LLM |
| `zentropy-tdd` | implement, create, build, add feature | Red-Green-Refactor cycle |
| `zentropy-playwright` | playwright, e2e, end-to-end, UI testing | E2E tests, mocking, selectors |
| `zentropy-lint` | lint, ruff, eslint, mypy, prettier | Linting stack, common errors |
| `zentropy-imports` | imports, import order | Python/TypeScript ordering |
| `zentropy-structure` | where should I put, project structure | Module organization |
| `zentropy-git` | commit, branch, git | Conventional commits, workflow |
| `zentropy-commands` | how do I start, run migrations | Docker, alembic, npm commands |
| `zentropy-docs` | docstring, documentation, comments | Google-style docstrings |
| `reflect` | remember this, add lesson, mistake, never again | Self-improvement, captures lessons |
| `config-sync` | update documentation, sync config, changed .claude/ | Keeps CLAUDE_TOOLS.md in sync |
| `plan-tracker` | plan, progress, status, resume, complete, phase | Updates implementation_plan.md after subtasks |

---

## Subagents Available

| Agent | Use For |
|-------|---------|
| `req-reader` | Look up requirement specs |
| `code-reviewer` | Review code against conventions |
| `security-reviewer` | Review code for security vulnerabilities (OWASP Top 10, injection, auth) |
| `test-runner` | Run and analyze test results |

### Proactive Subagent Usage

**BEFORE starting any implementation task:**
- **`req-reader`**: Always read the relevant REQ section first to get full spec context
- **`Explore`**: If unfamiliar with the code area, explore the codebase first

**AFTER completing code (run in parallel):**
- **`code-reviewer`** + **`security-reviewer`**: Launch BOTH simultaneously before commit
- Both are read-only — parallel execution is safe and faster

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
- `[workflow]` After completing a subtask, always follow this exact order: (1) push to remote, (2) use AskUserQuestion tool (not prose) to offer "Continue"/"Compact first"/"Stop", (3) if "Compact first" is selected, immediately provide a detailed summary for compaction. The checklist exists to prevent shortcuts at the finish line when you feel "done."

<!-- Add new lessons above this line -->

---

## Current Status

**Phase:** All backend phases complete. Frontend GUI next.
**Progress:** Phases 0–3.2 ✅ complete. Phase 4.1 (Chrome Extension) ⏸️ postponed.

**Completed Phases:** 1.1 Database Schema, 1.2 Provider Abstraction (3 future tasks remain), 1.3 API Scaffold, 2.1 LangGraph Foundation, 2.2 Chat Agent, 2.3 Onboarding Agent, 2.4 Scouter Agent, 2.5 Scoring Engine, 2.6 Strategist Agent, 2.7 Ghostwriter Agent, 2.8 Agent Communication, 3.1 Resume Generation, 3.2 Cover Letter Generation

**IMPORTANT:** After completing ANY subtask, update `docs/plan/implementation_plan.md` status (⬜ → ✅). See `plan-tracker` skill.

---

*Last updated: 2026-02-07*
