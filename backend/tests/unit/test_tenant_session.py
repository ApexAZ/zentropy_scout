"""Tests for TenantScopedSession wrapper.

REQ-014 §7.3: TenantScopedSession wraps AsyncSession with automatic
user_id filtering for defense-in-depth tenant isolation.

Tests verify:
- get_persona returns owned persona
- get_persona raises NotFoundError for other user's persona
- get_persona raises NotFoundError for non-existent persona
- list_personas returns only owned personas
- verify_persona_ownership returns True/False correctly
- user_id property is read-only and immutable
"""

import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.tenant_session import TenantScopedSession
from tests.conftest import TEST_USER_ID

OTHER_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def user_and_persona(db_session: AsyncSession):
    """Create test user with a persona."""
    from app.models import Persona, User

    user = User(id=TEST_USER_ID, email="tenant_test@example.com")
    db_session.add(user)
    await db_session.flush()

    persona = Persona(
        id=uuid.uuid4(),
        user_id=user.id,
        full_name="Test User",
        email="tenant_persona@example.com",
        phone="555-1111",
        home_city="Test City",
        home_state="TS",
        home_country="USA",
    )
    db_session.add(persona)
    await db_session.commit()
    await db_session.refresh(persona)
    return user, persona


@pytest_asyncio.fixture
async def other_user_persona(db_session: AsyncSession):
    """Create another user with a persona for cross-tenant tests."""
    from app.models import Persona, User

    other_user = User(id=OTHER_USER_ID, email="other_tenant@example.com")
    db_session.add(other_user)
    await db_session.flush()

    persona = Persona(
        id=uuid.uuid4(),
        user_id=other_user.id,
        full_name="Other User",
        email="other_persona@example.com",
        phone="555-2222",
        home_city="Other City",
        home_state="OS",
        home_country="USA",
    )
    db_session.add(persona)
    await db_session.commit()
    await db_session.refresh(persona)
    return other_user, persona


@pytest_asyncio.fixture
async def scoped_session(
    db_session: AsyncSession, user_and_persona
) -> TenantScopedSession:
    """Create a TenantScopedSession for the test user."""
    user, _persona = user_and_persona
    return TenantScopedSession(db_session, user.id)


# =============================================================================
# get_persona
# =============================================================================


class TestGetPersona:
    """TenantScopedSession.get_persona — Pattern A ownership check."""

    @pytest.mark.asyncio
    async def test_returns_owned_persona(
        self, scoped_session: TenantScopedSession, user_and_persona
    ) -> None:
        """Returns persona when it belongs to the session user."""
        user, persona = user_and_persona

        result = await scoped_session.get_persona(persona.id)
        assert result.id == persona.id
        assert result.user_id == user.id

    @pytest.mark.asyncio
    async def test_raises_not_found_for_other_users_persona(
        self, scoped_session: TenantScopedSession, other_user_persona
    ) -> None:
        """Raises NotFoundError when persona belongs to another user."""
        _other_user, other_persona = other_user_persona

        with pytest.raises(NotFoundError):
            await scoped_session.get_persona(other_persona.id)

    @pytest.mark.asyncio
    async def test_raises_not_found_for_nonexistent_persona(
        self, scoped_session: TenantScopedSession
    ) -> None:
        """Raises NotFoundError for non-existent persona ID."""
        with pytest.raises(NotFoundError):
            await scoped_session.get_persona(uuid.uuid4())


# =============================================================================
# list_personas
# =============================================================================


class TestListPersonas:
    """TenantScopedSession.list_personas — scoped listing."""

    @pytest.mark.asyncio
    async def test_returns_only_owned_personas(
        self, scoped_session: TenantScopedSession, user_and_persona, other_user_persona
    ) -> None:
        """Returns only personas belonging to the session user."""
        _user, own_persona = user_and_persona
        _other_user, other_persona = other_user_persona

        personas = await scoped_session.list_personas()

        persona_ids = [p.id for p in personas]
        assert own_persona.id in persona_ids
        assert other_persona.id not in persona_ids

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_personas(
        self, db_session: AsyncSession
    ) -> None:
        """Returns empty list when user has no personas."""
        from app.models import User

        lonely_user = User(id=uuid.uuid4(), email="lonely@example.com")
        db_session.add(lonely_user)
        await db_session.commit()

        scoped = TenantScopedSession(db_session, lonely_user.id)
        personas = await scoped.list_personas()
        assert personas == []


# =============================================================================
# verify_persona_ownership
# =============================================================================


class TestVerifyPersonaOwnership:
    """TenantScopedSession.verify_persona_ownership — bool check."""

    @pytest.mark.asyncio
    async def test_returns_true_for_owned_persona(
        self, scoped_session: TenantScopedSession, user_and_persona
    ) -> None:
        """Returns True when persona belongs to user."""
        _user, persona = user_and_persona
        assert await scoped_session.verify_persona_ownership(persona.id) is True

    @pytest.mark.asyncio
    async def test_returns_false_for_other_users_persona(
        self, scoped_session: TenantScopedSession, other_user_persona
    ) -> None:
        """Returns False when persona belongs to another user."""
        _other_user, other_persona = other_user_persona
        assert await scoped_session.verify_persona_ownership(other_persona.id) is False

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent_persona(
        self, scoped_session: TenantScopedSession
    ) -> None:
        """Returns False for non-existent persona ID."""
        assert await scoped_session.verify_persona_ownership(uuid.uuid4()) is False


# =============================================================================
# user_id property
# =============================================================================


class TestUserIdProperty:
    """TenantScopedSession.user_id — read-only property."""

    def test_user_id_returns_configured_value(self) -> None:
        """user_id property returns the UUID passed at construction."""
        mock_db = AsyncMock(spec=AsyncSession)
        uid = uuid.uuid4()
        scoped = TenantScopedSession(mock_db, uid)
        assert scoped.user_id == uid

    def test_user_id_is_read_only(self) -> None:
        """user_id property cannot be reassigned."""
        mock_db = AsyncMock(spec=AsyncSession)
        scoped = TenantScopedSession(mock_db, uuid.uuid4())
        with pytest.raises(AttributeError):
            scoped.user_id = uuid.uuid4()  # type: ignore[misc]
