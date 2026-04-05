"""SearchProfile API router.

REQ-034 §4.2, §4.3, §4.5: Endpoints for AI-generated job search criteria.
Three endpoints: GET returns the current profile, POST /generate triggers
AI regeneration, PATCH allows user-driven bucket edits and approval.

Ownership verification uses Pattern A from REQ-014 §5.1: direct persona lookup
with user_id filter, returning 404 for cross-tenant access to prevent
resource enumeration.

Coordinates with:
  - api/deps.py (BalanceCheck, CurrentUserId, DbSession, MeteredProvider)
  - core/errors.py (NotFoundError)
  - core/responses.py (DataResponse)
  - models/persona.py (Persona — for ownership verification)
  - repositories/search_profile_repository.py (SearchProfileRepository)
  - schemas/search_profile.py (SearchProfileApiUpdate, SearchProfileRead,
    SearchProfileUpdate)
  - services/discovery/search_profile_service.py (generate_profile —
    SearchProfileGenerationError propagates via api_error_handler in main.py)

Called by: api/v1/router.py.
"""

import uuid

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import BalanceCheck, CurrentUserId, DbSession, MeteredProvider
from app.core.errors import NotFoundError
from app.core.responses import DataResponse
from app.models.persona import Persona
from app.repositories.search_profile_repository import SearchProfileRepository
from app.schemas.search_profile import (
    SearchProfileApiUpdate,
    SearchProfileRead,
    SearchProfileUpdate,
)
from app.services.discovery.search_profile_service import generate_profile

router = APIRouter()


# =============================================================================
# Helpers (private)
# =============================================================================


async def _get_owned_persona(
    persona_id: uuid.UUID,
    user_id: uuid.UUID,
    db: DbSession,
) -> Persona:
    """Fetch a persona with ownership verification (Pattern A).

    REQ-014 §5.1: Direct persona lookup with user_id filter.
    Returns 404 (not 403) to prevent resource enumeration.

    Note: uses ``if not persona`` to match the codebase-wide convention
    (same pattern as ``personas._get_owned_persona``), mirroring the
    identical implementation in api/v1/personas.py.

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


async def _get_owned_persona_with_skills(
    persona_id: uuid.UUID,
    user_id: uuid.UUID,
    db: DbSession,
) -> Persona:
    """Fetch a persona with ownership verification and eager-loaded skills.

    REQ-034 §4.3: The generate endpoint calls compute_fingerprint() and
    _build_generate_prompt(), both of which access persona.skills synchronously.
    selectinload avoids async lazy-load errors and N+1 queries.

    Args:
        persona_id: The persona ID to look up.
        user_id: Current authenticated user ID.
        db: Database session.

    Returns:
        Persona instance with skills relationship loaded.

    Raises:
        NotFoundError: If persona not found or not owned by user.
    """
    result = await db.execute(
        select(Persona)
        .options(selectinload(Persona.skills))
        .where(Persona.id == persona_id, Persona.user_id == user_id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise NotFoundError("Persona", str(persona_id))
    return persona


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/{persona_id}")
async def get_search_profile(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[SearchProfileRead]:
    """Get the SearchProfile for a persona.

    REQ-034 §4.5: Returns AI-generated fit/stretch search criteria.
    Verifies persona ownership before returning the profile.

    Args:
        persona_id: UUID of the persona whose profile to return.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse containing the SearchProfile.

    Raises:
        NotFoundError: If persona not owned by user or profile does not exist.
    """
    persona = await _get_owned_persona(persona_id, user_id, db)

    # Use persona.id (from the ownership-verified object) rather than the
    # raw persona_id path parameter — prevents latent IDOR if the ownership
    # gate were ever decoupled from this lookup in a future refactor.
    profile = await SearchProfileRepository.get_by_persona_id(db, persona.id)
    if profile is None:
        raise NotFoundError("SearchProfile", str(persona_id))

    return DataResponse(data=SearchProfileRead.model_validate(profile))


@router.post("/{persona_id}/generate")
async def generate_search_profile(
    persona_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
    _balance: BalanceCheck,
    provider: MeteredProvider,
) -> DataResponse[SearchProfileRead]:
    """Generate or regenerate the SearchProfile for a persona via AI.

    REQ-034 §4.3: Calls the LLM once to derive fit/stretch search criteria.
    The generated profile is stored and reused by the polling loop without
    further LLM involvement. An existing profile is overwritten on each call.

    Note: ``_balance`` is declared before ``provider`` so that the balance
    gate conventionally precedes the LLM-touching dependency in parameter
    resolution order.

    Args:
        persona_id: UUID of the persona to generate search criteria for.
        user_id: Current authenticated user (injected).
        db: Database session (injected).
        _balance: Balance gate — raises 402 before provider call if insufficient.
        provider: Metered LLM provider (injected).

    Returns:
        DataResponse containing the newly generated SearchProfile.

    Raises:
        NotFoundError: If persona not owned by user.
        SearchProfileGenerationError: 502 if the LLM call fails or returns
            empty/unparseable content.
    """
    persona = await _get_owned_persona_with_skills(persona_id, user_id, db)

    # SearchProfileGenerationError (502) propagates via api_error_handler in main.py.
    profile = await generate_profile(db, persona, provider)

    await db.commit()
    await db.refresh(profile)
    return DataResponse(data=SearchProfileRead.model_validate(profile))


@router.patch("/{persona_id}")
async def update_search_profile(
    persona_id: uuid.UUID,
    request: SearchProfileApiUpdate,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[SearchProfileRead]:
    """Partially update a SearchProfile — edit buckets or set approved_at.

    REQ-034 §4.5: Used for user-driven bucket edits and the approval action
    (setting approved_at). Only fields explicitly provided in the request
    body are updated — all others are left unchanged.

    Accepts ``SearchProfileApiUpdate`` (user-facing schema) rather than the
    full ``SearchProfileUpdate`` to prevent clients from directly setting
    internal system fields (``is_stale``, ``persona_fingerprint``,
    ``generated_at``).

    Args:
        persona_id: UUID of the persona whose profile to update.
        request: Partial update data (fit_searches, stretch_searches, approved_at).
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse containing the updated SearchProfile.

    Raises:
        NotFoundError: If persona not owned by user or profile does not exist.
    """
    persona = await _get_owned_persona(persona_id, user_id, db)

    profile = await SearchProfileRepository.get_by_persona_id(db, persona.id)
    if profile is None:
        raise NotFoundError("SearchProfile", str(persona_id))

    # Map the API-facing request to the internal update schema.
    # SearchProfileUpdate fields not present in SearchProfileApiUpdate
    # (is_stale, persona_fingerprint, generated_at) are left as None so
    # the repository's exclude_none=True logic skips them.
    internal_update = SearchProfileUpdate(
        fit_searches=request.fit_searches,
        stretch_searches=request.stretch_searches,
        approved_at=request.approved_at,
    )
    updated = await SearchProfileRepository.update(db, profile.id, internal_update)

    await db.commit()
    await db.refresh(updated)
    return DataResponse(data=SearchProfileRead.model_validate(updated))
