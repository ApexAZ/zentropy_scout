"""Score type definitions for job-persona matching.

REQ-008 §1.1: Score Types.

Zentropy Scout uses three score types to evaluate job postings:

1. **Fit Score (0-100)**: How well the user's current skills and experience
   match the job requirements. A high Fit Score means the user is qualified
   for the role as-is.

2. **Stretch Score (0-100)**: How well the job aligns with the user's growth
   targets (target roles, skills to develop). A high Stretch Score means the
   job offers significant career development opportunities.

3. **Ghost Score (0-100)**: Likelihood the job posting is stale, fake, or
   otherwise suspicious. Implemented in ghost_detection.py (REQ-003 §7).

Key Principle (REQ-008 §1):
    "Scoring must be explainable. Users should understand why a job scored
    high or low, not just see a number."

REQ-008 §1.2: Scoring Philosophy:
    - Transparency: Every score has a breakdown users can inspect
    - Configurability: Users can adjust weights (future feature)
    - Graceful degradation: Missing data reduces confidence, does not break scoring
    - Bias awareness: Avoid penalizing non-traditional backgrounds
"""

from enum import Enum
from typing import Any, TypedDict

# =============================================================================
# Score Result TypedDict
# =============================================================================


class ScoreResult(TypedDict, total=False):
    """Score result for a single job posting.

    Relocated from app.agents.state during LLM redesign (REQ-017 §5.3).

    Attributes:
        job_posting_id: The scored job's ID.
        fit_score: Fit score (0-100).
        stretch_score: Stretch score (0-100).
        explanation: Human-readable explanation of scores.
        filtered_reason: If filtered out, why (e.g., "salary_below_minimum").
        score_details: Full component breakdown for frontend drill-down UI.
            Contains fit/stretch component scores, weights, and explanation
            fields (REQ-012 Appendix A.3).
    """

    job_posting_id: str
    fit_score: float | None
    stretch_score: float | None
    explanation: str | None
    filtered_reason: str | None
    # Any: JSONB-serializable dict with fit/stretch component breakdowns
    # and explanation structure. See REQ-012 Appendix A.3 for schema.
    score_details: dict[str, Any] | None


# =============================================================================
# Score Type Enum
# =============================================================================


class ScoreType(Enum):
    """Types of scores used in job-persona matching.

    REQ-008 §1.1: Three score types for job evaluation.
    """

    # How well current skills/experience match job requirements
    FIT = "fit"

    # How well job aligns with growth targets
    STRETCH = "stretch"

    # Likelihood posting is stale/fake (see ghost_detection.py)
    GHOST = "ghost"


# =============================================================================
# Score Interpretation Enum
# =============================================================================


class ScoreInterpretation(Enum):
    """Human-readable interpretation of scores.

    REQ-008 §7.1, §7.2 and REQ-003 §7.3: Score thresholds.

    Each score type has its own set of interpretation levels with
    different thresholds and meanings.
    """

    # Fit Score interpretations (REQ-008 §7.1)
    FIT_EXCELLENT = "fit_excellent"  # 80-100: Excellent match
    FIT_GOOD = "fit_good"  # 60-79: Good match, apply with confidence
    FIT_MODERATE = "fit_moderate"  # 40-59: Moderate match, worth considering
    FIT_LOW = "fit_low"  # 0-39: Low match

    # Stretch Score interpretations (REQ-008 §7.2)
    STRETCH_HIGH = "stretch_high"  # 70-100: Significant growth potential
    STRETCH_MODERATE = "stretch_moderate"  # 40-69: Some growth opportunities
    STRETCH_LOW = "stretch_low"  # 0-39: Similar to current role

    # Ghost Score interpretations (REQ-003 §7.3)
    GHOST_FRESH = "ghost_fresh"  # 0-25: No warning
    GHOST_MODERATE = "ghost_moderate"  # 26-50: Light warning
    GHOST_ELEVATED = "ghost_elevated"  # 51-75: Recommend verification
    GHOST_HIGH_RISK = "ghost_high_risk"  # 76-100: Suggest skipping


# =============================================================================
# Interpretation Thresholds
# =============================================================================

# WHY constants: Thresholds from REQ-008 §7.1, §7.2 and REQ-003 §7.3.
# Centralized here for consistency across the codebase.

# Fit Score thresholds (REQ-008 §7.1)
FIT_EXCELLENT_THRESHOLD = 80  # 80+: Excellent match
FIT_GOOD_THRESHOLD = 60  # 60-79: Good match
FIT_MODERATE_THRESHOLD = 40  # 40-59: Moderate match
# Below 40: Low match

# Stretch Score thresholds (REQ-008 §7.2)
STRETCH_HIGH_THRESHOLD = 70  # 70+: High stretch value
STRETCH_MODERATE_THRESHOLD = 40  # 40-69: Moderate stretch
# Below 40: Low stretch

# Ghost Score thresholds (REQ-003 §7.3)
# Also defined in ghost_detection.py for that module's use
GHOST_FRESH_THRESHOLD = 25  # 0-25: Fresh
GHOST_MODERATE_THRESHOLD = 50  # 26-50: Moderate
GHOST_ELEVATED_THRESHOLD = 75  # 51-75: Elevated
# Above 75: High Risk


# =============================================================================
# Interpretation Functions
# =============================================================================


def interpret_fit_score(score: int) -> ScoreInterpretation:
    """Interpret a Fit Score into a human-readable category.

    REQ-008 §7.1: Fit Score Thresholds.

    Args:
        score: Fit score value (0-100).

    Returns:
        ScoreInterpretation indicating match quality.

    Note:
        Scores are expected to be 0-100 per the domain contract. Callers
        (API layer) validate input via Pydantic before calling this function.
    """
    if score >= FIT_EXCELLENT_THRESHOLD:
        return ScoreInterpretation.FIT_EXCELLENT
    if score >= FIT_GOOD_THRESHOLD:
        return ScoreInterpretation.FIT_GOOD
    if score >= FIT_MODERATE_THRESHOLD:
        return ScoreInterpretation.FIT_MODERATE
    return ScoreInterpretation.FIT_LOW


def interpret_stretch_score(score: int) -> ScoreInterpretation:
    """Interpret a Stretch Score into a human-readable category.

    REQ-008 §7.2: Stretch Score Thresholds.

    Args:
        score: Stretch score value (0-100).

    Returns:
        ScoreInterpretation indicating growth potential.

    Note:
        Scores are expected to be 0-100 per the domain contract. Callers
        (API layer) validate input via Pydantic before calling this function.
    """
    if score >= STRETCH_HIGH_THRESHOLD:
        return ScoreInterpretation.STRETCH_HIGH
    if score >= STRETCH_MODERATE_THRESHOLD:
        return ScoreInterpretation.STRETCH_MODERATE
    return ScoreInterpretation.STRETCH_LOW


def interpret_ghost_score(score: int) -> ScoreInterpretation:
    """Interpret a Ghost Score into a human-readable category.

    REQ-003 §7.3: Ghost Score Interpretation.

    Args:
        score: Ghost score value (0-100).

    Returns:
        ScoreInterpretation indicating posting suspiciousness.

    Note:
        Scores are expected to be 0-100 per the domain contract. Callers
        (API layer) validate input via Pydantic before calling this function.
    """
    if score <= GHOST_FRESH_THRESHOLD:
        return ScoreInterpretation.GHOST_FRESH
    if score <= GHOST_MODERATE_THRESHOLD:
        return ScoreInterpretation.GHOST_MODERATE
    if score <= GHOST_ELEVATED_THRESHOLD:
        return ScoreInterpretation.GHOST_ELEVATED
    return ScoreInterpretation.GHOST_HIGH_RISK
