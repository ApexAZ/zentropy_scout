"""Cover letter editing service.

REQ-002b §7.3: User editing workflow for cover letter draft text.

Provides the function to update draft text on a cover letter that is
still in Draft status. Approved cover letters are immutable.

Public API:
- update_cover_letter_draft — replace draft_text on a Draft cover letter
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateError, NotFoundError, ValidationError
from app.models.cover_letter import CoverLetter

# =============================================================================
# Constants
# =============================================================================

_MAX_DRAFT_TEXT_LENGTH: int = 50_000
"""Maximum draft text length (characters). Consistent with cover_letter_output."""

# =============================================================================
# Result Dataclass
# =============================================================================


@dataclass(frozen=True)
class UpdateCoverLetterDraftResult:
    """Result of updating a cover letter draft.

    Attributes:
        cover_letter_id: UUID of the updated cover letter.
        status: Current status after update (always "Draft").
    """

    cover_letter_id: uuid.UUID
    status: str


# =============================================================================
# Public API
# =============================================================================


async def update_cover_letter_draft(
    db: AsyncSession,
    cover_letter_id: uuid.UUID,
    new_draft_text: str,
) -> UpdateCoverLetterDraftResult:
    """Update draft text on a cover letter.

    Only cover letters in Draft status can be edited. Approved and Archived
    cover letters are immutable.

    Args:
        db: Database session.
        cover_letter_id: The cover letter to update.
        new_draft_text: Replacement draft text.

    Returns:
        UpdateCoverLetterDraftResult with cover letter ID and status.

    Raises:
        ValidationError: If new_draft_text is empty, whitespace-only, or exceeds max length.
        NotFoundError: If cover letter does not exist or is soft-deleted.
        InvalidStateError: If cover letter is not in Draft status.
    """
    if not new_draft_text or not new_draft_text.strip():
        raise ValidationError("Draft text must not be empty.")
    if len(new_draft_text) > _MAX_DRAFT_TEXT_LENGTH:
        raise ValidationError(
            f"Draft text exceeds maximum of {_MAX_DRAFT_TEXT_LENGTH} characters."
        )

    cover_letter = await db.get(CoverLetter, cover_letter_id)
    if cover_letter is None:
        raise NotFoundError("CoverLetter", str(cover_letter_id))

    if cover_letter.is_archived:
        raise NotFoundError("CoverLetter", str(cover_letter_id))

    if cover_letter.status != "Draft":
        raise InvalidStateError(
            f"Cover letter must be Draft to edit. "
            f"Current status: '{cover_letter.status}'."
        )

    cover_letter.draft_text = new_draft_text
    cover_letter.updated_at = datetime.now(UTC)
    await db.commit()

    return UpdateCoverLetterDraftResult(
        cover_letter_id=cover_letter.id,
        status=cover_letter.status,
    )
