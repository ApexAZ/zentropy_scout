"""Cover letter output schema.

REQ-010 §5.5: Cover Letter Output Schema.

Defines the GeneratedCoverLetter dataclass — the final output of the cover
letter generation pipeline. Bundles the draft text, agent reasoning, word
count, stories used, and validation result into a single immutable object.

The to_cover_letter_record() method converts the output into a dict that
maps directly to the CoverLetter ORM model (REQ-005 §4.3) for database
persistence.

Flow:
    generate_cover_letter() -> CoverLetterResult (§5.3)
    validate_cover_letter() -> CoverLetterValidation (§5.4)
    -> GeneratedCoverLetter (§5.5, this module)
    -> to_cover_letter_record() -> dict for ORM insert
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.services.cover_letter_validation import CoverLetterValidation

# =============================================================================
# Constants
# =============================================================================

_MAX_DRAFT_LENGTH: int = 50_000
"""Maximum character length for draft text (matches §5.4 validation)."""

_MAX_REASONING_LENGTH: int = 10_000
"""Maximum character length for agent reasoning."""

_MAX_STORIES: int = 50
"""Maximum number of achievement stories referenced."""

_INITIAL_STATUS: str = "Draft"
"""Initial status for a newly generated cover letter."""


# =============================================================================
# Output Schema
# =============================================================================


@dataclass(frozen=True)
class GeneratedCoverLetter:
    """Output from cover letter generation pipeline.

    Bundles draft text with validation results for downstream consumption.
    Frozen to prevent mutation after construction.

    Attributes:
        draft_text: The generated cover letter text (plain text).
        agent_reasoning: 2-3 sentence explanation of story/emphasis choices.
        word_count: Word count of the draft (target 250-350 per §5.1).
        stories_used: Achievement story UUIDs referenced in the letter.
        validation: Result of automated validation (§5.4).

    Raises:
        ValueError: If input sizes exceed safety bounds.
    """

    draft_text: str
    agent_reasoning: str
    word_count: int
    stories_used: tuple[UUID, ...]
    validation: CoverLetterValidation

    def __post_init__(self) -> None:
        """Validate safety bounds on construction."""
        if len(self.draft_text) > _MAX_DRAFT_LENGTH:
            raise ValueError(
                f"draft_text has {len(self.draft_text)} characters, "
                f"exceeds maximum of {_MAX_DRAFT_LENGTH}"
            )
        if len(self.agent_reasoning) > _MAX_REASONING_LENGTH:
            raise ValueError(
                f"agent_reasoning has {len(self.agent_reasoning)} characters, "
                f"exceeds maximum of {_MAX_REASONING_LENGTH}"
            )
        if self.word_count < 0:
            raise ValueError(f"word_count is {self.word_count}, must be non-negative")
        if len(self.stories_used) > _MAX_STORIES:
            raise ValueError(
                f"stories_used has {len(self.stories_used)} items, "
                f"exceeds maximum of {_MAX_STORIES}"
            )

    def to_cover_letter_record(
        self,
        persona_id: UUID,
        job_posting_id: UUID,
    ) -> dict[str, Any]:
        """Convert to database record format for CoverLetter ORM model.

        Creates a dict suitable for inserting into the cover_letters table.
        Generates a fresh UUID and UTC timestamps. Sets status to 'Draft'
        and final_text to None (set on user approval).

        Note:
            Uses Any for values because the dict contains mixed types
            (UUID, str, None, list, datetime). ORM columns application_id,
            approved_at, and archived_at are intentionally omitted — they
            are lifecycle fields managed by separate workflows.

        Args:
            persona_id: The persona this cover letter belongs to.
            job_posting_id: The job posting this letter targets.

        Returns:
            Dict with keys matching CoverLetter ORM model columns.
        """
        now = datetime.now(UTC)
        return {
            "id": uuid4(),
            "persona_id": persona_id,
            "job_posting_id": job_posting_id,
            "achievement_stories_used": [str(u) for u in self.stories_used],
            "draft_text": self.draft_text,
            "final_text": None,
            "status": _INITIAL_STATUS,
            "agent_reasoning": self.agent_reasoning,
            "created_at": now,
            "updated_at": now,
        }
