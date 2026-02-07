"""Persona → Base Resume sync service.

REQ-002 §6.3: When user adds new items to Persona, Base Resumes need
to stay current. This service implements the flag-for-review mechanism:

1. raise_change_flag — creates a PersonaChangeFlag when persona data changes
2. resolve_change_flag — applies the user's resolution to affected BaseResumes
3. get_pending_flags — retrieves pending flags for a persona
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateError, NotFoundError, ValidationError
from app.models.persona import Persona
from app.models.persona_content import Bullet
from app.models.persona_settings import PersonaChangeFlag
from app.models.resume import BaseResume

_VALID_CHANGE_TYPES = frozenset(
    {
        "job_added",
        "bullet_added",
        "skill_added",
        "education_added",
        "certification_added",
    }
)
"""Allowed change_type values matching the DB CHECK constraint."""

_VALID_RESOLUTIONS = frozenset({"added_to_all", "added_to_some", "skipped"})
"""Allowed resolution values matching the DB CHECK constraint."""

# Maps change_type → BaseResume JSONB array field for simple list appends.
# bullet_added is special (modifies dict, not list) and handled separately.
_CHANGE_TYPE_TO_FIELD: dict[str, str] = {
    "job_added": "included_jobs",
    "skill_added": "skills_emphasis",
    "education_added": "included_education",
    "certification_added": "included_certifications",
}


@dataclass(frozen=True)
class ResolveFlagResult:
    """Summary of a flag resolution."""

    flag_id: uuid.UUID
    resolution: str
    resumes_updated: int


# =============================================================================
# Public API
# =============================================================================


async def raise_change_flag(
    db: AsyncSession,
    persona_id: uuid.UUID,
    change_type: str,
    item_id: uuid.UUID,
    item_description: str,
) -> PersonaChangeFlag:
    """Create a PersonaChangeFlag for a new persona item.

    Args:
        db: Database session.
        persona_id: The persona that was modified.
        change_type: One of job_added, bullet_added, skill_added,
            education_added, certification_added.
        item_id: ID of the newly added item.
        item_description: Human-readable summary for display.

    Returns:
        The created PersonaChangeFlag.

    Raises:
        NotFoundError: If persona does not exist.
        ValidationError: If change_type is invalid.
    """
    if change_type not in _VALID_CHANGE_TYPES:
        raise ValidationError(
            f"Invalid change_type '{change_type}'. "
            f"Must be one of: {', '.join(sorted(_VALID_CHANGE_TYPES))}."
        )

    persona = await db.get(Persona, persona_id)
    if persona is None:
        raise NotFoundError("Persona", str(persona_id))

    flag = PersonaChangeFlag(
        persona_id=persona_id,
        change_type=change_type,
        item_id=item_id,
        item_description=item_description,
        status="Pending",
    )
    db.add(flag)
    await db.flush()
    await db.refresh(flag)
    await db.commit()

    return flag


async def resolve_change_flag(
    db: AsyncSession,
    flag_id: uuid.UUID,
    resolution: str,
    target_resume_ids: list[uuid.UUID] | None = None,
) -> ResolveFlagResult:
    """Resolve a PersonaChangeFlag and sync to BaseResumes.

    Args:
        db: Database session.
        flag_id: The flag to resolve.
        resolution: One of added_to_all, added_to_some, skipped.
        target_resume_ids: Required when resolution is added_to_some.
            Specifies which BaseResumes to update.

    Returns:
        ResolveFlagResult with resolution details.

    Raises:
        NotFoundError: If flag does not exist, or if bullet_added
            references a nonexistent Bullet.
        InvalidStateError: If flag is already resolved.
        ValidationError: If resolution is invalid, or if added_to_some
            is used without target_resume_ids.
    """
    if resolution not in _VALID_RESOLUTIONS:
        raise ValidationError(
            f"Invalid resolution '{resolution}'. "
            f"Must be one of: {', '.join(sorted(_VALID_RESOLUTIONS))}."
        )

    flag = await db.get(PersonaChangeFlag, flag_id)
    if flag is None:
        raise NotFoundError("PersonaChangeFlag", str(flag_id))

    if flag.status == "Resolved":
        raise InvalidStateError("Change flag is already resolved.")

    if resolution == "added_to_some" and not target_resume_ids:
        raise ValidationError(
            "target_resume_ids is required when resolution is 'added_to_some'."
        )

    # --- Apply resolution to BaseResumes ---
    resumes_updated = 0

    if resolution != "skipped":
        resumes_updated = await _apply_to_resumes(
            db=db,
            flag=flag,
            resolution=resolution,
            target_resume_ids=target_resume_ids,
        )

    # --- Mark flag resolved ---
    now = datetime.now(UTC)
    flag.status = "Resolved"
    flag.resolution = resolution
    flag.resolved_at = now

    await db.commit()

    return ResolveFlagResult(
        flag_id=flag.id,
        resolution=resolution,
        resumes_updated=resumes_updated,
    )


async def get_pending_flags(
    db: AsyncSession,
    persona_id: uuid.UUID,
) -> list[PersonaChangeFlag]:
    """Get all pending change flags for a persona.

    Args:
        db: Database session.
        persona_id: The persona to query.

    Returns:
        List of PersonaChangeFlags with status=Pending, sorted by created_at.
    """
    result = await db.execute(
        select(PersonaChangeFlag)
        .where(
            PersonaChangeFlag.persona_id == persona_id,
            PersonaChangeFlag.status == "Pending",
        )
        .order_by(PersonaChangeFlag.created_at.asc())
    )
    return list(result.scalars().all())


# =============================================================================
# Internal Helpers
# =============================================================================


async def _get_target_resumes(
    db: AsyncSession,
    persona_id: uuid.UUID,
    resolution: str,
    target_resume_ids: list[uuid.UUID] | None,
) -> list[BaseResume]:
    """Fetch the BaseResumes to update based on resolution type.

    Args:
        db: Database session.
        persona_id: The persona owning the resumes.
        resolution: added_to_all or added_to_some.
        target_resume_ids: Specific resume IDs for added_to_some.

    Returns:
        List of active BaseResumes to update.
    """
    query = select(BaseResume).where(
        BaseResume.persona_id == persona_id,
        BaseResume.status == "Active",
    )

    if resolution == "added_to_some" and target_resume_ids:
        query = query.where(BaseResume.id.in_(target_resume_ids))

    result = await db.execute(query)
    return list(result.scalars().all())


def _append_to_jsonb_list(
    resume: BaseResume, field_name: str, item_id_str: str
) -> bool:
    """Append an item ID to a JSONB array field if not already present.

    Args:
        resume: The BaseResume to update.
        field_name: Name of the JSONB array field.
        item_id_str: String UUID to append.

    Returns:
        True if the item was added (not already present), False otherwise.
    """
    current_list = list(getattr(resume, field_name))
    if item_id_str in current_list:
        return False
    current_list.append(item_id_str)
    setattr(resume, field_name, current_list)
    return True


def _append_bullet_to_selections(
    resume: BaseResume, work_history_id_str: str, bullet_id_str: str
) -> bool:
    """Append a bullet ID to job_bullet_selections for a specific job.

    Only updates if the job is included in this resume's included_jobs.

    Args:
        resume: The BaseResume to update.
        work_history_id_str: String UUID of the parent job.
        bullet_id_str: String UUID of the bullet to add.

    Returns:
        True if the bullet was added, False if job not in resume or
        bullet already present.
    """
    if work_history_id_str not in resume.included_jobs:
        return False

    selections = dict(resume.job_bullet_selections)
    bullet_list = list(selections.get(work_history_id_str, []))

    if bullet_id_str in bullet_list:
        return False

    bullet_list.append(bullet_id_str)
    selections[work_history_id_str] = bullet_list
    resume.job_bullet_selections = selections
    return True


async def _apply_to_resumes(
    db: AsyncSession,
    flag: PersonaChangeFlag,
    resolution: str,
    target_resume_ids: list[uuid.UUID] | None,
) -> int:
    """Apply a flag's change to the appropriate BaseResume fields.

    Args:
        db: Database session.
        flag: The flag being resolved.
        resolution: added_to_all or added_to_some.
        target_resume_ids: Specific resume IDs for added_to_some.

    Returns:
        Number of BaseResumes actually updated.
    """
    resumes = await _get_target_resumes(
        db, flag.persona_id, resolution, target_resume_ids
    )

    item_id_str = str(flag.item_id)
    updated_count = 0

    if flag.change_type == "bullet_added":
        updated_count = await _apply_bullet_added(
            db, resumes, flag.item_id, item_id_str
        )
    else:
        field_name = _CHANGE_TYPE_TO_FIELD[flag.change_type]
        for resume in resumes:
            if _append_to_jsonb_list(resume, field_name, item_id_str):
                updated_count += 1

    return updated_count


async def _apply_bullet_added(
    db: AsyncSession,
    resumes: list[BaseResume],
    bullet_id: uuid.UUID,
    bullet_id_str: str,
) -> int:
    """Apply bullet_added to job_bullet_selections on target resumes.

    Looks up the bullet's parent work_history_id, then updates only
    resumes that include that job.

    Args:
        db: Database session.
        resumes: Target BaseResumes to potentially update.
        bullet_id: UUID of the bullet.
        bullet_id_str: String form of bullet UUID.

    Returns:
        Number of resumes updated.

    Raises:
        NotFoundError: If the Bullet does not exist.
    """
    bullet = await db.get(Bullet, bullet_id)
    if bullet is None:
        raise NotFoundError("Bullet", str(bullet_id))

    work_history_id_str = str(bullet.work_history_id)
    updated_count = 0

    for resume in resumes:
        if _append_bullet_to_selections(resume, work_history_id_str, bullet_id_str):
            updated_count += 1

    return updated_count
