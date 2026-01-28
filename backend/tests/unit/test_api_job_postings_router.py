"""Tests for Job Postings API router structure.

REQ-006 §5.1-5.3: URL structure, resource mapping, HTTP methods.
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


class TestJobPostingsRouterMounted:
    """Tests that job-postings router is mounted at correct path."""

    @pytest.mark.asyncio
    async def test_job_postings_endpoint_exists(self, client):
        """GET /api/v1/job-postings should return 401, not 404."""
        response = await client.get("/api/v1/job-postings")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_job_postings_id_endpoint_exists(self, client):
        """GET /api/v1/job-postings/{id} should return 401, not 404."""
        response = await client.get(
            "/api/v1/job-postings/123e4567-e89b-12d3-a456-426614174000"
        )
        assert response.status_code == 401


class TestJobPostingsNestedResources:
    """Tests for job posting nested resources."""

    @pytest.mark.asyncio
    async def test_extracted_skills_endpoint_exists(self, client):
        """GET /api/v1/job-postings/{id}/extracted-skills should exist."""
        response = await client.get(
            "/api/v1/job-postings/123e4567-e89b-12d3-a456-426614174000/extracted-skills"
        )
        assert response.status_code == 401


class TestJobPostingsActionEndpoints:
    """Tests for job posting action endpoints."""

    @pytest.mark.asyncio
    async def test_ingest_endpoint_exists(self, client):
        """POST /api/v1/job-postings/ingest should exist."""
        response = await client.post("/api/v1/job-postings/ingest", json={})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_bulk_dismiss_endpoint_exists(self, client):
        """POST /api/v1/job-postings/bulk-dismiss should exist."""
        response = await client.post("/api/v1/job-postings/bulk-dismiss", json={})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_bulk_favorite_endpoint_exists(self, client):
        """POST /api/v1/job-postings/bulk-favorite should exist."""
        response = await client.post("/api/v1/job-postings/bulk-favorite", json={})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_rescore_endpoint_exists(self, client):
        """POST /api/v1/job-postings/rescore should exist."""
        response = await client.post("/api/v1/job-postings/rescore")
        assert response.status_code == 401


class TestJobPostingsHTTPMethods:
    """Tests that job-postings router supports standard HTTP methods."""

    @pytest.mark.asyncio
    async def test_job_postings_supports_get(self, client):
        """Job-postings should support GET (list)."""
        response = await client.get("/api/v1/job-postings")
        assert response.status_code != 405

    @pytest.mark.asyncio
    async def test_job_postings_supports_post(self, client):
        """Job-postings should support POST (create)."""
        response = await client.post("/api/v1/job-postings", json={})
        assert response.status_code != 405

    @pytest.mark.asyncio
    async def test_job_postings_id_supports_get(self, client):
        """Job-postings/{id} should support GET (read)."""
        response = await client.get(
            "/api/v1/job-postings/123e4567-e89b-12d3-a456-426614174000"
        )
        assert response.status_code != 405

    @pytest.mark.asyncio
    async def test_job_postings_id_supports_patch(self, client):
        """Job-postings/{id} should support PATCH (partial update)."""
        response = await client.patch(
            "/api/v1/job-postings/123e4567-e89b-12d3-a456-426614174000", json={}
        )
        assert response.status_code != 405

    @pytest.mark.asyncio
    async def test_job_postings_id_supports_delete(self, client):
        """Job-postings/{id} should support DELETE."""
        response = await client.delete(
            "/api/v1/job-postings/123e4567-e89b-12d3-a456-426614174000"
        )
        assert response.status_code != 405
