"""Applications API router.

REQ-006 §5.2: Application tracking with timeline.
"""

# SECURITY TODO: When implementing stub endpoints, add ownership verification
# using the JOIN pattern from files.py - see docs/plan/security_fix_plan.md F-08

import uuid

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserId
from app.core.responses import (
    DataResponse,
    ErrorDetail,
    ErrorResponse,
    ListResponse,
    PaginationMeta,
)
from app.schemas.bulk import BulkArchiveRequest, BulkFailedItem, BulkOperationResult

router = APIRouter()


# =============================================================================
# Applications CRUD
# =============================================================================


@router.get("")
async def list_applications(
    _user_id: CurrentUserId,
) -> ListResponse[dict]:
    """List applications for current user.

    Supports filtering by status, applied_after, applied_before.
    """
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("")
async def create_application(
    _user_id: CurrentUserId,
) -> DataResponse[dict]:
    """Create a new application."""
    return DataResponse(data={})


@router.get("/{application_id}")
async def get_application(
    application_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> DataResponse[dict]:
    """Get an application by ID."""
    return DataResponse(data={})


@router.patch("/{application_id}")
async def update_application(
    application_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> DataResponse[dict]:
    """Partially update an application."""
    return DataResponse(data={})


@router.delete("/{application_id}")
async def delete_application(
    application_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> None:
    """Delete an application (soft delete)."""
    return None


# =============================================================================
# Timeline (nested resource)
# =============================================================================


@router.get("/{application_id}/timeline")
async def list_timeline_events(
    application_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> ListResponse[dict]:
    """List timeline events for an application."""
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("/{application_id}/timeline")
async def create_timeline_event(
    application_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> DataResponse[dict]:
    """Add a timeline event to an application."""
    return DataResponse(data={})


@router.get("/{application_id}/timeline/{event_id}")
async def get_timeline_event(
    application_id: uuid.UUID,  # noqa: ARG001
    event_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> DataResponse[dict]:
    """Get a timeline event by ID."""
    return DataResponse(data={})


_TIMELINE_IMMUTABLE_RESPONSE = ErrorResponse(
    error=ErrorDetail(
        code="METHOD_NOT_ALLOWED",
        message="Timeline events are immutable. Add a new event instead.",
    ),
)


@router.patch("/{application_id}/timeline/{event_id}")
async def update_timeline_event(
    application_id: uuid.UUID,  # noqa: ARG001
    event_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> JSONResponse:
    """Reject timeline event updates.

    REQ-004 §9: Timeline events are immutable — once created, they
    cannot be edited or deleted.

    Returns:
        405 Method Not Allowed with error envelope.
    """
    return JSONResponse(
        status_code=405,
        content=_TIMELINE_IMMUTABLE_RESPONSE.model_dump(),
    )


@router.delete("/{application_id}/timeline/{event_id}")
async def delete_timeline_event(
    application_id: uuid.UUID,  # noqa: ARG001
    event_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> JSONResponse:
    """Reject timeline event deletion.

    REQ-004 §9: Timeline events are immutable — once created, they
    cannot be edited or deleted.

    Returns:
        405 Method Not Allowed with error envelope.
    """
    return JSONResponse(
        status_code=405,
        content=_TIMELINE_IMMUTABLE_RESPONSE.model_dump(),
    )


# =============================================================================
# Bulk Operations
# =============================================================================


@router.post("/bulk-archive")
async def bulk_archive_applications(
    request: BulkArchiveRequest,
    _user_id: CurrentUserId,
) -> DataResponse[BulkOperationResult]:
    """Bulk archive multiple applications.

    REQ-006 §2.6: Bulk operations for efficiency.

    Args:
        request: List of application IDs to archive.

    Returns:
        Partial success result with succeeded and failed arrays.

    Raises:
        HTTPException: 400 if request validation fails (invalid UUIDs).
        HTTPException: 401 if user is not authenticated.
    """
    # For empty request, return empty result
    if not request.ids:
        return DataResponse(data=BulkOperationResult())

    # For now, report all IDs as NOT_FOUND (no DB implementation yet)
    result = BulkOperationResult(
        succeeded=[],
        failed=[BulkFailedItem(id=str(id_), error="NOT_FOUND") for id_ in request.ids],
    )
    return DataResponse(data=result)
