"""Cover letter structure definitions.

REQ-010 §5.1: Cover Letter Structure.

Defines the five-section structure that every generated cover letter must
follow. Provides section metadata (purpose, sentence range) and word count
bounds used by downstream modules:

- §5.4 (Validation) uses these constants to check generated cover letters.
- §5.5 (Output Schema) uses the section enum for structured output.
- ghostwriter_prompts.py system prompt mirrors this structure for LLM guidance.

Cross-reference: REQ-002b §8.1 defines the same structure from the storage
perspective (Opening, Body 1, Body 2, Closing).
"""

from dataclasses import dataclass
from enum import Enum

# =============================================================================
# Constants
# =============================================================================

MIN_COVER_LETTER_WORDS: int = 250
"""Minimum word count for a generated cover letter."""

MAX_COVER_LETTER_WORDS: int = 350
"""Maximum word count for a generated cover letter."""


# =============================================================================
# Section Enum
# =============================================================================


class CoverLetterSection(Enum):
    """The five sections of a generated cover letter.

    REQ-010 §5.1: Every cover letter follows this structure in order.
    """

    HOOK = "hook"
    VALUE_PROPOSITION = "value_proposition"
    ACHIEVEMENT_HIGHLIGHT = "achievement_highlight"
    CULTURAL_ALIGNMENT = "cultural_alignment"
    CLOSING = "closing"


# =============================================================================
# Section Spec
# =============================================================================


@dataclass(frozen=True)
class SectionSpec:
    """Metadata for a cover letter section.

    Attributes:
        purpose: What this section accomplishes.
        min_sentences: Minimum sentence count for this section.
        max_sentences: Maximum sentence count for this section.
    """

    purpose: str
    min_sentences: int
    max_sentences: int


# =============================================================================
# Section Specs Mapping
# =============================================================================

_SECTION_SPECS: dict[CoverLetterSection, SectionSpec] = {
    CoverLetterSection.HOOK: SectionSpec(
        purpose="Grab attention with company/role-specific opening",
        min_sentences=1,
        max_sentences=2,
    ),
    CoverLetterSection.VALUE_PROPOSITION: SectionSpec(
        purpose="Why you are a great fit (skills + experience match)",
        min_sentences=2,
        max_sentences=3,
    ),
    CoverLetterSection.ACHIEVEMENT_HIGHLIGHT: SectionSpec(
        purpose="Specific story demonstrating relevant capability",
        min_sentences=3,
        max_sentences=4,
    ),
    CoverLetterSection.CULTURAL_ALIGNMENT: SectionSpec(
        purpose="Show you understand their values/mission",
        min_sentences=1,
        max_sentences=2,
    ),
    CoverLetterSection.CLOSING: SectionSpec(
        purpose="Call to action + enthusiasm",
        min_sentences=1,
        max_sentences=2,
    ),
}


def get_section_spec(section: CoverLetterSection) -> SectionSpec:
    """Get the spec for a cover letter section.

    Args:
        section: The section to look up.

    Returns:
        SectionSpec with purpose and sentence range.

    Raises:
        KeyError: If the section has no spec defined (should never happen
            if _SECTION_SPECS is kept in sync with the enum).
    """
    return _SECTION_SPECS[section]


# =============================================================================
# Ordered Sections
# =============================================================================

COVER_LETTER_SECTIONS_ORDERED: tuple[CoverLetterSection, ...] = (
    CoverLetterSection.HOOK,
    CoverLetterSection.VALUE_PROPOSITION,
    CoverLetterSection.ACHIEVEMENT_HIGHLIGHT,
    CoverLetterSection.CULTURAL_ALIGNMENT,
    CoverLetterSection.CLOSING,
)
"""Sections in the order they appear in a cover letter."""
