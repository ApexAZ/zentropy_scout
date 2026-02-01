"""Unit tests for experience level match calculation.

REQ-008 §4.4: Experience Level Match component (25% of Fit Score).

Tests cover:
- Experience range matching (within, under, over)
- Penalty calculations for under/over-qualified
- Edge cases (no requirements, None experience, max-only)
"""

import pytest

from app.services.experience_level import calculate_experience_score

# =============================================================================
# No Requirements Specified Tests
# =============================================================================


class TestNoRequirementsSpecified:
    """Tests for when job has no experience requirements."""

    def test_no_min_no_max_returns_neutral(self) -> None:
        """Job with no experience requirements returns neutral score (70)."""
        score = calculate_experience_score(
            user_years=5,
            job_min_years=None,
            job_max_years=None,
        )
        assert score == 70.0

    def test_zero_experience_no_requirements_returns_neutral(self) -> None:
        """User with 0 years and no requirements returns neutral score."""
        score = calculate_experience_score(
            user_years=0,
            job_min_years=None,
            job_max_years=None,
        )
        assert score == 70.0

    def test_none_experience_no_requirements_returns_neutral(self) -> None:
        """User with None experience and no requirements returns neutral."""
        score = calculate_experience_score(
            user_years=None,
            job_min_years=None,
            job_max_years=None,
        )
        assert score == 70.0


# =============================================================================
# Within Range Tests (Perfect Match)
# =============================================================================


class TestWithinRange:
    """Tests for when user experience falls within job requirements."""

    def test_exact_minimum_returns_100(self) -> None:
        """User at exact minimum of range returns 100."""
        score = calculate_experience_score(
            user_years=5,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == 100.0

    def test_exact_maximum_returns_100(self) -> None:
        """User at exact maximum of range returns 100."""
        score = calculate_experience_score(
            user_years=8,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == 100.0

    def test_mid_range_returns_100(self) -> None:
        """User in middle of range returns 100."""
        score = calculate_experience_score(
            user_years=6,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == 100.0


# =============================================================================
# Minimum Only Tests
# =============================================================================


class TestMinimumOnly:
    """Tests for when job specifies only minimum experience."""

    def test_meets_minimum_returns_100(self) -> None:
        """User meeting minimum (no max) returns 100."""
        score = calculate_experience_score(
            user_years=5,
            job_min_years=3,
            job_max_years=None,
        )
        assert score == 100.0

    def test_exact_minimum_returns_100(self) -> None:
        """User at exact minimum (no max) returns 100."""
        score = calculate_experience_score(
            user_years=3,
            job_min_years=3,
            job_max_years=None,
        )
        assert score == 100.0

    def test_exceeds_minimum_significantly_returns_100(self) -> None:
        """User far exceeding minimum (no max) returns 100.

        When only minimum is specified, there's no overqualification penalty.
        """
        score = calculate_experience_score(
            user_years=15,
            job_min_years=3,
            job_max_years=None,
        )
        assert score == 100.0


# =============================================================================
# Maximum Only Tests (Unusual)
# =============================================================================


class TestMaximumOnly:
    """Tests for when job specifies only maximum experience (unusual)."""

    def test_under_maximum_returns_100(self) -> None:
        """User under maximum (no min) returns 100."""
        score = calculate_experience_score(
            user_years=3,
            job_min_years=None,
            job_max_years=5,
        )
        assert score == 100.0

    def test_at_maximum_returns_100(self) -> None:
        """User at exact maximum (no min) returns 100."""
        score = calculate_experience_score(
            user_years=5,
            job_min_years=None,
            job_max_years=5,
        )
        assert score == 100.0

    def test_exceeds_maximum_penalized(self) -> None:
        """User exceeding maximum (no min) gets over-qualified penalty.

        User: 7 years, max: 5 years
        Gap: 2 years over
        Score: max(50, 100 - (2 * 5)) = max(50, 90) = 90
        """
        score = calculate_experience_score(
            user_years=7,
            job_min_years=None,
            job_max_years=5,
        )
        assert score == pytest.approx(90.0, abs=0.1)


# =============================================================================
# Under-Qualified Tests (Range Specified)
# =============================================================================


class TestUnderQualified:
    """Tests for users under the required experience range."""

    def test_one_year_under_penalty(self) -> None:
        """Under by 1 year: -15 points.

        User: 4 years, job: 5-8 years
        Gap: 1 year under
        Score: 100 - (1 * 15) = 85
        """
        score = calculate_experience_score(
            user_years=4,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == pytest.approx(85.0, abs=0.1)

    def test_two_years_under_penalty(self) -> None:
        """Under by 2 years: -30 points.

        User: 3 years, job: 5-8 years
        Gap: 2 years under
        Score: 100 - (2 * 15) = 70
        """
        score = calculate_experience_score(
            user_years=3,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == pytest.approx(70.0, abs=0.1)

    def test_three_years_under_penalty(self) -> None:
        """Under by 3 years: -45 points.

        User: 2 years, job: 5-8 years
        Gap: 3 years under
        Score: 100 - (3 * 15) = 55
        """
        score = calculate_experience_score(
            user_years=2,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == pytest.approx(55.0, abs=0.1)

    def test_severe_under_qualification_floored_at_zero(self) -> None:
        """Severely under-qualified is floored at 0.

        User: 0 years, job: 10+ years
        Gap: 10 years under
        Score: max(0, 100 - (10 * 15)) = max(0, -50) = 0
        """
        score = calculate_experience_score(
            user_years=0,
            job_min_years=10,
            job_max_years=None,
        )
        assert score == 0.0

    def test_none_experience_treated_as_zero(self) -> None:
        """None experience is treated as 0 years.

        User: None (→ 0), job: 5 years
        Gap: 5 years under
        Score: max(0, 100 - (5 * 15)) = max(0, 25) = 25
        """
        score = calculate_experience_score(
            user_years=None,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == pytest.approx(25.0, abs=0.1)


# =============================================================================
# Over-Qualified Tests (Range Specified)
# =============================================================================


class TestOverQualified:
    """Tests for users over the required experience range."""

    def test_one_year_over_penalty(self) -> None:
        """Over by 1 year: -5 points.

        User: 9 years, job: 5-8 years
        Gap: 1 year over
        Score: max(50, 100 - (1 * 5)) = max(50, 95) = 95
        """
        score = calculate_experience_score(
            user_years=9,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == pytest.approx(95.0, abs=0.1)

    def test_two_years_over_penalty(self) -> None:
        """Over by 2 years: -10 points.

        User: 10 years, job: 5-8 years
        Gap: 2 years over
        Score: max(50, 100 - (2 * 5)) = max(50, 90) = 90
        """
        score = calculate_experience_score(
            user_years=10,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == pytest.approx(90.0, abs=0.1)

    def test_four_years_over_penalty(self) -> None:
        """Over by 4 years: -20 points.

        User: 12 years, job: 5-8 years
        Gap: 4 years over
        Score: max(50, 100 - (4 * 5)) = max(50, 80) = 80
        """
        score = calculate_experience_score(
            user_years=12,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == pytest.approx(80.0, abs=0.1)

    def test_severely_over_qualified_floored_at_50(self) -> None:
        """Severely over-qualified is floored at 50.

        User: 20 years, job: 5-8 years
        Gap: 12 years over
        Score: max(50, 100 - (12 * 5)) = max(50, 40) = 50
        """
        score = calculate_experience_score(
            user_years=20,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == 50.0

    def test_extremely_over_qualified_still_50(self) -> None:
        """Very senior person applying for junior role floors at 50.

        User: 30 years, job: 2-5 years
        Gap: 25 years over
        Score: max(50, 100 - (25 * 5)) = max(50, -25) = 50
        """
        score = calculate_experience_score(
            user_years=30,
            job_min_years=2,
            job_max_years=5,
        )
        assert score == 50.0


# =============================================================================
# Worked Examples from REQ-008 §4.4
# =============================================================================


class TestWorkedExamples:
    """Verify worked examples from REQ-008 §4.4."""

    def test_example_1_under_qualified(self) -> None:
        """Example 1: Under-qualified.

        User: 3 years experience
        Job: 5-8 years required
        Gap: 5 - 3 = 2 years under
        Score: max(0, 100 - (2 * 15)) = 100 - 30 = 70
        """
        score = calculate_experience_score(
            user_years=3,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == pytest.approx(70.0, abs=0.1)

    def test_example_2_perfect_fit(self) -> None:
        """Example 2: Perfect fit.

        User: 6 years experience
        Job: 5-8 years required
        5 <= 6 <= 8 = within range
        Score: 100
        """
        score = calculate_experience_score(
            user_years=6,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == 100.0

    def test_example_3_over_qualified(self) -> None:
        """Example 3: Over-qualified.

        User: 12 years experience
        Job: 5-8 years required
        Gap: 12 - 8 = 4 years over
        Score: max(50, 100 - (4 * 5)) = max(50, 80) = 80
        """
        score = calculate_experience_score(
            user_years=12,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == pytest.approx(80.0, abs=0.1)

    def test_example_4_severely_over_qualified(self) -> None:
        """Example 4: Severely over-qualified.

        User: 20 years experience
        Job: 5-8 years required
        Gap: 20 - 8 = 12 years over
        Score: max(50, 100 - (12 * 5)) = max(50, 40) = 50 (floored)
        """
        score = calculate_experience_score(
            user_years=20,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == 50.0

    def test_example_5_no_requirement_specified(self) -> None:
        """Example 5: No requirement specified.

        User: 7 years experience
        Job: No min/max set
        Score: 70 (neutral)
        """
        score = calculate_experience_score(
            user_years=7,
            job_min_years=None,
            job_max_years=None,
        )
        assert score == 70.0

    def test_example_6_minimum_only_meets_it(self) -> None:
        """Example 6: Minimum only, meets it.

        User: 5 years experience
        Job: 3+ years required (no max)
        5 >= 3
        Score: 100
        """
        score = calculate_experience_score(
            user_years=5,
            job_min_years=3,
            job_max_years=None,
        )
        assert score == 100.0


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_years_against_zero_minimum(self) -> None:
        """0 years meeting 0 minimum returns 100."""
        score = calculate_experience_score(
            user_years=0,
            job_min_years=0,
            job_max_years=2,
        )
        assert score == 100.0

    def test_fractional_years_under(self) -> None:
        """Fractional years experience handled correctly.

        User: 4.5 years, job: 5-8 years
        Gap: 0.5 years under
        Score: 100 - (0.5 * 15) = 92.5
        """
        score = calculate_experience_score(
            user_years=4.5,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == pytest.approx(92.5, abs=0.1)

    def test_fractional_years_over(self) -> None:
        """Fractional years over handled correctly.

        User: 8.5 years, job: 5-8 years
        Gap: 0.5 years over
        Score: max(50, 100 - (0.5 * 5)) = 97.5
        """
        score = calculate_experience_score(
            user_years=8.5,
            job_min_years=5,
            job_max_years=8,
        )
        assert score == pytest.approx(97.5, abs=0.1)

    def test_entry_level_against_senior_requirement(self) -> None:
        """Entry-level user against senior role.

        User: 1 year, job: 8-10 years
        Gap: 7 years under
        Score: max(0, 100 - (7 * 15)) = max(0, -5) = 0
        """
        score = calculate_experience_score(
            user_years=1,
            job_min_years=8,
            job_max_years=10,
        )
        assert score == 0.0

    def test_rejects_negative_experience(self) -> None:
        """Negative experience raises ValueError."""
        with pytest.raises(ValueError, match="negative"):
            calculate_experience_score(
                user_years=-1,
                job_min_years=3,
                job_max_years=5,
            )

    def test_rejects_negative_job_minimum(self) -> None:
        """Negative job minimum raises ValueError."""
        with pytest.raises(ValueError, match="negative"):
            calculate_experience_score(
                user_years=5,
                job_min_years=-1,
                job_max_years=5,
            )

    def test_rejects_negative_job_maximum(self) -> None:
        """Negative job maximum raises ValueError."""
        with pytest.raises(ValueError, match="negative"):
            calculate_experience_score(
                user_years=5,
                job_min_years=3,
                job_max_years=-1,
            )

    def test_rejects_min_greater_than_max(self) -> None:
        """Job minimum > maximum raises ValueError."""
        with pytest.raises(ValueError, match="min.*cannot exceed.*max"):
            calculate_experience_score(
                user_years=5,
                job_min_years=10,
                job_max_years=5,
            )

    def test_rejects_user_years_exceeding_max(self) -> None:
        """User years exceeding 100 raises ValueError."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            calculate_experience_score(
                user_years=101,
                job_min_years=5,
                job_max_years=8,
            )

    def test_rejects_job_min_exceeding_max(self) -> None:
        """Job minimum years exceeding 100 raises ValueError."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            calculate_experience_score(
                user_years=5,
                job_min_years=101,
                job_max_years=None,
            )

    def test_rejects_job_max_exceeding_max(self) -> None:
        """Job maximum years exceeding 100 raises ValueError."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            calculate_experience_score(
                user_years=5,
                job_min_years=None,
                job_max_years=101,
            )

    def test_accepts_exactly_100_years(self) -> None:
        """100 years is the maximum acceptable value."""
        score = calculate_experience_score(
            user_years=100,
            job_min_years=100,
            job_max_years=100,
        )
        assert score == 100.0
