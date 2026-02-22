"""Tests for Job Variants CRUD API endpoints.

REQ-006 §5.2: Job-specific resume variants.
REQ-002 §4.3: Job Variant — Snapshot Logic.
REQ-002 §5.4: User Actions — Archive/Restore.

Tests verify:
- GET /api/v1/job-variants (list with ownership filtering)
- POST /api/v1/job-variants (create with validation)
- GET /api/v1/job-variants/{id} (get single)
- PATCH /api/v1/job-variants/{id} (partial update, immutable after approval)
- DELETE /api/v1/job-variants/{id} (soft archive)
- POST /api/v1/job-variants/{id}/approve (snapshot logic)
- POST /api/v1/job-variants/{id}/restore (restore from archive)
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_JOB_SOURCE_ID, TEST_PERSONA_ID

_BASE_URL = "/api/v1/job-variants"


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def base_resume_in_db(db_session: AsyncSession):
    """Create a base resume for job variant tests."""
    from app.models.resume import BaseResume

    resume = BaseResume(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        name="Software Engineer Resume",
        role_type="Software Engineer",
        summary="Full-stack engineer with Python and React expertise.",
        included_jobs=["job-1", "job-2"],
        included_education=["edu-1"],
        included_certifications=["cert-1", "cert-2"],
        skills_emphasis=["skill-1", "skill-2", "skill-3"],
        job_bullet_selections={"job-1": ["bullet-a", "bullet-b"]},
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume


@pytest_asyncio.fixture
async def job_posting_in_db(db_session: AsyncSession):
    """Create a job posting linked to the test persona via PersonaJob."""
    from datetime import date

    from app.models.job_posting import JobPosting
    from app.models.persona_job import PersonaJob

    posting = JobPosting(
        id=uuid.uuid4(),
        source_id=TEST_JOB_SOURCE_ID,
        job_title="Senior Python Developer",
        company_name="Acme Corp",
        description="Looking for a senior Python developer.",
        first_seen_date=date(2026, 1, 15),
        description_hash="abc123hash",
    )
    db_session.add(posting)
    await db_session.flush()

    pj = PersonaJob(
        persona_id=TEST_PERSONA_ID,
        job_posting_id=posting.id,
        status="Discovered",
        discovery_method="manual",
    )
    db_session.add(pj)
    await db_session.commit()
    await db_session.refresh(posting)
    return posting


@pytest_asyncio.fixture
async def variant_in_db(db_session: AsyncSession, base_resume_in_db, job_posting_in_db):
    """Create a draft job variant for test queries."""
    from app.models.resume import JobVariant

    variant = JobVariant(
        id=uuid.uuid4(),
        base_resume_id=base_resume_in_db.id,
        job_posting_id=job_posting_in_db.id,
        summary="Tailored summary for Senior Python Developer role.",
        job_bullet_order={"job-1": ["bullet-b", "bullet-a"]},
        modifications_description="Reordered bullets to emphasize Python experience.",
    )
    db_session.add(variant)
    await db_session.commit()
    await db_session.refresh(variant)
    return variant


@pytest_asyncio.fixture
async def approved_variant_in_db(db_session: AsyncSession, base_resume_in_db):
    """Create an approved job variant with snapshots populated."""
    from datetime import UTC, date, datetime

    from app.models.job_posting import JobPosting
    from app.models.resume import JobVariant

    posting2 = JobPosting(
        id=uuid.uuid4(),
        source_id=TEST_JOB_SOURCE_ID,
        job_title="Backend Engineer",
        company_name="Beta Inc",
        description="Looking for a backend engineer.",
        first_seen_date=date(2026, 1, 20),
        description_hash="def456hash",
    )
    db_session.add(posting2)
    await db_session.commit()
    await db_session.refresh(posting2)

    variant = JobVariant(
        id=uuid.uuid4(),
        base_resume_id=base_resume_in_db.id,
        job_posting_id=posting2.id,
        summary="Approved tailored summary.",
        job_bullet_order={"job-1": ["bullet-a"]},
        status="Approved",
        approved_at=datetime.now(UTC),
        snapshot_included_jobs=base_resume_in_db.included_jobs,
        snapshot_job_bullet_selections=base_resume_in_db.job_bullet_selections,
        snapshot_included_education=base_resume_in_db.included_education,
        snapshot_included_certifications=base_resume_in_db.included_certifications,
        snapshot_skills_emphasis=base_resume_in_db.skills_emphasis,
    )
    db_session.add(variant)
    await db_session.commit()
    await db_session.refresh(variant)
    return variant


# =============================================================================
# List Job Variants
# =============================================================================


class TestListJobVariants:
    """GET /api/v1/job-variants — list with ownership filtering."""

    @pytest.mark.asyncio
    async def test_list_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.get(_BASE_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_returns_user_variants(
        self, client: AsyncClient, variant_in_db
    ) -> None:
        """Returns job variants belonging to the authenticated user."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["id"] == str(variant_in_db.id)

    @pytest.mark.asyncio
    async def test_list_empty_when_none_exist(self, client: AsyncClient) -> None:
        """Returns empty list when no job variants exist."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_includes_pagination_meta(
        self,
        client: AsyncClient,
        variant_in_db,  # noqa: ARG002
    ) -> None:
        """Response includes pagination metadata."""
        response = await client.get(_BASE_URL)
        body = response.json()
        assert "meta" in body
        assert "total" in body["meta"]
        assert "page" in body["meta"]
        assert "per_page" in body["meta"]


# =============================================================================
# Create Job Variant
# =============================================================================


class TestCreateJobVariant:
    """POST /api/v1/job-variants — create with validation."""

    @pytest.mark.asyncio
    async def test_create_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.post(
            _BASE_URL, json={"summary": "Test"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_success(
        self, client: AsyncClient, base_resume_in_db, job_posting_in_db
    ) -> None:
        """Creates a job variant and returns it with 201 status."""
        payload = {
            "base_resume_id": str(base_resume_in_db.id),
            "job_posting_id": str(job_posting_in_db.id),
            "summary": "Tailored for this specific role.",
            "job_bullet_order": {"job-1": ["bullet-b", "bullet-a"]},
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["summary"] == "Tailored for this specific role."
        assert body["data"]["status"] == "Draft"
        assert body["data"]["snapshot_included_jobs"] is None
        assert "id" in body["data"]

    @pytest.mark.asyncio
    async def test_create_with_modifications_description(
        self, client: AsyncClient, base_resume_in_db, job_posting_in_db
    ) -> None:
        """Creates a job variant with optional modifications_description."""
        payload = {
            "base_resume_id": str(base_resume_in_db.id),
            "job_posting_id": str(job_posting_in_db.id),
            "summary": "Tailored summary.",
            "modifications_description": "Reordered bullets for Python emphasis.",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 201
        body = response.json()
        assert (
            body["data"]["modifications_description"]
            == "Reordered bullets for Python emphasis."
        )

    @pytest.mark.asyncio
    async def test_create_missing_required_fields(self, client: AsyncClient) -> None:
        """Missing required fields returns 400."""
        response = await client.post(_BASE_URL, json={"summary": "Incomplete"})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_invalid_base_resume_returns_404(
        self, client: AsyncClient, job_posting_in_db
    ) -> None:
        """Non-existent base_resume_id returns 404."""
        payload = {
            "base_resume_id": str(uuid.uuid4()),
            "job_posting_id": str(job_posting_in_db.id),
            "summary": "Should fail.",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_invalid_job_posting_returns_404(
        self, client: AsyncClient, base_resume_in_db
    ) -> None:
        """Non-existent job_posting_id returns 404."""
        payload = {
            "base_resume_id": str(base_resume_in_db.id),
            "job_posting_id": str(uuid.uuid4()),
            "summary": "Should fail.",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 404


# =============================================================================
# Get Job Variant
# =============================================================================


class TestGetJobVariant:
    """GET /api/v1/job-variants/{id} — single resource."""

    @pytest.mark.asyncio
    async def test_get_requires_auth(self, unauthenticated_client: AsyncClient) -> None:
        """Unauthenticated request returns 401."""
        fake_id = uuid.uuid4()
        response = await unauthenticated_client.get(f"{_BASE_URL}/{fake_id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_success(self, client: AsyncClient, variant_in_db) -> None:
        """Returns job variant data with correct fields."""
        response = await client.get(f"{_BASE_URL}/{variant_in_db.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == str(variant_in_db.id)
        assert body["data"]["status"] == "Draft"
        assert body["data"]["summary"] == variant_in_db.summary

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        fake_id = uuid.uuid4()
        response = await client.get(f"{_BASE_URL}/{fake_id}")
        assert response.status_code == 404


# =============================================================================
# Update Job Variant
# =============================================================================


class TestUpdateJobVariant:
    """PATCH /api/v1/job-variants/{id} — partial update."""

    @pytest.mark.asyncio
    async def test_update_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        fake_id = uuid.uuid4()
        response = await unauthenticated_client.patch(
            f"{_BASE_URL}/{fake_id}", json={"summary": "Updated"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_summary(self, client: AsyncClient, variant_in_db) -> None:
        """Updates summary field only."""
        response = await client.patch(
            f"{_BASE_URL}/{variant_in_db.id}",
            json={"summary": "Updated tailored summary."},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["summary"] == "Updated tailored summary."

    @pytest.mark.asyncio
    async def test_update_bullet_order(
        self, client: AsyncClient, variant_in_db
    ) -> None:
        """Updates job_bullet_order."""
        new_order = {"job-1": ["bullet-a", "bullet-b"], "job-2": ["bullet-c"]}
        response = await client.patch(
            f"{_BASE_URL}/{variant_in_db.id}",
            json={"job_bullet_order": new_order},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["job_bullet_order"] == new_order

    @pytest.mark.asyncio
    async def test_update_approved_variant_rejected(
        self, client: AsyncClient, approved_variant_in_db
    ) -> None:
        """Updating an approved variant returns 422 (immutable)."""
        response = await client.patch(
            f"{_BASE_URL}/{approved_variant_in_db.id}",
            json={"summary": "Should fail."},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_archived_variant_rejected(
        self, client: AsyncClient, variant_in_db
    ) -> None:
        """Updating an archived variant returns 422 (immutable)."""
        # Archive the variant first
        await client.delete(f"{_BASE_URL}/{variant_in_db.id}")
        response = await client.patch(
            f"{_BASE_URL}/{variant_in_db.id}",
            json={"summary": "Should fail."},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        fake_id = uuid.uuid4()
        response = await client.patch(
            f"{_BASE_URL}/{fake_id}", json={"summary": "Ghost"}
        )
        assert response.status_code == 404


# =============================================================================
# Delete (Archive) Job Variant
# =============================================================================


class TestDeleteJobVariant:
    """DELETE /api/v1/job-variants/{id} — soft archive."""

    @pytest.mark.asyncio
    async def test_delete_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        fake_id = uuid.uuid4()
        response = await unauthenticated_client.delete(f"{_BASE_URL}/{fake_id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_archives_variant(
        self, client: AsyncClient, variant_in_db
    ) -> None:
        """DELETE sets status to Archived and returns 204."""
        response = await client.delete(f"{_BASE_URL}/{variant_in_db.id}")
        assert response.status_code == 204

        # Verify it's archived with timestamp
        get_response = await client.get(f"{_BASE_URL}/{variant_in_db.id}")
        assert get_response.status_code == 200
        data = get_response.json()["data"]
        assert data["status"] == "Archived"
        assert data["archived_at"] is not None

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        fake_id = uuid.uuid4()
        response = await client.delete(f"{_BASE_URL}/{fake_id}")
        assert response.status_code == 404


# =============================================================================
# Approve Job Variant (Snapshot Logic)
# =============================================================================


class TestApproveJobVariant:
    """POST /api/v1/job-variants/{id}/approve — snapshot on approval."""

    @pytest.mark.asyncio
    async def test_approve_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        fake_id = uuid.uuid4()
        response = await unauthenticated_client.post(f"{_BASE_URL}/{fake_id}/approve")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_approve_changes_status(
        self, client: AsyncClient, variant_in_db
    ) -> None:
        """Approval changes status from Draft to Approved."""
        response = await client.post(f"{_BASE_URL}/{variant_in_db.id}/approve")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["status"] == "Approved"
        assert body["data"]["approved_at"] is not None

    @pytest.mark.asyncio
    async def test_approve_populates_snapshot_fields(
        self, client: AsyncClient, variant_in_db, base_resume_in_db
    ) -> None:
        """Approval copies BaseResume selection fields into snapshot columns."""
        response = await client.post(f"{_BASE_URL}/{variant_in_db.id}/approve")
        assert response.status_code == 200
        body = response.json()
        data = body["data"]

        # Snapshot fields should match the BaseResume's selections
        assert data["snapshot_included_jobs"] == base_resume_in_db.included_jobs
        assert (
            data["snapshot_job_bullet_selections"]
            == base_resume_in_db.job_bullet_selections
        )
        assert (
            data["snapshot_included_education"] == base_resume_in_db.included_education
        )
        assert (
            data["snapshot_included_certifications"]
            == base_resume_in_db.included_certifications
        )
        assert data["snapshot_skills_emphasis"] == base_resume_in_db.skills_emphasis

    @pytest.mark.asyncio
    async def test_approve_already_approved_rejected(
        self, client: AsyncClient, approved_variant_in_db
    ) -> None:
        """Approving an already-approved variant returns 422."""
        response = await client.post(f"{_BASE_URL}/{approved_variant_in_db.id}/approve")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_approve_archived_variant_rejected(
        self, client: AsyncClient, variant_in_db
    ) -> None:
        """Approving an archived variant returns 422."""
        # Archive the variant first
        await client.delete(f"{_BASE_URL}/{variant_in_db.id}")
        response = await client.post(f"{_BASE_URL}/{variant_in_db.id}/approve")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_approve_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        fake_id = uuid.uuid4()
        response = await client.post(f"{_BASE_URL}/{fake_id}/approve")
        assert response.status_code == 404


# =============================================================================
# Restore Job Variant
# =============================================================================


class TestRestoreJobVariant:
    """POST /api/v1/job-variants/{id}/restore — restore from archive.

    REQ-002 §5.4: Restore returns variant to its pre-archive status.
    Draft variants restore to Draft; Approved variants restore to Approved.
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
    async def test_restore_archived_draft_variant(
        self, client: AsyncClient, variant_in_db
    ) -> None:
        """Restoring an archived draft variant sets status to Draft."""
        # Archive first
        await client.delete(f"{_BASE_URL}/{variant_in_db.id}")

        # Restore
        response = await client.post(f"{_BASE_URL}/{variant_in_db.id}/restore")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["status"] == "Draft"
        assert body["data"]["archived_at"] is None

    @pytest.mark.asyncio
    async def test_restore_archived_approved_variant(
        self, client: AsyncClient, approved_variant_in_db
    ) -> None:
        """Restoring an archived approved variant sets status to Approved."""
        # Archive first
        await client.delete(f"{_BASE_URL}/{approved_variant_in_db.id}")

        # Verify archived
        get_resp = await client.get(f"{_BASE_URL}/{approved_variant_in_db.id}")
        assert get_resp.json()["data"]["status"] == "Archived"

        # Restore
        response = await client.post(f"{_BASE_URL}/{approved_variant_in_db.id}/restore")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["status"] == "Approved"
        assert body["data"]["archived_at"] is None
        # Snapshots should still be present
        assert body["data"]["snapshot_included_jobs"] is not None

    @pytest.mark.asyncio
    async def test_restore_non_archived_rejected(
        self, client: AsyncClient, variant_in_db
    ) -> None:
        """Restoring a non-archived variant returns 422."""
        response = await client.post(f"{_BASE_URL}/{variant_in_db.id}/restore")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_restore_other_users_variant_returns_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Restoring another user's archived variant returns 404 (not 403)."""
        from datetime import date

        from app.models import Persona, User
        from app.models.job_posting import JobPosting
        from app.models.resume import BaseResume, JobVariant

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
        )
        db_session.add(other_resume)
        await db_session.flush()

        from tests.conftest import TEST_JOB_SOURCE_ID

        other_posting = JobPosting(
            id=uuid.uuid4(),
            source_id=TEST_JOB_SOURCE_ID,
            job_title="Other Job",
            company_name="Other Corp",
            description="Other job description.",
            first_seen_date=date(2026, 1, 1),
            description_hash="otherhash",
        )
        db_session.add(other_posting)
        await db_session.flush()

        other_variant = JobVariant(
            id=uuid.uuid4(),
            base_resume_id=other_resume.id,
            job_posting_id=other_posting.id,
            summary="Other variant.",
            status="Archived",
        )
        db_session.add(other_variant)
        await db_session.commit()

        response = await client.post(f"{_BASE_URL}/{other_variant.id}/restore")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_restore_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        fake_id = uuid.uuid4()
        response = await client.post(f"{_BASE_URL}/{fake_id}/restore")
        assert response.status_code == 404
