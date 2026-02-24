"""Tests for OAuth endpoints — initiation and callback.

REQ-013 §4.1, §4.2, §7.5: Tests for OAuth initiation redirect,
callback token exchange, account creation/linking, and JWT issuance.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.oauth import create_oauth_state_cookie
from tests.conftest import TEST_AUTH_SECRET

# ===================================================================
# Constants
# ===================================================================

_GOOGLE_INITIATE_URL = "/api/v1/auth/providers/google"
_LINKEDIN_INITIATE_URL = "/api/v1/auth/providers/linkedin"
_GOOGLE_CALLBACK_URL = "/api/v1/auth/callback/google"
_OAUTH_STATE_COOKIE = "oauth_state"
_PATCH_EXCHANGE = "app.api.v1.auth_oauth.exchange_code_for_tokens"
_PATCH_USERINFO = "app.api.v1.auth_oauth.fetch_userinfo"

# Mock user info returned by provider
_MOCK_GOOGLE_USERINFO = {
    "sub": "google-sub-test-123",
    "email": "oauthuser@example.com",
    "email_verified": True,
    "name": "OAuth User",
    "picture": "https://example.com/photo.jpg",
}


# ===================================================================
# Fixtures
# ===================================================================


@pytest_asyncio.fixture
async def oauth_client(
    db_engine,
) -> AsyncGenerator[AsyncClient, None]:
    """Unauthenticated client for OAuth endpoints (no JWT cookie needed)."""
    from app.core.database import get_db
    from app.main import app

    test_session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    original_auth_enabled = settings.auth_enabled
    original_auth_secret = settings.auth_secret
    original_google_id = settings.google_client_id
    original_google_secret = settings.google_client_secret
    original_linkedin_id = settings.linkedin_client_id
    original_linkedin_secret = settings.linkedin_client_secret

    settings.auth_enabled = True
    settings.auth_secret = SecretStr(TEST_AUTH_SECRET)
    settings.google_client_id = "test-google-client-id"
    settings.google_client_secret = SecretStr("test-google-client-secret")
    settings.linkedin_client_id = "test-linkedin-client-id"
    settings.linkedin_client_secret = SecretStr("test-linkedin-client-secret")

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=False,
    ) as ac:
        yield ac

    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret
    settings.google_client_id = original_google_id
    settings.google_client_secret = original_google_secret
    settings.linkedin_client_id = original_linkedin_id
    settings.linkedin_client_secret = original_linkedin_secret
    app.dependency_overrides.clear()


# ===================================================================
# GET /auth/providers/{provider} — OAuth Initiation
# ===================================================================


class TestOAuthInitiation:
    """Tests for GET /auth/providers/{provider}."""

    async def test_google_redirects_to_google_auth_url(self, oauth_client):
        """Google initiation redirects to Google's authorization URL."""
        response = await oauth_client.get(_GOOGLE_INITIATE_URL)
        assert response.status_code == 307
        location = response.headers["location"]
        assert "accounts.google.com" in location
        assert "client_id=test-google-client-id" in location
        assert "code_challenge" in location
        assert "code_challenge_method=S256" in location
        assert "response_type=code" in location
        assert "scope=" in location

    async def test_linkedin_redirects_to_linkedin_auth_url(self, oauth_client):
        """LinkedIn initiation redirects to LinkedIn's authorization URL."""
        response = await oauth_client.get(_LINKEDIN_INITIATE_URL)
        assert response.status_code == 307
        location = response.headers["location"]
        assert "linkedin.com" in location
        assert "client_id=test-linkedin-client-id" in location

    async def test_linkedin_does_not_include_pkce_params(self, oauth_client):
        """LinkedIn does not support PKCE — no code_challenge in redirect."""
        response = await oauth_client.get(_LINKEDIN_INITIATE_URL)
        location = response.headers["location"]
        assert "code_challenge" not in location
        assert "code_challenge_method" not in location

    async def test_sets_state_cookie(self, oauth_client):
        """Initiation should set an oauth_state cookie."""
        response = await oauth_client.get(_GOOGLE_INITIATE_URL)
        cookies = response.cookies
        assert _OAUTH_STATE_COOKIE in cookies or any(
            _OAUTH_STATE_COOKIE in c for c in response.headers.get_list("set-cookie")
        )

    async def test_unknown_provider_returns_400(self, oauth_client):
        """Unsupported provider returns 400."""
        response = await oauth_client.get("/api/v1/auth/providers/facebook")
        assert response.status_code == 400

    async def test_redirect_url_includes_state_parameter(self, oauth_client):
        """Redirect URL includes state parameter for CSRF protection."""
        response = await oauth_client.get(_GOOGLE_INITIATE_URL)
        location = response.headers["location"]
        assert "state=" in location


# ===================================================================
# GET /auth/callback/{provider} — OAuth Callback
# ===================================================================


class TestOAuthCallback:
    """Tests for GET /auth/callback/{provider}."""

    async def test_creates_new_user_and_redirects(self, oauth_client):
        """Successful callback creates user, sets JWT cookie, redirects."""
        state_cookie = create_oauth_state_cookie(
            state="test-state",
            code_verifier="test-verifier",
            secret=TEST_AUTH_SECRET,
        )

        with (
            patch(
                _PATCH_EXCHANGE,
                new_callable=AsyncMock,
                return_value={"access_token": "mock-token", "id_token": "mock-id"},
            ),
            patch(
                _PATCH_USERINFO,
                new_callable=AsyncMock,
                return_value=_MOCK_GOOGLE_USERINFO,
            ),
        ):
            response = await oauth_client.get(
                _GOOGLE_CALLBACK_URL,
                params={"code": "auth-code-123", "state": "test-state"},
                cookies={_OAUTH_STATE_COOKIE: state_cookie},
            )

        assert response.status_code == 307
        # Should redirect to frontend
        location = response.headers["location"]
        assert location.startswith("http://localhost:3000")
        # Should set JWT cookie
        set_cookie = response.headers.get("set-cookie", "")
        assert settings.auth_cookie_name in set_cookie

    async def test_rejects_missing_state_cookie(self, oauth_client):
        """Missing state cookie returns 400."""
        response = await oauth_client.get(
            _GOOGLE_CALLBACK_URL,
            params={"code": "auth-code", "state": "some-state"},
        )
        assert response.status_code == 400

    async def test_rejects_mismatched_state(self, oauth_client):
        """Mismatched state (CSRF) returns 400."""
        state_cookie = create_oauth_state_cookie(
            state="real-state",
            code_verifier="v",
            secret=TEST_AUTH_SECRET,
        )
        response = await oauth_client.get(
            _GOOGLE_CALLBACK_URL,
            params={"code": "auth-code", "state": "forged-state"},
            cookies={_OAUTH_STATE_COOKIE: state_cookie},
        )
        assert response.status_code == 400

    async def test_rejects_missing_code_parameter(self, oauth_client):
        """Missing authorization code returns 400."""
        state_cookie = create_oauth_state_cookie(
            state="valid-state",
            code_verifier="v",
            secret=TEST_AUTH_SECRET,
        )
        response = await oauth_client.get(
            _GOOGLE_CALLBACK_URL,
            params={"state": "valid-state"},
            cookies={_OAUTH_STATE_COOKIE: state_cookie},
        )
        assert response.status_code == 400

    async def test_links_existing_user_on_callback(self, oauth_client, db_session):
        """Callback links to existing verified user with matching email."""
        from datetime import UTC, datetime

        from app.repositories.user_repository import UserRepository

        # Create existing verified user
        await UserRepository.create(
            db_session,
            email="oauthuser@example.com",
            email_verified=datetime.now(UTC),
        )
        await db_session.commit()

        state_cookie = create_oauth_state_cookie(
            state="link-state",
            code_verifier="link-verifier",
            secret=TEST_AUTH_SECRET,
        )

        with (
            patch(
                _PATCH_EXCHANGE,
                new_callable=AsyncMock,
                return_value={"access_token": "mock-token"},
            ),
            patch(
                _PATCH_USERINFO,
                new_callable=AsyncMock,
                return_value=_MOCK_GOOGLE_USERINFO,
            ),
        ):
            response = await oauth_client.get(
                _GOOGLE_CALLBACK_URL,
                params={"code": "auth-code", "state": "link-state"},
                cookies={_OAUTH_STATE_COOKIE: state_cookie},
            )

        assert response.status_code == 307
        # JWT cookie should be issued for the existing user
        set_cookie = response.headers.get("set-cookie", "")
        assert settings.auth_cookie_name in set_cookie

    async def test_unknown_provider_returns_400(self, oauth_client):
        """Unsupported provider in callback returns 400."""
        response = await oauth_client.get(
            "/api/v1/auth/callback/facebook",
            params={"code": "code", "state": "state"},
        )
        assert response.status_code == 400

    async def test_clears_state_cookie_after_callback(self, oauth_client):
        """State cookie should be cleared after successful callback."""
        state_cookie = create_oauth_state_cookie(
            state="clear-state",
            code_verifier="v",
            secret=TEST_AUTH_SECRET,
        )

        with (
            patch(
                _PATCH_EXCHANGE,
                new_callable=AsyncMock,
                return_value={"access_token": "t"},
            ),
            patch(
                _PATCH_USERINFO,
                new_callable=AsyncMock,
                return_value=_MOCK_GOOGLE_USERINFO,
            ),
        ):
            response = await oauth_client.get(
                _GOOGLE_CALLBACK_URL,
                params={"code": "code", "state": "clear-state"},
                cookies={_OAUTH_STATE_COOKIE: state_cookie},
            )

        # Check that oauth_state cookie is deleted (max-age=0 or similar)
        set_cookies = response.headers.get_list("set-cookie")
        oauth_cookie_cleared = any(
            _OAUTH_STATE_COOKIE in c
            and ("max-age=0" in c.lower() or "expires=" in c.lower())
            for c in set_cookies
        )
        assert oauth_cookie_cleared
