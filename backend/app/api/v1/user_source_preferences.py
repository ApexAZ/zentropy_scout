"""User Source Preferences API router.

REQ-006 §5.2: Per-user job source settings (read/update only).
"""

# SECURITY TODO: When implementing stub endpoints, add ownership verification
# using the JOIN pattern from files.py - see docs/plan/security_fix_plan.md F-08

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUserId
from app.core.responses import DataResponse, ListResponse

router = APIRouter()


@router.get("")
async def list_user_source_preferences(
    _user_id: CurrentUserId,
) -> ListResponse[dict]:
    """List user's job source preferences."""
    return ListResponse(data=[], meta={"total": 0, "page": 1, "per_page": 20})


@router.get("/{preference_id}")
async def get_user_source_preference(
    preference_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> DataResponse[dict]:
    """Get a user source preference by ID."""
    return DataResponse(data={})


@router.patch("/{preference_id}")
async def update_user_source_preference(
    preference_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> DataResponse[dict]:
    """Update a user source preference (enable/disable source)."""
    return DataResponse(data={})
