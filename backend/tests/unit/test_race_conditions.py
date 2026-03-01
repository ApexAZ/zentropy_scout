"""Tests for race condition handling via DB-level unique constraints.

Security: Verifies that IntegrityError from concurrent INSERT races
is handled gracefully (no 500 errors) by the API endpoints.

Race conditions covered:

RACE-001: create_job_posting — concurrent INSERT on description_hash.
    Two requests check hash → both get None → both INSERT → second hits
    uq_job_postings_description_hash → handler catches IntegrityError,
    creates link to the existing job instead of returning 500.

RACE-002: finalize_onboarding — double-submit via SELECT FOR UPDATE.
    Two requests read persona.onboarding_complete = False → both proceed
    → both create entities → duplicate data. SELECT FOR UPDATE on the
    Persona row prevents the second request from reading stale state.
"""

import hashlib
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.models.persona_job import PersonaJob
from tests.conftest import TEST_PERSONA_ID, TEST_USER_ID

# =============================================================================
# Constants
# =============================================================================

_SOURCE_ID = uuid.UUID("40000000-0000-0000-0000-000000000001")
_JOB_POSTING_ID = uuid.UUID("40000000-0000-0000-0000-000000000002")
_JOB_TITLE = "Engineer"
_COMPANY_NAME = "TestCorp"
_DESCRIPTION = "Race condition test unique job description text for dedup"
_DESCRIPTION_HASH = hashlib.sha256(_DESCRIPTION.encode()).hexdigest()
_JOB_POSTINGS_URL = "/api/v1/job-postings"
_FAKE_EXISTING = SimpleNamespace(id=_JOB_POSTING_ID)
_PATCH_GET_BY_HASH = (
    "app.api.v1.job_postings.JobPostingRepository.get_by_description_hash"
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def race_source(
    db_session: AsyncSession,
) -> JobSource:
    """Pre-create a Manual source for race condition tests."""
    source = JobSource(
        id=_SOURCE_ID,
        source_name="Manual",
        source_type="Manual",
        description="Jobs from manual source",
    )
    db_session.add(source)
    await db_session.flush()
    return source


@pytest_asyncio.fixture
async def race_job_posting(
    db_session: AsyncSession,
    race_source: JobSource,
) -> JobPosting:
    """Pre-create a job posting with known hash (no PersonaJob link)."""
    jp = JobPosting(
        id=_JOB_POSTING_ID,
        source_id=race_source.id,
        job_title=_JOB_TITLE,
        company_name=_COMPANY_NAME,
        description=_DESCRIPTION,
        description_hash=_DESCRIPTION_HASH,
        first_seen_date=date(2026, 1, 1),
    )
    db_session.add(jp)
    await db_session.commit()
    return jp


@pytest_asyncio.fixture
async def race_job_with_link(
    db_session: AsyncSession,
    race_job_posting: JobPosting,
) -> JobPosting:
    """Pre-create a job posting WITH a PersonaJob link for User A."""
    pj = PersonaJob(
        persona_id=TEST_PERSONA_ID,
        job_posting_id=_JOB_POSTING_ID,
        status="Discovered",
        discovery_method="manual",
    )
    db_session.add(pj)
    await db_session.commit()
    return race_job_posting


# =============================================================================
# Tests — RACE-001: create_job_posting hash collision
# =============================================================================


class TestCreateJobPostingHashRace:
    """Concurrent create_job_posting with same description_hash."""

    @pytest.mark.asyncio
    async def test_hash_race_creates_link_not_500(
        self,
        client: AsyncClient,
        race_job_posting: JobPosting,  # noqa: ARG002
    ) -> None:
        """Race: INSERT hits uq_job_postings_description_hash → 201.

        Simulates: Request A created the job between our SELECT and INSERT.
        The handler catches IntegrityError, re-queries to find the existing
        job, and creates a PersonaJob link to it (201), instead of returning
        an unhandled IntegrityError (500).
        """
        with patch(
            _PATCH_GET_BY_HASH,
            new_callable=AsyncMock,
            side_effect=[None, _FAKE_EXISTING],
        ):
            response = await client.post(
                _JOB_POSTINGS_URL,
                json={
                    "job_title": _JOB_TITLE,
                    "company_name": _COMPANY_NAME,
                    "description": _DESCRIPTION,
                },
            )

        assert response.status_code != 500, (
            f"Unhandled IntegrityError on hash race: {response.text}"
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_hash_race_with_existing_link_returns_409(
        self,
        client: AsyncClient,
        race_job_with_link: JobPosting,  # noqa: ARG002
    ) -> None:
        """Race: INSERT hits constraint AND user already has a link → 409.

        Same race scenario, but User A already has a PersonaJob link
        to this job. Returns 409 DUPLICATE_JOB, not 500.
        """
        with patch(
            _PATCH_GET_BY_HASH,
            new_callable=AsyncMock,
            side_effect=[None, _FAKE_EXISTING],
        ):
            response = await client.post(
                _JOB_POSTINGS_URL,
                json={
                    "job_title": _JOB_TITLE,
                    "company_name": _COMPANY_NAME,
                    "description": _DESCRIPTION,
                },
            )

        assert response.status_code != 500, (
            f"Unhandled IntegrityError on hash race: {response.text}"
        )
        assert response.status_code == 409


# =============================================================================
# Tests — RACE-002: finalize_onboarding double-submit
# =============================================================================


class TestFinalizeOnboardingLocking:
    """SELECT FOR UPDATE prevents concurrent double-finalize."""

    @pytest.mark.asyncio
    async def test_double_finalize_second_raises_422(
        self,
        db_session: AsyncSession,
        test_user,  # noqa: ARG002
        test_persona,  # noqa: ARG002
    ) -> None:
        """Second finalize call raises InvalidStateError (422).

        This tests the behavioral contract. The SELECT FOR UPDATE
        is a defense-in-depth measure for true concurrent access.
        """
        from app.core.errors import InvalidStateError
        from app.services.onboarding_workflow import finalize_onboarding

        minimal_data = _minimal_gathered_data()

        # First call succeeds
        await finalize_onboarding(
            minimal_data, TEST_PERSONA_ID, TEST_USER_ID, db_session
        )

        # Second call must raise (onboarding already complete)
        with pytest.raises(InvalidStateError, match="already complete"):
            await finalize_onboarding(
                minimal_data, TEST_PERSONA_ID, TEST_USER_ID, db_session
            )


# =============================================================================
# Helpers
# =============================================================================


def _minimal_gathered_data() -> dict[str, object]:
    """Build minimal gathered_data for finalize_onboarding."""
    return {
        "basic_info": {
            "full_name": "Test User",
            "email": "test@example.com",
            "phone": "555-0100",
            "location_city": "Portland",
            "location_state": "OR",
            "linkedin_url": "https://linkedin.com/in/test",
        },
        "non_negotiables": {
            "minimum_salary": 100000,
            "preferred_work_model": "Remote",
            "commute_limit_minutes": 30,
            "must_have_benefits": ["health"],
            "deal_breakers": [],
            "custom_non_negotiables": [],
        },
        "growth_targets": {
            "target_roles": [_JOB_TITLE],
            "target_industries": ["Tech"],
            "interested_skills": ["Python"],
        },
        "work_history": [
            {
                "company_name": _COMPANY_NAME,
                "job_title": _JOB_TITLE,
                "start_date": "2020-01-01",
                "end_date": None,
                "is_current": True,
                "responsibilities_text": "Built things",
                "bullets": [
                    {
                        "text": "Designed systems",
                        "impact_type": "Technical",
                    }
                ],
            }
        ],
        "skills": [
            {
                "skill_name": "Python",
                "skill_type": "Hard",
                "proficiency_level": "Expert",
            }
        ],
        "education": {"skipped": True, "entries": []},
        "certifications": {"skipped": True, "entries": []},
        "achievement_stories": [
            {
                "title": "Big Win",
                "situation": "Problem existed",
                "task": "Fix it",
                "action": "I fixed it",
                "result": "It was fixed",
                "skills_demonstrated": ["Python"],
            }
        ],
        "voice_profile": {
            "formality_level": "Professional",
            "technical_depth": "High",
            "personality_keywords": ["analytical"],
            "avoided_phrases": [],
            "preferred_phrases": [],
        },
        "base_resume_setup": [
            {
                "name": "Default Resume",
                "role_type": _JOB_TITLE,
                "summary": "Experienced engineer",
                "included_jobs": [0],
                "included_education": [],
                "included_certifications": [],
                "skills_emphasis": [0],
            }
        ],
    }
