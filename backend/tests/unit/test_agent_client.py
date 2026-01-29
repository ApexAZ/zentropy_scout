"""Tests for Agent API client abstraction.

REQ-006 §2.3: API-Mediated Agents
REQ-007 §4.2: Chat Agent Tool Categories

These tests verify:
- AgentAPIClient protocol methods exist and have correct signatures
- BaseAgentClient methods correctly delegate to _request
- Factory function returns appropriate client based on config
"""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agents.base import (
    BaseAgentClient,
    LocalAgentClient,
    get_agent_client,
    reset_agent_client,
)


class MockAgentClient(BaseAgentClient):
    """Mock implementation of BaseAgentClient for testing.

    WHY: We need to test that BaseAgentClient methods correctly delegate
    to _request without actually making API calls.
    """

    def __init__(self) -> None:
        """Initialize with a mock _request method."""
        self._request = AsyncMock(return_value={"data": {}})

    async def _request(  # type: ignore[override]
        self,
        method: str,
        path: str,
        user_id: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Mock _request that records calls."""
        # This is replaced by AsyncMock in __init__
        raise NotImplementedError


@pytest.fixture
def mock_client() -> MockAgentClient:
    """Create a MockAgentClient for testing."""
    return MockAgentClient()


@pytest.fixture(autouse=True)
def reset_singleton() -> Generator[None, None, None]:
    """Reset the agent client singleton before each test."""
    reset_agent_client()
    yield
    reset_agent_client()


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestGetAgentClient:
    """Tests for get_agent_client factory function."""

    def test_returns_local_client_by_default(self):
        """Factory returns LocalAgentClient in local mode."""
        client = get_agent_client()
        assert isinstance(client, LocalAgentClient)

    def test_returns_singleton(self):
        """Factory returns the same instance on subsequent calls."""
        client1 = get_agent_client()
        client2 = get_agent_client()
        assert client1 is client2

    def test_reset_clears_singleton(self):
        """reset_agent_client clears the singleton."""
        client1 = get_agent_client()
        reset_agent_client()
        client2 = get_agent_client()
        assert client1 is not client2


# =============================================================================
# Job Posting Methods Tests
# =============================================================================


class TestJobPostingMethods:
    """Tests for job posting client methods."""

    @pytest.mark.asyncio
    async def test_list_job_postings(self, mock_client: MockAgentClient):
        """list_job_postings calls GET /job-postings with params."""
        user_id = str(uuid4())
        await mock_client.list_job_postings(user_id, status="New", page=2)

        mock_client._request.assert_called_once_with(
            "GET",
            "/job-postings",
            user_id,
            params={"page": 2, "per_page": 20, "status": "New"},
        )

    @pytest.mark.asyncio
    async def test_get_job_posting(self, mock_client: MockAgentClient):
        """get_job_posting calls GET /job-postings/{id}."""
        user_id = str(uuid4())
        job_id = str(uuid4())
        await mock_client.get_job_posting(job_id, user_id)

        mock_client._request.assert_called_once_with(
            "GET", f"/job-postings/{job_id}", user_id
        )

    @pytest.mark.asyncio
    async def test_create_job_posting(self, mock_client: MockAgentClient):
        """create_job_posting calls POST /job-postings."""
        user_id = str(uuid4())
        data = {"url": "https://example.com/job", "raw_text": "Job posting text"}
        await mock_client.create_job_posting(user_id, data)

        mock_client._request.assert_called_once_with(
            "POST", "/job-postings", user_id, data=data
        )

    @pytest.mark.asyncio
    async def test_update_job_posting(self, mock_client: MockAgentClient):
        """update_job_posting calls PATCH /job-postings/{id}."""
        user_id = str(uuid4())
        job_id = str(uuid4())
        data = {"status": "Reviewed"}
        await mock_client.update_job_posting(job_id, user_id, data)

        mock_client._request.assert_called_once_with(
            "PATCH", f"/job-postings/{job_id}", user_id, data=data
        )

    @pytest.mark.asyncio
    async def test_bulk_dismiss_job_postings(self, mock_client: MockAgentClient):
        """bulk_dismiss_job_postings calls POST /job-postings/bulk-dismiss."""
        user_id = str(uuid4())
        job_ids = [str(uuid4()), str(uuid4())]
        await mock_client.bulk_dismiss_job_postings(user_id, job_ids)

        mock_client._request.assert_called_once_with(
            "POST", "/job-postings/bulk-dismiss", user_id, data={"ids": job_ids}
        )

    @pytest.mark.asyncio
    async def test_bulk_favorite_job_postings(self, mock_client: MockAgentClient):
        """bulk_favorite_job_postings calls POST /job-postings/bulk-favorite."""
        user_id = str(uuid4())
        job_ids = [str(uuid4()), str(uuid4())]
        await mock_client.bulk_favorite_job_postings(user_id, job_ids, is_favorite=True)

        mock_client._request.assert_called_once_with(
            "POST",
            "/job-postings/bulk-favorite",
            user_id,
            data={"ids": job_ids, "is_favorite": True},
        )


# =============================================================================
# Application Methods Tests
# =============================================================================


class TestApplicationMethods:
    """Tests for application client methods."""

    @pytest.mark.asyncio
    async def test_list_applications(self, mock_client: MockAgentClient):
        """list_applications calls GET /applications with params."""
        user_id = str(uuid4())
        await mock_client.list_applications(user_id, status="Applied")

        mock_client._request.assert_called_once_with(
            "GET",
            "/applications",
            user_id,
            params={"page": 1, "per_page": 20, "status": "Applied"},
        )

    @pytest.mark.asyncio
    async def test_get_application(self, mock_client: MockAgentClient):
        """get_application calls GET /applications/{id}."""
        user_id = str(uuid4())
        app_id = str(uuid4())
        await mock_client.get_application(app_id, user_id)

        mock_client._request.assert_called_once_with(
            "GET", f"/applications/{app_id}", user_id
        )

    @pytest.mark.asyncio
    async def test_create_application(self, mock_client: MockAgentClient):
        """create_application calls POST /applications."""
        user_id = str(uuid4())
        job_posting_id = str(uuid4())
        data = {"job_posting_id": job_posting_id, "status": "Applied"}
        await mock_client.create_application(user_id, data)

        mock_client._request.assert_called_once_with(
            "POST", "/applications", user_id, data=data
        )

    @pytest.mark.asyncio
    async def test_update_application(self, mock_client: MockAgentClient):
        """update_application calls PATCH /applications/{id}."""
        user_id = str(uuid4())
        app_id = str(uuid4())
        data = {"status": "Interviewing"}
        await mock_client.update_application(app_id, user_id, data)

        mock_client._request.assert_called_once_with(
            "PATCH", f"/applications/{app_id}", user_id, data=data
        )


# =============================================================================
# Base Resume Methods Tests
# =============================================================================


class TestBaseResumeMethods:
    """Tests for base resume client methods."""

    @pytest.mark.asyncio
    async def test_list_base_resumes(self, mock_client: MockAgentClient):
        """list_base_resumes calls GET /base-resumes."""
        user_id = str(uuid4())
        await mock_client.list_base_resumes(user_id)

        mock_client._request.assert_called_once_with(
            "GET",
            "/base-resumes",
            user_id,
            params={"page": 1, "per_page": 20},
        )

    @pytest.mark.asyncio
    async def test_get_base_resume(self, mock_client: MockAgentClient):
        """get_base_resume calls GET /base-resumes/{id}."""
        user_id = str(uuid4())
        resume_id = str(uuid4())
        await mock_client.get_base_resume(resume_id, user_id)

        mock_client._request.assert_called_once_with(
            "GET", f"/base-resumes/{resume_id}", user_id
        )


# =============================================================================
# Job Variant Methods Tests
# =============================================================================


class TestJobVariantMethods:
    """Tests for job variant client methods."""

    @pytest.mark.asyncio
    async def test_list_job_variants(self, mock_client: MockAgentClient):
        """list_job_variants calls GET /job-variants."""
        user_id = str(uuid4())
        await mock_client.list_job_variants(user_id, status="Draft")

        mock_client._request.assert_called_once_with(
            "GET",
            "/job-variants",
            user_id,
            params={"page": 1, "per_page": 20, "status": "Draft"},
        )

    @pytest.mark.asyncio
    async def test_get_job_variant(self, mock_client: MockAgentClient):
        """get_job_variant calls GET /job-variants/{id}."""
        user_id = str(uuid4())
        variant_id = str(uuid4())
        await mock_client.get_job_variant(variant_id, user_id)

        mock_client._request.assert_called_once_with(
            "GET", f"/job-variants/{variant_id}", user_id
        )

    @pytest.mark.asyncio
    async def test_create_job_variant(self, mock_client: MockAgentClient):
        """create_job_variant calls POST /job-variants."""
        user_id = str(uuid4())
        data = {"job_posting_id": str(uuid4()), "base_resume_id": str(uuid4())}
        await mock_client.create_job_variant(user_id, data)

        mock_client._request.assert_called_once_with(
            "POST", "/job-variants", user_id, data=data
        )

    @pytest.mark.asyncio
    async def test_update_job_variant(self, mock_client: MockAgentClient):
        """update_job_variant calls PATCH /job-variants/{id}."""
        user_id = str(uuid4())
        variant_id = str(uuid4())
        data = {"status": "Approved"}
        await mock_client.update_job_variant(variant_id, user_id, data)

        mock_client._request.assert_called_once_with(
            "PATCH", f"/job-variants/{variant_id}", user_id, data=data
        )


# =============================================================================
# Cover Letter Methods Tests
# =============================================================================


class TestCoverLetterMethods:
    """Tests for cover letter client methods."""

    @pytest.mark.asyncio
    async def test_get_cover_letter(self, mock_client: MockAgentClient):
        """get_cover_letter calls GET /cover-letters/{id}."""
        user_id = str(uuid4())
        letter_id = str(uuid4())
        await mock_client.get_cover_letter(letter_id, user_id)

        mock_client._request.assert_called_once_with(
            "GET", f"/cover-letters/{letter_id}", user_id
        )

    @pytest.mark.asyncio
    async def test_create_cover_letter(self, mock_client: MockAgentClient):
        """create_cover_letter calls POST /cover-letters."""
        user_id = str(uuid4())
        data = {"job_variant_id": str(uuid4()), "content": "Dear Hiring Manager..."}
        await mock_client.create_cover_letter(user_id, data)

        mock_client._request.assert_called_once_with(
            "POST", "/cover-letters", user_id, data=data
        )

    @pytest.mark.asyncio
    async def test_update_cover_letter(self, mock_client: MockAgentClient):
        """update_cover_letter calls PATCH /cover-letters/{id}."""
        user_id = str(uuid4())
        letter_id = str(uuid4())
        data = {"status": "Approved"}
        await mock_client.update_cover_letter(letter_id, user_id, data)

        mock_client._request.assert_called_once_with(
            "PATCH", f"/cover-letters/{letter_id}", user_id, data=data
        )

    @pytest.mark.asyncio
    async def test_regenerate_cover_letter(self, mock_client: MockAgentClient):
        """regenerate_cover_letter calls POST /cover-letters/{id}/regenerate."""
        user_id = str(uuid4())
        letter_id = str(uuid4())
        await mock_client.regenerate_cover_letter(letter_id, user_id)

        mock_client._request.assert_called_once_with(
            "POST", f"/cover-letters/{letter_id}/regenerate", user_id
        )


# =============================================================================
# Persona Methods Tests
# =============================================================================


class TestPersonaMethods:
    """Tests for persona client methods."""

    @pytest.mark.asyncio
    async def test_get_persona(self, mock_client: MockAgentClient):
        """get_persona calls GET /personas/{id}."""
        user_id = str(uuid4())
        persona_id = str(uuid4())
        await mock_client.get_persona(persona_id, user_id)

        mock_client._request.assert_called_once_with(
            "GET", f"/personas/{persona_id}", user_id
        )

    @pytest.mark.asyncio
    async def test_update_persona(self, mock_client: MockAgentClient):
        """update_persona calls PATCH /personas/{id}."""
        user_id = str(uuid4())
        persona_id = str(uuid4())
        data = {"summary": "Updated summary"}
        await mock_client.update_persona(persona_id, user_id, data)

        mock_client._request.assert_called_once_with(
            "PATCH", f"/personas/{persona_id}", user_id, data=data
        )


# =============================================================================
# Persona Change Flag Methods Tests
# =============================================================================


class TestPersonaChangeFlagMethods:
    """Tests for persona change flag client methods."""

    @pytest.mark.asyncio
    async def test_list_persona_change_flags(self, mock_client: MockAgentClient):
        """list_persona_change_flags calls GET /persona-change-flags."""
        user_id = str(uuid4())
        await mock_client.list_persona_change_flags(user_id, resolved=False)

        mock_client._request.assert_called_once_with(
            "GET",
            "/persona-change-flags",
            user_id,
            params={"page": 1, "per_page": 20, "resolved": False},
        )

    @pytest.mark.asyncio
    async def test_update_persona_change_flag(self, mock_client: MockAgentClient):
        """update_persona_change_flag calls PATCH /persona-change-flags/{id}."""
        user_id = str(uuid4())
        flag_id = str(uuid4())
        data = {"resolved": True}
        await mock_client.update_persona_change_flag(flag_id, user_id, data)

        mock_client._request.assert_called_once_with(
            "PATCH", f"/persona-change-flags/{flag_id}", user_id, data=data
        )


# =============================================================================
# Refresh Methods Tests
# =============================================================================


class TestRefreshMethods:
    """Tests for refresh/trigger client methods."""

    @pytest.mark.asyncio
    async def test_trigger_refresh(self, mock_client: MockAgentClient):
        """trigger_refresh calls POST /refresh."""
        user_id = str(uuid4())
        await mock_client.trigger_refresh(user_id)

        mock_client._request.assert_called_once_with("POST", "/refresh", user_id)
