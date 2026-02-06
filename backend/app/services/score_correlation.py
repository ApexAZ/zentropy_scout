"""Score correlation utilities for validation.

REQ-008 §11.2: Validation Approach — Correlation Check.

Computes Pearson correlation between algorithm scores and human-labeled
scores from the golden set to validate scoring accuracy.

Target: r > 0.8 for both Fit and Stretch scores.

Usage:
    from app.services.score_correlation import validate_scores_against_golden_set
    from app.services.golden_set import load_golden_set

    golden_set = load_golden_set(Path("tests/fixtures/golden_set.json"))
    algorithm_scores = {
        "gs-001": {"fit": 85, "stretch": 42},
        "gs-002": {"fit": 60, "stretch": 68},
        # ... more entries
    }
    result = validate_scores_against_golden_set(golden_set, algorithm_scores)
    print(f"Passed: {result.passed}, Fit r={result.correlation.fit_correlation:.3f}")
"""

import math
from dataclasses import dataclass, field

from app.services.golden_set import GoldenSet

# =============================================================================
# Pearson Correlation Calculation
# =============================================================================


def compute_pearson_correlation(actual: list[float], predicted: list[float]) -> float:
    """Compute Pearson correlation coefficient between two lists.

    REQ-008 §11.2: Verify algorithm scores correlate with human labels.

    The Pearson correlation coefficient measures linear correlation between
    two variables, ranging from -1 (perfect negative) to +1 (perfect positive).

    Args:
        actual: List of actual/human-labeled values.
        predicted: List of predicted/algorithm values.

    Returns:
        Pearson correlation coefficient (-1.0 to 1.0).

    Raises:
        ValueError: If lists have fewer than 2 elements, different lengths,
            or zero variance.

    Note:
        Implementation uses the standard formula:
        r = Σ[(xi - x̄)(yi - ȳ)] / √[Σ(xi - x̄)² × Σ(yi - ȳ)²]
    """
    n = len(actual)

    if n < 2:
        raise ValueError("Correlation requires at least 2 data points")

    if len(predicted) != n:
        raise ValueError(
            f"Arrays must have same length: actual={n}, predicted={len(predicted)}"
        )

    # Calculate means
    mean_actual = sum(actual) / n
    mean_predicted = sum(predicted) / n

    # Calculate sums for correlation formula
    sum_xy = 0.0  # Sum of (xi - x̄)(yi - ȳ)
    sum_x2 = 0.0  # Sum of (xi - x̄)²
    sum_y2 = 0.0  # Sum of (yi - ȳ)²

    for i in range(n):
        dx = actual[i] - mean_actual
        dy = predicted[i] - mean_predicted
        sum_xy += dx * dy
        sum_x2 += dx * dx
        sum_y2 += dy * dy

    # Check for zero variance (epsilon comparison to avoid float equality)
    _ZERO_VARIANCE_EPSILON = 1e-12
    if sum_x2 < _ZERO_VARIANCE_EPSILON or sum_y2 < _ZERO_VARIANCE_EPSILON:
        raise ValueError(
            "Cannot compute correlation: one or both arrays have zero variance"
        )

    # Compute correlation
    denominator = math.sqrt(sum_x2 * sum_y2)
    return sum_xy / denominator


# =============================================================================
# Result Data Classes
# =============================================================================


@dataclass
class CorrelationResult:
    """Result of correlation calculation.

    Attributes:
        fit_correlation: Pearson r for Fit Score (algorithm vs human).
        stretch_correlation: Pearson r for Stretch Score (algorithm vs human).
        sample_size: Number of entries used in calculation.
    """

    fit_correlation: float
    stretch_correlation: float
    sample_size: int

    def passes_threshold(self, threshold: float) -> bool:
        """Check if both correlations meet or exceed the threshold.

        REQ-008 §11.2: Target correlation is r > 0.8.

        Args:
            threshold: Minimum acceptable correlation (typically 0.8).

        Returns:
            True if both fit and stretch correlations >= threshold.
        """
        return (
            self.fit_correlation >= threshold and self.stretch_correlation >= threshold
        )


@dataclass
class ValidationResult:
    """Complete validation result with per-entry details.

    Attributes:
        correlation: Overall correlation results.
        target_threshold: The threshold used for pass/fail determination.
        passed: Whether validation passed (both correlations >= threshold).
        entry_results: Per-entry score differences for debugging.
    """

    correlation: CorrelationResult
    target_threshold: float
    passed: bool
    entry_results: list[dict] = field(default_factory=list)


# =============================================================================
# Validation Function
# =============================================================================


def validate_scores_against_golden_set(
    golden_set: GoldenSet,
    algorithm_scores: dict[str, dict[str, int | float]],
) -> ValidationResult:
    """Validate algorithm scores against human-labeled golden set.

    REQ-008 §11.2: Correlation check for validation approach.

    Computes Pearson correlation between algorithm-generated scores and
    human-labeled scores from the golden set. Both Fit and Stretch scores
    must correlate above the target threshold (default 0.8) to pass.

    Args:
        golden_set: The golden set with human-labeled scores.
        algorithm_scores: Dict mapping entry ID to {"fit": score, "stretch": score}.

    Returns:
        ValidationResult with correlations, threshold, pass/fail, and entry details.

    Raises:
        ValueError: If algorithm_scores is missing entries from the golden set.

    Example:
        >>> result = validate_scores_against_golden_set(golden_set, scores)
        >>> if result.passed:
        ...     print(f"Validation passed! r={result.correlation.fit_correlation:.3f}")
        >>> else:
        ...     print(f"Validation failed. Review entry_results for details.")
    """
    # Collect scores for correlation calculation
    human_fit_scores: list[float] = []
    human_stretch_scores: list[float] = []
    algorithm_fit_scores: list[float] = []
    algorithm_stretch_scores: list[float] = []
    entry_results: list[dict] = []

    # Check for missing entries and collect scores
    missing_entries = []
    for entry in golden_set.entries:
        if entry.id not in algorithm_scores:
            missing_entries.append(entry.id)
            continue

        algo_scores = algorithm_scores[entry.id]

        # Collect for correlation
        human_fit_scores.append(float(entry.human_fit_score))
        human_stretch_scores.append(float(entry.human_stretch_score))
        algorithm_fit_scores.append(float(algo_scores["fit"]))
        algorithm_stretch_scores.append(float(algo_scores["stretch"]))

        # Calculate per-entry errors
        fit_error = algo_scores["fit"] - entry.human_fit_score
        stretch_error = algo_scores["stretch"] - entry.human_stretch_score
        entry_results.append(
            {
                "id": entry.id,
                "fit_error": fit_error,
                "stretch_error": stretch_error,
                "human_fit": entry.human_fit_score,
                "human_stretch": entry.human_stretch_score,
                "algo_fit": algo_scores["fit"],
                "algo_stretch": algo_scores["stretch"],
            }
        )

    if missing_entries:
        raise ValueError(f"Missing algorithm scores for entries: {missing_entries}")

    # Compute correlations
    fit_correlation = compute_pearson_correlation(
        human_fit_scores, algorithm_fit_scores
    )
    stretch_correlation = compute_pearson_correlation(
        human_stretch_scores, algorithm_stretch_scores
    )

    correlation = CorrelationResult(
        fit_correlation=fit_correlation,
        stretch_correlation=stretch_correlation,
        sample_size=len(golden_set.entries),
    )

    # Determine pass/fail using threshold from golden set metadata
    target_threshold = golden_set.metadata.target_correlation
    passed = correlation.passes_threshold(target_threshold)

    return ValidationResult(
        correlation=correlation,
        target_threshold=target_threshold,
        passed=passed,
        entry_results=entry_results,
    )
