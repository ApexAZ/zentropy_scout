"""Job Variants API router.

REQ-006 §5.2: Job-specific resume variants.
REQ-002 §4.3: Job Variant — Snapshot Logic.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from app.api.deps import CurrentUserId, DbSession
from app.core.errors import InvalidStateError, NotFoundError
from app.core.responses import DataResponse, ListResponse, PaginationMeta
from app.models import BaseResume, Persona
from app.models.job_posting import JobPosting
from app.models.resume import JobVariant

_MAX_SUMMARY_LENGTH = 5000
"""Safety bound on summary text length."""

_MAX_MODIFICATIONS_LENGTH = 2000
"""Safety bound on modifications_description text length."""

_MAX_JSONB_DICT_KEYS = 200
"""Safety bound on JSONB dict field key count (defense-in-depth)."""

_MAX_JSONB_LIST_LENGTH = 200
"""Safety bound on JSONB inner list lengths (defense-in-depth)."""

_STATUS_DRAFT = "Draft"
"""Job variant status: editable, not yet approved."""

_STATUS_APPROVED = "Approved"
"""Job variant status: approved and immutable."""

_STATUS_ARCHIVED = "Archived"
"""Job variant status: soft-deleted, hidden from default UI views."""

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class CreateJobVariantRequest(BaseModel):
    """Request body for creating a job variant.

    REQ-002 §4.3: Required fields for job variant creation.
    """

    model_config = ConfigDict(extra="forbid")

    base_resume_id: uuid.UUID
    job_posting_id: uuid.UUID
    summary: str = Field(..., min_length=1, max_length=_MAX_SUMMARY_LENGTH)
    job_bullet_order: dict[str, list[str]] = Field(default={})
    modifications_description: str | None = Field(
        default=None, max_length=_MAX_MODIFICATIONS_LENGTH
    )

    @field_validator("job_bullet_order")
    @classmethod
    def validate_job_bullet_order(cls, v: dict[str, list[str]]) -> dict[str, list[str]]:
        """Enforce size limits on JSONB dict field (defense-in-depth)."""
        if len(v) > _MAX_JSONB_DICT_KEYS:
            msg = f"Too many keys (max {_MAX_JSONB_DICT_KEYS})"
            raise ValueError(msg)
        for values in v.values():
            if len(values) > _MAX_JSONB_LIST_LENGTH:
                msg = f"List too long (max {_MAX_JSONB_LIST_LENGTH})"
                raise ValueError(msg)
        return v


class UpdateJobVariantRequest(BaseModel):
    """Request body for partially updating a draft job variant.

    All fields optional — only provided fields are updated.
    REQ-002 §4.3: Immutable after approval.
    """

    model_config = ConfigDict(extra="forbid")

    summary: str | None = Field(
        default=None, min_length=1, max_length=_MAX_SUMMARY_LENGTH
    )
    job_bullet_order: dict[str, list[str]] | None = None
    modifications_description: str | None = Field(
        default=None, max_length=_MAX_MODIFICATIONS_LENGTH
    )

    @field_validator("job_bullet_order")
    @classmethod
    def validate_job_bullet_order(
        cls, v: dict[str, list[str]] | None
    ) -> dict[str, list[str]] | None:
        """Enforce size limits on JSONB dict field (defense-in-depth)."""
        if v is None:
            return v
        if len(v) > _MAX_JSONB_DICT_KEYS:
            msg = f"Too many keys (max {_MAX_JSONB_DICT_KEYS})"
            raise ValueError(msg)
        for values in v.values():
            if len(values) > _MAX_JSONB_LIST_LENGTH:
                msg = f"List too long (max {_MAX_JSONB_LIST_LENGTH})"
                raise ValueError(msg)
        return v


# =============================================================================
# Helper Functions
# =============================================================================


def _variant_to_dict(variant: JobVariant) -> dict:
    """Convert JobVariant model to API response dict.

    Args:
        variant: The JobVariant model instance.

    Returns:
        Dict with variant data for API response.
    """
    return {
        "id": str(variant.id),
        "base_resume_id": str(variant.base_resume_id),
        "job_posting_id": str(variant.job_posting_id),
        "summary": variant.summary,
        "job_bullet_order": variant.job_bullet_order,
        "modifications_description": variant.modifications_description,
        "status": variant.status,
        "snapshot_included_jobs": variant.snapshot_included_jobs,
        "snapshot_job_bullet_selections": variant.snapshot_job_bullet_selections,
        "snapshot_included_education": variant.snapshot_included_education,
        "snapshot_included_certifications": variant.snapshot_included_certifications,
        "snapshot_skills_emphasis": variant.snapshot_skills_emphasis,
        "approved_at": (
            variant.approved_at.isoformat() if variant.approved_at else None
        ),
        "created_at": variant.created_at.isoformat(),
        "updated_at": variant.updated_at.isoformat(),
        "archived_at": (
            variant.archived_at.isoformat() if variant.archived_at else None
        ),
    }


async def _get_owned_variant(
    variant_id: uuid.UUID, user_id: uuid.UUID, db: DbSession
) -> JobVariant:
    """Fetch a job variant with ownership verification.

    Ownership chain: JobVariant → BaseResume → Persona (user_id).

    Args:
        variant_id: The job variant ID to look up.
        user_id: Current authenticated user ID.
        db: Database session.

    Returns:
        JobVariant instance owned by the user.

    Raises:
        NotFoundError: If variant not found or not owned by user.
    """
    result = await db.execute(
        select(JobVariant)
        .join(BaseResume, JobVariant.base_resume_id == BaseResume.id)
        .join(Persona, BaseResume.persona_id == Persona.id)
        .where(JobVariant.id == variant_id, Persona.user_id == user_id)
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise NotFoundError("job variant", str(variant_id))
    return variant


# =============================================================================
# Endpoints
# =============================================================================


@router.get("")
async def list_job_variants(
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List job variants for current user.

    REQ-006 §5.2: Filtered by current user's persona ownership.

    Args:
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        ListResponse with job variants and pagination meta.
    """
    result = await db.execute(
        select(JobVariant)
        .join(BaseResume, JobVariant.base_resume_id == BaseResume.id)
        .join(Persona, BaseResume.persona_id == Persona.id)
        .where(Persona.user_id == user_id)
        .order_by(JobVariant.created_at.desc())
    )
    variants = result.scalars().all()

    return ListResponse(
        data=[_variant_to_dict(v) for v in variants],
        meta=PaginationMeta(total=len(variants), page=1, per_page=len(variants) or 20),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_job_variant(
    request: CreateJobVariantRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Create a new job variant.

    REQ-002 §4.3: Creates a draft job variant linked to a base resume and job posting.

    Args:
        request: The create request body.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with created job variant.

    Raises:
        NotFoundError: If base resume or job posting not found or not owned by user.
    """
    # Verify base resume ownership
    resume_result = await db.execute(
        select(BaseResume)
        .join(Persona, BaseResume.persona_id == Persona.id)
        .where(BaseResume.id == request.base_resume_id, Persona.user_id == user_id)
    )
    if not resume_result.scalar_one_or_none():
        raise NotFoundError("base resume", str(request.base_resume_id))

    # Verify job posting ownership
    posting_result = await db.execute(
        select(JobPosting)
        .join(Persona, JobPosting.persona_id == Persona.id)
        .where(JobPosting.id == request.job_posting_id, Persona.user_id == user_id)
    )
    if not posting_result.scalar_one_or_none():
        raise NotFoundError("job posting", str(request.job_posting_id))

    variant = JobVariant(
        base_resume_id=request.base_resume_id,
        job_posting_id=request.job_posting_id,
        summary=request.summary,
        job_bullet_order=request.job_bullet_order,
        modifications_description=request.modifications_description,
    )
    db.add(variant)
    await db.commit()
    await db.refresh(variant)

    return DataResponse(data=_variant_to_dict(variant))


@router.get("/{variant_id}")
async def get_job_variant(
    variant_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get a job variant by ID.

    Args:
        variant_id: The job variant ID.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with job variant data.

    Raises:
        NotFoundError: If variant not found or not owned by user.
    """
    variant = await _get_owned_variant(variant_id, user_id, db)
    return DataResponse(data=_variant_to_dict(variant))


@router.patch("/{variant_id}")
async def update_job_variant(
    variant_id: uuid.UUID,
    request: UpdateJobVariantRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Partially update a draft job variant.

    REQ-002 §4.3: Immutable after approval — only Draft variants can be updated.

    Args:
        variant_id: The job variant ID.
        request: The update request body (partial fields).
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with updated job variant.

    Raises:
        NotFoundError: If variant not found or not owned by user.
        InvalidStateError: If variant is not in Draft status.
    """
    variant = await _get_owned_variant(variant_id, user_id, db)

    if variant.status != _STATUS_DRAFT:
        raise InvalidStateError(
            "Only draft job variants can be updated. Approved variants are immutable."
        )

    # Apply only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(variant, field, value)

    variant.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(variant)

    return DataResponse(data=_variant_to_dict(variant))


@router.delete("/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_variant(
    variant_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> Response:
    """Archive a job variant (soft delete).

    Args:
        variant_id: The job variant ID.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        204 No Content on success.

    Raises:
        NotFoundError: If variant not found or not owned by user.
    """
    variant = await _get_owned_variant(variant_id, user_id, db)

    variant.status = _STATUS_ARCHIVED
    variant.archived_at = datetime.now(UTC)
    variant.updated_at = datetime.now(UTC)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{variant_id}/approve")
async def approve_job_variant(
    variant_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Approve a draft job variant and snapshot base resume fields.

    REQ-002 §4.3.2: On approval, copies all inherited fields from the
    BaseResume into snapshot columns, making the variant fully self-contained
    and immutable.

    Args:
        variant_id: The job variant ID to approve.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with approved job variant including snapshot fields.

    Raises:
        NotFoundError: If variant not found or not owned by user.
        InvalidStateError: If variant is not in Draft status.
    """
    variant = await _get_owned_variant(variant_id, user_id, db)

    # Eager-load base_resume for snapshot field copy
    await db.refresh(variant, attribute_names=["base_resume"])

    if variant.status != _STATUS_DRAFT:
        raise InvalidStateError(
            "Only draft job variants can be approved. "
            "This variant is already approved or archived."
        )

    # Snapshot: copy BaseResume selection fields
    base = variant.base_resume
    variant.snapshot_included_jobs = base.included_jobs  # type: ignore[assignment]
    variant.snapshot_job_bullet_selections = base.job_bullet_selections
    variant.snapshot_included_education = base.included_education  # type: ignore[assignment]
    variant.snapshot_included_certifications = base.included_certifications  # type: ignore[assignment]
    variant.snapshot_skills_emphasis = base.skills_emphasis  # type: ignore[assignment]

    variant.status = _STATUS_APPROVED
    variant.approved_at = datetime.now(UTC)
    variant.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(variant)

    return DataResponse(data=_variant_to_dict(variant))


@router.post("/{variant_id}/restore")
async def restore_job_variant(
    variant_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Restore an archived job variant to its pre-archive status.

    REQ-002 §5.4: Restore returns variant to Draft or Approved based on
    whether it was approved before archiving (inferred from approved_at).

    Args:
        variant_id: The job variant ID to restore.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with restored job variant.

    Raises:
        NotFoundError: If variant not found or not owned by user.
        InvalidStateError: If variant is not in Archived status.
    """
    variant = await _get_owned_variant(variant_id, user_id, db)

    if variant.status != _STATUS_ARCHIVED:
        raise InvalidStateError("Only archived job variants can be restored.")

    variant.status = _STATUS_APPROVED if variant.approved_at else _STATUS_DRAFT
    variant.archived_at = None
    variant.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(variant)

    return DataResponse(data=_variant_to_dict(variant))
