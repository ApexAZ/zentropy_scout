"""Tests for Applications API ownership verification.

REQ-014 §5, §6: Multi-tenant ownership — returns 404 for cross-tenant access.

NOTE: This file exceeds 300 lines because Applications has 11 endpoints across
three sub-resources (CRUD, Timeline, Bulk) and each needs auth/success/failure/
cross-tenant tests. Splitting would fragment the cohesive test suite.

Tests verify:
- GET /api/v1/applications (list with ownership filtering)
- POST /api/v1/applications (create with persona ownership check)
- GET /api/v1/applications/{id} (get single with ownership)
- PATCH /api/v1/applications/{id} (update with ownership)
- DELETE /api/v1/applications/{id} (soft archive with ownership)
- GET /api/v1/applications/{id}/timeline (list events with ownership)
- POST /api/v1/applications/{id}/timeline (create event with ownership)
- GET /api/v1/applications/{id}/timeline/{event_id} (get event with ownership)
- PATCH /api/v1/applications/{id}/timeline/{event_id} (immutable — 405)
- DELETE /api/v1/applications/{id}/timeline/{event_id} (immutable — 405)
- POST /api/v1/applications/bulk-archive (bulk with ownership)
"""

import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_JOB_SOURCE_ID, TEST_PERSONA_ID

_BASE_URL = "/api/v1/applications"


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def job_posting_for_app(db_session: AsyncSession):
    """Create a job posting owned by the test user."""
    from app.models.job_posting import JobPosting

    posting = JobPosting(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        source_id=TEST_JOB_SOURCE_ID,
        job_title="Backend Engineer",
        company_name="App Corp",
        description="Build backend services.",
        description_hash="app_test_hash_001",
        first_seen_date=date(2026, 1, 20),
    )
    db_session.add(posting)
    await db_session.commit()
    await db_session.refresh(posting)
    return posting


@pytest_asyncio.fixture
async def base_resume_for_app(db_session: AsyncSession):
    """Create a base resume owned by the test user."""
    from app.models.resume import BaseResume

    resume = BaseResume(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        name="App Test Resume",
        role_type="Backend Engineer",
        summary="Experienced backend developer.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume


@pytest_asyncio.fixture
async def job_variant_for_app(
    db_session: AsyncSession, base_resume_for_app, job_posting_for_app
):
    """Create a job variant owned by the test user."""
    from app.models.resume import JobVariant

    variant = JobVariant(
        id=uuid.uuid4(),
        base_resume_id=base_resume_for_app.id,
        job_posting_id=job_posting_for_app.id,
        summary="Tailored summary for App Corp backend role.",
    )
    db_session.add(variant)
    await db_session.commit()
    await db_session.refresh(variant)
    return variant


@pytest_asyncio.fixture
async def application_in_db(
    db_session: AsyncSession, job_posting_for_app, job_variant_for_app
):
    """Create an application owned by the test user."""
    from app.models.application import Application

    app = Application(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        job_posting_id=job_posting_for_app.id,
        job_variant_id=job_variant_for_app.id,
        job_snapshot={"title": "Backend Engineer", "company": "App Corp"},
        notes="Applied via company website.",
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)
    return app


@pytest_asyncio.fixture
async def timeline_event_in_db(db_session: AsyncSession, application_in_db):
    """Create a timeline event on the test user's application."""
    from app.models.application import TimelineEvent

    event = TimelineEvent(
        id=uuid.uuid4(),
        application_id=application_in_db.id,
        event_type="applied",
        event_date=datetime(2026, 1, 20, 10, 0, 0, tzinfo=UTC),
        description="Submitted application through website.",
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)
    return event


@pytest_asyncio.fixture
async def other_user_application(db_session: AsyncSession):
    """Create an application owned by another user for cross-tenant tests."""
    from app.models import Persona, User
    from app.models.application import Application
    from app.models.job_posting import JobPosting
    from app.models.resume import BaseResume, JobVariant

    other_user = User(id=uuid.uuid4(), email="other_app@example.com")
    db_session.add(other_user)
    await db_session.flush()

    other_persona = Persona(
        id=uuid.uuid4(),
        user_id=other_user.id,
        full_name="Other App User",
        email="other_app_persona@example.com",
        phone="555-6666",
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
        description_hash="app_other_hash_001",
        first_seen_date=date(2026, 1, 15),
    )
    db_session.add(other_posting)
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

    other_variant = JobVariant(
        id=uuid.uuid4(),
        base_resume_id=other_resume.id,
        job_posting_id=other_posting.id,
        summary="Other variant summary.",
    )
    db_session.add(other_variant)
    await db_session.flush()

    app = Application(
        id=uuid.uuid4(),
        persona_id=other_persona.id,
        job_posting_id=other_posting.id,
        job_variant_id=other_variant.id,
        job_snapshot={"title": "Other Job", "company": "Other Corp"},
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)
    return app


# =============================================================================
# List Applications
# =============================================================================


class TestListApplications:
    """GET /api/v1/applications — list with ownership."""

    @pytest.mark.asyncio
    async def test_list_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.get(_BASE_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_returns_user_applications(
        self, client: AsyncClient, application_in_db
    ) -> None:
        """Returns applications belonging to the authenticated user."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["id"] == str(application_in_db.id)

    @pytest.mark.asyncio
    async def test_list_empty_when_none_exist(self, client: AsyncClient) -> None:
        """Returns empty list when no applications exist."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["meta"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_excludes_other_users_applications(
        self, client: AsyncClient, application_in_db, other_user_application
    ) -> None:
        """List does not include another user's applications."""
        response = await client.get(_BASE_URL)
        assert response.status_code == 200
        body = response.json()
        ids = [a["id"] for a in body["data"]]
        assert str(application_in_db.id) in ids
        assert str(other_user_application.id) not in ids


# =============================================================================
# Create Application
# =============================================================================


class TestCreateApplication:
    """POST /api/v1/applications — create with ownership check."""

    @pytest.mark.asyncio
    async def test_create_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.post(
            _BASE_URL, json={"job_snapshot": {}}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_success(
        self, client: AsyncClient, job_posting_for_app, job_variant_for_app
    ) -> None:
        """Creates an application linked to user's persona."""
        payload = {
            "persona_id": str(TEST_PERSONA_ID),
            "job_posting_id": str(job_posting_for_app.id),
            "job_variant_id": str(job_variant_for_app.id),
            "job_snapshot": {"title": "Backend Engineer"},
            "notes": "Applied via company website.",
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["persona_id"] == str(TEST_PERSONA_ID)
        assert body["data"]["status"] == "Applied"
        assert body["data"]["notes"] == "Applied via company website."

    @pytest.mark.asyncio
    async def test_create_invalid_persona_returns_404(
        self, client: AsyncClient, job_posting_for_app, job_variant_for_app
    ) -> None:
        """Non-existent persona_id returns 404."""
        payload = {
            "persona_id": str(uuid.uuid4()),
            "job_posting_id": str(job_posting_for_app.id),
            "job_variant_id": str(job_variant_for_app.id),
            "job_snapshot": {"title": "Ghost"},
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_other_users_persona_returns_404(
        self,
        client: AsyncClient,
        other_user_application,
        job_posting_for_app,
        job_variant_for_app,
    ) -> None:
        """Using another user's persona_id returns 404."""
        payload = {
            "persona_id": str(other_user_application.persona_id),
            "job_posting_id": str(job_posting_for_app.id),
            "job_variant_id": str(job_variant_for_app.id),
            "job_snapshot": {"title": "Hacked"},
        }
        response = await client.post(_BASE_URL, json=payload)
        assert response.status_code == 404


# =============================================================================
# Get Application
# =============================================================================


class TestGetApplication:
    """GET /api/v1/applications/{id} — single resource."""

    @pytest.mark.asyncio
    async def test_get_requires_auth(self, unauthenticated_client: AsyncClient) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.get(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_success(self, client: AsyncClient, application_in_db) -> None:
        """Returns application data for owned resource."""
        response = await client.get(f"{_BASE_URL}/{application_in_db.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == str(application_in_db.id)
        assert body["data"]["status"] == "Applied"
        assert body["data"]["job_snapshot"]["title"] == "Backend Engineer"

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        response = await client.get(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_other_users_application_returns_404(
        self, client: AsyncClient, other_user_application
    ) -> None:
        """Cross-tenant access returns 404 (not 403)."""
        response = await client.get(f"{_BASE_URL}/{other_user_application.id}")
        assert response.status_code == 404


# =============================================================================
# Update Application
# =============================================================================


class TestUpdateApplication:
    """PATCH /api/v1/applications/{id} — update with ownership."""

    @pytest.mark.asyncio
    async def test_update_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.patch(
            f"{_BASE_URL}/{uuid.uuid4()}", json={"notes": "Updated"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_notes(self, client: AsyncClient, application_in_db) -> None:
        """Updates notes field."""
        response = await client.patch(
            f"{_BASE_URL}/{application_in_db.id}",
            json={"notes": "Updated notes."},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["notes"] == "Updated notes."

    @pytest.mark.asyncio
    async def test_update_status(self, client: AsyncClient, application_in_db) -> None:
        """Updates status and status_updated_at."""
        response = await client.patch(
            f"{_BASE_URL}/{application_in_db.id}",
            json={"status": "Interviewing"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["status"] == "Interviewing"

    @pytest.mark.asyncio
    async def test_update_pin(self, client: AsyncClient, application_in_db) -> None:
        """Updates is_pinned field."""
        response = await client.patch(
            f"{_BASE_URL}/{application_in_db.id}",
            json={"is_pinned": True},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["is_pinned"] is True

    @pytest.mark.asyncio
    async def test_update_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        response = await client.patch(
            f"{_BASE_URL}/{uuid.uuid4()}", json={"notes": "Ghost"}
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_other_users_application_returns_404(
        self, client: AsyncClient, other_user_application
    ) -> None:
        """Cross-tenant update returns 404 (not 403)."""
        response = await client.patch(
            f"{_BASE_URL}/{other_user_application.id}",
            json={"notes": "Hacked"},
        )
        assert response.status_code == 404


# =============================================================================
# Delete (Archive) Application
# =============================================================================


class TestDeleteApplication:
    """DELETE /api/v1/applications/{id} — soft archive."""

    @pytest.mark.asyncio
    async def test_delete_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.delete(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_archives_application(
        self, client: AsyncClient, application_in_db
    ) -> None:
        """DELETE sets archived_at and returns 204."""
        response = await client.delete(f"{_BASE_URL}/{application_in_db.id}")
        assert response.status_code == 204

        # Verify archived_at is set
        get_response = await client.get(f"{_BASE_URL}/{application_in_db.id}")
        assert get_response.status_code == 200
        assert get_response.json()["data"]["archived_at"] is not None

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client: AsyncClient) -> None:
        """Non-existent ID returns 404."""
        response = await client.delete(f"{_BASE_URL}/{uuid.uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_other_users_application_returns_404(
        self, client: AsyncClient, other_user_application
    ) -> None:
        """Cross-tenant delete returns 404 (not 403)."""
        response = await client.delete(f"{_BASE_URL}/{other_user_application.id}")
        assert response.status_code == 404


# =============================================================================
# Timeline Events
# =============================================================================


class TestListTimelineEvents:
    """GET /api/v1/applications/{id}/timeline — list events with ownership."""

    @pytest.mark.asyncio
    async def test_list_timeline_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.get(
            f"{_BASE_URL}/{uuid.uuid4()}/timeline"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_timeline_success(
        self, client: AsyncClient, application_in_db, timeline_event_in_db
    ) -> None:
        """Returns timeline events for owned application."""
        response = await client.get(f"{_BASE_URL}/{application_in_db.id}/timeline")
        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["id"] == str(timeline_event_in_db.id)

    @pytest.mark.asyncio
    async def test_list_timeline_other_users_application_returns_404(
        self, client: AsyncClient, other_user_application
    ) -> None:
        """Cross-tenant timeline list returns 404."""
        response = await client.get(f"{_BASE_URL}/{other_user_application.id}/timeline")
        assert response.status_code == 404


class TestCreateTimelineEvent:
    """POST /api/v1/applications/{id}/timeline — create event with ownership."""

    @pytest.mark.asyncio
    async def test_create_timeline_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.post(
            f"{_BASE_URL}/{uuid.uuid4()}/timeline",
            json={
                "event_type": "applied",
                "event_date": "2026-01-20T10:00:00Z",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_timeline_success(
        self, client: AsyncClient, application_in_db
    ) -> None:
        """Creates a timeline event on owned application."""
        payload = {
            "event_type": "status_changed",
            "event_date": "2026-01-25T14:00:00Z",
            "description": "Moved to interview stage.",
        }
        response = await client.post(
            f"{_BASE_URL}/{application_in_db.id}/timeline", json=payload
        )
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["event_type"] == "status_changed"
        assert body["data"]["application_id"] == str(application_in_db.id)

    @pytest.mark.asyncio
    async def test_create_timeline_other_users_application_returns_404(
        self, client: AsyncClient, other_user_application
    ) -> None:
        """Cross-tenant timeline creation returns 404."""
        payload = {
            "event_type": "applied",
            "event_date": "2026-01-20T10:00:00Z",
        }
        response = await client.post(
            f"{_BASE_URL}/{other_user_application.id}/timeline", json=payload
        )
        assert response.status_code == 404


class TestGetTimelineEvent:
    """GET /api/v1/applications/{id}/timeline/{event_id} — single event."""

    @pytest.mark.asyncio
    async def test_get_timeline_event_success(
        self, client: AsyncClient, application_in_db, timeline_event_in_db
    ) -> None:
        """Returns timeline event for owned application."""
        response = await client.get(
            f"{_BASE_URL}/{application_in_db.id}/timeline/{timeline_event_in_db.id}"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == str(timeline_event_in_db.id)
        assert body["data"]["event_type"] == "applied"

    @pytest.mark.asyncio
    async def test_get_timeline_event_not_found(
        self, client: AsyncClient, application_in_db
    ) -> None:
        """Non-existent event ID returns 404."""
        response = await client.get(
            f"{_BASE_URL}/{application_in_db.id}/timeline/{uuid.uuid4()}"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_timeline_other_users_application_returns_404(
        self, client: AsyncClient, other_user_application
    ) -> None:
        """Cross-tenant timeline event access returns 404."""
        response = await client.get(
            f"{_BASE_URL}/{other_user_application.id}/timeline/{uuid.uuid4()}"
        )
        assert response.status_code == 404


class TestImmutableTimelineEvents:
    """PATCH/DELETE timeline events — always 405 (immutable)."""

    @pytest.mark.asyncio
    async def test_update_timeline_event_returns_405(
        self, client: AsyncClient, application_in_db, timeline_event_in_db
    ) -> None:
        """PATCH timeline event returns 405 Method Not Allowed."""
        response = await client.patch(
            f"{_BASE_URL}/{application_in_db.id}/timeline/{timeline_event_in_db.id}",
            json={"description": "Modified"},
        )
        assert response.status_code == 405
        body = response.json()
        assert body["error"]["code"] == "METHOD_NOT_ALLOWED"

    @pytest.mark.asyncio
    async def test_delete_timeline_event_returns_405(
        self, client: AsyncClient, application_in_db, timeline_event_in_db
    ) -> None:
        """DELETE timeline event returns 405 Method Not Allowed."""
        response = await client.delete(
            f"{_BASE_URL}/{application_in_db.id}/timeline/{timeline_event_in_db.id}"
        )
        assert response.status_code == 405
        body = response.json()
        assert body["error"]["code"] == "METHOD_NOT_ALLOWED"


# =============================================================================
# Bulk Archive
# =============================================================================


class TestBulkArchive:
    """POST /api/v1/applications/bulk-archive — bulk with ownership."""

    @pytest.mark.asyncio
    async def test_bulk_archive_requires_auth(
        self, unauthenticated_client: AsyncClient
    ) -> None:
        """Unauthenticated request returns 401."""
        response = await unauthenticated_client.post(
            f"{_BASE_URL}/bulk-archive", json={"ids": [str(uuid.uuid4())]}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_bulk_archive_empty_request(self, client: AsyncClient) -> None:
        """Empty IDs list returns empty result."""
        response = await client.post(f"{_BASE_URL}/bulk-archive", json={"ids": []})
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["succeeded"] == []
        assert body["data"]["failed"] == []

    @pytest.mark.asyncio
    async def test_bulk_archive_owned_applications(
        self, client: AsyncClient, application_in_db
    ) -> None:
        """Archives owned applications."""
        response = await client.post(
            f"{_BASE_URL}/bulk-archive",
            json={"ids": [str(application_in_db.id)]},
        )
        assert response.status_code == 200
        body = response.json()
        assert str(application_in_db.id) in body["data"]["succeeded"]
        assert body["data"]["failed"] == []

    @pytest.mark.asyncio
    async def test_bulk_archive_other_users_application_fails(
        self, client: AsyncClient, other_user_application
    ) -> None:
        """Other user's applications are reported as NOT_FOUND."""
        response = await client.post(
            f"{_BASE_URL}/bulk-archive",
            json={"ids": [str(other_user_application.id)]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["succeeded"] == []
        assert len(body["data"]["failed"]) == 1
        assert body["data"]["failed"][0]["error"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_bulk_archive_mixed_owned_and_other(
        self, client: AsyncClient, application_in_db, other_user_application
    ) -> None:
        """Mixed owned/other results in partial success."""
        response = await client.post(
            f"{_BASE_URL}/bulk-archive",
            json={
                "ids": [
                    str(application_in_db.id),
                    str(other_user_application.id),
                ]
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert str(application_in_db.id) in body["data"]["succeeded"]
        assert len(body["data"]["failed"]) == 1
        assert body["data"]["failed"][0]["id"] == str(other_user_application.id)
