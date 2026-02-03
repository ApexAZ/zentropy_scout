"""Unit tests for Auto-Draft Threshold.

REQ-008 §7.4: Auto-Draft Threshold.

Tests cover:
- Jobs meeting threshold (fit_score >= 90) qualify for auto-draft
- Jobs below threshold (fit_score < 90) do not qualify
- Boundary conditions at threshold edge (89, 90)
- Input validation (out of range scores, type validation)
- Threshold constant accessibility
"""

import pytest

from app.services.fit_score import (
    AUTO_DRAFT_THRESHOLD,
    qualifies_for_auto_draft,
)

# =============================================================================
# Threshold Constant Tests (REQ-008 §7.4)
# =============================================================================


class TestAutoDraftThresholdConstant:
    """Tests for AUTO_DRAFT_THRESHOLD constant."""

    def test_default_threshold_is_90(self) -> None:
        """Default auto-draft threshold is 90 per REQ-008 §7.4."""
        assert AUTO_DRAFT_THRESHOLD == 90

    def test_threshold_is_integer(self) -> None:
        """Threshold must be an integer."""
        assert isinstance(AUTO_DRAFT_THRESHOLD, int)


# =============================================================================
# Qualification Tests (REQ-008 §7.4)
# =============================================================================


class TestQualifiesForAutoDraft:
    """Tests for qualifies_for_auto_draft function."""

    # -------------------------------------------------------------------------
    # Scores AT or ABOVE threshold (90+) → Qualifies
    # -------------------------------------------------------------------------

    def test_score_90_qualifies(self) -> None:
        """Score of 90 (exactly at threshold) qualifies for auto-draft."""
        assert qualifies_for_auto_draft(90) is True

    def test_score_91_qualifies(self) -> None:
        """Score of 91 (above threshold) qualifies for auto-draft."""
        assert qualifies_for_auto_draft(91) is True

    def test_score_95_qualifies(self) -> None:
        """Score of 95 (mid-range above threshold) qualifies for auto-draft."""
        assert qualifies_for_auto_draft(95) is True

    def test_score_100_qualifies(self) -> None:
        """Score of 100 (maximum) qualifies for auto-draft."""
        assert qualifies_for_auto_draft(100) is True

    # -------------------------------------------------------------------------
    # Scores BELOW threshold (<90) → Does NOT qualify
    # -------------------------------------------------------------------------

    def test_score_89_does_not_qualify(self) -> None:
        """Score of 89 (just below threshold) does not qualify for auto-draft."""
        assert qualifies_for_auto_draft(89) is False

    def test_score_75_does_not_qualify(self) -> None:
        """Score of 75 (Medium tier) does not qualify for auto-draft."""
        assert qualifies_for_auto_draft(75) is False

    def test_score_60_does_not_qualify(self) -> None:
        """Score of 60 (Low tier) does not qualify for auto-draft."""
        assert qualifies_for_auto_draft(60) is False

    def test_score_0_does_not_qualify(self) -> None:
        """Score of 0 (minimum) does not qualify for auto-draft."""
        assert qualifies_for_auto_draft(0) is False

    def test_score_50_does_not_qualify(self) -> None:
        """Score of 50 (Poor tier) does not qualify for auto-draft."""
        assert qualifies_for_auto_draft(50) is False


# =============================================================================
# Validation Tests (REQ-008 §7.4)
# =============================================================================


class TestQualifiesForAutoDraftValidation:
    """Tests for input validation in qualifies_for_auto_draft."""

    # -------------------------------------------------------------------------
    # Type validation
    # -------------------------------------------------------------------------

    def test_rejects_float_input(self) -> None:
        """Float input raises TypeError."""
        with pytest.raises(TypeError, match="must be an integer"):
            qualifies_for_auto_draft(90.5)  # type: ignore[arg-type]

    def test_rejects_string_input(self) -> None:
        """String input raises TypeError."""
        with pytest.raises(TypeError, match="must be an integer"):
            qualifies_for_auto_draft("90")  # type: ignore[arg-type]

    def test_rejects_none_input(self) -> None:
        """None input raises TypeError."""
        with pytest.raises(TypeError, match="must be an integer"):
            qualifies_for_auto_draft(None)  # type: ignore[arg-type]

    def test_rejects_bool_true_input(self) -> None:
        """Boolean True input raises TypeError (bool is subclass of int)."""
        with pytest.raises(TypeError, match="must be an integer"):
            qualifies_for_auto_draft(True)  # type: ignore[arg-type]

    def test_rejects_bool_false_input(self) -> None:
        """Boolean False input raises TypeError (bool is subclass of int)."""
        with pytest.raises(TypeError, match="must be an integer"):
            qualifies_for_auto_draft(False)  # type: ignore[arg-type]

    # -------------------------------------------------------------------------
    # Range validation
    # -------------------------------------------------------------------------

    def test_rejects_negative_score(self) -> None:
        """Negative score raises ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            qualifies_for_auto_draft(-1)

    def test_rejects_score_over_100(self) -> None:
        """Score over 100 raises ValueError."""
        with pytest.raises(ValueError, match="cannot exceed 100"):
            qualifies_for_auto_draft(101)


# =============================================================================
# Boundary Tests (REQ-008 §7.4)
# =============================================================================


class TestAutoDraftBoundaryConditions:
    """Tests for boundary conditions at threshold edge."""

    def test_boundary_89_90(self) -> None:
        """Boundary at 89/90 - 89 does not qualify, 90 does."""
        assert qualifies_for_auto_draft(89) is False
        assert qualifies_for_auto_draft(90) is True

    def test_boundary_0_is_valid(self) -> None:
        """Score of 0 is valid (does not qualify)."""
        result = qualifies_for_auto_draft(0)
        assert result is False

    def test_boundary_100_is_valid(self) -> None:
        """Score of 100 is valid (qualifies)."""
        result = qualifies_for_auto_draft(100)
        assert result is True
