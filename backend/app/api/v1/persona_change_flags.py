"""Persona Change Flags API router.

REQ-006 §5.2, §5.4: HITL sync for persona changes.

Persona change flags track pending changes to Persona data (new skills, jobs, etc.)
that may need to be synced to BaseResumes. This supports a Human-in-the-Loop (HITL)
workflow where users review and approve changes before they propagate.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUserId, DbSession
from app.core.errors import InvalidStateError, NotFoundError
from app.core.responses import DataResponse, ListResponse, PaginationMeta
from app.models import Persona
from app.models.persona_settings import PersonaChangeFlag

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class ResolveChangeFlagRequest(BaseModel):
    """Request body for resolving a change flag.

    REQ-006 §5.4: Resolve a flag with a resolution decision.
    """

    status: Literal["Resolved"]
    resolution: Literal["added_to_all", "added_to_some", "skipped"]


# =============================================================================
# Helper Functions
# =============================================================================


def _flag_to_dict(flag: PersonaChangeFlag) -> dict:
    """Convert PersonaChangeFlag model to API response dict.

    Args:
        flag: The PersonaChangeFlag model instance.

    Returns:
        Dict with flag data for API response.
    """
    return {
        "id": str(flag.id),
        "persona_id": str(flag.persona_id),
        "change_type": flag.change_type,
        "item_id": str(flag.item_id),
        "item_description": flag.item_description,
        "status": flag.status,
        "resolution": flag.resolution,
        "resolved_at": flag.resolved_at.isoformat() if flag.resolved_at else None,
        "created_at": flag.created_at.isoformat(),
    }


# =============================================================================
# Endpoints
# =============================================================================


StatusFilter = Annotated[
    str | None,
    Query(description="Filter by status (Pending or Resolved)"),
]


@router.get("")
async def list_persona_change_flags(
    user_id: CurrentUserId,
    db: DbSession,
    status: StatusFilter = None,
) -> ListResponse[dict]:
    """List pending persona change flags.

    REQ-006 §5.4: Supports filtering by status=Pending.

    Args:
        user_id: Current authenticated user (injected).
        db: Database session (injected).
        status: Optional filter by status (Pending/Resolved).

    Returns:
        ListResponse with change flags for the user's personas.
    """
    # Build query for user's personas
    query = (
        select(PersonaChangeFlag)
        .join(Persona, PersonaChangeFlag.persona_id == Persona.id)
        .where(Persona.user_id == user_id)
        .order_by(PersonaChangeFlag.created_at.desc())
    )

    # Apply status filter if provided
    if status:
        query = query.where(PersonaChangeFlag.status == status)

    result = await db.execute(query)
    flags = result.scalars().all()

    return ListResponse(
        data=[_flag_to_dict(f) for f in flags],
        meta=PaginationMeta(total=len(flags), page=1, per_page=len(flags)),
    )


@router.get("/{flag_id}")
async def get_persona_change_flag(
    flag_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get a persona change flag by ID.

    Args:
        flag_id: The change flag ID to retrieve.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with flag details.

    Raises:
        NotFoundError: If flag not found or not owned by user.
    """
    result = await db.execute(
        select(PersonaChangeFlag)
        .join(Persona, PersonaChangeFlag.persona_id == Persona.id)
        .where(PersonaChangeFlag.id == flag_id, Persona.user_id == user_id)
    )
    flag = result.scalar_one_or_none()

    if not flag:
        raise NotFoundError("PersonaChangeFlag", str(flag_id))

    return DataResponse(data=_flag_to_dict(flag))


@router.patch("/{flag_id}")
async def update_persona_change_flag(
    flag_id: uuid.UUID,
    request: ResolveChangeFlagRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Update a persona change flag (approve/dismiss).

    REQ-006 §5.4: HITL sync - user approves or dismisses suggested changes.

    Args:
        flag_id: The change flag ID to update.
        request: The resolution request body.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with updated flag.

    Raises:
        NotFoundError: If flag not found or not owned by user.
        InvalidStateError: If flag is already resolved.
        ValidationError: If resolution is invalid.
    """
    # Find flag with ownership check
    result = await db.execute(
        select(PersonaChangeFlag)
        .join(Persona, PersonaChangeFlag.persona_id == Persona.id)
        .where(PersonaChangeFlag.id == flag_id, Persona.user_id == user_id)
    )
    flag = result.scalar_one_or_none()

    if not flag:
        raise NotFoundError("PersonaChangeFlag", str(flag_id))

    # Check if already resolved
    if flag.status == "Resolved":
        raise InvalidStateError("Change flag is already resolved")

    # Update flag (resolution validation handled by Pydantic Literal)
    flag.status = request.status
    flag.resolution = request.resolution
    flag.resolved_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(flag)

    return DataResponse(data=_flag_to_dict(flag))
