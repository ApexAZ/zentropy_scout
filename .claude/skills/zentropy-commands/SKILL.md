---
name: zentropy-commands
description: |
  Common CLI commands for Zentropy Scout. Load when:
  - Running docker, alembic, pytest, npm commands
  - Someone asks "how do I start", "run migrations", or "start the server"
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

# Start dev server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest -v

# Run specific test file
pytest tests/test_personas.py -v

# Run with coverage
pytest --cov=app --cov-report=html

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

## Quick Reference

| Task | Command |
|------|---------|
| Start DB | `docker compose up -d` |
| Stop DB | `docker compose down` |
| Reset DB | `docker compose down -v && docker compose up -d` |
| Migrate | `cd backend && alembic upgrade head` |
| Backend | `cd backend && uvicorn app.main:app --reload` |
| Frontend | `cd frontend && npm run dev` |
| Tests | `cd backend && pytest -v` |
| Lint | `cd backend && ruff check . && ruff format .` |
