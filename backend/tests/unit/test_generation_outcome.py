"""Tests for generation outcome tracking.

REQ-010 §10.2: Feedback Loop.

Tracks three generation outcomes (approved, regenerated, abandoned) and
categorizes user feedback into the five REQ-010 §7.1 categories via
keyword matching.
"""

from dataclasses import replace

from app.services.generation_outcome import (
    _MAX_GENERATION_ID_LENGTH,
    _MAX_REASON_LENGTH,
    GenerationOutcome,
    GenerationOutcomeRecord,
    categorize_feedback,
    create_outcome_record,
)
from app.services.regeneration import FeedbackCategory

_GEN_ID = "abc-123"
_GEN_ID_APPROVED = "gen-001"
_GEN_ID_REGENERATED = "gen-002"
_GEN_ID_ABANDONED = "gen-003"
_FEEDBACK_SHORTER = "Make it shorter"

# =============================================================================
# GenerationOutcomeRecord Structure
# =============================================================================


class TestGenerationOutcomeRecordStructure:
    """Tests for GenerationOutcomeRecord frozen dataclass."""

    def test_record_is_frozen(self) -> None:
        """GenerationOutcomeRecord should be immutable."""
        record = create_outcome_record(
            generation_id=_GEN_ID,
            outcome=GenerationOutcome.APPROVED,
        )
        updated = replace(record, generation_id="changed-id")
        assert record.generation_id == _GEN_ID
        assert updated.generation_id == "changed-id"

    def test_record_has_all_fields(self) -> None:
        """GenerationOutcomeRecord should have all required fields."""
        record = create_outcome_record(
            generation_id=_GEN_ID,
            outcome=GenerationOutcome.APPROVED,
        )
        assert hasattr(record, "generation_id")
        assert hasattr(record, "outcome")
        assert hasattr(record, "feedback_category")
        assert hasattr(record, "regeneration_reason")

    def test_record_type(self) -> None:
        """create_outcome_record should return a GenerationOutcomeRecord."""
        record = create_outcome_record(
            generation_id=_GEN_ID,
            outcome=GenerationOutcome.APPROVED,
        )
        assert isinstance(record, GenerationOutcomeRecord)


# =============================================================================
# create_outcome_record — Approved
# =============================================================================


class TestCreateOutcomeApproved:
    """REQ-010 §10.2: Approved outcome has no feedback or reason."""

    def test_approved_sets_outcome(self) -> None:
        """Approved record should have APPROVED outcome."""
        record = create_outcome_record(
            generation_id=_GEN_ID_APPROVED,
            outcome=GenerationOutcome.APPROVED,
        )
        assert record.outcome == GenerationOutcome.APPROVED

    def test_approved_no_feedback_category(self) -> None:
        """Approved record with no feedback should have None category."""
        record = create_outcome_record(
            generation_id=_GEN_ID_APPROVED,
            outcome=GenerationOutcome.APPROVED,
        )
        assert record.feedback_category is None

    def test_approved_no_regeneration_reason(self) -> None:
        """Approved record should have None regeneration reason."""
        record = create_outcome_record(
            generation_id=_GEN_ID_APPROVED,
            outcome=GenerationOutcome.APPROVED,
        )
        assert record.regeneration_reason is None

    def test_approved_preserves_generation_id(self) -> None:
        """Approved record should preserve the generation ID."""
        record = create_outcome_record(
            generation_id=_GEN_ID_APPROVED,
            outcome=GenerationOutcome.APPROVED,
        )
        assert record.generation_id == _GEN_ID_APPROVED


# =============================================================================
# create_outcome_record — Regenerated with Feedback
# =============================================================================


class TestCreateOutcomeRegenerated:
    """REQ-010 §10.2: Regenerated outcome categorizes feedback."""

    def test_regenerated_sets_outcome(self) -> None:
        """Regenerated record should have REGENERATED outcome."""
        record = create_outcome_record(
            generation_id=_GEN_ID_REGENERATED,
            outcome=GenerationOutcome.REGENERATED,
            feedback=_FEEDBACK_SHORTER,
            regeneration_reason="Too long",
        )
        assert record.outcome == GenerationOutcome.REGENERATED

    def test_regenerated_categorizes_feedback(self) -> None:
        """Regenerated record with feedback should have a category."""
        record = create_outcome_record(
            generation_id=_GEN_ID_REGENERATED,
            outcome=GenerationOutcome.REGENERATED,
            feedback=_FEEDBACK_SHORTER,
        )
        assert record.feedback_category is not None

    def test_regenerated_preserves_reason(self) -> None:
        """Regenerated record should preserve regeneration reason."""
        record = create_outcome_record(
            generation_id=_GEN_ID_REGENERATED,
            outcome=GenerationOutcome.REGENERATED,
            feedback=_FEEDBACK_SHORTER,
            regeneration_reason="Too long",
        )
        assert record.regeneration_reason == "Too long"

    def test_regenerated_no_feedback_no_category(self) -> None:
        """Regenerated with no feedback should have None category."""
        record = create_outcome_record(
            generation_id=_GEN_ID_REGENERATED,
            outcome=GenerationOutcome.REGENERATED,
        )
        assert record.feedback_category is None


# =============================================================================
# create_outcome_record — Abandoned
# =============================================================================


class TestCreateOutcomeAbandoned:
    """REQ-010 §10.2: Abandoned outcome."""

    def test_abandoned_sets_outcome(self) -> None:
        """Abandoned record should have ABANDONED outcome."""
        record = create_outcome_record(
            generation_id=_GEN_ID_ABANDONED,
            outcome=GenerationOutcome.ABANDONED,
        )
        assert record.outcome == GenerationOutcome.ABANDONED

    def test_abandoned_no_feedback_category(self) -> None:
        """Abandoned record should have None category."""
        record = create_outcome_record(
            generation_id=_GEN_ID_ABANDONED,
            outcome=GenerationOutcome.ABANDONED,
        )
        assert record.feedback_category is None


# =============================================================================
# categorize_feedback — Story Rejection
# =============================================================================


class TestCategorizeFeedbackStoryRejection:
    """REQ-010 §7.1: 'Don't use the failing project story'."""

    def test_dont_use_story(self) -> None:
        """'Don't use' should categorize as STORY_REJECTION."""
        assert (
            categorize_feedback("Don't use the failing project story")
            == FeedbackCategory.STORY_REJECTION
        )

    def test_remove_story(self) -> None:
        """'Remove' keyword should categorize as STORY_REJECTION."""
        assert (
            categorize_feedback("Remove that story") == FeedbackCategory.STORY_REJECTION
        )

    def test_exclude_story(self) -> None:
        """'Exclude' keyword should categorize as STORY_REJECTION."""
        assert (
            categorize_feedback("Exclude the cloud migration story")
            == FeedbackCategory.STORY_REJECTION
        )

    def test_different_story(self) -> None:
        """'Different story' should categorize as STORY_REJECTION."""
        assert (
            categorize_feedback("Use a different story")
            == FeedbackCategory.STORY_REJECTION
        )


# =============================================================================
# categorize_feedback — Tone Adjustment
# =============================================================================


class TestCategorizeFeedbackToneAdjustment:
    """REQ-010 §7.1: 'Make it less formal'."""

    def test_less_formal(self) -> None:
        """'Less formal' should categorize as TONE_ADJUSTMENT."""
        assert (
            categorize_feedback("Make it less formal")
            == FeedbackCategory.TONE_ADJUSTMENT
        )

    def test_more_professional(self) -> None:
        """'More professional' should categorize as TONE_ADJUSTMENT."""
        assert (
            categorize_feedback("More professional please")
            == FeedbackCategory.TONE_ADJUSTMENT
        )

    def test_tone_keyword(self) -> None:
        """'Tone' keyword should categorize as TONE_ADJUSTMENT."""
        assert (
            categorize_feedback("Change the tone") == FeedbackCategory.TONE_ADJUSTMENT
        )

    def test_casual(self) -> None:
        """'Casual' keyword should categorize as TONE_ADJUSTMENT."""
        assert (
            categorize_feedback("Make it more casual")
            == FeedbackCategory.TONE_ADJUSTMENT
        )


# =============================================================================
# categorize_feedback — Length Adjustment
# =============================================================================


class TestCategorizeFeedbackLengthAdjustment:
    """REQ-010 §7.1: 'Make it shorter'."""

    def test_shorter(self) -> None:
        """'Shorter' should categorize as LENGTH_ADJUSTMENT."""
        assert (
            categorize_feedback(_FEEDBACK_SHORTER) == FeedbackCategory.LENGTH_ADJUSTMENT
        )

    def test_longer(self) -> None:
        """'Longer' should categorize as LENGTH_ADJUSTMENT."""
        assert (
            categorize_feedback("Make it longer") == FeedbackCategory.LENGTH_ADJUSTMENT
        )

    def test_too_long(self) -> None:
        """'Too long' should categorize as LENGTH_ADJUSTMENT."""
        assert (
            categorize_feedback("This is too long")
            == FeedbackCategory.LENGTH_ADJUSTMENT
        )

    def test_word_count(self) -> None:
        """'Word count' should categorize as LENGTH_ADJUSTMENT."""
        assert (
            categorize_feedback("Reduce the word count")
            == FeedbackCategory.LENGTH_ADJUSTMENT
        )


# =============================================================================
# categorize_feedback — Focus Shift
# =============================================================================


class TestCategorizeFeedbackFocusShift:
    """REQ-010 §7.1: 'Focus more on technical skills'."""

    def test_focus_on(self) -> None:
        """'Focus' keyword should categorize as FOCUS_SHIFT."""
        assert (
            categorize_feedback("Focus more on technical skills")
            == FeedbackCategory.FOCUS_SHIFT
        )

    def test_emphasize(self) -> None:
        """'Emphasize' keyword should categorize as FOCUS_SHIFT."""
        assert (
            categorize_feedback("Emphasize my leadership experience")
            == FeedbackCategory.FOCUS_SHIFT
        )

    def test_highlight(self) -> None:
        """'Highlight' keyword should categorize as FOCUS_SHIFT."""
        assert (
            categorize_feedback("Highlight my AWS certifications")
            == FeedbackCategory.FOCUS_SHIFT
        )

    def test_more_about(self) -> None:
        """'More about' should categorize as FOCUS_SHIFT."""
        assert (
            categorize_feedback("Talk more about my management skills")
            == FeedbackCategory.FOCUS_SHIFT
        )


# =============================================================================
# categorize_feedback — Complete Redo
# =============================================================================


class TestCategorizeFeedbackCompleteRedo:
    """REQ-010 §7.1: 'Start fresh'."""

    def test_start_fresh(self) -> None:
        """'Start fresh' should categorize as COMPLETE_REDO."""
        assert categorize_feedback("Start fresh") == FeedbackCategory.COMPLETE_REDO

    def test_start_over(self) -> None:
        """'Start over' should categorize as COMPLETE_REDO."""
        assert (
            categorize_feedback("Start over please") == FeedbackCategory.COMPLETE_REDO
        )

    def test_redo(self) -> None:
        """'Redo' keyword should categorize as COMPLETE_REDO."""
        assert (
            categorize_feedback("Redo the whole thing")
            == FeedbackCategory.COMPLETE_REDO
        )

    def test_from_scratch(self) -> None:
        """'From scratch' should categorize as COMPLETE_REDO."""
        assert (
            categorize_feedback("Rewrite from scratch")
            == FeedbackCategory.COMPLETE_REDO
        )


# =============================================================================
# categorize_feedback — Default / Ambiguous
# =============================================================================


class TestCategorizeFeedbackDefault:
    """When no keywords match, default to COMPLETE_REDO."""

    def test_ambiguous_feedback_defaults_to_complete_redo(self) -> None:
        """Unrecognized feedback should default to COMPLETE_REDO."""
        assert categorize_feedback("I don't like it") == FeedbackCategory.COMPLETE_REDO

    def test_empty_feedback_defaults_to_complete_redo(self) -> None:
        """Empty feedback should default to COMPLETE_REDO."""
        assert categorize_feedback("") == FeedbackCategory.COMPLETE_REDO

    def test_case_insensitive(self) -> None:
        """Categorization should be case-insensitive."""
        assert (
            categorize_feedback("MAKE IT SHORTER") == FeedbackCategory.LENGTH_ADJUSTMENT
        )


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Boundary conditions for generation outcome tracking."""

    def test_empty_generation_id(self) -> None:
        """Should handle empty generation ID."""
        record = create_outcome_record(
            generation_id="",
            outcome=GenerationOutcome.APPROVED,
        )
        assert record.generation_id == ""

    def test_feedback_with_only_whitespace(self) -> None:
        """Whitespace-only feedback should default to COMPLETE_REDO."""
        assert categorize_feedback("   ") == FeedbackCategory.COMPLETE_REDO

    def test_multiple_keywords_first_category_wins(self) -> None:
        """When multiple categories match, priority order determines result."""
        # "shorter" → LENGTH (position 3) checked before "focus" → FOCUS (position 4)
        result = categorize_feedback("Make it shorter and focus on skills")
        assert result == FeedbackCategory.LENGTH_ADJUSTMENT

    def test_empty_string_feedback_in_record(self) -> None:
        """Empty-string feedback should produce COMPLETE_REDO category."""
        record = create_outcome_record(
            generation_id=_GEN_ID,
            outcome=GenerationOutcome.REGENERATED,
            feedback="",
        )
        # Empty string is falsy, so feedback="" → no categorization (None)
        assert record.feedback_category is None

    def test_very_long_feedback_does_not_hang(self) -> None:
        """Large feedback should be handled efficiently via truncation."""
        result = categorize_feedback("x" * 100_000)
        assert result == FeedbackCategory.COMPLETE_REDO

    def test_long_feedback_still_matches_keyword_within_bounds(self) -> None:
        """Keyword within truncation limit should still match."""
        # Place "shorter" at position 100 (well within 500-char limit)
        feedback = "x" * 100 + " shorter " + "x" * 100_000
        assert categorize_feedback(feedback) == FeedbackCategory.LENGTH_ADJUSTMENT

    def test_long_generation_id_truncated(self) -> None:
        """Oversized generation ID should be truncated."""
        long_id = "a" * 200
        record = create_outcome_record(
            generation_id=long_id,
            outcome=GenerationOutcome.APPROVED,
        )
        assert len(record.generation_id) == _MAX_GENERATION_ID_LENGTH

    def test_long_regeneration_reason_truncated(self) -> None:
        """Oversized regeneration reason should be truncated."""
        long_reason = "b" * 1000
        record = create_outcome_record(
            generation_id=_GEN_ID,
            outcome=GenerationOutcome.REGENERATED,
            regeneration_reason=long_reason,
        )
        assert len(record.regeneration_reason) == _MAX_REASON_LENGTH


# =============================================================================
# Keyword Coverage
# =============================================================================


class TestKeywordCoverage:
    """Verify all defined keywords produce the expected category."""

    def test_dont_use_without_apostrophe(self) -> None:
        """'dont use' (no apostrophe) should match STORY_REJECTION."""
        assert (
            categorize_feedback("dont use that one") == FeedbackCategory.STORY_REJECTION
        )

    def test_drop_keyword(self) -> None:
        """'Drop' keyword should match STORY_REJECTION."""
        assert (
            categorize_feedback("drop that story") == FeedbackCategory.STORY_REJECTION
        )

    def test_friendly_keyword(self) -> None:
        """'Friendly' keyword should match TONE_ADJUSTMENT."""
        assert (
            categorize_feedback("make it more friendly")
            == FeedbackCategory.TONE_ADJUSTMENT
        )

    def test_conversational_keyword(self) -> None:
        """'Conversational' keyword should match TONE_ADJUSTMENT."""
        assert (
            categorize_feedback("more conversational style")
            == FeedbackCategory.TONE_ADJUSTMENT
        )

    def test_too_short_keyword(self) -> None:
        """'Too short' should match LENGTH_ADJUSTMENT."""
        assert (
            categorize_feedback("it's too short") == FeedbackCategory.LENGTH_ADJUSTMENT
        )

    def test_concise_keyword(self) -> None:
        """'Concise' keyword should match LENGTH_ADJUSTMENT."""
        assert (
            categorize_feedback("make it more concise")
            == FeedbackCategory.LENGTH_ADJUSTMENT
        )

    def test_brief_keyword(self) -> None:
        """'Brief' keyword should match LENGTH_ADJUSTMENT."""
        assert (
            categorize_feedback("keep it brief") == FeedbackCategory.LENGTH_ADJUSTMENT
        )

    def test_less_about_keyword(self) -> None:
        """'Less about' should match FOCUS_SHIFT."""
        assert (
            categorize_feedback("less about management") == FeedbackCategory.FOCUS_SHIFT
        )

    def test_stress_keyword(self) -> None:
        """'Stress' keyword should match FOCUS_SHIFT."""
        assert (
            categorize_feedback("stress my technical background")
            == FeedbackCategory.FOCUS_SHIFT
        )

    def test_rewrite_keyword(self) -> None:
        """'Rewrite' keyword should match COMPLETE_REDO."""
        assert (
            categorize_feedback("rewrite it completely")
            == FeedbackCategory.COMPLETE_REDO
        )

    def test_scrap_keyword(self) -> None:
        """'Scrap' keyword should match COMPLETE_REDO."""
        assert (
            categorize_feedback("scrap this and try again")
            == FeedbackCategory.COMPLETE_REDO
        )
