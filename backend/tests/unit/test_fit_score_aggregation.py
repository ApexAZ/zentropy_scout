"""Unit tests for Fit Score aggregation.

REQ-008 §4.7: Fit Score Aggregation.

Tests cover:
- Weighted sum calculation (5 components)
- FitScoreResult structure (total, components)
- Rounding behavior (round to nearest integer)
- Edge cases (all zeros, all 100s, mixed scores)
- Input validation (out-of-range scores, NaN/Inf)
"""

import math

import pytest

from app.services.scoring.fit_score import calculate_fit_score

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

    @pytest.mark.parametrize(
        ("component", "expected_total"),
        [
            ("hard_skills", 40),
            ("soft_skills", 15),
            ("experience_level", 25),
            ("role_title", 10),
            ("location_logistics", 10),
        ],
    )
    def test_single_component_at_100_yields_weight_percent(
        self, component: str, expected_total: int
    ) -> None:
        """Each component at 100 (rest 0) should yield its weight percentage."""
        kwargs = {
            "hard_skills": 0.0,
            "soft_skills": 0.0,
            "experience_level": 0.0,
            "role_title": 0.0,
            "location_logistics": 0.0,
        }
        kwargs[component] = 100.0
        result = calculate_fit_score(**kwargs)
        assert result.total == expected_total


# =============================================================================
# Rounding Behavior Tests
# =============================================================================


class TestRoundingBehavior:
    """Tests for score rounding to nearest integer."""

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


# =============================================================================
# Components Dictionary Tests
# =============================================================================


class TestComponentsDictionary:
    """Tests for components dictionary in result."""

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
