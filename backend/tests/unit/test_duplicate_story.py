"""Tests for duplicate story selection edge cases.

REQ-010 §8.4: Duplicate Story Selection.

Four scenarios:
1. Only 1 story available → shorter cover letter (200-250 words)
2. Top 2 stories from same job → substitute #3 if outcomes similar
3. User excluded all high-scoring stories → use best available + disclaimer
4. All stories used recently → ignore freshness penalty
"""

import pytest

from app.services.duplicate_story import (
    _NORMAL_MAX_WORDS,
    _NORMAL_MIN_WORDS,
    _SHORT_MAX_WORDS,
    _SHORT_MIN_WORDS,
    check_duplicate_story_selection,
)

# =============================================================================
# Constants
# =============================================================================


class TestConstants:
    """Tests for module word count constants."""

    def test_normal_min_words_value(self) -> None:
        """Normal minimum word count should be 250."""
        assert _NORMAL_MIN_WORDS == 250

    def test_normal_max_words_value(self) -> None:
        """Normal maximum word count should be 350."""
        assert _NORMAL_MAX_WORDS == 350

    def test_short_min_words_value(self) -> None:
        """Short format minimum word count should be 200."""
        assert _SHORT_MIN_WORDS == 200

    def test_short_max_words_value(self) -> None:
        """Short format maximum word count should be 250."""
        assert _SHORT_MAX_WORDS == 250


# =============================================================================
# DuplicateStoryResult Structure
# =============================================================================


class TestDuplicateStoryResultStructure:
    """Tests for DuplicateStoryResult frozen dataclass."""

    def test_result_is_frozen(self) -> None:
        """DuplicateStoryResult should be immutable."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        with pytest.raises(AttributeError):
            result.use_short_format = True  # type: ignore[misc]

    def test_result_has_all_fields(self) -> None:
        """DuplicateStoryResult should have all required fields."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert hasattr(result, "use_short_format")
        assert hasattr(result, "substitution_made")
        assert hasattr(result, "using_excluded_fallback")
        assert hasattr(result, "freshness_overridden")
        assert hasattr(result, "adjusted_min_words")
        assert hasattr(result, "adjusted_max_words")
        assert hasattr(result, "warnings")

    def test_warnings_is_tuple(self) -> None:
        """Warnings should be a tuple for immutability."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert isinstance(result.warnings, tuple)


# =============================================================================
# Normal Case — No Edge Cases
# =============================================================================


class TestNormalCase:
    """REQ-010 §8.4: No edge cases triggered with sufficient stories."""

    def test_no_edge_cases_all_false(self) -> None:
        """All edge case flags should be False when no scenarios triggered."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert result.use_short_format is False
        assert result.substitution_made is False
        assert result.using_excluded_fallback is False
        assert result.freshness_overridden is False

    def test_normal_word_counts(self) -> None:
        """Normal case should use standard word count range (250-350)."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert result.adjusted_min_words == 250
        assert result.adjusted_max_words == 350

    def test_no_warnings_when_normal(self) -> None:
        """Normal case should produce zero warnings."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert len(result.warnings) == 0


# =============================================================================
# Scenario 1: Single Story Available
# =============================================================================


class TestSingleStoryAvailable:
    """REQ-010 §8.4: Only 1 story → shorter cover letter (200-250 words)."""

    def test_single_story_sets_short_format(self) -> None:
        """available_count=1 should set use_short_format=True."""
        result = check_duplicate_story_selection(
            available_count=1,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert result.use_short_format is True

    def test_single_story_adjusts_word_counts(self) -> None:
        """Single story should use short word count range (200-250)."""
        result = check_duplicate_story_selection(
            available_count=1,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert result.adjusted_min_words == 200
        assert result.adjusted_max_words == 250

    def test_single_story_produces_warning(self) -> None:
        """Single story should produce a warning about shorter letter."""
        result = check_duplicate_story_selection(
            available_count=1,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert any("200" in w and "250" in w for w in result.warnings)

    def test_two_stories_not_short_format(self) -> None:
        """Two stories available should NOT trigger short format."""
        result = check_duplicate_story_selection(
            available_count=2,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert result.use_short_format is False


# =============================================================================
# Scenario 2: Substitution Made (Same-Job Dedup)
# =============================================================================


class TestSubstitutionMade:
    """REQ-010 §8.4: Top 2 from same job → substitute if outcomes similar."""

    def test_substitution_flag_set(self) -> None:
        """substitution_made=True should be reflected in the result."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=True,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert result.substitution_made is True

    def test_substitution_produces_warning(self) -> None:
        """Substitution should produce a warning about diversity."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=True,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert any("substitut" in w.lower() for w in result.warnings)

    def test_no_substitution_no_warning(self) -> None:
        """No substitution should produce no substitution warning."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert not any("substitut" in w.lower() for w in result.warnings)


# =============================================================================
# Scenario 3: All High-Scoring Stories Excluded
# =============================================================================


class TestExcludedFallback:
    """REQ-010 §8.4: User excluded all high-scoring → best available + disclaimer."""

    def test_excluded_sets_flag(self) -> None:
        """all_high_scoring_excluded=True should set using_excluded_fallback."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=False,
            all_high_scoring_excluded=True,
            freshness_overridden=False,
        )
        assert result.using_excluded_fallback is True

    def test_excluded_produces_warning(self) -> None:
        """Excluded fallback should produce a disclaimer warning."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=False,
            all_high_scoring_excluded=True,
            freshness_overridden=False,
        )
        assert any("exclu" in w.lower() for w in result.warnings)

    def test_not_excluded_no_warning(self) -> None:
        """No exclusion should produce no exclusion warning."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert not any("exclu" in w.lower() for w in result.warnings)


# =============================================================================
# Scenario 4: Freshness Override
# =============================================================================


class TestFreshnessOverride:
    """REQ-010 §8.4: All stories recently used → ignore freshness penalty."""

    def test_freshness_sets_flag(self) -> None:
        """freshness_overridden=True should be reflected in the result."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=True,
        )
        assert result.freshness_overridden is True

    def test_freshness_produces_warning(self) -> None:
        """Freshness override should produce a warning."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=True,
        )
        assert any(
            "recently" in w.lower() or "reus" in w.lower() for w in result.warnings
        )

    def test_no_freshness_no_warning(self) -> None:
        """No freshness override should produce no freshness warning."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert not any(
            "recently" in w.lower() or "reus" in w.lower() for w in result.warnings
        )


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Boundary conditions for story selection edge case detection."""

    def test_zero_stories_does_not_trigger_short_format(self) -> None:
        """Zero stories is handled by data_availability; short format is for exactly 1."""
        result = check_duplicate_story_selection(
            available_count=0,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert result.use_short_format is False
        assert result.adjusted_min_words == 250
        assert result.adjusted_max_words == 350

    def test_negative_available_count_does_not_trigger_short_format(self) -> None:
        """Negative count should not trigger short format (invalid input, fail open)."""
        result = check_duplicate_story_selection(
            available_count=-1,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert result.use_short_format is False

    def test_large_available_count_uses_normal_format(self) -> None:
        """Many stories should use normal word count range."""
        result = check_duplicate_story_selection(
            available_count=100,
            substitution_made=False,
            all_high_scoring_excluded=False,
            freshness_overridden=False,
        )
        assert result.use_short_format is False
        assert result.adjusted_min_words == 250
        assert result.adjusted_max_words == 350


# =============================================================================
# Combinations
# =============================================================================


class TestCombinations:
    """Tests for multiple edge cases triggered simultaneously."""

    def test_single_story_and_excluded(self) -> None:
        """Single story + all excluded should trigger both flags."""
        result = check_duplicate_story_selection(
            available_count=1,
            substitution_made=False,
            all_high_scoring_excluded=True,
            freshness_overridden=False,
        )
        assert result.use_short_format is True
        assert result.using_excluded_fallback is True
        assert result.adjusted_min_words == 200
        assert result.adjusted_max_words == 250
        assert len(result.warnings) >= 2

    def test_all_scenarios_active(self) -> None:
        """All edge cases active should produce all flags and warnings."""
        result = check_duplicate_story_selection(
            available_count=1,
            substitution_made=True,
            all_high_scoring_excluded=True,
            freshness_overridden=True,
        )
        assert result.use_short_format is True
        assert result.substitution_made is True
        assert result.using_excluded_fallback is True
        assert result.freshness_overridden is True
        assert len(result.warnings) >= 4

    def test_substitution_and_freshness(self) -> None:
        """Substitution + freshness should both produce warnings."""
        result = check_duplicate_story_selection(
            available_count=5,
            substitution_made=True,
            all_high_scoring_excluded=False,
            freshness_overridden=True,
        )
        assert result.use_short_format is False
        assert result.substitution_made is True
        assert result.freshness_overridden is True
        assert result.adjusted_min_words == 250
        assert len(result.warnings) >= 2
