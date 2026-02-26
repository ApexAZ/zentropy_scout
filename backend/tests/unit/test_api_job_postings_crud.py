"""Tests for Job Postings CRUD API endpoints.

REQ-015 §9: API changes for shared pool + persona_jobs pattern.

Tests: GET list, GET detail, POST create, PATCH update, bulk dismiss/favorite,
cross-tenant isolation, and shared data immutability.

NOTE: This file exceeds 300 lines because it covers all CRUD operations
for a single router. Splitting would fragment the shared fixtures and
logical grouping.
"""

import hashlib
import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_posting import JobPosting
from app.models.persona_job import PersonaJob

_MISSING_UUID = uuid.UUID("99999999-9999-9999-9999-999999999999")
# Use real SHA-256 hashes so dedup tests match the router's _compute_description_hash
_HASH_A = hashlib.sha256(b"Build great software at Acme").hexdigest()
_HASH_B = hashlib.sha256(b"Analyze data at DataCo").hexdigest()


# =============================================================================
# Fixtures — shared test data
# =============================================================================


@pytest_asyncio.fixture
async def shared_job(
    db_session: AsyncSession,
    test_job_source,  # noqa: ARG001
) -> JobPosting:
    """Create a shared job posting in the pool."""
    jp = JobPosting(
        source_id=test_job_source.id,
        job_title="Software Engineer",
        company_name="Acme Corp",
        description="Build great software at Acme",
        description_hash=_HASH_A,
        first_seen_date=date.today(),
    )
    db_session.add(jp)
    await db_session.commit()
    await db_session.refresh(jp)
    return jp


@pytest_asyncio.fixture
async def shared_job_2(
    db_session: AsyncSession,
    test_job_source,  # noqa: ARG001
) -> JobPosting:
    """Create a second shared job in the pool."""
    jp = JobPosting(
        source_id=test_job_source.id,
        job_title="Data Scientist",
        company_name="DataCo",
        description="Analyze data at DataCo",
        description_hash=_HASH_B,
        first_seen_date=date.today(),
    )
    db_session.add(jp)
    await db_session.commit()
    await db_session.refresh(jp)
    return jp


@pytest_asyncio.fixture
async def persona_job_a(
    db_session: AsyncSession,
    test_persona,
    shared_job,  # noqa: ARG001
) -> PersonaJob:
    """PersonaJob linking test_persona (user A) to shared_job."""
    pj = PersonaJob(
        persona_id=test_persona.id,
        job_posting_id=shared_job.id,
        status="Discovered",
        discovery_method="manual",
    )
    db_session.add(pj)
    await db_session.commit()
    await db_session.refresh(pj)
    return pj


@pytest_asyncio.fixture
async def persona_job_b(
    db_session: AsyncSession,
    persona_user_b,
    shared_job,  # noqa: ARG001
) -> PersonaJob:
    """PersonaJob linking user B's persona to shared_job (cross-tenant)."""
    pj = PersonaJob(
        persona_id=persona_user_b.id,
        job_posting_id=shared_job.id,
        status="Discovered",
        discovery_method="pool",
    )
    db_session.add(pj)
    await db_session.commit()
    await db_session.refresh(pj)
    return pj


# =============================================================================
# GET /job-postings (list)
# =============================================================================


class TestListJobPostings:
    """GET /job-postings — list user's persona_jobs with nested job data."""

    @pytest.mark.asyncio
    async def test_empty_list(self, client: AsyncClient) -> None:
        """No persona_jobs returns empty data array."""
        response = await client.get("/api/v1/job-postings")
        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    @pytest.mark.asyncio
    async def test_returns_persona_jobs_with_nested_job(
        self, client: AsyncClient, persona_job_a: PersonaJob, shared_job: JobPosting
    ) -> None:
        """Returns PersonaJobResponse shape with nested job data."""
        response = await client.get("/api/v1/job-postings")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1

        item = data[0]
        assert item["id"] == str(persona_job_a.id)
        assert item["status"] == "Discovered"
        assert item["discovery_method"] == "manual"
        assert item["is_favorite"] is False

        # Nested shared job data
        assert item["job"]["id"] == str(shared_job.id)
        assert item["job"]["job_title"] == "Software Engineer"
        assert item["job"]["company_name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_only_returns_users_jobs(
        self,
        client: AsyncClient,
        persona_job_a: PersonaJob,
        persona_job_b: PersonaJob,  # noqa: ARG002 -ensures user B data exists
    ) -> None:
        """Only returns jobs linked to current user, not other users."""
        response = await client.get("/api/v1/job-postings")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == str(persona_job_a.id)

    @pytest.mark.asyncio
    async def test_returns_multiple_jobs(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        persona_job_a: PersonaJob,  # noqa: ARG002
        test_persona,
        shared_job_2: JobPosting,
    ) -> None:
        """Returns all persona_jobs for the user."""
        # Create second persona_job
        pj2 = PersonaJob(
            persona_id=test_persona.id,
            job_posting_id=shared_job_2.id,
            status="Discovered",
            discovery_method="scouter",
        )
        db_session.add(pj2)
        await db_session.commit()

        response = await client.get("/api/v1/job-postings")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 2


# =============================================================================
# GET /job-postings/{id} (detail)
# =============================================================================


class TestGetJobPosting:
    """GET /job-postings/{id} — detail by persona_job_id."""

    @pytest.mark.asyncio
    async def test_returns_persona_job(
        self, client: AsyncClient, persona_job_a: PersonaJob, shared_job: JobPosting
    ) -> None:
        """Returns PersonaJobResponse with nested job data."""
        response = await client.get(f"/api/v1/job-postings/{persona_job_a.id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == str(persona_job_a.id)
        assert data["status"] == "Discovered"
        assert data["job"]["id"] == str(shared_job.id)
        assert data["job"]["job_title"] == "Software Engineer"

    @pytest.mark.asyncio
    async def test_returns_404_not_found(self, client: AsyncClient) -> None:
        """Non-existent persona_job_id returns 404."""
        response = await client.get(f"/api/v1/job-postings/{_MISSING_UUID}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_cross_tenant(
        self, client: AsyncClient, persona_job_b: PersonaJob
    ) -> None:
        """Another user's persona_job returns 404 (not 403)."""
        response = await client.get(f"/api/v1/job-postings/{persona_job_b.id}")
        assert response.status_code == 404


# =============================================================================
# POST /job-postings (create)
# =============================================================================


class TestCreateJobPosting:
    """POST /job-postings — create in shared pool + persona_jobs link."""

    @pytest.mark.asyncio
    async def test_creates_new_job(self, client: AsyncClient) -> None:
        """Creates job in shared pool and persona_jobs link."""
        response = await client.post(
            "/api/v1/job-postings",
            json={
                "job_title": "Backend Developer",
                "company_name": "NewCo",
                "description": "Build APIs for NewCo",
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["status"] == "Discovered"
        assert data["discovery_method"] == "manual"
        assert data["job"]["job_title"] == "Backend Developer"
        assert data["job"]["company_name"] == "NewCo"

    @pytest.mark.asyncio
    async def test_dedup_links_existing_job(
        self, client: AsyncClient, shared_job: JobPosting
    ) -> None:
        """If job with same description_hash exists, just creates link."""
        response = await client.post(
            "/api/v1/job-postings",
            json={
                "job_title": "Software Engineer",
                "company_name": "Acme Corp",
                "description": "Build great software at Acme",  # Same as shared_job
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        # Should link to existing job posting
        assert data["job"]["id"] == str(shared_job.id)
        assert data["discovery_method"] == "manual"

    @pytest.mark.asyncio
    async def test_duplicate_link_returns_409(
        self,
        client: AsyncClient,
        persona_job_a: PersonaJob,  # noqa: ARG002 -ensures link exists
        shared_job: JobPosting,  # noqa: ARG002 -ensures job exists
    ) -> None:
        """If user already has link to this job, returns 409."""
        response = await client.post(
            "/api/v1/job-postings",
            json={
                "job_title": "Software Engineer",
                "company_name": "Acme Corp",
                "description": "Build great software at Acme",  # Same hash
            },
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_requires_job_title(self, client: AsyncClient) -> None:
        """Missing job_title returns validation error."""
        response = await client.post(
            "/api/v1/job-postings",
            json={"company_name": "Co", "description": "Desc"},
        )
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_creates_with_optional_fields(self, client: AsyncClient) -> None:
        """Creates job with all optional fields."""
        response = await client.post(
            "/api/v1/job-postings",
            json={
                "job_title": "Senior Engineer",
                "company_name": "BigCo",
                "description": "Lead engineering at BigCo",
                "location": "Remote",
                "salary_min": 150000,
                "salary_max": 200000,
                "salary_currency": "USD",
                "work_model": "Remote",
                "seniority_level": "Senior",
            },
        )
        assert response.status_code == 201
        job = response.json()["data"]["job"]
        assert job["location"] == "Remote"
        assert job["salary_min"] == 150000


# =============================================================================
# PATCH /job-postings/{id} (update persona_jobs only)
# =============================================================================


class TestUpdateJobPosting:
    """PATCH /job-postings/{id} — updates persona_jobs fields only."""

    @pytest.mark.asyncio
    async def test_updates_status(
        self, client: AsyncClient, persona_job_a: PersonaJob
    ) -> None:
        """Can update status field."""
        response = await client.patch(
            f"/api/v1/job-postings/{persona_job_a.id}",
            json={"status": "Dismissed"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "Dismissed"
        assert data["dismissed_at"] is not None  # Auto-set

    @pytest.mark.asyncio
    async def test_updates_is_favorite(
        self, client: AsyncClient, persona_job_a: PersonaJob
    ) -> None:
        """Can toggle is_favorite."""
        response = await client.patch(
            f"/api/v1/job-postings/{persona_job_a.id}",
            json={"is_favorite": True},
        )
        assert response.status_code == 200
        assert response.json()["data"]["is_favorite"] is True

    @pytest.mark.asyncio
    async def test_returns_nested_job_data(
        self, client: AsyncClient, persona_job_a: PersonaJob, shared_job: JobPosting
    ) -> None:
        """Update response includes nested job data."""
        response = await client.patch(
            f"/api/v1/job-postings/{persona_job_a.id}",
            json={"is_favorite": True},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["job"]["id"] == str(shared_job.id)
        assert data["job"]["job_title"] == "Software Engineer"

    @pytest.mark.asyncio
    async def test_rejects_invalid_status(
        self, client: AsyncClient, persona_job_a: PersonaJob
    ) -> None:
        """Invalid status value returns 422 (Literal validation)."""
        response = await client.patch(
            f"/api/v1/job-postings/{persona_job_a.id}",
            json={"status": "InvalidStatus"},
        )
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_rejects_shared_field(
        self, client: AsyncClient, persona_job_a: PersonaJob
    ) -> None:
        """Cannot update shared job posting fields (immutability)."""
        response = await client.patch(
            f"/api/v1/job-postings/{persona_job_a.id}",
            json={"job_title": "New Title"},
        )
        # extra="forbid" in UpdatePersonaJobRequest rejects unknown fields
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_returns_404_not_found(self, client: AsyncClient) -> None:
        """Non-existent persona_job_id returns 404."""
        response = await client.patch(
            f"/api/v1/job-postings/{_MISSING_UUID}",
            json={"status": "Dismissed"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_cross_tenant(
        self, client: AsyncClient, persona_job_b: PersonaJob
    ) -> None:
        """Another user's persona_job returns 404."""
        response = await client.patch(
            f"/api/v1/job-postings/{persona_job_b.id}",
            json={"status": "Dismissed"},
        )
        assert response.status_code == 404


# =============================================================================
# POST /job-postings/bulk-dismiss (DB-backed)
# =============================================================================


class TestBulkDismissDB:
    """POST /job-postings/bulk-dismiss — updates persona_jobs status."""

    @pytest.mark.asyncio
    async def test_dismisses_owned_jobs(
        self, client: AsyncClient, persona_job_a: PersonaJob
    ) -> None:
        """Dismisses persona_jobs owned by user."""
        response = await client.post(
            "/api/v1/job-postings/bulk-dismiss",
            json={"ids": [str(persona_job_a.id)]},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert str(persona_job_a.id) in data["succeeded"]
        assert data["failed"] == []

    @pytest.mark.asyncio
    async def test_dismiss_sets_dismissed_at(
        self, client: AsyncClient, persona_job_a: PersonaJob
    ) -> None:
        """Bulk dismiss also sets dismissed_at timestamp."""
        await client.post(
            "/api/v1/job-postings/bulk-dismiss",
            json={"ids": [str(persona_job_a.id)]},
        )
        # Verify via GET detail
        detail = await client.get(f"/api/v1/job-postings/{persona_job_a.id}")
        assert detail.status_code == 200
        assert detail.json()["data"]["dismissed_at"] is not None

    @pytest.mark.asyncio
    async def test_skips_unowned_jobs(
        self, client: AsyncClient, persona_job_b: PersonaJob
    ) -> None:
        """IDs not owned by user appear in failed list."""
        response = await client.post(
            "/api/v1/job-postings/bulk-dismiss",
            json={"ids": [str(persona_job_b.id)]},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["succeeded"] == []
        assert len(data["failed"]) == 1
        assert data["failed"][0]["error"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_empty_ids_returns_empty(self, client: AsyncClient) -> None:
        """Empty ids list returns empty result."""
        response = await client.post(
            "/api/v1/job-postings/bulk-dismiss",
            json={"ids": []},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["succeeded"] == []
        assert data["failed"] == []


# =============================================================================
# POST /job-postings/bulk-favorite (DB-backed)
# =============================================================================


class TestBulkFavoriteDB:
    """POST /job-postings/bulk-favorite — updates persona_jobs is_favorite."""

    @pytest.mark.asyncio
    async def test_favorites_owned_jobs(
        self, client: AsyncClient, persona_job_a: PersonaJob
    ) -> None:
        """Favorites persona_jobs owned by user."""
        response = await client.post(
            "/api/v1/job-postings/bulk-favorite",
            json={"ids": [str(persona_job_a.id)], "is_favorite": True},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert str(persona_job_a.id) in data["succeeded"]

    @pytest.mark.asyncio
    async def test_unfavorites_owned_jobs(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        persona_job_a: PersonaJob,
    ) -> None:
        """Unfavorites persona_jobs owned by user."""
        # Set favorite first
        persona_job_a.is_favorite = True
        await db_session.commit()

        response = await client.post(
            "/api/v1/job-postings/bulk-favorite",
            json={"ids": [str(persona_job_a.id)], "is_favorite": False},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert str(persona_job_a.id) in data["succeeded"]

    @pytest.mark.asyncio
    async def test_skips_unowned_jobs(
        self, client: AsyncClient, persona_job_b: PersonaJob
    ) -> None:
        """IDs not owned by user appear in failed list."""
        response = await client.post(
            "/api/v1/job-postings/bulk-favorite",
            json={"ids": [str(persona_job_b.id)], "is_favorite": True},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["succeeded"] == []
        assert len(data["failed"]) == 1
