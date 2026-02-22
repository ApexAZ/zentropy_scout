"""Tests for quality metrics tracking.

REQ-010 §10.1: Generation Quality Tracking.

Five metrics with targets and alert thresholds for monitoring content
generation quality over time.
"""

from dataclasses import replace

from app.services.quality_metrics import (
    ALL_METRICS,
    AVG_REGENERATIONS_PER_LETTER,
    FIRST_DRAFT_APPROVAL_RATE,
    STORY_SELECTION_SATISFACTION,
    VALIDATION_PASS_RATE,
    VOICE_ADHERENCE_SCORE,
    MetricStatus,
    evaluate_metric,
)

# =============================================================================
# QualityMetricDefinition Structure
# =============================================================================


class TestQualityMetricDefinitionImmutability:
    """Tests for QualityMetricDefinition immutability via behavioral approach."""

    def test_definition_preserves_original_values(self) -> None:
        """Modifying a copy preserves the original metric values."""
        original_target = FIRST_DRAFT_APPROVAL_RATE.target
        updated = replace(FIRST_DRAFT_APPROVAL_RATE, target=0.99)
        assert FIRST_DRAFT_APPROVAL_RATE.target == original_target
        assert updated.target == 0.99


# =============================================================================
# ALL_METRICS Collection
# =============================================================================


class TestAllMetrics:
    """Tests for the ALL_METRICS collection."""

    def test_all_metric_names_are_unique(self) -> None:
        """Each metric should have a distinct name."""
        names = [m.name for m in ALL_METRICS]
        assert len(names) == len(set(names))

    def test_alert_thresholds_are_worse_than_targets(self) -> None:
        """Alert threshold should always be worse than target for all metrics."""
        for metric in ALL_METRICS:
            if metric.higher_is_better:
                assert metric.alert_threshold < metric.target, metric.name
            else:
                assert metric.alert_threshold > metric.target, metric.name


# =============================================================================
# evaluate_metric — Higher-Is-Better Metrics
# =============================================================================


class TestEvaluateHigherIsBetter:
    """Tests for evaluate_metric with higher_is_better=True metrics."""

    def test_above_target_is_on_target(self) -> None:
        """Value above target should return ON_TARGET."""
        result = evaluate_metric(0.75, FIRST_DRAFT_APPROVAL_RATE)
        assert result == MetricStatus.ON_TARGET

    def test_at_target_is_on_target(self) -> None:
        """Value exactly at target should return ON_TARGET."""
        result = evaluate_metric(0.60, FIRST_DRAFT_APPROVAL_RATE)
        assert result == MetricStatus.ON_TARGET

    def test_between_target_and_alert_is_below_target(self) -> None:
        """Value between target and alert should return BELOW_TARGET."""
        result = evaluate_metric(0.50, FIRST_DRAFT_APPROVAL_RATE)
        assert result == MetricStatus.BELOW_TARGET

    def test_at_alert_threshold_is_alert(self) -> None:
        """Value exactly at alert threshold should return ALERT."""
        result = evaluate_metric(0.40, FIRST_DRAFT_APPROVAL_RATE)
        assert result == MetricStatus.ALERT

    def test_below_alert_is_alert(self) -> None:
        """Value below alert threshold should return ALERT."""
        result = evaluate_metric(0.20, FIRST_DRAFT_APPROVAL_RATE)
        assert result == MetricStatus.ALERT


# =============================================================================
# evaluate_metric — Lower-Is-Better Metrics
# =============================================================================


class TestEvaluateLowerIsBetter:
    """Tests for evaluate_metric with higher_is_better=False metrics."""

    def test_below_target_is_on_target(self) -> None:
        """Value below target should return ON_TARGET."""
        result = evaluate_metric(1.0, AVG_REGENERATIONS_PER_LETTER)
        assert result == MetricStatus.ON_TARGET

    def test_at_target_is_on_target(self) -> None:
        """Value exactly at target should return ON_TARGET."""
        result = evaluate_metric(1.5, AVG_REGENERATIONS_PER_LETTER)
        assert result == MetricStatus.ON_TARGET

    def test_between_target_and_alert_is_below_target(self) -> None:
        """Value between target and alert should return BELOW_TARGET."""
        result = evaluate_metric(2.0, AVG_REGENERATIONS_PER_LETTER)
        assert result == MetricStatus.BELOW_TARGET

    def test_at_alert_threshold_is_alert(self) -> None:
        """Value exactly at alert threshold should return ALERT."""
        result = evaluate_metric(2.5, AVG_REGENERATIONS_PER_LETTER)
        assert result == MetricStatus.ALERT

    def test_above_alert_is_alert(self) -> None:
        """Value above alert threshold should return ALERT."""
        result = evaluate_metric(3.5, AVG_REGENERATIONS_PER_LETTER)
        assert result == MetricStatus.ALERT


# =============================================================================
# evaluate_metric — All Metric Types
# =============================================================================


class TestEvaluateAllMetrics:
    """Verify evaluate_metric works correctly with each defined metric."""

    def test_validation_pass_rate_on_target(self) -> None:
        """95% validation pass rate should be ON_TARGET."""
        assert evaluate_metric(0.95, VALIDATION_PASS_RATE) == MetricStatus.ON_TARGET

    def test_validation_pass_rate_below_target(self) -> None:
        """85% validation pass rate should be BELOW_TARGET."""
        assert evaluate_metric(0.85, VALIDATION_PASS_RATE) == MetricStatus.BELOW_TARGET

    def test_validation_pass_rate_alert(self) -> None:
        """75% validation pass rate should be ALERT."""
        assert evaluate_metric(0.75, VALIDATION_PASS_RATE) == MetricStatus.ALERT

    def test_voice_adherence_on_target(self) -> None:
        """4.5 voice adherence should be ON_TARGET."""
        assert evaluate_metric(4.5, VOICE_ADHERENCE_SCORE) == MetricStatus.ON_TARGET

    def test_voice_adherence_below_target(self) -> None:
        """3.5 voice adherence should be BELOW_TARGET."""
        assert evaluate_metric(3.5, VOICE_ADHERENCE_SCORE) == MetricStatus.BELOW_TARGET

    def test_voice_adherence_alert(self) -> None:
        """2.5 voice adherence should be ALERT."""
        assert evaluate_metric(2.5, VOICE_ADHERENCE_SCORE) == MetricStatus.ALERT

    def test_story_satisfaction_on_target(self) -> None:
        """80% story satisfaction should be ON_TARGET."""
        assert (
            evaluate_metric(0.80, STORY_SELECTION_SATISFACTION)
            == MetricStatus.ON_TARGET
        )

    def test_story_satisfaction_alert(self) -> None:
        """45% story satisfaction should be ALERT."""
        assert evaluate_metric(0.45, STORY_SELECTION_SATISFACTION) == MetricStatus.ALERT


# =============================================================================
# Edge Cases
# =============================================================================


class TestEvaluateEdgeCases:
    """Boundary conditions for evaluate_metric."""

    def test_negative_value_higher_is_better(self) -> None:
        """Negative value should be ALERT for higher-is-better metric."""
        assert evaluate_metric(-0.5, FIRST_DRAFT_APPROVAL_RATE) == MetricStatus.ALERT

    def test_zero_value_higher_is_better(self) -> None:
        """Zero should be ALERT for first draft approval rate (alert=0.40)."""
        assert evaluate_metric(0.0, FIRST_DRAFT_APPROVAL_RATE) == MetricStatus.ALERT

    def test_zero_value_lower_is_better(self) -> None:
        """Zero should be ON_TARGET for avg regenerations (target=1.5)."""
        assert (
            evaluate_metric(0.0, AVG_REGENERATIONS_PER_LETTER) == MetricStatus.ON_TARGET
        )

    def test_negative_value_lower_is_better(self) -> None:
        """Negative regeneration count should be ON_TARGET (impossible but fail-safe)."""
        assert (
            evaluate_metric(-1.0, AVG_REGENERATIONS_PER_LETTER)
            == MetricStatus.ON_TARGET
        )
