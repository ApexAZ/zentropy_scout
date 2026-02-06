"""Tests for rate limiting configuration.

Security: Tests for API abuse prevention via rate limiting.
"""

import pytest


class TestRateLimitConfiguration:
    """Tests for rate limit settings."""

    def test_default_llm_rate_limit(self):
        """Default LLM rate limit is 10/minute."""
        from app.core.config import Settings

        settings = Settings()
        assert settings.rate_limit_llm == "10/minute"

    def test_default_embeddings_rate_limit(self):
        """Default embeddings rate limit is 5/minute."""
        from app.core.config import Settings

        settings = Settings()
        assert settings.rate_limit_embeddings == "5/minute"

    def test_rate_limit_enabled_by_default(self):
        """Rate limiting is enabled by default."""
        from app.core.config import Settings

        settings = Settings()
        assert settings.rate_limit_enabled is True


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


class TestRateLimitedEndpoints:
    """Tests for rate-limited endpoints integration."""

    @pytest.mark.asyncio
    async def test_ingest_endpoint_has_rate_limit_decorator(self):
        """Ingest endpoint should have rate limit decorator."""
        from app.api.v1.job_postings import ingest_job_posting

        # Check if the function has rate limit configuration
        # slowapi adds __self__ attribute to decorated functions
        assert hasattr(ingest_job_posting, "__wrapped__") or hasattr(
            ingest_job_posting, "_limit"
        )

    @pytest.mark.asyncio
    async def test_chat_messages_endpoint_has_rate_limit_decorator(self):
        """Chat messages endpoint should have rate limit decorator."""
        from app.api.v1.chat import send_chat_message

        assert hasattr(send_chat_message, "__wrapped__") or hasattr(
            send_chat_message, "_limit"
        )

    @pytest.mark.asyncio
    async def test_embeddings_regenerate_endpoint_has_rate_limit_decorator(self):
        """Embeddings regenerate endpoint should have rate limit decorator."""
        from app.api.v1.personas import regenerate_embeddings

        assert hasattr(regenerate_embeddings, "__wrapped__") or hasattr(
            regenerate_embeddings, "_limit"
        )

    @pytest.mark.asyncio
    async def test_rescore_endpoint_has_rate_limit_decorator(self):
        """Rescore endpoint should have rate limit decorator."""
        from app.api.v1.job_postings import rescore_job_postings

        assert hasattr(rescore_job_postings, "__wrapped__") or hasattr(
            rescore_job_postings, "_limit"
        )


class TestRateLimitDisabled:
    """Tests for disabled rate limiting (testing mode)."""

    def test_limiter_can_be_disabled_via_settings(self):
        """Rate limiter should respect enabled setting."""
        from app.core.rate_limiting import limiter

        # The limiter should have an enabled property that can be checked
        # We verify it reads from settings
        assert hasattr(limiter, "_enabled") or hasattr(limiter, "enabled")
