import asyncio
import uuid
from collections.abc import AsyncGenerator, Iterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.models.base import Base
from app.providers import factory
from app.providers.embedding.mock_adapter import MockEmbeddingProvider
from app.providers.llm.base import TaskType
from app.providers.llm.mock_adapter import MockLLMProvider

# Use separate test database
TEST_DATABASE_URL = settings.database_url.replace(
    settings.database_name, f"{settings.database_name}_test"
)

# Test user ID (consistent across tests for predictable auth)
TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
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
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_llm() -> Iterator[MockLLMProvider]:
    """Fixture that provides mock LLM and resets after test.

    REQ-009 §9.2: Provides MockLLMProvider with pre-configured responses
    for common task types. Automatically injects into factory singleton
    and resets after test.

    Yields:
        MockLLMProvider instance with pre-configured responses.
    """
    mock = MockLLMProvider(
        {
            TaskType.SKILL_EXTRACTION: '{"skills": ["Python", "SQL"]}',
            TaskType.COVER_LETTER: "Dear Hiring Manager...",
        }
    )

    # Inject mock into factory singleton
    factory._llm_provider = mock

    yield mock

    # Reset after test
    factory.reset_providers()


@pytest.fixture
def mock_embedding() -> Iterator[MockEmbeddingProvider]:
    """Fixture that provides mock embedding provider and resets after test.

    REQ-009 §9.2: Provides MockEmbeddingProvider with 1536-dimension vectors
    (matching text-embedding-3-small). Automatically injects into factory
    singleton and resets after test.

    Yields:
        MockEmbeddingProvider instance.
    """
    mock = MockEmbeddingProvider()

    # Inject mock into factory singleton
    factory._embedding_provider = mock

    yield mock

    # Reset after test
    factory.reset_providers()


# =============================================================================
# API Test Fixtures (REQ-006)
# =============================================================================


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user in the database.

    REQ-006 §6.1: Provides a User for authenticated API tests.

    Args:
        db_session: Database session from db_session fixture.

    Yields:
        User model instance.
    """
    from app.models import User

    user = User(id=TEST_USER_ID, email="test@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user


@pytest_asyncio.fixture
async def client(
    db_engine,
    test_user,  # noqa: ARG001 - ensures user exists
) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for authenticated API tests.

    REQ-006 §6.1: Sets up test database and DEFAULT_USER_ID for auth.

    Sets up:
    - Test database connection via dependency override
    - DEFAULT_USER_ID for local-first auth
    - httpx.AsyncClient with ASGI transport

    Args:
        db_engine: Test database engine from db_engine fixture.
        test_user: Test user (ensures user exists in DB).

    Yields:
        Configured AsyncClient for making API requests.
    """
    from app.core.database import get_db
    from app.main import app

    # Create session factory for this test
    test_session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Override get_db to use test database
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # Set test user ID in settings for auth
    original_user_id = settings.default_user_id
    settings.default_user_id = TEST_USER_ID

    # Create async client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Cleanup
    settings.default_user_id = original_user_id
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def unauthenticated_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client without authentication.

    REQ-006 §6.1: For testing 401 responses when auth is required.

    Yields:
        AsyncClient with no DEFAULT_USER_ID configured.
    """
    from app.main import app

    # Ensure no default user (unauthenticated)
    original_user_id = settings.default_user_id
    settings.default_user_id = None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Restore original setting
    settings.default_user_id = original_user_id
