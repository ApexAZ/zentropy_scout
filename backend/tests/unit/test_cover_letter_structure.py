"""Tests for cover letter structure definitions.

REQ-010 §5.1: Cover Letter Structure.

Verifies that the cover letter section enum, section specs, and word count
constants are correctly defined and consistent.
"""

import dataclasses

import pytest

from app.services.cover_letter_structure import (
    COVER_LETTER_SECTIONS_ORDERED,
    MAX_COVER_LETTER_WORDS,
    MIN_COVER_LETTER_WORDS,
    CoverLetterSection,
    SectionSpec,
    get_section_spec,
)

# =============================================================================
# CoverLetterSection Enum
# =============================================================================


class TestCoverLetterSection:
    """Tests for the CoverLetterSection enum."""

    def test_has_five_sections(self) -> None:
        """Cover letter structure defines exactly 5 sections per REQ-010 §5.1."""
        assert len(CoverLetterSection) == 5

    def test_hook_section_exists(self) -> None:
        assert CoverLetterSection.HOOK.value == "hook"

    def test_value_proposition_section_exists(self) -> None:
        assert CoverLetterSection.VALUE_PROPOSITION.value == "value_proposition"

    def test_achievement_highlight_section_exists(self) -> None:
        assert CoverLetterSection.ACHIEVEMENT_HIGHLIGHT.value == "achievement_highlight"

    def test_cultural_alignment_section_exists(self) -> None:
        assert CoverLetterSection.CULTURAL_ALIGNMENT.value == "cultural_alignment"

    def test_closing_section_exists(self) -> None:
        assert CoverLetterSection.CLOSING.value == "closing"


# =============================================================================
# SectionSpec
# =============================================================================


class TestSectionSpec:
    """Tests for the SectionSpec dataclass."""

    def test_section_spec_has_required_fields(self) -> None:
        """SectionSpec stores purpose and sentence range."""
        spec = SectionSpec(
            purpose="Test purpose",
            min_sentences=1,
            max_sentences=3,
        )
        assert spec.purpose == "Test purpose"
        assert spec.min_sentences == 1
        assert spec.max_sentences == 3

    def test_section_spec_min_less_than_max(self) -> None:
        """All real section specs should have min <= max sentences."""
        for section in CoverLetterSection:
            spec = get_section_spec(section)
            assert spec.min_sentences <= spec.max_sentences, (
                f"{section.name}: min_sentences ({spec.min_sentences}) > "
                f"max_sentences ({spec.max_sentences})"
            )

    def test_section_spec_positive_sentence_counts(self) -> None:
        """All section specs must have positive sentence counts."""
        for section in CoverLetterSection:
            spec = get_section_spec(section)
            assert spec.min_sentences > 0, f"{section.name}: min_sentences must be > 0"
            assert spec.max_sentences > 0, f"{section.name}: max_sentences must be > 0"

    def test_section_spec_has_nonempty_purpose(self) -> None:
        """All section specs must have a non-empty purpose string."""
        for section in CoverLetterSection:
            spec = get_section_spec(section)
            assert spec.purpose.strip(), f"{section.name}: purpose must not be empty"

    def test_section_spec_is_frozen(self) -> None:
        """SectionSpec is frozen to prevent accidental mutation of config data."""
        spec = SectionSpec(purpose="test", min_sentences=1, max_sentences=2)
        with pytest.raises(dataclasses.FrozenInstanceError):
            spec.purpose = "changed"  # type: ignore[misc]


# =============================================================================
# Section Specs Mapping
# =============================================================================


class TestGetSectionSpec:
    """Tests for the get_section_spec function."""

    def test_every_section_has_a_spec(self) -> None:
        """Every CoverLetterSection enum member must have a spec defined."""
        for section in CoverLetterSection:
            spec = get_section_spec(section)
            assert isinstance(spec, SectionSpec), f"Missing spec for {section.name}"

    def test_hook_spec_matches_req(self) -> None:
        """REQ-010 §5.1: Hook is 1-2 sentences."""
        spec = get_section_spec(CoverLetterSection.HOOK)
        assert spec.min_sentences == 1
        assert spec.max_sentences == 2

    def test_value_proposition_spec_matches_req(self) -> None:
        """REQ-010 §5.1: Value Proposition is 2-3 sentences."""
        spec = get_section_spec(CoverLetterSection.VALUE_PROPOSITION)
        assert spec.min_sentences == 2
        assert spec.max_sentences == 3

    def test_achievement_highlight_spec_matches_req(self) -> None:
        """REQ-010 §5.1: Achievement Highlight is 3-4 sentences."""
        spec = get_section_spec(CoverLetterSection.ACHIEVEMENT_HIGHLIGHT)
        assert spec.min_sentences == 3
        assert spec.max_sentences == 4

    def test_cultural_alignment_spec_matches_req(self) -> None:
        """REQ-010 §5.1: Cultural Alignment is 1-2 sentences."""
        spec = get_section_spec(CoverLetterSection.CULTURAL_ALIGNMENT)
        assert spec.min_sentences == 1
        assert spec.max_sentences == 2

    def test_closing_spec_matches_req(self) -> None:
        """REQ-010 §5.1: Closing is 1-2 sentences."""
        spec = get_section_spec(CoverLetterSection.CLOSING)
        assert spec.min_sentences == 1
        assert spec.max_sentences == 2


# =============================================================================
# Ordered Sections List
# =============================================================================


class TestSectionsOrdered:
    """Tests for the COVER_LETTER_SECTIONS_ORDERED constant."""

    def test_ordered_list_has_five_sections(self) -> None:
        assert len(COVER_LETTER_SECTIONS_ORDERED) == 5

    def test_ordered_list_starts_with_hook(self) -> None:
        assert COVER_LETTER_SECTIONS_ORDERED[0] == CoverLetterSection.HOOK

    def test_ordered_list_ends_with_closing(self) -> None:
        assert COVER_LETTER_SECTIONS_ORDERED[-1] == CoverLetterSection.CLOSING

    def test_ordered_list_matches_req_order(self) -> None:
        """REQ-010 §5.1: Sections appear in spec order."""
        expected = (
            CoverLetterSection.HOOK,
            CoverLetterSection.VALUE_PROPOSITION,
            CoverLetterSection.ACHIEVEMENT_HIGHLIGHT,
            CoverLetterSection.CULTURAL_ALIGNMENT,
            CoverLetterSection.CLOSING,
        )
        assert expected == COVER_LETTER_SECTIONS_ORDERED

    def test_ordered_list_contains_all_sections(self) -> None:
        """Every enum member is represented in the ordered list."""
        assert set(COVER_LETTER_SECTIONS_ORDERED) == set(CoverLetterSection)

    def test_ordered_list_is_immutable(self) -> None:
        """The ordered list should be a tuple to prevent mutation."""
        assert isinstance(COVER_LETTER_SECTIONS_ORDERED, tuple)


# =============================================================================
# Word Count Constants
# =============================================================================


class TestWordCountConstants:
    """Tests for cover letter word count bounds."""

    def test_min_words_is_250(self) -> None:
        """REQ-010 §5.1: Minimum 250 words."""
        assert MIN_COVER_LETTER_WORDS == 250

    def test_max_words_is_350(self) -> None:
        """REQ-010 §5.1: Maximum 350 words."""
        assert MAX_COVER_LETTER_WORDS == 350

    def test_min_less_than_max(self) -> None:
        assert MIN_COVER_LETTER_WORDS < MAX_COVER_LETTER_WORDS

    def test_word_count_range_is_positive(self) -> None:
        """Both bounds must be positive and the range must be reasonable."""
        assert MIN_COVER_LETTER_WORDS > 0
        assert MAX_COVER_LETTER_WORDS > 0
