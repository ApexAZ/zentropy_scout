"""Base Resumes API router.

REQ-006 §5.2: Base resumes filtered by current user's persona.
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user_id
from app.core.responses import DataResponse, ListResponse

router = APIRouter()


@router.get("")
async def list_base_resumes(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List base resumes for current user."""
    return ListResponse(data=[], meta={"total": 0, "page": 1, "per_page": 20})


@router.post("")
async def create_base_resume(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Create a new base resume."""
    return DataResponse(data={})


@router.get("/{resume_id}")
async def get_base_resume(
    resume_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get a base resume by ID."""
    return DataResponse(data={})


@router.patch("/{resume_id}")
async def update_base_resume(
    resume_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Partially update a base resume."""
    return DataResponse(data={})


@router.delete("/{resume_id}")
async def delete_base_resume(
    resume_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> None:
    """Delete a base resume."""
    return None


@router.get("/{resume_id}/download")
async def download_base_resume(
    resume_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> StreamingResponse:
    """Download rendered anchor PDF for base resume.

    REQ-006 §5.2, §2.7: File download endpoint.
    """
    # Placeholder - will return PDF from BYTEA column
    return StreamingResponse(
        iter([b""]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=resume.pdf"},
    )
