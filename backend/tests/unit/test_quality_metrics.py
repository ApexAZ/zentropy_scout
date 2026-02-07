"""Tests for quality metrics tracking.

REQ-010 §10.1: Generation Quality Tracking.

Five metrics with targets and alert thresholds for monitoring content
generation quality over time.
"""

import pytest

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


class TestQualityMetricDefinitionStructure:
    """Tests for QualityMetricDefinition frozen dataclass."""

    def test_definition_is_frozen(self) -> None:
        """QualityMetricDefinition should be immutable."""
        with pytest.raises(AttributeError):
            FIRST_DRAFT_APPROVAL_RATE.target = 0.99  # type: ignore[misc]

    def test_definition_has_all_fields(self) -> None:
        """QualityMetricDefinition should have all required fields."""
        assert hasattr(FIRST_DRAFT_APPROVAL_RATE, "name")
        assert hasattr(FIRST_DRAFT_APPROVAL_RATE, "target")
        assert hasattr(FIRST_DRAFT_APPROVAL_RATE, "alert_threshold")
        assert hasattr(FIRST_DRAFT_APPROVAL_RATE, "higher_is_better")


# =============================================================================
# MetricStatus Enum
# =============================================================================


class TestMetricStatusEnum:
    """Tests for MetricStatus enum values."""

    def test_has_on_target(self) -> None:
        """MetricStatus should have ON_TARGET value."""
        assert MetricStatus.ON_TARGET.value == "on_target"

    def test_has_below_target(self) -> None:
        """MetricStatus should have BELOW_TARGET value."""
        assert MetricStatus.BELOW_TARGET.value == "below_target"

    def test_has_alert(self) -> None:
        """MetricStatus should have ALERT value."""
        assert MetricStatus.ALERT.value == "alert"


# =============================================================================
# Metric Definitions — Values
# =============================================================================


class TestFirstDraftApprovalRate:
    """REQ-010 §10.1: First-draft approval rate > 60%, alert < 40%."""

    def test_name(self) -> None:
        """Should have the correct metric name."""
        assert FIRST_DRAFT_APPROVAL_RATE.name == "first_draft_approval_rate"

    def test_target(self) -> None:
        """Target should be 60%."""
        assert FIRST_DRAFT_APPROVAL_RATE.target == 0.60

    def test_alert_threshold(self) -> None:
        """Alert threshold should be 40%."""
        assert FIRST_DRAFT_APPROVAL_RATE.alert_threshold == 0.40

    def test_higher_is_better(self) -> None:
        """Higher approval rate is better."""
        assert FIRST_DRAFT_APPROVAL_RATE.higher_is_better is True


class TestValidationPassRate:
    """REQ-010 §10.1: Validation pass rate > 90%, alert < 80%."""

    def test_name(self) -> None:
        """Should have the correct metric name."""
        assert VALIDATION_PASS_RATE.name == "validation_pass_rate"

    def test_target(self) -> None:
        """Target should be 90%."""
        assert VALIDATION_PASS_RATE.target == 0.90

    def test_alert_threshold(self) -> None:
        """Alert threshold should be 80%."""
        assert VALIDATION_PASS_RATE.alert_threshold == 0.80

    def test_higher_is_better(self) -> None:
        """Higher pass rate is better."""
        assert VALIDATION_PASS_RATE.higher_is_better is True


class TestAvgRegenerationsPerLetter:
    """REQ-010 §10.1: Avg regenerations < 1.5, alert > 2.5."""

    def test_name(self) -> None:
        """Should have the correct metric name."""
        assert AVG_REGENERATIONS_PER_LETTER.name == "avg_regenerations_per_letter"

    def test_target(self) -> None:
        """Target should be 1.5."""
        assert AVG_REGENERATIONS_PER_LETTER.target == 1.5

    def test_alert_threshold(self) -> None:
        """Alert threshold should be 2.5."""
        assert AVG_REGENERATIONS_PER_LETTER.alert_threshold == 2.5

    def test_higher_is_better(self) -> None:
        """Lower regeneration count is better."""
        assert AVG_REGENERATIONS_PER_LETTER.higher_is_better is False


class TestVoiceAdherenceScore:
    """REQ-010 §10.1: Voice adherence > 4.0, alert < 3.0."""

    def test_name(self) -> None:
        """Should have the correct metric name."""
        assert VOICE_ADHERENCE_SCORE.name == "voice_adherence_score"

    def test_target(self) -> None:
        """Target should be 4.0."""
        assert VOICE_ADHERENCE_SCORE.target == 4.0

    def test_alert_threshold(self) -> None:
        """Alert threshold should be 3.0."""
        assert VOICE_ADHERENCE_SCORE.alert_threshold == 3.0

    def test_higher_is_better(self) -> None:
        """Higher voice adherence score is better."""
        assert VOICE_ADHERENCE_SCORE.higher_is_better is True


class TestStorySelectionSatisfaction:
    """REQ-010 §10.1: Story selection satisfaction > 70%, alert < 50%."""

    def test_name(self) -> None:
        """Should have the correct metric name."""
        assert STORY_SELECTION_SATISFACTION.name == "story_selection_satisfaction"

    def test_target(self) -> None:
        """Target should be 70%."""
        assert STORY_SELECTION_SATISFACTION.target == 0.70

    def test_alert_threshold(self) -> None:
        """Alert threshold should be 50%."""
        assert STORY_SELECTION_SATISFACTION.alert_threshold == 0.50

    def test_higher_is_better(self) -> None:
        """Higher satisfaction is better."""
        assert STORY_SELECTION_SATISFACTION.higher_is_better is True


# =============================================================================
# ALL_METRICS Collection
# =============================================================================


class TestAllMetrics:
    """Tests for the ALL_METRICS collection."""

    def test_contains_five_metrics(self) -> None:
        """Should contain exactly 5 metrics per REQ-010 §10.1."""
        assert len(ALL_METRICS) == 5

    def test_is_tuple(self) -> None:
        """ALL_METRICS should be a tuple for immutability."""
        assert isinstance(ALL_METRICS, tuple)

    def test_contains_all_metric_definitions(self) -> None:
        """Should contain all 5 defined metrics."""
        assert FIRST_DRAFT_APPROVAL_RATE in ALL_METRICS
        assert VALIDATION_PASS_RATE in ALL_METRICS
        assert AVG_REGENERATIONS_PER_LETTER in ALL_METRICS
        assert VOICE_ADHERENCE_SCORE in ALL_METRICS
        assert STORY_SELECTION_SATISFACTION in ALL_METRICS

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
