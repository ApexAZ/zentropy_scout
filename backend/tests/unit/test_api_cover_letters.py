"""Tests for Cover Letters API ownership verification.

REQ-014 §5, §6: Multi-tenant ownership — returns 404 for cross-tenant access.

Tests verify:
- GET /api/v1/cover-letters (list with ownership filtering)
- POST /api/v1/cover-letters (create with persona ownership check)
- GET /api/v1/cover-letters/{id} (get single with ownership)
- PATCH /api/v1/cover-letters/{id} (update with ownership)
- DELETE /api/v1/cover-letters/{id} (soft archive with ownership)
"""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_JOB_SOURCE_ID, TEST_PERSONA_ID

_BASE_URL = "/api/v1/cover-letters"


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def job_posting_for_cl(db_session: AsyncSession):
    """Create a job posting owned by the test user (needed for cover letters)."""
    from app.models.job_posting import JobPosting

    posting = JobPosting(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        source_id=TEST_JOB_SOURCE_ID,
        job_title="Software Engineer",
        company_name="Test Corp",
        description="Build great software.",
        description_hash="cl_test_hash_001",
        first_seen_date=date(2026, 1, 15),
    )
    db_session.add(posting)
    await db_session.commit()
    await db_session.refresh(posting)
    return posting


@pytest_asyncio.fixture
async def cover_letter_in_db(db_session: AsyncSession, job_posting_for_cl):
    """Create a cover letter owned by the test user."""
    from app.models.cover_letter import CoverLetter

    cl = CoverLetter(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        job_posting_id=job_posting_for_cl.id,
        draft_text="Dear Hiring Manager, I am excited to apply...",
        achievement_stories_used=[],
    )
    db_session.add(cl)
    await db_session.commit()
    await db_session.refresh(cl)
    return cl


@pytest_asyncio.fixture
async def other_user_cover_letter(db_session: AsyncSession):
    """Create a cover letter owned by another user for cross-tenant tests."""
    from app.models import Persona, User
    from app.models.cover_letter import CoverLetter
    from app.models.job_posting import JobPosting

    other_user = User(id=uuid.uuid4(), email="other_cl@example.com")
    db_session.add(other_user)
    await db_session.flush()

    other_persona = Persona(
        id=uuid.uuid4(),
        user_id=other_user.id,
        full_name="Other CL User",
        email="other_cl_persona@example.com",
        phone="555-7777",
        home_city="Other City",
        home_state="Other State",
        home_country="USA",
    )
    db_session.add(other_persona)
    await db_session.flush()

    other_posting = JobPosting(
        id=uuid.uuid4(),
        persona_id=other_persona.id,
        source_id=TEST_JOB_SOURCE_ID,
        job_title="Other Job",
        company_name="Other Corp",
        description="Other job description.",
        description_hash="cl_other_hash_001",
        first_seen_date=date(2026, 1, 15),
    )
    db_session.add(other_posting)
    await db_session.flush()

    cl = CoverLetter(
        id=uuid.uuid4(),
        persona_id=other_persona.id,
        job_posting_id=other_posting.id,
        draft_text="Other user's cover letter text.",
        achievement_stories_used=[],
    )
    db_session.add(cl)
    await db_session.commit()
    await db_session.refresh(cl)
    return cl


# =============================================================================
# List Cover Letters
# =============================================================================


class TestListCoverLetters:
    """GET /api/v1/cover-letters — list with ownership."""

    @pytest.mark.asyncio
    async def test_list_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.get(_BASE_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_returns_user_cover_letters(
        self, client: AsyncClient, cover_letter_in_db
    ) -> None:
        """Returns cover letters belonging to the authenticated user."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["id"] == str(cover_letter_in_db.id)

    @pytest.mark.asyncio
    async def test_list_empty_when_none_exist(self, client: AsyncClient) -> None:
        """Returns empty list when no cover letters exist."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_excludes_other_users_cover_letters(
        self, client: AsyncClient, cover_letter_in_db, other_user_cover_letter
    ) -> None:
        """List does not include another user's cover letters."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        ids = [cl["id"] for cl in body["data"]]
        assert str(cover_letter_in_db.id) in ids
        assert str(other_user_cover_letter.id) not in ids


# =============================================================================
# Create Cover Letter
# =============================================================================


class TestCreateCoverLetter:
    """POST /api/v1/cover-letters — create with ownership check."""

    @pytest.mark.asyncio
    async def test_create_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.post(
            _BASE_URL, json={"draft_text": "Test"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_success(
        self, client: AsyncClient, job_posting_for_cl
    ) -> None:
        """Creates a cover letter linked to user's persona."""
        payload = {
            "persona_id": str(TEST_PERSONA_ID),
            "job_posting_id": str(job_posting_for_cl.id),
            "draft_text": "Dear Hiring Manager, I would love to join your team...",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["persona_id"] == str(TEST_PERSONA_ID)
        assert body["data"]["status"] == "Draft"
        assert "id" in body["data"]

    @pytest.mark.asyncio
    async def test_create_invalid_persona_returns_404(
        self, client: AsyncClient, job_posting_for_cl
    ) -> None:
        """Non-existent persona_id returns 404."""
        payload = {
            "persona_id": str(uuid.uuid4()),
            "job_posting_id": str(job_posting_for_cl.id),
            "draft_text": "Should fail.",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_other_users_persona_returns_404(
        self, client: AsyncClient, other_user_cover_letter, job_posting_for_cl
    ) -> None:
        """Using another user's persona_id returns 404."""
        payload = {
            "persona_id": str(other_user_cover_letter.persona_id),
            "job_posting_id": str(job_posting_for_cl.id),
            "draft_text": "Should fail — wrong persona.",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 404


# =============================================================================
# Get Cover Letter
# =============================================================================


class TestGetCoverLetter:
    """GET /api/v1/cover-letters/{id} — single resource."""

    @pytest.mark.asyncio
    async def test_get_requires_auth(self, unauthenticated_client: AsyncClient) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.get(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_success(self, client: AsyncClient, cover_letter_in_db) -> None:
        """Returns cover letter data for owned resource."""
        response = await client.get(f"{_BASE_URL}/{cover_letter_in_db.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == str(cover_letter_in_db.id)
        assert body["data"]["draft_text"] == cover_letter_in_db.draft_text
        assert body["data"]["status"] == "Draft"

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        response = await client.get(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_other_users_cover_letter_returns_404(
        self, client: AsyncClient, other_user_cover_letter
    ) -> None:
        """Cross-tenant access returns 404 (not 403)."""
        response = await client.get(f"{_BASE_URL}/{other_user_cover_letter.id}")
        assert response.status_code == 404


# =============================================================================
# Update Cover Letter
# =============================================================================


class TestUpdateCoverLetter:
    """PATCH /api/v1/cover-letters/{id} — update with ownership."""

    @pytest.mark.asyncio
    async def test_update_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.patch(
            f"{_BASE_URL}/{uuid.uuid4()}", json={"draft_text": "Updated"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_draft_text(
        self, client: AsyncClient, cover_letter_in_db
    ) -> None:
        """Updates draft_text field."""
        response = await client.patch(
            f"{_BASE_URL}/{cover_letter_in_db.id}",
            json={"draft_text": "Revised cover letter text."},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["draft_text"] == "Revised cover letter text."

    @pytest.mark.asyncio
    async def test_update_status_to_approved_sets_timestamp(
        self, client: AsyncClient, cover_letter_in_db
    ) -> None:
        """Transitioning to Approved sets approved_at."""
        response = await client.patch(
            f"{_BASE_URL}/{cover_letter_in_db.id}",
            json={"status": "Approved"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["status"] == "Approved"
        assert body["data"]["approved_at"] is not None

    @pytest.mark.asyncio
    async def test_update_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        response = await client.patch(
            f"{_BASE_URL}/{uuid.uuid4()}", json={"draft_text": "Ghost"}
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_other_users_cover_letter_returns_404(
        self, client: AsyncClient, other_user_cover_letter
    ) -> None:
        """Cross-tenant update returns 404 (not 403)."""
        response = await client.patch(
            f"{_BASE_URL}/{other_user_cover_letter.id}",
            json={"draft_text": "Hacked text"},
        )
        assert response.status_code == 404


# =============================================================================
# Delete (Archive) Cover Letter
# =============================================================================


class TestDeleteCoverLetter:
    """DELETE /api/v1/cover-letters/{id} — soft archive."""

    @pytest.mark.asyncio
    async def test_delete_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.delete(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_archives_cover_letter(
        self, client: AsyncClient, cover_letter_in_db
    ) -> None:
        """DELETE sets status to Archived and returns 204."""
        response = await client.delete(f"{_BASE_URL}/{cover_letter_in_db.id}")
        assert response.status_code == 204

        # Verify it's archived
        get_response = await client.get(f"{_BASE_URL}/{cover_letter_in_db.id}")
        assert get_response.status_code == 200
        assert get_response.json()["data"]["status"] == "Archived"
        assert get_response.json()["data"]["archived_at"] is not None

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        response = await client.delete(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_other_users_cover_letter_returns_404(
        self, client: AsyncClient, other_user_cover_letter
    ) -> None:
        """Cross-tenant delete returns 404 (not 403)."""
        response = await client.delete(f"{_BASE_URL}/{other_user_cover_letter.id}")
        assert response.status_code == 404
