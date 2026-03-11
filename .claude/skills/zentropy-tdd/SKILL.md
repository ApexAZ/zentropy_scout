---
name: zentropy-tdd
description: |
  Test-Driven Development and testing patterns for Zentropy Scout. Load this skill when:
  - Creating new components, services, repositories, or features
  - Writing unit tests, integration tests, or test fixtures
  - Setting up pytest, conftest.py, or test databases
  - Mocking LLM providers or external services
  - Running tests or checking coverage
  - Debugging test failures or flaky tests
  - Someone says "implement", "create", "build", or "add feature"
  - Someone asks about "test", "pytest", "mock", "fixture", "coverage", "hypothesis", or "TDD"
---

# TDD & Testing Patterns

## Core Philosophy

**Test WHAT code does, not HOW it does it.** See CLAUDE.md "Testing Philosophy" for full rationale and examples.

**Decision criterion:** "Would this test still pass if I rewrote the implementation using a completely different internal structure but preserved the same external behavior?" YES = behavioral (good). NO = structural (bad).

**Exception — test implementation when:**
- **Performance guarantees** — "Must use O(1) lookup"
- **Security requirements** — "Must use constant-time comparison"
- **Contractual obligations** — "Must call audit log before delete"
- **High production risk** — Wrong model name sent to external API = silent billing/quality issue that no behavioral test can catch

---

## TDD Protocol: Red-Green-Refactor

**Never write implementation code without a failing test first.**

### 1. RED (The Specification)

Create test file BEFORE the implementation. Define public interface and expected behavior.

```python
# tests/unit/test_persona_service.py
from app.services.persona import PersonaService  # Does not exist yet!

@pytest.mark.asyncio
async def test_create_persona_extracts_skills():
    service = PersonaService(mock_llm, mock_repo)
    result = await service.create_from_text("I am a Python developer with 5 years experience")
    assert result.id is not None
    assert "Python" in [s["name"] for s in result.skills]
```

Run the test — it MUST fail (ImportError or AssertionError).

### 2. GREEN (The Implementation)

Write **minimum code** to satisfy the test. Do not over-engineer.

### 3. REFACTOR (The Cleanup)

Apply linting, add docstrings, run `ruff check . && ruff format .`, verify tests still pass.

### TDD Checklist

Before writing ANY implementation code:
- [ ] Test file exists at correct path
- [ ] Test imports the module that will be created
- [ ] Test defines expected inputs and outputs
- [ ] Test has been run and FAILED (Red)
- [ ] Failure is ImportError or AssertionError (not syntax error)

---

## Decision Matrix

| Question | Test Type | Tools |
|----------|-----------|-------|
| Pure logic? (parsing, validation) | **Unit Test** | Pytest + mocks |
| Invariant for ALL inputs? (sanitization) | **Property Test** | Pytest + Hypothesis |
| Database interaction? | **Integration Test** | Pytest + Docker DB |
| External APIs? (LLM, embeddings) | **Integration Test** | Pytest + mock provider |
| User flow/UI? | **Functional Test** | Playwright |
| API endpoint? | **Integration Test** | Pytest + httpx AsyncClient |

---

## Test Quality Checklist

Before marking a test complete:
1. **Behavior focus** — Would a caller/user care about this assertion?
2. **Meaningful** — Does it catch real bugs, not just raise coverage?
3. **Readable** — Can someone understand intent without reading implementation?
4. **Independent** — Passes/fails regardless of test execution order?
5. **Clear name** — Uses `test_<behavior>_when_<condition>` format?
6. **No companions** — Is this behavior already tested elsewhere? If yes, don't write a duplicate — either strengthen the existing test or skip this one.

---

## Test Bloat Patterns

Every test must justify its existence: **"What real bug would this test catch that no other test catches?"** If the answer is "nothing," it's bloat. These are the patterns that produce bloat — never write them.

### Structural Assertion Patterns (conftest.py hook detects some)

| Banned Pattern | Why It's Wrong | What to Do Instead |
|----------------|----------------|-------------------|
| `isinstance(result, T)` | Tests return type, not behavior | Assert on the result's value or properties |
| `issubclass(Foo, Bar)` | Tests inheritance chain | Test that `Foo` exhibits `Bar`'s behavioral contract |
| `hasattr(obj, "field")` | Tests attribute existence | Call the attribute and assert on its behavior |
| `callable(obj)` | Tests callable status | Call the function and assert on its return value |
| `get_type_hints(Cls)` / `dataclasses.fields(Cls)` | Tests schema shape | Construct instances and assert on behavior |
| `"method" in Cls.__abstractmethods__` | Tests ABC internals | Test that concrete subclasses implement the method |
| `CONSTANT == 42` / `enum.value == "literal"` | Duplicates the source code | Test behavior that depends on the constant's value |
| `len(some_enum) == N` | Breaks when enum grows | Test specific members that matter for behavior |

### Behavioral Bloat Patterns (not auto-detected)

| Pattern | Example | Why It's Bloat | Fix |
|---------|---------|----------------|-----|
| **Constructor mirror** | `obj = Foo(x=1)` → `assert obj.x == 1` | Tests that Python assignment works, not business logic. Was the #1 bloat source in the 2026-03 audit (drove most of 225 deletions). | DELETE if constructor just assigns. KEEP if constructor validates/transforms (e.g., `Entry(score=101)` → `raises ValueError` tests validation behavior, not assignment) |
| **Pass-through mock** | `mock.return_value = X` → `assert result == X` | The mock guarantees the test passes — it can never fail | If the function transforms/filters/branches on the result, assert on that. If it's pure delegation with no logic, DELETE the test — there's nothing to break |
| **Default-value mirror** | `assert config.timeout == 30` | Mirrors Pydantic/ORM default; duplicates source code | Test behavior that depends on the default (e.g., "request times out after default period") |
| **Mock-only assertion** | `mock.assert_called_once_with(args)` as sole assertion | Tests wiring, not behavior; breaks on any refactor | Add output/result assertions; mock call checks are supplementary, never primary |
| **caplog-only test** | `assert "Processing" in caplog.text` | Logging is developer convenience, not a contract; fragile to rewording | DELETE unless log message is part of a monitoring/alerting contract |
| **`is not None` sole assertion** | `assert result is not None` | Redundant when companion tests assert on properties of result | DELETE if companions exist; if no companions, add real assertions instead |
| **Subsumed/duplicate** | Same code path tested identically in two places | One test can never catch a bug the other misses | DELETE the less specific test; keep the one with richer assertions |

### Frontend-Specific Bloat Patterns (from 2026-03 audit)

| Pattern | Example | Why It's Bloat | Fix |
|---------|---------|----------------|-----|
| **Sole toBeInTheDocument smoke** | `expect(getByText("Title")).toBeInTheDocument()` | Unconditional element, companion test interacts with same element | DELETE if companion exists. KEEP if conditional render, only test for element, or tests error/empty/loading states |
| **TypeScript constructor mirror** | `const obj: IFoo = {x:1}; expect(obj.x).toBe(1)` | `tsc --noEmit` already enforces type conformance | DELETE entire test. Was the #1 frontend bloat source (167 deletions) |
| **Tailwind toHaveClass** | `expect(el).toHaveClass("bg-primary")` | Tests which CSS utility class is applied, not user-visible behavior | DELETE or remove assertion. Keep the rendered text/content assertion if present. Exception: `toHaveClass("sr-only")` for accessibility |
| **Radix data-state on tabs** | `expect(tab).toHaveAttribute("data-state", "active")` | Tests Radix UI internal attribute, not visible content | Replace with content visibility check or `data-editable` on editors. Note: `data-state` on checkboxes/switches IS legitimate |
| **Constant echo (Map/config)** | `expect(MAP.get("key")).toEqual(value)` | Duplicates source literal; behavioral tests already verify same mapping | DELETE if a function-level test covers the same path |
| **Redundant CalledTimes** | `expect(fn).toHaveBeenCalledTimes(1)` after `toHaveBeenCalledWith(args)` | CalledWith already proves the call happened; "exactly once" is rarely a behavioral contract | DELETE unless double-invocation is a known risk |

**Frontend DELETE rule (mechanical):** Delete a sole-assertion `toBeInTheDocument()` test if ALL of:
1. Uses ONLY `.toBeInTheDocument()` as its assertion
2. Element renders UNCONDITIONALLY (no props/state variation)
3. A companion test in the same file already covers the element with richer assertions (text content, attributes, interaction)

**KEEP if ANY of:** conditional rendering, only test for that element, multiple assertions (toHaveAttribute, toHaveValue, etc.), unique error/empty/loading state.

### Approved Exception: Frozen-Test Pattern

When verifying immutability, test through the public API (`replace()`), not Python's freeze mechanism:

```python
# GOOD: Tests immutability through public API
def test_result_preserves_original_on_copy():
    result = SomeResult(field="value")
    updated = replace(result, field="new")
    assert result.field == "value"   # Original unchanged
    assert updated.field == "new"    # Copy has new value
```

---

## Evaluating Existing Tests

When auditing or reviewing tests, follow this evaluation process:

1. **Read the test.** What does it assert?
2. **Read the source function.** Is the assertion testing behavior or echoing implementation?
3. **Check for companions.** Does another test already cover this behavior more thoroughly?
4. **Apply the refactor test.** Would this test still pass after a complete reimplementation that preserves external behavior?

### Dispositions

| Disposition | When to Use |
|-------------|-------------|
| **KEEP** | Actually valuable — tests real behavior, no companion covers it |
| **DELETE** | No value, no refactor path, companion covers the behavior |
| **REFACTOR** | Currently tests implementation but COULD test behavior instead |
| **CONSOLIDATE** | Multiple tests that should be one parametrized test |

---

## Test Setup Reference

All test infrastructure lives in `backend/tests/conftest.py`. Key fixtures:

### Fixture Architecture (SAVEPOINT rollback + xdist)

```
_worker_db (session-scoped) ← creates per-worker database under xdist (no-op serial)
  └─ db_engine (session-scoped) ← creates tables ONCE, drops on teardown
       └─ _ensure_schema (module-scoped, autouse) ← restores schema if migration tests destroyed it
            └─ db_connection (function-scoped) ← begin() + rollback() per test
                 └─ db_session (function-scoped) ← SAVEPOINT via join_transaction_mode="create_savepoint"
                      ├─ test_user, test_persona, test_job_source ← commit to SAVEPOINT
                      ├─ client ← yields db_session as override_get_db (same connection)
                      └─ unauthenticated_client ← same pattern, no auth
```

Each test runs inside a transaction that's rolled back — no data leaks between tests, tables created only once.

### Key Fixtures

- **`_worker_db`** — Session-scoped. Creates per-worker database under xdist (no-op in serial mode). Installs pgcrypto + vector extensions. Drops on teardown.
- **`db_engine`** — Session-scoped async engine, `loop_scope="session"`. Depends on `_worker_db`. Schema created once.
- **`db_connection`** — Function-scoped. Opens connection, begins transaction, yields, rolls back.
- **`db_session`** — Function-scoped. `AsyncSession(bind=db_connection, join_transaction_mode="create_savepoint")`. Commits go to SAVEPOINT (auto-restarted by SQLAlchemy).
- **`_ensure_schema`** — Module-scoped autouse. Detects if migration tests destroyed the schema and restores it.
- **`mock_llm`** — `MockLLMProvider` with pre-configured responses, injected into factory
- **`mock_embedding`** — `MockEmbeddingProvider` (768-dim vectors), injected into factory
- **`client`** — Authenticated `AsyncClient` with JWT cookie, DB override (`override_get_db` yields `db_session`)
- **`test_user`** / **`test_persona`** / **`test_job_source`** — Standard test data

Before writing a new test file, **always read an existing sibling test file** in the same directory to match the exact mock setup pattern, fixture usage, and naming conventions.

### File Organization

```
backend/tests/
├── conftest.py              # Shared fixtures (read this first)
├── unit/                    # Pure logic + API endpoint tests
└── fixtures/                # Test data files
```

---

## Slow Test Markers + Parallel Execution (xdist)

Tests run in parallel via `pytest-xdist` (`-n auto` in `addopts`). Migration tests are marked `@pytest.mark.slow` and **skipped by default**.

| Mode | Command | Tests | Duration |
|------|---------|-------|----------|
| **Default TDD** | `pytest tests/` | 4,134 | ~26s |
| **Full parallel** | `pytest tests/ -m ""` | 4,259 | ~34s |
| **Full serial** | `pytest tests/ -m "" -n 0` | 4,259 | ~121s |
| **Slow only** | `pytest tests/ -m slow` | 125 | ~10s |

### Marking New Migration Tests

- **100% migration file** — Add module-level: `pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("migrations")]`
- **Mixed file** — Add class-level: `@pytest.mark.slow` and `@pytest.mark.xdist_group("migrations")` on migration test classes only
- Migration files must import `TEST_DATABASE_URL` and `TEST_DB_NAME` from `tests.conftest` (not compute locally)
- Use `TEST_DB_NAME` (not `f"{original}_test"`) when patching `settings.database_name` for alembic

The pre-push hook runs with `-m "" -n auto` (all tests, parallel). Both markers are registered in `pyproject.toml`.

---

## xdist Parallel Execution

### How It Works

Each xdist worker (gw0, gw1, ...) gets its own database:
1. `PYTEST_XDIST_WORKER` env var detected at conftest import time
2. `_worker_db` session-scoped fixture creates `zentropy_scout_test_gw0` etc. with pgcrypto + vector extensions
3. `TEST_DATABASE_URL` computed with worker suffix
4. Database dropped on worker teardown

### Rules for xdist-Compatible Tests

1. **No module-level state sharing** — Each worker is a separate process with its own conftest fixtures
2. **Migration tests MUST use `xdist_group("migrations")`** — They `DROP SCHEMA public CASCADE`, which would destroy other workers' databases if run in parallel
3. **Import `TEST_DATABASE_URL` from conftest** — Never compute it locally with `settings.database_url.replace()`. The conftest version is worker-aware.
4. **`-n 0` for serial mode** — Use when debugging test ordering issues or fixture teardown problems

### Disabling xdist

```bash
# Run serial (ignore addopts -n auto)
pytest tests/ -n 0

# Or override addopts entirely
pytest tests/ -o "addopts="
```

---

## SAVEPOINT Gotchas

### Timestamp Tolerance

PostgreSQL's `now()` returns the **transaction start time**, not wall-clock time. Under SAVEPOINT isolation, `now()` in a column default may predate Python's `datetime.now()` captured before the DB operation:

```python
# BAD — can flake under SAVEPOINT
before = datetime.now(UTC)
db_session.add(Flag(user_id=user.id))
await db_session.flush()
assert flag.created_at >= before  # May fail!

# GOOD — allow tolerance for transaction time
before = datetime.now(UTC)
db_session.add(Flag(user_id=user.id))
await db_session.flush()
assert flag.created_at >= before - timedelta(seconds=2)
```

### Concurrent DB Access in Tests

The shared `db_session` is bound to a single asyncpg connection — it **cannot handle concurrent operations** (`asyncio.gather`). For true concurrency:

```python
# Create per-task sessions from the engine (each gets its own connection)
async def _make_one_call(idx):
    async with AsyncSession(db_engine, expire_on_commit=False) as task_session:
        # ... do work with task_session ...
        await task_session.commit()

results = await asyncio.gather(*[_make_one_call(i) for i in range(20)])
```

**Important:** Data committed via `db_session.commit()` only commits the SAVEPOINT, invisible to other connections. Concurrent tests must seed data directly via `AsyncSession(db_engine)` and clean up in a `finally` block or autouse fixture.

---

## Property-Based Testing with Hypothesis

Use Hypothesis for testing invariants that must hold for ANY input. Especially valuable for security-sensitive code like sanitization.

```python
from hypothesis import given, settings
from hypothesis import strategies as st

unicode_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0, max_size=500,
)

@given(unicode_text)
@settings(max_examples=500)
def test_sanitize_idempotent(text: str) -> None:
    once = sanitize_llm_input(text)
    twice = sanitize_llm_input(once)
    assert once == twice
```

| Scenario | Approach |
|----------|----------|
| Specific known inputs -> expected outputs | Example-based (pytest) |
| Invariants across all possible inputs | Property-based (Hypothesis) |
| Security: no forbidden patterns in output | Property-based (Hypothesis) |
| Regression: specific bug reproduction | Example-based (pytest) |

Key rules: use `assume()` to discard invalid inputs, pre-compile regex at module level, use `st.sampled_from()` for injection-adjacent characters. See `backend/tests/unit/test_llm_sanitization_fuzz.py` for examples.

---

## Frontend Test Setup Reference

Frontend tests use Vitest + React Testing Library + jsdom. Key patterns:

- **Test file convention:** `component-name.test.tsx` colocated with component
- **Mock pattern:** Use `vi.hoisted()` for mock definitions, `vi.mock()` for module mocking
- **Render helper:** Each file has a `renderFoo()` helper wrapping `render(<Foo {...defaults} />)`
- **User events:** `const user = userEvent.setup()` — always use `userEvent` over `fireEvent`
- **Async queries:** Use `waitFor()` for elements that appear after state changes
- **Cleanup:** `afterEach(() => { cleanup(); vi.restoreAllMocks(); })`

Before writing a new frontend test file, **always read an existing sibling test file** in the same directory to match the exact `vi.hoisted()` shape, `MockApiError` inclusion, `beforeEach`/`afterEach` hooks, ID format, and testid prefixes.

---

## Handling Stubs During TDD

Prefer underscore prefix over `noqa` for unused stub parameters:

```python
# Good
async def complete(self, _messages, _task, _max_tokens=None):
    raise NotImplementedError("Implementation in next task")

# Avoid
async def complete(self, messages, task, max_tokens=None):  # noqa: ARG002
    raise NotImplementedError("Implementation in next task")
```

If you must use noqa, track it in the active plan file for cleanup.

---

## Workflow Summary

```
1. THINK   -> What should this component do?
2. TEST    -> Write test defining that behavior
3. RUN     -> pytest (must FAIL)
4. CODE    -> Minimum implementation
5. RUN     -> pytest (must PASS)
6. CLEAN   -> ruff format, docstrings
7. RUN     -> pytest (still PASS)
8. COMMIT  -> "feat(component): add X with tests"
```
