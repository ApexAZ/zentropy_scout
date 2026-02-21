"""User Source Preferences API router.

REQ-006 §5.2: Per-user job source settings (read/update only).
REQ-014 §5.2: Ownership verification via JOIN through persona.
"""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import CurrentUserId, DbSession
from app.core.errors import NotFoundError
from app.core.responses import DataResponse, ListResponse, PaginationMeta
from app.models import Persona
from app.models.job_source import UserSourcePreference

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class UpdatePreferenceRequest(BaseModel):
    """Request body for updating a user source preference."""

    model_config = ConfigDict(extra="forbid")

    is_enabled: bool | None = None
    display_order: int | None = Field(default=None, ge=0, le=10000)


# =============================================================================
# Helper Functions
# =============================================================================


def _preference_to_dict(pref: UserSourcePreference) -> dict:
    """Convert UserSourcePreference model to API response dict.

    Args:
            pref: The UserSourcePreference model instance.

    Returns:
            Dict with preference data for API response.
    """
    return {
        "id": str(pref.id),
        "persona_id": str(pref.persona_id),
        "source_id": str(pref.source_id),
        "is_enabled": pref.is_enabled,
        "display_order": pref.display_order,
    }


async def _get_owned_preference(
    preference_id: uuid.UUID, user_id: uuid.UUID, db: DbSession
) -> UserSourcePreference:
    """Fetch a user source preference with ownership verification.

    REQ-014 §5.2: JOIN through persona for tenant isolation.

    Args:
            preference_id: The preference ID to look up.
            user_id: Current authenticated user ID.
            db: Database session.

    Returns:
            UserSourcePreference owned by the user.

    Raises:
            NotFoundError: If preference not found or not owned by user.
    """
    result = await db.execute(
        select(UserSourcePreference)
        .join(Persona, UserSourcePreference.persona_id == Persona.id)
        .where(UserSourcePreference.id == preference_id, Persona.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        raise NotFoundError("UserSourcePreference", str(preference_id))
    return pref


# =============================================================================
# Endpoints
# =============================================================================


@router.get("")
async def list_user_source_preferences(
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List user's job source preferences.

    REQ-014 §5.4: Scoped to authenticated user via persona JOIN.

    Args:
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            ListResponse with preferences and pagination meta.
    """
    result = await db.execute(
        select(UserSourcePreference)
        .join(Persona, UserSourcePreference.persona_id == Persona.id)
        .where(Persona.user_id == user_id)
        .order_by(UserSourcePreference.display_order)
    )
    prefs = result.scalars().all()

    return ListResponse(
        data=[_preference_to_dict(p) for p in prefs],
        meta=PaginationMeta(total=len(prefs), page=1, per_page=len(prefs) or 20),
    )


@router.get("/{preference_id}")
async def get_user_source_preference(
    preference_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get a user source preference by ID.

    REQ-014 §5.2: Returns 404 for cross-tenant access.

    Args:
            preference_id: The preference ID.
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            DataResponse with preference data.

    Raises:
            NotFoundError: If preference not found or not owned by user.
    """
    pref = await _get_owned_preference(preference_id, user_id, db)
    return DataResponse(data=_preference_to_dict(pref))


@router.patch("/{preference_id}")
async def update_user_source_preference(
    preference_id: uuid.UUID,
    request: UpdatePreferenceRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Update a user source preference (enable/disable source).

    REQ-014 §5.2: Returns 404 for cross-tenant access.

    Args:
            preference_id: The preference ID.
            request: The update request body (partial fields).
            user_id: Current authenticated user (injected).
            db: Database session (injected).

    Returns:
            DataResponse with updated preference.

    Raises:
            NotFoundError: If preference not found or not owned by user.
    """
    pref = await _get_owned_preference(preference_id, user_id, db)

    update_data = request.model_dump(exclude_unset=True)
    # SECURITY: safe because extra="forbid" restricts to declared fields only
    for field, value in update_data.items():
        setattr(pref, field, value)

    await db.commit()
    await db.refresh(pref)

    return DataResponse(data=_preference_to_dict(pref))
