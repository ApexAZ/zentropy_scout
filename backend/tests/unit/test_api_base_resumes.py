"""Tests for Base Resumes CRUD API endpoints.

REQ-006 §5.2: Base resumes filtered by current user's persona.
REQ-002 §4.2: Base Resume — Rendered Document Storage.
REQ-002 §5.4: User Actions — Archive/Restore.

Tests verify:
- GET /api/v1/base-resumes (list with ownership filtering)
- POST /api/v1/base-resumes (create with validation)
- GET /api/v1/base-resumes/{id} (get single, excludes rendered_document)
- PATCH /api/v1/base-resumes/{id} (partial update)
- DELETE /api/v1/base-resumes/{id} (soft archive)
- POST /api/v1/base-resumes/{id}/restore (restore from archive)
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_PERSONA_ID

_BASE_URL = "/api/v1/base-resumes"


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def base_resume_in_db(db_session: AsyncSession):
    """Create a base resume for test queries."""
    from app.models.resume import BaseResume

    resume = BaseResume(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        name="Scrum Master Resume",
        role_type="Scrum Master",
        summary="Experienced agile practitioner with 10 years of delivery.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume


@pytest_asyncio.fixture
async def base_resume_with_pdf(db_session: AsyncSession):
    """Create a base resume that has a rendered document."""
    from app.models.resume import BaseResume

    resume = BaseResume(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        name="Product Owner Resume",
        role_type="Product Owner",
        summary="Product strategist with customer-centric delivery focus.",
        rendered_document=b"%PDF-1.4 test content",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume


# =============================================================================
# List Base Resumes
# =============================================================================


class TestListBaseResumes:
    """GET /api/v1/base-resumes — list with ownership filtering."""

    @pytest.mark.asyncio
    async def test_list_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.get(_BASE_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_returns_user_resumes(
        self, client: AsyncClient, base_resume_in_db
    ) -> None:
        """Returns base resumes belonging to the authenticated user."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 1
        ids = [r["id"] for r in body["data"]]
        assert str(base_resume_in_db.id) in ids

    @pytest.mark.asyncio
    async def test_list_empty_when_none_exist(self, client: AsyncClient) -> None:
        """Returns empty list when no base resumes exist."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_includes_pagination_meta(
        self,
        client: AsyncClient,
        base_resume_in_db,  # noqa: ARG002
    ) -> None:
        """Response includes pagination metadata."""
        response = await client.get(_BASE_URL)
        body = response.json()
        assert "meta" in body
        assert "total" in body["meta"]
        assert "page" in body["meta"]
        assert "per_page" in body["meta"]

    @pytest.mark.asyncio
    async def test_list_excludes_rendered_document(
        self, client: AsyncClient, base_resume_with_pdf
    ) -> None:
        """List response does not include rendered_document binary."""
        response = await client.get(_BASE_URL)
        body = response.json()
        matching = [r for r in body["data"] if r["id"] == str(base_resume_with_pdf.id)]
        assert len(matching) == 1
        assert "rendered_document" not in matching[0]


# =============================================================================
# Create Base Resume
# =============================================================================


class TestCreateBaseResume:
    """POST /api/v1/base-resumes — create with validation."""

    @pytest.mark.asyncio
    async def test_create_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.post(
            _BASE_URL, json={"name": "Test", "role_type": "Dev", "summary": "Test"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_success(self, client: AsyncClient) -> None:
        """Creates a base resume and returns it with 201 status."""
        payload = {
            "persona_id": str(TEST_PERSONA_ID),
            "name": "Software Engineer Resume",
            "role_type": "Software Engineer",
            "summary": "Full-stack engineer with Python and React expertise.",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["name"] == "Software Engineer Resume"
        assert body["data"]["role_type"] == "Software Engineer"
        assert body["data"]["status"] == "Active"
        assert "id" in body["data"]

    @pytest.mark.asyncio
    async def test_create_with_optional_fields(self, client: AsyncClient) -> None:
        """Creates a base resume with optional JSONB selection fields."""
        job_id = str(uuid.uuid4())
        payload = {
            "persona_id": str(TEST_PERSONA_ID),
            "name": "Full Resume",
            "role_type": "Manager",
            "summary": "Experienced manager.",
            "included_jobs": [job_id],
            "skills_emphasis": [str(uuid.uuid4())],
            "is_primary": True,
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["included_jobs"] == [job_id]
        assert body["data"]["is_primary"] is True

    @pytest.mark.asyncio
    async def test_create_missing_required_fields(self, client: AsyncClient) -> None:
        """Missing required fields returns 400."""
        response = await client.post(_BASE_URL, json={"name": "Incomplete"})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_duplicate_name_returns_409(
        self, client: AsyncClient, base_resume_in_db
    ) -> None:
        """Duplicate name for same persona returns 409."""
        payload = {
            "persona_id": str(TEST_PERSONA_ID),
            "name": base_resume_in_db.name,
            "role_type": "Any Role",
            "summary": "Duplicate name test.",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_create_invalid_persona_returns_404(
        self, client: AsyncClient
    ) -> None:
        """Non-existent persona_id returns 404."""
        payload = {
            "persona_id": str(uuid.uuid4()),
            "name": "Ghost Resume",
            "role_type": "Ghost",
            "summary": "Should fail.",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 404


# =============================================================================
# Get Base Resume
# =============================================================================


class TestGetBaseResume:
    """GET /api/v1/base-resumes/{id} — single resource."""

    @pytest.mark.asyncio
    async def test_get_requires_auth(self, unauthenticated_client: AsyncClient) -> None:
        """Unauthenticated request returns 401."""
        fake_id = uuid.uuid4()
        response = await unauthenticated_client.get(f"{_BASE_URL}/{fake_id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_success(self, client: AsyncClient, base_resume_in_db) -> None:
        """Returns base resume data with correct fields."""
        response = await client.get(f"{_BASE_URL}/{base_resume_in_db.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == str(base_resume_in_db.id)
        assert body["data"]["name"] == "Scrum Master Resume"
        assert body["data"]["role_type"] == "Scrum Master"

    @pytest.mark.asyncio
    async def test_get_excludes_rendered_document(
        self, client: AsyncClient, base_resume_with_pdf
    ) -> None:
        """Detail response does not include rendered_document binary."""
        response = await client.get(f"{_BASE_URL}/{base_resume_with_pdf.id}")
        assert response.status_code == 200
        body = response.json()
        assert "rendered_document" not in body["data"]
        assert "rendered_at" in body["data"]

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        fake_id = uuid.uuid4()
        response = await client.get(f"{_BASE_URL}/{fake_id}")
        assert response.status_code == 404


# =============================================================================
# Update Base Resume
# =============================================================================


class TestUpdateBaseResume:
    """PATCH /api/v1/base-resumes/{id} — partial update."""

    @pytest.mark.asyncio
    async def test_update_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        fake_id = uuid.uuid4()
        response = await unauthenticated_client.patch(
            f"{_BASE_URL}/{fake_id}", json={"name": "Updated"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_name(self, client: AsyncClient, base_resume_in_db) -> None:
        """Updates name field only."""
        response = await client.patch(
            f"{_BASE_URL}/{base_resume_in_db.id}",
            json={"name": "Updated Scrum Resume"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["name"] == "Updated Scrum Resume"
        # Other fields unchanged
        assert body["data"]["role_type"] == "Scrum Master"

    @pytest.mark.asyncio
    async def test_update_summary_and_skills(
        self, client: AsyncClient, base_resume_in_db
    ) -> None:
        """Updates multiple fields in a single PATCH."""
        skill_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        response = await client.patch(
            f"{_BASE_URL}/{base_resume_in_db.id}",
            json={
                "summary": "Revised summary with new focus areas.",
                "skills_emphasis": skill_ids,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["summary"] == "Revised summary with new focus areas."
        assert body["data"]["skills_emphasis"] == skill_ids

    @pytest.mark.asyncio
    async def test_update_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        fake_id = uuid.uuid4()
        response = await client.patch(f"{_BASE_URL}/{fake_id}", json={"name": "Ghost"})
        assert response.status_code == 404


# =============================================================================
# Delete (Archive) Base Resume
# =============================================================================


class TestDeleteBaseResume:
    """DELETE /api/v1/base-resumes/{id} — soft archive."""

    @pytest.mark.asyncio
    async def test_delete_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        fake_id = uuid.uuid4()
        response = await unauthenticated_client.delete(f"{_BASE_URL}/{fake_id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_archives_resume(
        self, client: AsyncClient, base_resume_in_db
    ) -> None:
        """DELETE sets status to Archived and returns 204."""
        response = await client.delete(f"{_BASE_URL}/{base_resume_in_db.id}")
        assert response.status_code == 204

        # Verify it's archived (get should still return it)
        get_response = await client.get(f"{_BASE_URL}/{base_resume_in_db.id}")
        assert get_response.status_code == 200
        assert get_response.json()["data"]["status"] == "Archived"

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        fake_id = uuid.uuid4()
        response = await client.delete(f"{_BASE_URL}/{fake_id}")
        assert response.status_code == 404


# =============================================================================
# Restore Base Resume
# =============================================================================


class TestRestoreBaseResume:
    """POST /api/v1/base-resumes/{id}/restore — restore from archive.

    REQ-002 §5.4: Restore sets status back to Active.
    """

    @pytest.mark.asyncio
    async def test_restore_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        fake_id = uuid.uuid4()
        response = await unauthenticated_client.post(f"{_BASE_URL}/{fake_id}/restore")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_restore_archived_resume(
        self, client: AsyncClient, base_resume_in_db
    ) -> None:
        """Restoring an archived resume sets status to Active."""
        # Archive first
        await client.delete(f"{_BASE_URL}/{base_resume_in_db.id}")

        # Restore
        response = await client.post(f"{_BASE_URL}/{base_resume_in_db.id}/restore")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["status"] == "Active"
        assert body["data"]["archived_at"] is None

    @pytest.mark.asyncio
    async def test_restore_active_resume_rejected(
        self, client: AsyncClient, base_resume_in_db
    ) -> None:
        """Restoring an already-active resume returns 422."""
        response = await client.post(f"{_BASE_URL}/{base_resume_in_db.id}/restore")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_restore_other_users_resume_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Restoring another user's archived resume returns 404 (not 403)."""
        from app.models import Persona, User
        from app.models.resume import BaseResume

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
        await db_session.flush()

        other_resume = BaseResume(
            id=uuid.uuid4(),
            persona_id=other_persona.id,
            name="Other Resume",
            role_type="Other",
            summary="Other user's resume.",
            status="Archived",
        )
        db_session.add(other_resume)
        await db_session.commit()

        response = await client.post(f"{_BASE_URL}/{other_resume.id}/restore")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_restore_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        fake_id = uuid.uuid4()
        response = await client.post(f"{_BASE_URL}/{fake_id}/restore")
        assert response.status_code == 404
