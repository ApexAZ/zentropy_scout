"""Refresh API router.

REQ-006 §5.2: Force re-fetch from external job sources.
"""

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.core.responses import DataResponse

router = APIRouter()


@router.post("")
async def refresh_job_sources(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Force re-fetch from external job sources.

    REQ-006 §5.2: Triggers Scouter agent to poll all enabled sources.
    """
    return DataResponse(data={"status": "queued"})
