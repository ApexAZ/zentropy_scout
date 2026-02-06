"""Location/logistics match calculation for Fit Score.

REQ-008 §4.6: Location/Logistics component (10% of Fit Score).

Compares user's location/work model preferences against job requirements.
Two-step calculation:
1. Work model preference matrix (Remote Only, Hybrid OK, Onsite OK)
2. Location proximity modifier for non-remote jobs

Key scoring rules:
- Remote Only + Remote = 100
- Remote Only + Hybrid = 50
- Remote Only + Onsite = 0
- Hybrid OK + Remote/Hybrid = 100
- Hybrid OK + Onsite = 60
- Onsite OK + Any = 100

Location modifier (non-remote only):
- Job in commutable city: no penalty
- Job NOT in commutable city: score * 0.7 (30% penalty)
"""

from app.services.fit_score import FIT_NEUTRAL_SCORE

# =============================================================================
# Constants
# =============================================================================

# Remote preference constants
REMOTE_ONLY = "Remote Only"
HYBRID_OK = "Hybrid OK"
ONSITE_OK = "Onsite OK"

# Valid remote preference values
_VALID_REMOTE_PREFERENCES = frozenset({REMOTE_ONLY, HYBRID_OK, ONSITE_OK})

# Valid job work model values
_VALID_WORK_MODELS = frozenset({"Remote", "Hybrid", "Onsite"})

# Maximum commutable cities to prevent DoS
_MAX_COMMUTABLE_CITIES = 1000

# Location proximity penalty multiplier for non-commutable locations
_NON_COMMUTABLE_PENALTY_MULTIPLIER = 0.7

# =============================================================================
# Work Model Score Matrix (REQ-008 §4.6)
# =============================================================================

# Score matrix: (remote_preference, job_work_model) -> base_score
_WORK_MODEL_SCORES: dict[tuple[str, str], float] = {
    # Remote Only preference
    (REMOTE_ONLY, "Remote"): 100.0,
    (REMOTE_ONLY, "Hybrid"): 50.0,
    (REMOTE_ONLY, "Onsite"): 0.0,
    # Hybrid OK preference
    (HYBRID_OK, "Remote"): 100.0,
    (HYBRID_OK, "Hybrid"): 100.0,
    (HYBRID_OK, "Onsite"): 60.0,
    # Onsite OK preference (most flexible)
    (ONSITE_OK, "Remote"): 100.0,
    (ONSITE_OK, "Hybrid"): 100.0,
    (ONSITE_OK, "Onsite"): 100.0,
}


# =============================================================================
# Location/Logistics Score Calculation (REQ-008 §4.6)
# =============================================================================


def calculate_logistics_score(
    remote_preference: str | None,
    commutable_cities: list[str] | None,
    job_work_model: str | None,
    job_location: str | None,
) -> float:
    """Calculate location/logistics match score (0-100).

    REQ-008 §4.6: Location/Logistics (10% of Fit Score).

    Uses two-step calculation:
    1. Work model preference matrix → base score
    2. Location proximity modifier → penalty if non-commutable

    Args:
        remote_preference: User's work model preference.
            One of: "Remote Only", "Hybrid OK", "Onsite OK", or None/empty.
        commutable_cities: List of city names user can commute to.
            None or empty means location check is skipped.
        job_work_model: Job's work model requirement.
            One of: "Remote", "Hybrid", "Onsite", or None/empty.
        job_location: Job's physical location for non-remote jobs.
            None for remote jobs or when unspecified.

    Returns:
        Location/logistics score 0-100:
        - 100: Perfect work model match
        - 70: Neutral (missing data)
        - 0-100: Based on preference matrix and location penalty

    Raises:
        ValueError: If remote_preference or job_work_model is invalid,
            or if commutable_cities exceeds maximum size.
    """
    # Normalize empty/whitespace strings to None
    effective_preference = (
        remote_preference.strip()
        if remote_preference and remote_preference.strip()
        else None
    )
    effective_work_model = (
        job_work_model.strip() if job_work_model and job_work_model.strip() else None
    )

    # Handle missing data → neutral score
    if effective_preference is None or effective_work_model is None:
        return FIT_NEUTRAL_SCORE

    # Validate remote preference
    if effective_preference not in _VALID_REMOTE_PREFERENCES:
        msg = (
            f"Invalid remote_preference: '{effective_preference}'. "
            f"Must be one of: {', '.join(sorted(_VALID_REMOTE_PREFERENCES))}"
        )
        raise ValueError(msg)

    # Validate job work model
    if effective_work_model not in _VALID_WORK_MODELS:
        msg = (
            f"Invalid job_work_model: '{effective_work_model}'. "
            f"Must be one of: {', '.join(sorted(_VALID_WORK_MODELS))}"
        )
        raise ValueError(msg)

    # Validate commutable cities size (DoS protection)
    if (
        commutable_cities is not None
        and len(commutable_cities) > _MAX_COMMUTABLE_CITIES
    ):
        msg = f"commutable_cities list exceeds maximum size of {_MAX_COMMUTABLE_CITIES}"
        raise ValueError(msg)

    # Step 1: Get base score from work model preference matrix
    base_score = _WORK_MODEL_SCORES[(effective_preference, effective_work_model)]

    # Step 2: Apply location proximity modifier for non-remote jobs
    # Skipped if:
    # - Job is Remote (location doesn't matter)
    # - commutable_cities is None or empty (user didn't define preferences)
    # - Job location is in user's commutable cities
    if (
        effective_work_model != "Remote"
        and commutable_cities
        and not _is_location_commutable(job_location, commutable_cities)
    ):
        base_score *= _NON_COMMUTABLE_PENALTY_MULTIPLIER

    return base_score


def _is_location_commutable(
    job_location: str | None,
    commutable_cities: list[str],
) -> bool:
    """Check if job location is in user's commutable cities.

    Performs case-insensitive, whitespace-normalized comparison.

    Args:
        job_location: Job's physical location (may be None).
        commutable_cities: List of cities user can commute to.

    Returns:
        True if job location matches any commutable city, False otherwise.
    """
    if not job_location:
        return False

    # Normalize job location
    normalized_location = job_location.strip().lower()
    if not normalized_location:
        return False

    # Check against normalized commutable cities
    normalized_cities = {city.strip().lower() for city in commutable_cities if city}
    return normalized_location in normalized_cities
