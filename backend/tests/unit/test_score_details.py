"""Tests for score_details JSONB column on persona_jobs.

REQ-012 Appendix A.3: FitScoreResult, StretchScoreResult, and
ScoreExplanation are computed by the service layer but only aggregate
scores are persisted. The score_details JSONB column stores component
breakdowns and explanation data for the frontend score drill-down UI.

REQ-015 §4.2: Per-user scoring fields (score_details, fit_score,
stretch_score) moved from job_postings to persona_jobs.

Tests verify:
- PersonaJob model stores and retrieves score_details JSONB
- build_scored_result includes score_details parameter
- build_filtered_score_result sets score_details to None
"""

import uuid
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_posting import JobPosting
from app.models.persona_job import PersonaJob
from app.services.scoring_flow import build_filtered_score_result, build_scored_result
from tests.conftest import TEST_PERSONA_ID

_JOB_SOURCE_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
_JOB_POSTING_ID = uuid.UUID("30000000-0000-0000-0000-000000000002")

_SAMPLE_FIT: dict[str, Any] = {
    "total": 85.0,
    "components": {
        "hard_skills": 90.0,
        "soft_skills": 75.0,
        "experience_level": 88.0,
        "role_title": 72.0,
        "location_logistics": 95.0,
    },
    "weights": {
        "hard_skills": 0.40,
        "soft_skills": 0.15,
        "experience_level": 0.25,
        "role_title": 0.10,
        "location_logistics": 0.10,
    },
}

_SAMPLE_STRETCH: dict[str, Any] = {
    "total": 72.0,
    "components": {
        "target_role": 80.0,
        "target_skills": 60.0,
        "growth_trajectory": 70.0,
    },
    "weights": {
        "target_role": 0.50,
        "target_skills": 0.40,
        "growth_trajectory": 0.10,
    },
}


@pytest_asyncio.fixture
async def score_details_scenario(
    db_session: AsyncSession,
    test_user,  # noqa: ARG001
    test_persona,  # noqa: ARG001
) -> SimpleNamespace:
    """Create a job posting for score_details tests."""
    from app.models.job_source import JobSource

    source = JobSource(
        id=_JOB_SOURCE_ID,
        source_name="test-source",
        source_type="Manual",
        description="Test source for score details tests.",
    )
    db_session.add(source)
    await db_session.flush()

    job = JobPosting(
        id=_JOB_POSTING_ID,
        source_id=_JOB_SOURCE_ID,
        external_id="ext-123",
        job_title="Software Engineer",
        company_name="TestCorp",
        description="A test job posting.",
        description_hash="abc123",
        first_seen_date=date(2026, 2, 8),
    )
    db_session.add(job)
    await db_session.flush()

    persona_job = PersonaJob(
        persona_id=TEST_PERSONA_ID,
        job_posting_id=_JOB_POSTING_ID,
        status="Discovered",
        discovery_method="manual",
    )
    db_session.add(persona_job)
    await db_session.flush()

    return SimpleNamespace(job=job, source=source, persona_job=persona_job)


# =============================================================================
# Model Column Tests
# =============================================================================


class TestScoreDetailsColumn:
    """Tests for score_details JSONB column on PersonaJob model.

    REQ-015 §4.2: Per-user scoring fields moved to persona_jobs.
    """

    @pytest.mark.asyncio
    async def test_defaults_to_none(
        self,
        score_details_scenario: SimpleNamespace,
        db_session: AsyncSession,
    ) -> None:
        """New persona_jobs should have score_details=None by default."""
        result = await db_session.execute(
            select(PersonaJob).where(
                PersonaJob.id == score_details_scenario.persona_job.id
            )
        )
        pj = result.scalar_one()
        assert pj.score_details is None

    @pytest.mark.asyncio
    async def test_stores_jsonb(
        self, score_details_scenario: SimpleNamespace, db_session: AsyncSession
    ) -> None:
        """score_details should accept and persist a JSONB dict."""
        details = {
            "fit": _SAMPLE_FIT,
            "stretch": _SAMPLE_STRETCH,
            "explanation": {
                "summary": "Strong technical fit.",
                "strengths": ["Python", "FastAPI"],
                "gaps": ["Kubernetes"],
                "stretch_opportunities": ["ML pipeline"],
                "warnings": [],
            },
        }
        pj = score_details_scenario.persona_job
        pj.score_details = details
        await db_session.flush()

        result = await db_session.execute(
            select(PersonaJob).where(PersonaJob.id == pj.id)
        )
        refreshed = result.scalar_one()
        assert refreshed.score_details is not None
        assert refreshed.score_details["fit"]["total"] == 85.0
        assert refreshed.score_details["stretch"]["components"]["target_role"] == 80.0
        assert refreshed.score_details["explanation"]["strengths"] == [
            "Python",
            "FastAPI",
        ]

    @pytest.mark.asyncio
    async def test_coexists_with_aggregate_scores(
        self, score_details_scenario: SimpleNamespace, db_session: AsyncSession
    ) -> None:
        """score_details coexists with fit_score/stretch_score integer columns."""
        pj = score_details_scenario.persona_job
        pj.fit_score = 85
        pj.stretch_score = 72
        pj.score_details = {"fit": _SAMPLE_FIT, "stretch": _SAMPLE_STRETCH}
        await db_session.flush()

        result = await db_session.execute(
            select(PersonaJob).where(PersonaJob.id == pj.id)
        )
        refreshed = result.scalar_one()
        assert refreshed.fit_score == 85
        assert refreshed.stretch_score == 72
        assert refreshed.score_details["fit"]["total"] == 85.0


# =============================================================================
# build_scored_result / build_filtered_score_result Tests
# =============================================================================


class TestBuildScoredResultScoreDetails:
    """Tests for score_details in build_scored_result."""

    def test_includes_when_provided(self) -> None:
        """build_scored_result should include score_details in the result."""
        details = {"fit": _SAMPLE_FIT, "stretch": _SAMPLE_STRETCH}
        result = build_scored_result(
            job_id=uuid.uuid4(),
            fit_score=85.0,
            stretch_score=72.0,
            explanation="Good match.",
            score_details=details,
        )
        assert result["score_details"] == details

    def test_defaults_to_none(self) -> None:
        """build_scored_result should default score_details to None."""
        result = build_scored_result(
            job_id=uuid.uuid4(), fit_score=85.0, stretch_score=72.0
        )
        assert result.get("score_details") is None


class TestBuildFilteredScoreResultScoreDetails:
    """Tests for score_details in build_filtered_score_result."""

    def test_filtered_result_has_none(self) -> None:
        """Filtered jobs should not have score_details."""
        from app.services.scoring_flow import JobFilterResult

        filter_result = JobFilterResult(
            job_id=uuid.uuid4(),
            passed=False,
            failed_reasons=["salary_below_minimum"],
            warnings=[],
        )
        result = build_filtered_score_result(filter_result)
        assert result.get("score_details") is None
