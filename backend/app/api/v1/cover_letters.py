"""Cover Letters API router.

REQ-006 §5.2: Cover letter management.
REQ-014 §5.2: Ownership verification via JOIN through persona.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CurrentUserId, DbSession
from app.core.errors import NotFoundError
from app.core.responses import DataResponse, ListResponse, PaginationMeta
from app.models import Persona
from app.models.cover_letter import CoverLetter

_MAX_TEXT_LENGTH = 50000
"""Safety bound on text field lengths (defense-in-depth)."""

_STATUS_APPROVED = "Approved"
"""Status constant for approved cover letters."""

_STATUS_ARCHIVED = "Archived"
"""Status constant for archived cover letters."""

_MAX_STORIES_COUNT = 50
"""Maximum number of achievement story references per cover letter."""

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class CreateCoverLetterRequest(BaseModel):
    """Request body for creating a cover letter.

    REQ-006 §5.2: Required fields for cover letter creation.
    """

    model_config = ConfigDict(extra="forbid")

    persona_id: uuid.UUID
    job_posting_id: uuid.UUID
    draft_text: str = Field(..., min_length=1, max_length=_MAX_TEXT_LENGTH)
    achievement_stories_used: list[str] = Field(
        default=[], max_length=_MAX_STORIES_COUNT
    )
    agent_reasoning: str | None = Field(default=None, max_length=_MAX_TEXT_LENGTH)


class UpdateCoverLetterRequest(BaseModel):
    """Request body for partially updating a cover letter.

    All fields optional — only provided fields are updated.
    """

    model_config = ConfigDict(extra="forbid")

    draft_text: str | None = Field(
        default=None, min_length=1, max_length=_MAX_TEXT_LENGTH
    )
    final_text: str | None = Field(
        default=None, min_length=1, max_length=_MAX_TEXT_LENGTH
    )
    status: str | None = Field(default=None, pattern="^(Draft|Approved|Archived)$")
    agent_reasoning: str | None = Field(default=None, max_length=_MAX_TEXT_LENGTH)
    achievement_stories_used: list[str] | None = Field(
        default=None, max_length=_MAX_STORIES_COUNT
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _cover_letter_to_dict(cl: CoverLetter) -> dict:
    """Convert CoverLetter model to API response dict.

    Args:
            cl: The CoverLetter model instance.

    Returns:
            Dict with cover letter data for API response.
    """
    return {
        "id": str(cl.id),
        "persona_id": str(cl.persona_id),
        "job_posting_id": str(cl.job_posting_id),
        "application_id": str(cl.application_id) if cl.application_id else None,
        "draft_text": cl.draft_text,
        "final_text": cl.final_text,
        "status": cl.status,
        "achievement_stories_used": cl.achievement_stories_used,
        "agent_reasoning": cl.agent_reasoning,
        "approved_at": cl.approved_at.isoformat() if cl.approved_at else None,
        "created_at": cl.created_at.isoformat(),
        "updated_at": cl.updated_at.isoformat(),
        "archived_at": cl.archived_at.isoformat() if cl.archived_at else None,
    }


async def _get_owned_cover_letter(
    cover_letter_id: uuid.UUID, user_id: uuid.UUID, db: DbSession
) -> CoverLetter:
    """Fetch a cover letter with ownership verification.

    REQ-014 §5.2: JOIN through persona for tenant isolation.

    Args:
            cover_letter_id: The cover letter ID to look up.
            user_id: Current authenticated user ID.
            db: Database session.

    Returns:
            CoverLetter owned by the user.

    Raises:
            NotFoundError: If cover letter not found or not owned by user.
    """
    result = await db.execute(
        select(CoverLetter)
        .join(Persona, CoverLetter.persona_id == Persona.id)
        .where(CoverLetter.id == cover_letter_id, Persona.user_id == user_id)
    )
    cl = result.scalar_one_or_none()
    if not cl:
        raise NotFoundError("CoverLetter", str(cover_letter_id))
    return cl


# =============================================================================
# Endpoints
# =============================================================================


@router.get("")
async def list_cover_letters(
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List cover letters for current user.

    REQ-014 §5.4: Scoped to authenticated user via persona JOIN.

    Args:
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            ListResponse with cover letters and pagination meta.
    """
    result = await db.execute(
        select(CoverLetter)
        .join(Persona, CoverLetter.persona_id == Persona.id)
        .where(Persona.user_id == user_id)
        .order_by(CoverLetter.created_at.desc())
    )
    letters = result.scalars().all()

    return ListResponse(
        data=[_cover_letter_to_dict(cl) for cl in letters],
        meta=PaginationMeta(total=len(letters), page=1, per_page=len(letters) or 20),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_cover_letter(
    request: CreateCoverLetterRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Create a new cover letter.

    REQ-014 §5.2: Verifies persona ownership before creation.

    Args:
            request: The create request body.
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            DataResponse with created cover letter.

    Raises:
            NotFoundError: If persona or job posting not found or not owned by user.
    """
    # Verify persona ownership
    persona_result = await db.execute(
        select(Persona).where(
            Persona.id == request.persona_id, Persona.user_id == user_id
        )
    )
    if not persona_result.scalar_one_or_none():
        raise NotFoundError("Persona", str(request.persona_id))

    cl = CoverLetter(
        persona_id=request.persona_id,
        job_posting_id=request.job_posting_id,
        draft_text=request.draft_text,
        achievement_stories_used=request.achievement_stories_used,
        agent_reasoning=request.agent_reasoning,
    )
    db.add(cl)
    await db.commit()
    await db.refresh(cl)

    return DataResponse(data=_cover_letter_to_dict(cl))


@router.get("/{cover_letter_id}")
async def get_cover_letter(
    cover_letter_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get a cover letter by ID.

    REQ-014 §5.2: Returns 404 for cross-tenant access.

    Args:
            cover_letter_id: The cover letter ID.
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            DataResponse with cover letter data.

    Raises:
            NotFoundError: If cover letter not found or not owned by user.
    """
    cl = await _get_owned_cover_letter(cover_letter_id, user_id, db)
    return DataResponse(data=_cover_letter_to_dict(cl))


@router.patch("/{cover_letter_id}")
async def update_cover_letter(
    cover_letter_id: uuid.UUID,
    request: UpdateCoverLetterRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Partially update a cover letter.

    REQ-014 §5.2: Returns 404 for cross-tenant access.

    Args:
            cover_letter_id: The cover letter ID.
            request: The update request body (partial fields).
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            DataResponse with updated cover letter.

    Raises:
            NotFoundError: If cover letter not found or not owned by user.
    """
    cl = await _get_owned_cover_letter(cover_letter_id, user_id, db)

    update_data = request.model_dump(exclude_unset=True)

    # Handle status transition to Approved
    if update_data.get("status") == _STATUS_APPROVED and cl.status != _STATUS_APPROVED:
        update_data["approved_at"] = datetime.now(UTC)

    # SECURITY: safe because extra="forbid" restricts to declared fields only
    for field, value in update_data.items():
        setattr(cl, field, value)

    cl.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(cl)

    return DataResponse(data=_cover_letter_to_dict(cl))


@router.delete("/{cover_letter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cover_letter(
    cover_letter_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> Response:
    """Archive a cover letter (soft delete).

    REQ-014 §5.2: Returns 404 for cross-tenant access.

    Args:
            cover_letter_id: The cover letter ID.
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            204 No Content on success.

    Raises:
            NotFoundError: If cover letter not found or not owned by user.
    """
    cl = await _get_owned_cover_letter(cover_letter_id, user_id, db)

    cl.status = _STATUS_ARCHIVED
    cl.archived_at = datetime.now(UTC)
    cl.updated_at = datetime.now(UTC)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
