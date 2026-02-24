"""Tests for password auth endpoints.

REQ-013 §7.5: POST /auth/verify-password, POST /auth/register,
POST /auth/change-password.

These tests require PostgreSQL (integration tests). Skipped automatically
if the database is not available.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import bcrypt
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.user import User
from tests.conftest import TEST_AUTH_SECRET, TEST_USER_ID, create_test_jwt

_TEST_PASSWORD = "ValidP@ss1"  # nosec B105  # gitleaks:allow
_BCRYPT_ROUNDS = 4  # Low cost factor for fast tests


# ===================================================================
# Fixtures
# ===================================================================


@pytest_asyncio.fixture
async def user_with_password(db_session: AsyncSession) -> User:
    """Create a test user with bcrypt password hash."""
    password_hash = bcrypt.hashpw(
        _TEST_PASSWORD.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    ).decode()
    user = User(
        id=TEST_USER_ID,
        email="test@example.com",
        password_hash=password_hash,
        email_verified=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def password_client(
    db_engine,
) -> AsyncGenerator[AsyncClient, None]:
    """Unauthenticated client for verify-password and register tests.

    Auth is enabled but no JWT cookie is provided.
    """
    from app.core.database import get_db
    from app.main import app

    test_session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    original_auth_enabled = settings.auth_enabled
    original_auth_secret = settings.auth_secret
    settings.auth_enabled = True
    settings.auth_secret = SecretStr(TEST_AUTH_SECRET)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_password_client(
    db_engine,
    user_with_password,  # noqa: ARG001 - ensures user exists in DB
) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated client with JWT cookie for change-password tests."""
    from app.core.database import get_db
    from app.main import app

    test_session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    original_auth_enabled = settings.auth_enabled
    original_auth_secret = settings.auth_secret
    settings.auth_enabled = True
    settings.auth_secret = SecretStr(TEST_AUTH_SECRET)

    test_jwt = create_test_jwt(TEST_USER_ID)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={settings.auth_cookie_name: test_jwt},
    ) as ac:
        yield ac

    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    app.dependency_overrides.clear()


# ===================================================================
# POST /api/v1/auth/verify-password
# ===================================================================


class TestVerifyPassword:
    """Tests for POST /api/v1/auth/verify-password."""

    async def test_valid_credentials_returns_user_info(
        self,
        password_client,
        user_with_password,  # noqa: ARG002 - fixture ensures user exists
    ):
        """Valid email + password returns 200 with user data."""
        response = await password_client.post(
            "/api/v1/auth/verify-password",
            json={"email": "test@example.com", "password": _TEST_PASSWORD},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == str(TEST_USER_ID)
        assert data["email"] == "test@example.com"

    async def test_valid_credentials_sets_jwt_cookie(
        self,
        password_client,
        user_with_password,  # noqa: ARG002 - fixture ensures user exists
    ):
        """Successful login sets httpOnly JWT cookie."""
        response = await password_client.post(
            "/api/v1/auth/verify-password",
            json={"email": "test@example.com", "password": _TEST_PASSWORD},
        )
        assert response.status_code == 200
        set_cookie = response.headers.get("set-cookie", "")
        assert "zentropy.session-token" in set_cookie
        assert "httponly" in set_cookie.lower()

    async def test_wrong_password_returns_401(
        self,
        password_client,
        user_with_password,  # noqa: ARG002 - fixture ensures user exists
    ):
        """Wrong password returns 401."""
        response = await password_client.post(
            "/api/v1/auth/verify-password",
            json={"email": "test@example.com", "password": "WrongP@ss1"},
        )
        assert response.status_code == 401

    async def test_nonexistent_email_returns_401(self, password_client):
        """Non-existent email returns 401 (not 404, prevents enumeration)."""
        response = await password_client.post(
            "/api/v1/auth/verify-password",
            json={"email": "nobody@example.com", "password": "AnyP@ss1"},
        )
        assert response.status_code == 401

    async def test_oauth_user_without_password_returns_401(
        self, password_client, db_session
    ):
        """OAuth-only user (no password_hash) returns 401."""
        user = User(id=uuid.uuid4(), email="oauth@example.com", password_hash=None)
        db_session.add(user)
        await db_session.commit()

        response = await password_client.post(
            "/api/v1/auth/verify-password",
            json={"email": "oauth@example.com", "password": "AnyP@ss1"},
        )
        assert response.status_code == 401

    async def test_generic_error_message_prevents_enumeration(self, password_client):
        """Error message is generic regardless of failure reason."""
        response = await password_client.post(
            "/api/v1/auth/verify-password",
            json={"email": "nobody@example.com", "password": "AnyP@ss1"},
        )
        error_msg = response.json()["error"]["message"].lower()
        assert "invalid email or password" in error_msg

    async def test_missing_email_returns_400(self, password_client):
        """Missing email field returns validation error."""
        response = await password_client.post(
            "/api/v1/auth/verify-password",
            json={"password": "AnyP@ss1"},
        )
        assert response.status_code == 400

    async def test_missing_password_returns_400(self, password_client):
        """Missing password field returns validation error."""
        response = await password_client.post(
            "/api/v1/auth/verify-password",
            json={"email": "test@example.com"},
        )
        assert response.status_code == 400

    async def test_extra_fields_rejected(self, password_client):
        """Extra fields in request body are rejected (extra='forbid')."""
        response = await password_client.post(
            "/api/v1/auth/verify-password",
            json={
                "email": "test@example.com",
                "password": "AnyP@ss1",
                "extra_field": "should be rejected",
            },
        )
        assert response.status_code == 400


# ===================================================================
# POST /api/v1/auth/register
# ===================================================================


class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    @patch(
        "app.api.v1.auth.check_password_breached",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_success_creates_user_and_returns_201(
        self, _mock_hibp, password_client
    ):
        """Valid registration creates user and returns 201."""
        response = await password_client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "NewP@ss1!"},
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["email"] == "new@example.com"
        assert "id" in data

    @patch(
        "app.api.v1.auth.check_password_breached",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_duplicate_email_returns_409(
        self,
        _mock_hibp,
        password_client,
        user_with_password,  # noqa: ARG002 - fixture ensures user exists
    ):
        """Registering with existing email returns 409."""
        response = await password_client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "NewP@ss1!"},
        )
        assert response.status_code == 409

    @patch(
        "app.api.v1.auth.check_password_breached",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_weak_password_returns_400(self, _mock_hibp, password_client):
        """Weak password returns 400."""
        response = await password_client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "short"},
        )
        assert response.status_code == 400

    @patch(
        "app.api.v1.auth.check_password_breached",
        new_callable=AsyncMock,
        return_value=True,
    )
    async def test_breached_password_returns_422(self, _mock_hibp, password_client):
        """Password in HIBP breach database returns 422."""
        response = await password_client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "ValidP@ss1"},
        )
        assert response.status_code == 422
        assert "breach" in response.json()["error"]["message"].lower()

    @patch(
        "app.api.v1.auth.check_password_breached",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_password_stored_as_bcrypt_hash(
        self, _mock_hibp, password_client, db_session
    ):
        """Stored password_hash is a valid bcrypt hash."""
        response = await password_client.post(
            "/api/v1/auth/register",
            json={"email": "hash@example.com", "password": "NewP@ss1!"},
        )
        assert response.status_code == 201

        result = await db_session.execute(
            select(User.password_hash).where(User.email == "hash@example.com")
        )
        stored_hash = result.scalar_one_or_none()
        assert stored_hash is not None
        assert stored_hash.startswith("$2b$")

    async def test_missing_email_returns_400(self, password_client):
        """Missing email field returns validation error."""
        response = await password_client.post(
            "/api/v1/auth/register",
            json={"password": "ValidP@ss1"},
        )
        assert response.status_code == 400

    async def test_invalid_email_format_returns_400(self, password_client):
        """Invalid email format returns validation error."""
        response = await password_client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "ValidP@ss1!"},
        )
        assert response.status_code == 400

    @patch(
        "app.api.v1.auth.check_password_breached",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_email_normalized_to_lowercase(self, _mock_hibp, password_client):
        """Email is stored lowercase regardless of input case."""
        response = await password_client.post(
            "/api/v1/auth/register",
            json={"email": "UPPER@Example.COM", "password": "NewP@ss1!"},
        )
        assert response.status_code == 201
        assert response.json()["data"]["email"] == "upper@example.com"


# ===================================================================
# POST /api/v1/auth/change-password
# ===================================================================


class TestChangePassword:
    """Tests for POST /api/v1/auth/change-password."""

    @patch(
        "app.api.v1.auth.check_password_breached",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_success_updates_password_hash(
        self, _mock_hibp, auth_password_client, db_session
    ):
        """Valid change returns 200 and updates stored hash."""
        response = await auth_password_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": _TEST_PASSWORD,
                "new_password": "NewStr0ng!Pass",
            },
        )
        assert response.status_code == 200

        result = await db_session.execute(
            select(User.password_hash).where(User.id == TEST_USER_ID)
        )
        new_hash = result.scalar_one()
        assert bcrypt.checkpw(b"NewStr0ng!Pass", new_hash.encode())

    @patch(
        "app.api.v1.auth.check_password_breached",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_invalidates_sessions_after_change(
        self, _mock_hibp, auth_password_client, db_session
    ):
        """Password change sets token_invalidated_before for session revocation."""
        before = datetime.now(UTC).replace(microsecond=0)
        response = await auth_password_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": _TEST_PASSWORD,
                "new_password": "NewStr0ng!Pass",
            },
        )
        assert response.status_code == 200

        result = await db_session.execute(
            select(User.token_invalidated_before).where(User.id == TEST_USER_ID)
        )
        invalidated = result.scalar_one()
        assert invalidated is not None
        assert invalidated >= before
        # Microseconds truncated for JWT iat compatibility
        assert invalidated.microsecond == 0

    @patch(
        "app.api.v1.auth.check_password_breached",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_reissues_jwt_cookie_after_change(
        self, _mock_hibp, auth_password_client
    ):
        """Password change re-issues JWT cookie to keep current session valid."""
        response = await auth_password_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": _TEST_PASSWORD,
                "new_password": "NewStr0ng!Pass",
            },
        )
        assert response.status_code == 200
        set_cookie = response.headers.get("set-cookie", "")
        assert "zentropy.session-token" in set_cookie
        assert "httponly" in set_cookie.lower()

    async def test_wrong_current_password_returns_401(self, auth_password_client):
        """Wrong current password returns 401."""
        response = await auth_password_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "WrongP@ss1",
                "new_password": "NewStr0ng!Pass",
            },
        )
        assert response.status_code == 401

    async def test_missing_current_password_when_set_returns_400(
        self, auth_password_client
    ):
        """User with password must provide current_password."""
        response = await auth_password_client.post(
            "/api/v1/auth/change-password",
            json={"new_password": "NewStr0ng!Pass"},
        )
        assert response.status_code == 400

    @patch(
        "app.api.v1.auth.check_password_breached",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_oauth_user_sets_password_without_current(
        self, _mock_hibp, auth_password_client, db_session
    ):
        """OAuth-only user (no password_hash) can set password."""
        # Remove password from existing user to simulate OAuth-only
        await db_session.execute(
            sql_update(User).where(User.id == TEST_USER_ID).values(password_hash=None)
        )
        await db_session.commit()

        response = await auth_password_client.post(
            "/api/v1/auth/change-password",
            json={"new_password": "NewStr0ng!Pass"},
        )
        assert response.status_code == 200

    @patch(
        "app.api.v1.auth.check_password_breached",
        new_callable=AsyncMock,
        return_value=False,
    )
    async def test_weak_new_password_returns_400(
        self, _mock_hibp, auth_password_client
    ):
        """Weak new password returns 400."""
        response = await auth_password_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": _TEST_PASSWORD,
                "new_password": "weak",
            },
        )
        assert response.status_code == 400

    async def test_unauthenticated_returns_401(self, password_client):
        """Request without JWT returns 401."""
        response = await password_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": _TEST_PASSWORD,
                "new_password": "NewStr0ng!Pass",
            },
        )
        assert response.status_code == 401

    @patch(
        "app.api.v1.auth.check_password_breached",
        new_callable=AsyncMock,
        return_value=True,
    )
    async def test_breached_new_password_returns_422(
        self, _mock_hibp, auth_password_client
    ):
        """Breached new password returns 422."""
        response = await auth_password_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": _TEST_PASSWORD,
                "new_password": "ValidP@ss1",
            },
        )
        assert response.status_code == 422
        assert "breach" in response.json()["error"]["message"].lower()
