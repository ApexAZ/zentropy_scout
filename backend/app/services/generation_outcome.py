"""Generation outcome tracking for quality metrics.

REQ-010 §10.2: Feedback Loop.

Tracks three generation outcomes (approved, regenerated, abandoned) and
categorizes user feedback into the five REQ-010 §7.1 categories via
keyword matching. Produces a structured record for quality metric
computation (REQ-010 §10.1).

The graph node calls ``create_outcome_record`` after user action and
passes the result to the repository layer for persistence.
"""

from dataclasses import dataclass
from enum import Enum

from app.services.regeneration import FeedbackCategory

_MAX_FEEDBACK_INPUT: int = 500
"""Safety bound on feedback text before categorization (REQ-010 §7.2)."""

_MAX_REASON_LENGTH: int = 500
"""Safety bound on regeneration reason text."""

_MAX_GENERATION_ID_LENGTH: int = 64
"""Safety bound on generation ID string length."""

# =============================================================================
# Enums
# =============================================================================


class GenerationOutcome(str, Enum):
    """Possible outcomes for a content generation.

    REQ-010 §10.2: Three outcomes tracked per generation.

    Values:
        APPROVED: User accepted without regeneration.
        REGENERATED: User requested regeneration with feedback.
        ABANDONED: User abandoned the generation entirely.
    """

    APPROVED = "approved"
    REGENERATED = "regenerated"
    ABANDONED = "abandoned"


# =============================================================================
# Data Models
# =============================================================================


@dataclass(frozen=True)
class GenerationOutcomeRecord:
    """Structured record for a generation outcome event.

    REQ-010 §10.2: Captures the outcome, optional feedback category,
    and optional regeneration reason for quality metric tracking.

    Attributes:
        generation_id: ID of the content generation.
        outcome: What the user did (approved, regenerated, abandoned).
        feedback_category: Classified feedback category (if feedback given).
        regeneration_reason: Free-text reason for regeneration (if given).
    """

    generation_id: str
    outcome: GenerationOutcome
    feedback_category: FeedbackCategory | None
    regeneration_reason: str | None


# =============================================================================
# Feedback Categorization (REQ-010 §7.1 + §10.2)
# =============================================================================

_CATEGORY_KEYWORDS: tuple[tuple[FeedbackCategory, tuple[str, ...]], ...] = (
    (
        FeedbackCategory.STORY_REJECTION,
        ("don't use", "dont use", "remove", "exclude", "different story", "drop"),
    ),
    (
        FeedbackCategory.TONE_ADJUSTMENT,
        ("tone", "formal", "casual", "professional", "friendly", "conversational"),
    ),
    (
        FeedbackCategory.LENGTH_ADJUSTMENT,
        (
            "shorter",
            "longer",
            "too long",
            "too short",
            "word count",
            "concise",
            "brief",
        ),
    ),
    (
        FeedbackCategory.FOCUS_SHIFT,
        ("focus", "emphasize", "highlight", "more about", "less about", "stress"),
    ),
    (
        FeedbackCategory.COMPLETE_REDO,
        ("start fresh", "start over", "redo", "from scratch", "rewrite", "scrap"),
    ),
)
"""Keyword-to-category mapping, ordered by priority (first match wins).

Note: Uses substring matching, so short keywords like "drop" may match
within longer words (e.g., "dropdown"). This is a v1 heuristic — an
LLM-based classifier can replace it for higher accuracy.
"""


def categorize_feedback(feedback: str) -> FeedbackCategory:
    """Classify user feedback into a REQ-010 §7.1 category.

    Uses keyword matching against the lowercased feedback text.
    Categories are checked in priority order; the first match wins.
    If no keywords match, defaults to COMPLETE_REDO.

    Input is truncated to ``_MAX_FEEDBACK_INPUT`` characters as a
    defense-in-depth measure against oversized input.

    Args:
        feedback: User feedback text (may be empty or whitespace).

    Returns:
        The matched FeedbackCategory, or COMPLETE_REDO as default.
    """
    lowered = feedback[:_MAX_FEEDBACK_INPUT].lower().strip()
    for category, keywords in _CATEGORY_KEYWORDS:
        for keyword in keywords:
            if keyword in lowered:
                return category
    return FeedbackCategory.COMPLETE_REDO


# =============================================================================
# Record Creation
# =============================================================================


def create_outcome_record(
    *,
    generation_id: str,
    outcome: GenerationOutcome,
    feedback: str | None = None,
    regeneration_reason: str | None = None,
) -> GenerationOutcomeRecord:
    """Create a structured generation outcome record.

    REQ-010 §10.2: Builds a record capturing the user's action after
    content generation. If feedback is provided, it is automatically
    categorized via keyword matching.

    Args:
        generation_id: ID of the content generation.
        outcome: What the user did (approved, regenerated, abandoned).
        feedback: Optional user feedback text to categorize.
        regeneration_reason: Optional free-text reason for regeneration.

    Returns:
        Frozen GenerationOutcomeRecord for quality metric tracking.
    """
    # Defense-in-depth: truncate oversized inputs
    bounded_id = generation_id[:_MAX_GENERATION_ID_LENGTH]
    feedback_category = categorize_feedback(feedback) if feedback else None
    bounded_reason = (
        regeneration_reason[:_MAX_REASON_LENGTH]
        if regeneration_reason is not None
        else None
    )

    return GenerationOutcomeRecord(
        generation_id=bounded_id,
        outcome=outcome,
        feedback_category=feedback_category,
        regeneration_reason=bounded_reason,
    )
