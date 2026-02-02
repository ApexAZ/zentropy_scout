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

    # Filter out empty/whitespace-only target roles
    valid_target_roles: list[str] = []
    if target_roles is not None:
        for role in target_roles:
            if role and role.strip():
                valid_target_roles.append(role.strip())

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
    # If embeddings not available, return neutral
    if target_roles_embedding is None or job_title_embedding is None:
        return STRETCH_NEUTRAL_SCORE

    # Validate embeddings
    if len(target_roles_embedding) == 0 or len(job_title_embedding) == 0:
        msg = "Embeddings cannot be empty"
        raise ValueError(msg)

    if len(target_roles_embedding) != len(job_title_embedding):
        msg = (
            f"Embedding dimensions must match: "
            f"{len(target_roles_embedding)} vs {len(job_title_embedding)}"
        )
        raise ValueError(msg)

    if (
        len(target_roles_embedding) > _MAX_EMBEDDING_DIMENSIONS
        or len(job_title_embedding) > _MAX_EMBEDDING_DIMENSIONS
    ):
        msg = f"Embeddings exceed maximum dimensions of {_MAX_EMBEDDING_DIMENSIONS}"
        raise ValueError(msg)

    # Calculate cosine similarity and scale to 30-100 (with baseline)
    similarity = cosine_similarity(target_roles_embedding, job_title_embedding)

    # Scale from [-1, 1] to [30, 100] with 30-point baseline
    # Formula: max(0, 30 + (similarity + 1) * 35)
    # - similarity = -1 → 30 + 0 = 30
    # - similarity = 0 → 30 + 35 = 65
    # - similarity = +1 → 30 + 70 = 100
    return max(0, 30 + (similarity + 1) * 35)
