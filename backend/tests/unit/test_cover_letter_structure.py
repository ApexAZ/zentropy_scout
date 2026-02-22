"""Tests for cover letter structure definitions.

REQ-010 §5.1: Cover Letter Structure.

Verifies that the cover letter section enum, section specs, and word count
constants are correctly defined and consistent.
"""

from dataclasses import replace

from app.services.cover_letter_structure import (
    CoverLetterSection,
    SectionSpec,
    get_section_spec,
)

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

    def test_section_spec_preserves_original_values(self) -> None:
        """Modifying a copy preserves the original spec values."""
        spec = SectionSpec(purpose="test", min_sentences=1, max_sentences=2)
        updated = replace(spec, purpose="changed")
        assert spec.purpose == "test"
        assert updated.purpose == "changed"


# =============================================================================
# Section Specs Mapping
# =============================================================================


class TestGetSectionSpec:
    """Tests for the get_section_spec function."""

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
