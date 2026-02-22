"""Tests for rate limiting behavior.

Security: Tests for API abuse prevention via rate limiting.
REQ-013 §7.4: Rate limit key transitions from IP to per-user in hosted mode.
"""

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.core.rate_limiting import _rate_limit_key_func
from tests.conftest import TEST_AUTH_SECRET, TEST_USER_ID, create_test_jwt


class TestRateLimitExceededHandler:
    """Tests for rate limit exceeded response format."""

    @pytest.mark.asyncio
    async def test_rate_limit_returns_429_status(self):
        """Rate limit exceeded should return 429 status code."""
        from unittest.mock import MagicMock

        from starlette.requests import Request as StarletteRequest

        from app.core.rate_limiting import rate_limit_exceeded_handler

        # Create a mock request
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/job-postings/ingest",
        }
        request = StarletteRequest(scope)

        # Create a mock exception with the detail attribute
        exc = MagicMock()
        exc.detail = "10 per 1 minute"

        response = rate_limit_exceeded_handler(request, exc)

        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_returns_error_envelope(self):
        """Rate limit response should use standard error envelope."""
        import json
        from unittest.mock import MagicMock

        from starlette.requests import Request as StarletteRequest

        from app.core.rate_limiting import rate_limit_exceeded_handler

        scope = {"type": "http", "method": "POST", "path": "/test"}
        request = StarletteRequest(scope)

        # Create a mock exception with the detail attribute
        exc = MagicMock()
        exc.detail = "10 per 1 minute"

        response = rate_limit_exceeded_handler(request, exc)
        body = json.loads(response.body.decode())

        assert "error" in body
        assert body["error"]["code"] == "RATE_LIMITED"
        assert "Rate limit exceeded" in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_rate_limit_retry_after_fallback_on_invalid_detail(self):
        """Retry-After should fall back to 60 if parsing fails."""
        from unittest.mock import MagicMock

        from starlette.requests import Request as StarletteRequest

        from app.core.rate_limiting import rate_limit_exceeded_handler

        scope = {"type": "http", "method": "POST", "path": "/test"}
        request = StarletteRequest(scope)

        # Create a mock exception with unparseable detail
        exc = MagicMock()
        exc.detail = "unexpected format"

        response = rate_limit_exceeded_handler(request, exc)

        assert response.headers.get("Retry-After") == "60"

    @pytest.mark.asyncio
    async def test_rate_limit_retry_after_handles_none_detail(self):
        """Retry-After should fall back to 60 if detail is None."""
        from unittest.mock import MagicMock

        from starlette.requests import Request as StarletteRequest

        from app.core.rate_limiting import rate_limit_exceeded_handler

        scope = {"type": "http", "method": "POST", "path": "/test"}
        request = StarletteRequest(scope)

        # Create a mock exception with None detail
        exc = MagicMock()
        exc.detail = None

        response = rate_limit_exceeded_handler(request, exc)

        assert response.headers.get("Retry-After") == "60"


class TestRateLimitKeyFunction:
    """REQ-013 §7.4: Rate limit key transitions from IP-based to per-user."""

    @pytest.fixture(autouse=False)
    def auth_enabled_settings(self):
        """Enable auth with test secret, restore after test."""
        original_auth = settings.auth_enabled
        original_secret = settings.auth_secret
        settings.auth_enabled = True
        settings.auth_secret = SecretStr(TEST_AUTH_SECRET)
        yield
        settings.auth_enabled = original_auth
        settings.auth_secret = original_secret

    def _make_request(
        self, *, client_host: str = "192.168.1.1", cookies: dict | None = None
    ) -> MagicMock:
        """Create a mock request with client and cookies."""
        request = MagicMock()
        request.client.host = client_host
        request.cookies = cookies or {}
        return request

    def test_returns_ip_when_auth_disabled(self):
        """When auth is disabled, rate limit key is client IP (current behavior)."""
        original = settings.auth_enabled
        settings.auth_enabled = False
        try:
            request = self._make_request(client_host="10.0.0.1")
            key = _rate_limit_key_func(request)
            assert key == "10.0.0.1"
        finally:
            settings.auth_enabled = original

    def test_returns_user_sub_when_auth_enabled_with_valid_jwt(
        self,
        auth_enabled_settings,  # noqa: ARG002
    ):
        """When auth enabled + valid JWT cookie, key is 'user:{sub}'."""
        token = create_test_jwt()
        request = self._make_request(cookies={settings.auth_cookie_name: token})
        key = _rate_limit_key_func(request)
        assert key == f"user:{TEST_USER_ID}"

    def test_returns_unauth_ip_when_auth_enabled_no_cookie(
        self,
        auth_enabled_settings,  # noqa: ARG002
    ):
        """When auth enabled + no JWT cookie, key is 'unauth:{ip}'."""
        request = self._make_request(client_host="203.0.113.5")
        key = _rate_limit_key_func(request)
        assert key == "unauth:203.0.113.5"

    def test_returns_unauth_ip_when_auth_enabled_invalid_jwt(
        self,
        auth_enabled_settings,  # noqa: ARG002
    ):
        """When auth enabled + invalid JWT, key is 'unauth:{ip}'."""
        request = self._make_request(
            client_host="198.51.100.10",
            cookies={settings.auth_cookie_name: "invalid-jwt-token"},
        )
        key = _rate_limit_key_func(request)
        assert key == "unauth:198.51.100.10"

    def test_returns_unauth_ip_when_auth_enabled_expired_jwt(
        self,
        auth_enabled_settings,  # noqa: ARG002
    ):
        """When auth enabled + expired JWT, key is 'unauth:{ip}'."""
        from datetime import timedelta

        token = create_test_jwt(expires_delta=timedelta(hours=-1))
        request = self._make_request(
            client_host="198.51.100.20",
            cookies={settings.auth_cookie_name: token},
        )
        key = _rate_limit_key_func(request)
        assert key == "unauth:198.51.100.20"

    def test_returns_unauth_ip_when_auth_enabled_wrong_secret(
        self,
        auth_enabled_settings,  # noqa: ARG002
    ):
        """JWT signed with wrong secret is treated as unauthenticated."""
        token = create_test_jwt(
            secret="different-secret-that-does-not-match-the-real-one"
        )
        request = self._make_request(
            client_host="198.51.100.30",
            cookies={settings.auth_cookie_name: token},
        )
        key = _rate_limit_key_func(request)
        assert key == "unauth:198.51.100.30"
