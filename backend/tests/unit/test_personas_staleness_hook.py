"""Integration tests for the persona PATCH staleness hook.

REQ-034 §4.4: Verifies that PATCH /personas/{id} marks the SearchProfile as
stale when a material field is updated, and leaves it unchanged when only
non-material fields are updated.

Tests use the real ASGI + db_session stack (same test infrastructure as
test_api_personas_crud.py) so that the full commit/flush cycle is exercised.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.search_profile_repository import SearchProfileRepository
from app.schemas.search_profile import SearchProfileCreate
from tests.conftest import TEST_PERSONA_ID

_BASE_URL = "/api/v1/personas"

_FINGERPRINT = "a" * 64
"""Known-good fingerprint used in test profiles (content immaterial — 64 hex chars)."""


# =============================================================================
# Helpers
# =============================================================================


async def _create_search_profile(db_session: AsyncSession) -> None:
    """Insert a SearchProfile (is_stale=False) for the test persona.

    Uses the repository's create() which flushes immediately, making the row
    visible to subsequent queries within the same session.

    Args:
        db_session: Shared test session (same one injected into the API handler).
    """
    await SearchProfileRepository.create(
        db_session,
        SearchProfileCreate(
            persona_id=TEST_PERSONA_ID,
            fit_searches=[],
            stretch_searches=[],
            persona_fingerprint=_FINGERPRINT,
            is_stale=False,
        ),
    )


# =============================================================================
# Staleness hook
# =============================================================================


class TestPersonaStalenessHook:
    """REQ-034 §4.4: Staleness hook fires on PATCH /personas/{id}."""

    @pytest.mark.asyncio
    async def test_material_field_patch_marks_profile_stale(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_persona,  # noqa: ANN001
    ) -> None:
        """PATCH a material field (target_roles) → SearchProfile.is_stale becomes True."""
        await _create_search_profile(db_session)

        response = await client.patch(
            f"{_BASE_URL}/{test_persona.id}",
            json={"target_roles": ["Staff Engineer"]},
        )
        assert response.status_code == 200

        profile = await SearchProfileRepository.get_by_persona_id(
            db_session, TEST_PERSONA_ID
        )
        assert profile is not None
        assert profile.is_stale is True

    @pytest.mark.asyncio
    async def test_non_material_field_patch_leaves_profile_fresh(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_persona,  # noqa: ANN001
    ) -> None:
        """PATCH a non-material field (professional_summary) → is_stale unchanged."""
        await _create_search_profile(db_session)

        response = await client.patch(
            f"{_BASE_URL}/{test_persona.id}",
            json={"professional_summary": "Updated summary text."},
        )
        assert response.status_code == 200

        profile = await SearchProfileRepository.get_by_persona_id(
            db_session, TEST_PERSONA_ID
        )
        assert profile is not None
        assert profile.is_stale is False

    @pytest.mark.asyncio
    async def test_material_field_patch_without_profile_succeeds(
        self,
        client: AsyncClient,
        test_persona,  # noqa: ANN001
    ) -> None:
        """PATCH a material field when no SearchProfile exists → 200, no error."""
        response = await client.patch(
            f"{_BASE_URL}/{test_persona.id}",
            json={"target_skills": ["Kubernetes", "Terraform"]},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_stretch_appetite_patch_marks_profile_stale(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_persona,  # noqa: ANN001
    ) -> None:
        """PATCH stretch_appetite (another material field) → is_stale becomes True."""
        await _create_search_profile(db_session)

        response = await client.patch(
            f"{_BASE_URL}/{test_persona.id}",
            json={"stretch_appetite": "High"},
        )
        assert response.status_code == 200

        profile = await SearchProfileRepository.get_by_persona_id(
            db_session, TEST_PERSONA_ID
        )
        assert profile is not None
        assert profile.is_stale is True

    @pytest.mark.asyncio
    async def test_remote_preference_patch_marks_profile_stale(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_persona,  # noqa: ANN001
    ) -> None:
        """PATCH remote_preference → is_stale becomes True."""
        await _create_search_profile(db_session)

        response = await client.patch(
            f"{_BASE_URL}/{test_persona.id}",
            json={"remote_preference": "Remote Only"},
        )
        assert response.status_code == 200

        profile = await SearchProfileRepository.get_by_persona_id(
            db_session, TEST_PERSONA_ID
        )
        assert profile is not None
        assert profile.is_stale is True

    @pytest.mark.asyncio
    async def test_home_city_patch_marks_profile_stale(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_persona,  # noqa: ANN001
    ) -> None:
        """PATCH home_city (location_preferences group) → is_stale becomes True."""
        await _create_search_profile(db_session)

        response = await client.patch(
            f"{_BASE_URL}/{test_persona.id}",
            json={"home_city": "Chicago"},
        )
        assert response.status_code == 200

        profile = await SearchProfileRepository.get_by_persona_id(
            db_session, TEST_PERSONA_ID
        )
        assert profile is not None
        assert profile.is_stale is True

    @pytest.mark.asyncio
    async def test_mixed_material_and_non_material_fields_marks_profile_stale(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_persona,  # noqa: ANN001
    ) -> None:
        """PATCH mixing material + non-material fields → is_stale becomes True."""
        await _create_search_profile(db_session)

        response = await client.patch(
            f"{_BASE_URL}/{test_persona.id}",
            json={
                "professional_summary": "Updated summary.",
                "target_roles": ["Principal Engineer"],
            },
        )
        assert response.status_code == 200

        profile = await SearchProfileRepository.get_by_persona_id(
            db_session, TEST_PERSONA_ID
        )
        assert profile is not None
        assert profile.is_stale is True
