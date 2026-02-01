"""Unit tests for location/logistics match calculation.

REQ-008 §4.6: Location/Logistics component (10% of Fit Score).

Tests cover:
- Work model preference matrix (Remote Only, Hybrid OK, Onsite OK)
- Location proximity modifier for non-remote jobs
- Edge cases (missing data, empty commutable cities)
- Input validation (invalid values, oversized lists)
"""

import pytest

from app.services.location_logistics import calculate_logistics_score

# =============================================================================
# Work Model Preference Tests — Remote Only
# =============================================================================


class TestRemoteOnlyPreference:
    """Tests for users with 'Remote Only' preference."""

    def test_remote_only_with_remote_job_returns_100(self) -> None:
        """Remote Only user + Remote job = perfect match."""
        score = calculate_logistics_score(
            remote_preference="Remote Only",
            commutable_cities=None,
            job_work_model="Remote",
            job_location=None,
        )
        assert score == 100.0

    def test_remote_only_with_hybrid_job_returns_50(self) -> None:
        """Remote Only user + Hybrid job = partial match."""
        score = calculate_logistics_score(
            remote_preference="Remote Only",
            commutable_cities=None,
            job_work_model="Hybrid",
            job_location="Seattle",
        )
        assert score == 50.0

    def test_remote_only_with_onsite_job_returns_0(self) -> None:
        """Remote Only user + Onsite job = no match."""
        score = calculate_logistics_score(
            remote_preference="Remote Only",
            commutable_cities=None,
            job_work_model="Onsite",
            job_location="San Francisco",
        )
        assert score == 0.0


# =============================================================================
# Work Model Preference Tests — Hybrid OK
# =============================================================================


class TestHybridOkPreference:
    """Tests for users with 'Hybrid OK' preference."""

    def test_hybrid_ok_with_remote_job_returns_100(self) -> None:
        """Hybrid OK user + Remote job = full match."""
        score = calculate_logistics_score(
            remote_preference="Hybrid OK",
            commutable_cities=None,
            job_work_model="Remote",
            job_location=None,
        )
        assert score == 100.0

    def test_hybrid_ok_with_hybrid_job_returns_100(self) -> None:
        """Hybrid OK user + Hybrid job = full match."""
        score = calculate_logistics_score(
            remote_preference="Hybrid OK",
            commutable_cities=None,
            job_work_model="Hybrid",
            job_location="Seattle",
        )
        assert score == 100.0

    def test_hybrid_ok_with_onsite_job_returns_60(self) -> None:
        """Hybrid OK user + Onsite job = acceptable but not ideal."""
        score = calculate_logistics_score(
            remote_preference="Hybrid OK",
            commutable_cities=None,
            job_work_model="Onsite",
            job_location="Austin",
        )
        assert score == 60.0


# =============================================================================
# Work Model Preference Tests — Onsite OK
# =============================================================================


class TestOnsiteOkPreference:
    """Tests for users with 'Onsite OK' preference (most flexible)."""

    def test_onsite_ok_with_remote_job_returns_100(self) -> None:
        """Onsite OK user + Remote job = full match."""
        score = calculate_logistics_score(
            remote_preference="Onsite OK",
            commutable_cities=None,
            job_work_model="Remote",
            job_location=None,
        )
        assert score == 100.0

    def test_onsite_ok_with_hybrid_job_returns_100(self) -> None:
        """Onsite OK user + Hybrid job = full match."""
        score = calculate_logistics_score(
            remote_preference="Onsite OK",
            commutable_cities=None,
            job_work_model="Hybrid",
            job_location="Denver",
        )
        assert score == 100.0

    def test_onsite_ok_with_onsite_job_returns_100(self) -> None:
        """Onsite OK user + Onsite job = full match."""
        score = calculate_logistics_score(
            remote_preference="Onsite OK",
            commutable_cities=None,
            job_work_model="Onsite",
            job_location="Chicago",
        )
        assert score == 100.0


# =============================================================================
# Location Proximity Modifier Tests
# =============================================================================


class TestLocationProximity:
    """Tests for location proximity modifier (non-remote jobs)."""

    def test_commutable_city_no_penalty(self) -> None:
        """Job in commutable city keeps full score."""
        score = calculate_logistics_score(
            remote_preference="Hybrid OK",
            commutable_cities=["Seattle", "Bellevue", "Redmond"],
            job_work_model="Onsite",
            job_location="Seattle",
        )
        # Base score 60 for Hybrid OK + Onsite, no penalty for commutable
        assert score == 60.0

    def test_non_commutable_city_applies_penalty(self) -> None:
        """Job NOT in commutable city applies 30% penalty."""
        score = calculate_logistics_score(
            remote_preference="Hybrid OK",
            commutable_cities=["Seattle", "Bellevue"],
            job_work_model="Onsite",
            job_location="San Francisco",
        )
        # Base score 60 * 0.7 = 42.0
        assert score == pytest.approx(42.0, abs=0.01)

    def test_hybrid_job_with_non_commutable_applies_penalty(self) -> None:
        """Hybrid job in non-commutable city also gets penalty."""
        score = calculate_logistics_score(
            remote_preference="Hybrid OK",
            commutable_cities=["Seattle"],
            job_work_model="Hybrid",
            job_location="New York",
        )
        # Base score 100 * 0.7 = 70.0
        assert score == pytest.approx(70.0, abs=0.01)

    def test_remote_job_skips_location_check(self) -> None:
        """Remote jobs skip location proximity check entirely."""
        score = calculate_logistics_score(
            remote_preference="Hybrid OK",
            commutable_cities=["Seattle"],
            job_work_model="Remote",
            job_location="Anywhere",  # Doesn't matter for remote
        )
        # Full score, no penalty applied
        assert score == 100.0

    def test_empty_commutable_cities_skips_location_check(self) -> None:
        """Empty commutable cities list skips location check."""
        score = calculate_logistics_score(
            remote_preference="Hybrid OK",
            commutable_cities=[],
            job_work_model="Onsite",
            job_location="San Francisco",
        )
        # Base score 60, no penalty because commutable cities not defined
        assert score == 60.0

    def test_none_commutable_cities_skips_location_check(self) -> None:
        """None commutable cities skips location check."""
        score = calculate_logistics_score(
            remote_preference="Hybrid OK",
            commutable_cities=None,
            job_work_model="Onsite",
            job_location="San Francisco",
        )
        # Base score 60, no penalty
        assert score == 60.0

    def test_case_insensitive_city_matching(self) -> None:
        """City matching should be case-insensitive."""
        score = calculate_logistics_score(
            remote_preference="Onsite OK",
            commutable_cities=["seattle", "bellevue"],
            job_work_model="Onsite",
            job_location="Seattle",
        )
        # Should match despite case difference
        assert score == 100.0

    def test_city_with_extra_whitespace_still_matches(self) -> None:
        """City matching should normalize whitespace."""
        score = calculate_logistics_score(
            remote_preference="Onsite OK",
            commutable_cities=["Seattle"],
            job_work_model="Onsite",
            job_location="  Seattle  ",
        )
        assert score == 100.0


# =============================================================================
# Missing Data / Edge Cases
# =============================================================================


class TestMissingData:
    """Tests for missing or neutral data scenarios."""

    def test_missing_remote_preference_returns_neutral(self) -> None:
        """No user preference returns neutral score (70)."""
        score = calculate_logistics_score(
            remote_preference=None,
            commutable_cities=None,
            job_work_model="Remote",
            job_location=None,
        )
        assert score == 70.0

    def test_missing_job_work_model_returns_neutral(self) -> None:
        """No job work model returns neutral score (70)."""
        score = calculate_logistics_score(
            remote_preference="Remote Only",
            commutable_cities=None,
            job_work_model=None,
            job_location=None,
        )
        assert score == 70.0

    def test_both_missing_returns_neutral(self) -> None:
        """Both preference and work model missing returns neutral."""
        score = calculate_logistics_score(
            remote_preference=None,
            commutable_cities=None,
            job_work_model=None,
            job_location=None,
        )
        assert score == 70.0

    def test_empty_string_preference_returns_neutral(self) -> None:
        """Empty string preference treated as missing."""
        score = calculate_logistics_score(
            remote_preference="",
            commutable_cities=None,
            job_work_model="Remote",
            job_location=None,
        )
        assert score == 70.0

    def test_whitespace_preference_returns_neutral(self) -> None:
        """Whitespace-only preference treated as missing."""
        score = calculate_logistics_score(
            remote_preference="   ",
            commutable_cities=None,
            job_work_model="Remote",
            job_location=None,
        )
        assert score == 70.0

    def test_empty_string_work_model_returns_neutral(self) -> None:
        """Empty string work model treated as missing."""
        score = calculate_logistics_score(
            remote_preference="Remote Only",
            commutable_cities=None,
            job_work_model="",
            job_location=None,
        )
        assert score == 70.0


# =============================================================================
# Input Validation / Invalid Values
# =============================================================================


class TestInputValidation:
    """Tests for invalid input handling."""

    def test_invalid_preference_raises_error(self) -> None:
        """Invalid remote preference raises ValueError."""
        with pytest.raises(ValueError, match="Invalid remote_preference"):
            calculate_logistics_score(
                remote_preference="Work From Home",  # Not a valid option
                commutable_cities=None,
                job_work_model="Remote",
                job_location=None,
            )

    def test_invalid_work_model_raises_error(self) -> None:
        """Invalid job work model raises ValueError."""
        with pytest.raises(ValueError, match="Invalid job_work_model"):
            calculate_logistics_score(
                remote_preference="Remote Only",
                commutable_cities=None,
                job_work_model="Flexible",  # Not a valid option
                job_location=None,
            )

    def test_oversized_commutable_cities_raises_error(self) -> None:
        """Too many commutable cities raises ValueError (DoS protection)."""
        cities = [f"City{i}" for i in range(1001)]  # Over 1000 limit
        with pytest.raises(ValueError, match="exceeds maximum"):
            calculate_logistics_score(
                remote_preference="Onsite OK",
                commutable_cities=cities,
                job_work_model="Onsite",
                job_location="City1",
            )


# =============================================================================
# Worked Examples from REQ-008 §4.6
# =============================================================================


class TestWorkedExamples:
    """Tests matching worked examples from REQ-008 §4.6."""

    def test_example1_perfect_remote_match(self) -> None:
        """Example 1: Remote Only user + Remote job = 100."""
        score = calculate_logistics_score(
            remote_preference="Remote Only",
            commutable_cities=None,
            job_work_model="Remote",
            job_location=None,
        )
        assert score == 100.0

    def test_example2_remote_only_hybrid(self) -> None:
        """Example 2: Remote Only user + Hybrid job = 50."""
        score = calculate_logistics_score(
            remote_preference="Remote Only",
            commutable_cities=None,
            job_work_model="Hybrid",
            job_location="Seattle",
        )
        assert score == 50.0

    def test_example3_hybrid_ok_onsite_commutable(self) -> None:
        """Example 3: Hybrid OK + Onsite in commutable city = 60."""
        score = calculate_logistics_score(
            remote_preference="Hybrid OK",
            commutable_cities=["Seattle", "Bellevue"],
            job_work_model="Onsite",
            job_location="Seattle",
        )
        assert score == 60.0

    def test_example4_hybrid_ok_onsite_non_commutable(self) -> None:
        """Example 4: Hybrid OK + Onsite NOT in commutable = 42."""
        score = calculate_logistics_score(
            remote_preference="Hybrid OK",
            commutable_cities=["Seattle", "Bellevue"],
            job_work_model="Onsite",
            job_location="San Francisco",
        )
        assert score == pytest.approx(42.0, abs=0.01)

    def test_example5_onsite_ok_no_cities(self) -> None:
        """Example 5: Onsite OK + no commutable cities = 100."""
        score = calculate_logistics_score(
            remote_preference="Onsite OK",
            commutable_cities=None,
            job_work_model="Onsite",
            job_location="Austin",
        )
        assert score == 100.0


# =============================================================================
# Score Bounds Tests
# =============================================================================


class TestScoreBounds:
    """Tests that scores are always within valid range."""

    def test_score_never_exceeds_100(self) -> None:
        """Score should never exceed 100."""
        score = calculate_logistics_score(
            remote_preference="Onsite OK",
            commutable_cities=["Seattle"],
            job_work_model="Remote",
            job_location=None,
        )
        assert score <= 100.0

    def test_score_never_below_0(self) -> None:
        """Score should never go below 0."""
        score = calculate_logistics_score(
            remote_preference="Remote Only",
            commutable_cities=["Seattle"],
            job_work_model="Onsite",
            job_location="San Francisco",
        )
        # Remote Only + Onsite = 0, then penalty would make it negative
        # but we clamp to 0
        assert score >= 0.0

    def test_zero_score_not_penalized_further(self) -> None:
        """Score of 0 from work model mismatch should stay 0 with penalty."""
        score = calculate_logistics_score(
            remote_preference="Remote Only",
            commutable_cities=["Seattle"],
            job_work_model="Onsite",
            job_location="San Francisco",
        )
        # Base 0, penalty would make 0 * 0.7 = 0 anyway
        assert score == 0.0
