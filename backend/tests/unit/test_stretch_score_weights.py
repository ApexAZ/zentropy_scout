"""Unit tests for Stretch Score component weights.

REQ-008 §5.1: Stretch Score component weights validation.

Tests cover:
- get_stretch_component_weights() returns values that sum to 100%
"""

from app.services.stretch_score import get_stretch_component_weights

# =============================================================================
# get_stretch_component_weights() Tests
# =============================================================================


class TestGetStretchComponentWeights:
    """Tests for the get_stretch_component_weights accessor function."""

    def test_dict_values_sum_to_100_percent(self) -> None:
        """Dictionary values sum to 1.0 (100%)."""
        weights = get_stretch_component_weights()
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001
