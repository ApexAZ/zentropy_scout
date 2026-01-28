"""Tests for bulk operation endpoints.

REQ-006 §2.6: Bulk operations for efficiency.
Tests the /bulk-dismiss, /bulk-favorite, and /bulk-archive endpoints.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import create_app

# Test user ID for authenticated requests
TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def app():
    """Create test application instance."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create authenticated async HTTP client for testing.

    Sets DEFAULT_USER_ID to simulate authenticated user without
    requiring database setup.
    """
    original_user_id = settings.default_user_id
    settings.default_user_id = TEST_USER_ID

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    settings.default_user_id = original_user_id


@pytest.fixture
async def unauthenticated_client(app):
    """Create unauthenticated async HTTP client for testing."""
    original_user_id = settings.default_user_id
    settings.default_user_id = None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    settings.default_user_id = original_user_id


class TestBulkDismissJobPostings:
    """Tests for POST /api/v1/job-postings/bulk-dismiss."""

    @pytest.mark.asyncio
    async def test_bulk_dismiss_requires_ids(self, client):
        """Request must include ids array."""
        response = await client.post("/api/v1/job-postings/bulk-dismiss", json={})
        # REQ-006 §8.1: 400 for validation errors
        assert response.status_code == 400
        assert "ids" in response.text.lower()

    @pytest.mark.asyncio
    async def test_bulk_dismiss_empty_ids_is_valid(self, client):
        """Empty ids array returns empty succeeded array."""
        response = await client.post(
            "/api/v1/job-postings/bulk-dismiss", json={"ids": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["succeeded"] == []
        assert data["data"]["failed"] == []

    @pytest.mark.asyncio
    async def test_bulk_dismiss_returns_partial_success_format(self, client):
        """Response includes succeeded and failed arrays."""
        # Use UUIDs that won't exist (will report as NOT_FOUND in failed)
        fake_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        response = await client.post(
            "/api/v1/job-postings/bulk-dismiss", json={"ids": fake_ids}
        )
        assert response.status_code == 200
        data = response.json()
        assert "succeeded" in data["data"]
        assert "failed" in data["data"]
        assert isinstance(data["data"]["succeeded"], list)
        assert isinstance(data["data"]["failed"], list)

    @pytest.mark.asyncio
    async def test_bulk_dismiss_invalid_uuid_format(self, client):
        """Invalid UUID format returns 400."""
        response = await client.post(
            "/api/v1/job-postings/bulk-dismiss", json={"ids": ["not-a-uuid"]}
        )
        # REQ-006 §8.1: 400 for validation errors
        assert response.status_code == 400


class TestBulkFavoriteJobPostings:
    """Tests for POST /api/v1/job-postings/bulk-favorite."""

    @pytest.mark.asyncio
    async def test_bulk_favorite_requires_ids(self, client):
        """Request must include ids array."""
        response = await client.post(
            "/api/v1/job-postings/bulk-favorite", json={"is_favorite": True}
        )
        # REQ-006 §8.1: 400 for validation errors
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_bulk_favorite_requires_is_favorite(self, client):
        """Request must include is_favorite boolean."""
        response = await client.post(
            "/api/v1/job-postings/bulk-favorite",
            json={"ids": [str(uuid.uuid4())]},
        )
        # REQ-006 §8.1: 400 for validation errors
        assert response.status_code == 400
        assert "is_favorite" in response.text.lower()

    @pytest.mark.asyncio
    async def test_bulk_favorite_empty_ids_is_valid(self, client):
        """Empty ids array returns empty succeeded array."""
        response = await client.post(
            "/api/v1/job-postings/bulk-favorite",
            json={"ids": [], "is_favorite": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["succeeded"] == []
        assert data["data"]["failed"] == []

    @pytest.mark.asyncio
    async def test_bulk_favorite_returns_partial_success_format(self, client):
        """Response includes succeeded and failed arrays."""
        fake_ids = [str(uuid.uuid4())]
        response = await client.post(
            "/api/v1/job-postings/bulk-favorite",
            json={"ids": fake_ids, "is_favorite": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert "succeeded" in data["data"]
        assert "failed" in data["data"]

    @pytest.mark.asyncio
    async def test_bulk_unfavorite_also_works(self, client):
        """is_favorite=False should also work."""
        response = await client.post(
            "/api/v1/job-postings/bulk-favorite",
            json={"ids": [], "is_favorite": False},
        )
        assert response.status_code == 200


class TestBulkArchiveApplications:
    """Tests for POST /api/v1/applications/bulk-archive."""

    @pytest.mark.asyncio
    async def test_bulk_archive_requires_ids(self, client):
        """Request must include ids array."""
        response = await client.post("/api/v1/applications/bulk-archive", json={})
        # REQ-006 §8.1: 400 for validation errors
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_bulk_archive_empty_ids_is_valid(self, client):
        """Empty ids array returns empty succeeded array."""
        response = await client.post(
            "/api/v1/applications/bulk-archive", json={"ids": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["succeeded"] == []
        assert data["data"]["failed"] == []

    @pytest.mark.asyncio
    async def test_bulk_archive_returns_partial_success_format(self, client):
        """Response includes succeeded and failed arrays."""
        fake_ids = [str(uuid.uuid4())]
        response = await client.post(
            "/api/v1/applications/bulk-archive", json={"ids": fake_ids}
        )
        assert response.status_code == 200
        data = response.json()
        assert "succeeded" in data["data"]
        assert "failed" in data["data"]


class TestBulkOperationAuth:
    """Tests that bulk operations require authentication."""

    @pytest.mark.asyncio
    async def test_bulk_dismiss_requires_auth(self, unauthenticated_client):
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.post(
            "/api/v1/job-postings/bulk-dismiss",
            json={"ids": []},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_bulk_favorite_requires_auth(self, unauthenticated_client):
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.post(
            "/api/v1/job-postings/bulk-favorite",
            json={"ids": [], "is_favorite": True},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_bulk_archive_requires_auth(self, unauthenticated_client):
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.post(
            "/api/v1/applications/bulk-archive",
            json={"ids": []},
        )
        assert response.status_code == 401
