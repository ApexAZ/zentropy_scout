"""Base Resumes API router.

REQ-006 §5.2: Base resumes filtered by current user's persona.
"""

import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import CurrentUserId, DbSession
from app.core.errors import NotFoundError
from app.core.file_validation import sanitize_filename_for_header
from app.core.responses import DataResponse, ListResponse, PaginationMeta
from app.models import BaseResume, Persona

router = APIRouter()


@router.get("")
async def list_base_resumes(
    _user_id: CurrentUserId,
) -> ListResponse[dict]:
    """List base resumes for current user."""
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("")
async def create_base_resume(
    _user_id: CurrentUserId,
) -> DataResponse[dict]:
    """Create a new base resume."""
    return DataResponse(data={})


@router.get("/{resume_id}")
async def get_base_resume(
    resume_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> DataResponse[dict]:
    """Get a base resume by ID."""
    return DataResponse(data={})


@router.patch("/{resume_id}")
async def update_base_resume(
    resume_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> DataResponse[dict]:
    """Partially update a base resume."""
    return DataResponse(data={})


@router.delete("/{resume_id}")
async def delete_base_resume(
    resume_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> None:
    """Delete a base resume."""
    return None


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
    # Query base resume with ownership check
    result = await db.execute(
        select(BaseResume)
        .join(Persona, BaseResume.persona_id == Persona.id)
        .where(BaseResume.id == resume_id, Persona.user_id == user_id)
    )
    base_resume = result.scalar_one_or_none()

    if not base_resume:
        raise NotFoundError("BaseResume", str(resume_id))

    if not base_resume.rendered_document:
        raise NotFoundError("BaseResume", str(resume_id))

    # Security: sanitize filename to prevent header injection
    safe_filename = sanitize_filename_for_header(
        f"{base_resume.name.replace(' ', '_')}.pdf"
    )

    return StreamingResponse(
        iter([base_resume.rendered_document]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )
