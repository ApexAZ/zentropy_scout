"""Tests for Fit Score component weights.

REQ-008 §4.1: Fit Score Component Weights.

Tests cover:
- Weight constants have correct values per spec
- Weights sum to 100% (1.0)
- get_fit_component_weights() returns all components
"""

from app.services.fit_score import (
    FIT_NEUTRAL_SCORE,
    FIT_WEIGHT_EXPERIENCE_LEVEL,
    FIT_WEIGHT_HARD_SKILLS,
    FIT_WEIGHT_LOCATION_LOGISTICS,
    FIT_WEIGHT_ROLE_TITLE,
    FIT_WEIGHT_SOFT_SKILLS,
    get_fit_component_weights,
)

# =============================================================================
# Weight Value Tests (REQ-008 §4.1)
# =============================================================================


class TestFitScoreWeightValues:
    """Tests for individual weight values per REQ-008 §4.1."""

    def test_hard_skills_weight_is_40_percent(self) -> None:
        """Hard Skills Match is weighted at 40%."""
        assert FIT_WEIGHT_HARD_SKILLS == 0.40

    def test_soft_skills_weight_is_15_percent(self) -> None:
        """Soft Skills Match is weighted at 15%."""
        assert FIT_WEIGHT_SOFT_SKILLS == 0.15

    def test_experience_level_weight_is_25_percent(self) -> None:
        """Experience Level is weighted at 25%."""
        assert FIT_WEIGHT_EXPERIENCE_LEVEL == 0.25

    def test_role_title_weight_is_10_percent(self) -> None:
        """Role Title Match is weighted at 10%."""
        assert FIT_WEIGHT_ROLE_TITLE == 0.10

    def test_location_logistics_weight_is_10_percent(self) -> None:
        """Location/Logistics is weighted at 10%."""
        assert FIT_WEIGHT_LOCATION_LOGISTICS == 0.10


# =============================================================================
# Weight Sum Tests
# =============================================================================


class TestFitScoreWeightSum:
    """Tests for weight sum validation."""

    def test_weights_sum_to_100_percent(self) -> None:
        """All component weights must sum to 1.0 (100%)."""
        total = (
            FIT_WEIGHT_HARD_SKILLS
            + FIT_WEIGHT_SOFT_SKILLS
            + FIT_WEIGHT_EXPERIENCE_LEVEL
            + FIT_WEIGHT_ROLE_TITLE
            + FIT_WEIGHT_LOCATION_LOGISTICS
        )

        assert abs(total - 1.0) < 0.001


# =============================================================================
# Accessor Function Tests
# =============================================================================


class TestGetFitComponentWeights:
    """Tests for get_fit_component_weights() accessor."""

    def test_returns_all_five_components(self) -> None:
        """Returns dictionary with all 5 component weights."""
        weights = get_fit_component_weights()

        assert len(weights) == 5
        assert "hard_skills" in weights
        assert "soft_skills" in weights
        assert "experience_level" in weights
        assert "role_title" in weights
        assert "location_logistics" in weights

    def test_values_match_constants(self) -> None:
        """Returned values match the constant definitions."""
        weights = get_fit_component_weights()

        assert weights["hard_skills"] == FIT_WEIGHT_HARD_SKILLS
        assert weights["soft_skills"] == FIT_WEIGHT_SOFT_SKILLS
        assert weights["experience_level"] == FIT_WEIGHT_EXPERIENCE_LEVEL
        assert weights["role_title"] == FIT_WEIGHT_ROLE_TITLE
        assert weights["location_logistics"] == FIT_WEIGHT_LOCATION_LOGISTICS

    def test_dict_values_sum_to_100_percent(self) -> None:
        """Dictionary values sum to 1.0 (100%)."""
        weights = get_fit_component_weights()
        total = sum(weights.values())

        assert abs(total - 1.0) < 0.001


# =============================================================================
# Neutral Score Tests (REQ-008 §9.1)
# =============================================================================


class TestFitNeutralScore:
    """Tests for neutral score constant."""

    def test_neutral_score_is_70(self) -> None:
        """Neutral score for missing data is 70."""
        assert FIT_NEUTRAL_SCORE == 70

    def test_neutral_score_is_reasonable(self) -> None:
        """Neutral score is in valid range (above average, below excellent)."""
        assert 50 < FIT_NEUTRAL_SCORE < 80
