"""Tests for IDOR protection on Application create endpoint.

VULN-003: The create_application endpoint accepted job_variant_id and
cover_letter_id from the request body without verifying they belong to
the authenticated user. An attacker could reference another user's
variant or cover letter when creating an Application.

These tests verify cross-tenant isolation: User A's resources cannot be
referenced by User B when creating Applications.
"""

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cover_letter import CoverLetter
from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.models.persona_job import PersonaJob
from app.models.resume import BaseResume, JobVariant
from tests.conftest import PERSONA_B_ID, TEST_PERSONA_ID

# =============================================================================
# Constants
# =============================================================================

_SOURCE_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
_JOB_POSTING_ID = uuid.UUID("30000000-0000-0000-0000-000000000002")
_BASE_RESUME_A_ID = uuid.UUID("30000000-0000-0000-0000-000000000003")
_VARIANT_A_ID = uuid.UUID("30000000-0000-0000-0000-000000000004")
_COVER_LETTER_A_ID = uuid.UUID("30000000-0000-0000-0000-000000000005")
_BASE_RESUME_B_ID = uuid.UUID("30000000-0000-0000-0000-000000000006")
_VARIANT_B_ID = uuid.UUID("30000000-0000-0000-0000-000000000007")
_COVER_LETTER_B_ID = uuid.UUID("30000000-0000-0000-0000-000000000008")

_APPLICATIONS_URL = "/api/v1/applications"
_JOB_SNAPSHOT = {"title": "Engineer", "company_name": "TestCorp"}


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def idor_scenario(
    db_session: AsyncSession,
    test_user,  # noqa: ARG001
    test_persona,  # noqa: ARG001
    user_b,  # noqa: ARG001
    persona_user_b,  # noqa: ARG001
) -> SimpleNamespace:
    """Create cross-tenant entity chains for IDOR testing.

    Sets up:
    - Shared job source + job posting (Tier 0 shared pool)
    - User A: BaseResume, JobVariant, CoverLetter, PersonaJob link
    - User B: BaseResume, JobVariant, CoverLetter, PersonaJob link
    """
    # Shared infrastructure
    source = JobSource(
        id=_SOURCE_ID,
        source_name="IDOR Test Source",
        source_type="Extension",
        description="Test source",
    )
    db_session.add(source)
    await db_session.flush()

    job_posting = JobPosting(
        id=_JOB_POSTING_ID,
        source_id=_SOURCE_ID,
        job_title="Engineer",
        company_name="TestCorp",
        description="Description",
        first_seen_date=date(2026, 1, 1),
        description_hash="idor_test_hash",
    )
    db_session.add(job_posting)
    await db_session.flush()

    # PersonaJob links (both users linked to the shared job)
    pj_a = PersonaJob(persona_id=TEST_PERSONA_ID, job_posting_id=_JOB_POSTING_ID)
    pj_b = PersonaJob(persona_id=PERSONA_B_ID, job_posting_id=_JOB_POSTING_ID)
    db_session.add_all([pj_a, pj_b])
    await db_session.flush()

    # User A's resources
    base_resume_a = BaseResume(
        id=_BASE_RESUME_A_ID,
        persona_id=TEST_PERSONA_ID,
        name="User A Resume",
        role_type="Engineer",
        summary="Summary A",
        is_primary=True,
        included_jobs=[],
        included_education=[],
        included_certifications=[],
        skills_emphasis=[],
        job_bullet_selections={},
        job_bullet_order={},
    )
    db_session.add(base_resume_a)
    await db_session.flush()

    variant_a = JobVariant(
        id=_VARIANT_A_ID,
        base_resume_id=_BASE_RESUME_A_ID,
        job_posting_id=_JOB_POSTING_ID,
        summary="Variant A",
        status="Approved",
        approved_at=datetime.now(UTC),
        snapshot_included_jobs=[],
        snapshot_included_education=[],
        snapshot_included_certifications=[],
        snapshot_skills_emphasis=[],
        snapshot_job_bullet_selections={},
    )
    db_session.add(variant_a)

    cover_letter_a = CoverLetter(
        id=_COVER_LETTER_A_ID,
        persona_id=TEST_PERSONA_ID,
        job_posting_id=_JOB_POSTING_ID,
        status="Approved",
        draft_text="Cover letter A content",
    )
    db_session.add(cover_letter_a)
    await db_session.flush()

    # User B's resources
    base_resume_b = BaseResume(
        id=_BASE_RESUME_B_ID,
        persona_id=PERSONA_B_ID,
        name="User B Resume",
        role_type="Engineer",
        summary="Summary B",
        is_primary=True,
        included_jobs=[],
        included_education=[],
        included_certifications=[],
        skills_emphasis=[],
        job_bullet_selections={},
        job_bullet_order={},
    )
    db_session.add(base_resume_b)
    await db_session.flush()

    variant_b = JobVariant(
        id=_VARIANT_B_ID,
        base_resume_id=_BASE_RESUME_B_ID,
        job_posting_id=_JOB_POSTING_ID,
        summary="Variant B",
        status="Approved",
        approved_at=datetime.now(UTC),
        snapshot_included_jobs=[],
        snapshot_included_education=[],
        snapshot_included_certifications=[],
        snapshot_skills_emphasis=[],
        snapshot_job_bullet_selections={},
    )
    db_session.add(variant_b)

    cover_letter_b = CoverLetter(
        id=_COVER_LETTER_B_ID,
        persona_id=PERSONA_B_ID,
        job_posting_id=_JOB_POSTING_ID,
        status="Approved",
        draft_text="Cover letter B content",
    )
    db_session.add(cover_letter_b)
    await db_session.commit()

    return SimpleNamespace(
        job_posting_id=_JOB_POSTING_ID,
        variant_a_id=_VARIANT_A_ID,
        variant_b_id=_VARIANT_B_ID,
        cover_letter_a_id=_COVER_LETTER_A_ID,
        cover_letter_b_id=_COVER_LETTER_B_ID,
    )


# =============================================================================
# Tests — P0: IDOR on job_variant_id
# =============================================================================


class TestApplicationVariantIDOR:
    """User B must not be able to reference User A's JobVariant."""

    @pytest.mark.asyncio
    async def test_create_with_own_variant_succeeds(
        self,
        client: AsyncClient,
        idor_scenario: SimpleNamespace,
    ) -> None:
        """User A can create an Application referencing their own variant."""
        response = await client.post(
            _APPLICATIONS_URL,
            json={
                "persona_id": str(TEST_PERSONA_ID),
                "job_posting_id": str(idor_scenario.job_posting_id),
                "job_variant_id": str(idor_scenario.variant_a_id),
                "job_snapshot": _JOB_SNAPSHOT,
            },
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_with_other_users_variant_rejected(
        self,
        client_user_b: AsyncClient,
        idor_scenario: SimpleNamespace,
    ) -> None:
        """User B cannot create an Application referencing User A's variant.

        VULN-003: This was the core IDOR — job_variant_id was accepted
        without ownership verification.
        """
        response = await client_user_b.post(
            _APPLICATIONS_URL,
            json={
                "persona_id": str(PERSONA_B_ID),
                "job_posting_id": str(idor_scenario.job_posting_id),
                "job_variant_id": str(idor_scenario.variant_a_id),
                "job_snapshot": _JOB_SNAPSHOT,
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_with_nonexistent_variant_rejected(
        self,
        client: AsyncClient,
        idor_scenario: SimpleNamespace,
    ) -> None:
        """Nonexistent job_variant_id should return 404."""
        response = await client.post(
            _APPLICATIONS_URL,
            json={
                "persona_id": str(TEST_PERSONA_ID),
                "job_posting_id": str(idor_scenario.job_posting_id),
                "job_variant_id": str(uuid.uuid4()),
                "job_snapshot": _JOB_SNAPSHOT,
            },
        )
        assert response.status_code == 404


# =============================================================================
# Tests — P0: IDOR on cover_letter_id
# =============================================================================


class TestApplicationCoverLetterIDOR:
    """User B must not be able to reference User A's CoverLetter."""

    @pytest.mark.asyncio
    async def test_create_with_own_cover_letter_succeeds(
        self,
        client: AsyncClient,
        idor_scenario: SimpleNamespace,
    ) -> None:
        """User A can create an Application with their own cover letter."""
        response = await client.post(
            _APPLICATIONS_URL,
            json={
                "persona_id": str(TEST_PERSONA_ID),
                "job_posting_id": str(idor_scenario.job_posting_id),
                "job_variant_id": str(idor_scenario.variant_a_id),
                "cover_letter_id": str(idor_scenario.cover_letter_a_id),
                "job_snapshot": _JOB_SNAPSHOT,
            },
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_with_other_users_cover_letter_rejected(
        self,
        client_user_b: AsyncClient,
        idor_scenario: SimpleNamespace,
    ) -> None:
        """User B cannot create an Application with User A's cover letter.

        VULN-003: cover_letter_id was accepted without ownership verification.
        """
        response = await client_user_b.post(
            _APPLICATIONS_URL,
            json={
                "persona_id": str(PERSONA_B_ID),
                "job_posting_id": str(idor_scenario.job_posting_id),
                "job_variant_id": str(idor_scenario.variant_b_id),
                "cover_letter_id": str(idor_scenario.cover_letter_a_id),
                "job_snapshot": _JOB_SNAPSHOT,
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_with_nonexistent_cover_letter_rejected(
        self,
        client: AsyncClient,
        idor_scenario: SimpleNamespace,
    ) -> None:
        """Nonexistent cover_letter_id should return 404."""
        response = await client.post(
            _APPLICATIONS_URL,
            json={
                "persona_id": str(TEST_PERSONA_ID),
                "job_posting_id": str(idor_scenario.job_posting_id),
                "job_variant_id": str(idor_scenario.variant_a_id),
                "cover_letter_id": str(uuid.uuid4()),
                "job_snapshot": _JOB_SNAPSHOT,
            },
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_without_cover_letter_succeeds(
        self,
        client: AsyncClient,
        idor_scenario: SimpleNamespace,
    ) -> None:
        """Application without cover_letter_id should succeed (it's optional)."""
        response = await client.post(
            _APPLICATIONS_URL,
            json={
                "persona_id": str(TEST_PERSONA_ID),
                "job_posting_id": str(idor_scenario.job_posting_id),
                "job_variant_id": str(idor_scenario.variant_a_id),
                "job_snapshot": _JOB_SNAPSHOT,
            },
        )
        assert response.status_code == 201
