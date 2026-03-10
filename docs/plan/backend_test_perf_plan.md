# Backend Test Performance Optimization Plan

**Created:** 2026-03-10
**Status:** 🟡 In Progress

---

## Context

The backend has 4,259 tests across 193 files taking ~467s (7m47s). Profiling revealed **338s (72%) is fixture setup**: `db_engine` and `db_session` in `backend/tests/conftest.py` are function-scoped, running `Base.metadata.create_all` and `Base.metadata.drop_all` for EVERY test — 4,259 full schema create/drop cycles.

This is a **DX/infrastructure improvement** — no formal REQ document. Motivated by:
- Faster TDD feedback loops (~7x speedup target)
- Fixing a known flaky test caused by PostgreSQL overload
- Enabling parallel execution for further gains

### Current Fixture Architecture

```
db_engine (function-scoped) ← creates/drops ALL tables per test
  └─ db_session (function-scoped) ← new session, rollback on teardown
       ├─ test_user, test_persona, test_job_source ← commit test data
       └─ client (also depends on db_engine directly) ← creates own sessionmaker
```

**Key complication:** `client` fixture creates its own `async_sessionmaker` from `db_engine` (line 307). Its `override_get_db` yields sessions on a DIFFERENT connection than `db_session`. With SAVEPOINT isolation, the `client`'s API sessions must share the SAME connection as `db_session` to see test data.

**Solution:** Introduce a `db_connection` intermediate fixture. Both `db_session` and `client` bind to the same connection → same transaction → test data visible everywhere.

### Flaky Test

`test_api_usage.py::test_summary_does_not_expose_margin_multiplier` (line 285) — `KeyError: 'data'` because `response.json()["data"]` fails when PostgreSQL returns errors under full-suite load. Passes 100% in isolation.

---

## How to Use This Document

1. Find the first ⬜ task — that's where to start
2. Each task = one commit, sized for ~60k variable tokens
3. After each task: update status → commit → STOP and ask user
4. After each phase: full test suite as quality gate

---

## Dependency Chain

```
Phase 1: Session-Scoped Engine + SAVEPOINT Rollback (core refactor)
    ↓
Phase 2: Slow Test Markers (independent, quick DX win)
    ↓
Phase 3: pytest-xdist Parallel Execution (depends on Phase 1)
```

---

## Phase 1: Session-Scoped Engine + SAVEPOINT Rollback

**Status:** 🟡 In Progress

*Refactor `backend/tests/conftest.py` to create tables ONCE at session start, wrap each test in a SAVEPOINT, and rollback after. Fixes the flaky test by eliminating PostgreSQL overload. Expected: ~467s → ~130-170s.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read `backend/tests/conftest.py`, `backend/app/core/database.py` |
| 🧪 **TDD** | Verify all 4,259 tests pass before AND after refactor |
| 🗃️ **Patterns** | SQLAlchemy docs: "Joining a Session into an External Transaction" |
| ✅ **Verify** | `cd backend && pytest tests/ -v` — full suite, all pass |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 1 | **Security triage gate** — Spawn `security-triage` subagent (general-purpose, opus, foreground). Verdicts: CLEAR → proceed. VULNERABLE → fix. FALSE POSITIVE → PROSECUTION PROTOCOL. NEEDS INVESTIGATION → escalate. | `plan, security` | ✅ |
| 2 | **Defensive fix for flaky test** — Read `backend/tests/unit/test_api_usage.py` lines 284-298. Add `assert response.status_code == 200, response.text` before `response.json()["data"]` access. Makes failure diagnostic instead of cryptic KeyError. Verify: `pytest tests/unit/test_api_usage.py -v`. | `tdd, plan` | ✅ |
| 3 | **Refactor conftest.py: session-scoped engine + SAVEPOINT rollback** — Core refactor of `backend/tests/conftest.py`. See implementation notes below. Verify: `cd backend && pytest tests/ -v` — all 4,259 tests pass. Benchmark new duration vs 467s baseline. | `tdd, db, plan` | ✅ 2026-03-10 19:55 UTC — 4,259 passed, 120.88s (3.86x speedup) |
| 4 | **Phase 1 gate — full test suite + push** — Run full backend + frontend suite. Record new duration. Fix regressions. Commit, push. | `plan, commands` | ⬜ |

#### §3 Implementation Notes

**Step 1 — Session-scoped engine:**
```python
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def db_engine():
    skip_if_no_postgres()
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)   # ONCE
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)      # ONCE
    await engine.dispose()
```

**Step 2 — New `db_connection` fixture (function-scoped):**
```python
@pytest_asyncio.fixture(scope="function")
async def db_connection(db_engine):
    async with db_engine.connect() as conn:
        trans = await conn.begin()
        yield conn
        await trans.rollback()
```
This is the isolation boundary — each test gets a transaction that's rolled back.

**Step 3 — Refactor `db_session` to use SAVEPOINT:**
```python
@pytest_asyncio.fixture(scope="function")
async def db_session(db_connection):
    nested = await db_connection.begin_nested()  # SAVEPOINT
    session = AsyncSession(bind=db_connection, expire_on_commit=False)

    @event.listens_for(session.sync_session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    yield session
    await session.close()
```
The event listener restarts the SAVEPOINT after `session.commit()` calls (171 occurrences across 37 files). No test code changes needed.

**Step 4 — Refactor `client` to share the connection:**
```python
@pytest_asyncio.fixture
async def client(db_session, test_user, test_persona, test_job_source):
    from app.core.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session  # Same connection → sees test data

    app.dependency_overrides[get_db] = override_get_db
    # ... rest unchanged (auth setup, AsyncClient, cleanup)
```
Remove `db_engine` from `client`'s parameter list. Remove the `test_session_factory` creation. Same for `unauthenticated_client` → depend on `db_session` instead of `db_engine`.

**Step 5 — Update `pyproject.toml`:**
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
testpaths = ["tests"]
```

**Step 6 — Add import:**
```python
from sqlalchemy import event  # Add to conftest.py imports
```

**Migration tests are UNAFFECTED** — 5 files define their own `migration_engine` fixtures locally. They don't use conftest's `db_engine`.

**High-risk tests to watch:** `test_retention_cleanup.py` (ON COMMIT DROP), `test_cross_tenant_isolation.py` (multi-user commits), `test_race_conditions.py` (production `begin_nested()`), `test_api_usage.py` (formerly flaky).

---

## Phase 2: Slow Test Markers

**Status:** ⬜ Incomplete

*Mark migration tests with `@pytest.mark.slow` and configure default filtering. Improves day-to-day TDD feedback by skipping ~119 inherently slow migration tests.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read migration test files to identify marker targets |
| 🧪 **TDD** | Verify `pytest` skips slow tests, `pytest -m ""` runs all |
| ✅ **Verify** | Both fast and full modes pass |
| 🔍 **Review** | `code-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 5 | **Add `@pytest.mark.slow` + configure filtering** — Register `slow` marker in `pyproject.toml`. Add `pytestmark = pytest.mark.slow` to all 5 migration test files. Add class-level `@pytest.mark.slow` to `TestMigration020Upgrade` and `TestMigration020Downgrade` in `test_metering_models.py` (NOT module-level — file has non-migration tests). Set `addopts = "-m 'not slow'"` in `pyproject.toml`. Update pre-push hook to add `-m ""`. Verify: default run skips slow, `-m ""` runs all, `-m slow` runs only migration tests. | `tdd, plan` | ⬜ |
| 6 | **Phase 2 gate — full test suite + push** — Run full suite with `-m ""`. Fix regressions. Commit, push. | `plan, commands` | ⬜ |

#### Files to Mark
| File | Marker Level | Why |
|------|-------------|-----|
| `test_migration_010_auth_tables.py` | Module (`pytestmark`) | 100% migration tests |
| `test_migration_011_rename_indexes.py` | Module | 100% migration tests |
| `test_migration_012_persona_jobs.py` | Module | 100% migration tests |
| `test_migration_013_backfill.py` | Module | 100% migration tests |
| `test_migration_014_drop_per_user_columns.py` | Module | 100% migration tests |
| `test_metering_models.py` | Class-level only | Mixed file — only migration classes |

#### Pre-push Hook Update
Current (line 100 of `.pre-commit-config.yaml`):
```bash
cd backend && .venv/bin/python -m pytest tests/ -v --tb=short
```
New:
```bash
cd backend && .venv/bin/python -m pytest tests/ -v --tb=short -m ""
```

---

## Phase 3: pytest-xdist Parallel Execution

**Status:** ⬜ Incomplete

*Install pytest-xdist and configure parallel test execution across multiple workers. Each worker gets its own database. Expected: ~130-170s → ~40-80s with 4 workers.*

#### Workflow
| Step | Action |
|------|--------|
| 📖 **Before** | Read post-Phase-1 conftest.py, pyproject.toml |
| 🧪 **TDD** | Verify all tests pass with `-n auto` |
| 🗃️ **Patterns** | pytest-xdist docs for per-worker database provisioning |
| ✅ **Verify** | `pytest -n auto -m ""` — all pass in parallel |
| 🔍 **Review** | `code-reviewer` + `security-reviewer` |
| 📝 **Commit** | One commit per subtask |

#### Tasks
| § | Task | Hints | Status |
|---|------|-------|--------|
| 7 | **Install pytest-xdist + per-worker database provisioning** — Add `pytest-xdist>=3.5.0` to dev deps. Create per-worker DB provisioning in conftest.py: detect `worker_id`, create `zentropy_scout_test_gw0` etc. at session start, update `TEST_DATABASE_URL`, drop at session end. Add `@pytest.mark.xdist_group("migrations")` to migration tests (they DROP/CREATE schema — can't run in parallel). Update `addopts` to include `-n auto`. Update pre-push hook. Verify: `pytest -n auto -m "not slow"` (fast parallel), `pytest -n auto -m ""` (all parallel). | `tdd, db, plan` | ⬜ |
| 8 | **Phase 3 gate — full test suite + push** — Run full suite parallel. Record final duration vs 467s baseline. Fix regressions. Commit, push. | `plan, commands` | ⬜ |

#### §7 Implementation Notes

**Per-worker database lifecycle:**
1. Session-scoped fixture `_worker_db` detects `worker_id` fixture (`"master"` if serial)
2. Connects to `postgres` database, runs `CREATE DATABASE zentropy_scout_test_{worker_id}`
3. Updates `TEST_DATABASE_URL` module variable for the session-scoped `db_engine`
4. On teardown: `DROP DATABASE`

**Migration test isolation under xdist:** Migration tests run `DROP SCHEMA public CASCADE` — if two workers run them simultaneously, they'll interfere. Solution: `@pytest.mark.xdist_group("migrations")` forces all migration tests to a single worker.

**Risk:** Phase 3 adds complexity. If it proves flaky, the plan can stop after Phase 2 — the ~300s savings from Phase 1 alone is a major win.

---

## Task Count Summary

| Phase | Subtasks | Gates | Total |
|-------|----------|-------|-------|
| 1: Session-Scoped Engine + SAVEPOINT | 2 | 2 (security + test) | 4 |
| 2: Slow Test Markers | 1 | 1 | 2 |
| 3: pytest-xdist Parallel | 1 | 1 | 2 |
| **Total** | **4** | **4** | **8** |

---

## Critical Files Reference

| File | Phase | Changes |
|------|-------|---------|
| `backend/tests/conftest.py` | §3, §7 | Session-scoped engine, `db_connection`, SAVEPOINT `db_session`, `client`/`unauthenticated_client` refactor, xdist DB provisioning |
| `backend/pyproject.toml` | §3, §5, §7 | `asyncio_default_fixture_loop_scope`, `slow` marker, `addopts`, xdist dep |
| `backend/tests/unit/test_api_usage.py` | §2 | Defensive `status_code` assertion |
| `.pre-commit-config.yaml` | §5, §7 | Pre-push hook: `-m ""`, `-n auto` |
| `backend/tests/unit/test_migration_01{0-4}_*.py` | §5 | `pytestmark = pytest.mark.slow` |
| `backend/tests/unit/test_metering_models.py` | §5 | Class-level `@pytest.mark.slow` on migration classes |

---

## Expected Performance

| Phase | Duration | Speedup |
|-------|----------|---------|
| Baseline | ~467s | — |
| After Phase 1 (SAVEPOINT) | ~130-170s | ~3x |
| After Phase 2 (slow markers, default) | ~100-140s | ~3.5x (skips ~119 migration tests) |
| After Phase 3 (xdist, 4 workers) | ~40-80s | ~6-10x |

---

## Verification

After each phase gate:
1. `cd backend && pytest tests/ -v` — all tests pass
2. `cd frontend && npm run test:run && npm run lint && npm run typecheck` — frontend unaffected
3. Compare test duration to baseline (467s)
4. The formerly flaky test (`test_summary_does_not_expose_margin_multiplier`) passes reliably

---

## Change Log

| Date | Change |
|------|--------|
| 2026-03-10 | Plan created. 3 phases, 8 items. DX infrastructure — no REQ document. |
