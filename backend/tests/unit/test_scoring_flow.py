"""Tests for the Strategist scoring flow.

REQ-007 §7.2: Strategist Agent — Scoring Flow.

The scoring flow orchestrates:
1. Non-negotiables filtering (pass/fail gate)
2. Score calculation for passing jobs
3. Result aggregation

This tests the integration between non_negotiables_filter and batch_scoring
services, which are called by the Strategist agent.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.services.scoring_flow import (
    JobFilterResult,
    build_filtered_score_result,
    build_scored_result,
    filter_job_non_negotiables,
    filter_jobs_batch,
)

# =============================================================================
# Test Fixtures - Minimal Persona Data for Filtering
# =============================================================================


@dataclass
class MockPersonaNonNegotiables:
    """Minimal persona data for non-negotiables filtering."""

    remote_preference: str
    minimum_base_salary: int | None
    commutable_cities: list[str]
    industry_exclusions: list[str]
    visa_sponsorship_required: bool


@dataclass
class MockJobForFilter:
    """Minimal job data for non-negotiables filtering."""

    id: UUID
    work_model: str | None
    salary_max: int | None
    location: str | None
    industry: str | None
    visa_sponsorship: bool | None


# =============================================================================
# Non-Negotiables Filter Tests (§7.2 Step 1)
# =============================================================================


class TestScoringFlowNonNegotiablesFilter:
    """Tests for non-negotiables filtering in scoring flow."""

    def test_job_passes_all_filters(self) -> None:
        """Job meeting all non-negotiables should pass."""
        persona = MockPersonaNonNegotiables(
            remote_preference="Hybrid OK",
            minimum_base_salary=100000,
            commutable_cities=["San Francisco", "Oakland"],
            industry_exclusions=["Gambling", "Tobacco"],
            visa_sponsorship_required=False,
        )
        job = MockJobForFilter(
            id=uuid4(),
            work_model="Remote",
            salary_max=150000,
            location="San Francisco",
            industry="Technology",
            visa_sponsorship=True,
        )

        result = filter_job_non_negotiables(persona, job)

        assert result.passed is True
        assert len(result.failed_reasons) == 0

    def test_job_fails_remote_preference(self) -> None:
        """Job with wrong work model should fail remote filter."""
        persona = MockPersonaNonNegotiables(
            remote_preference="Remote Only",
            minimum_base_salary=None,
            commutable_cities=[],
            industry_exclusions=[],
            visa_sponsorship_required=False,
        )
        job = MockJobForFilter(
            id=uuid4(),
            work_model="Onsite",
            salary_max=None,
            location=None,
            industry=None,
            visa_sponsorship=None,
        )

        result = filter_job_non_negotiables(persona, job)

        assert result.passed is False
        assert any("Remote" in reason for reason in result.failed_reasons)

    def test_job_fails_salary_minimum(self) -> None:
        """Job below salary minimum should fail."""
        persona = MockPersonaNonNegotiables(
            remote_preference="No Preference",
            minimum_base_salary=150000,
            commutable_cities=[],
            industry_exclusions=[],
            visa_sponsorship_required=False,
        )
        job = MockJobForFilter(
            id=uuid4(),
            work_model="Remote",
            salary_max=100000,  # Below minimum
            location=None,
            industry=None,
            visa_sponsorship=None,
        )

        result = filter_job_non_negotiables(persona, job)

        assert result.passed is False
        assert any("Salary" in reason for reason in result.failed_reasons)

    def test_job_fails_commutable_cities(self) -> None:
        """Non-remote job in non-commutable city should fail."""
        persona = MockPersonaNonNegotiables(
            remote_preference="Onsite OK",
            minimum_base_salary=None,
            commutable_cities=["San Francisco", "Oakland"],
            industry_exclusions=[],
            visa_sponsorship_required=False,
        )
        job = MockJobForFilter(
            id=uuid4(),
            work_model="Onsite",
            salary_max=None,
            location="New York",  # Not commutable
            industry=None,
            visa_sponsorship=None,
        )

        result = filter_job_non_negotiables(persona, job)

        assert result.passed is False
        assert any("commutable" in reason.lower() for reason in result.failed_reasons)

    def test_job_fails_industry_exclusion(self) -> None:
        """Job in excluded industry should fail."""
        persona = MockPersonaNonNegotiables(
            remote_preference="No Preference",
            minimum_base_salary=None,
            commutable_cities=[],
            industry_exclusions=["Gambling", "Tobacco"],
            visa_sponsorship_required=False,
        )
        job = MockJobForFilter(
            id=uuid4(),
            work_model="Remote",
            salary_max=None,
            location=None,
            industry="Gambling",  # Excluded
            visa_sponsorship=None,
        )

        result = filter_job_non_negotiables(persona, job)

        assert result.passed is False
        assert any("Gambling" in reason for reason in result.failed_reasons)

    def test_job_fails_visa_sponsorship(self) -> None:
        """Job without visa sponsorship should fail when required."""
        persona = MockPersonaNonNegotiables(
            remote_preference="No Preference",
            minimum_base_salary=None,
            commutable_cities=[],
            industry_exclusions=[],
            visa_sponsorship_required=True,
        )
        job = MockJobForFilter(
            id=uuid4(),
            work_model="Remote",
            salary_max=None,
            location=None,
            industry=None,
            visa_sponsorship=False,  # No sponsorship
        )

        result = filter_job_non_negotiables(persona, job)

        assert result.passed is False
        assert any("sponsorship" in reason.lower() for reason in result.failed_reasons)

    def test_job_fails_multiple_filters(self) -> None:
        """Job failing multiple filters should aggregate all reasons."""
        persona = MockPersonaNonNegotiables(
            remote_preference="Remote Only",
            minimum_base_salary=200000,
            commutable_cities=[],
            industry_exclusions=["Gambling"],
            visa_sponsorship_required=False,
        )
        job = MockJobForFilter(
            id=uuid4(),
            work_model="Onsite",  # Fails remote
            salary_max=100000,  # Fails salary
            location=None,
            industry="Gambling",  # Fails industry
            visa_sponsorship=None,
        )

        result = filter_job_non_negotiables(persona, job)

        assert result.passed is False
        # Should have at least 3 failure reasons
        assert len(result.failed_reasons) >= 3

    def test_undisclosed_salary_passes_with_warning(self) -> None:
        """Undisclosed salary should pass with warning."""
        persona = MockPersonaNonNegotiables(
            remote_preference="No Preference",
            minimum_base_salary=100000,
            commutable_cities=[],
            industry_exclusions=[],
            visa_sponsorship_required=False,
        )
        job = MockJobForFilter(
            id=uuid4(),
            work_model="Remote",
            salary_max=None,  # Undisclosed
            location=None,
            industry=None,
            visa_sponsorship=None,
        )

        result = filter_job_non_negotiables(persona, job)

        assert result.passed is True
        assert any("Salary" in warning for warning in result.warnings)


# =============================================================================
# Scoring Flow Result Structure Tests (§7.2 Steps 3-5)
# =============================================================================


class TestScoringFlowResultStructure:
    """Tests for scoring flow result structure."""

    def test_filtered_job_result_structure(self) -> None:
        """Filtered jobs should have None scores and a filter reason."""
        # This tests the expected structure after filtering fails
        persona = MockPersonaNonNegotiables(
            remote_preference="Remote Only",
            minimum_base_salary=None,
            commutable_cities=[],
            industry_exclusions=[],
            visa_sponsorship_required=False,
        )
        job = MockJobForFilter(
            id=uuid4(),
            work_model="Onsite",
            salary_max=None,
            location=None,
            industry=None,
            visa_sponsorship=None,
        )

        filter_result = filter_job_non_negotiables(persona, job)

        # The Strategist would create a ScoreResult like this:
        assert filter_result.passed is False
        # When creating ScoreResult for filtered job:
        # - fit_score = None
        # - stretch_score = None
        # - filtered_reason = "|".join(filter_result.failed_reasons)
        expected_filter_reason = "|".join(filter_result.failed_reasons)
        assert len(expected_filter_reason) > 0

    def test_passing_job_gets_scored(self) -> None:
        """Jobs passing filter should proceed to scoring."""
        persona = MockPersonaNonNegotiables(
            remote_preference="No Preference",
            minimum_base_salary=None,
            commutable_cities=[],
            industry_exclusions=[],
            visa_sponsorship_required=False,
        )
        job = MockJobForFilter(
            id=uuid4(),
            work_model="Remote",
            salary_max=150000,
            location=None,
            industry="Technology",
            visa_sponsorship=True,
        )

        filter_result = filter_job_non_negotiables(persona, job)

        assert filter_result.passed is True
        # When creating ScoreResult for passing job:
        # - fit_score = calculated value (0-100)
        # - stretch_score = calculated value (0-100)
        # - filtered_reason = None


# =============================================================================
# Mixed Jobs Processing Tests (§7.2 Complete Flow)
# =============================================================================


class TestScoringFlowMixedJobs:
    """Tests for processing multiple jobs with mixed filter results."""

    def test_batch_filters_correctly_separates_jobs(self) -> None:
        """Batch processing should separate passing and filtered jobs."""
        persona = MockPersonaNonNegotiables(
            remote_preference="Remote Only",
            minimum_base_salary=100000,
            commutable_cities=[],
            industry_exclusions=[],
            visa_sponsorship_required=False,
        )

        jobs = [
            # Job 1: Passes all filters
            MockJobForFilter(
                id=uuid4(),
                work_model="Remote",
                salary_max=150000,
                location=None,
                industry="Technology",
                visa_sponsorship=None,
            ),
            # Job 2: Fails remote preference
            MockJobForFilter(
                id=uuid4(),
                work_model="Onsite",
                salary_max=200000,
                location=None,
                industry="Technology",
                visa_sponsorship=None,
            ),
            # Job 3: Passes all filters
            MockJobForFilter(
                id=uuid4(),
                work_model="Remote",
                salary_max=120000,
                location=None,
                industry="Finance",
                visa_sponsorship=None,
            ),
            # Job 4: Fails salary minimum
            MockJobForFilter(
                id=uuid4(),
                work_model="Remote",
                salary_max=80000,
                location=None,
                industry="Technology",
                visa_sponsorship=None,
            ),
        ]

        passing_jobs: list[MockJobForFilter] = []
        filtered_jobs: list[tuple[MockJobForFilter, list[str]]] = []

        for job in jobs:
            result = filter_job_non_negotiables(persona, job)
            if result.passed:
                passing_jobs.append(job)
            else:
                filtered_jobs.append((job, result.failed_reasons))

        # Job 1 and 3 pass, Job 2 and 4 fail
        assert len(passing_jobs) == 2
        assert len(filtered_jobs) == 2

    def test_all_jobs_pass(self) -> None:
        """All jobs passing should result in empty filtered list."""
        persona = MockPersonaNonNegotiables(
            remote_preference="No Preference",
            minimum_base_salary=None,
            commutable_cities=[],
            industry_exclusions=[],
            visa_sponsorship_required=False,
        )

        jobs = [
            MockJobForFilter(
                id=uuid4(),
                work_model="Remote",
                salary_max=100000,
                location=None,
                industry="Technology",
                visa_sponsorship=None,
            )
            for _ in range(5)
        ]

        passing_jobs = []
        filtered_jobs = []

        for job in jobs:
            result = filter_job_non_negotiables(persona, job)
            if result.passed:
                passing_jobs.append(job)
            else:
                filtered_jobs.append(job)

        assert len(passing_jobs) == 5
        assert len(filtered_jobs) == 0

    def test_all_jobs_fail(self) -> None:
        """All jobs failing should result in empty passing list."""
        persona = MockPersonaNonNegotiables(
            remote_preference="Remote Only",
            minimum_base_salary=None,
            commutable_cities=[],
            industry_exclusions=[],
            visa_sponsorship_required=False,
        )

        jobs = [
            MockJobForFilter(
                id=uuid4(),
                work_model="Onsite",  # All fail remote
                salary_max=100000,
                location=None,
                industry="Technology",
                visa_sponsorship=None,
            )
            for _ in range(5)
        ]

        passing_jobs = []
        filtered_jobs = []

        for job in jobs:
            result = filter_job_non_negotiables(persona, job)
            if result.passed:
                passing_jobs.append(job)
            else:
                filtered_jobs.append(job)

        assert len(passing_jobs) == 0
        assert len(filtered_jobs) == 5

    def test_empty_jobs_list(self) -> None:
        """Empty jobs list should return empty results."""
        persona = MockPersonaNonNegotiables(
            remote_preference="No Preference",
            minimum_base_salary=None,
            commutable_cities=[],
            industry_exclusions=[],
            visa_sponsorship_required=False,
        )

        jobs: list[MockJobForFilter] = []

        passing_jobs = []
        filtered_jobs = []

        for job in jobs:
            result = filter_job_non_negotiables(persona, job)
            if result.passed:
                passing_jobs.append(job)
            else:
                filtered_jobs.append(job)

        assert len(passing_jobs) == 0
        assert len(filtered_jobs) == 0


# =============================================================================
# Scoring Flow Service Tests
# =============================================================================


class TestScoringFlowService:
    """Tests for the scoring_flow service functions."""

    def test_filter_job_non_negotiables_passes(self) -> None:
        """filter_job_non_negotiables should return passed=True for valid job."""
        persona = MockPersonaNonNegotiables(
            remote_preference="No Preference",
            minimum_base_salary=None,
            commutable_cities=[],
            industry_exclusions=[],
            visa_sponsorship_required=False,
        )
        job = MockJobForFilter(
            id=uuid4(),
            work_model="Remote",
            salary_max=150000,
            location=None,
            industry="Technology",
            visa_sponsorship=None,
        )

        result = filter_job_non_negotiables(persona, job)

        assert result.passed is True
        assert result.job_id == job.id
        assert len(result.failed_reasons) == 0

    def test_filter_job_non_negotiables_fails(self) -> None:
        """filter_job_non_negotiables should return passed=False for invalid job."""
        persona = MockPersonaNonNegotiables(
            remote_preference="Remote Only",
            minimum_base_salary=None,
            commutable_cities=[],
            industry_exclusions=[],
            visa_sponsorship_required=False,
        )
        job = MockJobForFilter(
            id=uuid4(),
            work_model="Onsite",
            salary_max=None,
            location=None,
            industry=None,
            visa_sponsorship=None,
        )

        result = filter_job_non_negotiables(persona, job)

        assert result.passed is False
        assert result.job_id == job.id
        assert len(result.failed_reasons) > 0

    def test_filter_jobs_batch_separates_correctly(self) -> None:
        """filter_jobs_batch should separate passing and filtered jobs."""
        persona = MockPersonaNonNegotiables(
            remote_preference="Remote Only",
            minimum_base_salary=None,
            commutable_cities=[],
            industry_exclusions=[],
            visa_sponsorship_required=False,
        )
        jobs = [
            MockJobForFilter(
                id=uuid4(),
                work_model="Remote",  # Passes
                salary_max=None,
                location=None,
                industry=None,
                visa_sponsorship=None,
            ),
            MockJobForFilter(
                id=uuid4(),
                work_model="Onsite",  # Fails
                salary_max=None,
                location=None,
                industry=None,
                visa_sponsorship=None,
            ),
        ]

        passing, filtered = filter_jobs_batch(persona, jobs)

        assert len(passing) == 1
        assert len(filtered) == 1
        assert passing[0].work_model == "Remote"
        assert filtered[0].passed is False

    def test_build_filtered_score_result(self) -> None:
        """build_filtered_score_result should create correct ScoreResult."""
        filter_result = JobFilterResult(
            job_id=uuid4(),
            passed=False,
            failed_reasons=["salary_below_minimum", "remote_preference_not_met"],
            warnings=[],
        )

        score_result = build_filtered_score_result(filter_result)

        assert score_result["job_posting_id"] == str(filter_result.job_id)
        assert score_result["fit_score"] is None
        assert score_result["stretch_score"] is None
        assert score_result["explanation"] is None
        assert (
            score_result["filtered_reason"]
            == "salary_below_minimum|remote_preference_not_met"
        )

    def test_build_scored_result(self) -> None:
        """build_scored_result should create correct ScoreResult with scores."""
        job_id = uuid4()

        score_result = build_scored_result(
            job_id=job_id,
            fit_score=85.5,
            stretch_score=72.0,
            explanation="Strong technical match",
        )

        assert score_result["job_posting_id"] == str(job_id)
        assert score_result["fit_score"] == 85.5
        assert score_result["stretch_score"] == 72.0
        assert score_result["explanation"] == "Strong technical match"
        assert score_result["filtered_reason"] is None

    def test_build_scored_result_without_explanation(self) -> None:
        """build_scored_result should work without explanation."""
        job_id = uuid4()

        score_result = build_scored_result(
            job_id=job_id,
            fit_score=90.0,
            stretch_score=60.0,
        )

        assert score_result["fit_score"] == 90.0
        assert score_result["explanation"] is None
        assert score_result["filtered_reason"] is None

    def test_build_scored_result_validates_fit_score_too_low(self) -> None:
        """build_scored_result should reject fit_score below 0."""
        import pytest

        with pytest.raises(ValueError, match="fit_score must be 0-100"):
            build_scored_result(
                job_id=uuid4(),
                fit_score=-5.0,
                stretch_score=50.0,
            )

    def test_build_scored_result_validates_fit_score_too_high(self) -> None:
        """build_scored_result should reject fit_score above 100."""
        import pytest

        with pytest.raises(ValueError, match="fit_score must be 0-100"):
            build_scored_result(
                job_id=uuid4(),
                fit_score=150.0,
                stretch_score=50.0,
            )

    def test_build_scored_result_validates_stretch_score_too_low(self) -> None:
        """build_scored_result should reject stretch_score below 0."""
        import pytest

        with pytest.raises(ValueError, match="stretch_score must be 0-100"):
            build_scored_result(
                job_id=uuid4(),
                fit_score=50.0,
                stretch_score=-10.0,
            )

    def test_build_scored_result_validates_stretch_score_too_high(self) -> None:
        """build_scored_result should reject stretch_score above 100."""
        import pytest

        with pytest.raises(ValueError, match="stretch_score must be 0-100"):
            build_scored_result(
                job_id=uuid4(),
                fit_score=50.0,
                stretch_score=105.0,
            )

    def test_build_scored_result_accepts_boundary_values(self) -> None:
        """build_scored_result should accept scores at 0 and 100."""
        job_id = uuid4()

        # Both at 0
        result_zero = build_scored_result(
            job_id=job_id,
            fit_score=0.0,
            stretch_score=0.0,
        )
        assert result_zero["fit_score"] == 0.0
        assert result_zero["stretch_score"] == 0.0

        # Both at 100
        result_max = build_scored_result(
            job_id=job_id,
            fit_score=100.0,
            stretch_score=100.0,
        )
        assert result_max["fit_score"] == 100.0
        assert result_max["stretch_score"] == 100.0

    def test_build_filtered_score_result_empty_reasons(self) -> None:
        """build_filtered_score_result should return None for empty reasons."""
        filter_result = JobFilterResult(
            job_id=uuid4(),
            passed=False,
            failed_reasons=[],  # Edge case: empty reasons
            warnings=[],
        )

        score_result = build_filtered_score_result(filter_result)

        # Should be None, not empty string
        assert score_result["filtered_reason"] is None
