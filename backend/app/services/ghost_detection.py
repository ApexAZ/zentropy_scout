"""Ghost detection service for job postings.

REQ-007 §6.5 + REQ-003 §7: Calculates ghost score to identify potentially
stale or suspicious job postings.

Ghost Score Formula:
    ghost_score = (days_open_score * 0.30) +
                  (repost_score * 0.30) +
                  (vagueness_score * 0.20) +
                  (missing_fields_score * 0.10) +
                  (requirement_mismatch_score * 0.10)

Score Interpretation (REQ-003 §7.3):
    0-25:  Fresh - No warning
    26-50: Moderate - Light warning about age/history
    51-75: Elevated - Clear warning, recommend verification
    76-100: High Risk - Strong warning, suggest skipping
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from app.providers import ProviderError, factory
from app.providers.llm.base import LLMMessage, TaskType

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# WHY: Weights from REQ-003 §7.2. These determine how much each signal
# contributes to the final ghost score.
DAYS_OPEN_WEIGHT = 0.30
REPOST_WEIGHT = 0.30
VAGUENESS_WEIGHT = 0.20
MISSING_FIELDS_WEIGHT = 0.10
REQUIREMENT_MISMATCH_WEIGHT = 0.10

# WHY: Thresholds for days_open scoring per REQ-003 §7.2.
# 0-30 days = fresh (0), 31-60 = moderate (50), 60+ = stale (100)
DAYS_FRESH_THRESHOLD = 30
DAYS_MODERATE_THRESHOLD = 60

# WHY: Expected years of experience range by seniority level.
# Used to detect mismatches (e.g., "Senior" role asking for 1 year,
# or "Entry" role asking for 10 years).
SENIORITY_MIN_YEARS: dict[str, int] = {
    "Entry": 0,
    "Mid": 2,
    "Senior": 5,
    "Lead": 7,
    "Executive": 10,
}

# Maximum expected years by seniority (Entry/Mid asking for 10+ is suspicious)
SENIORITY_MAX_YEARS: dict[str, int] = {
    "Entry": 2,
    "Mid": 5,
    "Senior": 99,  # No upper limit for Senior+
    "Lead": 99,
    "Executive": 99,
}


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class GhostSignals:
    """Container for ghost detection signals.

    REQ-003 §7.5: Structure for JSONB storage in ghost_signals column.
    """

    # Days open signal
    days_open: int
    days_open_score: int

    # Repost signal
    repost_count: int
    repost_score: int

    # Vagueness signal (LLM-assessed)
    vagueness_score: int

    # Missing fields signal
    missing_fields: list[str]
    missing_fields_score: int

    # Requirement mismatch signal
    requirement_mismatch: bool
    requirement_mismatch_score: int

    # Metadata
    calculated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Final score (calculated)
    ghost_score: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSONB storage.

        Returns:
            Dict suitable for storing in ghost_signals JSONB column.

        Note:
            Uses Any for values because JSONB dict contains mixed types
            (int, str, bool, list, datetime as ISO string).
        """
        return {
            "days_open": self.days_open,
            "days_open_score": self.days_open_score,
            "repost_count": self.repost_count,
            "repost_score": self.repost_score,
            "vagueness_score": self.vagueness_score,
            "missing_fields": self.missing_fields,
            "missing_fields_score": self.missing_fields_score,
            "requirement_mismatch": self.requirement_mismatch,
            "requirement_mismatch_score": self.requirement_mismatch_score,
            "calculated_at": self.calculated_at.isoformat(),
            "ghost_score": self.ghost_score,
        }


# =============================================================================
# Individual Signal Calculations
# =============================================================================


def calculate_days_open_score(
    posted_date: date | None,
    first_seen_date: date | None = None,
) -> int:
    """Calculate score based on how long the job has been posted.

    REQ-003 §7.2: Days open scoring:
    - 0-30 days: 0 (fresh)
    - 31-60 days: 50 (moderate)
    - 60+ days: 100 (stale)

    Args:
        posted_date: Original posting date (preferred).
        first_seen_date: When we first discovered the posting (fallback).

    Returns:
        Score 0-100 based on posting age.
    """
    # Use posted_date if available, otherwise first_seen_date
    effective_date = posted_date or first_seen_date

    # Benefit of the doubt if we have no date info
    if effective_date is None:
        return 0

    days_open = (date.today() - effective_date).days

    if days_open <= DAYS_FRESH_THRESHOLD:
        return 0
    if days_open <= DAYS_MODERATE_THRESHOLD:
        return 50
    return 100


def calculate_repost_score(repost_count: int) -> int:
    """Calculate score based on number of reposts.

    REQ-003 §7.2: Repost scoring:
    - 0: 0 (first posting)
    - 1: 30
    - 2: 60
    - 3+: 100 (frequent reposter)

    Args:
        repost_count: Number of times this job has been reposted.

    Returns:
        Score 0-100 based on repost frequency.
    """
    if repost_count == 0:
        return 0
    if repost_count == 1:
        return 30
    if repost_count == 2:
        return 60
    return 100


def calculate_missing_fields_score(
    salary_min: int | None,
    salary_max: int | None,
    application_deadline: date | None,
    location: str | None,
) -> int:
    """Calculate score based on missing critical fields.

    REQ-003 §7.2: Missing salary, deadline, location each add ~33 points.

    Args:
        salary_min: Minimum salary (either min or max counts as present).
        salary_max: Maximum salary.
        application_deadline: Application deadline date.
        location: Job location.

    Returns:
        Score 0-100 based on number of missing fields.
    """
    missing_count = 0

    # Salary is missing if both min and max are None
    if salary_min is None and salary_max is None:
        missing_count += 1

    if application_deadline is None:
        missing_count += 1

    if location is None:
        missing_count += 1

    # Each missing field = 33 points (3 fields total)
    # 0 missing = 0, 1 missing = 33, 2 missing = 67, 3 missing = 100
    if missing_count == 0:
        return 0
    if missing_count == 1:
        return 33
    if missing_count == 2:
        return 67
    return 100


def calculate_requirement_mismatch_score(
    seniority_level: str | None,
    years_experience_min: int | None,
) -> int:
    """Calculate score based on seniority/experience mismatch.

    REQ-003 §7.2: Detects suspicious mismatches like "Senior" role
    asking for only 1-2 years experience, or "Entry" role asking for 10 years.

    Args:
        seniority_level: Job seniority (Entry, Mid, Senior, Lead, Executive).
        years_experience_min: Minimum years of experience requested.

    Returns:
        100 if mismatch detected, 0 otherwise.
    """
    # Can't determine mismatch without seniority level
    if seniority_level is None:
        return 0

    # No years specified - can't detect mismatch
    if years_experience_min is None:
        return 0

    # Get expected bounds for this seniority
    expected_min = SENIORITY_MIN_YEARS.get(seniority_level)
    expected_max = SENIORITY_MAX_YEARS.get(seniority_level)

    if expected_min is None or expected_max is None:
        return 0

    # Check for mismatch: years requested too low OR too high for seniority
    # WHY: "Senior" asking for < 3 years is suspicious (bait-and-switch).
    # "Entry" asking for 10 years is also suspicious (misclassified job).
    if years_experience_min < expected_min - 2:
        return 100
    if years_experience_min > expected_max + 2:
        return 100

    return 0


async def calculate_vagueness_score(description: str) -> int:
    """Calculate vagueness score using LLM assessment.

    REQ-003 §7.2: LLM assesses how vague or specific the job description is.
    Uses Haiku/cheap model for cost efficiency.

    Args:
        description: Job description text to assess.

    Returns:
        Score 0-100 where higher = more vague.
    """
    prompt = """Assess the vagueness of this job description on a scale of 0-100.

0 = Very specific (clear responsibilities, concrete requirements, specific tech stack)
50 = Moderate (some specifics but missing key details)
100 = Very vague (generic phrases, no concrete requirements, "fast-paced environment" clichés)

Respond with ONLY a number between 0 and 100.

Job Description:
"""
    try:
        llm = factory.get_llm_provider()
        response = await llm.complete(
            messages=[
                # WHY 2000 chars: Vagueness assessment only needs enough text to assess
                # specificity. Longer text increases cost without improving accuracy.
                LLMMessage(role="user", content=prompt + description[:2000]),
            ],
            task=TaskType.GHOST_DETECTION,
        )

        # Extract number from response (including negative)
        content = response.content or ""
        numbers = re.findall(r"-?\d+", content)
        if numbers:
            score = int(numbers[0])
            # Clamp to 0-100
            return max(0, min(100, score))

        # Default to middle if can't parse
        return 50

    except ProviderError as e:
        logger.warning("Vagueness assessment failed (%s), using default score", e)
        return 50


# =============================================================================
# Main Ghost Score Calculation
# =============================================================================


def _get_missing_fields(
    salary_min: int | None,
    salary_max: int | None,
    application_deadline: date | None,
    location: str | None,
) -> list[str]:
    """Get list of missing critical field names.

    Args:
        salary_min: Minimum salary.
        salary_max: Maximum salary.
        application_deadline: Application deadline date.
        location: Job location.

    Returns:
        List of missing field names (e.g., ["salary", "deadline"]).
    """
    missing = []

    if salary_min is None and salary_max is None:
        missing.append("salary")

    if application_deadline is None:
        missing.append("deadline")

    if location is None:
        missing.append("location")

    return missing


async def calculate_ghost_score(
    posted_date: date | None,
    first_seen_date: date | None,
    repost_count: int,
    salary_min: int | None,
    salary_max: int | None,
    application_deadline: date | None,
    location: str | None,
    seniority_level: str | None,
    years_experience_min: int | None,
    description: str,
) -> GhostSignals:
    """Calculate full ghost score with all signals.

    REQ-007 §6.5 + REQ-003 §7: Weighted sum of all ghost detection signals.

    Args:
        posted_date: Original posting date.
        first_seen_date: When we first discovered the posting.
        repost_count: Number of times reposted.
        salary_min: Minimum salary.
        salary_max: Maximum salary.
        application_deadline: Application deadline.
        location: Job location.
        seniority_level: Job seniority level.
        years_experience_min: Minimum years experience requested.
        description: Job description text.

    Returns:
        GhostSignals with all signal values and final ghost_score.
    """
    # Calculate individual signals
    days_open_score = calculate_days_open_score(posted_date, first_seen_date)
    repost_score = calculate_repost_score(repost_count)
    missing_fields_score = calculate_missing_fields_score(
        salary_min, salary_max, application_deadline, location
    )
    requirement_mismatch_score = calculate_requirement_mismatch_score(
        seniority_level, years_experience_min
    )
    vagueness_score = await calculate_vagueness_score(description)

    # Calculate weighted score
    weighted_score = (
        (days_open_score * DAYS_OPEN_WEIGHT)
        + (repost_score * REPOST_WEIGHT)
        + (vagueness_score * VAGUENESS_WEIGHT)
        + (missing_fields_score * MISSING_FIELDS_WEIGHT)
        + (requirement_mismatch_score * REQUIREMENT_MISMATCH_WEIGHT)
    )

    # Calculate days open for metadata
    effective_date = posted_date or first_seen_date
    days_open = (date.today() - effective_date).days if effective_date else 0

    # Detect requirement mismatch
    has_mismatch = requirement_mismatch_score == 100

    return GhostSignals(
        days_open=days_open,
        days_open_score=days_open_score,
        repost_count=repost_count,
        repost_score=repost_score,
        vagueness_score=vagueness_score,
        missing_fields=_get_missing_fields(
            salary_min, salary_max, application_deadline, location
        ),
        missing_fields_score=missing_fields_score,
        requirement_mismatch=has_mismatch,
        requirement_mismatch_score=requirement_mismatch_score,
        ghost_score=round(weighted_score),
    )
