"""Persona Change Flags API router.

REQ-006 §5.2, §5.4: HITL sync for persona changes.
"""

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.core.responses import DataResponse, ListResponse

router = APIRouter()


@router.get("")
async def list_persona_change_flags(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List pending persona change flags.

    REQ-006 §5.4: Supports filtering by status=Pending.
    """
    return ListResponse(data=[], meta={"total": 0, "page": 1, "per_page": 20})


@router.get("/{flag_id}")
async def get_persona_change_flag(
    flag_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get a persona change flag by ID."""
    return DataResponse(data={})


@router.patch("/{flag_id}")
async def update_persona_change_flag(
    flag_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Update a persona change flag (approve/dismiss).

    REQ-006 §5.4: HITL sync - user approves or dismisses suggested changes.
    """
    return DataResponse(data={})
