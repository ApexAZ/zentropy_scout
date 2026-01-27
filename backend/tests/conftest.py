import asyncio
from collections.abc import AsyncGenerator, Iterator

import pytest
import pytest_asyncio
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
