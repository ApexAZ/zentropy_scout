"""Tests for Personas CRUD API endpoints with ownership verification.

REQ-014 §5.1: Pattern A — direct persona lookup with user_id filter.
REQ-014 §6.2: Personas GET/{id}, PATCH/{id}, DELETE/{id} must verify ownership.

Tests verify:
- GET /api/v1/personas (list scoped to authenticated user)
- POST /api/v1/personas (create bound to authenticated user)
- GET /api/v1/personas/{id} (ownership verified, 404 for cross-tenant)
- PATCH /api/v1/personas/{id} (ownership verified, partial update)
- DELETE /api/v1/personas/{id} (ownership verified, hard delete with CASCADE)
- Nested endpoints verify persona ownership before returning stubs
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_USER_ID

_BASE_URL = "/api/v1/personas"


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def other_user_persona(db_session: AsyncSession):
    """Create a persona belonging to a different user (cross-tenant fixture)."""
    from app.models import Persona, User

    other_user = User(id=uuid.uuid4(), email="other@example.com")
    db_session.add(other_user)
    await db_session.flush()

    other_persona = Persona(
        id=uuid.uuid4(),
        user_id=other_user.id,
        full_name="Other User",
        email="other_persona@example.com",
        phone="555-9999",
        home_city="Other City",
        home_state="Other State",
        home_country="USA",
    )
    db_session.add(other_persona)
    await db_session.commit()
    await db_session.refresh(other_persona)
    return other_persona


@pytest_asyncio.fixture
async def deletable_persona(db_session: AsyncSession):
    """Create a persona owned by the test user that can be safely deleted.

    Separate from test_persona fixture to avoid breaking other tests.
    """
    from app.models.persona import Persona

    persona = Persona(
        id=uuid.uuid4(),
        user_id=TEST_USER_ID,
        email="deletable@example.com",
        full_name="Deletable Persona",
        phone="555-0000",
        home_city="Delete City",
        home_state="Delete State",
        home_country="USA",
    )
    db_session.add(persona)
    await db_session.commit()
    await db_session.refresh(persona)
    return persona


# =============================================================================
# List Personas
# =============================================================================


class TestListPersonas:
    """GET /api/v1/personas — list scoped to authenticated user."""

    @pytest.mark.asyncio
    async def test_list_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.get(_BASE_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_returns_owned_personas(
        self, client: AsyncClient, test_persona
    ) -> None:
        """Returns personas belonging to the authenticated user."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) >= 1
        ids = [p["id"] for p in body["data"]]
        assert str(test_persona.id) in ids

    @pytest.mark.asyncio
    async def test_list_excludes_other_users_personas(
        self, client: AsyncClient, other_user_persona
    ) -> None:
        """Other users' personas do not appear in list."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        ids = [p["id"] for p in body["data"]]
        assert str(other_user_persona.id) not in ids

    @pytest.mark.asyncio
    async def test_list_includes_pagination_meta(self, client: AsyncClient) -> None:
        """Response includes pagination metadata."""
        response = await client.get(_BASE_URL)
        body = response.json()
        assert "meta" in body
        assert "total" in body["meta"]
        assert "page" in body["meta"]
        assert "per_page" in body["meta"]


# =============================================================================
# Create Persona
# =============================================================================


class TestCreatePersona:
    """POST /api/v1/personas — create bound to authenticated user."""

    @pytest.mark.asyncio
    async def test_create_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.post(_BASE_URL, json={})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_success(self, client: AsyncClient) -> None:
        """Creates a persona and returns it with 201 status."""
        payload = {
            "email": "new_persona@example.com",
            "full_name": "New Persona",
            "phone": "555-0000",
            "home_city": "New City",
            "home_state": "New State",
            "home_country": "USA",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["full_name"] == "New Persona"
        assert body["data"]["email"] == "new_persona@example.com"
        assert "id" in body["data"]

    @pytest.mark.asyncio
    async def test_create_binds_to_authenticated_user(
        self, client: AsyncClient
    ) -> None:
        """Created persona is automatically bound to the JWT user_id."""
        payload = {
            "email": "bound@example.com",
            "full_name": "Bound User",
            "phone": "555-1111",
            "home_city": "City",
            "home_state": "State",
            "home_country": "USA",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["user_id"] == str(TEST_USER_ID)

    @pytest.mark.asyncio
    async def test_create_with_optional_fields(self, client: AsyncClient) -> None:
        """Creates a persona with optional fields populated."""
        payload = {
            "email": "full@example.com",
            "full_name": "Full Persona",
            "phone": "555-2222",
            "home_city": "Full City",
            "home_state": "Full State",
            "home_country": "USA",
            "linkedin_url": "https://linkedin.com/in/test",
            "professional_summary": "Experienced engineer.",
            "years_experience": 10,
            "current_role": "Senior Engineer",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["linkedin_url"] == "https://linkedin.com/in/test"
        assert body["data"]["years_experience"] == 10

    @pytest.mark.asyncio
    async def test_create_missing_required_fields(self, client: AsyncClient) -> None:
        """Missing required fields returns 400."""
        response = await client.post(_BASE_URL, json={"full_name": "Incomplete"})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_duplicate_email_returns_409(
        self, client: AsyncClient, test_persona
    ) -> None:
        """Duplicate persona email returns 409."""
        payload = {
            "email": test_persona.email,
            "full_name": "Duplicate Email",
            "phone": "555-3333",
            "home_city": "Dup City",
            "home_state": "Dup State",
            "home_country": "USA",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_create_rejects_extra_fields(self, client: AsyncClient) -> None:
        """Extra fields (e.g. user_id) are rejected by extra='forbid'."""
        payload = {
            "email": "extra@example.com",
            "full_name": "Extra Fields",
            "phone": "555-4444",
            "home_city": "City",
            "home_state": "State",
            "home_country": "USA",
            "user_id": str(uuid.uuid4()),
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 400


# =============================================================================
# Get Persona
# =============================================================================


class TestGetPersona:
    """GET /api/v1/personas/{id} — ownership verified."""

    @pytest.mark.asyncio
    async def test_get_requires_auth(self, unauthenticated_client: AsyncClient) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.get(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_owned_persona(self, client: AsyncClient, test_persona) -> None:
        """Returns persona data for owned resource."""
        response = await client.get(f"{_BASE_URL}/{test_persona.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == str(test_persona.id)
        assert body["data"]["full_name"] == "Test User"

    @pytest.mark.asyncio
    async def test_get_other_users_persona_returns_404(
        self, client: AsyncClient, other_user_persona
    ) -> None:
        """Cross-tenant access returns 404 (not 403) to prevent enumeration."""
        response = await client.get(f"{_BASE_URL}/{other_user_persona.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        response = await client.get(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 404


# =============================================================================
# Update Persona
# =============================================================================


class TestUpdatePersona:
    """PATCH /api/v1/personas/{id} — ownership verified, partial update."""

    @pytest.mark.asyncio
    async def test_update_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.patch(
            f"{_BASE_URL}/{uuid.uuid4()}", json={"full_name": "Updated"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_full_name(self, client: AsyncClient, test_persona) -> None:
        """Updates full_name field only, other fields unchanged."""
        response = await client.patch(
            f"{_BASE_URL}/{test_persona.id}",
            json={"full_name": "Updated Name"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["full_name"] == "Updated Name"
        # Other fields unchanged
        assert body["data"]["home_city"] == "Test City"

    @pytest.mark.asyncio
    async def test_update_multiple_fields(
        self, client: AsyncClient, test_persona
    ) -> None:
        """Updates multiple fields in a single PATCH."""
        response = await client.patch(
            f"{_BASE_URL}/{test_persona.id}",
            json={
                "current_role": "Staff Engineer",
                "years_experience": 15,
                "remote_preference": "Remote Only",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["current_role"] == "Staff Engineer"
        assert body["data"]["years_experience"] == 15
        assert body["data"]["remote_preference"] == "Remote Only"

    @pytest.mark.asyncio
    async def test_update_other_users_persona_returns_404(
        self, client: AsyncClient, other_user_persona
    ) -> None:
        """Cross-tenant update returns 404 (not 403)."""
        response = await client.patch(
            f"{_BASE_URL}/{other_user_persona.id}",
            json={"full_name": "Hacked"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_404(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        response = await client.patch(
            f"{_BASE_URL}/{uuid.uuid4()}", json={"full_name": "Ghost"}
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_email_to_duplicate_returns_409(
        self, client: AsyncClient, test_persona, db_session
    ) -> None:
        """Updating email to a duplicate returns 409."""
        from app.models.persona import Persona

        # Create a second persona owned by the test user
        second = Persona(
            id=uuid.uuid4(),
            user_id=TEST_USER_ID,
            email="second_persona@example.com",
            full_name="Second Persona",
            phone="555-7777",
            home_city="City",
            home_state="State",
            home_country="USA",
        )
        db_session.add(second)
        await db_session.commit()
        await db_session.refresh(second)

        # Try to update second persona's email to match test_persona's email
        response = await client.patch(
            f"{_BASE_URL}/{second.id}",
            json={"email": test_persona.email},
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_update_rejects_extra_fields(
        self, client: AsyncClient, test_persona
    ) -> None:
        """Extra fields (e.g. user_id) are rejected by extra='forbid'."""
        response = await client.patch(
            f"{_BASE_URL}/{test_persona.id}",
            json={"user_id": str(uuid.uuid4())},
        )
        assert response.status_code == 400


# =============================================================================
# Delete Persona
# =============================================================================


class TestDeletePersona:
    """DELETE /api/v1/personas/{id} — ownership verified, hard delete."""

    @pytest.mark.asyncio
    async def test_delete_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.delete(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_owned_persona(
        self, client: AsyncClient, deletable_persona
    ) -> None:
        """DELETE returns 204 and removes the persona."""
        response = await client.delete(f"{_BASE_URL}/{deletable_persona.id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = await client.get(f"{_BASE_URL}/{deletable_persona.id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_other_users_persona_returns_404(
        self, client: AsyncClient, other_user_persona
    ) -> None:
        """Cross-tenant delete returns 404 (not 403)."""
        response = await client.delete(f"{_BASE_URL}/{other_user_persona.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        response = await client.delete(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 404


# =============================================================================
# Nested Endpoint Ownership Verification
# =============================================================================


class TestNestedEndpointOwnership:
    """Nested persona sub-resource stubs verify persona ownership.

    REQ-014 §5: Even stub endpoints must block cross-tenant access.
    """

    @pytest.mark.asyncio
    async def test_nested_list_with_unowned_persona_returns_404(
        self, client: AsyncClient, other_user_persona
    ) -> None:
        """Nested list endpoints return 404 for unowned persona."""
        nested_paths = [
            f"{_BASE_URL}/{other_user_persona.id}/work-history",
            f"{_BASE_URL}/{other_user_persona.id}/skills",
            f"{_BASE_URL}/{other_user_persona.id}/education",
            f"{_BASE_URL}/{other_user_persona.id}/certifications",
            f"{_BASE_URL}/{other_user_persona.id}/achievement-stories",
            f"{_BASE_URL}/{other_user_persona.id}/voice-profile",
            f"{_BASE_URL}/{other_user_persona.id}/custom-non-negotiables",
        ]
        for path in nested_paths:
            response = await client.get(path)
            assert response.status_code == 404, (
                f"Expected 404 for {path}, got {response.status_code}"
            )

    @pytest.mark.asyncio
    async def test_nested_list_with_owned_persona_returns_200(
        self, client: AsyncClient, test_persona
    ) -> None:
        """Nested list endpoints return 200 for owned persona."""
        nested_paths = [
            f"{_BASE_URL}/{test_persona.id}/work-history",
            f"{_BASE_URL}/{test_persona.id}/skills",
            f"{_BASE_URL}/{test_persona.id}/education",
            f"{_BASE_URL}/{test_persona.id}/certifications",
            f"{_BASE_URL}/{test_persona.id}/achievement-stories",
            f"{_BASE_URL}/{test_persona.id}/voice-profile",
            f"{_BASE_URL}/{test_persona.id}/custom-non-negotiables",
        ]
        for path in nested_paths:
            response = await client.get(path)
            assert response.status_code == 200, (
                f"Expected 200 for {path}, got {response.status_code}"
            )

    @pytest.mark.asyncio
    async def test_nested_post_with_unowned_persona_returns_404(
        self, client: AsyncClient, other_user_persona
    ) -> None:
        """Nested POST (create) endpoints return 404 for unowned persona."""
        nested_paths = [
            f"{_BASE_URL}/{other_user_persona.id}/work-history",
            f"{_BASE_URL}/{other_user_persona.id}/skills",
            f"{_BASE_URL}/{other_user_persona.id}/education",
            f"{_BASE_URL}/{other_user_persona.id}/certifications",
            f"{_BASE_URL}/{other_user_persona.id}/achievement-stories",
            f"{_BASE_URL}/{other_user_persona.id}/custom-non-negotiables",
        ]
        for path in nested_paths:
            response = await client.post(path)
            assert response.status_code == 404, (
                f"Expected 404 for POST {path}, got {response.status_code}"
            )

    @pytest.mark.asyncio
    async def test_nested_delete_with_unowned_persona_returns_404(
        self, client: AsyncClient, other_user_persona
    ) -> None:
        """Nested DELETE endpoints return 404 for unowned persona."""
        fake_id = uuid.uuid4()
        nested_paths = [
            f"{_BASE_URL}/{other_user_persona.id}/work-history/{fake_id}",
            f"{_BASE_URL}/{other_user_persona.id}/skills/{fake_id}",
            f"{_BASE_URL}/{other_user_persona.id}/education/{fake_id}",
            f"{_BASE_URL}/{other_user_persona.id}/certifications/{fake_id}",
            f"{_BASE_URL}/{other_user_persona.id}/achievement-stories/{fake_id}",
            f"{_BASE_URL}/{other_user_persona.id}/custom-non-negotiables/{fake_id}",
        ]
        for path in nested_paths:
            response = await client.delete(path)
            assert response.status_code == 404, (
                f"Expected 404 for DELETE {path}, got {response.status_code}"
            )

    @pytest.mark.asyncio
    async def test_embeddings_regenerate_with_unowned_persona_returns_404(
        self, client: AsyncClient, other_user_persona
    ) -> None:
        """POST embeddings/regenerate returns 404 for unowned persona."""
        response = await client.post(
            f"{_BASE_URL}/{other_user_persona.id}/embeddings/regenerate"
        )
        assert response.status_code == 404
