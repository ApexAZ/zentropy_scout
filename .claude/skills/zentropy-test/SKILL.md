---
name: zentropy-test
description: |
  Testing patterns for Zentropy Scout. Load this skill when:
  - Writing unit tests, integration tests, or test fixtures
  - Setting up pytest, conftest.py, or test databases
  - Mocking LLM providers or external services
  - Running tests or checking coverage
  - Debugging test failures or flaky tests
  - Someone asks about "test", "pytest", "mock", "fixture", "coverage", or "TDD"
---

# Zentropy Scout Testing Patterns

## Testing Philosophy: Behavior Over Implementation

**CRITICAL:** Always test WHAT code does, not HOW it does it. Tests should verify observable behavior from the perspective of callers, not internal implementation details.

### Good vs Bad Tests

```python
# GOOD: Tests behavior - what the caller cares about
def test_extraction_tasks_use_cheaper_model():
    """Extraction should route to a cost-effective model."""
    adapter = ClaudeAdapter(config)
    model = adapter.get_model_for_task(TaskType.EXTRACTION)
    assert "haiku" in model.lower()  # Tests observable behavior

# BAD: Tests implementation - brittle, breaks on refactor
def test_routing_dict_has_nine_entries():
    """Don't test internal data structure sizes."""
    assert len(DEFAULT_ROUTING) == 9  # Implementation detail

# GOOD: Tests contract/interface
def test_provider_returns_response_with_content():
    """Provider should return response with content field."""
    response = await provider.complete(messages, task)
    assert response.content is not None  # Tests the contract

# BAD: Tests internal state
def test_provider_sets_internal_client():
    """Don't test private attributes."""
    assert provider._client is not None  # Private implementation
```

### When Tests Should Change

- **Change tests when:** Behavior requirements change
- **Don't change tests when:** Refactoring internals

If refactoring breaks tests, the tests were testing implementation, not behavior.

### Test Quality Checklist

Before marking a test complete, verify:

1. **Behavior focus:** Would a caller/user care about this assertion?
2. **Meaningful:** Does it catch real bugs, not just "make coverage go up"?
3. **Readable:** Can someone understand intent without reading implementation?
4. **Independent:** Passes/fails regardless of test execution order?
5. **Clear name:** Uses `test_<behavior>_when_<condition>` format?

### Red Flags in Tests

Watch for these anti-patterns:

- Testing exact string matches when substring would suffice
- Asserting dict/list lengths instead of contents
- Testing private methods or attributes (`_prefixed`)
- Mocking so much that you're testing the mocks, not the code
- Tests that pass even if you comment out the implementation

---

## Test Structure

```
backend/tests/
├── conftest.py              # Shared fixtures
├── test_personas.py         # Mirror source structure
├── test_job_postings.py
├── repositories/
│   └── test_persona_repository.py
└── services/
    └── test_extraction_service.py
```

## conftest.py Setup

```python
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.base import Base

# Test database URL (use separate test DB)
TEST_DATABASE_URL = "postgresql+asyncpg://zentropy_user:zentropy_dev_password@localhost:5432/zentropy_scout_test"

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    """Create test database session."""
    async_session = sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session
        await session.rollback()
```

## Mock LLM Provider

```python
from typing import Optional, Type
from pydantic import BaseModel

class MockLLMProvider:
    """Mock provider for testing without real API calls."""

    def __init__(self, responses: dict[str, any] = None):
        self.responses = responses or {}
        self.calls = []  # Track calls for assertions

    async def complete(
        self,
        messages: list[dict],
        task: str,
        output_schema: Optional[Type[BaseModel]] = None,
        **kwargs
    ):
        # Record the call
        self.calls.append({
            "messages": messages,
            "task": task,
            "output_schema": output_schema,
        })

        # Return configured response or default
        if task in self.responses:
            response = self.responses[task]
            if output_schema and isinstance(response, dict):
                return output_schema.model_validate(response)
            return response

        raise ValueError(f"No mock response configured for task: {task}")

@pytest.fixture
def mock_llm():
    """Fixture that returns a factory for mock providers."""
    def _create(responses: dict = None):
        return MockLLMProvider(responses=responses)
    return _create
```

## Testing Async Code

```python
import pytest

@pytest.mark.asyncio
async def test_create_persona(db_session, mock_llm):
    """Test persona creation with mocked LLM."""
    # Arrange
    llm = mock_llm(responses={
        "extraction": {
            "skills": [{"name": "Python", "level": "expert"}],
            "experiences": [],
        }
    })
    repo = PersonaRepository(db_session)
    service = PersonaService(repo, llm)

    # Act
    persona = await service.create_from_text("I am a Python developer")

    # Assert
    assert persona.id is not None
    assert len(llm.calls) == 1
    assert llm.calls[0]["task"] == "extraction"
```

## Testing Repository Layer

```python
@pytest.mark.asyncio
async def test_persona_repository_create(db_session):
    """Test repository CRUD operations."""
    repo = PersonaRepository(db_session)

    # Create
    persona = await repo.create(PersonaCreate(
        name="Test User",
        skills={"python": {"level": "expert"}}
    ))

    assert persona.id is not None

    # Read
    found = await repo.get_by_id(persona.id)
    assert found.name == "Test User"

    # Update
    updated = await repo.update(persona.id, {"name": "Updated Name"})
    assert updated.name == "Updated Name"

    # Delete
    await repo.delete(persona.id)
    assert await repo.get_by_id(persona.id) is None
```

## Testing API Endpoints

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest_asyncio.fixture
async def client(db_session):
    """Create test client with overridden dependencies."""
    app.dependency_overrides[get_db] = lambda: db_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_create_persona_endpoint(client):
    """Test POST /api/v1/personas."""
    response = await client.post(
        "/api/v1/personas",
        json={"name": "Test User"}
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "Test User"
```

## Running Tests

```bash
# Run all tests
pytest -v

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific file
pytest tests/test_personas.py -v

# Run tests matching pattern
pytest -k "persona" -v

# Run with output
pytest -v -s

# Run failed tests only
pytest --lf
```

## pyproject.toml Test Config

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
filterwarnings = [
    "ignore::DeprecationWarning",
]

[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/__init__.py"]
```
