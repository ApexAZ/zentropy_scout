"""Cover Letters API router.

REQ-006 §5.2: Cover letter management.
"""

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.core.responses import DataResponse, ListResponse, PaginationMeta

router = APIRouter()


@router.get("")
async def list_cover_letters(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List cover letters for current user."""
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("")
async def create_cover_letter(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Create a new cover letter."""
    return DataResponse(data={})


@router.get("/{cover_letter_id}")
async def get_cover_letter(
    cover_letter_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get a cover letter by ID."""
    return DataResponse(data={})


@router.patch("/{cover_letter_id}")
async def update_cover_letter(
    cover_letter_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Partially update a cover letter."""
    return DataResponse(data={})


@router.delete("/{cover_letter_id}")
async def delete_cover_letter(
    cover_letter_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> None:
    """Delete a cover letter."""
    return None
