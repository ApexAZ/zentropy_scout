"""Tests for job posting response schemas.

REQ-015 §8.3: Response models enforce privacy boundaries.
JobPostingResponse excludes also_found_on and cross-user aggregations.
PersonaJobResponse nests shared job data with per-user fields.
"""

import uuid
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.schemas.job_posting import JobPostingResponse, PersonaJobResponse

_NOW = datetime.now(UTC)
_TODAY = date.today()
_JOB_ID = uuid.uuid4()
_PJ_ID = uuid.uuid4()


def _make_job_data(**overrides: object) -> dict:
    """Build minimal valid JobPostingResponse data."""
    data = {
        "id": _JOB_ID,
        "job_title": "Software Engineer",
        "company_name": "Acme Corp",
        "is_active": True,
        "description": "Build great things",
        "description_hash": "abc123" * 5 + "ab",
        "first_seen_date": _TODAY,
        "ghost_score": 10,
        "repost_count": 0,
    }
    data.update(overrides)
    return data


def _make_pj_data(**overrides: object) -> dict:
    """Build minimal valid PersonaJobResponse data."""
    data = {
        "id": _PJ_ID,
        "job": _make_job_data(),
        "status": "Discovered",
        "is_favorite": False,
        "discovery_method": "scouter",
        "discovered_at": _NOW,
    }
    data.update(overrides)
    return data


class TestJobPostingResponse:
    """Test JobPostingResponse schema (REQ-015 §8.3)."""

    def test_minimal_fields(self):
        """Schema accepts minimal required fields."""
        resp = JobPostingResponse(**_make_job_data())
        assert resp.id == _JOB_ID
        assert resp.job_title == "Software Engineer"
        assert resp.company_name == "Acme Corp"
        assert resp.is_active is True
        assert resp.description == "Build great things"

    def test_all_optional_fields(self):
        """Schema accepts all optional factual fields."""
        resp = JobPostingResponse(
            **_make_job_data(
                external_id="ext-123",
                company_url="https://acme.com",
                source_url="https://linkedin.com/jobs/123",
                apply_url="https://acme.com/apply",
                location="Remote",
                work_model="Remote",
                seniority_level="Senior",
                salary_min=100000,
                salary_max=150000,
                salary_currency="USD",
                culture_text="We value innovation",
                requirements="5+ years Python",
                years_experience_min=5,
                years_experience_max=10,
                posted_date=_TODAY,
                application_deadline=_TODAY,
                last_verified_at=_NOW,
                expired_at=_NOW,
                ghost_signals={"stale_listing": True},
                previous_posting_ids=[str(uuid.uuid4())],
            )
        )
        assert resp.location == "Remote"
        assert resp.salary_min == 100000
        assert resp.seniority_level == "Senior"

    def test_excludes_also_found_on(self):
        """Privacy: also_found_on MUST NOT be present in response."""
        resp = JobPostingResponse(**_make_job_data())
        # Verify it's not in the serialized output
        dumped = resp.model_dump()
        assert "also_found_on" not in dumped

    def test_excludes_raw_text(self):
        """raw_text is internal — not exposed in public response."""
        resp = JobPostingResponse(**_make_job_data())
        dumped = resp.model_dump()
        assert "raw_text" not in dumped

    def test_rejects_extra_fields(self):
        """Schema with extra='forbid' rejects unknown fields."""
        with pytest.raises(ValidationError):
            JobPostingResponse(**_make_job_data(also_found_on={"sources": []}))

    def test_source_id_included(self):
        """source_id is included for client-side source display."""
        resp = JobPostingResponse(**_make_job_data(source_id=uuid.uuid4()))
        assert resp.source_id is not None


class TestPersonaJobResponse:
    """Test PersonaJobResponse schema (REQ-015 §8.3)."""

    def test_minimal_fields(self):
        """Schema accepts minimal required fields."""
        resp = PersonaJobResponse(**_make_pj_data())
        assert resp.id == _PJ_ID
        assert resp.status == "Discovered"
        assert resp.is_favorite is False
        assert resp.discovery_method == "scouter"

    def test_nested_job_data(self):
        """PersonaJobResponse nests JobPostingResponse."""
        resp = PersonaJobResponse(**_make_pj_data())
        assert isinstance(resp.job, JobPostingResponse)
        assert resp.job.job_title == "Software Engineer"
        assert resp.job.company_name == "Acme Corp"

    def test_all_scoring_fields(self):
        """Schema accepts all per-user scoring fields."""
        resp = PersonaJobResponse(
            **_make_pj_data(
                fit_score=85,
                stretch_score=30,
                failed_non_negotiables=["Python 5+ years"],
                score_details={"skill_match": 0.9},
                scored_at=_NOW,
                dismissed_at=_NOW,
            )
        )
        assert resp.fit_score == 85
        assert resp.stretch_score == 30
        assert resp.failed_non_negotiables == ["Python 5+ years"]
        assert resp.score_details == {"skill_match": 0.9}

    def test_optional_fields_default_none(self):
        """Scoring fields default to None when not provided."""
        resp = PersonaJobResponse(**_make_pj_data())
        assert resp.fit_score is None
        assert resp.stretch_score is None
        assert resp.failed_non_negotiables is None
        assert resp.score_details is None
        assert resp.scored_at is None
        assert resp.dismissed_at is None

    def test_discovery_methods(self):
        """All valid discovery methods are accepted."""
        for method in ("scouter", "manual", "pool"):
            resp = PersonaJobResponse(**_make_pj_data(discovery_method=method))
            assert resp.discovery_method == method

    def test_statuses(self):
        """All valid statuses are accepted."""
        for status in ("Discovered", "Dismissed", "Applied"):
            resp = PersonaJobResponse(**_make_pj_data(status=status))
            assert resp.status == status

    def test_rejects_extra_fields(self):
        """Schema with extra='forbid' rejects unknown fields."""
        with pytest.raises(ValidationError):
            PersonaJobResponse(**_make_pj_data(user_count=42))

    def test_serialization_roundtrip(self):
        """Schema can serialize to dict and back."""
        original = PersonaJobResponse(**_make_pj_data(fit_score=75))
        dumped = original.model_dump(mode="json")
        restored = PersonaJobResponse(**dumped)
        assert restored.id == original.id
        assert restored.fit_score == 75
        assert restored.job.job_title == "Software Engineer"
