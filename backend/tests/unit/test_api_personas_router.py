"""Tests for Personas API router structure.

REQ-006 §5.1-5.3: URL structure, resource mapping, HTTP methods.

These tests verify the router is mounted correctly and responds
to the expected HTTP methods. Actual CRUD logic is tested elsewhere.
"""

import pytest
from httpx import ASGITransport, AsyncClient

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


class TestPersonasRouterMounted:
    """Tests that personas router is mounted at correct path."""

    @pytest.mark.asyncio
    async def test_personas_endpoint_exists(self, client):
        """GET /api/v1/personas should return 401 (auth required), not 404."""
        response = await client.get("/api/v1/personas")
        # 401 = route exists but auth required
        # 404 = route doesn't exist
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_personas_id_endpoint_exists(self, client):
        """GET /api/v1/personas/{id} should return 401, not 404."""
        response = await client.get(
            "/api/v1/personas/123e4567-e89b-12d3-a456-426614174000"
        )
        assert response.status_code == 401


class TestPersonasNestedResources:
    """Tests for persona nested resources (REQ-006 §5.2)."""

    @pytest.mark.asyncio
    async def test_work_history_endpoint_exists(self, client):
        """GET /api/v1/personas/{id}/work-history should exist."""
        response = await client.get(
            "/api/v1/personas/123e4567-e89b-12d3-a456-426614174000/work-history"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_skills_endpoint_exists(self, client):
        """GET /api/v1/personas/{id}/skills should exist."""
        response = await client.get(
            "/api/v1/personas/123e4567-e89b-12d3-a456-426614174000/skills"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_education_endpoint_exists(self, client):
        """GET /api/v1/personas/{id}/education should exist."""
        response = await client.get(
            "/api/v1/personas/123e4567-e89b-12d3-a456-426614174000/education"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_certifications_endpoint_exists(self, client):
        """GET /api/v1/personas/{id}/certifications should exist."""
        response = await client.get(
            "/api/v1/personas/123e4567-e89b-12d3-a456-426614174000/certifications"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_achievement_stories_endpoint_exists(self, client):
        """GET /api/v1/personas/{id}/achievement-stories should exist."""
        response = await client.get(
            "/api/v1/personas/123e4567-e89b-12d3-a456-426614174000/achievement-stories"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_voice_profile_endpoint_exists(self, client):
        """GET /api/v1/personas/{id}/voice-profile should exist."""
        response = await client.get(
            "/api/v1/personas/123e4567-e89b-12d3-a456-426614174000/voice-profile"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_custom_non_negotiables_endpoint_exists(self, client):
        """GET /api/v1/personas/{id}/custom-non-negotiables should exist."""
        response = await client.get(
            "/api/v1/personas/123e4567-e89b-12d3-a456-426614174000/custom-non-negotiables"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_embeddings_regenerate_endpoint_exists(self, client):
        """POST /api/v1/personas/{id}/embeddings/regenerate should exist."""
        response = await client.post(
            "/api/v1/personas/123e4567-e89b-12d3-a456-426614174000/embeddings/regenerate"
        )
        assert response.status_code == 401


class TestPersonasHTTPMethods:
    """Tests that personas router supports standard HTTP methods (REQ-006 §5.3)."""

    @pytest.mark.asyncio
    async def test_personas_supports_get(self, client):
        """Personas should support GET (list)."""
        response = await client.get("/api/v1/personas")
        assert response.status_code != 405  # 405 = Method Not Allowed

    @pytest.mark.asyncio
    async def test_personas_supports_post(self, client):
        """Personas should support POST (create)."""
        response = await client.post("/api/v1/personas", json={})
        assert response.status_code != 405

    @pytest.mark.asyncio
    async def test_personas_id_supports_get(self, client):
        """Personas/{id} should support GET (read)."""
        response = await client.get(
            "/api/v1/personas/123e4567-e89b-12d3-a456-426614174000"
        )
        assert response.status_code != 405

    @pytest.mark.asyncio
    async def test_personas_id_supports_patch(self, client):
        """Personas/{id} should support PATCH (partial update)."""
        response = await client.patch(
            "/api/v1/personas/123e4567-e89b-12d3-a456-426614174000", json={}
        )
        assert response.status_code != 405

    @pytest.mark.asyncio
    async def test_personas_id_supports_delete(self, client):
        """Personas/{id} should support DELETE."""
        response = await client.delete(
            "/api/v1/personas/123e4567-e89b-12d3-a456-426614174000"
        )
        assert response.status_code != 405
