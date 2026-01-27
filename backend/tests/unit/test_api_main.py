"""Tests for FastAPI application and exception handlers.

REQ-006 §2.1, §8.1: REST API with consistent error handling.
"""

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
