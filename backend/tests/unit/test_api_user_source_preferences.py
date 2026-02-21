"""Tests for User Source Preferences API ownership verification.

REQ-014 §5, §6: Multi-tenant ownership — returns 404 for cross-tenant access.

Tests verify:
- GET /api/v1/user-source-preferences (list with ownership filtering)
- GET /api/v1/user-source-preferences/{id} (get single with ownership)
- PATCH /api/v1/user-source-preferences/{id} (update with ownership)
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_JOB_SOURCE_ID, TEST_PERSONA_ID

_BASE_URL = "/api/v1/user-source-preferences"


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def preference_in_db(db_session: AsyncSession):
    """Create a user source preference owned by the test user."""
    from app.models.job_source import UserSourcePreference

    pref = UserSourcePreference(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        source_id=TEST_JOB_SOURCE_ID,
        is_enabled=True,
        display_order=1,
    )
    db_session.add(pref)
    await db_session.commit()
    await db_session.refresh(pref)
    return pref


@pytest_asyncio.fixture
async def other_user_preference(db_session: AsyncSession):
    """Create a preference owned by another user for cross-tenant tests."""
    from app.models import Persona, User
    from app.models.job_source import JobSource, UserSourcePreference

    other_user = User(id=uuid.uuid4(), email="other_pref@example.com")
    db_session.add(other_user)
    await db_session.flush()

    other_persona = Persona(
        id=uuid.uuid4(),
        user_id=other_user.id,
        full_name="Other Pref User",
        email="other_pref_persona@example.com",
        phone="555-8888",
        home_city="Other City",
        home_state="Other State",
        home_country="USA",
    )
    db_session.add(other_persona)
    await db_session.flush()

    other_source = JobSource(
        id=uuid.uuid4(),
        source_name="OtherTestSource",
        source_type="API",
        description="Source for cross-tenant testing",
    )
    db_session.add(other_source)
    await db_session.flush()

    pref = UserSourcePreference(
        id=uuid.uuid4(),
        persona_id=other_persona.id,
        source_id=other_source.id,
        is_enabled=False,
        display_order=5,
    )
    db_session.add(pref)
    await db_session.commit()
    await db_session.refresh(pref)
    return pref


# =============================================================================
# List Preferences
# =============================================================================


class TestListPreferences:
    """GET /api/v1/user-source-preferences — list with ownership."""

    @pytest.mark.asyncio
    async def test_list_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.get(_BASE_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_returns_user_preferences(
        self, client: AsyncClient, preference_in_db
    ) -> None:
        """Returns preferences belonging to the authenticated user."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["id"] == str(preference_in_db.id)

    @pytest.mark.asyncio
    async def test_list_empty_when_none_exist(self, client: AsyncClient) -> None:
        """Returns empty list when no preferences exist."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_excludes_other_users_preferences(
        self, client: AsyncClient, preference_in_db, other_user_preference
    ) -> None:
        """List does not include another user's preferences."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        ids = [p["id"] for p in body["data"]]
        assert str(preference_in_db.id) in ids
        assert str(other_user_preference.id) not in ids


# =============================================================================
# Get Preference
# =============================================================================


class TestGetPreference:
    """GET /api/v1/user-source-preferences/{id} — single resource."""

    @pytest.mark.asyncio
    async def test_get_requires_auth(self, unauthenticated_client: AsyncClient) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.get(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_success(self, client: AsyncClient, preference_in_db) -> None:
        """Returns preference data for owned resource."""
        response = await client.get(f"{_BASE_URL}/{preference_in_db.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == str(preference_in_db.id)
        assert body["data"]["is_enabled"] is True
        assert body["data"]["display_order"] == 1

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        response = await client.get(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_other_users_preference_returns_404(
        self, client: AsyncClient, other_user_preference
    ) -> None:
        """Cross-tenant access returns 404 (not 403) to prevent enumeration."""
        response = await client.get(f"{_BASE_URL}/{other_user_preference.id}")
        assert response.status_code == 404


# =============================================================================
# Update Preference
# =============================================================================


class TestUpdatePreference:
    """PATCH /api/v1/user-source-preferences/{id} — update with ownership."""

    @pytest.mark.asyncio
    async def test_update_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.patch(
            f"{_BASE_URL}/{uuid.uuid4()}", json={"is_enabled": False}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_is_enabled(
        self, client: AsyncClient, preference_in_db
    ) -> None:
        """Updates is_enabled field."""
        response = await client.patch(
            f"{_BASE_URL}/{preference_in_db.id}",
            json={"is_enabled": False},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["is_enabled"] is False
        assert body["data"]["display_order"] == 1  # Unchanged

    @pytest.mark.asyncio
    async def test_update_display_order(
        self, client: AsyncClient, preference_in_db
    ) -> None:
        """Updates display_order field."""
        response = await client.patch(
            f"{_BASE_URL}/{preference_in_db.id}",
            json={"display_order": 99},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["display_order"] == 99

    @pytest.mark.asyncio
    async def test_update_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        response = await client.patch(
            f"{_BASE_URL}/{uuid.uuid4()}", json={"is_enabled": False}
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_other_users_preference_returns_404(
        self, client: AsyncClient, other_user_preference
    ) -> None:
        """Cross-tenant update returns 404 (not 403)."""
        response = await client.patch(
            f"{_BASE_URL}/{other_user_preference.id}",
            json={"is_enabled": True},
        )
        assert response.status_code == 404
