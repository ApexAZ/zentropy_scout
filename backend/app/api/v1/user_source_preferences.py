"""User Source Preferences API router.

REQ-006 §5.2: Per-user job source settings (read/update only).
"""

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.core.responses import DataResponse, ListResponse

router = APIRouter()


@router.get("")
async def list_user_source_preferences(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List user's job source preferences."""
    return ListResponse(data=[], meta={"total": 0, "page": 1, "per_page": 20})


@router.get("/{preference_id}")
async def get_user_source_preference(
    preference_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get a user source preference by ID."""
    return DataResponse(data={})


@router.patch("/{preference_id}")
async def update_user_source_preference(
    preference_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Update a user source preference (enable/disable source)."""
    return DataResponse(data={})
