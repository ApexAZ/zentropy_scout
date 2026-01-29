"""Job Postings API router.

REQ-006 §5.2: Job postings resource with nested and action endpoints.

Endpoints:
- /job-postings - CRUD for job postings
- /job-postings/{id}/extracted-skills - Read-only extracted skills
- /job-postings/ingest - POST raw job text for parsing (Chrome extension)
- /job-postings/ingest/confirm - Confirm ingest preview to create job
- /job-postings/bulk-dismiss - Bulk dismiss jobs
- /job-postings/bulk-favorite - Bulk favorite/unfavorite jobs
- /job-postings/rescore - Re-run Strategist scoring
"""

import hashlib
import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.core.database import get_db
from app.core.errors import ConflictError, NotFoundError
from app.core.responses import DataResponse, ListResponse
from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.models.persona import Persona
from app.schemas.bulk import (
    BulkDismissRequest,
    BulkFailedItem,
    BulkFavoriteRequest,
    BulkOperationResult,
)
from app.schemas.ingest import (
    IngestConfirmRequest,
    IngestJobPostingRequest,
    IngestJobPostingResponse,
    IngestPreview,
)
from app.services.ingest_token_store import get_token_store
from app.services.job_extraction import extract_job_data

router = APIRouter()


# =============================================================================
# Job Postings CRUD
# =============================================================================


@router.get("")
async def list_job_postings(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List job postings for current user.

    Supports filtering by status, is_favorite, fit_score_min, company_name.
    Supports sorting by fit_score, created_at, etc.
    """
    return ListResponse(data=[], meta={"total": 0, "page": 1, "per_page": 20})


@router.post("")
async def create_job_posting(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Create a new job posting manually."""
    return DataResponse(data={})


@router.get("/{job_posting_id}")
async def get_job_posting(
    job_posting_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Get a job posting by ID."""
    return DataResponse(data={})


@router.patch("/{job_posting_id}")
async def update_job_posting(
    job_posting_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Partially update a job posting."""
    return DataResponse(data={})


@router.delete("/{job_posting_id}")
async def delete_job_posting(
    job_posting_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> None:
    """Delete a job posting (soft delete)."""
    return None


# =============================================================================
# Extracted Skills (nested, read-only)
# =============================================================================


@router.get("/{job_posting_id}/extracted-skills")
async def list_extracted_skills(
    job_posting_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> ListResponse[dict]:
    """List skills extracted from job posting by Scouter.

    REQ-006 §5.2: Read-only for clients, populated by Scouter agent.
    """
    return ListResponse(data=[], meta={"total": 0, "page": 1, "per_page": 20})


# =============================================================================
# Action Endpoints
# =============================================================================


@router.post("/ingest")
async def ingest_job_posting(
    request: IngestJobPostingRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DataResponse[IngestJobPostingResponse]:
    """Ingest raw job posting text from Chrome extension.

    REQ-006 §5.6: Chrome extension submits raw job text for parsing.
    Returns a preview with confirmation token for user review.

    Args:
        request: Raw job text and source information.
        user_id: Current user ID from auth.
        db: Database session.

    Returns:
        Preview of extracted data with confirmation token.

    Raises:
        ConflictError: If job from this URL already exists (409).
    """
    # Check for duplicate URL
    source_url_str = str(request.source_url)
    stmt = select(JobPosting).where(JobPosting.source_url == source_url_str)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        raise ConflictError(
            code="DUPLICATE_JOB",
            message="Job from this URL already exists",
            details=[{"existing_id": str(existing.id)}],
        )

    # Extract job data from raw text
    extracted = await extract_job_data(request.raw_text)

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
            {
                "skill_name": s.get("skill_name", ""),
                "importance_level": s.get("importance_level", "Preferred"),
            }
            for s in extracted.get("extracted_skills", [])
        ],
        culture_text=extracted.get("culture_text"),
        description_snippet=extracted.get("description_snippet"),
    )

    # Store preview with token
    token_store = get_token_store()
    token, expires_at = token_store.create(
        user_id=user_id,
        raw_text=request.raw_text,
        source_url=source_url_str,
        source_name=request.source_name,
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
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DataResponse[dict]:
    """Confirm ingest preview to create job posting.

    REQ-006 §5.6: Creates actual JobPosting from confirmed preview.

    Args:
        request: Confirmation token and optional modifications.
        user_id: Current user ID from auth.
        db: Database session.

    Returns:
        Created job posting data.

    Raises:
        NotFoundError: If token is invalid or expired (404).
    """
    # Get and consume the preview token
    token_store = get_token_store()
    preview_data = token_store.consume(request.confirmation_token, user_id)

    if preview_data is None:
        raise NotFoundError("Preview", request.confirmation_token)

    # Look up user's persona
    stmt = select(Persona).where(Persona.user_id == user_id)
    result = await db.execute(stmt)
    persona = result.scalar_one_or_none()
    if persona is None:
        raise NotFoundError("Persona", str(user_id))

    # Look up or create job source for "Extension" type
    source_stmt = select(JobSource).where(JobSource.source_type == "Extension")
    source_result = await db.execute(source_stmt)
    job_source = source_result.scalar_one_or_none()
    if job_source is None:
        # Create default extension source if not exists
        job_source = JobSource(
            source_name="Extension",
            source_type="Extension",
            description="Chrome extension job capture",
        )
        db.add(job_source)
        await db.flush()

    # Merge extracted data with any modifications
    extracted = preview_data.extracted_data.copy()
    if request.modifications:
        extracted.update(request.modifications)

    # Compute description hash for dedup
    description = extracted.get("description_snippet") or preview_data.raw_text[:1000]
    description_hash = hashlib.sha256(description.encode()).hexdigest()[:32]

    # Create the job posting with all required fields
    job_posting = JobPosting(
        persona_id=persona.id,
        source_id=job_source.id,
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
        status="Discovered",
    )

    db.add(job_posting)
    await db.commit()
    await db.refresh(job_posting)

    return DataResponse(
        data={
            "id": str(job_posting.id),
            "job_title": job_posting.job_title,
            "company_name": job_posting.company_name,
            "location": job_posting.location,
            "salary_min": job_posting.salary_min,
            "salary_max": job_posting.salary_max,
            "salary_currency": job_posting.salary_currency,
            "status": job_posting.status,
            "source_url": job_posting.source_url,
            "created_at": job_posting.created_at.isoformat()
            if job_posting.created_at
            else None,
        }
    )


@router.post("/bulk-dismiss")
async def bulk_dismiss_job_postings(
    request: BulkDismissRequest,
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[BulkOperationResult]:
    """Bulk dismiss multiple job postings.

    REQ-006 §2.6: Bulk operations for efficiency.

    Args:
        request: List of job posting IDs to dismiss.

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


@router.post("/bulk-favorite")
async def bulk_favorite_job_postings(
    request: BulkFavoriteRequest,
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[BulkOperationResult]:
    """Bulk favorite/unfavorite multiple job postings.

    REQ-006 §2.6: Bulk operations for efficiency.

    Args:
        request: List of job posting IDs and favorite flag.

    Returns:
        Partial success result with succeeded and failed arrays.

    Raises:
        HTTPException: 400 if request validation fails (invalid UUIDs, missing is_favorite).
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


@router.post("/rescore")
async def rescore_job_postings(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Re-run Strategist scoring on all Discovered jobs.

    REQ-006 §5.2: Trigger after persona changes to update fit scores.
    """
    return DataResponse(data={"status": "queued"})
