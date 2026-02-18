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

The full review-before-commit workflow (reviewers, resolution, verification) is defined in the `zentropy-planner` skill (steps 4–7). That is the single source of truth — follow it for all implementation work.

This skill covers git conventions only (branches, commit messages, workflow).

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
