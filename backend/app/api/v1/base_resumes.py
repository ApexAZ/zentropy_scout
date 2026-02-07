"""Base Resumes API router.

REQ-006 §5.2: Base resumes CRUD, filtered by current user's persona.
REQ-002 §4.2: Base Resume — Rendered Document Storage.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserId, DbSession
from app.core.errors import ConflictError, InvalidStateError, NotFoundError
from app.core.file_validation import sanitize_filename_for_header
from app.core.responses import DataResponse, ListResponse, PaginationMeta
from app.models import BaseResume, Persona

_MAX_JSONB_LIST_LENGTH = 200
"""Safety bound on JSONB list field lengths (defense-in-depth)."""

_MAX_SUMMARY_LENGTH = 5000
"""Safety bound on summary text length."""

_STATUS_ACTIVE = "Active"
"""Base resume status: normal state, visible in UI."""

_STATUS_ARCHIVED = "Archived"
"""Base resume status: soft-deleted, hidden from default UI views."""

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class CreateBaseResumeRequest(BaseModel):
    """Request body for creating a base resume.

    REQ-002 §4.2: Required fields for base resume creation.
    """

    model_config = ConfigDict(extra="forbid")

    persona_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=100)
    role_type: str = Field(..., min_length=1, max_length=255)
    summary: str = Field(..., min_length=1, max_length=_MAX_SUMMARY_LENGTH)
    included_jobs: list[str] = Field(default=[], max_length=_MAX_JSONB_LIST_LENGTH)
    included_education: list[str] = Field(default=[], max_length=_MAX_JSONB_LIST_LENGTH)
    included_certifications: list[str] = Field(
        default=[], max_length=_MAX_JSONB_LIST_LENGTH
    )
    skills_emphasis: list[str] = Field(default=[], max_length=_MAX_JSONB_LIST_LENGTH)
    job_bullet_selections: dict[str, list[str]] = Field(default={})
    job_bullet_order: dict[str, list[str]] = Field(default={})
    is_primary: bool = False
    display_order: int = Field(default=0, ge=0, le=10000)


class UpdateBaseResumeRequest(BaseModel):
    """Request body for partially updating a base resume.

    All fields optional — only provided fields are updated.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    role_type: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(
        default=None, min_length=1, max_length=_MAX_SUMMARY_LENGTH
    )
    included_jobs: list[str] | None = Field(
        default=None, max_length=_MAX_JSONB_LIST_LENGTH
    )
    included_education: list[str] | None = Field(
        default=None, max_length=_MAX_JSONB_LIST_LENGTH
    )
    included_certifications: list[str] | None = Field(
        default=None, max_length=_MAX_JSONB_LIST_LENGTH
    )
    skills_emphasis: list[str] | None = Field(
        default=None, max_length=_MAX_JSONB_LIST_LENGTH
    )
    job_bullet_selections: dict[str, list[str]] | None = None
    job_bullet_order: dict[str, list[str]] | None = None
    is_primary: bool | None = None
    display_order: int | None = Field(default=None, ge=0, le=10000)


# =============================================================================
# Helper Functions
# =============================================================================


def _resume_to_dict(resume: BaseResume) -> dict:
    """Convert BaseResume model to API response dict.

    Excludes rendered_document binary — use download endpoint instead.

    Args:
        resume: The BaseResume model instance.

    Returns:
        Dict with resume data for API response.
    """
    return {
        "id": str(resume.id),
        "persona_id": str(resume.persona_id),
        "name": resume.name,
        "role_type": resume.role_type,
        "summary": resume.summary,
        "included_jobs": resume.included_jobs,
        "included_education": resume.included_education,
        "included_certifications": resume.included_certifications,
        "skills_emphasis": resume.skills_emphasis,
        "job_bullet_selections": resume.job_bullet_selections,
        "job_bullet_order": resume.job_bullet_order,
        "rendered_at": resume.rendered_at.isoformat() if resume.rendered_at else None,
        "is_primary": resume.is_primary,
        "status": resume.status,
        "display_order": resume.display_order,
        "created_at": resume.created_at.isoformat(),
        "updated_at": resume.updated_at.isoformat(),
        "archived_at": resume.archived_at.isoformat() if resume.archived_at else None,
    }


async def _get_owned_resume(
    resume_id: uuid.UUID, user_id: uuid.UUID, db: DbSession
) -> BaseResume:
    """Fetch a base resume with ownership verification.

    Args:
        resume_id: The base resume ID to look up.
        user_id: Current authenticated user ID.
        db: Database session.

    Returns:
        BaseResume instance owned by the user.

    Raises:
        NotFoundError: If resume not found or not owned by user.
    """
    result = await db.execute(
        select(BaseResume)
        .join(Persona, BaseResume.persona_id == Persona.id)
        .where(BaseResume.id == resume_id, Persona.user_id == user_id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise NotFoundError("BaseResume", str(resume_id))
    return resume


# =============================================================================
# Endpoints
# =============================================================================


@router.get("")
async def list_base_resumes(
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List base resumes for current user.

    REQ-006 §5.2: Filtered by current user's persona ownership.

    Args:
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        ListResponse with base resumes and pagination meta.
    """
    result = await db.execute(
        select(BaseResume)
        .join(Persona, BaseResume.persona_id == Persona.id)
        .where(Persona.user_id == user_id)
        .order_by(BaseResume.display_order, BaseResume.created_at.desc())
    )
    resumes = result.scalars().all()

    return ListResponse(
        data=[_resume_to_dict(r) for r in resumes],
        meta=PaginationMeta(total=len(resumes), page=1, per_page=len(resumes) or 20),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_base_resume(
    request: CreateBaseResumeRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Create a new base resume.

    REQ-002 §4.2: Creates a base resume linked to a user's persona.

    Args:
        request: The create request body.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with created base resume.

    Raises:
        NotFoundError: If persona not found or not owned by user.
        ConflictError: If name already exists for this persona.
    """
    # Verify persona ownership
    persona_result = await db.execute(
        select(Persona).where(
            Persona.id == request.persona_id, Persona.user_id == user_id
        )
    )
    persona = persona_result.scalar_one_or_none()
    if not persona:
        raise NotFoundError("Persona", str(request.persona_id))

    resume = BaseResume(
        persona_id=request.persona_id,
        name=request.name,
        role_type=request.role_type,
        summary=request.summary,
        included_jobs=request.included_jobs,
        included_education=request.included_education,
        included_certifications=request.included_certifications,
        skills_emphasis=request.skills_emphasis,
        job_bullet_selections=request.job_bullet_selections,
        job_bullet_order=request.job_bullet_order,
        is_primary=request.is_primary,
        display_order=request.display_order,
    )
    db.add(resume)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(
            code="DUPLICATE_NAME",
            message="A base resume with this name already exists for this persona.",
        ) from None

    await db.refresh(resume)
    return DataResponse(data=_resume_to_dict(resume))


@router.get("/{resume_id}")
async def get_base_resume(
    resume_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get a base resume by ID.

    Args:
        resume_id: The base resume ID.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with base resume data.

    Raises:
        NotFoundError: If resume not found or not owned by user.
    """
    resume = await _get_owned_resume(resume_id, user_id, db)
    return DataResponse(data=_resume_to_dict(resume))


@router.patch("/{resume_id}")
async def update_base_resume(
    resume_id: uuid.UUID,
    request: UpdateBaseResumeRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Partially update a base resume.

    Args:
        resume_id: The base resume ID.
        request: The update request body (partial fields).
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with updated base resume.

    Raises:
        NotFoundError: If resume not found or not owned by user.
    """
    resume = await _get_owned_resume(resume_id, user_id, db)

    # Apply only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(resume, field, value)

    resume.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(resume)

    return DataResponse(data=_resume_to_dict(resume))


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_base_resume(
    resume_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> Response:
    """Archive a base resume (soft delete).

    REQ-002 §5.1: Base Resumes are never hard deleted — DELETE archives.

    Args:
        resume_id: The base resume ID.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        204 No Content on success.

    Raises:
        NotFoundError: If resume not found or not owned by user.
    """
    resume = await _get_owned_resume(resume_id, user_id, db)

    resume.status = _STATUS_ARCHIVED
    resume.archived_at = datetime.now(UTC)
    resume.updated_at = datetime.now(UTC)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{resume_id}/restore")
async def restore_base_resume(
    resume_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Restore an archived base resume to Active.

    REQ-002 §5.4: Restore sets status back to Active and clears archived_at.

    Args:
        resume_id: The base resume ID.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with restored base resume.

    Raises:
        NotFoundError: If resume not found or not owned by user.
        InvalidStateError: If resume is not in Archived status.
    """
    resume = await _get_owned_resume(resume_id, user_id, db)

    if resume.status != _STATUS_ARCHIVED:
        raise InvalidStateError("Only archived base resumes can be restored.")

    resume.status = _STATUS_ACTIVE
    resume.archived_at = None
    resume.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(resume)

    return DataResponse(data=_resume_to_dict(resume))


@router.get("/{resume_id}/download")
async def download_base_resume(
    resume_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> StreamingResponse:
    """Download rendered anchor PDF for base resume.

    REQ-006 §5.2, §2.7: File download endpoint.

    Args:
        resume_id: The base resume ID to download.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        StreamingResponse with PDF binary and Content-Disposition header.

    Raises:
        NotFoundError: If resume not found, not owned by user, or no rendered document.
    """
    resume = await _get_owned_resume(resume_id, user_id, db)

    if not resume.rendered_document:
        raise NotFoundError("BaseResume", str(resume_id))

    # Security: sanitize filename to prevent header injection
    safe_filename = sanitize_filename_for_header(f"{resume.name.replace(' ', '_')}.pdf")

    return StreamingResponse(
        iter([resume.rendered_document]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )
