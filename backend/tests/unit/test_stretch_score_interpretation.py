"""Unit tests for Stretch Score interpretation.

REQ-008 §7.2: Stretch Score Thresholds.

Tests cover:
- Threshold label and interpretation text mapping
- Boundary conditions at threshold edges
- Input validation (out of range scores, type validation)
- Integration with calculate_stretch_score
"""

import pytest

from app.services.scoring.stretch_score import (
    StretchScoreLabel,
    calculate_stretch_score,
    interpret_stretch_score,
)

# =============================================================================
# Threshold Label & Interpretation Tests (REQ-008 §7.2)
# =============================================================================


class TestStretchScoreThresholds:
    """Tests for Stretch Score to label and interpretation mapping."""

    @pytest.mark.parametrize(
        ("score", "expected_label", "expected_interpretation"),
        [
            # High Growth (80-100)
            (100, StretchScoreLabel.HIGH_GROWTH, "Strong alignment with career goals"),
            (90, StretchScoreLabel.HIGH_GROWTH, "Strong alignment with career goals"),
            (80, StretchScoreLabel.HIGH_GROWTH, "Strong alignment with career goals"),
            # Moderate Growth (60-79)
            (79, StretchScoreLabel.MODERATE_GROWTH, "Some goal alignment"),
            (70, StretchScoreLabel.MODERATE_GROWTH, "Some goal alignment"),
            (60, StretchScoreLabel.MODERATE_GROWTH, "Some goal alignment"),
            # Lateral (40-59)
            (59, StretchScoreLabel.LATERAL, "Similar to current role"),
            (50, StretchScoreLabel.LATERAL, "Similar to current role"),
            (40, StretchScoreLabel.LATERAL, "Similar to current role"),
            # Low Growth (0-39)
            (39, StretchScoreLabel.LOW_GROWTH, "Not aligned with stated goals"),
            (20, StretchScoreLabel.LOW_GROWTH, "Not aligned with stated goals"),
            (0, StretchScoreLabel.LOW_GROWTH, "Not aligned with stated goals"),
        ],
    )
    def test_threshold_label_and_interpretation(
        self,
        score: int,
        expected_label: StretchScoreLabel,
        expected_interpretation: str,
    ) -> None:
        """Score maps to correct label, interpretation text, and stored score."""
        result = interpret_stretch_score(score)

        assert result.score == score
        assert result.label == expected_label
        assert result.interpretation == expected_interpretation


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
