"""Experience level match calculation for Fit Score.

REQ-008 §4.4: Experience Level Match component (25% of Fit Score).

Compares user's years of experience against job requirements.
Under-qualified users receive heavier penalties than over-qualified.

Key formulas:
- Under-qualified: score = max(0, 100 - (gap * 15))
- Over-qualified: score = max(50, 100 - (gap * 5))
- No requirements: score = 70 (neutral)

Rationale: Under-qualified is penalized 3x more than over-qualified because
employers strongly prefer candidates who meet requirements, but are less
concerned about "overqualified" candidates (who may just want the job).
"""

from app.services.fit_score import FIT_NEUTRAL_SCORE

# =============================================================================
# Constants
# =============================================================================

# Penalty per year under minimum requirement
_UNDER_QUALIFIED_PENALTY_PER_YEAR = 15

# Penalty per year over maximum requirement
_OVER_QUALIFIED_PENALTY_PER_YEAR = 5

# Floor for under-qualified (can go to 0)
_UNDER_QUALIFIED_FLOOR = 0

# Floor for over-qualified (can't go below 50)
# WHY: Over-qualified candidates are still viable, just less ideal
_OVER_QUALIFIED_FLOOR = 50

# Maximum reasonable years of experience to prevent DoS
# WHY: Matches defensive pattern in hard_skills_match.py and soft_skills_match.py
_MAX_YEARS = 100


# =============================================================================
# Experience Level Score Calculation (REQ-008 §4.4)
# =============================================================================


def calculate_experience_score(
    user_years: float | int | None,
    job_min_years: float | int | None,
    job_max_years: float | int | None,
) -> float:
    """Calculate experience level match score (0-100).

    REQ-008 §4.4: Experience Level Match (25% of Fit Score).

    Compares user's years of experience against job requirements,
    applying penalties for under-qualification (heavy) or
    over-qualification (light).

    Args:
        user_years: User's total years of experience. None → 0.
        job_min_years: Job's minimum years required. None if unspecified.
        job_max_years: Job's maximum years (upper bound). None if unspecified.

    Returns:
        Experience score 0-100:
        - 100: Perfect match (within range or meets requirement)
        - 70: Neutral (no requirements specified)
        - 0-99: Under-qualified (penalty based on gap)
        - 50-99: Over-qualified (lighter penalty, floor at 50)

    Raises:
        ValueError: If any value is negative, exceeds max, or if min > max.

    Examples:
        >>> calculate_experience_score(6, 5, 8)  # Within range
        100.0
        >>> calculate_experience_score(3, 5, 8)  # 2 years under
        70.0
        >>> calculate_experience_score(12, 5, 8)  # 4 years over
        80.0
        >>> calculate_experience_score(5, None, None)  # No requirements
        70.0
    """
    # Normalize None user experience to 0
    # WHY: New users may not have set years_experience yet (REQ-001)
    effective_user_years = user_years if user_years is not None else 0

    # Validate inputs are non-negative
    if effective_user_years < 0:
        msg = "User years cannot be negative"
        raise ValueError(msg)

    if job_min_years is not None and job_min_years < 0:
        msg = "Job minimum years cannot be negative"
        raise ValueError(msg)

    if job_max_years is not None and job_max_years < 0:
        msg = "Job maximum years cannot be negative"
        raise ValueError(msg)

    # Validate upper bounds (defensive against unreasonable values)
    if effective_user_years > _MAX_YEARS:
        msg = f"User years ({effective_user_years}) exceeds maximum of {_MAX_YEARS}"
        raise ValueError(msg)

    if job_min_years is not None and job_min_years > _MAX_YEARS:
        msg = f"Job minimum years ({job_min_years}) exceeds maximum of {_MAX_YEARS}"
        raise ValueError(msg)

    if job_max_years is not None and job_max_years > _MAX_YEARS:
        msg = f"Job maximum years ({job_max_years}) exceeds maximum of {_MAX_YEARS}"
        raise ValueError(msg)

    # Validate min <= max when both specified
    if (
        job_min_years is not None
        and job_max_years is not None
        and job_min_years > job_max_years
    ):
        msg = (
            f"Job min years ({job_min_years}) cannot exceed max years ({job_max_years})"
        )
        raise ValueError(msg)

    # Case 1: No requirements specified → neutral score
    if job_min_years is None and job_max_years is None:
        return FIT_NEUTRAL_SCORE

    # Case 2: Range specified (min AND max)
    if job_min_years is not None and job_max_years is not None:
        if job_min_years <= effective_user_years <= job_max_years:
            # Perfect fit: within range
            return 100.0
        elif effective_user_years < job_min_years:
            # Under-qualified
            gap = job_min_years - effective_user_years
            return max(
                _UNDER_QUALIFIED_FLOOR,
                100 - (gap * _UNDER_QUALIFIED_PENALTY_PER_YEAR),
            )
        else:
            # Over-qualified (user_years > job_max_years)
            gap = effective_user_years - job_max_years
            return max(
                _OVER_QUALIFIED_FLOOR,
                100 - (gap * _OVER_QUALIFIED_PENALTY_PER_YEAR),
            )

    # Case 3: Minimum only specified
    if job_min_years is not None:
        if effective_user_years >= job_min_years:
            # Meets or exceeds minimum
            return 100.0
        # Under-qualified
        gap = job_min_years - effective_user_years
        return max(
            _UNDER_QUALIFIED_FLOOR,
            100 - (gap * _UNDER_QUALIFIED_PENALTY_PER_YEAR),
        )

    # Case 4: Maximum only specified (unusual)
    # This is the final case - if job_min_years is None, job_max_years must be set
    # (we already returned for both-None case above)
    if effective_user_years <= job_max_years:  # type: ignore[operator]
        # Under or at maximum
        return 100.0
    # Over-qualified
    gap = effective_user_years - job_max_years  # type: ignore[operator]
    return max(
        _OVER_QUALIFIED_FLOOR,
        100 - (gap * _OVER_QUALIFIED_PENALTY_PER_YEAR),
    )
