"""Combined Interpretation service.

REQ-008 §7.3: Combined Interpretation — How Fit and Stretch scores together
produce a job recommendation.

Combined Interpretation answers: "Should I apply to this job?"

The 2x2 matrix (REQ-008 §7.3):
- High Fit (75+) + High Stretch (80+) → Top Priority — Apply immediately
- High Fit (75+) + Low Stretch (<80)  → Safe Bet — Good fit, but not growth
- Low Fit (<75)  + High Stretch (80+) → Stretch Opportunity — Worth the reach
- Low Fit (<75)  + Low Stretch (<80)  → Likely Skip — Neither fit nor growth

Design principles:
1. Both inputs are integer scores (0-100)
2. Thresholds are inclusive: >= 75 is High Fit, >= 80 is High Stretch
3. Result is immutable (frozen dataclass)
4. Input validation catches type errors and out-of-range values
"""

from dataclasses import dataclass
from enum import Enum

# =============================================================================
# Thresholds (REQ-008 §7.3)
# =============================================================================

# WHY these thresholds:
# REQ-008 §7.3 defines the 2x2 matrix boundaries.
# - Fit >= 75 aligns with the "Good" tier from §7.1 (75-89)
# - Stretch >= 80 aligns with the "High Growth" tier from §7.2 (80-100)

# Fit Score threshold: >= 75 is "High Fit"
_COMBINED_FIT_HIGH_THRESHOLD = 75

# Stretch Score threshold: >= 80 is "High Stretch"
_COMBINED_STRETCH_HIGH_THRESHOLD = 80


# =============================================================================
# Recommendation Enum (REQ-008 §7.3)
# =============================================================================


class CombinedRecommendation(Enum):
    """Job recommendation labels based on Fit + Stretch scores.

    REQ-008 §7.3: Combined Interpretation.

    Labels map the 2x2 matrix of Fit and Stretch to actionable guidance:
    - TOP_PRIORITY: High Fit + High Stretch — Apply immediately
    - SAFE_BET: High Fit + Low Stretch — Good fit, but not growth
    - STRETCH_OPPORTUNITY: Low Fit + High Stretch — Worth the reach
    - LIKELY_SKIP: Low Fit + Low Stretch — Neither fit nor growth
    """

    TOP_PRIORITY = "Top Priority"
    SAFE_BET = "Safe Bet"
    STRETCH_OPPORTUNITY = "Stretch Opportunity"
    LIKELY_SKIP = "Likely Skip"


# =============================================================================
# Guidance Text (REQ-008 §7.3)
# =============================================================================

# Guidance text per recommendation (from REQ-008 §7.3 table)
_COMBINED_GUIDANCE = {
    CombinedRecommendation.TOP_PRIORITY: "Apply immediately",
    CombinedRecommendation.SAFE_BET: "Good fit, but not growth",
    CombinedRecommendation.STRETCH_OPPORTUNITY: "Worth the reach",
    CombinedRecommendation.LIKELY_SKIP: "Neither fit nor growth",
}


# =============================================================================
# Result Dataclass (REQ-008 §7.3)
# =============================================================================


@dataclass(frozen=True)
class CombinedInterpretationResult:
    """Result of Combined Interpretation.

    REQ-008 §7.3: Contains recommendation and guidance text.

    Attributes:
        fit_score: The original Fit Score (0-100).
        stretch_score: The original Stretch Score (0-100).
        recommendation: The recommendation enum (Top Priority, Safe Bet, etc.).
        guidance: Human-readable guidance text.
    """

    fit_score: int
    stretch_score: int
    recommendation: CombinedRecommendation
    guidance: str


# =============================================================================
# Combined Interpretation Function (REQ-008 §7.3)
# =============================================================================


def interpret_combined_scores(
    fit_score: int,
    stretch_score: int,
) -> CombinedInterpretationResult:
    """Interpret combined Fit and Stretch scores into a job recommendation.

    REQ-008 §7.3: Combined Interpretation.

    Maps Fit Score and Stretch Score to one of four recommendations:
    - High Fit (75+) + High Stretch (80+) → Top Priority
    - High Fit (75+) + Low Stretch (<80) → Safe Bet
    - Low Fit (<75) + High Stretch (80+) → Stretch Opportunity
    - Low Fit (<75) + Low Stretch (<80) → Likely Skip

    Args:
        fit_score: Fit Score (0-100 integer).
        stretch_score: Stretch Score (0-100 integer).

    Returns:
        CombinedInterpretationResult with recommendation and guidance text.

    Raises:
        TypeError: If either score is not an integer.
        ValueError: If either score is negative or exceeds 100.
    """
    # Type validation for fit_score
    if not isinstance(fit_score, int):
        msg = (
            f"Fit score must be an integer, got {type(fit_score).__name__}: {fit_score}"
        )
        raise TypeError(msg)

    # Type validation for stretch_score
    if not isinstance(stretch_score, int):
        msg = (
            f"Stretch score must be an integer, "
            f"got {type(stretch_score).__name__}: {stretch_score}"
        )
        raise TypeError(msg)

    # Range validation for fit_score
    if fit_score < 0:
        msg = f"Fit score cannot be negative: {fit_score}"
        raise ValueError(msg)
    if fit_score > 100:
        msg = f"Fit score cannot exceed 100: {fit_score}"
        raise ValueError(msg)

    # Range validation for stretch_score
    if stretch_score < 0:
        msg = f"Stretch score cannot be negative: {stretch_score}"
        raise ValueError(msg)
    if stretch_score > 100:
        msg = f"Stretch score cannot exceed 100: {stretch_score}"
        raise ValueError(msg)

    # Determine if scores are "high" based on thresholds
    is_high_fit = fit_score >= _COMBINED_FIT_HIGH_THRESHOLD
    is_high_stretch = stretch_score >= _COMBINED_STRETCH_HIGH_THRESHOLD

    # Map to recommendation based on 2x2 matrix
    if is_high_fit and is_high_stretch:
        recommendation = CombinedRecommendation.TOP_PRIORITY
    elif is_high_fit and not is_high_stretch:
        recommendation = CombinedRecommendation.SAFE_BET
    elif not is_high_fit and is_high_stretch:
        recommendation = CombinedRecommendation.STRETCH_OPPORTUNITY
    else:
        recommendation = CombinedRecommendation.LIKELY_SKIP

    return CombinedInterpretationResult(
        fit_score=fit_score,
        stretch_score=stretch_score,
        recommendation=recommendation,
        guidance=_COMBINED_GUIDANCE[recommendation],
    )
