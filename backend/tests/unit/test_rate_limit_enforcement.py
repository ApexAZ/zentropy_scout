"""Rate limit enforcement tests — verify slowapi actually blocks excess requests.

Security: The existing test_rate_limiting.py tests configuration and handler logic
via mocks. These tests verify enforcement end-to-end at the HTTP transport layer
using a minimal FastAPI app with low rate limits.

§13.7: Load testing rate limits (verify slowapi enforcement).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.rate_limiting import rate_limit_exceeded_handler

# ---------------------------------------------------------------------------
# Minimal test app — isolates slowapi enforcement from real app dependencies
# ---------------------------------------------------------------------------

_TEST_BASE_URL = "http://test"
_TEST_LIMIT_LOW = "3/minute"
_TEST_LIMIT_HIGH = "6/minute"
_ENDPOINT_LOW = "/low"
_ENDPOINT_HIGH = "/high"


def _build_test_app(*, enabled: bool = True) -> FastAPI:
    """Create a minimal FastAPI app with rate-limited endpoints.

    Args:
        enabled: Whether the rate limiter is active.

    Returns:
        Configured FastAPI app with /low and /high endpoints.
    """
    limiter = Limiter(key_func=get_remote_address, enabled=enabled)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @app.get(_ENDPOINT_LOW)
    @limiter.limit(_TEST_LIMIT_LOW)
    async def low_limit(request: Request) -> dict[str, str]:  # noqa: ARG001
        return {"status": "ok"}

    @app.get(_ENDPOINT_HIGH)
    @limiter.limit(_TEST_LIMIT_HIGH)
    async def high_limit(request: Request) -> dict[str, str]:  # noqa: ARG001
        return {"status": "ok"}

    return app


@asynccontextmanager
async def _test_client(
    *,
    enabled: bool = True,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client bound to a fresh test app.

    Each call creates a new app + limiter, ensuring tests are isolated.

    Args:
        enabled: Whether the rate limiter is active.

    Yields:
        Configured AsyncClient for making requests.
    """
    app = _build_test_app(enabled=enabled)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=_TEST_BASE_URL) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRateLimitEnforcement:
    """Verify slowapi blocks requests exceeding the configured limit."""

    @pytest.mark.asyncio
    async def test_requests_within_limit_succeed(self):
        """All requests within the limit should return 200."""
        async with _test_client() as ac:
            for _ in range(3):
                resp = await ac.get(_ENDPOINT_LOW)
                assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_request_exceeding_limit_returns_429(self):
        """The request exceeding the limit should return 429."""
        async with _test_client() as ac:
            # Exhaust the 3/minute limit
            for _ in range(3):
                resp = await ac.get(_ENDPOINT_LOW)
                assert resp.status_code == 200

            # 4th request should be rejected
            resp = await ac.get(_ENDPOINT_LOW)
            assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_429_response_has_error_envelope(self):
        """429 response should use the standard error envelope format."""
        async with _test_client() as ac:
            for _ in range(3):
                await ac.get(_ENDPOINT_LOW)

            resp = await ac.get(_ENDPOINT_LOW)
            body = resp.json()

            assert "error" in body
            assert body["error"]["code"] == "RATE_LIMITED"
            assert "Rate limit exceeded" in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_429_response_has_retry_after_header(self):
        """429 response should include a Retry-After header."""
        async with _test_client() as ac:
            for _ in range(3):
                await ac.get(_ENDPOINT_LOW)

            resp = await ac.get(_ENDPOINT_LOW)

            assert "retry-after" in resp.headers
            retry_after = int(resp.headers["retry-after"])
            assert retry_after > 0

    @pytest.mark.asyncio
    async def test_different_endpoints_have_independent_limits(self):
        """Each endpoint's rate limit counter is tracked independently."""
        async with _test_client() as ac:
            # Exhaust the /low limit (3/minute)
            for _ in range(3):
                await ac.get(_ENDPOINT_LOW)

            # /low should now be blocked
            resp = await ac.get(_ENDPOINT_LOW)
            assert resp.status_code == 429

            # /high should still work (separate counter, 6/minute limit)
            resp = await ac.get(_ENDPOINT_HIGH)
            assert resp.status_code == 200


class TestRateLimitDisabledEnforcement:
    """Verify rate limiter can be fully disabled."""

    @pytest.mark.asyncio
    async def test_disabled_limiter_allows_all_requests(self):
        """When disabled, all requests should succeed regardless of volume."""
        async with _test_client(enabled=False) as ac:
            # Send more requests than the limit allows
            for _ in range(10):
                resp = await ac.get(_ENDPOINT_LOW)
                assert resp.status_code == 200


class TestRateLimitBurstBehavior:
    """Verify burst request handling."""

    @pytest.mark.asyncio
    async def test_rapid_burst_enforces_limit(self):
        """Rapid concurrent-style requests should still be counted."""
        async with _test_client() as ac:
            responses = []
            # Send 6 requests as fast as possible
            for _ in range(6):
                resp = await ac.get(_ENDPOINT_LOW)
                responses.append(resp.status_code)

            # First 3 should succeed, remaining should be 429
            assert responses[:3] == [200, 200, 200]
            assert all(code == 429 for code in responses[3:])

    @pytest.mark.asyncio
    async def test_high_limit_allows_more_requests(self):
        """Higher limit endpoint should allow more requests before blocking."""
        async with _test_client() as ac:
            responses = []
            for _ in range(8):
                resp = await ac.get(_ENDPOINT_HIGH)
                responses.append(resp.status_code)

            # First 6 should succeed, remaining should be 429
            assert responses[:6] == [200, 200, 200, 200, 200, 200]
            assert all(code == 429 for code in responses[6:])
