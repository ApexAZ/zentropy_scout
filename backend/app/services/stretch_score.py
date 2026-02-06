"""Stretch Score calculation service.

REQ-008 §5: Stretch Score — How well job aligns with user's growth targets.

Stretch Score answers: "Will this job help me grow toward my goals?"

Component weights (REQ-008 §5.1):
- Target Role Alignment:    50% — How closely job title matches target roles
- Target Skills Exposure:   40% — How many target skills appear in job requirements
- Growth Trajectory:        10% — Is this a step up from current role?

Total: 100%

Design principles:
1. Each component returns a score 0-100
2. Final score is weighted sum: sum(component * weight)
3. Missing growth targets defaults to 50 (neutral) — see REQ-008 §5.2, §5.3, §5.4
4. Role alignment is weighted highest because title indicates career direction
"""

import math
import re
from dataclasses import dataclass
from enum import Enum

from app.services.hard_skills_match import normalize_skill
from app.services.role_title_match import normalize_title
from app.services.soft_skills_match import cosine_similarity

# =============================================================================
# Component Weights (REQ-008 §5.1)
# =============================================================================

# WHY these weights:
# REQ-008 §5.1 defines the relative importance of each component.
# Target Role Alignment is weighted highest (50%) because the primary
# growth indicator is whether the job title matches where the user wants to go.

# Target Role Alignment (REQ-008 §5.2)
# How closely job title matches user's target roles.
# Highest weight because role alignment is the primary growth indicator.
STRETCH_WEIGHT_TARGET_ROLE = 0.50

# Target Skills Exposure (REQ-008 §5.3)
# How many target skills appear in job requirements.
# Second-highest because gaining experience with target skills is valuable.
STRETCH_WEIGHT_TARGET_SKILLS = 0.40

# Growth Trajectory (REQ-008 §5.4)
# Is this a step up, lateral, or step down from current role?
# Lowest weight because title-level advancement is less important than
# role/skill fit for career growth.
STRETCH_WEIGHT_GROWTH_TRAJECTORY = 0.10


# =============================================================================
# Validation
# =============================================================================

# Weights must sum to 1.0 (100%)
_WEIGHT_SUM = (
    STRETCH_WEIGHT_TARGET_ROLE
    + STRETCH_WEIGHT_TARGET_SKILLS
    + STRETCH_WEIGHT_GROWTH_TRAJECTORY
)

# Sanity check at import time (RuntimeError survives python -O, unlike assert)
if abs(_WEIGHT_SUM - 1.0) >= 0.001:
    raise RuntimeError(f"Stretch score weights must sum to 1.0, got {_WEIGHT_SUM}")


# =============================================================================
# Neutral Score (REQ-008 §5.2, §5.3, §5.4)
# =============================================================================

# When growth targets are not defined, use a neutral score of 50.
# This differs from Fit Score's neutral of 70 because:
# - No growth targets = no preference = middle of the road
# - 50 indicates "can't assess stretch value" rather than "good stretch"
STRETCH_NEUTRAL_SCORE = 50


# =============================================================================
# Component Weight Accessors
# =============================================================================


def get_stretch_component_weights() -> dict[str, float]:
    """Return all Stretch Score component weights as a dictionary.

    REQ-008 §5.1: Component Weights.

    Returns:
        Dictionary mapping component names to their weights.
        Weights sum to 1.0 (100%).

    Example:
        >>> weights = get_stretch_component_weights()
        >>> weights["target_role"]
        0.50
    """
    return {
        "target_role": STRETCH_WEIGHT_TARGET_ROLE,
        "target_skills": STRETCH_WEIGHT_TARGET_SKILLS,
        "growth_trajectory": STRETCH_WEIGHT_GROWTH_TRAJECTORY,
    }


# =============================================================================
# Target Role Alignment (REQ-008 §5.2)
# =============================================================================

# Maximum target roles to prevent DoS
_MAX_TARGET_ROLES = 100

# Maximum embedding dimensions (consistent with soft_skills_match)
_MAX_EMBEDDING_DIMENSIONS = 5000


def _validate_embeddings(
    embedding_a: list[float],
    embedding_b: list[float],
    max_dimensions: int,
) -> None:
    """Validate that two embeddings are non-empty, same-sized, and within bounds.

    Raises:
        ValueError: If embeddings are empty, mismatched, or exceed max dimensions.
    """
    if len(embedding_a) == 0 or len(embedding_b) == 0:
        msg = "Embeddings cannot be empty"
        raise ValueError(msg)

    if len(embedding_a) != len(embedding_b):
        msg = (
            f"Embedding dimensions must match: {len(embedding_a)} vs {len(embedding_b)}"
        )
        raise ValueError(msg)

    if len(embedding_a) > max_dimensions or len(embedding_b) > max_dimensions:
        msg = f"Embeddings exceed maximum dimensions of {max_dimensions}"
        raise ValueError(msg)


def _filter_valid_strings(items: list[str] | None) -> list[str]:
    """Filter out empty/whitespace-only strings from a list."""
    if items is None:
        return []
    return [item.strip() for item in items if item and item.strip()]


def calculate_target_role_alignment(
    target_roles: list[str] | None,
    job_title: str | None,
    target_roles_embedding: list[float] | None,
    job_title_embedding: list[float] | None,
) -> float:
    """Calculate target role alignment score (0-100).

    REQ-008 §5.2: Target Role Alignment (50% of Stretch Score).

    Uses two-step matching:
    1. Exact match (after normalization) → returns 100
    2. Semantic similarity via embeddings → scaled using baseline formula

    The scaling formula is: max(0, 30 + (similarity + 1) * 35)
    This gives a range of [30, 100] for similarity in [-1, 1], reflecting
    that target roles should be somewhat career-relevant even if not a
    perfect match.

    Args:
        target_roles: User's target roles from growth targets. None if not set.
        job_title: Job posting's title. None if not specified.
        target_roles_embedding: Pre-computed embedding of target roles
            (concatenated/averaged). None if not available.
        job_title_embedding: Pre-computed embedding of job title.
            None if not available.

    Returns:
        Target role alignment score 0-100:
        - 100: Exact match (after normalization)
        - 50: Neutral (missing data)
        - 30-100: Semantic similarity score with baseline

    Raises:
        ValueError: If embeddings have different dimensions or exceed max size,
            or if target roles exceed max count.
    """
    # Validate target roles count
    if target_roles is not None and len(target_roles) > _MAX_TARGET_ROLES:
        msg = f"Target roles exceed maximum of {_MAX_TARGET_ROLES}"
        raise ValueError(msg)

    valid_target_roles = _filter_valid_strings(target_roles)

    # Handle missing data - return neutral score
    if not valid_target_roles or not job_title or not job_title.strip():
        return STRETCH_NEUTRAL_SCORE

    # Normalize all titles for comparison
    normalized_targets = [normalize_title(role) for role in valid_target_roles]
    normalized_job = normalize_title(job_title)

    # Step 1: Check for exact match (after normalization)
    if normalized_job in normalized_targets:
        return 100.0

    # Step 2: Semantic similarity via embeddings
    if target_roles_embedding is None or job_title_embedding is None:
        return STRETCH_NEUTRAL_SCORE

    _validate_embeddings(
        target_roles_embedding, job_title_embedding, _MAX_EMBEDDING_DIMENSIONS
    )

    # Scale from [-1, 1] to [30, 100] with 30-point baseline
    similarity = cosine_similarity(target_roles_embedding, job_title_embedding)
    return max(0, 30 + (similarity + 1) * 35)


# =============================================================================
# Target Skills Exposure (REQ-008 §5.3)
# =============================================================================

# Maximum skill list size to prevent DoS via large inputs
_MAX_TARGET_SKILLS = 500


def calculate_target_skills_exposure(
    target_skills: list[str] | None,
    job_skills: list[str] | None,
) -> float:
    """Calculate target skills exposure score (0-100).

    REQ-008 §5.3: Target Skills Exposure (40% of Stretch Score).

    Counts how many of the user's target skills appear in the job posting.
    Uses tiered scoring based on match count.

    Scoring tiers:
    - 0 matches: 20 (job offers no exposure to target skills)
    - 1 match: 50 (minimal exposure)
    - 2 matches: 75 (good exposure)
    - 3+ matches: 100 (excellent exposure)

    Args:
        target_skills: User's target skills from growth targets. None if not set.
        job_skills: Skill names from job's extracted_skills. None if not specified.

    Returns:
        Target skills exposure score 0-100:
        - 50: Neutral (no target skills defined)
        - 20: No matches (job doesn't expose target skills)
        - 50/75/100: Tiered based on match count

    Raises:
        ValueError: If skill lists exceed maximum size (_MAX_TARGET_SKILLS).
    """
    # Validate input sizes
    if target_skills is not None and len(target_skills) > _MAX_TARGET_SKILLS:
        msg = f"Target skills exceed maximum of {_MAX_TARGET_SKILLS}"
        raise ValueError(msg)

    if job_skills is not None and len(job_skills) > _MAX_TARGET_SKILLS:
        msg = f"Job skills exceed maximum of {_MAX_TARGET_SKILLS}"
        raise ValueError(msg)

    valid_target_skills = _filter_valid_strings(target_skills)

    # No target skills defined → neutral score
    if not valid_target_skills:
        return STRETCH_NEUTRAL_SCORE

    # Normalize target skills for comparison
    normalized_targets = {normalize_skill(s) for s in valid_target_skills}

    # Handle missing/empty job skills → 0 matches
    if not job_skills:
        return 20.0

    # Normalize job skills for comparison
    normalized_job_skills = {normalize_skill(s) for s in job_skills if s and s.strip()}

    # Calculate intersection count
    matches = len(normalized_targets & normalized_job_skills)

    # Map match count to tiered score
    # 0=20, 1=50, 2=75, 3+=100
    score_tiers = {0: 20.0, 1: 50.0, 2: 75.0}
    return score_tiers.get(matches, 100.0)


# =============================================================================
# Growth Trajectory (REQ-008 §5.4)
# =============================================================================

# 7-tier career level hierarchy (lowest to highest)
_LEVEL_ORDER = ["junior", "mid", "senior", "lead", "director", "vp", "c_level"]

# Maximum title length to prevent resource exhaustion on large inputs
_MAX_TITLE_LENGTH = 500


def _is_c_level(normalized: str) -> bool:
    """Check if normalized title indicates C-level."""
    if "chief of staff" in normalized:
        return False
    if re.search(r"\b(ceo|cto|cfo|coo)\b", normalized):
        return True
    return bool(re.search(r"\bchief\b", normalized))


def _is_vp_level(normalized: str) -> bool:
    """Check if normalized title indicates VP level."""
    if any(
        keyword in normalized
        for keyword in [" vp", "vp ", "vice president", "svp", "evp"]
    ):
        return True
    return (
        normalized == "vp" or normalized.startswith("vp ") or normalized.endswith(" vp")
    )


_LEAD_KEYWORDS = ("lead", "principal", "staff")

_MANAGER_PATTERNS = (
    "engineering manager",
    "team manager",
    "people manager",
    "hiring manager",
    "development manager",
    "tech manager",
    "technical manager",
    "operations manager",
    "it manager",
)

_SENIOR_KEYWORDS = ("senior", "sr.", "sr ")
_JUNIOR_KEYWORDS = ("junior", "jr.", "jr ", "associate", "entry-level", "intern")


def infer_level(title: str | None) -> str | None:
    """Infer career level from job title.

    REQ-008 §5.4: Level inference for Growth Trajectory calculation.

    Maps job titles to a 7-tier career level hierarchy:
    - junior: Entry-level positions (junior, associate, intern)
    - mid: Standard positions without seniority indicator
    - senior: Senior individual contributors
    - lead: Team leads, managers, principals, staff engineers
    - director: Director-level positions
    - vp: Vice President level
    - c_level: C-suite executives (CEO, CTO, CFO, etc.)

    Args:
        title: Job title to analyze. None or empty returns None.

    Returns:
        Career level string, or None if title is empty/whitespace.
        Note: Valid titles always return a level (defaults to 'mid').
    """
    if title is None or not title.strip():
        return None

    # Truncate oversized titles to prevent resource exhaustion
    truncated = title[:_MAX_TITLE_LENGTH] if len(title) > _MAX_TITLE_LENGTH else title
    normalized = truncated.lower().strip()

    # Order matters: check from highest to lowest level
    if _is_c_level(normalized):
        return "c_level"
    if _is_vp_level(normalized):
        return "vp"
    if "director" in normalized:
        return "director"
    if any(keyword in normalized for keyword in _LEAD_KEYWORDS):
        return "lead"
    if any(pattern in normalized for pattern in _MANAGER_PATTERNS):
        return "lead"
    if "chief of staff" in normalized:
        return "lead"
    if any(keyword in normalized for keyword in _SENIOR_KEYWORDS):
        return "senior"
    if any(keyword in normalized for keyword in _JUNIOR_KEYWORDS):
        return "junior"

    return "mid"


def calculate_growth_trajectory(
    current_role: str | None,
    job_title: str | None,
) -> float:
    """Calculate growth trajectory score (0-100).

    REQ-008 §5.4: Growth Trajectory (10% of Stretch Score).

    Compares the user's current career level to the job's level to determine
    if the job represents career advancement.

    Scoring:
    - Step up (job level > current level): 100.0
    - Lateral move (same level): 70.0
    - Step down (job level < current level): 30.0
    - Cannot determine (missing data): 50.0 (neutral)

    Args:
        current_role: User's current job title. None if not set.
        job_title: Target job's title. None if not specified.

    Returns:
        Growth trajectory score 0-100:
        - 100.0: Step up (career advancement)
        - 70.0: Lateral move (same level)
        - 30.0: Step down (below current level)
        - 50.0: Neutral (cannot determine levels)
    """
    # Infer levels from titles
    current_level = infer_level(current_role)
    job_level = infer_level(job_title)

    # If either level cannot be determined, return neutral
    if current_level is None or job_level is None:
        return STRETCH_NEUTRAL_SCORE

    # Look up indices in level hierarchy
    try:
        current_idx = _LEVEL_ORDER.index(current_level)
        job_idx = _LEVEL_ORDER.index(job_level)
    except ValueError:
        # Should not happen if infer_level returns valid levels
        return STRETCH_NEUTRAL_SCORE

    # Score based on level comparison
    if job_idx > current_idx:
        return 100.0  # Step up
    elif job_idx == current_idx:
        return 70.0  # Lateral move
    else:
        return 30.0  # Step down


# =============================================================================
# Stretch Score Result (REQ-008 §5.5)
# =============================================================================


@dataclass
class StretchScoreResult:
    """Result of Stretch Score aggregation.

    REQ-008 §5.5: Contains total score and breakdown by component.

    Attributes:
        total: Final Stretch Score (0-100), rounded to nearest integer.
        components: Dictionary of individual component scores (0-100 floats).
        weights: Dictionary of weights used for each component (sum to 1.0).
    """

    total: int
    components: dict[str, float]
    weights: dict[str, float]


# =============================================================================
# Stretch Score Aggregation (REQ-008 §5.5)
# =============================================================================


def calculate_stretch_score(
    target_role: float,
    target_skills: float,
    growth_trajectory: float,
) -> StretchScoreResult:
    """Calculate aggregated Stretch Score from component scores.

    REQ-008 §5.5: Stretch Score Aggregation.

    Computes weighted sum of the 3 component scores:
    - Target Role Alignment (50%)
    - Target Skills Exposure (40%)
    - Growth Trajectory (10%)

    Args:
        target_role: Target role alignment score (0-100).
        target_skills: Target skills exposure score (0-100).
        growth_trajectory: Growth trajectory score (0-100).

    Returns:
        StretchScoreResult with:
        - total: Rounded integer score (0-100)
        - components: Dict of input scores
        - weights: Dict of component weights

    Raises:
        ValueError: If any component score is negative or exceeds 100.
    """
    # Validate all component scores
    component_scores = {
        "target_role": target_role,
        "target_skills": target_skills,
        "growth_trajectory": growth_trajectory,
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
    weights = get_stretch_component_weights()

    # Calculate weighted sum
    total_score = sum(
        component_scores[name] * weights[name] for name in component_scores
    )

    # Round to nearest integer
    rounded_total = round(total_score)

    return StretchScoreResult(
        total=rounded_total,
        components=component_scores,
        weights=weights,
    )


# =============================================================================
# Stretch Score Interpretation (REQ-008 §7.2)
# =============================================================================


class StretchScoreLabel(Enum):
    """Stretch Score threshold labels.

    REQ-008 §7.2: Stretch Score Thresholds.

    Labels map score ranges to human-readable interpretations:
    - HIGH_GROWTH (80-100): Strong alignment with career goals
    - MODERATE_GROWTH (60-79): Some goal alignment
    - LATERAL (40-59): Similar to current role
    - LOW_GROWTH (0-39): Not aligned with stated goals
    """

    HIGH_GROWTH = "High Growth"
    MODERATE_GROWTH = "Moderate Growth"
    LATERAL = "Lateral"
    LOW_GROWTH = "Low Growth"


# Threshold boundaries (inclusive lower bounds)
_STRETCH_THRESHOLD_HIGH_GROWTH = 80
_STRETCH_THRESHOLD_MODERATE_GROWTH = 60
_STRETCH_THRESHOLD_LATERAL = 40
# Below 40 is LOW_GROWTH (no explicit threshold needed)

# Interpretation text per label
_STRETCH_INTERPRETATIONS = {
    StretchScoreLabel.HIGH_GROWTH: "Strong alignment with career goals",
    StretchScoreLabel.MODERATE_GROWTH: "Some goal alignment",
    StretchScoreLabel.LATERAL: "Similar to current role",
    StretchScoreLabel.LOW_GROWTH: "Not aligned with stated goals",
}


@dataclass(frozen=True)
class StretchScoreInterpretation:
    """Result of Stretch Score interpretation.

    REQ-008 §7.2: Contains label and interpretation text.

    Attributes:
        score: The original score (0-100).
        label: The threshold label (High Growth, Moderate Growth, Lateral, Low Growth).
        interpretation: Human-readable interpretation text.
    """

    score: int
    label: StretchScoreLabel
    interpretation: str


def interpret_stretch_score(score: int) -> StretchScoreInterpretation:
    """Interpret a Stretch Score into a threshold label.

    REQ-008 §7.2: Stretch Score Thresholds.

    Maps a Stretch Score (0-100) to one of four threshold labels:
    - 80-100: High Growth (Strong alignment with career goals)
    - 60-79: Moderate Growth (Some goal alignment)
    - 40-59: Lateral (Similar to current role)
    - 0-39: Low Growth (Not aligned with stated goals)

    Args:
        score: Stretch Score (0-100 integer).

    Returns:
        StretchScoreInterpretation with label and interpretation text.

    Raises:
        TypeError: If score is not an integer.
        ValueError: If score is negative or exceeds 100.
    """
    if not isinstance(score, int):
        msg = f"Stretch score must be an integer, got {type(score).__name__}: {score}"
        raise TypeError(msg)
    if score < 0:
        msg = f"Stretch score cannot be negative: {score}"
        raise ValueError(msg)
    if score > 100:
        msg = f"Stretch score cannot exceed 100: {score}"
        raise ValueError(msg)

    # Determine label based on thresholds
    if score >= _STRETCH_THRESHOLD_HIGH_GROWTH:
        label = StretchScoreLabel.HIGH_GROWTH
    elif score >= _STRETCH_THRESHOLD_MODERATE_GROWTH:
        label = StretchScoreLabel.MODERATE_GROWTH
    elif score >= _STRETCH_THRESHOLD_LATERAL:
        label = StretchScoreLabel.LATERAL
    else:
        label = StretchScoreLabel.LOW_GROWTH

    return StretchScoreInterpretation(
        score=score,
        label=label,
        interpretation=_STRETCH_INTERPRETATIONS[label],
    )
