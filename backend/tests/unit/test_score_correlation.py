"""Tests for score correlation utilities.

REQ-008 §11.2: Validation Approach — Correlation Check.

Verify algorithm scores correlate with human labels (r > 0.8).
"""

import pytest

from app.services.golden_set import GoldenSet, GoldenSetEntry, GoldenSetMetadata
from app.services.score_correlation import (
    CorrelationResult,
    ValidationResult,
    compute_pearson_correlation,
    validate_scores_against_golden_set,
)

# =============================================================================
# compute_pearson_correlation Tests
# =============================================================================


class TestComputePearsonCorrelation:
    """Tests for Pearson correlation coefficient calculation."""

    def test_correlation_returns_one_when_perfect_positive(self) -> None:
        """Perfect positive correlation should return 1.0."""
        actual = [10, 20, 30, 40, 50]
        predicted = [10, 20, 30, 40, 50]

        result = compute_pearson_correlation(actual, predicted)

        assert result == pytest.approx(1.0, abs=0.001)

    def test_correlation_returns_negative_one_when_perfect_negative(self) -> None:
        """Perfect negative correlation should return -1.0."""
        actual = [10, 20, 30, 40, 50]
        predicted = [50, 40, 30, 20, 10]

        result = compute_pearson_correlation(actual, predicted)

        assert result == pytest.approx(-1.0, abs=0.001)

    def test_correlation_returns_moderate_value_when_weakly_correlated(self) -> None:
        """Weak correlation should return moderate value."""
        actual = [1, 2, 3, 4, 5]
        predicted = [3, 1, 4, 2, 5]  # Partially correlated

        result = compute_pearson_correlation(actual, predicted)

        # With partially correlated data, result should be moderate
        # This specific data produces r=0.5 (weak positive)
        assert 0.3 < result < 0.7

    def test_correlation_returns_high_value_when_strongly_correlated(self) -> None:
        """Strong positive correlation should return value near 1.0."""
        actual = [10, 20, 30, 40, 50]
        predicted = [12, 22, 28, 42, 48]  # Close but not perfect

        result = compute_pearson_correlation(actual, predicted)

        assert result > 0.95

    def test_correlation_is_scale_invariant(self) -> None:
        """Correlation should be scale-invariant."""
        actual = [10, 20, 30, 40, 50]
        predicted = [100, 200, 300, 400, 500]  # Same pattern, 10x scale

        result = compute_pearson_correlation(actual, predicted)

        assert result == pytest.approx(1.0, abs=0.001)

    def test_correlation_raises_error_when_fewer_than_two_points(self) -> None:
        """Should raise error with fewer than 2 data points."""
        with pytest.raises(ValueError, match="at least 2"):
            compute_pearson_correlation([1], [1])

    def test_correlation_raises_error_when_lengths_differ(self) -> None:
        """Should raise error when arrays have different lengths."""
        with pytest.raises(ValueError, match="same length"):
            compute_pearson_correlation([1, 2, 3], [1, 2])

    def test_correlation_raises_error_when_variance_is_zero(self) -> None:
        """Should raise error when values have zero variance."""
        with pytest.raises(ValueError, match="zero variance"):
            compute_pearson_correlation([50, 50, 50], [1, 2, 3])


# =============================================================================
# CorrelationResult Tests
# =============================================================================


class TestCorrelationResult:
    """Tests for CorrelationResult data class."""

    def test_result_stores_correlations_when_initialized(self) -> None:
        """Result should store fit and stretch correlations."""
        result = CorrelationResult(
            fit_correlation=0.85,
            stretch_correlation=0.78,
            sample_size=50,
        )

        assert result.fit_correlation == 0.85
        assert result.stretch_correlation == 0.78
        assert result.sample_size == 50

    def test_result_passes_threshold_when_both_high(self) -> None:
        """Result should pass when both correlations exceed threshold."""
        result = CorrelationResult(
            fit_correlation=0.85,
            stretch_correlation=0.82,
            sample_size=50,
        )

        assert result.passes_threshold(0.8) is True

    def test_result_fails_threshold_when_fit_low(self) -> None:
        """Result should fail when fit correlation is below threshold."""
        result = CorrelationResult(
            fit_correlation=0.75,
            stretch_correlation=0.85,
            sample_size=50,
        )

        assert result.passes_threshold(0.8) is False

    def test_result_fails_threshold_when_stretch_low(self) -> None:
        """Result should fail when stretch correlation is below threshold."""
        result = CorrelationResult(
            fit_correlation=0.85,
            stretch_correlation=0.75,
            sample_size=50,
        )

        assert result.passes_threshold(0.8) is False


# =============================================================================
# ValidationResult Tests
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult data class."""

    def test_validation_result_stores_fields_when_initialized(self) -> None:
        """Validation result should store all fields."""
        correlation = CorrelationResult(
            fit_correlation=0.85,
            stretch_correlation=0.82,
            sample_size=50,
        )
        result = ValidationResult(
            correlation=correlation,
            target_threshold=0.8,
            passed=True,
            entry_results=[
                {"id": "gs-001", "fit_error": 5, "stretch_error": 3},
            ],
        )

        assert result.correlation.fit_correlation == 0.85
        assert result.target_threshold == 0.8
        assert result.passed is True
        assert len(result.entry_results) == 1


# =============================================================================
# validate_scores_against_golden_set Tests
# =============================================================================


class TestValidateScoresAgainstGoldenSet:
    """Tests for validating algorithm scores against golden set."""

    @staticmethod
    def _create_golden_set(entries: list[dict]) -> GoldenSet:
        """Helper to create a golden set from entry dicts."""
        gs_entries = [
            GoldenSetEntry(
                id=e["id"],
                persona_summary=e.get("persona_summary", "Test persona"),
                job_summary=e.get("job_summary", "Test job"),
                human_fit_score=e["human_fit_score"],
                human_stretch_score=e["human_stretch_score"],
            )
            for e in entries
        ]
        metadata = GoldenSetMetadata(version="1.0.0", created_date="2026-02-04")
        return GoldenSet(metadata=metadata, entries=gs_entries)

    def test_validation_passes_when_scores_match_closely(self) -> None:
        """Validation should pass when algorithm matches human scores closely."""
        golden_set = self._create_golden_set(
            [
                {"id": "gs-001", "human_fit_score": 80, "human_stretch_score": 40},
                {"id": "gs-002", "human_fit_score": 60, "human_stretch_score": 70},
                {"id": "gs-003", "human_fit_score": 90, "human_stretch_score": 30},
                {"id": "gs-004", "human_fit_score": 50, "human_stretch_score": 80},
                {"id": "gs-005", "human_fit_score": 70, "human_stretch_score": 50},
            ]
        )

        # Algorithm scores that match human scores closely
        algorithm_scores = {
            "gs-001": {"fit": 82, "stretch": 38},
            "gs-002": {"fit": 58, "stretch": 72},
            "gs-003": {"fit": 91, "stretch": 28},
            "gs-004": {"fit": 52, "stretch": 78},
            "gs-005": {"fit": 68, "stretch": 52},
        }

        result = validate_scores_against_golden_set(golden_set, algorithm_scores)

        assert result.passed is True
        assert result.correlation.fit_correlation > 0.9
        assert result.correlation.stretch_correlation > 0.9

    def test_validation_fails_when_scores_are_inverted(self) -> None:
        """Validation should fail when algorithm diverges from human scores."""
        golden_set = self._create_golden_set(
            [
                {"id": "gs-001", "human_fit_score": 80, "human_stretch_score": 40},
                {"id": "gs-002", "human_fit_score": 60, "human_stretch_score": 70},
                {"id": "gs-003", "human_fit_score": 90, "human_stretch_score": 30},
                {"id": "gs-004", "human_fit_score": 50, "human_stretch_score": 80},
                {"id": "gs-005", "human_fit_score": 70, "human_stretch_score": 50},
            ]
        )

        # Algorithm scores that are inverted from human scores
        algorithm_scores = {
            "gs-001": {"fit": 20, "stretch": 60},  # Inverted
            "gs-002": {"fit": 40, "stretch": 30},  # Inverted
            "gs-003": {"fit": 10, "stretch": 70},  # Inverted
            "gs-004": {"fit": 50, "stretch": 20},  # Inverted
            "gs-005": {"fit": 30, "stretch": 50},  # Inverted
        }

        result = validate_scores_against_golden_set(golden_set, algorithm_scores)

        assert result.passed is False
        # Inverted scores should produce negative correlation
        assert result.correlation.fit_correlation < 0

    def test_validation_uses_metadata_threshold(self) -> None:
        """Validation should use target threshold from golden set metadata."""
        entries = [
            GoldenSetEntry(
                id=f"gs-{i:03d}",
                persona_summary=f"Persona {i}",
                job_summary=f"Job {i}",
                human_fit_score=50 + i * 10,
                human_stretch_score=50 + i * 5,
            )
            for i in range(5)
        ]
        metadata = GoldenSetMetadata(
            version="1.0.0",
            created_date="2026-02-04",
            target_correlation=0.9,  # Higher threshold
        )
        golden_set = GoldenSet(metadata=metadata, entries=entries)

        # Scores that correlate at ~0.85 (above 0.8 but below 0.9)
        algorithm_scores = {
            f"gs-{i:03d}": {"fit": 48 + i * 10, "stretch": 52 + i * 5} for i in range(5)
        }

        result = validate_scores_against_golden_set(golden_set, algorithm_scores)

        # Should use 0.9 threshold from metadata, not default 0.8
        assert result.target_threshold == 0.9

    def test_validation_reports_per_entry_errors(self) -> None:
        """Validation should report per-entry score differences."""
        golden_set = self._create_golden_set(
            [
                {"id": "gs-001", "human_fit_score": 80, "human_stretch_score": 40},
                {"id": "gs-002", "human_fit_score": 60, "human_stretch_score": 70},
            ]
        )

        algorithm_scores = {
            "gs-001": {"fit": 85, "stretch": 35},  # +5, -5
            "gs-002": {"fit": 55, "stretch": 75},  # -5, +5
        }

        result = validate_scores_against_golden_set(golden_set, algorithm_scores)

        assert len(result.entry_results) == 2
        entry_1 = next(e for e in result.entry_results if e["id"] == "gs-001")
        assert entry_1["fit_error"] == 5
        assert entry_1["stretch_error"] == -5

    def test_validation_raises_error_when_entry_missing(self) -> None:
        """Should raise error when algorithm scores are missing for an entry."""
        golden_set = self._create_golden_set(
            [
                {"id": "gs-001", "human_fit_score": 80, "human_stretch_score": 40},
                {"id": "gs-002", "human_fit_score": 60, "human_stretch_score": 70},
            ]
        )

        # Missing gs-002
        algorithm_scores = {
            "gs-001": {"fit": 85, "stretch": 35},
        }

        with pytest.raises(ValueError, match="Missing.*gs-002"):
            validate_scores_against_golden_set(golden_set, algorithm_scores)
