"""Unit tests for Stretch Score interpretation.

REQ-008 §7.2: Stretch Score Thresholds.

Tests cover:
- Threshold label mapping (High Growth, Moderate Growth, Lateral, Low Growth)
- Boundary conditions at threshold edges
- Input validation (out of range scores, type validation)
- Integration with calculate_stretch_score
- Result immutability
"""

from dataclasses import replace

import pytest

from app.services.stretch_score import (
    StretchScoreLabel,
    calculate_stretch_score,
    interpret_stretch_score,
)

# =============================================================================
# Threshold Label Tests (REQ-008 §7.2)
# =============================================================================


class TestStretchScoreThresholdLabels:
    """Tests for Stretch Score to label mapping."""

    # -------------------------------------------------------------------------
    # High Growth (80-100)
    # -------------------------------------------------------------------------

    def test_score_80_returns_high_growth(self) -> None:
        """Score of 80 (lower bound) returns High Growth."""
        result = interpret_stretch_score(80)
        assert result.label == StretchScoreLabel.HIGH_GROWTH

    def test_score_100_returns_high_growth(self) -> None:
        """Score of 100 (upper bound) returns High Growth."""
        result = interpret_stretch_score(100)
        assert result.label == StretchScoreLabel.HIGH_GROWTH

    def test_score_90_returns_high_growth(self) -> None:
        """Score of 90 (mid-range) returns High Growth."""
        result = interpret_stretch_score(90)
        assert result.label == StretchScoreLabel.HIGH_GROWTH

    # -------------------------------------------------------------------------
    # Moderate Growth (60-79)
    # -------------------------------------------------------------------------

    def test_score_60_returns_moderate_growth(self) -> None:
        """Score of 60 (lower bound) returns Moderate Growth."""
        result = interpret_stretch_score(60)
        assert result.label == StretchScoreLabel.MODERATE_GROWTH

    def test_score_79_returns_moderate_growth(self) -> None:
        """Score of 79 (upper bound) returns Moderate Growth."""
        result = interpret_stretch_score(79)
        assert result.label == StretchScoreLabel.MODERATE_GROWTH

    def test_score_70_returns_moderate_growth(self) -> None:
        """Score of 70 (mid-range) returns Moderate Growth."""
        result = interpret_stretch_score(70)
        assert result.label == StretchScoreLabel.MODERATE_GROWTH

    # -------------------------------------------------------------------------
    # Lateral (40-59)
    # -------------------------------------------------------------------------

    def test_score_40_returns_lateral(self) -> None:
        """Score of 40 (lower bound) returns Lateral."""
        result = interpret_stretch_score(40)
        assert result.label == StretchScoreLabel.LATERAL

    def test_score_59_returns_lateral(self) -> None:
        """Score of 59 (upper bound) returns Lateral."""
        result = interpret_stretch_score(59)
        assert result.label == StretchScoreLabel.LATERAL

    def test_score_50_returns_lateral(self) -> None:
        """Score of 50 (mid-range) returns Lateral."""
        result = interpret_stretch_score(50)
        assert result.label == StretchScoreLabel.LATERAL

    # -------------------------------------------------------------------------
    # Low Growth (0-39)
    # -------------------------------------------------------------------------

    def test_score_0_returns_low_growth(self) -> None:
        """Score of 0 (lower bound) returns Low Growth."""
        result = interpret_stretch_score(0)
        assert result.label == StretchScoreLabel.LOW_GROWTH

    def test_score_39_returns_low_growth(self) -> None:
        """Score of 39 (upper bound) returns Low Growth."""
        result = interpret_stretch_score(39)
        assert result.label == StretchScoreLabel.LOW_GROWTH

    def test_score_20_returns_low_growth(self) -> None:
        """Score of 20 (mid-range) returns Low Growth."""
        result = interpret_stretch_score(20)
        assert result.label == StretchScoreLabel.LOW_GROWTH


# =============================================================================
# Interpretation Text Tests
# =============================================================================


class TestStretchScoreInterpretationText:
    """Tests for interpretation text in result."""

    def test_high_growth_has_interpretation_text(self) -> None:
        """High Growth result includes interpretation text."""
        result = interpret_stretch_score(90)
        assert result.interpretation == "Strong alignment with career goals"

    def test_moderate_growth_has_interpretation_text(self) -> None:
        """Moderate Growth result includes interpretation text."""
        result = interpret_stretch_score(70)
        assert result.interpretation == "Some goal alignment"

    def test_lateral_has_interpretation_text(self) -> None:
        """Lateral result includes interpretation text."""
        result = interpret_stretch_score(50)
        assert result.interpretation == "Similar to current role"

    def test_low_growth_has_interpretation_text(self) -> None:
        """Low Growth result includes interpretation text."""
        result = interpret_stretch_score(20)
        assert result.interpretation == "Not aligned with stated goals"


# =============================================================================
# Result Structure Tests
# =============================================================================


class TestStretchScoreInterpretationResult:
    """Tests for interpretation result structure."""

    def test_result_has_score(self) -> None:
        """Result includes the original score."""
        result = interpret_stretch_score(75)
        assert result.score == 75

    def test_result_has_label(self) -> None:
        """Result includes the label enum."""
        result = interpret_stretch_score(75)
        assert result.label == StretchScoreLabel.MODERATE_GROWTH

    def test_result_has_interpretation(self) -> None:
        """Result includes interpretation text."""
        result = interpret_stretch_score(75)
        assert result.interpretation is not None


# =============================================================================
# Input Validation Tests
# =============================================================================


class TestStretchScoreInterpretationValidation:
    """Tests for input validation."""

    def test_negative_score_raises_error(self) -> None:
        """Negative score raises ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            interpret_stretch_score(-1)

    def test_score_over_100_raises_error(self) -> None:
        """Score over 100 raises ValueError."""
        with pytest.raises(ValueError, match="cannot exceed 100"):
            interpret_stretch_score(101)

    def test_boundary_0_is_valid(self) -> None:
        """Score of 0 is valid."""
        result = interpret_stretch_score(0)
        assert result.score == 0

    def test_boundary_100_is_valid(self) -> None:
        """Score of 100 is valid."""
        result = interpret_stretch_score(100)
        assert result.score == 100


# =============================================================================
# Type Validation Tests
# =============================================================================


class TestStretchScoreTypeValidation:
    """Tests for type validation in interpret_stretch_score."""

    def test_float_input_raises_type_error(self) -> None:
        """Float input raises TypeError."""
        with pytest.raises(TypeError, match="must be an integer"):
            interpret_stretch_score(75.5)  # type: ignore[arg-type]

    def test_string_input_raises_type_error(self) -> None:
        """String input raises TypeError."""
        with pytest.raises(TypeError, match="must be an integer"):
            interpret_stretch_score("85")  # type: ignore[arg-type]

    def test_none_input_raises_type_error(self) -> None:
        """None input raises TypeError."""
        with pytest.raises(TypeError, match="must be an integer"):
            interpret_stretch_score(None)  # type: ignore[arg-type]


# =============================================================================
# Integration Tests
# =============================================================================


class TestStretchScoreIntegration:
    """Tests for integration with calculate_stretch_score."""

    def test_chain_calculate_and_interpret(self) -> None:
        """Can chain calculate_stretch_score result into interpret_stretch_score."""
        stretch_result = calculate_stretch_score(
            target_role=90.0,
            target_skills=85.0,
            growth_trajectory=80.0,
        )
        interpretation = interpret_stretch_score(stretch_result.total)
        assert interpretation.score == stretch_result.total
        assert interpretation.label in StretchScoreLabel

    def test_chain_high_growth_score(self) -> None:
        """calculate_stretch_score producing 80+ is interpreted as High Growth."""
        stretch_result = calculate_stretch_score(
            target_role=100.0,
            target_skills=100.0,
            growth_trajectory=100.0,
        )
        interpretation = interpret_stretch_score(stretch_result.total)
        assert interpretation.label == StretchScoreLabel.HIGH_GROWTH

    def test_chain_low_growth_score(self) -> None:
        """calculate_stretch_score producing 0-39 is interpreted as Low Growth."""
        stretch_result = calculate_stretch_score(
            target_role=0.0,
            target_skills=0.0,
            growth_trajectory=0.0,
        )
        interpretation = interpret_stretch_score(stretch_result.total)
        assert interpretation.label == StretchScoreLabel.LOW_GROWTH


# =============================================================================
# Immutability Tests
# =============================================================================


class TestStretchScoreInterpretationImmutability:
    """Tests for StretchScoreInterpretation immutability via behavioral approach."""

    def test_interpretation_preserves_original_score(self) -> None:
        """Modifying a copy preserves the original score."""
        result = interpret_stretch_score(75)
        updated = replace(result, score=90)
        assert result.score == 75
        assert updated.score == 90

    def test_interpretation_preserves_original_label(self) -> None:
        """Modifying a copy preserves the original label."""
        result = interpret_stretch_score(75)
        updated = replace(result, label=StretchScoreLabel.HIGH_GROWTH)
        assert result.label == StretchScoreLabel.MODERATE_GROWTH
        assert updated.label == StretchScoreLabel.HIGH_GROWTH

    def test_interpretation_preserves_original_text(self) -> None:
        """Modifying a copy preserves the original interpretation text."""
        result = interpret_stretch_score(75)
        original_text = result.interpretation
        updated = replace(result, interpretation="Modified")
        assert result.interpretation == original_text
        assert updated.interpretation == "Modified"
