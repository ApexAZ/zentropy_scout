"""Unit tests for Fit Score interpretation.

REQ-008 §7.1: Fit Score Thresholds.

Tests cover:
- Threshold label mapping (High, Medium, Low, Poor)
- Boundary conditions at threshold edges
- Input validation (out of range scores, type validation)
- Integration with calculate_fit_score
- Result immutability

Note: Refactored from 5 tiers to 4 tiers (2026-02-02). The "Stretch" label
was removed because it conflicted with the separate "Stretch Score" concept.
Labels simplified from Excellent/Good/Fair/Poor to High/Medium/Low/Poor (2026-02-03).
"""

import pytest

from app.services.fit_score import (
    FitScoreLabel,
    calculate_fit_score,
    interpret_fit_score,
)

# =============================================================================
# Threshold Label Tests (REQ-008 §7.1)
# =============================================================================


class TestFitScoreThresholdLabels:
    """Tests for Fit Score to label mapping."""

    # -------------------------------------------------------------------------
    # High (90-100)
    # -------------------------------------------------------------------------

    def test_score_90_returns_high(self) -> None:
        """Score of 90 (lower bound) returns High."""
        result = interpret_fit_score(90)
        assert result.label == FitScoreLabel.HIGH

    def test_score_100_returns_high(self) -> None:
        """Score of 100 (upper bound) returns High."""
        result = interpret_fit_score(100)
        assert result.label == FitScoreLabel.HIGH

    def test_score_95_returns_high(self) -> None:
        """Score of 95 (mid-range) returns High."""
        result = interpret_fit_score(95)
        assert result.label == FitScoreLabel.HIGH

    # -------------------------------------------------------------------------
    # Medium (75-89)
    # -------------------------------------------------------------------------

    def test_score_75_returns_medium(self) -> None:
        """Score of 75 (lower bound) returns Medium."""
        result = interpret_fit_score(75)
        assert result.label == FitScoreLabel.MEDIUM

    def test_score_89_returns_medium(self) -> None:
        """Score of 89 (upper bound) returns Medium."""
        result = interpret_fit_score(89)
        assert result.label == FitScoreLabel.MEDIUM

    def test_score_82_returns_medium(self) -> None:
        """Score of 82 (mid-range) returns Medium."""
        result = interpret_fit_score(82)
        assert result.label == FitScoreLabel.MEDIUM

    # -------------------------------------------------------------------------
    # Low (60-74)
    # -------------------------------------------------------------------------

    def test_score_60_returns_low(self) -> None:
        """Score of 60 (lower bound) returns Low."""
        result = interpret_fit_score(60)
        assert result.label == FitScoreLabel.LOW

    def test_score_74_returns_low(self) -> None:
        """Score of 74 (upper bound) returns Low."""
        result = interpret_fit_score(74)
        assert result.label == FitScoreLabel.LOW

    def test_score_67_returns_low(self) -> None:
        """Score of 67 (mid-range) returns Low."""
        result = interpret_fit_score(67)
        assert result.label == FitScoreLabel.LOW

    # -------------------------------------------------------------------------
    # Poor (0-59) — Combined with former "Stretch" tier
    # -------------------------------------------------------------------------

    def test_score_0_returns_poor(self) -> None:
        """Score of 0 (lower bound) returns Poor."""
        result = interpret_fit_score(0)
        assert result.label == FitScoreLabel.POOR

    def test_score_59_returns_poor(self) -> None:
        """Score of 59 (upper bound) returns Poor."""
        result = interpret_fit_score(59)
        assert result.label == FitScoreLabel.POOR

    def test_score_30_returns_poor(self) -> None:
        """Score of 30 (mid-range) returns Poor."""
        result = interpret_fit_score(30)
        assert result.label == FitScoreLabel.POOR


# =============================================================================
# Interpretation Text Tests
# =============================================================================


class TestFitScoreInterpretationText:
    """Tests for interpretation text in result."""

    def test_high_has_interpretation_text(self) -> None:
        """High result includes interpretation text."""
        result = interpret_fit_score(95)
        assert result.interpretation == "Strong match, high confidence"

    def test_medium_has_interpretation_text(self) -> None:
        """Medium result includes interpretation text."""
        result = interpret_fit_score(82)
        assert result.interpretation == "Solid match, minor gaps"

    def test_low_has_interpretation_text(self) -> None:
        """Low result includes interpretation text."""
        result = interpret_fit_score(67)
        assert result.interpretation == "Partial match, notable gaps"

    def test_poor_has_interpretation_text(self) -> None:
        """Poor result includes interpretation text."""
        result = interpret_fit_score(30)
        assert result.interpretation == "Not a good fit"


# =============================================================================
# Result Structure Tests
# =============================================================================


class TestFitScoreInterpretationResult:
    """Tests for interpretation result structure."""

    def test_result_has_score(self) -> None:
        """Result includes the original score."""
        result = interpret_fit_score(85)
        assert result.score == 85

    def test_result_has_label(self) -> None:
        """Result includes the label enum."""
        result = interpret_fit_score(85)
        assert result.label == FitScoreLabel.MEDIUM

    def test_result_has_interpretation(self) -> None:
        """Result includes interpretation text."""
        result = interpret_fit_score(85)
        assert result.interpretation is not None


# =============================================================================
# Input Validation Tests
# =============================================================================


class TestFitScoreInterpretationValidation:
    """Tests for input validation."""

    def test_negative_score_raises_error(self) -> None:
        """Negative score raises ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            interpret_fit_score(-1)

    def test_score_over_100_raises_error(self) -> None:
        """Score over 100 raises ValueError."""
        with pytest.raises(ValueError, match="cannot exceed 100"):
            interpret_fit_score(101)

    def test_boundary_0_is_valid(self) -> None:
        """Score of 0 is valid."""
        result = interpret_fit_score(0)
        assert result.score == 0

    def test_boundary_100_is_valid(self) -> None:
        """Score of 100 is valid."""
        result = interpret_fit_score(100)
        assert result.score == 100


# =============================================================================
# FitScoreLabel Enum Tests
# =============================================================================


class TestFitScoreLabelEnum:
    """Tests for FitScoreLabel enum."""

    def test_enum_has_all_labels(self) -> None:
        """Enum has all 4 threshold labels."""
        labels = [label.value for label in FitScoreLabel]
        assert "High" in labels
        assert "Medium" in labels
        assert "Low" in labels
        assert "Poor" in labels

    def test_enum_count(self) -> None:
        """Enum has exactly 4 labels."""
        assert len(FitScoreLabel) == 4


# =============================================================================
# Type Validation Tests
# =============================================================================


class TestFitScoreTypeValidation:
    """Tests for type validation in interpret_fit_score."""

    def test_float_input_raises_type_error(self) -> None:
        """Float input raises TypeError."""
        with pytest.raises(TypeError, match="must be an integer"):
            interpret_fit_score(75.5)  # type: ignore[arg-type]

    def test_string_input_raises_type_error(self) -> None:
        """String input raises TypeError."""
        with pytest.raises(TypeError, match="must be an integer"):
            interpret_fit_score("85")  # type: ignore[arg-type]

    def test_none_input_raises_type_error(self) -> None:
        """None input raises TypeError."""
        with pytest.raises(TypeError, match="must be an integer"):
            interpret_fit_score(None)  # type: ignore[arg-type]


# =============================================================================
# Integration Tests
# =============================================================================


class TestFitScoreIntegration:
    """Tests for integration with calculate_fit_score."""

    def test_chain_calculate_and_interpret(self) -> None:
        """Can chain calculate_fit_score result into interpret_fit_score."""
        fit_result = calculate_fit_score(
            hard_skills=90.0,
            soft_skills=85.0,
            experience_level=80.0,
            role_title=75.0,
            location_logistics=70.0,
        )
        interpretation = interpret_fit_score(fit_result.total)
        assert interpretation.score == fit_result.total
        assert interpretation.label in FitScoreLabel

    def test_chain_high_score(self) -> None:
        """calculate_fit_score producing 90+ is interpreted as High."""
        fit_result = calculate_fit_score(
            hard_skills=100.0,
            soft_skills=100.0,
            experience_level=100.0,
            role_title=100.0,
            location_logistics=100.0,
        )
        interpretation = interpret_fit_score(fit_result.total)
        assert interpretation.label == FitScoreLabel.HIGH

    def test_chain_poor_score(self) -> None:
        """calculate_fit_score producing 0-59 is interpreted as Poor."""
        fit_result = calculate_fit_score(
            hard_skills=0.0,
            soft_skills=0.0,
            experience_level=0.0,
            role_title=0.0,
            location_logistics=0.0,
        )
        interpretation = interpret_fit_score(fit_result.total)
        assert interpretation.label == FitScoreLabel.POOR


# =============================================================================
# Immutability Tests
# =============================================================================


class TestFitScoreInterpretationImmutability:
    """Tests for FitScoreInterpretation immutability."""

    def test_cannot_modify_score(self) -> None:
        """Cannot modify score attribute after creation."""
        result = interpret_fit_score(85)
        with pytest.raises(AttributeError):
            result.score = 90  # type: ignore[misc]

    def test_cannot_modify_label(self) -> None:
        """Cannot modify label attribute after creation."""
        result = interpret_fit_score(85)
        with pytest.raises(AttributeError):
            result.label = FitScoreLabel.HIGH  # type: ignore[misc]

    def test_cannot_modify_interpretation(self) -> None:
        """Cannot modify interpretation attribute after creation."""
        result = interpret_fit_score(85)
        with pytest.raises(AttributeError):
            result.interpretation = "Modified"  # type: ignore[misc]
