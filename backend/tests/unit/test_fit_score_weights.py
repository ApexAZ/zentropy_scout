"""Tests for Fit Score component weights.

REQ-008 §4.1: Fit Score Component Weights.

Tests cover:
- get_fit_component_weights() returns values that sum to 100%
"""

from app.services.scoring.fit_score import get_fit_component_weights

# =============================================================================
# Accessor Function Tests
# =============================================================================


class TestGetFitComponentWeights:
    """Tests for get_fit_component_weights() accessor."""

    def test_dict_values_sum_to_100_percent(self) -> None:
        """Dictionary values sum to 1.0 (100%)."""
        weights = get_fit_component_weights()
        total = sum(weights.values())

        assert abs(total - 1.0) < 0.001
