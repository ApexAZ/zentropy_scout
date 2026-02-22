"""Job Postings API router.

REQ-015 §9: Shared job pool with persona_jobs pattern.
All user-facing reads/writes go through persona_jobs.
Shared pool data is immutable from user API.

NOTE: This file exceeds 300 lines due to the ingest/confirm flow
(~170 lines) colocated with CRUD and bulk operations. Splitting
would fragment the logical grouping of all job-posting endpoints.

Endpoints:
- /job-postings - CRUD via persona_jobs (shared pool + per-user link)
- /job-postings/{id}/extracted-skills - Read-only extracted skills
- /job-postings/ingest - POST raw job text for parsing (Chrome extension)
- /job-postings/ingest/confirm - Confirm ingest preview to create job
- /job-postings/bulk-dismiss - Bulk dismiss jobs
- /job-postings/bulk-favorite - Bulk favorite/unfavorite jobs
- /job-postings/rescore - Re-run Strategist scoring
"""

import hashlib
import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import CurrentUserId, DbSession
from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.rate_limiting import limiter
from app.core.responses import DataResponse, ListResponse, PaginationMeta
from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.models.persona import Persona
from app.models.persona_job import PersonaJob
from app.repositories.job_posting_repository import JobPostingRepository
from app.repositories.persona_job_repository import PersonaJobRepository
from app.schemas.bulk import (
    BulkDismissRequest,
    BulkFailedItem,
    BulkFavoriteRequest,
    BulkOperationResult,
)
from app.schemas.ingest import (
    ExtractedSkillPreview,
    IngestConfirmRequest,
    IngestJobPostingRequest,
    IngestJobPostingResponse,
    IngestPreview,
)
from app.schemas.job_posting import (
    CreateJobPostingRequest,
    PersonaJobResponse,
    UpdatePersonaJobRequest,
)
from app.services.ingest_token_store import get_token_store
from app.services.job_extraction import extract_job_data

router = APIRouter()

_DISCOVERY_MANUAL = "manual"

# Security: Allowed modification fields for ingest confirm
# Prevents mass assignment of sensitive fields (e.g., id, persona_id, source_id)
ALLOWED_INGEST_MODIFICATIONS: set[str] = {
    "job_title",
    "company_name",
    "location",
    "salary_min",
    "salary_max",
    "salary_currency",
    "employment_type",
    "culture_text",
    "description_snippet",
    "extracted_skills",  # Can override skill list
}

# Security: Type + length constraints for ingest modification values
# Validates user-supplied values before they reach the database
_MODIFICATION_STR_LIMITS: dict[str, int] = {
    "job_title": 500,
    "company_name": 500,
    "location": 500,
    "salary_currency": 10,
    "employment_type": 50,
    "culture_text": 50000,
    "description_snippet": 5000,
}
_MODIFICATION_INT_FIELDS: set[str] = {"salary_min", "salary_max"}


# =============================================================================
# Helpers
# =============================================================================


async def _get_user_persona(db: DbSession, user_id: uuid.UUID) -> Persona:
    """Look up the authenticated user's persona.

    Args:
        db: Database session.
        user_id: Current user ID.

    Returns:
        User's Persona.

    Raises:
        NotFoundError: If user has no persona.
    """
    result = await db.execute(select(Persona).where(Persona.user_id == user_id))
    persona = result.scalar_one_or_none()
    if persona is None:
        raise NotFoundError("Persona", str(user_id))
    return persona


async def _get_or_create_source(db: DbSession, source_type: str) -> JobSource:
    """Look up or create a JobSource by type.

    Args:
        db: Database session.
        source_type: Source type (Extension, Manual, etc.).

    Returns:
        JobSource instance.
    """
    result = await db.execute(
        select(JobSource).where(JobSource.source_type == source_type)
    )
    source = result.scalar_one_or_none()
    if source is None:
        source = JobSource(
            source_name=source_type,
            source_type=source_type,
            description=f"Jobs from {source_type.lower()} source",
        )
        db.add(source)
        await db.flush()
    return source


def _compute_description_hash(text: str) -> str:
    """Compute SHA-256 hash of description for dedup.

    Args:
        text: Description text to hash.

    Returns:
        64-char hex digest string.
    """
    return hashlib.sha256(text.encode()).hexdigest()


# =============================================================================
# Job Postings CRUD
# =============================================================================


@router.get("")
async def list_job_postings(
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[PersonaJobResponse]:
    """List job postings for current user.

    REQ-015 §9.1: Returns persona_jobs joined with shared job data,
    filtered by user's personas.
    """
    persona_jobs = await PersonaJobRepository.get_all_for_user(db, user_id=user_id)
    items = [PersonaJobResponse.model_validate(pj) for pj in persona_jobs]
    return ListResponse(
        data=items,
        meta=PaginationMeta(total=len(items), page=1, per_page=max(len(items), 20)),
    )


@router.post("", status_code=201)
async def create_job_posting(
    request: CreateJobPostingRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[PersonaJobResponse]:
    """Create a new job posting manually.

    REQ-015 §9.1: Creates in shared pool + persona_jobs link.
    Dedup check first — if job with same description_hash exists,
    just creates the persona_jobs link.

    Raises:
        ConflictError: If user already has a link to this job (409).
    """
    persona = await _get_user_persona(db, user_id)
    description_hash = _compute_description_hash(request.description)

    # Dedup: check if job with this hash already exists
    existing_job = await JobPostingRepository.get_by_description_hash(
        db, description_hash
    )

    if existing_job is not None:
        # Check if user already has a link to this job
        existing_link = await PersonaJobRepository.get_by_persona_and_job(
            db,
            persona_id=persona.id,
            job_posting_id=existing_job.id,
            user_id=user_id,
        )
        if existing_link is not None:
            raise ConflictError(
                code="DUPLICATE_JOB",
                message="You already have this job in your list",
                details=[{"existing_id": str(existing_link.id)}],
            )

        # Create persona_jobs link to existing job
        persona_job = await PersonaJobRepository.create(
            db,
            persona_id=persona.id,
            job_posting_id=existing_job.id,
            discovery_method=_DISCOVERY_MANUAL,
            user_id=user_id,
        )
    else:
        # Create new job in shared pool
        source = await _get_or_create_source(db, "Manual")
        job_posting = await JobPostingRepository.create(
            db,
            source_id=source.id,
            job_title=request.job_title,
            company_name=request.company_name,
            description=request.description,
            description_hash=description_hash,
            first_seen_date=date.today(),
            source_url=request.source_url,
            location=request.location,
            work_model=request.work_model,
            seniority_level=request.seniority_level,
            salary_min=request.salary_min,
            salary_max=request.salary_max,
            salary_currency=request.salary_currency,
            culture_text=request.culture_text,
            requirements=request.requirements,
        )

        # Create persona_jobs link
        persona_job = await PersonaJobRepository.create(
            db,
            persona_id=persona.id,
            job_posting_id=job_posting.id,
            discovery_method=_DISCOVERY_MANUAL,
            user_id=user_id,
        )

    if persona_job is None:
        raise NotFoundError("Persona", str(persona.id))

    await db.commit()

    # Re-fetch with relationship loaded for response
    result = await PersonaJobRepository.get_by_id(db, persona_job.id, user_id=user_id)
    return DataResponse(data=PersonaJobResponse.model_validate(result))


@router.get("/{persona_job_id}")
async def get_job_posting(
    persona_job_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[PersonaJobResponse]:
    """Get a job posting by persona_job ID.

    REQ-015 §9.1: Lookup via persona_jobs. Returns 404 if user has
    no link to this job, preventing shared pool browsing.
    """
    persona_job = await PersonaJobRepository.get_by_id(
        db, persona_job_id, user_id=user_id
    )
    if persona_job is None:
        raise NotFoundError("PersonaJob", str(persona_job_id))

    return DataResponse(data=PersonaJobResponse.model_validate(persona_job))


@router.patch("/{persona_job_id}")
async def update_job_posting(
    persona_job_id: uuid.UUID,
    request: UpdatePersonaJobRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[PersonaJobResponse]:
    """Partially update a job posting's per-user fields.

    REQ-015 §9.1: Updates persona_jobs fields only. Shared job data
    is immutable from user API.
    """
    update_data = request.model_dump(exclude_unset=True)

    # Auto-set dismissed_at when status changes to Dismissed
    if update_data.get("status") == "Dismissed":
        update_data["dismissed_at"] = datetime.now(UTC)

    persona_job = await PersonaJobRepository.update(
        db, persona_job_id, user_id=user_id, **update_data
    )
    if persona_job is None:
        raise NotFoundError("PersonaJob", str(persona_job_id))

    await db.commit()
    return DataResponse(data=PersonaJobResponse.model_validate(persona_job))


@router.delete("/{persona_job_id}")
async def delete_job_posting(
    persona_job_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> None:
    """Delete a job posting (soft delete).

    NOTE: Stub — shared pool jobs are dismissed, not deleted.
    """
    return None


# =============================================================================
# Extracted Skills (nested, read-only)
# =============================================================================


@router.get("/{persona_job_id}/extracted-skills")
async def list_extracted_skills(
    persona_job_id: uuid.UUID,  # noqa: ARG001
    _user_id: CurrentUserId,
) -> ListResponse[dict]:
    """List skills extracted from job posting by Scouter.

    REQ-006 §5.2: Read-only for clients, populated by Scouter agent.
    """
    return ListResponse(data=[], meta=PaginationMeta(total=0, page=1, per_page=20))


# =============================================================================
# Ingest Endpoints
# =============================================================================


@router.post("/ingest")
@limiter.limit(settings.rate_limit_llm)
async def ingest_job_posting(
    request: Request,  # noqa: ARG001 - Required by rate limiter
    body: IngestJobPostingRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[IngestJobPostingResponse]:
    """Ingest raw job posting text from Chrome extension.

    REQ-006 §5.6: Chrome extension submits raw job text for parsing.
    Returns a preview with confirmation token for user review.
    Security: Rate limited to prevent LLM cost abuse.

    Args:
        request: HTTP request (required by rate limiter).
        body: Raw job text and source information.
        user_id: Current user ID from auth.
        db: Database session.

    Returns:
        Preview of extracted data with confirmation token.

    Raises:
        ConflictError: If job from this URL already exists (409).
    """
    # Check for duplicate URL scoped to current user (REQ-014 §5.2)
    source_url_str = str(body.source_url) if body.source_url is not None else None
    if source_url_str is not None:
        stmt = (
            select(JobPosting)
            .join(PersonaJob, PersonaJob.job_posting_id == JobPosting.id)
            .join(Persona, PersonaJob.persona_id == Persona.id)
            .where(JobPosting.source_url == source_url_str, Persona.user_id == user_id)
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            raise ConflictError(
                code="DUPLICATE_JOB",
                message="Job from this URL already exists",
                details=[{"existing_id": str(existing.id)}],
            )

    # Extract job data from raw text
    extracted = await extract_job_data(body.raw_text)

    # Build preview from extracted data
    preview = IngestPreview(
        job_title=extracted.get("job_title"),
        company_name=extracted.get("company_name"),
        location=extracted.get("location"),
        salary_min=extracted.get("salary_min"),
        salary_max=extracted.get("salary_max"),
        salary_currency=extracted.get("salary_currency"),
        employment_type=extracted.get("employment_type"),
        extracted_skills=[
            ExtractedSkillPreview(
                skill_name=s.get("skill_name", ""),
                skill_type=s.get("skill_type", "Hard"),
                is_required=s.get("is_required", True),
                years_requested=s.get("years_requested"),
            )
            for s in extracted.get("extracted_skills", [])
        ],
        culture_text=extracted.get("culture_text"),
        description_snippet=extracted.get("description_snippet"),
    )

    # Store preview with token
    token_store = get_token_store()
    token, expires_at = token_store.create(
        user_id=user_id,
        raw_text=body.raw_text,
        source_url=source_url_str or "",
        source_name=body.source_name,
        extracted_data=extracted,
    )

    return DataResponse(
        data=IngestJobPostingResponse(
            preview=preview,
            confirmation_token=token,
            expires_at=expires_at,
        )
    )


@router.post("/ingest/confirm", status_code=201)
async def confirm_ingest_job_posting(
    request: IngestConfirmRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[PersonaJobResponse]:
    """Confirm ingest preview to create job posting.

    REQ-015 §9.1: Creates in shared pool + persona_jobs link.

    Args:
        request: Confirmation token and optional modifications.
        user_id: Current user ID from auth.
        db: Database session.

    Returns:
        Created PersonaJobResponse with nested job data.

    Raises:
        NotFoundError: If token is invalid or expired (404).
    """
    # Get and consume the preview token
    token_store = get_token_store()
    preview_data = token_store.consume(request.confirmation_token, user_id)

    if preview_data is None:
        raise NotFoundError("Preview")

    persona = await _get_user_persona(db, user_id)
    source = await _get_or_create_source(db, "Extension")

    # Merge extracted data with any modifications
    extracted: dict[str, Any] = dict(preview_data.extracted_data)
    if request.modifications:
        # Security: Validate modification keys against whitelist
        invalid_keys = set(request.modifications.keys()) - ALLOWED_INGEST_MODIFICATIONS
        if invalid_keys:
            raise ValidationError(
                message=f"Invalid modification keys: {', '.join(sorted(invalid_keys))}",
                details=[
                    {"field": key, "error": "FIELD_NOT_ALLOWED"} for key in invalid_keys
                ],
            )

        # Security: Validate modification value types and lengths
        for key, value in request.modifications.items():
            if key == "extracted_skills":
                if not isinstance(value, list):
                    raise ValidationError(
                        message=f"'{key}' must be a list",
                        details=[{"field": key, "error": "INVALID_TYPE"}],
                    )
                continue
            if key in _MODIFICATION_INT_FIELDS:
                if not isinstance(value, int) or isinstance(value, bool):
                    raise ValidationError(
                        message=f"'{key}' must be an integer",
                        details=[{"field": key, "error": "INVALID_TYPE"}],
                    )
                continue
            max_len = _MODIFICATION_STR_LIMITS.get(key)
            if max_len and isinstance(value, str) and len(value) > max_len:
                raise ValidationError(
                    message=f"'{key}' exceeds maximum length ({max_len})",
                    details=[{"field": key, "error": "VALUE_TOO_LONG"}],
                )

        extracted.update(request.modifications)

    # Compute description hash for dedup
    description = extracted.get("description_snippet") or preview_data.raw_text[:1000]
    description_hash = _compute_description_hash(description)

    # Create the shared job posting (Tier 0 — no per-user fields)
    job_posting = JobPosting(
        source_id=source.id,
        source_url=preview_data.source_url,
        raw_text=preview_data.raw_text,
        job_title=extracted.get("job_title") or "Unknown Title",
        company_name=extracted.get("company_name") or "Unknown Company",
        location=extracted.get("location"),
        salary_min=extracted.get("salary_min"),
        salary_max=extracted.get("salary_max"),
        salary_currency=extracted.get("salary_currency"),
        culture_text=extracted.get("culture_text"),
        description=description,
        description_hash=description_hash,
        first_seen_date=date.today(),
    )

    db.add(job_posting)
    await db.flush()

    # Create per-user link (PersonaJob)
    persona_job = PersonaJob(
        persona_id=persona.id,
        job_posting_id=job_posting.id,
        status="Discovered",
        discovery_method=_DISCOVERY_MANUAL,
    )
    db.add(persona_job)

    await db.commit()

    # Re-fetch with relationship loaded for PersonaJobResponse
    result = await PersonaJobRepository.get_by_id(db, persona_job.id, user_id=user_id)
    return DataResponse(data=PersonaJobResponse.model_validate(result))


# =============================================================================
# Bulk Operations
# =============================================================================


@router.post("/bulk-dismiss")
async def bulk_dismiss_job_postings(
    request: BulkDismissRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[BulkOperationResult]:
    """Bulk dismiss multiple job postings.

    REQ-015 §9.1: Updates persona_jobs status to Dismissed.
    Only affects jobs owned by the authenticated user.
    """
    if not request.ids:
        return DataResponse(data=BulkOperationResult())

    # Find which requested IDs are owned by this user
    owned_stmt = (
        select(PersonaJob.id)
        .join(Persona, PersonaJob.persona_id == Persona.id)
        .where(PersonaJob.id.in_(request.ids), Persona.user_id == user_id)
    )
    result = await db.execute(owned_stmt)
    owned_ids = {row[0] for row in result.all()}

    # Update owned persona_jobs
    if owned_ids:
        await PersonaJobRepository.bulk_update_status(
            db,
            persona_job_ids=list(owned_ids),
            user_id=user_id,
            status="Dismissed",
            dismissed_at=datetime.now(UTC),
        )
        await db.commit()

    succeeded = [str(id_) for id_ in request.ids if id_ in owned_ids]
    failed = [
        BulkFailedItem(id=str(id_), error="NOT_FOUND")
        for id_ in request.ids
        if id_ not in owned_ids
    ]
    return DataResponse(data=BulkOperationResult(succeeded=succeeded, failed=failed))


@router.post("/bulk-favorite")
async def bulk_favorite_job_postings(
    request: BulkFavoriteRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[BulkOperationResult]:
    """Bulk favorite/unfavorite multiple job postings.

    REQ-015 §9.1: Updates persona_jobs is_favorite flag.
    Only affects jobs owned by the authenticated user.
    """
    if not request.ids:
        return DataResponse(data=BulkOperationResult())

    # Find which requested IDs are owned by this user
    owned_stmt = (
        select(PersonaJob.id)
        .join(Persona, PersonaJob.persona_id == Persona.id)
        .where(PersonaJob.id.in_(request.ids), Persona.user_id == user_id)
    )
    result = await db.execute(owned_stmt)
    owned_ids = {row[0] for row in result.all()}

    # Update owned persona_jobs
    if owned_ids:
        await PersonaJobRepository.bulk_update_favorite(
            db,
            persona_job_ids=list(owned_ids),
            user_id=user_id,
            is_favorite=request.is_favorite,
        )
        await db.commit()

    succeeded = [str(id_) for id_ in request.ids if id_ in owned_ids]
    failed = [
        BulkFailedItem(id=str(id_), error="NOT_FOUND")
        for id_ in request.ids
        if id_ not in owned_ids
    ]
    return DataResponse(data=BulkOperationResult(succeeded=succeeded, failed=failed))


@router.post("/rescore")
@limiter.limit(settings.rate_limit_llm)
async def rescore_job_postings(
    request: Request,  # noqa: ARG001 - Required by rate limiter
    _user_id: CurrentUserId,
) -> DataResponse[dict]:
    """Re-run Strategist scoring on all Discovered jobs.

    REQ-006 §5.2: Trigger after persona changes to update fit scores.
    Security: Rate limited to prevent LLM cost abuse.
    """
    return DataResponse(data={"status": "queued"})
