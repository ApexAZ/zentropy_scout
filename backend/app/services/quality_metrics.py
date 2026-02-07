"""Quality metrics tracking for content generation.

REQ-010 §10.1: Generation Quality Tracking.

Defines five quality metrics with targets and alert thresholds for
monitoring content generation performance. Each metric has a target
(desired performance) and an alert threshold (below which something
needs attention).

Metrics:
1. First-draft approval rate: approved without regeneration (> 60%)
2. Validation pass rate: pass automated checks (> 90%)
3. Avg regenerations per letter: regeneration request count (< 1.5)
4. Voice adherence score: manual review sample 1-5 (> 4.0)
5. Story selection satisfaction: user kept selected stories (> 70%)
"""

from dataclasses import dataclass
from enum import Enum

# =============================================================================
# Enums
# =============================================================================


class MetricStatus(Enum):
    """Evaluation result for a quality metric against its thresholds.

    Attributes:
        ON_TARGET: Value meets or exceeds the target.
        BELOW_TARGET: Value is worse than target but better than alert.
        ALERT: Value has crossed the alert threshold.
    """

    ON_TARGET = "on_target"
    BELOW_TARGET = "below_target"
    ALERT = "alert"


# =============================================================================
# Data Models
# =============================================================================


@dataclass(frozen=True)
class QualityMetricDefinition:
    """Definition of a quality metric with target and alert thresholds.

    REQ-010 §10.1: Each metric has a target (desired performance) and
    an alert threshold (below which something needs attention).

    Attributes:
        name: Machine-readable metric identifier.
        target: Target value for healthy performance.
        alert_threshold: Value at which an alert should be raised.
        higher_is_better: True if higher values are better (rates, scores).
            False if lower values are better (counts like regenerations).
    """

    name: str
    target: float
    alert_threshold: float
    higher_is_better: bool


# =============================================================================
# Metric Definitions (REQ-010 §10.1)
# =============================================================================

FIRST_DRAFT_APPROVAL_RATE = QualityMetricDefinition(
    name="first_draft_approval_rate",
    target=0.60,
    alert_threshold=0.40,
    higher_is_better=True,
)
"""Approved without regeneration: target > 60%, alert < 40%."""

VALIDATION_PASS_RATE = QualityMetricDefinition(
    name="validation_pass_rate",
    target=0.90,
    alert_threshold=0.80,
    higher_is_better=True,
)
"""Pass automated checks: target > 90%, alert < 80%."""

AVG_REGENERATIONS_PER_LETTER = QualityMetricDefinition(
    name="avg_regenerations_per_letter",
    target=1.5,
    alert_threshold=2.5,
    higher_is_better=False,
)
"""Regeneration request count: target < 1.5, alert > 2.5."""

VOICE_ADHERENCE_SCORE = QualityMetricDefinition(
    name="voice_adherence_score",
    target=4.0,
    alert_threshold=3.0,
    higher_is_better=True,
)
"""Manual review sample (1-5): target > 4.0, alert < 3.0."""

STORY_SELECTION_SATISFACTION = QualityMetricDefinition(
    name="story_selection_satisfaction",
    target=0.70,
    alert_threshold=0.50,
    higher_is_better=True,
)
"""User kept selected stories: target > 70%, alert < 50%."""

ALL_METRICS: tuple[QualityMetricDefinition, ...] = (
    FIRST_DRAFT_APPROVAL_RATE,
    VALIDATION_PASS_RATE,
    AVG_REGENERATIONS_PER_LETTER,
    VOICE_ADHERENCE_SCORE,
    STORY_SELECTION_SATISFACTION,
)
"""All defined quality metrics (REQ-010 §10.1)."""


# =============================================================================
# Evaluation
# =============================================================================


def evaluate_metric(
    value: float,
    metric: QualityMetricDefinition,
) -> MetricStatus:
    """Evaluate a metric value against its target and alert thresholds.

    REQ-010 §10.1: Compares a measured value to the metric's target and
    alert threshold, returning the appropriate status.

    For higher-is-better metrics (rates, scores):
        - value >= target → ON_TARGET
        - alert_threshold < value < target → BELOW_TARGET
        - value <= alert_threshold → ALERT

    For lower-is-better metrics (counts):
        - value <= target → ON_TARGET
        - target < value < alert_threshold → BELOW_TARGET
        - value >= alert_threshold → ALERT

    Args:
        value: The measured metric value.
        metric: The metric definition with target and alert threshold.

    Returns:
        MetricStatus indicating whether the value is on target,
        below target, or at alert level.
    """
    if metric.higher_is_better:
        if value >= metric.target:
            return MetricStatus.ON_TARGET
        if value <= metric.alert_threshold:
            return MetricStatus.ALERT
        return MetricStatus.BELOW_TARGET

    # Lower is better (e.g., avg regenerations)
    if value <= metric.target:
        return MetricStatus.ON_TARGET
    if value >= metric.alert_threshold:
        return MetricStatus.ALERT
    return MetricStatus.BELOW_TARGET
