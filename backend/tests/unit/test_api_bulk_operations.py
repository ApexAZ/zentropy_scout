"""Tests for bulk operation endpoints.

REQ-006 §2.6: Bulk operations for efficiency.
Tests the /bulk-dismiss, /bulk-favorite, and /bulk-archive endpoints.

These tests use dependency overrides for auth (not JWT cookies) because they
test request/response shapes without database setup. JWT auth integration
is tested via the conftest.py client fixture in other test files.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.api.deps import get_current_user_id
from app.core.config import settings
from app.main import create_app
from tests.conftest import TEST_AUTH_SECRET, TEST_USER_ID


@pytest.fixture
def app() -> FastAPI:
    """Create test application instance."""
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create authenticated async HTTP client for testing.

    Overrides get_current_user_id to return TEST_USER_ID directly,
    bypassing JWT validation. This avoids needing database setup
    for tests that only verify request/response shapes.
    """

    async def override_get_current_user_id() -> uuid.UUID:
        return TEST_USER_ID

    app.dependency_overrides[get_current_user_id] = override_get_current_user_id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def unauthenticated_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create unauthenticated async HTTP client for testing.

    Auth is enabled but no JWT cookie provided — triggers 401 before
    any DB query (cookie check is first in the validation chain).
    """
    original_auth_enabled = settings.auth_enabled
    original_auth_secret = settings.auth_secret
    settings.auth_enabled = True
    settings.auth_secret = SecretStr(TEST_AUTH_SECRET)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    settings.auth_enabled = original_auth_enabled
    settings.auth_secret = original_auth_secret


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
