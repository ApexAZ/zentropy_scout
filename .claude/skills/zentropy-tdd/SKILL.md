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

## Core Philosophy: Behavior Over Implementation

**Test WHAT code does, not HOW it does it.** Tests should verify observable behavior from the perspective of callers, not internal implementation details.

### Good vs Bad Tests

```python
# GOOD: Tests behavior - what the caller cares about
def test_extraction_tasks_use_cheaper_model():
    adapter = ClaudeAdapter(config)
    model = adapter.get_model_for_task(TaskType.EXTRACTION)
    assert "haiku" in model.lower()

# BAD: Tests implementation - brittle, breaks on refactor
def test_routing_dict_has_nine_entries():
    assert len(DEFAULT_ROUTING) == 9
```

### When Implementation Details Matter

Test implementation when:
- **Performance guarantees** — "Must use O(1) lookup"
- **Security requirements** — "Must use constant-time comparison"
- **Contractual obligations** — "Must call audit log before delete"
- **Resource constraints** — "Must stream, not buffer"

### When Tests Should Change

- **Change tests when:** Behavior requirements change
- **Don't change tests when:** Refactoring internals

If refactoring breaks tests, they were testing implementation, not behavior.

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

## Test Quality

### Checklist

Before marking a test complete:
1. **Behavior focus** — Would a caller/user care about this assertion?
2. **Meaningful** — Does it catch real bugs, not just raise coverage?
3. **Readable** — Can someone understand intent without reading implementation?
4. **Independent** — Passes/fails regardless of test execution order?
5. **Clear name** — Uses `test_<behavior>_when_<condition>` format?

### Red Flags

- Testing exact string matches when substring would suffice
- Asserting dict/list lengths instead of contents
- Testing private methods or attributes (`_prefixed`)
- Mocking so much you're testing the mocks
- Tests that pass even if you comment out the implementation

### Anti-Patterns

| Anti-Pattern | Correct Approach |
|--------------|------------------|
| Writing implementation first | Write test first |
| Testing private methods | Test public interface only |
| Testing framework internals | Test your code's behavior |
| 100% coverage as goal | Cover critical paths and edge cases |
| Mocking everything | Use real DB for integration tests |

---

## Test Setup

### File Organization

```
backend/tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Pure logic, fully mocked
│   ├── test_extraction.py
│   └── test_scoring.py
├── integration/             # Real DB, mocked externals
│   ├── test_persona_repository.py
│   └── test_api_personas.py
└── fixtures/
```

### conftest.py

```python
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.base import Base

TEST_DATABASE_URL = "postgresql+asyncpg://zentropy_user:zentropy_dev_password@localhost:5432/zentropy_scout_test"

@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    async_session = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()
```

### Mock LLM Provider

```python
class MockLLMProvider:
    def __init__(self, responses: dict = None):
        self.responses = responses or {}
        self.calls = []

    async def complete(self, messages, task, output_schema=None, **kwargs):
        self.calls.append({"messages": messages, "task": task, "output_schema": output_schema})
        if task in self.responses:
            response = self.responses[task]
            if output_schema and isinstance(response, dict):
                return output_schema.model_validate(response)
            return response
        raise ValueError(f"No mock response for task: {task}")

@pytest.fixture
def mock_llm():
    def _create(responses=None):
        return MockLLMProvider(responses=responses)
    return _create
```

---

## Testing Patterns

### Async Code

```python
@pytest.mark.asyncio
async def test_create_persona(db_session, mock_llm):
    llm = mock_llm(responses={"extraction": {"skills": [{"name": "Python", "level": "expert"}]}})
    repo = PersonaRepository(db_session)
    service = PersonaService(repo, llm)
    persona = await service.create_from_text("I am a Python developer")
    assert persona.id is not None
    assert len(llm.calls) == 1
```

### API Endpoints

```python
@pytest_asyncio.fixture
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_create_persona_endpoint(client):
    response = await client.post("/api/v1/personas", json={"name": "Test User"})
    assert response.status_code == 201
    assert "id" in response.json()
```

---

## Property-Based Testing with Hypothesis

Use Hypothesis for testing invariants that must hold for ANY input. Especially valuable for security-sensitive code.

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

### When to Use Hypothesis vs Example-Based

| Scenario | Approach |
|----------|----------|
| Specific known inputs -> expected outputs | Example-based (pytest) |
| Invariants across all possible inputs | Property-based (Hypothesis) |
| Security: no forbidden patterns in output | Property-based (Hypothesis) |
| Regression: specific bug reproduction | Example-based (pytest) |

### Key Patterns

- Use `assume()` (not `return`) to discard invalid inputs
- Pre-compile regex at module level, not inside `@given`
- Use `st.sampled_from()` for injection-adjacent characters
- Extract shared assertion helpers for reused invariants
- Existing fuzz tests: `backend/tests/unit/test_llm_sanitization_fuzz.py`

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

If you must use noqa, track it in `implementation_plan.md` for cleanup.

---

## Running Tests

```bash
pytest -v                                    # All tests
pytest --cov=app --cov-report=html           # With coverage
pytest tests/unit/test_file.py -v            # Specific file
pytest -k "persona" -v                       # Pattern match
pytest --lf                                  # Failed tests only
```

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
