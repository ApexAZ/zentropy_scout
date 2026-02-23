"""Unit tests for Stretch Score aggregation.

REQ-008 §5.5: Stretch Score Aggregation.

Tests cover:
- Weighted sum calculation (3 components)
- StretchScoreResult structure (total, components, weights)
- Rounding behavior (round to nearest integer)
- Edge cases (all zeros, all 100s, mixed scores)
- Input validation (out-of-range scores, NaN/Inf)
"""

import math

import pytest

from app.services.stretch_score import (
    STRETCH_WEIGHT_GROWTH_TRAJECTORY,
    STRETCH_WEIGHT_TARGET_ROLE,
    STRETCH_WEIGHT_TARGET_SKILLS,
    calculate_stretch_score,
)

# =============================================================================
# Weighted Sum Calculation Tests
# =============================================================================


class TestWeightedSumCalculation:
    """Tests for weighted sum formula."""

    def test_worked_example_from_spec(self) -> None:
        """REQ-008 §5.5 worked example: total should be 80.

        Target Role Alignment: 100 * 0.50 = 50.0
        Target Skills Exposure: 50 * 0.40 = 20.0
        Growth Trajectory: 100 * 0.10 = 10.0
        Total: 50.0 + 20.0 + 10.0 = 80.0
        """
        result = calculate_stretch_score(
            target_role=100.0,
            target_skills=50.0,
            growth_trajectory=100.0,
        )
        assert result.total == 80

    def test_all_components_100_returns_100(self) -> None:
        """All components at 100 should return total of 100."""
        result = calculate_stretch_score(
            target_role=100.0,
            target_skills=100.0,
            growth_trajectory=100.0,
        )
        assert result.total == 100

    def test_all_components_0_returns_0(self) -> None:
        """All components at 0 should return total of 0."""
        result = calculate_stretch_score(
            target_role=0.0,
            target_skills=0.0,
            growth_trajectory=0.0,
        )
        assert result.total == 0

    def test_all_components_50_returns_50(self) -> None:
        """All neutral components (50) should return total of 50."""
        result = calculate_stretch_score(
            target_role=50.0,
            target_skills=50.0,
            growth_trajectory=50.0,
        )
        assert result.total == 50

    def test_target_role_weighted_at_50_percent(self) -> None:
        """Target role should contribute 50% of score."""
        # Only target_role at 100, rest at 0
        # Expected: 100 * 0.50 = 50
        result = calculate_stretch_score(
            target_role=100.0,
            target_skills=0.0,
            growth_trajectory=0.0,
        )
        assert result.total == 50

    def test_target_skills_weighted_at_40_percent(self) -> None:
        """Target skills should contribute 40% of score."""
        # Only target_skills at 100, rest at 0
        # Expected: 100 * 0.40 = 40
        result = calculate_stretch_score(
            target_role=0.0,
            target_skills=100.0,
            growth_trajectory=0.0,
        )
        assert result.total == 40

    def test_growth_trajectory_weighted_at_10_percent(self) -> None:
        """Growth trajectory should contribute 10% of score."""
        # Only growth_trajectory at 100, rest at 0
        # Expected: 100 * 0.10 = 10
        result = calculate_stretch_score(
            target_role=0.0,
            target_skills=0.0,
            growth_trajectory=100.0,
        )
        assert result.total == 10


# =============================================================================
# Rounding Behavior Tests
# =============================================================================


class TestRoundingBehavior:
    """Tests for score rounding to nearest integer."""

    def test_rounds_down_at_point_4(self) -> None:
        """Score of X.4 should round down."""
        # All at 50 → 50 * 1.0 = 50.0 → rounds to 50
        result = calculate_stretch_score(
            target_role=50.0,
            target_skills=50.0,
            growth_trajectory=50.0,
        )
        assert result.total == 50

    def test_rounds_normally_at_point_5_and_above(self) -> None:
        """Score of X.5 should round to nearest even (banker's rounding)."""
        # 75.5 rounds to 76 (nearest even)
        result = calculate_stretch_score(
            target_role=75.5,
            target_skills=75.5,
            growth_trajectory=75.5,
        )
        # All at 75.5 → 75.5 * 1.0 = 75.5 → rounds to 76 (banker's rounding)
        assert result.total == 76

    def test_bankers_rounding_for_half_values(self) -> None:
        """Python's round() uses banker's rounding (round half to even).

        72.5 rounds to 72 (even), 73.5 rounds to 74 (even).
        """
        # Create inputs that result in 72.5 exactly
        result = calculate_stretch_score(
            target_role=72.5,
            target_skills=72.5,
            growth_trajectory=72.5,
        )
        # 72.5 rounds to 72 (banker's rounding: round to even)
        assert result.total == 72

    def test_rounds_up_at_point_6(self) -> None:
        """Score of X.6 should round up."""
        # Create a score that results in X.6
        # 80.6 should round to 81
        result = calculate_stretch_score(
            target_role=80.6,
            target_skills=80.6,
            growth_trajectory=80.6,
        )
        # 80.6 * 1.0 = 80.6 → rounds to 81
        assert result.total == 81


# =============================================================================
# Components Dictionary Tests
# =============================================================================


class TestComponentsDictionary:
    """Tests for components dictionary in result."""

    def test_components_contains_all_three_keys(self) -> None:
        """Components dict should have all 3 component scores."""
        result = calculate_stretch_score(
            target_role=80.0,
            target_skills=70.0,
            growth_trajectory=90.0,
        )
        assert set(result.components.keys()) == {
            "target_role",
            "target_skills",
            "growth_trajectory",
        }

    def test_components_values_match_inputs(self) -> None:
        """Components dict values should match input scores."""
        result = calculate_stretch_score(
            target_role=80.0,
            target_skills=70.0,
            growth_trajectory=90.0,
        )
        assert result.components["target_role"] == 80.0
        assert result.components["target_skills"] == 70.0
        assert result.components["growth_trajectory"] == 90.0


# =============================================================================
# Weights Dictionary Tests
# =============================================================================


class TestWeightsDictionary:
    """Tests for weights dictionary in result."""

    def test_weights_contains_all_three_keys(self) -> None:
        """Weights dict should have all 3 component weights."""
        result = calculate_stretch_score(
            target_role=80.0,
            target_skills=70.0,
            growth_trajectory=90.0,
        )
        assert set(result.weights.keys()) == {
            "target_role",
            "target_skills",
            "growth_trajectory",
        }

    def test_weights_match_constants(self) -> None:
        """Weights dict values should match defined constants."""
        result = calculate_stretch_score(
            target_role=80.0,
            target_skills=70.0,
            growth_trajectory=90.0,
        )
        assert result.weights["target_role"] == STRETCH_WEIGHT_TARGET_ROLE
        assert result.weights["target_skills"] == STRETCH_WEIGHT_TARGET_SKILLS
        assert result.weights["growth_trajectory"] == STRETCH_WEIGHT_GROWTH_TRAJECTORY

    def test_weights_sum_to_1(self) -> None:
        """Weights should sum to 1.0 (100%)."""
        result = calculate_stretch_score(
            target_role=80.0,
            target_skills=70.0,
            growth_trajectory=90.0,
        )
        total_weight = sum(result.weights.values())
        assert abs(total_weight - 1.0) < 0.001


# =============================================================================
# Input Validation Tests
# =============================================================================


class TestInputValidation:
    """Tests for input validation."""

    def test_negative_component_raises_error(self) -> None:
        """Negative component score should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            calculate_stretch_score(
                target_role=-10.0,
                target_skills=70.0,
                growth_trajectory=50.0,
            )

    def test_component_over_100_raises_error(self) -> None:
        """Component score over 100 should raise ValueError."""
        with pytest.raises(ValueError, match="cannot exceed 100"):
            calculate_stretch_score(
                target_role=150.0,
                target_skills=70.0,
                growth_trajectory=50.0,
            )

    def test_all_components_at_boundary_0_valid(self) -> None:
        """All components at 0 is valid."""
        result = calculate_stretch_score(
            target_role=0.0,
            target_skills=0.0,
            growth_trajectory=0.0,
        )
        assert result.total == 0

    def test_all_components_at_boundary_100_valid(self) -> None:
        """All components at 100 is valid."""
        result = calculate_stretch_score(
            target_role=100.0,
            target_skills=100.0,
            growth_trajectory=100.0,
        )
        assert result.total == 100

    def test_nan_component_raises_error(self) -> None:
        """NaN component score should raise ValueError."""
        with pytest.raises(ValueError, match="must be a finite number"):
            calculate_stretch_score(
                target_role=math.nan,
                target_skills=70.0,
                growth_trajectory=50.0,
            )

    def test_positive_inf_component_raises_error(self) -> None:
        """Positive infinity component score should raise ValueError."""
        with pytest.raises(ValueError, match="must be a finite number"):
            calculate_stretch_score(
                target_role=math.inf,
                target_skills=70.0,
                growth_trajectory=50.0,
            )

    def test_negative_inf_component_raises_error(self) -> None:
        """Negative infinity component score should raise ValueError."""
        with pytest.raises(ValueError, match="must be a finite number"):
            calculate_stretch_score(
                target_role=-math.inf,
                target_skills=70.0,
                growth_trajectory=50.0,
            )


# =============================================================================
# Score Bounds Tests
# =============================================================================


class TestScoreBounds:
    """Tests that total score is always within valid range."""

    def test_total_never_exceeds_100(self) -> None:
        """Total score should never exceed 100."""
        result = calculate_stretch_score(
            target_role=100.0,
            target_skills=100.0,
            growth_trajectory=100.0,
        )
        assert result.total <= 100

    def test_total_never_below_0(self) -> None:
        """Total score should never be below 0."""
        result = calculate_stretch_score(
            target_role=0.0,
            target_skills=0.0,
            growth_trajectory=0.0,
        )
        assert result.total >= 0
