"""Scoring flow service for job scoring.

REQ-007 §7.2 / REQ-017 §6: Scoring Flow.

Orchestrates the complete scoring flow:
1. Non-negotiables filtering (pass/fail gate)
2. Score calculation for passing jobs
3. Result aggregation into ScoreResult format

Called by JobScoringService.score_batch() in job_scoring_service.py.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar
from uuid import UUID

from app.services.non_negotiables_filter import (
    NonNegotiablesResult,
    aggregate_filter_results,
    check_commutable_cities,
    check_industry_exclusions,
    check_minimum_salary,
    check_remote_preference,
    check_visa_sponsorship,
)
from app.services.score_types import ScoreResult

_JobT = TypeVar("_JobT", bound="JobFilterDataLike")

# =============================================================================
# Protocol Definitions (for dependency injection)
# =============================================================================


class PersonaNonNegotiablesLike(Protocol):
    """Protocol for persona non-negotiables data.

    Matches the fields needed from Persona for non-negotiables filtering.
    """

    @property
    def remote_preference(self) -> str:
        """Work model preference (Remote Only, Hybrid OK, etc.)."""
        ...

    @property
    def minimum_base_salary(self) -> int | None:
        """Minimum acceptable base salary."""
        ...

    @property
    def commutable_cities(self) -> list[str]:
        """Cities user can commute to."""
        ...

    @property
    def industry_exclusions(self) -> list[str]:
        """Industries to exclude from search."""
        ...

    @property
    def visa_sponsorship_required(self) -> bool:
        """Whether visa sponsorship is required."""
        ...


class JobFilterDataLike(Protocol):
    """Protocol for job data needed for non-negotiables filtering.

    Matches the fields needed from JobPosting for filtering.
    """

    @property
    def id(self) -> UUID:
        """Job posting ID."""
        ...

    @property
    def work_model(self) -> str | None:
        """Work model (Remote, Hybrid, Onsite)."""
        ...

    @property
    def salary_max(self) -> int | None:
        """Maximum salary offered."""
        ...

    @property
    def location(self) -> str | None:
        """Job location."""
        ...

    @property
    def industry(self) -> str | None:
        """Company industry."""
        ...

    @property
    def visa_sponsorship(self) -> bool | None:
        """Whether visa sponsorship is offered."""
        ...


# =============================================================================
# Filter Result
# =============================================================================


@dataclass
class JobFilterResult:
    """Result of non-negotiables filtering for a single job.

    Attributes:
        job_id: UUID of the job posting.
        passed: Whether the job passed all non-negotiables.
        failed_reasons: List of failure reasons if not passed.
        warnings: List of warnings (e.g., undisclosed data).
    """

    job_id: UUID
    passed: bool
    failed_reasons: list[str]
    warnings: list[str]


# =============================================================================
# Non-Negotiables Filter Functions
# =============================================================================


def filter_job_non_negotiables(
    persona: PersonaNonNegotiablesLike,
    job: JobFilterDataLike,
) -> JobFilterResult:
    """Apply all non-negotiables filters to a single job.

    REQ-007 §7.2 Step 1: Non-Negotiables Filter (Pass/Fail).

    Checks:
    - Remote preference
    - Minimum salary
    - Commutable cities
    - Industry exclusions
    - Visa sponsorship

    Args:
        persona: Persona with non-negotiables preferences.
        job: Job posting to filter.

    Returns:
        JobFilterResult with pass/fail status and reasons.
    """
    results: list[NonNegotiablesResult] = [
        check_remote_preference(persona.remote_preference, job.work_model),
        check_minimum_salary(persona.minimum_base_salary, job.salary_max),
        check_commutable_cities(
            persona.commutable_cities, job.location, job.work_model
        ),
        check_industry_exclusions(persona.industry_exclusions, job.industry),
        check_visa_sponsorship(persona.visa_sponsorship_required, job.visa_sponsorship),
    ]

    aggregated = aggregate_filter_results(results)

    return JobFilterResult(
        job_id=job.id,
        passed=aggregated.passed,
        failed_reasons=aggregated.failed_reasons,
        warnings=aggregated.warnings,
    )


def filter_jobs_batch(
    persona: PersonaNonNegotiablesLike,
    jobs: Sequence[_JobT],
) -> tuple[list[_JobT], list[JobFilterResult]]:
    """Filter a batch of jobs using non-negotiables.

    REQ-007 §7.2 Step 1: Non-Negotiables Filter (Pass/Fail).

    Separates jobs into passing and filtered groups.

    Args:
        persona: Persona with non-negotiables preferences.
        jobs: Sequence of job postings to filter.

    Returns:
        Tuple of (passing_jobs, filtered_results).
        - passing_jobs: Jobs that passed all filters (for scoring).
        - filtered_results: JobFilterResult for jobs that failed.
    """
    passing_jobs: list[_JobT] = []
    filtered_results: list[JobFilterResult] = []

    for job in jobs:
        result = filter_job_non_negotiables(persona, job)
        if result.passed:
            passing_jobs.append(job)
        else:
            filtered_results.append(result)

    return passing_jobs, filtered_results


# =============================================================================
# Score Result Builders
# =============================================================================


def build_filtered_score_result(filter_result: JobFilterResult) -> ScoreResult:
    """Build a ScoreResult for a filtered (failed) job.

    REQ-007 §7.2: Jobs failing non-negotiables have None scores.

    Args:
        filter_result: The filter result with failure reasons.

    Returns:
        ScoreResult with None scores and filtered_reason populated.
    """
    # Handle edge case where failed_reasons is empty (should not happen in
    # practice since passed=False implies at least one reason)
    filtered_reason = "|".join(filter_result.failed_reasons) or None
    return ScoreResult(
        job_posting_id=str(filter_result.job_id),
        fit_score=None,
        stretch_score=None,
        explanation=None,
        filtered_reason=filtered_reason,
        score_details=None,
    )


def build_scored_result(
    job_id: UUID,
    fit_score: float,
    stretch_score: float,
    explanation: str | None = None,
    score_details: dict[str, Any] | None = None,
) -> ScoreResult:
    """Build a ScoreResult for a scored (passing) job.

    REQ-007 §7.2 Steps 3-4: Fit and Stretch scores for passing jobs.

    Args:
        job_id: UUID of the job posting.
        fit_score: Calculated Fit Score (0-100).
        stretch_score: Calculated Stretch Score (0-100).
        explanation: Optional score explanation.
        score_details: Optional component breakdown for frontend drill-down
            (REQ-012 Appendix A.3).

    Returns:
        ScoreResult with scores populated.

    Raises:
        ValueError: If scores are outside the valid 0-100 range.
    """
    # Validate score bounds per REQ-007 contract
    if not (0 <= fit_score <= 100):
        msg = f"fit_score must be 0-100, got {fit_score}"
        raise ValueError(msg)
    if not (0 <= stretch_score <= 100):
        msg = f"stretch_score must be 0-100, got {stretch_score}"
        raise ValueError(msg)

    return ScoreResult(
        job_posting_id=str(job_id),
        fit_score=fit_score,
        stretch_score=stretch_score,
        explanation=explanation,
        filtered_reason=None,
        score_details=score_details,
    )
