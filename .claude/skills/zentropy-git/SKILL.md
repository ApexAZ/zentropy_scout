---
name: zentropy-git
description: |
  Git workflow conventions for Zentropy Scout. Load when:
  - Creating branches, committing, or preparing PRs
  - Someone mentions "commit", "branch", "git", or "conventional commits"
---

# Zentropy Scout Git Conventions

## Branch Naming

```
feature/phase-1.1-database-schema
feature/phase-2.3-onboarding-agent
fix/persona-validation-error
docs/update-req-005-migration-notes
refactor/extract-llm-retry-logic
```

| Prefix | Use Case |
|--------|----------|
| `feature/` | New functionality |
| `fix/` | Bug fixes |
| `docs/` | Documentation only |
| `refactor/` | Code restructuring (no behavior change) |
| `test/` | Adding or fixing tests |
| `chore/` | Build, deps, CI changes |

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Examples

```bash
feat(db): add personas and job_postings tables
fix(api): handle null culture_text in extraction
docs(req): update REQ-005 with JSONB index notes
refactor(providers): extract retry logic to base class
test(scoring): add cosine similarity edge cases
chore(deps): upgrade pydantic to 2.6.0
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation |
| `refactor` | Code change (no feature/fix) |
| `test` | Adding/fixing tests |
| `chore` | Maintenance (deps, CI, build) |
| `perf` | Performance improvement |

### Scopes

| Scope | Area |
|-------|------|
| `db` | Database, migrations |
| `api` | API endpoints |
| `agents` | LangGraph agents |
| `providers` | LLM/embedding providers |
| `ui` | Frontend |
| `extension` | Chrome extension |
| `docs` | Documentation |
| `deps` | Dependencies |
| `ci` | CI/CD |

## Workflow

```bash
# 1. Create feature branch
git checkout -b feature/phase-1.1-database

# 2. Make changes, commit often
git add .
git commit -m "feat(db): add persona table with JSONB skills"

# 3. Push and create PR
git push -u origin feature/phase-1.1-database

# 4. After review, squash merge to main
```

## Pre-Commit Quality Gate

**REQUIRED:** Before committing ANY code changes (new files, refactors, or multi-file edits), you MUST follow this quality workflow:

### Step 1: Code Review + Security Review (MANDATORY, run in parallel)
1. After making changes but BEFORE committing
2. Launch BOTH `code-reviewer` AND `security-reviewer` agents simultaneously
3. Both are read-only (Read, Grep, Glob only) — parallel execution is safe
4. Wait for both reviews to complete

### Step 2: Fix ALL Issues (MANDATORY)
5. **ALL findings must be addressed** - regardless of severity (Critical, Major, Minor, Low)
6. Security issues take priority but ALL must be fixed
7. Do NOT commit until every finding is resolved
8. **If fixes change behavior:** Write/update tests FIRST (TDD)
9. **If fixes are implementation-only:** Existing tests should still pass

### Step 3: Re-Review If Fixes Were Made
10. If you made fixes, re-run BOTH reviewers in parallel
11. Repeat until both return clean reports

### Step 4: Verify Tests
12. Run affected tests: `pytest tests/unit/test_<module>.py -v`
13. If behavior changed, ensure new tests cover the change
14. All tests must pass before proceeding

### Step 5: Commit
15. Once ALL review findings are fixed and tests are green, proceed with commit

### Quick Reference
```
┌─────────────────┐     ┌──────────────────┐
│  code-reviewer  │     │ security-reviewer│
│   (parallel)    │     │    (parallel)    │
└────────┬────────┘     └────────┬─────────┘
         └───────────┬───────────┘
                     ▼
         Combine all findings
                     ↓
         Fix ALL issues (every severity)
                     ↓
         Fixes made? → Re-run BOTH reviewers
                     ↓
         Behavior changed? → Write/update tests (TDD)
                     ↓
         Run tests (must pass)
                     ↓
         Commit
```

**Why fix ALL findings?** Low-severity issues accumulate into technical debt and inconsistent code. Security issues, even minor ones, can become exploit vectors. Fixing them immediately is faster than tracking them for later.

## Commit Message Tips

- **Subject line:** Max 50 chars, imperative mood ("add" not "added")
- **Body:** Wrap at 72 chars, explain what and why (not how)
- **Footer:** Reference issues (`Closes #123`)

```bash
# Good
feat(db): add persona table with skills JSONB column

# Bad
feat: added some database stuff
```
