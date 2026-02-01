"""Fit Score calculation service.

REQ-008 §4: Fit Score — How well user's current skills match job requirements.

Fit Score answers: "Am I qualified for this job as-is?"

Component weights (REQ-008 §4.1):
- Hard Skills Match:    40% — Technical skills alignment
- Soft Skills Match:    15% — Interpersonal/leadership skills
- Experience Level:     25% — Years of experience vs. requirements
- Role Title Match:     10% — Job title similarity to current/past roles
- Location/Logistics:   10% — Work model preference alignment

Total: 100%

Design principles:
1. Each component returns a score 0-100
2. Final score is weighted sum: sum(component * weight)
3. Missing data defaults to 70 (neutral) — see REQ-008 §9.1
4. Proficiency levels matter — "Learning" != "5+ years"
"""

import math
from dataclasses import dataclass

# =============================================================================
# Component Weights (REQ-008 §4.1)
# =============================================================================

# WHY these weights:
# REQ-008 §4.1 defines the relative importance of each component.
# Hard skills are weighted highest because technical qualifications
# are the primary filter for most job applications.

# Hard Skills Match (REQ-008 §4.2)
# Technical skills alignment with proficiency weighting.
# Highest weight because it's the most objective match criteria.
FIT_WEIGHT_HARD_SKILLS = 0.40

# Soft Skills Match (REQ-008 §4.3)
# Interpersonal/leadership skills via embedding similarity.
# Lower weight because soft skills are harder to verify from listings.
FIT_WEIGHT_SOFT_SKILLS = 0.15

# Experience Level (REQ-008 §4.4)
# Years of experience vs. job requirements.
# Second-highest because experience level is a common deal-breaker.
FIT_WEIGHT_EXPERIENCE_LEVEL = 0.25

# Role Title Match (REQ-008 §4.5)
# Job title similarity to user's current/past roles.
# Lower weight because titles vary widely across companies.
FIT_WEIGHT_ROLE_TITLE = 0.10

# Location/Logistics (REQ-008 §4.6)
# Work model preference alignment (remote/hybrid/onsite).
# Lower weight because non-negotiables filter already handles strict rules.
FIT_WEIGHT_LOCATION_LOGISTICS = 0.10


# =============================================================================
# Validation
# =============================================================================

# Weights must sum to 1.0 (100%)
_WEIGHT_SUM = (
    FIT_WEIGHT_HARD_SKILLS
    + FIT_WEIGHT_SOFT_SKILLS
    + FIT_WEIGHT_EXPERIENCE_LEVEL
    + FIT_WEIGHT_ROLE_TITLE
    + FIT_WEIGHT_LOCATION_LOGISTICS
)

# Sanity check at import time (RuntimeError survives python -O, unlike assert)
if abs(_WEIGHT_SUM - 1.0) >= 0.001:
    raise RuntimeError(f"Fit score weights must sum to 1.0, got {_WEIGHT_SUM}")


# =============================================================================
# Neutral Score (REQ-008 §9.1)
# =============================================================================

# When data is missing (job doesn't specify skills, experience, etc.),
# use a neutral score of 70 rather than penalizing or ignoring.
# REQ-008 §9.1: "Missing data reduces confidence, does not break scoring."
FIT_NEUTRAL_SCORE = 70


# =============================================================================
# Component Weight Accessors
# =============================================================================


def get_fit_component_weights() -> dict[str, float]:
    """Return all Fit Score component weights as a dictionary.

    REQ-008 §4.1: Component Weights.

    Returns:
        Dictionary mapping component names to their weights.
        Weights sum to 1.0 (100%).

    Example:
        >>> weights = get_fit_component_weights()
        >>> weights["hard_skills"]
        0.40
    """
    return {
        "hard_skills": FIT_WEIGHT_HARD_SKILLS,
        "soft_skills": FIT_WEIGHT_SOFT_SKILLS,
        "experience_level": FIT_WEIGHT_EXPERIENCE_LEVEL,
        "role_title": FIT_WEIGHT_ROLE_TITLE,
        "location_logistics": FIT_WEIGHT_LOCATION_LOGISTICS,
    }


# =============================================================================
# Fit Score Result (REQ-008 §4.7)
# =============================================================================


@dataclass(frozen=True)
class FitScoreResult:
    """Result of Fit Score aggregation.

    REQ-008 §4.7: Contains total score and breakdown by component.

    Attributes:
        total: Final Fit Score (0-100), rounded to nearest integer.
        components: Dictionary of individual component scores (0-100 floats).
        weights: Dictionary of weights used for each component (sum to 1.0).
    """

    total: int
    components: dict[str, float]
    weights: dict[str, float]


# =============================================================================
# Fit Score Aggregation (REQ-008 §4.7)
# =============================================================================


def calculate_fit_score(
    hard_skills: float,
    soft_skills: float,
    experience_level: float,
    role_title: float,
    location_logistics: float,
) -> FitScoreResult:
    """Calculate aggregated Fit Score from component scores.

    REQ-008 §4.7: Fit Score Aggregation.

    Computes weighted sum of the 5 component scores:
    - Hard Skills (40%)
    - Soft Skills (15%)
    - Experience Level (25%)
    - Role Title (10%)
    - Location/Logistics (10%)

    Args:
        hard_skills: Hard skills match score (0-100).
        soft_skills: Soft skills match score (0-100).
        experience_level: Experience level match score (0-100).
        role_title: Role title match score (0-100).
        location_logistics: Location/logistics match score (0-100).

    Returns:
        FitScoreResult with:
        - total: Rounded integer score (0-100)
        - components: Dict of input scores
        - weights: Dict of component weights

    Raises:
        ValueError: If any component score is negative or exceeds 100.
    """
    # Validate all component scores
    component_scores = {
        "hard_skills": hard_skills,
        "soft_skills": soft_skills,
        "experience_level": experience_level,
        "role_title": role_title,
        "location_logistics": location_logistics,
    }

    for name, score in component_scores.items():
        if not math.isfinite(score):
            msg = f"Component score '{name}' must be a finite number: {score}"
            raise ValueError(msg)
        if score < 0:
            msg = f"Component score '{name}' cannot be negative: {score}"
            raise ValueError(msg)
        if score > 100:
            msg = f"Component score '{name}' cannot exceed 100: {score}"
            raise ValueError(msg)

    # Get weights
    weights = get_fit_component_weights()

    # Calculate weighted sum
    total_score = sum(
        component_scores[name] * weights[name] for name in component_scores
    )

    # Round to nearest integer
    rounded_total = round(total_score)

    return FitScoreResult(
        total=rounded_total,
        components=component_scores,
        weights=weights,
    )
