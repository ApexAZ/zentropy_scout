"""Job Postings API router.

REQ-006 §5.2: Job postings resource with nested and action endpoints.

Endpoints:
- /job-postings - CRUD for job postings
- /job-postings/{id}/extracted-skills - Read-only extracted skills
- /job-postings/ingest - POST raw job text for parsing (Chrome extension)
- /job-postings/bulk-dismiss - Bulk dismiss jobs
- /job-postings/bulk-favorite - Bulk favorite/unfavorite jobs
- /job-postings/rescore - Re-run Strategist scoring
"""

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.core.responses import DataResponse, ListResponse

router = APIRouter()


# =============================================================================
# Job Postings CRUD
# =============================================================================


@router.get("")
async def list_job_postings(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List job postings for current user.

    Supports filtering by status, is_favorite, fit_score_min, company_name.
    Supports sorting by fit_score, created_at, etc.
    """
    return ListResponse(data=[], meta={"total": 0, "page": 1, "per_page": 20})


@router.post("")
async def create_job_posting(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Create a new job posting manually."""
    return DataResponse(data={})


@router.get("/{job_posting_id}")
async def get_job_posting(
    job_posting_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get a job posting by ID."""
    return DataResponse(data={})


@router.patch("/{job_posting_id}")
async def update_job_posting(
    job_posting_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Partially update a job posting."""
    return DataResponse(data={})


@router.delete("/{job_posting_id}")
async def delete_job_posting(
    job_posting_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> None:
    """Delete a job posting (soft delete)."""
    return None


# =============================================================================
# Extracted Skills (nested, read-only)
# =============================================================================


@router.get("/{job_posting_id}/extracted-skills")
async def list_extracted_skills(
    job_posting_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List skills extracted from job posting by Scouter.

    REQ-006 §5.2: Read-only for clients, populated by Scouter agent.
    """
    return ListResponse(data=[], meta={"total": 0, "page": 1, "per_page": 20})


# =============================================================================
# Action Endpoints
# =============================================================================


@router.post("/ingest")
async def ingest_job_posting(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Ingest raw job posting text from Chrome extension.

    REQ-006 §5.6: Chrome extension submits raw job text for parsing.
    """
    return DataResponse(data={"status": "processing"})


@router.post("/bulk-dismiss")
async def bulk_dismiss_job_postings(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Bulk dismiss multiple job postings.

    REQ-006 §2.6: Bulk operations for efficiency.
    """
    return DataResponse(data={"dismissed_count": 0})


@router.post("/bulk-favorite")
async def bulk_favorite_job_postings(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Bulk favorite/unfavorite multiple job postings.

    REQ-006 §2.6: Bulk operations for efficiency.
    """
    return DataResponse(data={"updated_count": 0})


@router.post("/rescore")
async def rescore_job_postings(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Re-run Strategist scoring on all Discovered jobs.

    REQ-006 §5.2: Trigger after persona changes to update fit scores.
    """
    return DataResponse(data={"status": "queued"})
