"""Tests for regeneration handling types.

REQ-010 §7.1: Feedback Categories — enum and configuration types
that §7.2 (sanitization) and §7.3 (prompt modifier) will consume.
"""

from dataclasses import replace

import pytest

from app.services.regeneration import (
    MAX_FEEDBACK_LENGTH,
    MAX_TONE_LENGTH,
    MAX_WORD_COUNT,
    FeedbackCategory,
    RegenerationConfig,
)

# =============================================================================
# FeedbackCategory Enum (REQ-010 §7.1)
# =============================================================================


class TestFeedbackCategory:
    """Test the FeedbackCategory enum values and behavior."""

    def test_from_string(self) -> None:
        """Can construct from string value."""
        assert FeedbackCategory("tone_adjustment") is FeedbackCategory.TONE_ADJUSTMENT

    def test_from_string_raises_when_invalid(self) -> None:
        """Invalid string raises ValueError."""
        with pytest.raises(ValueError, match="not_a_category"):
            FeedbackCategory("not_a_category")


# =============================================================================
# RegenerationConfig (REQ-010 §7.1)
# =============================================================================


class TestRegenerationConfig:
    """Test the RegenerationConfig data structure."""

    def test_minimal_creation(self) -> None:
        """Can create with just feedback text and category."""
        config = RegenerationConfig(
            feedback="Make it shorter",
            category=FeedbackCategory.LENGTH_ADJUSTMENT,
        )
        assert config.feedback == "Make it shorter"
        assert config.category is FeedbackCategory.LENGTH_ADJUSTMENT

    def test_defaults_are_none(self) -> None:
        """Optional fields default to None."""
        config = RegenerationConfig(
            feedback="Start fresh",
            category=FeedbackCategory.COMPLETE_REDO,
        )
        assert config.excluded_story_ids is None
        assert config.tone_override is None
        assert config.word_count_target is None

    def test_story_rejection_with_excluded_ids(self) -> None:
        """Story rejection carries excluded story IDs."""
        config = RegenerationConfig(
            feedback="Don't use the failing project story",
            category=FeedbackCategory.STORY_REJECTION,
            excluded_story_ids=("story-1", "story-2"),
        )
        assert config.excluded_story_ids == ("story-1", "story-2")

    def test_tone_adjustment_with_override(self) -> None:
        """Tone adjustment carries a tone override string."""
        config = RegenerationConfig(
            feedback="Make it less formal",
            category=FeedbackCategory.TONE_ADJUSTMENT,
            tone_override="casual",
        )
        assert config.tone_override == "casual"

    def test_length_adjustment_with_word_count(self) -> None:
        """Length adjustment carries min/max word count target."""
        config = RegenerationConfig(
            feedback="Make it shorter",
            category=FeedbackCategory.LENGTH_ADJUSTMENT,
            word_count_target=(200, 300),
        )
        assert config.word_count_target == (200, 300)

    def test_focus_shift_with_feedback_only(self) -> None:
        """Focus shift relies on feedback text; no extra fields needed."""
        config = RegenerationConfig(
            feedback="Focus more on technical skills",
            category=FeedbackCategory.FOCUS_SHIFT,
        )
        assert config.feedback == "Focus more on technical skills"
        assert config.category is FeedbackCategory.FOCUS_SHIFT

    def test_is_frozen(self) -> None:
        """Config is immutable once created."""
        config = RegenerationConfig(
            feedback="test",
            category=FeedbackCategory.COMPLETE_REDO,
        )
        updated = replace(config, feedback="changed")
        assert config.feedback == "test"
        assert updated.feedback == "changed"

    def test_full_configuration(self) -> None:
        """All fields can be set together."""
        config = RegenerationConfig(
            feedback="Use different stories and make it casual, 200-300 words",
            category=FeedbackCategory.STORY_REJECTION,
            excluded_story_ids=("story-abc",),
            tone_override="casual",
            word_count_target=(200, 300),
        )
        assert (
            config.feedback == "Use different stories and make it casual, 200-300 words"
        )
        assert config.category is FeedbackCategory.STORY_REJECTION
        assert config.excluded_story_ids == ("story-abc",)
        assert config.tone_override == "casual"
        assert config.word_count_target == (200, 300)

    def test_excluded_story_ids_is_truly_immutable(self) -> None:
        """Tuple excluded_story_ids cannot be mutated in-place."""
        config = RegenerationConfig(
            feedback="test",
            category=FeedbackCategory.STORY_REJECTION,
            excluded_story_ids=("story-1",),
        )
        updated = replace(config, excluded_story_ids=("story-1", "story-2"))
        assert config.excluded_story_ids == ("story-1",)
        assert updated.excluded_story_ids == ("story-1", "story-2")

    def test_empty_feedback_accepted(self) -> None:
        """Empty feedback string is valid (edge case)."""
        config = RegenerationConfig(
            feedback="",
            category=FeedbackCategory.COMPLETE_REDO,
        )
        assert config.feedback == ""

    def test_empty_excluded_story_ids_tuple(self) -> None:
        """Empty tuple is distinct from None (explicitly no exclusions)."""
        config = RegenerationConfig(
            feedback="test",
            category=FeedbackCategory.STORY_REJECTION,
            excluded_story_ids=(),
        )
        assert config.excluded_story_ids == ()
        assert config.excluded_story_ids is not None


# =============================================================================
# RegenerationConfig Validation (defense-in-depth)
# =============================================================================


class TestRegenerationConfigValidation:
    """Test __post_init__ validation on RegenerationConfig."""

    def test_feedback_at_max_length_accepted(self) -> None:
        """Feedback exactly at MAX_FEEDBACK_LENGTH is valid."""
        config = RegenerationConfig(
            feedback="x" * MAX_FEEDBACK_LENGTH,
            category=FeedbackCategory.COMPLETE_REDO,
        )
        assert len(config.feedback) == MAX_FEEDBACK_LENGTH

    def test_feedback_exceeding_max_raises(self) -> None:
        """Feedback exceeding MAX_FEEDBACK_LENGTH raises ValueError."""
        with pytest.raises(ValueError, match="feedback exceeds"):
            RegenerationConfig(
                feedback="x" * (MAX_FEEDBACK_LENGTH + 1),
                category=FeedbackCategory.COMPLETE_REDO,
            )

    def test_tone_override_at_max_length_accepted(self) -> None:
        """Tone override exactly at MAX_TONE_LENGTH is valid."""
        config = RegenerationConfig(
            feedback="test",
            category=FeedbackCategory.TONE_ADJUSTMENT,
            tone_override="x" * MAX_TONE_LENGTH,
        )
        assert len(config.tone_override) == MAX_TONE_LENGTH

    def test_tone_override_exceeding_max_raises(self) -> None:
        """Tone override exceeding MAX_TONE_LENGTH raises ValueError."""
        with pytest.raises(ValueError, match="tone_override exceeds"):
            RegenerationConfig(
                feedback="test",
                category=FeedbackCategory.TONE_ADJUSTMENT,
                tone_override="x" * (MAX_TONE_LENGTH + 1),
            )

    def test_word_count_target_negative_min_raises(self) -> None:
        """Negative min word count raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            RegenerationConfig(
                feedback="test",
                category=FeedbackCategory.LENGTH_ADJUSTMENT,
                word_count_target=(-1, 300),
            )

    def test_word_count_target_negative_max_raises(self) -> None:
        """Negative max word count raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            RegenerationConfig(
                feedback="test",
                category=FeedbackCategory.LENGTH_ADJUSTMENT,
                word_count_target=(100, -1),
            )

    def test_word_count_target_inverted_raises(self) -> None:
        """Min exceeding max raises ValueError."""
        with pytest.raises(ValueError, match="min must not exceed max"):
            RegenerationConfig(
                feedback="test",
                category=FeedbackCategory.LENGTH_ADJUSTMENT,
                word_count_target=(300, 200),
            )

    def test_word_count_target_equal_min_max_accepted(self) -> None:
        """Equal min and max is valid (exact word count target)."""
        config = RegenerationConfig(
            feedback="test",
            category=FeedbackCategory.LENGTH_ADJUSTMENT,
            word_count_target=(250, 250),
        )
        assert config.word_count_target == (250, 250)

    def test_word_count_target_exceeding_max_raises(self) -> None:
        """Max exceeding MAX_WORD_COUNT raises ValueError."""
        with pytest.raises(ValueError, match="word_count_target max exceeds"):
            RegenerationConfig(
                feedback="test",
                category=FeedbackCategory.LENGTH_ADJUSTMENT,
                word_count_target=(100, MAX_WORD_COUNT + 1),
            )

    def test_word_count_target_at_max_accepted(self) -> None:
        """Word count target exactly at MAX_WORD_COUNT is valid."""
        config = RegenerationConfig(
            feedback="test",
            category=FeedbackCategory.LENGTH_ADJUSTMENT,
            word_count_target=(100, MAX_WORD_COUNT),
        )
        assert config.word_count_target == (100, MAX_WORD_COUNT)

    def test_word_count_zero_min_accepted(self) -> None:
        """Zero min word count is valid."""
        config = RegenerationConfig(
            feedback="test",
            category=FeedbackCategory.LENGTH_ADJUSTMENT,
            word_count_target=(0, 300),
        )
        assert config.word_count_target == (0, 300)
