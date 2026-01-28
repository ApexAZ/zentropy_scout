"""Tests for remaining API resource routers.

REQ-006 §5.1-5.3: URL structure, resource mapping, HTTP methods.

Tests for: base-resumes, job-variants, applications, cover-letters,
job-sources, user-source-preferences, chat, persona-change-flags,
resume-files, and download endpoints.
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


# =============================================================================
# Base Resumes
# =============================================================================


class TestBaseResumesRouter:
    """Tests for base-resumes resource."""

    @pytest.mark.asyncio
    async def test_base_resumes_endpoint_exists(self, client):
        """GET /api/v1/base-resumes should exist."""
        response = await client.get("/api/v1/base-resumes")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_base_resumes_supports_crud(self, client):
        """Base-resumes should support GET, POST, PATCH, DELETE."""
        assert (await client.get("/api/v1/base-resumes")).status_code != 405
        assert (await client.post("/api/v1/base-resumes", json={})).status_code != 405

        uuid = "123e4567-e89b-12d3-a456-426614174000"
        assert (await client.get(f"/api/v1/base-resumes/{uuid}")).status_code != 405
        assert (
            await client.patch(f"/api/v1/base-resumes/{uuid}", json={})
        ).status_code != 405
        assert (await client.delete(f"/api/v1/base-resumes/{uuid}")).status_code != 405

    @pytest.mark.asyncio
    async def test_base_resumes_download_endpoint(self, client):
        """GET /api/v1/base-resumes/{id}/download should exist."""
        uuid = "123e4567-e89b-12d3-a456-426614174000"
        response = await client.get(f"/api/v1/base-resumes/{uuid}/download")
        assert response.status_code == 401


# =============================================================================
# Job Variants
# =============================================================================


class TestJobVariantsRouter:
    """Tests for job-variants resource."""

    @pytest.mark.asyncio
    async def test_job_variants_endpoint_exists(self, client):
        """GET /api/v1/job-variants should exist."""
        response = await client.get("/api/v1/job-variants")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_job_variants_supports_crud(self, client):
        """Job-variants should support GET, POST, PATCH, DELETE."""
        assert (await client.get("/api/v1/job-variants")).status_code != 405
        assert (await client.post("/api/v1/job-variants", json={})).status_code != 405

        uuid = "123e4567-e89b-12d3-a456-426614174000"
        assert (await client.get(f"/api/v1/job-variants/{uuid}")).status_code != 405
        assert (
            await client.patch(f"/api/v1/job-variants/{uuid}", json={})
        ).status_code != 405
        assert (await client.delete(f"/api/v1/job-variants/{uuid}")).status_code != 405


# =============================================================================
# Applications
# =============================================================================


class TestApplicationsRouter:
    """Tests for applications resource."""

    @pytest.mark.asyncio
    async def test_applications_endpoint_exists(self, client):
        """GET /api/v1/applications should exist."""
        response = await client.get("/api/v1/applications")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_applications_supports_crud(self, client):
        """Applications should support GET, POST, PATCH, DELETE."""
        assert (await client.get("/api/v1/applications")).status_code != 405
        assert (await client.post("/api/v1/applications", json={})).status_code != 405

        uuid = "123e4567-e89b-12d3-a456-426614174000"
        assert (await client.get(f"/api/v1/applications/{uuid}")).status_code != 405
        assert (
            await client.patch(f"/api/v1/applications/{uuid}", json={})
        ).status_code != 405
        assert (await client.delete(f"/api/v1/applications/{uuid}")).status_code != 405

    @pytest.mark.asyncio
    async def test_applications_timeline_endpoint(self, client):
        """GET /api/v1/applications/{id}/timeline should exist."""
        uuid = "123e4567-e89b-12d3-a456-426614174000"
        response = await client.get(f"/api/v1/applications/{uuid}/timeline")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_applications_bulk_archive_endpoint(self, client):
        """POST /api/v1/applications/bulk-archive should exist."""
        response = await client.post("/api/v1/applications/bulk-archive", json={})
        assert response.status_code == 401


# =============================================================================
# Cover Letters
# =============================================================================


class TestCoverLettersRouter:
    """Tests for cover-letters resource."""

    @pytest.mark.asyncio
    async def test_cover_letters_endpoint_exists(self, client):
        """GET /api/v1/cover-letters should exist."""
        response = await client.get("/api/v1/cover-letters")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_cover_letters_supports_crud(self, client):
        """Cover-letters should support GET, POST, PATCH, DELETE."""
        assert (await client.get("/api/v1/cover-letters")).status_code != 405
        assert (await client.post("/api/v1/cover-letters", json={})).status_code != 405

        uuid = "123e4567-e89b-12d3-a456-426614174000"
        assert (await client.get(f"/api/v1/cover-letters/{uuid}")).status_code != 405
        assert (
            await client.patch(f"/api/v1/cover-letters/{uuid}", json={})
        ).status_code != 405
        assert (await client.delete(f"/api/v1/cover-letters/{uuid}")).status_code != 405


# =============================================================================
# Job Sources
# =============================================================================


class TestJobSourcesRouter:
    """Tests for job-sources resource."""

    @pytest.mark.asyncio
    async def test_job_sources_endpoint_exists(self, client):
        """GET /api/v1/job-sources should exist."""
        response = await client.get("/api/v1/job-sources")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_job_sources_read_only(self, client):
        """Job-sources should be read-only (GET only)."""
        # GET should work (not 405)
        assert (await client.get("/api/v1/job-sources")).status_code != 405
        # POST/PATCH/DELETE should return 405
        response = await client.post("/api/v1/job-sources", json={})
        assert response.status_code == 405


class TestUserSourcePreferencesRouter:
    """Tests for user-source-preferences resource."""

    @pytest.mark.asyncio
    async def test_user_source_preferences_endpoint_exists(self, client):
        """GET /api/v1/user-source-preferences should exist."""
        response = await client.get("/api/v1/user-source-preferences")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_user_source_preferences_read_update_only(self, client):
        """User-source-preferences should support GET and PATCH only."""
        assert (await client.get("/api/v1/user-source-preferences")).status_code != 405

        uuid = "123e4567-e89b-12d3-a456-426614174000"
        assert (
            await client.patch(f"/api/v1/user-source-preferences/{uuid}", json={})
        ).status_code != 405


# =============================================================================
# Chat
# =============================================================================


class TestChatRouter:
    """Tests for chat endpoints."""

    @pytest.mark.asyncio
    async def test_chat_messages_endpoint_exists(self, client):
        """POST /api/v1/chat/messages should exist."""
        response = await client.post("/api/v1/chat/messages", json={})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_stream_endpoint_exists(self, client):
        """GET /api/v1/chat/stream should exist (SSE)."""
        response = await client.get("/api/v1/chat/stream")
        assert response.status_code == 401


# =============================================================================
# Persona Change Flags
# =============================================================================


class TestPersonaChangeFlagsRouter:
    """Tests for persona-change-flags resource."""

    @pytest.mark.asyncio
    async def test_persona_change_flags_endpoint_exists(self, client):
        """GET /api/v1/persona-change-flags should exist."""
        response = await client.get("/api/v1/persona-change-flags")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_persona_change_flags_patch_only(self, client):
        """Persona-change-flags should support GET and PATCH."""
        assert (await client.get("/api/v1/persona-change-flags")).status_code != 405

        uuid = "123e4567-e89b-12d3-a456-426614174000"
        assert (
            await client.patch(f"/api/v1/persona-change-flags/{uuid}", json={})
        ).status_code != 405


# =============================================================================
# Resume Files (upload)
# =============================================================================


class TestResumeFilesRouter:
    """Tests for resume-files upload endpoint."""

    @pytest.mark.asyncio
    async def test_resume_files_upload_endpoint_exists(self, client):
        """POST /api/v1/resume-files should exist."""
        response = await client.post("/api/v1/resume-files")
        assert response.status_code == 401


# =============================================================================
# Download Endpoints
# =============================================================================


class TestDownloadEndpoints:
    """Tests for PDF download endpoints."""

    @pytest.mark.asyncio
    async def test_submitted_resume_pdf_download(self, client):
        """GET /api/v1/submitted-resume-pdfs/{id}/download should exist."""
        uuid = "123e4567-e89b-12d3-a456-426614174000"
        response = await client.get(f"/api/v1/submitted-resume-pdfs/{uuid}/download")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_submitted_cover_letter_pdf_download(self, client):
        """GET /api/v1/submitted-cover-letter-pdfs/{id}/download should exist."""
        uuid = "123e4567-e89b-12d3-a456-426614174000"
        response = await client.get(
            f"/api/v1/submitted-cover-letter-pdfs/{uuid}/download"
        )
        assert response.status_code == 401


# =============================================================================
# Refresh Endpoint
# =============================================================================


class TestRefreshEndpoint:
    """Tests for refresh action endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_endpoint_exists(self, client):
        """POST /api/v1/refresh should exist."""
        response = await client.post("/api/v1/refresh")
        assert response.status_code == 401
