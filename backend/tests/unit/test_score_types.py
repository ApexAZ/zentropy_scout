"""Tests for score types definitions.

REQ-008 §1.1: Score Types.

Zentropy Scout uses three score types:
- Fit Score (0-100): How well current skills match job requirements
- Stretch Score (0-100): How well job aligns with growth targets
- Ghost Score (0-100): Likelihood posting is stale/fake (REQ-003 §7)
"""

from app.services.score_types import (
    ScoreInterpretation,
    interpret_fit_score,
    interpret_ghost_score,
    interpret_stretch_score,
)

# =============================================================================
# Fit Score Interpretation Tests (REQ-008 §7.1)
# =============================================================================


class TestInterpretFitScore:
    """Tests for interpret_fit_score function.

    REQ-008 §7.1: Fit Score Thresholds
    - 80-100: Excellent match
    - 60-79: Good match, apply with confidence
    - 40-59: Moderate match, worth considering
    - 0-39: Low match
    """

    def test_excellent_fit_at_threshold(self) -> None:
        """Score of 80 is Excellent."""
        result = interpret_fit_score(80)
        assert result == ScoreInterpretation.FIT_EXCELLENT

    def test_excellent_fit_at_max(self) -> None:
        """Score of 100 is Excellent."""
        result = interpret_fit_score(100)
        assert result == ScoreInterpretation.FIT_EXCELLENT

    def test_good_fit_at_threshold(self) -> None:
        """Score of 60 is Good."""
        result = interpret_fit_score(60)
        assert result == ScoreInterpretation.FIT_GOOD

    def test_good_fit_just_below_excellent(self) -> None:
        """Score of 79 is Good (just below Excellent)."""
        result = interpret_fit_score(79)
        assert result == ScoreInterpretation.FIT_GOOD

    def test_moderate_fit_at_threshold(self) -> None:
        """Score of 40 is Moderate."""
        result = interpret_fit_score(40)
        assert result == ScoreInterpretation.FIT_MODERATE

    def test_moderate_fit_just_below_good(self) -> None:
        """Score of 59 is Moderate (just below Good)."""
        result = interpret_fit_score(59)
        assert result == ScoreInterpretation.FIT_MODERATE

    def test_low_fit_at_threshold(self) -> None:
        """Score of 39 is Low."""
        result = interpret_fit_score(39)
        assert result == ScoreInterpretation.FIT_LOW

    def test_low_fit_at_zero(self) -> None:
        """Score of 0 is Low."""
        result = interpret_fit_score(0)
        assert result == ScoreInterpretation.FIT_LOW


# =============================================================================
# Stretch Score Interpretation Tests (REQ-008 §7.2)
# =============================================================================


class TestInterpretStretchScore:
    """Tests for interpret_stretch_score function.

    REQ-008 §7.2: Stretch Score Thresholds
    - 70-100: High stretch value (significant growth potential)
    - 40-69: Moderate stretch (some growth opportunities)
    - 0-39: Low stretch (similar to current role)
    """

    def test_high_stretch_at_threshold(self) -> None:
        """Score of 70 is High."""
        result = interpret_stretch_score(70)
        assert result == ScoreInterpretation.STRETCH_HIGH

    def test_high_stretch_at_max(self) -> None:
        """Score of 100 is High."""
        result = interpret_stretch_score(100)
        assert result == ScoreInterpretation.STRETCH_HIGH

    def test_moderate_stretch_at_threshold(self) -> None:
        """Score of 40 is Moderate."""
        result = interpret_stretch_score(40)
        assert result == ScoreInterpretation.STRETCH_MODERATE

    def test_moderate_stretch_just_below_high(self) -> None:
        """Score of 69 is Moderate (just below High)."""
        result = interpret_stretch_score(69)
        assert result == ScoreInterpretation.STRETCH_MODERATE

    def test_low_stretch_at_threshold(self) -> None:
        """Score of 39 is Low."""
        result = interpret_stretch_score(39)
        assert result == ScoreInterpretation.STRETCH_LOW

    def test_low_stretch_at_zero(self) -> None:
        """Score of 0 is Low."""
        result = interpret_stretch_score(0)
        assert result == ScoreInterpretation.STRETCH_LOW


# =============================================================================
# Ghost Score Interpretation Tests (REQ-003 §7.3)
# =============================================================================


class TestInterpretGhostScore:
    """Tests for interpret_ghost_score function.

    REQ-003 §7.3: Ghost Score Interpretation
    - 0-25: Fresh (no warning)
    - 26-50: Moderate (light warning)
    - 51-75: Elevated (recommend verification)
    - 76-100: High Risk (suggest skipping)
    """

    def test_fresh_at_max_threshold(self) -> None:
        """Score of 25 is Fresh."""
        result = interpret_ghost_score(25)
        assert result == ScoreInterpretation.GHOST_FRESH

    def test_fresh_at_zero(self) -> None:
        """Score of 0 is Fresh."""
        result = interpret_ghost_score(0)
        assert result == ScoreInterpretation.GHOST_FRESH

    def test_moderate_at_threshold(self) -> None:
        """Score of 26 is Moderate."""
        result = interpret_ghost_score(26)
        assert result == ScoreInterpretation.GHOST_MODERATE

    def test_moderate_at_max(self) -> None:
        """Score of 50 is Moderate."""
        result = interpret_ghost_score(50)
        assert result == ScoreInterpretation.GHOST_MODERATE

    def test_elevated_at_threshold(self) -> None:
        """Score of 51 is Elevated."""
        result = interpret_ghost_score(51)
        assert result == ScoreInterpretation.GHOST_ELEVATED

    def test_elevated_at_max(self) -> None:
        """Score of 75 is Elevated."""
        result = interpret_ghost_score(75)
        assert result == ScoreInterpretation.GHOST_ELEVATED

    def test_high_risk_at_threshold(self) -> None:
        """Score of 76 is High Risk."""
        result = interpret_ghost_score(76)
        assert result == ScoreInterpretation.GHOST_HIGH_RISK

    def test_high_risk_at_max(self) -> None:
        """Score of 100 is High Risk."""
        result = interpret_ghost_score(100)
        assert result == ScoreInterpretation.GHOST_HIGH_RISK
