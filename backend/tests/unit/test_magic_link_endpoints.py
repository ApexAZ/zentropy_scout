"""Tests for magic link + session endpoints.

REQ-013 §4.4, §7.5: POST /auth/magic-link, GET /auth/verify-magic-link,
POST /auth/logout, GET /auth/me.

These tests require PostgreSQL (integration tests).
"""

import hashlib
import secrets
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.user import User
from app.models.verification_token import VerificationToken
from tests.conftest import TEST_AUTH_SECRET, TEST_USER_ID, create_test_jwt

_MAGIC_LINK_URL = "/api/v1/auth/magic-link"
_VERIFY_URL = "/api/v1/auth/verify-magic-link"
_LOGOUT_URL = "/api/v1/auth/logout"
_ME_URL = "/api/v1/auth/me"
_PATCH_SEND_EMAIL = "app.api.v1.auth_magic_link.send_magic_link_email"

_TEST_EMAIL = "magicuser@example.com"
_TOKEN_TTL_MINUTES = 10


# ===================================================================
# Fixtures
# ===================================================================


@pytest_asyncio.fixture
async def verified_user(db_session: AsyncSession) -> User:
    """Create a verified test user."""
    user = User(
        id=TEST_USER_ID,
        email=_TEST_EMAIL,
        email_verified=datetime.now(UTC),
        name="Magic User",
        image="https://example.com/avatar.jpg",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def minimal_user(db_session: AsyncSession) -> User:
    """Create a verified user without name or image (optional fields NULL)."""
    user = User(
        id=TEST_USER_ID,
        email=_TEST_EMAIL,
        email_verified=datetime.now(UTC),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def unverified_user(db_session: AsyncSession) -> User:
    """Create an unverified test user (email_verified=NULL)."""
    user = User(
        id=TEST_USER_ID,
        email=_TEST_EMAIL,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def magic_link_client(
    db_engine,
) -> AsyncGenerator[AsyncClient, None]:
    """Unauthenticated client for magic link endpoints."""
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
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=False,
    ) as ac:
        yield ac

    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_client(
    db_engine,
    verified_user,  # noqa: ARG001 - ensures user exists in DB
) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated client with JWT cookie for /me and logout tests."""
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

    token = create_test_jwt()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={settings.auth_cookie_name: token},
    ) as ac:
        yield ac

    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def minimal_auth_client(
    db_engine,
    minimal_user,  # noqa: ARG001 - ensures user exists in DB
) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated client for user without name/image."""
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

    token = create_test_jwt()
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={settings.auth_cookie_name: token},
    ) as ac:
        yield ac

    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    app.dependency_overrides.clear()


def _create_token_and_hash() -> tuple[str, str]:
    """Generate a plain token and its SHA-256 hash for test setup."""
    plain = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(plain.encode()).hexdigest()
    return plain, hashed


async def _insert_verification_token(
    db_session: AsyncSession,
    identifier: str,
    token_hash: str,
    *,
    expires: datetime | None = None,
) -> VerificationToken:
    """Insert a verification token directly for test setup."""
    if expires is None:
        expires = datetime.now(UTC) + timedelta(minutes=_TOKEN_TTL_MINUTES)
    vt = VerificationToken(
        identifier=identifier,
        token=token_hash,
        expires=expires,
    )
    db_session.add(vt)
    await db_session.commit()
    return vt


# ===================================================================
# POST /auth/magic-link
# ===================================================================


class TestMagicLinkRequest:
    """Tests for POST /auth/magic-link."""

    async def test_returns_success_for_existing_user(
        self,
        magic_link_client,
        verified_user,  # noqa: ARG002 - ensures user exists
    ):
        """Always returns success message even for existing users."""
        with patch(_PATCH_SEND_EMAIL, new_callable=AsyncMock) as mock_send:
            response = await magic_link_client.post(
                _MAGIC_LINK_URL, json={"email": _TEST_EMAIL}
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "sign-in link has been sent" in data["message"]
        mock_send.assert_awaited_once()

    async def test_returns_success_for_nonexistent_email(self, magic_link_client):
        """Returns success even when email doesn't exist (enumeration defense)."""
        with patch(_PATCH_SEND_EMAIL, new_callable=AsyncMock) as mock_send:
            response = await magic_link_client.post(
                _MAGIC_LINK_URL, json={"email": "nobody@example.com"}
            )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "sign-in link has been sent" in data["message"]
        # Should NOT send email for non-existent user
        mock_send.assert_not_awaited()

    async def test_stores_hashed_token_in_database(
        self,
        magic_link_client,
        verified_user,  # noqa: ARG002
        db_session,
    ):
        """Token stored in verification_tokens table as SHA-256 hash."""
        with patch(_PATCH_SEND_EMAIL, new_callable=AsyncMock):
            await magic_link_client.post(_MAGIC_LINK_URL, json={"email": _TEST_EMAIL})

        result = await db_session.execute(
            select(VerificationToken).where(VerificationToken.identifier == _TEST_EMAIL)
        )
        token_row = result.scalar_one_or_none()
        assert token_row is not None
        # Token should look like a hex SHA-256 hash (64 chars)
        assert len(token_row.token) == 64
        # Should have a future expiry
        assert token_row.expires > datetime.now(UTC)

    async def test_token_expires_in_10_minutes(
        self,
        magic_link_client,
        verified_user,  # noqa: ARG002
        db_session,
    ):
        """Token TTL is approximately 10 minutes."""
        with patch(_PATCH_SEND_EMAIL, new_callable=AsyncMock):
            await magic_link_client.post(_MAGIC_LINK_URL, json={"email": _TEST_EMAIL})

        result = await db_session.execute(
            select(VerificationToken).where(VerificationToken.identifier == _TEST_EMAIL)
        )
        token_row = result.scalar_one()
        # Expires within 10 minutes (+/- 5 seconds tolerance)
        expected_expiry = datetime.now(UTC) + timedelta(minutes=10)
        delta = abs((token_row.expires - expected_expiry).total_seconds())
        assert delta < 5

    async def test_sends_email_with_plain_token(
        self,
        magic_link_client,
        verified_user,  # noqa: ARG002 - ensures user exists
    ):
        """Email is sent with the plain (unhashed) token."""
        with patch(_PATCH_SEND_EMAIL, new_callable=AsyncMock) as mock_send:
            await magic_link_client.post(_MAGIC_LINK_URL, json={"email": _TEST_EMAIL})

        mock_send.assert_awaited_once()
        call_kwargs = mock_send.call_args.kwargs
        assert call_kwargs["to_email"] == _TEST_EMAIL
        # Plain token should be present (not the hash)
        plain_token = call_kwargs["token"]
        assert len(plain_token) > 0
        # It should NOT be a 64-char hex hash
        assert len(plain_token) != 64

    async def test_rejects_invalid_email_format(self, magic_link_client):
        """Invalid email format returns 400."""
        response = await magic_link_client.post(
            _MAGIC_LINK_URL, json={"email": "not-an-email"}
        )
        assert response.status_code == 400

    async def test_normalizes_email_to_lowercase(
        self,
        magic_link_client,
        verified_user,  # noqa: ARG002 - ensures user exists
    ):
        """Email is normalized to lowercase before lookup."""
        with patch(_PATCH_SEND_EMAIL, new_callable=AsyncMock) as mock_send:
            response = await magic_link_client.post(
                _MAGIC_LINK_URL, json={"email": "MagicUser@Example.COM"}
            )

        assert response.status_code == 200
        # Should find the user and send email
        mock_send.assert_awaited_once()


# ===================================================================
# GET /auth/verify-magic-link
# ===================================================================


class TestVerifyMagicLink:
    """Tests for GET /auth/verify-magic-link."""

    async def test_valid_token_sets_jwt_cookie_and_redirects(
        self,
        magic_link_client,
        verified_user,  # noqa: ARG002
        db_session,
    ):
        """Valid token issues JWT cookie and redirects to frontend."""
        plain_token, token_hash = _create_token_and_hash()
        await _insert_verification_token(db_session, _TEST_EMAIL, token_hash)

        response = await magic_link_client.get(
            _VERIFY_URL,
            params={"token": plain_token, "identifier": _TEST_EMAIL},
        )

        assert response.status_code == 307
        location = response.headers["location"]
        assert location.startswith(settings.frontend_url)
        # JWT cookie should be set
        set_cookie = response.headers.get("set-cookie", "")
        assert settings.auth_cookie_name in set_cookie

    async def test_deletes_token_after_use(
        self,
        magic_link_client,
        verified_user,  # noqa: ARG002
        db_session,
    ):
        """Token is single-use — deleted from DB after verification."""
        plain_token, token_hash = _create_token_and_hash()
        await _insert_verification_token(db_session, _TEST_EMAIL, token_hash)

        await magic_link_client.get(
            _VERIFY_URL,
            params={"token": plain_token, "identifier": _TEST_EMAIL},
        )

        result = await db_session.execute(
            select(VerificationToken).where(
                VerificationToken.identifier == _TEST_EMAIL,
                VerificationToken.token == token_hash,
            )
        )
        assert result.scalar_one_or_none() is None

    async def test_sets_email_verified_for_unverified_user(
        self, magic_link_client, unverified_user, db_session
    ):
        """Sets email_verified timestamp if not already set."""
        plain_token, token_hash = _create_token_and_hash()
        await _insert_verification_token(db_session, _TEST_EMAIL, token_hash)

        await magic_link_client.get(
            _VERIFY_URL,
            params={"token": plain_token, "identifier": _TEST_EMAIL},
        )

        await db_session.refresh(unverified_user)
        assert unverified_user.email_verified is not None

    async def test_does_not_overwrite_existing_email_verified(
        self, magic_link_client, verified_user, db_session
    ):
        """Does not overwrite email_verified if already set."""
        original_verified = verified_user.email_verified
        plain_token, token_hash = _create_token_and_hash()
        await _insert_verification_token(db_session, _TEST_EMAIL, token_hash)

        await magic_link_client.get(
            _VERIFY_URL,
            params={"token": plain_token, "identifier": _TEST_EMAIL},
        )

        await db_session.refresh(verified_user)
        assert verified_user.email_verified == original_verified

    async def test_invalid_token_returns_400(
        self,
        magic_link_client,
        verified_user,  # noqa: ARG002
        db_session,
    ):
        """Invalid (wrong) token returns 400."""
        _plain_token, token_hash = _create_token_and_hash()
        await _insert_verification_token(db_session, _TEST_EMAIL, token_hash)

        response = await magic_link_client.get(
            _VERIFY_URL,
            params={"token": "completely-wrong-token", "identifier": _TEST_EMAIL},
        )
        assert response.status_code == 400

    async def test_expired_token_returns_400(
        self,
        magic_link_client,
        verified_user,  # noqa: ARG002
        db_session,
    ):
        """Expired token returns 400."""
        plain_token, token_hash = _create_token_and_hash()
        expired = datetime.now(UTC) - timedelta(minutes=1)
        await _insert_verification_token(
            db_session, _TEST_EMAIL, token_hash, expires=expired
        )

        response = await magic_link_client.get(
            _VERIFY_URL,
            params={"token": plain_token, "identifier": _TEST_EMAIL},
        )
        assert response.status_code == 400

    async def test_reused_token_returns_400(
        self,
        magic_link_client,
        verified_user,  # noqa: ARG002
        db_session,
    ):
        """Token cannot be used twice (single-use)."""
        plain_token, token_hash = _create_token_and_hash()
        await _insert_verification_token(db_session, _TEST_EMAIL, token_hash)

        # First use — success
        response1 = await magic_link_client.get(
            _VERIFY_URL,
            params={"token": plain_token, "identifier": _TEST_EMAIL},
        )
        assert response1.status_code == 307

        # Second use — 400 (token deleted)
        response2 = await magic_link_client.get(
            _VERIFY_URL,
            params={"token": plain_token, "identifier": _TEST_EMAIL},
        )
        assert response2.status_code == 400

    async def test_mismatched_identifier_returns_400(
        self,
        magic_link_client,
        verified_user,  # noqa: ARG002
        db_session,
    ):
        """Token with wrong identifier (email) returns 400."""
        plain_token, token_hash = _create_token_and_hash()
        await _insert_verification_token(db_session, _TEST_EMAIL, token_hash)

        response = await magic_link_client.get(
            _VERIFY_URL,
            params={"token": plain_token, "identifier": "wrong@example.com"},
        )
        assert response.status_code == 400

    async def test_missing_token_param_returns_400(self, magic_link_client):
        """Missing token query parameter returns 400."""
        response = await magic_link_client.get(
            _VERIFY_URL,
            params={"identifier": _TEST_EMAIL},
        )
        assert response.status_code == 400

    async def test_missing_identifier_param_returns_400(self, magic_link_client):
        """Missing identifier query parameter returns 400."""
        response = await magic_link_client.get(
            _VERIFY_URL,
            params={"token": "some-token"},
        )
        assert response.status_code == 400

    async def test_creates_user_if_not_exists(self, magic_link_client, db_session):
        """Creates a new user if the email doesn't exist yet."""
        new_email = "newuser@example.com"
        plain_token, token_hash = _create_token_and_hash()
        await _insert_verification_token(db_session, new_email, token_hash)

        response = await magic_link_client.get(
            _VERIFY_URL,
            params={"token": plain_token, "identifier": new_email},
        )

        assert response.status_code == 307
        result = await db_session.execute(select(User).where(User.email == new_email))
        user = result.scalar_one()
        assert user.email_verified is not None


# ===================================================================
# POST /auth/logout
# ===================================================================


class TestLogout:
    """Tests for POST /auth/logout."""

    async def test_clears_auth_cookie(self, auth_client):
        """Logout clears the auth cookie."""
        response = await auth_client.post(_LOGOUT_URL)

        assert response.status_code == 200
        data = response.json()["data"]
        assert "signed out" in data["message"].lower()
        # Cookie should be cleared (max-age=0)
        set_cookies = response.headers.get_list("set-cookie")
        cookie_cleared = any(
            settings.auth_cookie_name in c and "max-age=0" in c.lower()
            for c in set_cookies
        )
        assert cookie_cleared

    async def test_returns_success_even_without_cookie(self, magic_link_client):
        """Logout returns success even if no cookie is present."""
        response = await magic_link_client.post(_LOGOUT_URL)
        assert response.status_code == 200


# ===================================================================
# GET /auth/me
# ===================================================================


class TestGetMe:
    """Tests for GET /auth/me."""

    async def test_returns_user_info_when_authenticated(self, auth_client):
        """Returns current user's id, email, name, and image."""
        response = await auth_client.get(_ME_URL)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == str(TEST_USER_ID)
        assert data["email"] == _TEST_EMAIL
        assert data["name"] == "Magic User"
        assert data["image"] == "https://example.com/avatar.jpg"

    async def test_returns_401_when_unauthenticated(self, magic_link_client):
        """Returns 401 when no valid JWT cookie is present."""
        response = await magic_link_client.get(_ME_URL)
        assert response.status_code == 401

    async def test_returns_null_for_missing_optional_fields(self, minimal_auth_client):
        """Returns null for name and image when not set."""
        response = await minimal_auth_client.get(_ME_URL)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] is None
        assert data["image"] is None
