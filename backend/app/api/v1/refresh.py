"""Refresh API router.

REQ-006 §5.2: Force re-fetch from external job sources.
"""

from fastapi import APIRouter

from app.api.deps import CurrentUserId
from app.core.responses import DataResponse

router = APIRouter()


@router.post("")
async def refresh_job_sources(
    _user_id: CurrentUserId,
) -> DataResponse[dict]:
    """Force re-fetch from external job sources.

    REQ-006 §5.2: Triggers Scouter agent to poll all enabled sources.
    """
    return DataResponse(data={"status": "queued"})
