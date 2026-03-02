"""Tests for admin authentication infrastructure.

REQ-022 §5.1–§5.5: ADMIN_EMAILS config, JWT `adm` claim, `require_admin`
dependency, ADMIN_EMAILS bootstrap on login, and admin-specific error classes.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import bcrypt
import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from httpx import Response as HttpxResponse
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.auth import create_jwt
from app.core.config import settings
from app.core.errors import (
    AdminRequiredError,
    NoPricingConfigError,
    UnregisteredModelError,
)
from app.models.user import User
from tests.conftest import TEST_AUTH_SECRET, TEST_USER_ID

_TEST_PASSWORD = "ValidP@ss1"  # nosec B105  # gitleaks:allow
_BCRYPT_ROUNDS = 4  # Low cost factor for fast tests
_ADMIN_EMAIL = "admin@example.com"
_NON_ADMIN_EMAIL = "user@example.com"
_VERIFY_URL = "/api/v1/auth/verify-password"

# Pre-computed bcrypt hash for _TEST_PASSWORD (avoids repeating bcrypt.hashpw)
_TEST_PASSWORD_HASH = bcrypt.hashpw(
    _TEST_PASSWORD.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
).decode()


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _decode_test_jwt(token: str) -> dict:
    """Decode a JWT using test credentials."""
    return jwt.decode(
        token,
        TEST_AUTH_SECRET,
        algorithms=["HS256"],
        audience="zentropy-scout",
        issuer="zentropy-scout",
    )


def _extract_jwt_payload(response: HttpxResponse) -> dict:
    """Extract and decode JWT from response Set-Cookie header."""
    set_cookie = response.headers.get("set-cookie", "")
    token = set_cookie.split("zentropy.session-token=")[1].split(";")[0]
    return _decode_test_jwt(token)


# ---------------------------------------------------------------------------
# JWT `adm` claim tests (§5.2)
# ---------------------------------------------------------------------------


class TestJwtAdminClaim:
    """JWT includes `adm` claim when is_admin=True, omits when False."""

    def test_admin_jwt_includes_adm_claim(self) -> None:
        """Admin user gets adm=True in JWT payload."""
        token = create_jwt(
            user_id=str(TEST_USER_ID),
            secret=TEST_AUTH_SECRET,
            is_admin=True,
        )
        payload = _decode_test_jwt(token)
        assert payload["adm"] is True

    def test_non_admin_jwt_omits_adm_claim(self) -> None:
        """Non-admin user JWT does not contain adm claim at all."""
        token = create_jwt(
            user_id=str(TEST_USER_ID),
            secret=TEST_AUTH_SECRET,
            is_admin=False,
        )
        payload = _decode_test_jwt(token)
        assert "adm" not in payload

    def test_default_is_admin_false_omits_adm(self) -> None:
        """Default create_jwt (no is_admin arg) omits adm claim."""
        token = create_jwt(
            user_id=str(TEST_USER_ID),
            secret=TEST_AUTH_SECRET,
        )
        payload = _decode_test_jwt(token)
        assert "adm" not in payload

    def test_admin_jwt_still_has_standard_claims(self) -> None:
        """Admin JWT preserves all standard claims (sub, aud, iss, exp, iat)."""
        token = create_jwt(
            user_id=str(TEST_USER_ID),
            secret=TEST_AUTH_SECRET,
            is_admin=True,
        )
        payload = _decode_test_jwt(token)
        assert payload["sub"] == str(TEST_USER_ID)
        assert payload["aud"] == "zentropy-scout"
        assert "exp" in payload
        assert "iat" in payload


# ---------------------------------------------------------------------------
# Error class tests (§5.3, §14)
# ---------------------------------------------------------------------------


class TestAdminErrorClasses:
    """Admin-specific error classes have correct codes and status codes."""

    def test_admin_required_error_is_403(self) -> None:
        """AdminRequiredError returns 403 with ADMIN_REQUIRED code."""
        err = AdminRequiredError()
        assert err.status_code == 403
        assert err.code == "ADMIN_REQUIRED"
        assert "admin" in err.message.lower()

    def test_unregistered_model_error_is_503(self) -> None:
        """UnregisteredModelError returns 503 with provider and model info."""
        err = UnregisteredModelError(provider="claude", model="claude-3-5-haiku")
        assert err.status_code == 503
        assert err.code == "UNREGISTERED_MODEL"
        assert "claude" in err.message
        assert "claude-3-5-haiku" in err.message

    def test_no_pricing_config_error_is_503(self) -> None:
        """NoPricingConfigError returns 503 with provider and model info."""
        err = NoPricingConfigError(provider="openai", model="gpt-4o")
        assert err.status_code == 503
        assert err.code == "NO_PRICING_CONFIG"
        assert "openai" in err.message
        assert "gpt-4o" in err.message


# ---------------------------------------------------------------------------
# require_admin dependency tests (§5.3) — DB integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRequireAdmin:
    """require_admin dependency gates access for non-admin users."""

    async def test_admin_user_passes(self, db_session: AsyncSession) -> None:
        """Admin user ID is returned when is_admin=True."""
        from app.api.deps import require_admin

        user = User(id=TEST_USER_ID, email=_ADMIN_EMAIL, is_admin=True)
        db_session.add(user)
        await db_session.flush()

        result = await require_admin(user_id=TEST_USER_ID, db=db_session)
        assert result == TEST_USER_ID

    async def test_non_admin_raises_403(self, db_session: AsyncSession) -> None:
        """Non-admin user raises AdminRequiredError (403)."""
        from app.api.deps import require_admin

        user = User(id=TEST_USER_ID, email=_NON_ADMIN_EMAIL, is_admin=False)
        db_session.add(user)
        await db_session.flush()

        with pytest.raises(AdminRequiredError):
            await require_admin(user_id=TEST_USER_ID, db=db_session)

    async def test_nonexistent_user_raises_403(self, db_session: AsyncSession) -> None:
        """User not found in DB raises AdminRequiredError (403)."""
        from app.api.deps import require_admin

        fake_id = uuid.uuid4()
        with pytest.raises(AdminRequiredError):
            await require_admin(user_id=fake_id, db=db_session)


# ---------------------------------------------------------------------------
# ADMIN_EMAILS bootstrap on login (§5.1) — HTTP integration
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def admin_bootstrap_client(
    db_engine,
) -> AsyncGenerator[AsyncClient, None]:
    """Unauthenticated client with ADMIN_EMAILS configured for bootstrap tests."""
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
    original_admin_emails = settings.admin_emails
    settings.auth_enabled = True
    settings.auth_secret = SecretStr(TEST_AUTH_SECRET)
    settings.admin_emails = _ADMIN_EMAIL

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    settings.admin_emails = original_admin_emails
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def admin_user_in_db(db_session: AsyncSession) -> User:
    """Create a verified user whose email matches ADMIN_EMAILS."""
    user = User(
        id=TEST_USER_ID,
        email=_ADMIN_EMAIL,
        password_hash=_TEST_PASSWORD_HASH,
        email_verified=datetime.now(UTC),
        is_admin=False,  # Not yet admin — bootstrap should promote
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def non_admin_user_in_db(db_session: AsyncSession) -> User:
    """Create a verified user whose email does NOT match ADMIN_EMAILS."""
    user = User(
        id=TEST_USER_ID,
        email=_NON_ADMIN_EMAIL,
        password_hash=_TEST_PASSWORD_HASH,
        email_verified=datetime.now(UTC),
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
class TestAdminEmailsBootstrap:
    """ADMIN_EMAILS env var auto-promotes matching users on login."""

    @pytest.mark.usefixtures("admin_user_in_db")
    async def test_matching_email_promotes_to_admin(
        self,
        admin_bootstrap_client: AsyncClient,
    ) -> None:
        """User with email in ADMIN_EMAILS gets is_admin=True on login."""
        response = await admin_bootstrap_client.post(
            _VERIFY_URL,
            json={"email": _ADMIN_EMAIL, "password": _TEST_PASSWORD},
        )
        assert response.status_code == 200

        payload = _extract_jwt_payload(response)
        assert payload.get("adm") is True

    async def test_case_insensitive_email_match(
        self,
        admin_bootstrap_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Email matching is case-insensitive (uppercase ADMIN_EMAILS matches lowercase user)."""
        user = User(
            email=_ADMIN_EMAIL,
            password_hash=_TEST_PASSWORD_HASH,
            email_verified=datetime.now(UTC),
        )
        db_session.add(user)
        await db_session.commit()

        # Set ADMIN_EMAILS with uppercase
        original = settings.admin_emails
        settings.admin_emails = _ADMIN_EMAIL.upper()

        response = await admin_bootstrap_client.post(
            _VERIFY_URL,
            json={"email": _ADMIN_EMAIL, "password": _TEST_PASSWORD},
        )
        settings.admin_emails = original
        assert response.status_code == 200

        payload = _extract_jwt_payload(response)
        assert payload.get("adm") is True

    @pytest.mark.usefixtures("non_admin_user_in_db")
    async def test_non_matching_email_not_promoted(
        self,
        admin_bootstrap_client: AsyncClient,
    ) -> None:
        """User whose email is NOT in ADMIN_EMAILS stays non-admin."""
        response = await admin_bootstrap_client.post(
            _VERIFY_URL,
            json={"email": _NON_ADMIN_EMAIL, "password": _TEST_PASSWORD},
        )
        assert response.status_code == 200

        payload = _extract_jwt_payload(response)
        assert "adm" not in payload

    async def test_already_admin_user_still_gets_adm_claim(
        self,
        admin_bootstrap_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """User already is_admin=True gets adm claim (no redundant update)."""
        user = User(
            email=_ADMIN_EMAIL,
            password_hash=_TEST_PASSWORD_HASH,
            email_verified=datetime.now(UTC),
            is_admin=True,  # Already admin
        )
        db_session.add(user)
        await db_session.commit()

        response = await admin_bootstrap_client.post(
            _VERIFY_URL,
            json={"email": _ADMIN_EMAIL, "password": _TEST_PASSWORD},
        )
        assert response.status_code == 200

        payload = _extract_jwt_payload(response)
        assert payload.get("adm") is True

    async def test_empty_admin_emails_promotes_nobody(
        self,
        admin_bootstrap_client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Empty ADMIN_EMAILS string does not promote any user."""
        user = User(
            email=_ADMIN_EMAIL,
            password_hash=_TEST_PASSWORD_HASH,
            email_verified=datetime.now(UTC),
        )
        db_session.add(user)
        await db_session.commit()

        original = settings.admin_emails
        settings.admin_emails = ""

        response = await admin_bootstrap_client.post(
            _VERIFY_URL,
            json={"email": _ADMIN_EMAIL, "password": _TEST_PASSWORD},
        )
        settings.admin_emails = original
        assert response.status_code == 200

        payload = _extract_jwt_payload(response)
        assert "adm" not in payload


# ---------------------------------------------------------------------------
# Config: admin_emails setting (§13.1)
# ---------------------------------------------------------------------------


class TestAdminEmailsConfig:
    """Settings.admin_emails field exists and defaults to empty string."""

    def test_admin_emails_defaults_to_empty_string(self) -> None:
        """admin_emails has an empty string default."""
        from app.core.config import Settings

        s = Settings(
            database_password="test_password",  # nosec B106  # gitleaks:allow
        )
        assert s.admin_emails == ""

    def test_admin_emails_accepts_comma_separated(self) -> None:
        """admin_emails can be set to comma-separated emails."""
        from app.core.config import Settings

        s = Settings(
            database_password="test_password",  # nosec B106  # gitleaks:allow
            admin_emails="a@b.com, c@d.com",
        )
        assert s.admin_emails == "a@b.com, c@d.com"
