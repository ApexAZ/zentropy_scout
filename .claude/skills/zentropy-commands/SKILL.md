---
name: zentropy-commands
description: |
  Common CLI commands for Zentropy Scout. Load when:
  - Running docker, alembic, pytest, npm, or gh commands
  - Someone asks "how do I start", "run migrations", "start the server", or "check CI"
---

# Zentropy Scout Common Commands

## Database (Docker)

```bash
# Start PostgreSQL + pgvector
docker compose up -d

# Stop (keeps data)
docker compose down

# Stop and DELETE all data
docker compose down -v

# Connect to psql
docker compose exec postgres psql -U zentropy_user -d zentropy_scout

# View logs
docker compose logs -f postgres
```

## Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/WSL

# Install dependencies
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start dev server (MUST run from project root, not backend/, so .env is found)
cd /home/brianhusk/repos/zentropy_scout
source backend/.venv/bin/activate
uvicorn backend.app.main:app --reload --port 8000

# Run tests (default: skip slow, parallel via xdist)
pytest tests/ -v                          # ~26s, 4,134 tests

# Run ALL tests (including slow migration tests)
pytest tests/ -v -m ""                    # ~34s, 4,259 tests

# Run serial (no xdist, for debugging)
pytest tests/ -v -m "" -n 0              # ~121s

# Run specific test file
pytest tests/unit/test_personas.py -v

# Run with coverage
pytest --cov=app --cov-report=html -m ""

# Lint and format
ruff check .
ruff format .

# Type check
pyright
```

## Alembic (Migrations)

```bash
cd backend

# Create new migration (auto-generate from models)
alembic revision --autogenerate -m "add persona table"

# Create empty migration (manual)
alembic revision -m "add custom index"

# Apply all migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade abc123

# Show current revision
alembic current

# Show migration history
alembic history

# Show SQL without applying
alembic upgrade head --sql
```

## Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Type check
npm run typecheck

# Lint
npm run lint
```

## Visual Regression (Docker)

```bash
cd frontend

# Run visual regression tests (compare against committed baselines)
npm run test:e2e:visual

# Update baselines after intentional UI changes
npm run test:e2e:visual:update
```

> **Note:** Visual regression tests run inside Docker (Ubuntu Noble) to ensure
> consistent font rendering between WSL2 local and CI. Baselines live in
> `frontend/tests/__screenshots__/` and must be committed to git.

## CI / GitHub (gh CLI)

```bash
# List recent workflow runs
gh run list --limit=5

# Trigger a workflow manually
gh workflow run semgrep.yml
gh workflow run sonarcloud.yml
gh workflow run pip-audit.yml

# Watch a running workflow
gh run watch <run-id>

# View logs for a failed run
gh run view <run-id> --log-failed

# List repo secrets (names only, not values)
gh secret list

# Check PR status and checks
gh pr status
gh pr checks

# View PR comments
gh api repos/ApexAZ/zentropy_scout/pulls/<pr-number>/comments
```

## Quick Reference

| Task | Command |
|------|---------|
| Start DB | `docker compose up -d` |
| Stop DB | `docker compose down` |
| Reset DB | `docker compose down -v && docker compose up -d` |
| Migrate | `cd backend && alembic upgrade head` |
| Backend | `cd /home/brianhusk/repos/zentropy_scout && source backend/.venv/bin/activate && uvicorn backend.app.main:app --reload --port 8000` |
| Frontend | `cd frontend && npm run dev` |
| Tests (default) | `cd backend && pytest -v` |
| Tests (all) | `cd backend && pytest -v -m ""` |
| Tests (serial) | `cd backend && pytest -v -m "" -n 0` |
| Visual regression | `cd frontend && npm run test:e2e:visual` |
| Update baselines | `cd frontend && npm run test:e2e:visual:update` |
| Lint | `cd backend && ruff check . && ruff format .` |
