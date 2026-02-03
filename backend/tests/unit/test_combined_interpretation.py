"""Unit tests for Combined Interpretation (Fit + Stretch → Recommendation).

REQ-008 §7.3: Combined Interpretation.

Tests cover:
- Recommendation label mapping (Top Priority, Safe Bet, Stretch Opportunity, Likely Skip)
- Boundary conditions at threshold edges
- Input validation (out of range scores, type validation)
- Result structure and immutability
"""

import pytest

from app.services.combined_interpretation import (
    CombinedRecommendation,
    interpret_combined_scores,
)

# =============================================================================
# Recommendation Label Tests (REQ-008 §7.3)
# =============================================================================


class TestCombinedRecommendationLabels:
    """Tests for Fit + Stretch to recommendation mapping."""

    # -------------------------------------------------------------------------
    # Top Priority: High Fit (75+) + High Stretch (80+)
    # -------------------------------------------------------------------------

    def test_high_fit_high_stretch_returns_top_priority(self) -> None:
        """High Fit (75+) and High Stretch (80+) returns Top Priority."""
        result = interpret_combined_scores(fit_score=75, stretch_score=80)
        assert result.recommendation == CombinedRecommendation.TOP_PRIORITY

    def test_max_scores_returns_top_priority(self) -> None:
        """Maximum scores (100, 100) returns Top Priority."""
        result = interpret_combined_scores(fit_score=100, stretch_score=100)
        assert result.recommendation == CombinedRecommendation.TOP_PRIORITY

    def test_fit_90_stretch_95_returns_top_priority(self) -> None:
        """High scores in both dimensions returns Top Priority."""
        result = interpret_combined_scores(fit_score=90, stretch_score=95)
        assert result.recommendation == CombinedRecommendation.TOP_PRIORITY

    # -------------------------------------------------------------------------
    # Safe Bet: High Fit (75+) + Low Stretch (<80)
    # -------------------------------------------------------------------------

    def test_high_fit_low_stretch_returns_safe_bet(self) -> None:
        """High Fit (75+) and Low Stretch (<80) returns Safe Bet."""
        result = interpret_combined_scores(fit_score=75, stretch_score=79)
        assert result.recommendation == CombinedRecommendation.SAFE_BET

    def test_high_fit_zero_stretch_returns_safe_bet(self) -> None:
        """High Fit with zero Stretch returns Safe Bet."""
        result = interpret_combined_scores(fit_score=90, stretch_score=0)
        assert result.recommendation == CombinedRecommendation.SAFE_BET

    def test_fit_85_stretch_50_returns_safe_bet(self) -> None:
        """Good Fit and moderate Stretch returns Safe Bet."""
        result = interpret_combined_scores(fit_score=85, stretch_score=50)
        assert result.recommendation == CombinedRecommendation.SAFE_BET

    # -------------------------------------------------------------------------
    # Stretch Opportunity: Low Fit (<75) + High Stretch (80+)
    # -------------------------------------------------------------------------

    def test_low_fit_high_stretch_returns_stretch_opportunity(self) -> None:
        """Low Fit (<75) and High Stretch (80+) returns Stretch Opportunity."""
        result = interpret_combined_scores(fit_score=74, stretch_score=80)
        assert result.recommendation == CombinedRecommendation.STRETCH_OPPORTUNITY

    def test_zero_fit_high_stretch_returns_stretch_opportunity(self) -> None:
        """Zero Fit with High Stretch returns Stretch Opportunity."""
        result = interpret_combined_scores(fit_score=0, stretch_score=100)
        assert result.recommendation == CombinedRecommendation.STRETCH_OPPORTUNITY

    def test_fit_50_stretch_90_returns_stretch_opportunity(self) -> None:
        """Low-moderate Fit and high Stretch returns Stretch Opportunity."""
        result = interpret_combined_scores(fit_score=50, stretch_score=90)
        assert result.recommendation == CombinedRecommendation.STRETCH_OPPORTUNITY

    # -------------------------------------------------------------------------
    # Likely Skip: Low Fit (<75) + Low Stretch (<80)
    # -------------------------------------------------------------------------

    def test_low_fit_low_stretch_returns_likely_skip(self) -> None:
        """Low Fit (<75) and Low Stretch (<80) returns Likely Skip."""
        result = interpret_combined_scores(fit_score=74, stretch_score=79)
        assert result.recommendation == CombinedRecommendation.LIKELY_SKIP

    def test_zero_scores_returns_likely_skip(self) -> None:
        """Zero scores in both dimensions returns Likely Skip."""
        result = interpret_combined_scores(fit_score=0, stretch_score=0)
        assert result.recommendation == CombinedRecommendation.LIKELY_SKIP

    def test_fit_50_stretch_50_returns_likely_skip(self) -> None:
        """Moderate scores in both dimensions returns Likely Skip."""
        result = interpret_combined_scores(fit_score=50, stretch_score=50)
        assert result.recommendation == CombinedRecommendation.LIKELY_SKIP


# =============================================================================
# Boundary Condition Tests
# =============================================================================


class TestCombinedInterpretationBoundaries:
    """Tests for boundary conditions at threshold edges."""

    def test_fit_exactly_75_is_high(self) -> None:
        """Fit score of exactly 75 is considered High."""
        result = interpret_combined_scores(fit_score=75, stretch_score=80)
        assert result.recommendation == CombinedRecommendation.TOP_PRIORITY

    def test_fit_exactly_74_is_low(self) -> None:
        """Fit score of exactly 74 is considered Low."""
        result = interpret_combined_scores(fit_score=74, stretch_score=80)
        assert result.recommendation == CombinedRecommendation.STRETCH_OPPORTUNITY

    def test_stretch_exactly_80_is_high(self) -> None:
        """Stretch score of exactly 80 is considered High."""
        result = interpret_combined_scores(fit_score=75, stretch_score=80)
        assert result.recommendation == CombinedRecommendation.TOP_PRIORITY

    def test_stretch_exactly_79_is_low(self) -> None:
        """Stretch score of exactly 79 is considered Low."""
        result = interpret_combined_scores(fit_score=75, stretch_score=79)
        assert result.recommendation == CombinedRecommendation.SAFE_BET

    def test_both_at_boundary_high(self) -> None:
        """Both scores at their respective High thresholds."""
        result = interpret_combined_scores(fit_score=75, stretch_score=80)
        assert result.recommendation == CombinedRecommendation.TOP_PRIORITY

    def test_both_at_boundary_low(self) -> None:
        """Both scores one below their respective High thresholds."""
        result = interpret_combined_scores(fit_score=74, stretch_score=79)
        assert result.recommendation == CombinedRecommendation.LIKELY_SKIP


# =============================================================================
# Guidance Text Tests
# =============================================================================


class TestCombinedInterpretationGuidance:
    """Tests for guidance text in result."""

    def test_top_priority_has_guidance(self) -> None:
        """Top Priority result includes guidance text."""
        result = interpret_combined_scores(fit_score=90, stretch_score=90)
        assert result.guidance == "Apply immediately"

    def test_safe_bet_has_guidance(self) -> None:
        """Safe Bet result includes guidance text."""
        result = interpret_combined_scores(fit_score=90, stretch_score=50)
        assert result.guidance == "Good fit, but not growth"

    def test_stretch_opportunity_has_guidance(self) -> None:
        """Stretch Opportunity result includes guidance text."""
        result = interpret_combined_scores(fit_score=50, stretch_score=90)
        assert result.guidance == "Worth the reach"

    def test_likely_skip_has_guidance(self) -> None:
        """Likely Skip result includes guidance text."""
        result = interpret_combined_scores(fit_score=50, stretch_score=50)
        assert result.guidance == "Neither fit nor growth"


# =============================================================================
# Result Structure Tests
# =============================================================================


class TestCombinedInterpretationResult:
    """Tests for interpretation result structure."""

    def test_result_has_fit_score(self) -> None:
        """Result includes the original fit score."""
        result = interpret_combined_scores(fit_score=85, stretch_score=70)
        assert result.fit_score == 85

    def test_result_has_stretch_score(self) -> None:
        """Result includes the original stretch score."""
        result = interpret_combined_scores(fit_score=85, stretch_score=70)
        assert result.stretch_score == 70

    def test_result_has_recommendation(self) -> None:
        """Result includes the recommendation enum."""
        result = interpret_combined_scores(fit_score=85, stretch_score=70)
        assert result.recommendation == CombinedRecommendation.SAFE_BET

    def test_result_has_guidance(self) -> None:
        """Result includes guidance text."""
        result = interpret_combined_scores(fit_score=85, stretch_score=70)
        assert result.guidance is not None


# =============================================================================
# Input Validation Tests
# =============================================================================


class TestCombinedInterpretationValidation:
    """Tests for input validation."""

    def test_negative_fit_score_raises_error(self) -> None:
        """Negative fit score raises ValueError."""
        with pytest.raises(ValueError, match="Fit score cannot be negative"):
            interpret_combined_scores(fit_score=-1, stretch_score=50)

    def test_negative_stretch_score_raises_error(self) -> None:
        """Negative stretch score raises ValueError."""
        with pytest.raises(ValueError, match="Stretch score cannot be negative"):
            interpret_combined_scores(fit_score=50, stretch_score=-1)

    def test_fit_score_over_100_raises_error(self) -> None:
        """Fit score over 100 raises ValueError."""
        with pytest.raises(ValueError, match="Fit score cannot exceed 100"):
            interpret_combined_scores(fit_score=101, stretch_score=50)

    def test_stretch_score_over_100_raises_error(self) -> None:
        """Stretch score over 100 raises ValueError."""
        with pytest.raises(ValueError, match="Stretch score cannot exceed 100"):
            interpret_combined_scores(fit_score=50, stretch_score=101)

    def test_boundary_0_fit_is_valid(self) -> None:
        """Fit score of 0 is valid."""
        result = interpret_combined_scores(fit_score=0, stretch_score=50)
        assert result.fit_score == 0

    def test_boundary_0_stretch_is_valid(self) -> None:
        """Stretch score of 0 is valid."""
        result = interpret_combined_scores(fit_score=50, stretch_score=0)
        assert result.stretch_score == 0

    def test_boundary_100_fit_is_valid(self) -> None:
        """Fit score of 100 is valid."""
        result = interpret_combined_scores(fit_score=100, stretch_score=50)
        assert result.fit_score == 100

    def test_boundary_100_stretch_is_valid(self) -> None:
        """Stretch score of 100 is valid."""
        result = interpret_combined_scores(fit_score=50, stretch_score=100)
        assert result.stretch_score == 100


# =============================================================================
# Type Validation Tests
# =============================================================================


class TestCombinedInterpretationTypeValidation:
    """Tests for type validation in interpret_combined_scores."""

    def test_float_fit_score_raises_type_error(self) -> None:
        """Float fit score raises TypeError."""
        with pytest.raises(TypeError, match="Fit score must be an integer"):
            interpret_combined_scores(fit_score=75.5, stretch_score=80)  # type: ignore[arg-type]

    def test_float_stretch_score_raises_type_error(self) -> None:
        """Float stretch score raises TypeError."""
        with pytest.raises(TypeError, match="Stretch score must be an integer"):
            interpret_combined_scores(fit_score=75, stretch_score=80.5)  # type: ignore[arg-type]

    def test_string_fit_score_raises_type_error(self) -> None:
        """String fit score raises TypeError."""
        with pytest.raises(TypeError, match="Fit score must be an integer"):
            interpret_combined_scores(fit_score="75", stretch_score=80)  # type: ignore[arg-type]

    def test_string_stretch_score_raises_type_error(self) -> None:
        """String stretch score raises TypeError."""
        with pytest.raises(TypeError, match="Stretch score must be an integer"):
            interpret_combined_scores(fit_score=75, stretch_score="80")  # type: ignore[arg-type]

    def test_none_fit_score_raises_type_error(self) -> None:
        """None fit score raises TypeError."""
        with pytest.raises(TypeError, match="Fit score must be an integer"):
            interpret_combined_scores(fit_score=None, stretch_score=80)  # type: ignore[arg-type]

    def test_none_stretch_score_raises_type_error(self) -> None:
        """None stretch score raises TypeError."""
        with pytest.raises(TypeError, match="Stretch score must be an integer"):
            interpret_combined_scores(fit_score=75, stretch_score=None)  # type: ignore[arg-type]


# =============================================================================
# CombinedRecommendation Enum Tests
# =============================================================================


class TestCombinedRecommendationEnum:
    """Tests for CombinedRecommendation enum."""

    def test_enum_has_all_recommendations(self) -> None:
        """Enum has all 4 recommendation labels."""
        labels = [label.value for label in CombinedRecommendation]
        assert "Top Priority" in labels
        assert "Safe Bet" in labels
        assert "Stretch Opportunity" in labels
        assert "Likely Skip" in labels

    def test_enum_count(self) -> None:
        """Enum has exactly 4 recommendations."""
        assert len(CombinedRecommendation) == 4


# =============================================================================
# Immutability Tests
# =============================================================================


class TestCombinedInterpretationImmutability:
    """Tests for CombinedInterpretationResult immutability."""

    def test_cannot_modify_fit_score(self) -> None:
        """Cannot modify fit_score attribute after creation."""
        result = interpret_combined_scores(fit_score=75, stretch_score=80)
        with pytest.raises(AttributeError):
            result.fit_score = 90  # type: ignore[misc]

    def test_cannot_modify_stretch_score(self) -> None:
        """Cannot modify stretch_score attribute after creation."""
        result = interpret_combined_scores(fit_score=75, stretch_score=80)
        with pytest.raises(AttributeError):
            result.stretch_score = 90  # type: ignore[misc]

    def test_cannot_modify_recommendation(self) -> None:
        """Cannot modify recommendation attribute after creation."""
        result = interpret_combined_scores(fit_score=75, stretch_score=80)
        with pytest.raises(AttributeError):
            result.recommendation = CombinedRecommendation.LIKELY_SKIP  # type: ignore[misc]

    def test_cannot_modify_guidance(self) -> None:
        """Cannot modify guidance attribute after creation."""
        result = interpret_combined_scores(fit_score=75, stretch_score=80)
        with pytest.raises(AttributeError):
            result.guidance = "Modified"  # type: ignore[misc]
