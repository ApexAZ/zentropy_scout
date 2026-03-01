"""Tests for Persona Change Flags API endpoints.

REQ-006 §5.4: HITL sync for persona changes.

These tests verify:
- GET /api/v1/persona-change-flags (list with status filtering)
- GET /api/v1/persona-change-flags/{id} (get single flag)
- PATCH /api/v1/persona-change-flags/{id} (resolve a flag)
"""

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_USER_ID

# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def persona_for_flags(db_session: AsyncSession):
    """Create a persona for change flag tests."""
    from app.models import Persona

    persona = Persona(
        id=uuid.uuid4(),
        user_id=TEST_USER_ID,
        full_name="Test User",
        email="flagtestpersona@example.com",
        phone="555-555-5555",
        home_city="San Francisco",
        home_state="California",
        home_country="USA",
    )
    db_session.add(persona)
    await db_session.commit()
    await db_session.refresh(persona)
    return persona


@pytest_asyncio.fixture
async def pending_change_flag(db_session: AsyncSession, persona_for_flags):
    """Create a pending change flag."""
    from app.models import PersonaChangeFlag

    flag = PersonaChangeFlag(
        id=uuid.uuid4(),
        persona_id=persona_for_flags.id,
        change_type="skill_added",
        item_id=uuid.uuid4(),
        item_description="Added skill: Kubernetes",
        status="Pending",
    )
    db_session.add(flag)
    await db_session.commit()
    await db_session.refresh(flag)
    return flag


@pytest_asyncio.fixture
async def resolved_change_flag(db_session: AsyncSession, persona_for_flags):
    """Create a resolved change flag."""
    from app.models import PersonaChangeFlag

    flag = PersonaChangeFlag(
        id=uuid.uuid4(),
        persona_id=persona_for_flags.id,
        change_type="job_added",
        item_id=uuid.uuid4(),
        item_description="Added work history: Senior Engineer at Acme",
        status="Resolved",
        resolution="added_to_all",
        resolved_at=datetime.now(UTC),
    )
    db_session.add(flag)
    await db_session.commit()
    await db_session.refresh(flag)
    return flag


@pytest_asyncio.fixture
async def other_user_flag(db_session: AsyncSession):
    """Create a change flag belonging to a different user."""
    from app.models import Persona, PersonaChangeFlag, User

    # Create different user
    other_user = User(
        id=uuid.uuid4(),
        email="otheruser@example.com",
    )
    db_session.add(other_user)
    await db_session.flush()

    # Create persona for other user
    other_persona = Persona(
        id=uuid.uuid4(),
        user_id=other_user.id,
        full_name="Other User",
        email="otherpersona@example.com",
        phone="555-555-5556",
        home_city="New York",
        home_state="New York",
        home_country="USA",
    )
    db_session.add(other_persona)
    await db_session.flush()

    # Create flag for other user's persona
    flag = PersonaChangeFlag(
        id=uuid.uuid4(),
        persona_id=other_persona.id,
        change_type="skill_added",
        item_id=uuid.uuid4(),
        item_description="Other user's skill",
        status="Pending",
    )
    db_session.add(flag)
    await db_session.commit()
    await db_session.refresh(flag)
    return flag


# =============================================================================
# List Tests - GET /api/v1/persona-change-flags
# =============================================================================


class TestListPersonaChangeFlags:
    """Tests for GET /api/v1/persona-change-flags."""

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, unauthenticated_client: AsyncClient):
        """List should return 401 without authentication."""
        response = await unauthenticated_client.get("/api/v1/persona-change-flags")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_returns_user_flags(
        self,
        client: AsyncClient,
        pending_change_flag,
    ):
        """List returns flags for current user's persona only."""
        response = await client.get("/api/v1/persona-change-flags")

        assert response.status_code == 200
        result = response.json()
        assert "data" in result
        assert len(result["data"]) == 1
        assert result["data"][0]["id"] == str(pending_change_flag.id)
        assert result["data"][0]["change_type"] == "skill_added"
        assert result["data"][0]["item_description"] == "Added skill: Kubernetes"
        assert result["data"][0]["status"] == "Pending"

    @pytest.mark.asyncio
    async def test_list_excludes_other_user_flags(
        self,
        client: AsyncClient,
        other_user_flag,  # noqa: ARG002
    ):
        """List should not return flags from other users."""
        response = await client.get("/api/v1/persona-change-flags")

        assert response.status_code == 200
        result = response.json()
        # Should be empty since we only created other user's flag
        assert result["data"] == []

    @pytest.mark.asyncio
    async def test_list_filter_by_status_pending(
        self,
        client: AsyncClient,
        pending_change_flag,
        resolved_change_flag,  # noqa: ARG002
    ):
        """List with status=Pending returns only pending flags."""
        response = await client.get("/api/v1/persona-change-flags?status=Pending")

        assert response.status_code == 200
        result = response.json()
        assert len(result["data"]) == 1
        assert result["data"][0]["id"] == str(pending_change_flag.id)
        assert result["data"][0]["status"] == "Pending"

    @pytest.mark.asyncio
    async def test_list_filter_by_status_resolved(
        self,
        client: AsyncClient,
        pending_change_flag,  # noqa: ARG002
        resolved_change_flag,
    ):
        """List with status=Resolved returns only resolved flags."""
        response = await client.get("/api/v1/persona-change-flags?status=Resolved")

        assert response.status_code == 200
        result = response.json()
        assert len(result["data"]) == 1
        assert result["data"][0]["id"] == str(resolved_change_flag.id)
        assert result["data"][0]["status"] == "Resolved"

    @pytest.mark.asyncio
    async def test_list_returns_empty_when_no_flags(
        self,
        client: AsyncClient,
    ):
        """List returns empty array when no flags exist."""
        response = await client.get("/api/v1/persona-change-flags")

        assert response.status_code == 200
        result = response.json()
        assert result["data"] == []
        assert result["meta"]["total"] == 0


# =============================================================================
# Get Tests - GET /api/v1/persona-change-flags/{id}
# =============================================================================


class TestGetPersonaChangeFlag:
    """Tests for GET /api/v1/persona-change-flags/{id}."""

    @pytest.mark.asyncio
    async def test_get_requires_auth(self, unauthenticated_client: AsyncClient):
        """Get should return 401 without authentication."""
        flag_id = uuid.uuid4()
        response = await unauthenticated_client.get(
            f"/api/v1/persona-change-flags/{flag_id}"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_success(
        self,
        client: AsyncClient,
        pending_change_flag,
    ):
        """Get returns flag details."""
        response = await client.get(
            f"/api/v1/persona-change-flags/{pending_change_flag.id}"
        )

        assert response.status_code == 200
        result = response.json()
        assert result["data"]["id"] == str(pending_change_flag.id)
        assert result["data"]["change_type"] == "skill_added"
        assert result["data"]["item_description"] == "Added skill: Kubernetes"
        assert result["data"]["status"] == "Pending"
        assert "created_at" in result["data"]

    @pytest.mark.asyncio
    async def test_get_not_found(
        self,
        client: AsyncClient,
    ):
        """Get non-existent flag returns 404."""
        flag_id = uuid.uuid4()
        response = await client.get(f"/api/v1/persona-change-flags/{flag_id}")

        assert response.status_code == 404
        result = response.json()
        assert result["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_other_user_flag_returns_404(
        self,
        client: AsyncClient,
        other_user_flag,
    ):
        """Get flag belonging to another user returns 404 (not 403)."""
        # Return 404 instead of 403 to avoid revealing existence
        response = await client.get(
            f"/api/v1/persona-change-flags/{other_user_flag.id}"
        )

        assert response.status_code == 404


# =============================================================================
# Patch Tests - PATCH /api/v1/persona-change-flags/{id}
# =============================================================================


class TestPatchPersonaChangeFlag:
    """Tests for PATCH /api/v1/persona-change-flags/{id}."""

    @pytest.mark.asyncio
    async def test_patch_requires_auth(self, unauthenticated_client: AsyncClient):
        """Patch should return 401 without authentication."""
        flag_id = uuid.uuid4()
        response = await unauthenticated_client.patch(
            f"/api/v1/persona-change-flags/{flag_id}",
            json={"status": "Resolved", "resolution": "added_to_all"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_resolve_flag_added_to_all(
        self,
        client: AsyncClient,
        pending_change_flag,
    ):
        """Resolve flag with added_to_all resolution."""
        response = await client.patch(
            f"/api/v1/persona-change-flags/{pending_change_flag.id}",
            json={"status": "Resolved", "resolution": "added_to_all"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["data"]["status"] == "Resolved"
        assert result["data"]["resolution"] == "added_to_all"
        assert result["data"]["resolved_at"] is not None

    @pytest.mark.asyncio
    async def test_resolve_flag_added_to_some(
        self,
        client: AsyncClient,
        pending_change_flag,
    ):
        """Resolve flag with added_to_some resolution."""
        response = await client.patch(
            f"/api/v1/persona-change-flags/{pending_change_flag.id}",
            json={"status": "Resolved", "resolution": "added_to_some"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["data"]["status"] == "Resolved"
        assert result["data"]["resolution"] == "added_to_some"

    @pytest.mark.asyncio
    async def test_resolve_flag_skipped(
        self,
        client: AsyncClient,
        pending_change_flag,
    ):
        """Resolve flag with skipped resolution."""
        response = await client.patch(
            f"/api/v1/persona-change-flags/{pending_change_flag.id}",
            json={"status": "Resolved", "resolution": "skipped"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["data"]["status"] == "Resolved"
        assert result["data"]["resolution"] == "skipped"

    @pytest.mark.asyncio
    async def test_patch_not_found(
        self,
        client: AsyncClient,
    ):
        """Patch non-existent flag returns 404."""
        flag_id = uuid.uuid4()
        response = await client.patch(
            f"/api/v1/persona-change-flags/{flag_id}",
            json={"status": "Resolved", "resolution": "skipped"},
        )

        assert response.status_code == 404
        result = response.json()
        assert result["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_patch_other_user_flag_returns_404(
        self,
        client: AsyncClient,
        other_user_flag,
    ):
        """Patch flag belonging to another user returns 404."""
        response = await client.patch(
            f"/api/v1/persona-change-flags/{other_user_flag.id}",
            json={"status": "Resolved", "resolution": "added_to_all"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_invalid_resolution(
        self,
        client: AsyncClient,
        pending_change_flag,
    ):
        """Patch with invalid resolution value returns 400."""
        response = await client.patch(
            f"/api/v1/persona-change-flags/{pending_change_flag.id}",
            json={"status": "Resolved", "resolution": "invalid_value"},
        )

        # Project custom config returns 400 for validation errors
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_patch_already_resolved_returns_422(
        self,
        client: AsyncClient,
        resolved_change_flag,
    ):
        """Patch already resolved flag returns 422 INVALID_STATE_TRANSITION."""
        response = await client.patch(
            f"/api/v1/persona-change-flags/{resolved_change_flag.id}",
            json={"status": "Resolved", "resolution": "skipped"},
        )

        assert response.status_code == 422
        result = response.json()
        assert result["error"]["code"] == "INVALID_STATE_TRANSITION"

    @pytest.mark.asyncio
    async def test_patch_missing_resolution_when_resolving(
        self,
        client: AsyncClient,
        pending_change_flag,
    ):
        """Patch to Resolved without resolution returns 400."""
        response = await client.patch(
            f"/api/v1/persona-change-flags/{pending_change_flag.id}",
            json={"status": "Resolved"},  # Missing resolution
        )

        # Project custom config returns 400 for validation errors
        assert response.status_code == 400
