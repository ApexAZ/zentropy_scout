import ast
import asyncio
import inspect
import socket
import textwrap
import uuid
from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
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

# Test auth configuration (REQ-013 §7.1)
# Security: This is a test-only secret. Production uses a real secret from env.
TEST_AUTH_SECRET = "test-secret-key-that-is-at-least-32-characters-long"  # nosec B105  # gitleaks:allow


def create_test_jwt(
    user_id: uuid.UUID = TEST_USER_ID,
    *,
    secret: str = TEST_AUTH_SECRET,
    expires_delta: timedelta | None = None,
    iat: datetime | None = None,
) -> str:
    """Create a signed JWT for test authentication.

    Args:
        user_id: User UUID to encode in the sub claim.
        secret: Signing secret (must match settings.auth_secret in tests).
        expires_delta: Time until expiration. Defaults to 1 hour.
        iat: Issued-at time. Defaults to now.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "aud": "zentropy-scout",
        "iss": "zentropy-scout",
        "exp": now + (expires_delta or timedelta(hours=1)),
        "iat": iat or now,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _is_postgres_available() -> bool:
    """Check if PostgreSQL is accepting connections.

    Returns:
        True if PostgreSQL is reachable on port 5432, False otherwise.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", 5432))
        sock.close()
        return result == 0
    except OSError:
        return False


# Check once at module load time
_POSTGRES_AVAILABLE = _is_postgres_available()


def skip_if_no_postgres() -> None:
    """Skip test if PostgreSQL is not available.

    Called by fixtures that require database connection.
    Provides clear skip message to help diagnose CI/local issues.
    """
    if not _POSTGRES_AVAILABLE:
        pytest.skip(
            "PostgreSQL not available on port 5432. "
            "Start database with: docker compose up -d"
        )


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create test database engine.

    Skips test if PostgreSQL is not available (e.g., Docker not running).
    """
    skip_if_no_postgres()

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
# API Test Fixtures (REQ-006, REQ-013)
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


# Test persona ID (consistent for tests)
TEST_PERSONA_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


@pytest_asyncio.fixture
async def test_persona(db_session: AsyncSession, test_user):
    """Create a test persona for authenticated API tests.

    REQ-006 §5.6: Ingest endpoint needs a persona to attach jobs to.

    Args:
        db_session: Database session.
        test_user: Test user (owner of persona).

    Yields:
        Persona model instance.
    """
    from app.models.persona import Persona

    persona = Persona(
        id=TEST_PERSONA_ID,
        user_id=test_user.id,
        email="persona@example.com",
        full_name="Test User",
        phone="555-1234",
        home_city="Test City",
        home_state="Test State",
        home_country="USA",
    )
    db_session.add(persona)
    await db_session.commit()
    await db_session.refresh(persona)
    yield persona


# Test job source ID
TEST_JOB_SOURCE_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")


@pytest_asyncio.fixture
async def test_job_source(db_session: AsyncSession):
    """Create a test job source for ingest tests.

    REQ-006 §5.6: Ingest creates jobs with source reference.

    Args:
        db_session: Database session.

    Yields:
        JobSource model instance.
    """
    from app.models.job_source import JobSource

    source = JobSource(
        id=TEST_JOB_SOURCE_ID,
        source_name="Extension",
        source_type="Extension",
        description="Chrome extension job capture",
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    yield source


@pytest_asyncio.fixture
async def client(
    db_engine,
    test_user,  # noqa: ARG001 - ensures user exists
    test_persona,  # noqa: ARG001 - ensures persona exists
    test_job_source,  # noqa: ARG001 - ensures job source exists
) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for authenticated API tests.

    REQ-013 §7.1: Uses JWT cookie for authentication (hosted mode).
    Enables auth_enabled=True and injects a valid JWT for TEST_USER_ID.

    Sets up:
    - Test database connection via dependency override
    - JWT auth with test secret
    - httpx.AsyncClient with ASGI transport + auth cookie

    Args:
        db_engine: Test database engine from db_engine fixture.
        test_user: Test user (ensures user exists in DB).
        test_persona: Test persona (ensures persona exists).
        test_job_source: Test job source (ensures source exists).

    Yields:
        Configured AsyncClient for making authenticated API requests.
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

    # Enable JWT auth with test secret
    original_auth_enabled = settings.auth_enabled
    original_auth_secret = settings.auth_secret
    settings.auth_enabled = True
    settings.auth_secret = SecretStr(TEST_AUTH_SECRET)

    # Generate valid JWT for test user
    test_jwt = create_test_jwt(TEST_USER_ID)

    # Create async client with auth cookie
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={settings.auth_cookie_name: test_jwt},
    ) as ac:
        yield ac

    # Cleanup
    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def unauthenticated_client(db_engine) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client without authentication.

    REQ-013 §7.1: For testing 401 responses when auth is required.
    Auth is enabled but no JWT cookie is provided.

    Args:
        db_engine: Test database engine (needed for DB override).

    Yields:
        AsyncClient with no auth cookie.
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

    # Enable auth so missing cookie triggers 401
    original_auth_enabled = settings.auth_enabled
    original_auth_secret = settings.auth_secret
    settings.auth_enabled = True
    settings.auth_secret = SecretStr(TEST_AUTH_SECRET)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Restore original settings
    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    app.dependency_overrides.clear()


# =============================================================================
# Cross-Tenant Test Fixtures (REQ-014 §10.2)
# =============================================================================

# User B constants (cross-tenant testing counterpart to TEST_USER_ID)
USER_B_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")
PERSONA_B_ID = uuid.UUID("00000000-0000-0000-0000-000000000098")


@pytest_asyncio.fixture
async def user_b(db_session: AsyncSession):
    """Create User B for cross-tenant isolation tests.

    REQ-014 §10.2: Second user for verifying data isolation.

    Args:
        db_session: Database session from db_session fixture.

    Yields:
        User model instance for User B.
    """
    from app.models import User

    user = User(id=USER_B_ID, email="userb@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user


@pytest_asyncio.fixture
async def persona_user_b(db_session: AsyncSession, user_b):
    """Create Persona for User B.

    REQ-014 §10.2: Persona owned by User B for cross-tenant tests.

    Args:
        db_session: Database session.
        user_b: User B (owner of persona).

    Yields:
        Persona model instance for User B.
    """
    from app.models.persona import Persona

    persona = Persona(
        id=PERSONA_B_ID,
        user_id=user_b.id,
        full_name="User B",
        email="persona_b@example.com",
        phone="555-9999",
        home_city="Other City",
        home_state="Other State",
        home_country="USA",
    )
    db_session.add(persona)
    await db_session.commit()
    await db_session.refresh(persona)
    yield persona


@pytest_asyncio.fixture
async def client_user_b(
    client,  # noqa: ARG001 - ensures DB override, auth config, user_a data
    user_b,  # noqa: ARG001 - ensures user_b exists in DB
    persona_user_b,  # noqa: ARG001 - ensures user_b has a persona
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client authenticated as User B for cross-tenant tests.

    REQ-014 §10.2: Depends on ``client`` to ensure DB override
    and auth settings are already configured.

    Args:
        client: User A's client (ensures DB and auth setup).
        user_b: User B (ensures user exists in DB).
        persona_user_b: User B's persona (ensures persona exists).

    Yields:
        AsyncClient authenticated as User B.
    """
    from app.main import app

    test_jwt = create_test_jwt(USER_B_ID)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={settings.auth_cookie_name: test_jwt},
    ) as ac:
        yield ac


# =============================================================================
# Autouse Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_ingest_token_store() -> Iterator[None]:
    """Reset ingest token store before each test.

    REQ-006 §5.6: Ensures clean token state between tests.

    Yields:
        None (autouse fixture).
    """
    from app.services.ingest_token_store import reset_token_store

    reset_token_store()
    yield
    reset_token_store()


@pytest.fixture(autouse=True)
def disable_rate_limiting() -> Iterator[None]:
    """Disable rate limiting during tests.

    Security: Rate limiting is tested separately; disable for other tests
    to avoid flaky failures from rate limit triggers.

    Yields:
        None (autouse fixture).
    """
    from app.core.rate_limiting import limiter

    # Store original state and disable
    original_enabled = limiter.enabled
    limiter.enabled = False

    yield

    # Restore original state
    limiter.enabled = original_enabled


# =============================================================================
# Test Antipattern Detection (warning-only)
# =============================================================================

_BANNED_FUNCTIONS = frozenset({"isinstance", "issubclass", "hasattr"})
_BANNED_ATTRS = frozenset({"__abstractmethods__"})


def _find_antipatterns_in_source(source: str) -> list[str]:
    """Scan test function source for banned structural assertion patterns."""
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return []

    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # isinstance(), issubclass(), hasattr() calls
        if isinstance(node.func, ast.Name) and node.func.id in _BANNED_FUNCTIONS:
            findings.append(node.func.id)
        # dataclasses.fields() calls
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "fields"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in ("dataclasses", "fields")
        ):
            findings.append("dataclasses.fields")
        # __abstractmethods__ access
        if isinstance(node.func, ast.Attribute) and node.func.attr in _BANNED_ATTRS:
            findings.append(node.func.attr)
    return findings


_antipattern_warnings: list[str] = []


def pytest_runtest_teardown(item: pytest.Item) -> None:
    """Check each test for antipattern usage after it runs."""
    if not hasattr(item, "obj") or not callable(item.obj):
        return
    try:
        source = inspect.getsource(item.obj)
    except (OSError, TypeError):
        return

    patterns = _find_antipatterns_in_source(source)
    if patterns:
        _antipattern_warnings.append(f"  {item.nodeid}: {', '.join(patterns)}")


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
) -> None:
    """Report test antipatterns at the end of the test session (warning only)."""
    if _antipattern_warnings:
        terminalreporter.section("test antipattern warnings")
        terminalreporter.line(
            "The following tests use banned structural assertion patterns."
        )
        terminalreporter.line(
            "See CLAUDE.md 'Test Antipatterns to Avoid' for approved alternatives."
        )
        terminalreporter.line("")
        for w in _antipattern_warnings:
            terminalreporter.line(w)
        _antipattern_warnings.clear()
