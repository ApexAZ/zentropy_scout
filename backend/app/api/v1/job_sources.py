"""Job Sources API router.

REQ-006 §5.2: System-managed job sources (read-only).
"""

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.core.responses import DataResponse, ListResponse

router = APIRouter()


@router.get("")
async def list_job_sources(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List available job sources.

    REQ-006 §5.2: System-managed, users can only toggle preferences.
    """
    return ListResponse(data=[], meta={"total": 0, "page": 1, "per_page": 20})


@router.get("/{source_id}")
async def get_job_source(
    source_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get a job source by ID."""
    return DataResponse(data={})
