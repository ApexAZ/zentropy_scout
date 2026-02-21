"""Applications API router.

REQ-006 §5.2: Application tracking with timeline.
REQ-014 §5.2: Ownership verification via JOIN through persona.

NOTE: This file exceeds 300 lines because it serves three logical sub-resources
(Application CRUD, Timeline events, Bulk operations) that share the
`_get_owned_application()` ownership helper. Splitting would fragment cohesion.
"""

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from app.api.deps import CurrentUserId, DbSession
from app.core.errors import NotFoundError
from app.core.responses import (
    DataResponse,
    ErrorDetail,
    ErrorResponse,
    ListResponse,
    PaginationMeta,
)
from app.models import Persona
from app.models.application import Application, TimelineEvent
from app.schemas.bulk import BulkArchiveRequest, BulkFailedItem, BulkOperationResult

_MAX_TEXT_LENGTH = 50000
"""Safety bound on text field lengths (defense-in-depth)."""

_MAX_JSON_SIZE = 65536
"""Safety bound on JSONB field serialized size (64 KB, defense-in-depth)."""

_INTERVIEW_STAGE_PATTERN = "^(Phone Screen|Onsite|Final Round)$"
"""Regex for valid interview stages (shared between schemas)."""

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class CreateApplicationRequest(BaseModel):
    """Request body for creating an application.

    REQ-006 §5.2: Required fields for application creation.
    """

    model_config = ConfigDict(extra="forbid")

    persona_id: uuid.UUID
    job_posting_id: uuid.UUID
    job_variant_id: uuid.UUID
    cover_letter_id: uuid.UUID | None = None
    job_snapshot: dict
    notes: str | None = Field(default=None, max_length=_MAX_TEXT_LENGTH)

    @field_validator("job_snapshot")
    @classmethod
    def validate_snapshot_size(cls, v: dict) -> dict:
        """Defense-in-depth: cap JSONB payload size."""
        if len(json.dumps(v)) > _MAX_JSON_SIZE:
            msg = f"job_snapshot exceeds maximum size of {_MAX_JSON_SIZE} bytes"
            raise ValueError(msg)
        return v


class UpdateApplicationRequest(BaseModel):
    """Request body for partially updating an application.

    All fields optional — only provided fields are updated.
    """

    model_config = ConfigDict(extra="forbid")

    status: str | None = Field(
        default=None,
        pattern="^(Applied|Interviewing|Offer|Accepted|Rejected|Withdrawn)$",
    )
    current_interview_stage: str | None = Field(
        default=None,
        pattern=_INTERVIEW_STAGE_PATTERN,
    )
    notes: str | None = Field(default=None, max_length=_MAX_TEXT_LENGTH)
    offer_details: dict | None = None
    rejection_details: dict | None = None
    is_pinned: bool | None = None

    @field_validator("offer_details", "rejection_details")
    @classmethod
    def validate_json_size(cls, v: dict | None) -> dict | None:
        """Defense-in-depth: cap JSONB payload size."""
        if v is not None and len(json.dumps(v)) > _MAX_JSON_SIZE:
            msg = f"Field exceeds maximum size of {_MAX_JSON_SIZE} bytes"
            raise ValueError(msg)
        return v


class CreateTimelineEventRequest(BaseModel):
    """Request body for creating a timeline event.

    REQ-004 §9: Timeline events are immutable once created.
    """

    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(
        ...,
        pattern="^(applied|status_changed|note_added|interview_scheduled|"
        "interview_completed|offer_received|offer_accepted|rejected|withdrawn|"
        "follow_up_sent|response_received|custom)$",
    )
    event_date: datetime
    description: str | None = Field(default=None, max_length=_MAX_TEXT_LENGTH)
    interview_stage: str | None = Field(
        default=None,
        pattern=_INTERVIEW_STAGE_PATTERN,
    )


# =============================================================================
# Helper Functions
# =============================================================================


def _application_to_dict(app: Application) -> dict:
    """Convert Application model to API response dict.

    Args:
            app: The Application model instance.

    Returns:
            Dict with application data for API response.
    """
    return {
        "id": str(app.id),
        "persona_id": str(app.persona_id),
        "job_posting_id": str(app.job_posting_id),
        "job_variant_id": str(app.job_variant_id),
        "cover_letter_id": str(app.cover_letter_id) if app.cover_letter_id else None,
        "submitted_resume_pdf_id": (
            str(app.submitted_resume_pdf_id) if app.submitted_resume_pdf_id else None
        ),
        "submitted_cover_letter_pdf_id": (
            str(app.submitted_cover_letter_pdf_id)
            if app.submitted_cover_letter_pdf_id
            else None
        ),
        "job_snapshot": app.job_snapshot,
        "status": app.status,
        "current_interview_stage": app.current_interview_stage,
        "offer_details": app.offer_details,
        "rejection_details": app.rejection_details,
        "notes": app.notes,
        "is_pinned": app.is_pinned,
        "applied_at": app.applied_at.isoformat(),
        "status_updated_at": app.status_updated_at.isoformat(),
        "created_at": app.created_at.isoformat(),
        "updated_at": app.updated_at.isoformat(),
        "archived_at": app.archived_at.isoformat() if app.archived_at else None,
    }


def _timeline_event_to_dict(event: TimelineEvent) -> dict:
    """Convert TimelineEvent model to API response dict.

    Args:
            event: The TimelineEvent model instance.

    Returns:
            Dict with timeline event data for API response.
    """
    return {
        "id": str(event.id),
        "application_id": str(event.application_id),
        "event_type": event.event_type,
        "event_date": event.event_date.isoformat(),
        "description": event.description,
        "interview_stage": event.interview_stage,
        "created_at": event.created_at.isoformat(),
    }


async def _get_owned_application(
    application_id: uuid.UUID, user_id: uuid.UUID, db: DbSession
) -> Application:
    """Fetch an application with ownership verification.

    REQ-014 §5.2: JOIN through persona for tenant isolation.

    Args:
            application_id: The application ID to look up.
            user_id: Current authenticated user ID.
            db: Database session.

    Returns:
            Application owned by the user.

    Raises:
            NotFoundError: If application not found or not owned by user.
    """
    result = await db.execute(
        select(Application)
        .join(Persona, Application.persona_id == Persona.id)
        .where(Application.id == application_id, Persona.user_id == user_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise NotFoundError("Application", str(application_id))
    return app


# =============================================================================
# Applications CRUD
# =============================================================================


@router.get("")
async def list_applications(
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List applications for current user.

    REQ-014 §5.4: Scoped to authenticated user via persona JOIN.
    Supports filtering by status, applied_after, applied_before.

    Note:
            Archived applications (archived_at IS NOT NULL) are included by default.
            Client-side filtering can exclude them if needed.

    Args:
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            ListResponse with applications and pagination meta.
    """
    # NOTE: includes archived records; client filters as needed
    result = await db.execute(
        select(Application)
        .join(Persona, Application.persona_id == Persona.id)
        .where(Persona.user_id == user_id)
        .order_by(Application.applied_at.desc())
    )
    apps = result.scalars().all()

    return ListResponse(
        data=[_application_to_dict(a) for a in apps],
        meta=PaginationMeta(total=len(apps), page=1, per_page=len(apps) or 20),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_application(
    request: CreateApplicationRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Create a new application.

    REQ-014 §5.2: Verifies persona ownership before creation.

    Args:
            request: The create request body.
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            DataResponse with created application.

    Raises:
            NotFoundError: If persona not found or not owned by user.
    """
    # Verify persona ownership
    persona_result = await db.execute(
        select(Persona).where(
            Persona.id == request.persona_id, Persona.user_id == user_id
        )
    )
    if not persona_result.scalar_one_or_none():
        raise NotFoundError("Persona", str(request.persona_id))

    app = Application(
        persona_id=request.persona_id,
        job_posting_id=request.job_posting_id,
        job_variant_id=request.job_variant_id,
        cover_letter_id=request.cover_letter_id,
        job_snapshot=request.job_snapshot,
        notes=request.notes,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)

    return DataResponse(data=_application_to_dict(app))


@router.get("/{application_id}")
async def get_application(
    application_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get an application by ID.

    REQ-014 §5.2: Returns 404 for cross-tenant access.

    Args:
            application_id: The application ID.
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            DataResponse with application data.

    Raises:
            NotFoundError: If application not found or not owned by user.
    """
    app = await _get_owned_application(application_id, user_id, db)
    return DataResponse(data=_application_to_dict(app))


@router.patch("/{application_id}")
async def update_application(
    application_id: uuid.UUID,
    request: UpdateApplicationRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Partially update an application.

    REQ-014 §5.2: Returns 404 for cross-tenant access.

    Args:
            application_id: The application ID.
            request: The update request body (partial fields).
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            DataResponse with updated application.

    Raises:
            NotFoundError: If application not found or not owned by user.
    """
    app = await _get_owned_application(application_id, user_id, db)

    update_data = request.model_dump(exclude_unset=True)

    # Update status_updated_at when status changes
    if "status" in update_data and update_data["status"] != app.status:
        app.status_updated_at = datetime.now(UTC)

    # SECURITY: safe because extra="forbid" restricts to declared fields only
    for field, value in update_data.items():
        setattr(app, field, value)

    app.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(app)

    return DataResponse(data=_application_to_dict(app))


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> Response:
    """Archive an application (soft delete).

    REQ-014 §5.2: Returns 404 for cross-tenant access.

    Args:
            application_id: The application ID.
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            204 No Content on success.

    Raises:
            NotFoundError: If application not found or not owned by user.
    """
    app = await _get_owned_application(application_id, user_id, db)

    app.archived_at = datetime.now(UTC)
    app.updated_at = datetime.now(UTC)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# Timeline (nested resource)
# =============================================================================


@router.get("/{application_id}/timeline")
async def list_timeline_events(
    application_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List timeline events for an application.

    REQ-014 §5.2: Verifies application ownership first.

    Args:
            application_id: The parent application ID.
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            ListResponse with timeline events.

    Raises:
            NotFoundError: If application not found or not owned by user.
    """
    await _get_owned_application(application_id, user_id, db)

    result = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.application_id == application_id)
        .order_by(TimelineEvent.event_date.desc())
    )
    events = result.scalars().all()

    return ListResponse(
        data=[_timeline_event_to_dict(e) for e in events],
        meta=PaginationMeta(total=len(events), page=1, per_page=len(events) or 20),
    )


@router.post("/{application_id}/timeline", status_code=status.HTTP_201_CREATED)
async def create_timeline_event(
    application_id: uuid.UUID,
    request: CreateTimelineEventRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Add a timeline event to an application.

    REQ-004 §9: Timeline events are immutable once created.
    REQ-014 §5.2: Verifies application ownership first.

    Args:
            application_id: The parent application ID.
            request: The timeline event data.
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            DataResponse with created timeline event.

    Raises:
            NotFoundError: If application not found or not owned by user.
    """
    await _get_owned_application(application_id, user_id, db)

    event = TimelineEvent(
        application_id=application_id,
        event_type=request.event_type,
        event_date=request.event_date,
        description=request.description,
        interview_stage=request.interview_stage,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    return DataResponse(data=_timeline_event_to_dict(event))


@router.get("/{application_id}/timeline/{event_id}")
async def get_timeline_event(
    application_id: uuid.UUID,
    event_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get a timeline event by ID.

    REQ-014 §5.2: Verifies application ownership first.

    Args:
            application_id: The parent application ID.
            event_id: The timeline event ID.
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            DataResponse with timeline event data.

    Raises:
            NotFoundError: If application or event not found, or not owned by user.
    """
    await _get_owned_application(application_id, user_id, db)

    result = await db.execute(
        select(TimelineEvent).where(
            TimelineEvent.id == event_id,
            TimelineEvent.application_id == application_id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise NotFoundError("TimelineEvent", str(event_id))

    return DataResponse(data=_timeline_event_to_dict(event))


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
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[BulkOperationResult]:
    """Bulk archive multiple applications.

    REQ-006 §2.6: Bulk operations for efficiency.
    REQ-014 §5.2: Each item individually verified for ownership.

    Args:
            request: List of application IDs to archive.
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            Partial success result with succeeded and failed arrays.
    """
    if not request.ids:
        return DataResponse(data=BulkOperationResult())

    succeeded: list[str] = []
    failed: list[BulkFailedItem] = []

    for app_id in request.ids:
        result = await db.execute(
            select(Application)
            .join(Persona, Application.persona_id == Persona.id)
            .where(Application.id == app_id, Persona.user_id == user_id)
        )
        app = result.scalar_one_or_none()

        if not app:
            failed.append(BulkFailedItem(id=str(app_id), error="NOT_FOUND"))
            continue

        app.archived_at = datetime.now(UTC)
        app.updated_at = datetime.now(UTC)
        succeeded.append(str(app_id))

    await db.commit()

    return DataResponse(data=BulkOperationResult(succeeded=succeeded, failed=failed))
