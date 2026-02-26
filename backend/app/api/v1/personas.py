"""Personas API router.

REQ-006 §5.2: Personas resource with nested sub-resources.
REQ-014 §5.1: Pattern A — direct persona lookup with user_id filter.
REQ-014 §6.2: All persona endpoints verify ownership.

NOTE: This file exceeds 300 lines due to the number of nested resources
under /personas. Splitting would fragment the logical grouping. All persona
sub-resources are kept together for cohesion.

Top-level CRUD endpoints are fully implemented with ownership verification.
Nested sub-resource endpoints verify persona ownership but return stub
responses until repository and service layers are built.

Endpoints:
- /personas - CRUD for user personas
- /personas/{id}/work-history - Work history entries (stub)
- /personas/{id}/skills - Skills list (stub)
- /personas/{id}/education - Education entries (stub)
- /personas/{id}/certifications - Certifications (stub)
- /personas/{id}/achievement-stories - Achievement stories (stub)
- /personas/{id}/voice-profile - Voice profile (stub)
- /personas/{id}/custom-non-negotiables - Custom job filters (stub)
- /personas/{id}/embeddings/regenerate - Trigger embedding regeneration (stub)
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserId, DbSession
from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError
from app.core.rate_limiting import limiter
from app.core.responses import DataResponse, ListResponse, PaginationMeta
from app.models.persona import Persona

_MAX_SUMMARY_LENGTH = 10000
"""Safety bound on professional summary text length."""

_MAX_JSONB_LIST_LENGTH = 200
"""Safety bound on JSONB list field lengths (defense-in-depth)."""

_MAX_JSONB_ITEM_LENGTH = 500
"""Safety bound on individual string items within JSONB lists."""

BoundedStr = Annotated[
    str, StringConstraints(min_length=1, max_length=_MAX_JSONB_ITEM_LENGTH)
]
"""String type with length bounds for JSONB list items (defense-in-depth)."""

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class _PersonaOptionalFields(BaseModel):
    """Shared optional fields for persona create/update schemas.

    Centralizes field definitions to eliminate duplication between
    CreatePersonaRequest and UpdatePersonaRequest.
    """

    model_config = ConfigDict(extra="forbid")

    # Online presence
    linkedin_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)

    # Professional info
    professional_summary: str | None = Field(
        default=None, max_length=_MAX_SUMMARY_LENGTH
    )
    years_experience: int | None = Field(default=None, ge=0, le=100)
    current_role: str | None = Field(default=None, max_length=255)
    current_company: str | None = Field(default=None, max_length=255)

    # Career goals (JSONB arrays)
    target_roles: list[BoundedStr] | None = Field(
        default=None, max_length=_MAX_JSONB_LIST_LENGTH
    )
    target_skills: list[BoundedStr] | None = Field(
        default=None, max_length=_MAX_JSONB_LIST_LENGTH
    )

    # Location preferences
    commutable_cities: list[BoundedStr] | None = Field(
        default=None, max_length=_MAX_JSONB_LIST_LENGTH
    )
    relocation_cities: list[BoundedStr] | None = Field(
        default=None, max_length=_MAX_JSONB_LIST_LENGTH
    )
    industry_exclusions: list[BoundedStr] | None = Field(
        default=None, max_length=_MAX_JSONB_LIST_LENGTH
    )

    # Preferences
    stretch_appetite: str | None = Field(default=None, max_length=20)
    minimum_base_salary: int | None = Field(default=None, ge=0, le=10_000_000)
    salary_currency: str | None = Field(default=None, max_length=10)
    max_commute_minutes: int | None = Field(default=None, ge=0, le=1440)
    remote_preference: str | None = Field(default=None, max_length=30)
    relocation_open: bool | None = None
    visa_sponsorship_required: bool | None = None
    company_size_preference: str | None = Field(default=None, max_length=30)
    max_travel_percent: str | None = Field(default=None, max_length=20)

    # Thresholds
    minimum_fit_threshold: int | None = Field(default=None, ge=0, le=100)
    auto_draft_threshold: int | None = Field(default=None, ge=0, le=100)
    polling_frequency: str | None = Field(default=None, max_length=20)


class CreatePersonaRequest(_PersonaOptionalFields):
    """Request body for creating a persona.

    REQ-006 §5.2: Required contact fields for persona creation.
    """

    # Required contact info
    email: str = Field(..., min_length=1, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=1, max_length=50)
    home_city: str = Field(..., min_length=1, max_length=100)
    home_state: str = Field(..., min_length=1, max_length=100)
    home_country: str = Field(..., min_length=1, max_length=100)


class UpdatePersonaRequest(_PersonaOptionalFields):
    """Request body for partially updating a persona.

    All fields optional — only provided fields are updated.
    """

    # Contact info (all optional for partial updates)
    email: str | None = Field(default=None, min_length=1, max_length=255)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, min_length=1, max_length=50)
    home_city: str | None = Field(default=None, min_length=1, max_length=100)
    home_state: str | None = Field(default=None, min_length=1, max_length=100)
    home_country: str | None = Field(default=None, min_length=1, max_length=100)

    # Onboarding state
    onboarding_complete: bool | None = None
    onboarding_step: str | None = Field(default=None, max_length=50)


# =============================================================================
# Helper Functions
# =============================================================================


async def _handle_integrity_error(db: DbSession, exc: IntegrityError) -> NoReturn:
    """Roll back and raise a user-friendly ConflictError.

    Args:
        db: Database session to roll back.
        exc: The IntegrityError from SQLAlchemy.

    Raises:
        ConflictError: Always — with DUPLICATE_EMAIL or generic CONFLICT code.
    """
    await db.rollback()
    error_msg = str(exc.orig) if exc.orig else str(exc)
    if "email" in error_msg.lower():
        raise ConflictError(
            code="DUPLICATE_EMAIL",
            message="A persona with this email already exists.",
        ) from None
    raise ConflictError(
        code="CONFLICT",
        message="A database constraint was violated.",
    ) from None


def _persona_to_dict(persona: Persona) -> dict:
    """Convert Persona model to API response dict.

    Args:
        persona: The Persona model instance.

    Returns:
        Dict with persona data for API response.
    """
    return {
        "id": str(persona.id),
        "user_id": str(persona.user_id),
        "email": persona.email,
        "full_name": persona.full_name,
        "phone": persona.phone,
        "home_city": persona.home_city,
        "home_state": persona.home_state,
        "home_country": persona.home_country,
        "linkedin_url": persona.linkedin_url,
        "portfolio_url": persona.portfolio_url,
        "professional_summary": persona.professional_summary,
        "years_experience": persona.years_experience,
        "current_role": persona.current_role,
        "current_company": persona.current_company,
        "target_roles": persona.target_roles,
        "target_skills": persona.target_skills,
        "commutable_cities": persona.commutable_cities,
        "relocation_cities": persona.relocation_cities,
        "industry_exclusions": persona.industry_exclusions,
        "stretch_appetite": persona.stretch_appetite,
        "minimum_base_salary": persona.minimum_base_salary,
        "salary_currency": persona.salary_currency,
        "max_commute_minutes": persona.max_commute_minutes,
        "remote_preference": persona.remote_preference,
        "relocation_open": persona.relocation_open,
        "visa_sponsorship_required": persona.visa_sponsorship_required,
        "company_size_preference": persona.company_size_preference,
        "max_travel_percent": persona.max_travel_percent,
        "minimum_fit_threshold": persona.minimum_fit_threshold,
        "auto_draft_threshold": persona.auto_draft_threshold,
        "polling_frequency": persona.polling_frequency,
        "onboarding_complete": persona.onboarding_complete,
        "onboarding_step": persona.onboarding_step,
        "created_at": persona.created_at.isoformat(),
        "updated_at": persona.updated_at.isoformat(),
    }


async def _get_owned_persona(
    persona_id: uuid.UUID, user_id: uuid.UUID, db: DbSession
) -> Persona:
    """Fetch a persona with ownership verification (Pattern A).

    REQ-014 §5.1: Direct persona lookup with user_id filter.
    Returns 404 (not 403) to prevent resource enumeration.

    Args:
        persona_id: The persona ID to look up.
        user_id: Current authenticated user ID.
        db: Database session.

    Returns:
        Persona instance owned by the user.

    Raises:
        NotFoundError: If persona not found or not owned by user.
    """
    result = await db.execute(
        select(Persona).where(Persona.id == persona_id, Persona.user_id == user_id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise NotFoundError("Persona", str(persona_id))
    return persona


# =============================================================================
# Personas CRUD
# =============================================================================


@router.get("")
async def list_personas(
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List all personas for current user.

    REQ-006 §5.2: Most users have exactly one persona.
    REQ-014 §5.4: List scoped to authenticated user.

    Args:
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        ListResponse with personas and pagination meta.
    """
    result = await db.execute(
        select(Persona)
        .where(Persona.user_id == user_id)
        .order_by(Persona.created_at.desc())
    )
    personas = result.scalars().all()

    return ListResponse(
        data=[_persona_to_dict(p) for p in personas],
        meta=PaginationMeta(total=len(personas), page=1, per_page=len(personas) or 20),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_persona(
    request: CreatePersonaRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Create a new persona.

    REQ-006 §5.2: User profile creation.
    Automatically binds to the authenticated user's ID.

    Args:
        request: The create request body.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with created persona.

    Raises:
        ConflictError: If email already exists.
    """
    # Build kwargs from required + optional fields
    create_data = request.model_dump(exclude_unset=True)
    create_data["user_id"] = user_id

    persona = Persona(**create_data)
    db.add(persona)

    try:
        await db.commit()
    except IntegrityError as exc:
        await _handle_integrity_error(db, exc)

    await db.refresh(persona)
    return DataResponse(data=_persona_to_dict(persona))


@router.get("/{persona_id}")
async def get_persona(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get a persona by ID.

    REQ-014 §5.1: Ownership verified via Pattern A.

    Args:
        persona_id: The persona ID.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with persona data.

    Raises:
        NotFoundError: If persona not found or not owned by user.
    """
    persona = await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data=_persona_to_dict(persona))


@router.patch("/{persona_id}")
async def update_persona(
    persona_id: uuid.UUID,
    request: UpdatePersonaRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Partially update a persona.

    REQ-014 §5.1: Ownership verified via Pattern A.

    Args:
        persona_id: The persona ID.
        request: The update request body (partial fields).
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with updated persona.

    Raises:
        NotFoundError: If persona not found or not owned by user.
        ConflictError: If email update violates uniqueness.
    """
    persona = await _get_owned_persona(persona_id, user_id, db)

    # Apply only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(persona, field, value)

    persona.updated_at = datetime.now(UTC)

    try:
        await db.commit()
    except IntegrityError as exc:
        await _handle_integrity_error(db, exc)

    await db.refresh(persona)

    return DataResponse(data=_persona_to_dict(persona))


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> Response:
    """Delete a persona.

    WARNING: This is a hard delete with CASCADE — all child entities
    (work histories, skills, resumes, applications, etc.) are removed.

    REQ-014 §5.1: Ownership verified via Pattern A.

    Args:
        persona_id: The persona ID.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        204 No Content on success.

    Raises:
        NotFoundError: If persona not found or not owned by user.
    """
    persona = await _get_owned_persona(persona_id, user_id, db)
    await db.delete(persona)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# =============================================================================
# Work History (nested resource — stub with ownership check)
# =============================================================================


@router.get("/{persona_id}/work-history")
async def list_work_history(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List work history entries for a persona."""
    await _get_owned_persona(persona_id, user_id, db)
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("/{persona_id}/work-history")
async def create_work_history(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Add a work history entry."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.get("/{persona_id}/work-history/{entry_id}")
async def get_work_history(
    persona_id: uuid.UUID,
    entry_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get a work history entry."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.patch("/{persona_id}/work-history/{entry_id}")
async def update_work_history(
    persona_id: uuid.UUID,
    entry_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Update a work history entry."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.delete("/{persona_id}/work-history/{entry_id}")
async def delete_work_history(
    persona_id: uuid.UUID,
    entry_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> None:
    """Delete a work history entry."""
    await _get_owned_persona(persona_id, user_id, db)


# =============================================================================
# Skills (nested resource — stub with ownership check)
# =============================================================================


@router.get("/{persona_id}/skills")
async def list_skills(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List skills for a persona."""
    await _get_owned_persona(persona_id, user_id, db)
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("/{persona_id}/skills")
async def create_skill(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Add a skill to the persona."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.get("/{persona_id}/skills/{skill_id}")
async def get_skill(
    persona_id: uuid.UUID,
    skill_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get a skill by ID."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.patch("/{persona_id}/skills/{skill_id}")
async def update_skill(
    persona_id: uuid.UUID,
    skill_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Update a skill."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.delete("/{persona_id}/skills/{skill_id}")
async def delete_skill(
    persona_id: uuid.UUID,
    skill_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> None:
    """Delete a skill."""
    await _get_owned_persona(persona_id, user_id, db)


# =============================================================================
# Education (nested resource — stub with ownership check)
# =============================================================================


@router.get("/{persona_id}/education")
async def list_education(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List education entries for a persona."""
    await _get_owned_persona(persona_id, user_id, db)
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("/{persona_id}/education")
async def create_education(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Add an education entry."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.get("/{persona_id}/education/{entry_id}")
async def get_education(
    persona_id: uuid.UUID,
    entry_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get an education entry."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.patch("/{persona_id}/education/{entry_id}")
async def update_education(
    persona_id: uuid.UUID,
    entry_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Update an education entry."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.delete("/{persona_id}/education/{entry_id}")
async def delete_education(
    persona_id: uuid.UUID,
    entry_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> None:
    """Delete an education entry."""
    await _get_owned_persona(persona_id, user_id, db)


# =============================================================================
# Certifications (nested resource — stub with ownership check)
# =============================================================================


@router.get("/{persona_id}/certifications")
async def list_certifications(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List certifications for a persona."""
    await _get_owned_persona(persona_id, user_id, db)
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("/{persona_id}/certifications")
async def create_certification(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Add a certification."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.get("/{persona_id}/certifications/{cert_id}")
async def get_certification(
    persona_id: uuid.UUID,
    cert_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get a certification by ID."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.patch("/{persona_id}/certifications/{cert_id}")
async def update_certification(
    persona_id: uuid.UUID,
    cert_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Update a certification."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.delete("/{persona_id}/certifications/{cert_id}")
async def delete_certification(
    persona_id: uuid.UUID,
    cert_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> None:
    """Delete a certification."""
    await _get_owned_persona(persona_id, user_id, db)


# =============================================================================
# Achievement Stories (nested resource — stub with ownership check)
# =============================================================================


@router.get("/{persona_id}/achievement-stories")
async def list_achievement_stories(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List achievement stories for a persona."""
    await _get_owned_persona(persona_id, user_id, db)
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("/{persona_id}/achievement-stories")
async def create_achievement_story(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Add an achievement story."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.get("/{persona_id}/achievement-stories/{story_id}")
async def get_achievement_story(
    persona_id: uuid.UUID,
    story_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get an achievement story by ID."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.patch("/{persona_id}/achievement-stories/{story_id}")
async def update_achievement_story(
    persona_id: uuid.UUID,
    story_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Update an achievement story."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.delete("/{persona_id}/achievement-stories/{story_id}")
async def delete_achievement_story(
    persona_id: uuid.UUID,
    story_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> None:
    """Delete an achievement story."""
    await _get_owned_persona(persona_id, user_id, db)


# =============================================================================
# Voice Profile (1:1 with persona, read/update only — stub with ownership check)
# =============================================================================


@router.get("/{persona_id}/voice-profile")
async def get_voice_profile(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get the voice profile for a persona.

    REQ-006 §5.2: 1:1 with persona, no create/delete.
    """
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.patch("/{persona_id}/voice-profile")
async def update_voice_profile(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Update the voice profile for a persona."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


# =============================================================================
# Custom Non-Negotiables (nested resource — stub with ownership check)
# =============================================================================


@router.get("/{persona_id}/custom-non-negotiables")
async def list_custom_non_negotiables(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List custom non-negotiables for a persona.

    REQ-006 §5.2: Custom filters like "No Amazon subsidiaries".
    """
    await _get_owned_persona(persona_id, user_id, db)
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("/{persona_id}/custom-non-negotiables")
async def create_custom_non_negotiable(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Add a custom non-negotiable."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.get("/{persona_id}/custom-non-negotiables/{nn_id}")
async def get_custom_non_negotiable(
    persona_id: uuid.UUID,
    nn_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get a custom non-negotiable by ID."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.patch("/{persona_id}/custom-non-negotiables/{nn_id}")
async def update_custom_non_negotiable(
    persona_id: uuid.UUID,
    nn_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Update a custom non-negotiable."""
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={})


@router.delete("/{persona_id}/custom-non-negotiables/{nn_id}")
async def delete_custom_non_negotiable(
    persona_id: uuid.UUID,
    nn_id: uuid.UUID,  # noqa: ARG001
    user_id: CurrentUserId,
    db: DbSession,
) -> None:
    """Delete a custom non-negotiable."""
    await _get_owned_persona(persona_id, user_id, db)


# =============================================================================
# Embeddings (action endpoint — stub with ownership check)
# =============================================================================


@router.post("/{persona_id}/embeddings/regenerate")
@limiter.limit(settings.rate_limit_embeddings)
async def regenerate_embeddings(
    request: Request,  # noqa: ARG001
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Trigger persona embedding regeneration.

    REQ-006 §5.2: POST action to regenerate vector embeddings.
    Security: Rate limited to prevent embedding cost abuse.
    """
    await _get_owned_persona(persona_id, user_id, db)
    return DataResponse(data={"status": "queued"})
