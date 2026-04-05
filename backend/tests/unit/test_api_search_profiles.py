"""Tests for SearchProfile API endpoints.

REQ-034 §4.5: Verifies GET /search-profiles/{persona_id},
POST /search-profiles/{persona_id}/generate, and
PATCH /search-profiles/{persona_id}.

Tests use the real ASGI + db_session stack (same infrastructure as
test_api_personas_crud.py) so that the full commit/flush cycle is exercised.
The mock_llm fixture is used for the generate endpoint to avoid hitting real
LLM APIs. test_persona is a dependency of the client fixture and does not
need to be declared separately in each test method.
"""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.llm.base import TaskType
from app.repositories.search_profile_repository import SearchProfileRepository
from app.schemas.search_profile import SearchProfileCreate
from app.services.discovery.search_profile_service import SearchProfileGenerationError
from tests.conftest import TEST_PERSONA_ID

_BASE_URL = "/api/v1/search-profiles"

_FINGERPRINT = "c" * 64
"""Known-good 64-char fingerprint for test profiles (content immaterial)."""

_VALID_BUCKET_DICT = {
    "label": "Senior Engineer",
    "keywords": ["python", "backend"],
    "titles": ["Senior Software Engineer"],
    "remoteok_tags": ["python"],
    "location": None,
}
"""Minimal valid SearchBucket dict used in generate mock responses."""

_VALID_GENERATE_JSON = json.dumps(
    {
        "fit_searches": [_VALID_BUCKET_DICT],
        "stretch_searches": [],
    }
)
"""Valid JSON string returned by the mock LLM for SEARCH_PROFILE_GENERATION."""


# =============================================================================
# Helpers
# =============================================================================


async def _create_profile(
    db_session: AsyncSession,
    *,
    is_stale: bool = False,
) -> None:
    """Insert a SearchProfile for the test persona.

    Args:
        db_session: Shared test session.
        is_stale: Whether the profile should start as stale.
    """
    await SearchProfileRepository.create(
        db_session,
        SearchProfileCreate(
            persona_id=TEST_PERSONA_ID,
            fit_searches=[],
            stretch_searches=[],
            persona_fingerprint=_FINGERPRINT,
            is_stale=is_stale,
        ),
    )


# =============================================================================
# GET /search-profiles/{persona_id}
# =============================================================================


class TestGetSearchProfile:
    """REQ-034 §4.5: GET /search-profiles/{persona_id}."""

    @pytest.mark.asyncio
    async def test_get_search_profile_returns_existing_profile(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """GET returns 200 with profile data when a SearchProfile exists."""
        await _create_profile(db_session)

        response = await client.get(f"{_BASE_URL}/{TEST_PERSONA_ID}")
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["persona_id"] == str(TEST_PERSONA_ID)
        assert data["is_stale"] is False
        assert data["fit_searches"] == []
        assert data["stretch_searches"] == []

    @pytest.mark.asyncio
    async def test_get_search_profile_returns_404_when_no_profile(
        self,
        client: AsyncClient,
    ) -> None:
        """GET returns 404 when the persona has no SearchProfile."""
        response = await client.get(f"{_BASE_URL}/{TEST_PERSONA_ID}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_search_profile_returns_404_for_unknown_persona(
        self,
        client: AsyncClient,
    ) -> None:
        """GET returns 404 when persona_id does not belong to the authenticated user."""
        unknown_persona_id = uuid.uuid4()
        response = await client.get(f"{_BASE_URL}/{unknown_persona_id}")
        assert response.status_code == 404


# =============================================================================
# POST /search-profiles/{persona_id}/generate
# =============================================================================


class TestGenerateSearchProfile:
    """REQ-034 §4.3, §4.5: POST /search-profiles/{persona_id}/generate."""

    @pytest.mark.asyncio
    async def test_generate_profile_creates_new_profile(
        self,
        client: AsyncClient,
        mock_llm,  # noqa: ANN001
    ) -> None:
        """POST /generate returns 200 and creates a new SearchProfile via LLM."""
        mock_llm.set_response(TaskType.SEARCH_PROFILE_GENERATION, _VALID_GENERATE_JSON)

        response = await client.post(f"{_BASE_URL}/{TEST_PERSONA_ID}/generate")
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["persona_id"] == str(TEST_PERSONA_ID)
        assert data["is_stale"] is False
        assert len(data["fit_searches"]) == 1
        assert data["fit_searches"][0]["label"] == "Senior Engineer"

    @pytest.mark.asyncio
    async def test_generate_profile_updates_existing_stale_profile(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        mock_llm,  # noqa: ANN001
    ) -> None:
        """POST /generate overwrites an existing stale profile and returns 200."""
        await _create_profile(db_session, is_stale=True)
        mock_llm.set_response(TaskType.SEARCH_PROFILE_GENERATION, _VALID_GENERATE_JSON)

        response = await client.post(f"{_BASE_URL}/{TEST_PERSONA_ID}/generate")
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["is_stale"] is False
        assert len(data["fit_searches"]) == 1

    @pytest.mark.asyncio
    async def test_generate_profile_returns_502_on_llm_failure(
        self,
        client: AsyncClient,
    ) -> None:
        """POST /generate returns 502 when the LLM call fails."""
        with patch(
            "app.api.v1.search_profiles.generate_profile",
            new=AsyncMock(side_effect=SearchProfileGenerationError("LLM call failed")),
        ):
            response = await client.post(f"{_BASE_URL}/{TEST_PERSONA_ID}/generate")

        assert response.status_code == 502
        assert response.json()["error"]["code"] == "SEARCH_PROFILE_GENERATION_ERROR"

    @pytest.mark.asyncio
    async def test_generate_profile_returns_404_for_unknown_persona(
        self,
        client: AsyncClient,
    ) -> None:
        """POST /generate returns 404 when persona_id is not owned by user."""
        unknown_persona_id = uuid.uuid4()
        response = await client.post(f"{_BASE_URL}/{unknown_persona_id}/generate")
        assert response.status_code == 404


# =============================================================================
# PATCH /search-profiles/{persona_id}
# =============================================================================


class TestPatchSearchProfile:
    """REQ-034 §4.5: PATCH /search-profiles/{persona_id}."""

    @pytest.mark.asyncio
    async def test_patch_search_profile_updates_fit_searches(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """PATCH with fit_searches replacement returns 200 with updated data."""
        await _create_profile(db_session)

        response = await client.patch(
            f"{_BASE_URL}/{TEST_PERSONA_ID}",
            json={
                "fit_searches": [_VALID_BUCKET_DICT],
            },
        )
        assert response.status_code == 200

        data = response.json()["data"]
        assert len(data["fit_searches"]) == 1
        assert data["fit_searches"][0]["label"] == "Senior Engineer"
        # Verify unspecified fields are left unchanged (REQ-034 §4.5).
        assert data["stretch_searches"] == []

    @pytest.mark.asyncio
    async def test_patch_search_profile_sets_approved_at(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """PATCH with approved_at sets the approval timestamp and returns 200."""
        await _create_profile(db_session)

        response = await client.patch(
            f"{_BASE_URL}/{TEST_PERSONA_ID}",
            json={"approved_at": "2026-04-05T12:00:00Z"},
        )
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["approved_at"] is not None
        assert "2026-04-05" in data["approved_at"]

    @pytest.mark.asyncio
    async def test_patch_search_profile_returns_404_when_no_profile(
        self,
        client: AsyncClient,
    ) -> None:
        """PATCH returns 404 when the persona has no SearchProfile."""
        response = await client.patch(
            f"{_BASE_URL}/{TEST_PERSONA_ID}",
            json={"fit_searches": []},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_search_profile_returns_404_for_unknown_persona(
        self,
        client: AsyncClient,
    ) -> None:
        """PATCH returns 404 when persona_id is not owned by the authenticated user."""
        unknown_persona_id = uuid.uuid4()
        response = await client.patch(
            f"{_BASE_URL}/{unknown_persona_id}",
            json={"fit_searches": []},
        )
        assert response.status_code == 404
