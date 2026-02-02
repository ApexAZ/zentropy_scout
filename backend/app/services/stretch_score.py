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
