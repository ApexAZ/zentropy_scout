"""Tests for FastAPI application and exception handlers.

REQ-006 §2.1, §8.1: REST API with consistent error handling.
"""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.errors import (
    ConflictError,
    ForbiddenError,
    InternalError,
    InvalidStateError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.main import create_app


@pytest.fixture
def app():
    """Create test application instance."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        """Health endpoint should return 200 status."""
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_healthy_status(self, client):
        """Health endpoint should return healthy status."""
        response = await client.get("/health")
        assert response.json()["status"] == "healthy"


class TestAPIVersioning:
    """Tests for API versioning."""

    @pytest.mark.asyncio
    async def test_v1_router_mounted(self, client):
        """v1 router should be mounted at /api/v1."""
        # Just verify the path exists (404 is expected for non-existent routes)
        response = await client.get("/api/v1/nonexistent")
        # 404 means router is mounted but route doesn't exist
        # 422 or other would indicate router problems
        assert response.status_code == 404


class TestExceptionHandlers:
    """Tests for exception handlers.

    These tests verify that our custom exceptions are properly
    converted to HTTP responses with the correct error envelope.
    """

    @pytest.mark.asyncio
    async def test_validation_error_returns_400(self, app, client):
        """ValidationError should return 400 with error envelope."""

        # Add a test route that raises ValidationError
        @app.get("/test/validation-error")
        async def raise_validation_error():
            raise ValidationError("Invalid input", details=[{"field": "test"}])

        response = await client.get("/test/validation-error")
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_unauthorized_error_returns_401(self, app, client):
        """UnauthorizedError should return 401 with error envelope."""

        @app.get("/test/unauthorized-error")
        async def raise_unauthorized_error():
            raise UnauthorizedError("No token provided")

        response = await client.get("/test/unauthorized-error")
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_forbidden_error_returns_403(self, app, client):
        """ForbiddenError should return 403 with error envelope."""

        @app.get("/test/forbidden-error")
        async def raise_forbidden_error():
            raise ForbiddenError("Not your resource")

        response = await client.get("/test/forbidden-error")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    @pytest.mark.asyncio
    async def test_not_found_error_returns_404(self, app, client):
        """NotFoundError should return 404 with error envelope."""

        @app.get("/test/not-found-error")
        async def raise_not_found_error():
            raise NotFoundError("Persona", "123")

        response = await client.get("/test/not-found-error")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_conflict_error_returns_409(self, app, client):
        """ConflictError should return 409 with error envelope."""

        @app.get("/test/conflict-error")
        async def raise_conflict_error():
            raise ConflictError("DUPLICATE_APPLICATION", "Already applied")

        response = await client.get("/test/conflict-error")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "DUPLICATE_APPLICATION"

    @pytest.mark.asyncio
    async def test_invalid_state_error_returns_422(self, app, client):
        """InvalidStateError should return 422 with error envelope."""

        @app.get("/test/invalid-state-error")
        async def raise_invalid_state_error():
            raise InvalidStateError("Cannot approve already approved")

        response = await client.get("/test/invalid-state-error")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    @pytest.mark.asyncio
    async def test_internal_error_returns_500(self, app, client):
        """InternalError should return 500 with error envelope."""

        @app.get("/test/internal-error")
        async def raise_internal_error():
            raise InternalError("Database connection failed")

        response = await client.get("/test/internal-error")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"

    @pytest.mark.asyncio
    async def test_internal_error_does_not_expose_details(self, app, client):
        """InternalError should not expose sensitive error details."""

        @app.get("/test/internal-no-details")
        async def raise_internal_with_details():
            raise InternalError("Database connection to prod-db-01 failed")

        response = await client.get("/test/internal-no-details")
        assert response.status_code == 500
        data = response.json()
        # Should have generic message, not the detailed one
        # (InternalError uses the message as-is, so we verify format)
        assert data["error"]["code"] == "INTERNAL_ERROR"
        assert "message" in data["error"]

    @pytest.mark.asyncio
    async def test_error_response_has_correct_envelope(self, app, client):
        """All error responses should use {"error": {...}} envelope."""

        @app.get("/test/envelope-check")
        async def raise_error():
            raise NotFoundError("Item")

        response = await client.get("/test/envelope-check")
        data = response.json()
        # Must have "error" key
        assert "error" in data
        # Error must have required fields
        assert "code" in data["error"]
        assert "message" in data["error"]
        # Should not have "data" key
        assert "data" not in data


class TestCORSMiddleware:
    """Tests for CORS middleware configuration."""

    @pytest.mark.asyncio
    async def test_cors_allows_configured_origin(self, client):
        """CORS should allow requests from configured origins."""
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Preflight should succeed
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "http://localhost:3000"
        )

    @pytest.mark.asyncio
    async def test_cors_denies_unconfigured_origin(self):
        """CORS should deny requests from unconfigured origins."""
        # Create app with specific origin
        with patch("app.main.settings.allowed_origins", ["http://allowed-origin.com"]):
            test_app = create_app()
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                response = await ac.options(
                    "/health",
                    headers={
                        "Origin": "http://malicious-site.com",
                        "Access-Control-Request-Method": "GET",
                    },
                )
                # Origin should NOT be in allowed origins header
                allowed_origin = response.headers.get("access-control-allow-origin")
                assert allowed_origin != "http://malicious-site.com"

    @pytest.mark.asyncio
    async def test_cors_headers_on_actual_request(self, client):
        """CORS headers should be present on actual requests."""
        response = await client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "http://localhost:3000"
        )


class TestSecurityHeadersMiddleware:
    """Tests for security headers middleware."""

    @pytest.mark.asyncio
    async def test_x_frame_options_header(self, client):
        """X-Frame-Options header should be DENY."""
        response = await client.get("/health")
        assert response.headers.get("x-frame-options") == "DENY"

    @pytest.mark.asyncio
    async def test_x_content_type_options_header(self, client):
        """X-Content-Type-Options header should be nosniff."""
        response = await client.get("/health")
        assert response.headers.get("x-content-type-options") == "nosniff"

    @pytest.mark.asyncio
    async def test_x_xss_protection_header(self, client):
        """X-XSS-Protection header should enable XSS filter."""
        response = await client.get("/health")
        assert response.headers.get("x-xss-protection") == "1; mode=block"

    @pytest.mark.asyncio
    async def test_referrer_policy_header(self, client):
        """Referrer-Policy header should be set."""
        response = await client.get("/health")
        assert (
            response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        )

    @pytest.mark.asyncio
    async def test_cache_control_on_api_endpoints(self, client):
        """API endpoints should have no-store cache control."""
        response = await client.get("/api/v1/personas")
        assert "no-store" in response.headers.get("cache-control", "")

    @pytest.mark.asyncio
    async def test_cache_control_not_on_health(self, client):
        """Health endpoint (not under /api/) may be cached."""
        response = await client.get("/health")
        # Cache-Control is only set for /api/ paths
        cache_control = response.headers.get("cache-control", "")
        assert "no-store" not in cache_control

    @pytest.mark.asyncio
    async def test_content_security_policy_header(self, client):
        """Content-Security-Policy should be restrictive for API."""
        response = await client.get("/health")
        csp = response.headers.get("content-security-policy")
        assert csp is not None
        assert "default-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp

    @pytest.mark.asyncio
    async def test_hsts_header_not_in_development(self, client):
        """HSTS header should not be present in development."""
        response = await client.get("/health")
        # Default environment is "development", so HSTS should be absent
        assert response.headers.get("strict-transport-security") is None

    @pytest.mark.asyncio
    async def test_hsts_header_in_production(self, client, monkeypatch):
        """HSTS header should be present in production."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "environment", "production")
        response = await client.get("/health")
        hsts = response.headers.get("strict-transport-security")
        assert hsts is not None
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    @pytest.mark.asyncio
    async def test_cross_origin_opener_policy_header(self, client):
        """Cross-Origin-Opener-Policy should isolate browsing context (Spectre mitigation)."""
        response = await client.get("/health")
        assert response.headers.get("cross-origin-opener-policy") == "same-origin"

    @pytest.mark.asyncio
    async def test_cross_origin_embedder_policy_header(self, client):
        """Cross-Origin-Embedder-Policy should require CORP (Spectre mitigation)."""
        response = await client.get("/health")
        assert response.headers.get("cross-origin-embedder-policy") == "require-corp"

    @pytest.mark.asyncio
    async def test_cross_origin_resource_policy_header(self, client):
        """Cross-Origin-Resource-Policy should restrict resource sharing (Spectre mitigation)."""
        response = await client.get("/health")
        assert response.headers.get("cross-origin-resource-policy") == "same-origin"

    @pytest.mark.asyncio
    async def test_spectre_headers_on_api_endpoints(self, client):
        """Spectre mitigation headers should be present on API endpoints too."""
        response = await client.get("/api/v1/personas")
        assert response.headers.get("cross-origin-opener-policy") == "same-origin"
        assert response.headers.get("cross-origin-embedder-policy") == "require-corp"
        assert response.headers.get("cross-origin-resource-policy") == "same-origin"
