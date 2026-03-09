"""Tests for quality metrics tracking.

REQ-010 §10.1: Generation Quality Tracking.

Five metrics with targets and alert thresholds for monitoring content
generation quality over time.
"""

from app.services.quality_metrics import (
    ALL_METRICS,
    AVG_REGENERATIONS_PER_LETTER,
    FIRST_DRAFT_APPROVAL_RATE,
    MetricStatus,
    evaluate_metric,
)

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
