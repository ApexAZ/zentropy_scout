"""Regeneration handling types for the Ghostwriter agent.

REQ-010 §7: When users request regeneration ("try a different approach"),
the system modifies the prompt based on feedback. This module defines
the feedback categories and configuration types used by:
    - §7.2: Feedback sanitization (sanitize_user_feedback)
    - §7.3: Prompt modifier (build_regeneration_context)

Feedback Categories (§7.1):
    STORY_REJECTION  — Exclude story, select next best
    TONE_ADJUSTMENT  — Add tone override to voice block
    LENGTH_ADJUSTMENT — Adjust word count target
    FOCUS_SHIFT      — Add emphasis instruction
    COMPLETE_REDO    — Clear context, regenerate from scratch
"""

from dataclasses import dataclass
from enum import Enum

# =============================================================================
# Constants
# =============================================================================

# WHY: Defense-in-depth limits defined here so both RegenerationConfig
# validation and sanitize_user_feedback (§7.2) reference the same constants.
MAX_FEEDBACK_LENGTH = 500
MAX_TONE_LENGTH = 50
MAX_WORD_COUNT = 5000


# =============================================================================
# Feedback Categories (REQ-010 §7.1)
# =============================================================================


class FeedbackCategory(str, Enum):
    """User feedback categories for regeneration.

    REQ-010 §7.1: Five categories map to specific prompt modifications.
    Inherits from str so values are JSON-serializable and comparable
    as strings (e.g., for state serialization in LangGraph).

    Values:
        STORY_REJECTION: Exclude story, select next best.
        TONE_ADJUSTMENT: Add tone override to voice block.
        LENGTH_ADJUSTMENT: Adjust word count target.
        FOCUS_SHIFT: Add emphasis instruction.
        COMPLETE_REDO: Clear context, regenerate from scratch.
    """

    STORY_REJECTION = "story_rejection"
    """Exclude a story and select next best. Example: "Don't use the failing project story"."""

    TONE_ADJUSTMENT = "tone_adjustment"
    """Add tone override to voice block. Example: "Make it less formal"."""

    LENGTH_ADJUSTMENT = "length_adjustment"
    """Adjust word count target. Example: "Make it shorter"."""

    FOCUS_SHIFT = "focus_shift"
    """Add emphasis instruction. Example: "Focus more on technical skills"."""

    COMPLETE_REDO = "complete_redo"
    """Clear context and regenerate from scratch. Example: "Start fresh"."""


# =============================================================================
# Regeneration Config
# =============================================================================


@dataclass(frozen=True)
class RegenerationConfig:
    """Configuration for a regeneration request.

    Bundles the user's feedback with category-specific overrides.
    Frozen to prevent accidental mutation during prompt building.

    IMPORTANT: ``feedback`` MUST be sanitized via ``sanitize_user_feedback()``
    (REQ-010 §7.2) before prompt insertion. Passing unsanitized feedback to
    an LLM is a security violation.

    Attributes:
        feedback: Raw user feedback text. Must be sanitized before prompt use.
        category: The feedback category determining prompt modification strategy.
        excluded_story_ids: Story IDs to exclude (STORY_REJECTION). Tuple for
            true immutability on a frozen dataclass.
        tone_override: Desired tone adjustment string (TONE_ADJUSTMENT).
            Constrained to MAX_TONE_LENGTH to limit injection surface.
        word_count_target: Min/max word count tuple (LENGTH_ADJUSTMENT).

    Raises:
        ValueError: If feedback exceeds MAX_FEEDBACK_LENGTH, tone_override
            exceeds MAX_TONE_LENGTH, or word_count_target has invalid bounds.
    """

    feedback: str
    category: FeedbackCategory
    excluded_story_ids: tuple[str, ...] | None = None
    tone_override: str | None = None
    word_count_target: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        """Validate field constraints for defense-in-depth."""
        if len(self.feedback) > MAX_FEEDBACK_LENGTH:
            raise ValueError(f"feedback exceeds {MAX_FEEDBACK_LENGTH} characters")

        if self.tone_override is not None and len(self.tone_override) > MAX_TONE_LENGTH:
            raise ValueError(f"tone_override exceeds {MAX_TONE_LENGTH} characters")

        if self.word_count_target is not None:
            lo, hi = self.word_count_target
            if lo < 0 or hi < 0:
                raise ValueError("word_count_target values must be non-negative")
            if lo > hi:
                raise ValueError("word_count_target min must not exceed max")
            if hi > MAX_WORD_COUNT:
                raise ValueError(f"word_count_target max exceeds {MAX_WORD_COUNT}")
