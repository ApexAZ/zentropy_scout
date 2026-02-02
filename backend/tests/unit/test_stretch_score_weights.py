"""Unit tests for Stretch Score component weights.

REQ-008 §5.1: Stretch Score component weights validation.

Tests cover:
- Individual weight value assertions
- Weight sum validation (must equal 1.0)
- Accessor function behavior
"""

import pytest

from app.services.stretch_score import (
    STRETCH_NEUTRAL_SCORE,
    STRETCH_WEIGHT_GROWTH_TRAJECTORY,
    STRETCH_WEIGHT_TARGET_ROLE,
    STRETCH_WEIGHT_TARGET_SKILLS,
    get_stretch_component_weights,
)

# =============================================================================
# Individual Weight Values (REQ-008 §5.1)
# =============================================================================


class TestStretchScoreWeightValues:
    """Tests for individual Stretch Score weight values."""

    def test_target_role_weight_is_50_percent(self) -> None:
        """Target Role Alignment is weighted at 50%."""
        assert STRETCH_WEIGHT_TARGET_ROLE == 0.50

    def test_target_skills_weight_is_40_percent(self) -> None:
        """Target Skills Exposure is weighted at 40%."""
        assert STRETCH_WEIGHT_TARGET_SKILLS == 0.40

    def test_growth_trajectory_weight_is_10_percent(self) -> None:
        """Growth Trajectory is weighted at 10%."""
        assert STRETCH_WEIGHT_GROWTH_TRAJECTORY == 0.10


# =============================================================================
# Weight Sum Validation
# =============================================================================


class TestStretchScoreWeightSum:
    """Tests for Stretch Score weight sum validation."""

    def test_weights_sum_to_100_percent(self) -> None:
        """All Stretch Score weights must sum to exactly 1.0 (100%)."""
        total = (
            STRETCH_WEIGHT_TARGET_ROLE
            + STRETCH_WEIGHT_TARGET_SKILLS
            + STRETCH_WEIGHT_GROWTH_TRAJECTORY
        )
        assert total == pytest.approx(1.0, abs=0.001)


# =============================================================================
# get_stretch_component_weights() Tests
# =============================================================================


class TestGetStretchComponentWeights:
    """Tests for the get_stretch_component_weights accessor function."""

    def test_returns_all_three_components(self) -> None:
        """Returns dictionary with all 3 component keys."""
        weights = get_stretch_component_weights()
        expected_keys = {"target_role", "target_skills", "growth_trajectory"}
        assert set(weights.keys()) == expected_keys

    def test_values_match_constants(self) -> None:
        """Dictionary values match the module-level constants."""
        weights = get_stretch_component_weights()
        assert weights["target_role"] == STRETCH_WEIGHT_TARGET_ROLE
        assert weights["target_skills"] == STRETCH_WEIGHT_TARGET_SKILLS
        assert weights["growth_trajectory"] == STRETCH_WEIGHT_GROWTH_TRAJECTORY

    def test_dict_values_sum_to_100_percent(self) -> None:
        """Dictionary values sum to 1.0 (100%)."""
        weights = get_stretch_component_weights()
        total = sum(weights.values())
        assert total == pytest.approx(1.0, abs=0.001)


# =============================================================================
# Neutral Score (REQ-008 §5.2, §5.3, §5.4)
# =============================================================================


class TestStretchNeutralScore:
    """Tests for the neutral score constant."""

    def test_neutral_score_is_50(self) -> None:
        """Neutral score for missing data is 50 (per REQ-008 §5.2, §5.3, §5.4)."""
        assert STRETCH_NEUTRAL_SCORE == 50

    def test_neutral_score_is_reasonable(self) -> None:
        """Neutral score is within valid range (0-100)."""
        assert 0 <= STRETCH_NEUTRAL_SCORE <= 100
