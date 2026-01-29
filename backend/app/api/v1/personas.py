"""Personas API router.

REQ-006 §5.2: Personas resource with nested sub-resources.

NOTE: This file exceeds 300 lines due to the number of nested resources
under /personas. Splitting would fragment the logical grouping. All persona
sub-resources are kept together for cohesion.

NOTE: Endpoint functions return stub responses. Full implementation will be
added when repository and service layers are built in Phase 2+.

Endpoints:
- /personas - CRUD for user personas
- /personas/{id}/work-history - Work history entries
- /personas/{id}/skills - Skills list
- /personas/{id}/education - Education entries
- /personas/{id}/certifications - Certifications
- /personas/{id}/achievement-stories - Achievement stories
- /personas/{id}/voice-profile - Voice profile (read/update only)
- /personas/{id}/custom-non-negotiables - Custom job filters
- /personas/{id}/embeddings/regenerate - Trigger embedding regeneration
"""

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user_id
from app.core.responses import DataResponse, ListResponse, PaginationMeta

router = APIRouter()


# =============================================================================
# Personas CRUD
# =============================================================================


@router.get("")
async def list_personas(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List all personas for current user.

    REQ-006 §5.2: Most users have exactly one persona.
    """
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("")
async def create_persona(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Create a new persona.

    REQ-006 §5.2: User profile creation.
    """
    return DataResponse(data={})


@router.get("/{persona_id}")
async def get_persona(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get a persona by ID."""
    return DataResponse(data={})


@router.patch("/{persona_id}")
async def update_persona(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Partially update a persona."""
    return DataResponse(data={})


@router.delete("/{persona_id}")
async def delete_persona(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> None:
    """Delete a persona (soft delete)."""
    return None


# =============================================================================
# Work History (nested resource)
# =============================================================================


@router.get("/{persona_id}/work-history")
async def list_work_history(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List work history entries for a persona."""
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("/{persona_id}/work-history")
async def create_work_history(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Add a work history entry."""
    return DataResponse(data={})


@router.get("/{persona_id}/work-history/{entry_id}")
async def get_work_history(
    persona_id: uuid.UUID,  # noqa: ARG001
    entry_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get a work history entry."""
    return DataResponse(data={})


@router.patch("/{persona_id}/work-history/{entry_id}")
async def update_work_history(
    persona_id: uuid.UUID,  # noqa: ARG001
    entry_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Update a work history entry."""
    return DataResponse(data={})


@router.delete("/{persona_id}/work-history/{entry_id}")
async def delete_work_history(
    persona_id: uuid.UUID,  # noqa: ARG001
    entry_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> None:
    """Delete a work history entry."""
    return None


# =============================================================================
# Skills (nested resource)
# =============================================================================


@router.get("/{persona_id}/skills")
async def list_skills(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List skills for a persona."""
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("/{persona_id}/skills")
async def create_skill(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Add a skill to the persona."""
    return DataResponse(data={})


@router.get("/{persona_id}/skills/{skill_id}")
async def get_skill(
    persona_id: uuid.UUID,  # noqa: ARG001
    skill_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get a skill by ID."""
    return DataResponse(data={})


@router.patch("/{persona_id}/skills/{skill_id}")
async def update_skill(
    persona_id: uuid.UUID,  # noqa: ARG001
    skill_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Update a skill."""
    return DataResponse(data={})


@router.delete("/{persona_id}/skills/{skill_id}")
async def delete_skill(
    persona_id: uuid.UUID,  # noqa: ARG001
    skill_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> None:
    """Delete a skill."""
    return None


# =============================================================================
# Education (nested resource)
# =============================================================================


@router.get("/{persona_id}/education")
async def list_education(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List education entries for a persona."""
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("/{persona_id}/education")
async def create_education(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Add an education entry."""
    return DataResponse(data={})


@router.get("/{persona_id}/education/{entry_id}")
async def get_education(
    persona_id: uuid.UUID,  # noqa: ARG001
    entry_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get an education entry."""
    return DataResponse(data={})


@router.patch("/{persona_id}/education/{entry_id}")
async def update_education(
    persona_id: uuid.UUID,  # noqa: ARG001
    entry_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Update an education entry."""
    return DataResponse(data={})


@router.delete("/{persona_id}/education/{entry_id}")
async def delete_education(
    persona_id: uuid.UUID,  # noqa: ARG001
    entry_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> None:
    """Delete an education entry."""
    return None


# =============================================================================
# Certifications (nested resource)
# =============================================================================


@router.get("/{persona_id}/certifications")
async def list_certifications(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List certifications for a persona."""
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("/{persona_id}/certifications")
async def create_certification(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Add a certification."""
    return DataResponse(data={})


@router.get("/{persona_id}/certifications/{cert_id}")
async def get_certification(
    persona_id: uuid.UUID,  # noqa: ARG001
    cert_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get a certification by ID."""
    return DataResponse(data={})


@router.patch("/{persona_id}/certifications/{cert_id}")
async def update_certification(
    persona_id: uuid.UUID,  # noqa: ARG001
    cert_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Update a certification."""
    return DataResponse(data={})


@router.delete("/{persona_id}/certifications/{cert_id}")
async def delete_certification(
    persona_id: uuid.UUID,  # noqa: ARG001
    cert_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> None:
    """Delete a certification."""
    return None


# =============================================================================
# Achievement Stories (nested resource)
# =============================================================================


@router.get("/{persona_id}/achievement-stories")
async def list_achievement_stories(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List achievement stories for a persona."""
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("/{persona_id}/achievement-stories")
async def create_achievement_story(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Add an achievement story."""
    return DataResponse(data={})


@router.get("/{persona_id}/achievement-stories/{story_id}")
async def get_achievement_story(
    persona_id: uuid.UUID,  # noqa: ARG001
    story_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get an achievement story by ID."""
    return DataResponse(data={})


@router.patch("/{persona_id}/achievement-stories/{story_id}")
async def update_achievement_story(
    persona_id: uuid.UUID,  # noqa: ARG001
    story_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Update an achievement story."""
    return DataResponse(data={})


@router.delete("/{persona_id}/achievement-stories/{story_id}")
async def delete_achievement_story(
    persona_id: uuid.UUID,  # noqa: ARG001
    story_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> None:
    """Delete an achievement story."""
    return None


# =============================================================================
# Voice Profile (1:1 with persona, read/update only)
# =============================================================================


@router.get("/{persona_id}/voice-profile")
async def get_voice_profile(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get the voice profile for a persona.

    REQ-006 §5.2: 1:1 with persona, no create/delete.
    """
    return DataResponse(data={})


@router.patch("/{persona_id}/voice-profile")
async def update_voice_profile(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Update the voice profile for a persona."""
    return DataResponse(data={})


# =============================================================================
# Custom Non-Negotiables (nested resource)
# =============================================================================


@router.get("/{persona_id}/custom-non-negotiables")
async def list_custom_non_negotiables(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List custom non-negotiables for a persona.

    REQ-006 §5.2: Custom filters like "No Amazon subsidiaries".
    """
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


@router.post("/{persona_id}/custom-non-negotiables")
async def create_custom_non_negotiable(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Add a custom non-negotiable."""
    return DataResponse(data={})


@router.get("/{persona_id}/custom-non-negotiables/{nn_id}")
async def get_custom_non_negotiable(
    persona_id: uuid.UUID,  # noqa: ARG001
    nn_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get a custom non-negotiable by ID."""
    return DataResponse(data={})


@router.patch("/{persona_id}/custom-non-negotiables/{nn_id}")
async def update_custom_non_negotiable(
    persona_id: uuid.UUID,  # noqa: ARG001
    nn_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Update a custom non-negotiable."""
    return DataResponse(data={})


@router.delete("/{persona_id}/custom-non-negotiables/{nn_id}")
async def delete_custom_non_negotiable(
    persona_id: uuid.UUID,  # noqa: ARG001
    nn_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> None:
    """Delete a custom non-negotiable."""
    return None


# =============================================================================
# Embeddings (action endpoint)
# =============================================================================


@router.post("/{persona_id}/embeddings/regenerate")
async def regenerate_embeddings(
    persona_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Trigger persona embedding regeneration.

    REQ-006 §5.2: POST action to regenerate vector embeddings.
    """
    return DataResponse(data={"status": "queued"})
