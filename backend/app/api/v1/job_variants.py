"""Job Variants API router.

REQ-006 §5.2: Job-specific resume variants.
"""

# SECURITY TODO: When implementing stub endpoints, add ownership verification
# using the JOIN pattern from files.py - see docs/plan/security_fix_plan.md F-08

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.core.responses import DataResponse, ListResponse, PaginationMeta

router = APIRouter()


@router.get("")
async def list_job_variants(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List job variants for current user.

    Supports filtering by status, base_resume_id.
    """
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("")
async def create_job_variant(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Create a new job variant."""
    return DataResponse(data={})


@router.get("/{variant_id}")
async def get_job_variant(
    variant_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get a job variant by ID."""
    return DataResponse(data={})


@router.patch("/{variant_id}")
async def update_job_variant(
    variant_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Partially update a job variant."""
    return DataResponse(data={})


@router.delete("/{variant_id}")
async def delete_job_variant(
    variant_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> None:
    """Delete a job variant."""
    return None
