"""Base Resumes API router.

REQ-006 §5.2: Base resumes CRUD, filtered by current user's persona.
REQ-002 §4.2: Base Resume — Rendered Document Storage.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import BalanceCheck, CurrentUserId, DbSession, MeteredProvider
from app.core.errors import (
    ConflictError,
    InvalidStateError,
    NotFoundError,
    ValidationError,
)
from app.core.file_validation import sanitize_filename_for_header
from app.core.responses import DataResponse, ListResponse, PaginationMeta
from app.models import BaseResume, Persona
from app.models.resume_template import ResumeTemplate
from app.schemas.resume import GenerateResumeRequest, GenerateResumeResponse
from app.services.markdown_docx_renderer import render_docx
from app.services.markdown_pdf_renderer import render_pdf
from app.services.pdf_generation import render_base_resume_pdf
from app.services.resume_generation_service import llm_generate, template_fill

_MAX_JSONB_LIST_LENGTH = 200
"""Safety bound on JSONB list field lengths (defense-in-depth)."""

_MAX_SUMMARY_LENGTH = 5000
"""Safety bound on summary text length."""

_STATUS_ACTIVE = "Active"
"""Base resume status: normal state, visible in UI."""

_STATUS_ARCHIVED = "Archived"
"""Base resume status: soft-deleted, hidden from default UI views."""

router = APIRouter()


# =============================================================================
# Request/Response Schemas
# =============================================================================


class CreateBaseResumeRequest(BaseModel):
    """Request body for creating a base resume.

    REQ-002 §4.2: Required fields for base resume creation.
    """

    model_config = ConfigDict(extra="forbid")

    persona_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=100)
    role_type: str = Field(..., min_length=1, max_length=255)
    summary: str = Field(..., min_length=1, max_length=_MAX_SUMMARY_LENGTH)
    included_jobs: list[str] = Field(default=[], max_length=_MAX_JSONB_LIST_LENGTH)
    included_education: list[str] = Field(default=[], max_length=_MAX_JSONB_LIST_LENGTH)
    included_certifications: list[str] = Field(
        default=[], max_length=_MAX_JSONB_LIST_LENGTH
    )
    skills_emphasis: list[str] = Field(default=[], max_length=_MAX_JSONB_LIST_LENGTH)
    job_bullet_selections: dict[str, list[str]] = Field(default={})
    job_bullet_order: dict[str, list[str]] = Field(default={})
    is_primary: bool = False
    display_order: int = Field(default=0, ge=0, le=10000)
    # REQ-025 §4.1: Markdown content and template reference
    markdown_content: str | None = None
    template_id: uuid.UUID | None = None


class UpdateBaseResumeRequest(BaseModel):
    """Request body for partially updating a base resume.

    All fields optional — only provided fields are updated.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    role_type: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(
        default=None, min_length=1, max_length=_MAX_SUMMARY_LENGTH
    )
    included_jobs: list[str] | None = Field(
        default=None, max_length=_MAX_JSONB_LIST_LENGTH
    )
    included_education: list[str] | None = Field(
        default=None, max_length=_MAX_JSONB_LIST_LENGTH
    )
    included_certifications: list[str] | None = Field(
        default=None, max_length=_MAX_JSONB_LIST_LENGTH
    )
    skills_emphasis: list[str] | None = Field(
        default=None, max_length=_MAX_JSONB_LIST_LENGTH
    )
    job_bullet_selections: dict[str, list[str]] | None = None
    job_bullet_order: dict[str, list[str]] | None = None
    is_primary: bool | None = None
    display_order: int | None = Field(default=None, ge=0, le=10000)
    # REQ-025 §4.1: Markdown content and template reference
    markdown_content: str | None = None
    template_id: uuid.UUID | None = None


# =============================================================================
# Helper Functions
# =============================================================================


def _resume_to_dict(resume: BaseResume) -> dict:
    """Convert BaseResume model to API response dict.

    Excludes rendered_document binary — use download endpoint instead.

    Args:
        resume: The BaseResume model instance.

    Returns:
        Dict with resume data for API response.
    """
    return {
        "id": str(resume.id),
        "persona_id": str(resume.persona_id),
        "name": resume.name,
        "role_type": resume.role_type,
        "summary": resume.summary,
        "included_jobs": resume.included_jobs,
        "included_education": resume.included_education,
        "included_certifications": resume.included_certifications,
        "skills_emphasis": resume.skills_emphasis,
        "job_bullet_selections": resume.job_bullet_selections,
        "job_bullet_order": resume.job_bullet_order,
        "markdown_content": resume.markdown_content,
        "template_id": str(resume.template_id) if resume.template_id else None,
        "rendered_at": resume.rendered_at.isoformat() if resume.rendered_at else None,
        "is_primary": resume.is_primary,
        "status": resume.status,
        "display_order": resume.display_order,
        "created_at": resume.created_at.isoformat(),
        "updated_at": resume.updated_at.isoformat(),
        "archived_at": resume.archived_at.isoformat() if resume.archived_at else None,
    }


async def _get_owned_resume(
    resume_id: uuid.UUID, user_id: uuid.UUID, db: DbSession
) -> BaseResume:
    """Fetch a base resume with ownership verification.

    Args:
        resume_id: The base resume ID to look up.
        user_id: Current authenticated user ID.
        db: Database session.

    Returns:
        BaseResume instance owned by the user.

    Raises:
        NotFoundError: If resume not found or not owned by user.
    """
    result = await db.execute(
        select(BaseResume)
        .join(Persona, BaseResume.persona_id == Persona.id)
        .where(BaseResume.id == resume_id, Persona.user_id == user_id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise NotFoundError("BaseResume", str(resume_id))
    return resume


# =============================================================================
# Endpoints
# =============================================================================


@router.get("")
async def list_base_resumes(
    user_id: CurrentUserId,
    db: DbSession,
) -> ListResponse[dict]:
    """List base resumes for current user.

    REQ-006 §5.2: Filtered by current user's persona ownership.

    Args:
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        ListResponse with base resumes and pagination meta.
    """
    result = await db.execute(
        select(BaseResume)
        .join(Persona, BaseResume.persona_id == Persona.id)
        .where(Persona.user_id == user_id)
        .order_by(BaseResume.display_order, BaseResume.created_at.desc())
    )
    resumes = result.scalars().all()

    return ListResponse(
        data=[_resume_to_dict(r) for r in resumes],
        meta=PaginationMeta(total=len(resumes), page=1, per_page=len(resumes) or 20),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_base_resume(
    request: CreateBaseResumeRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Create a new base resume.

    REQ-002 §4.2: Creates a base resume linked to a user's persona.

    Args:
        request: The create request body.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with created base resume.

    Raises:
        NotFoundError: If persona not found or not owned by user.
        ConflictError: If name already exists for this persona.
    """
    # Verify persona ownership
    persona_result = await db.execute(
        select(Persona).where(
            Persona.id == request.persona_id, Persona.user_id == user_id
        )
    )
    persona = persona_result.scalar_one_or_none()
    if not persona:
        raise NotFoundError("Persona", str(request.persona_id))

    resume = BaseResume(
        persona_id=request.persona_id,
        name=request.name,
        role_type=request.role_type,
        summary=request.summary,
        included_jobs=request.included_jobs,
        included_education=request.included_education,
        included_certifications=request.included_certifications,
        skills_emphasis=request.skills_emphasis,
        job_bullet_selections=request.job_bullet_selections,
        job_bullet_order=request.job_bullet_order,
        is_primary=request.is_primary,
        display_order=request.display_order,
    )
    db.add(resume)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictError(
            code="DUPLICATE_NAME",
            message="A base resume with this name already exists for this persona.",
        ) from None

    await db.refresh(resume)
    return DataResponse(data=_resume_to_dict(resume))


@router.get("/{resume_id}")
async def get_base_resume(
    resume_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Get a base resume by ID.

    Args:
        resume_id: The base resume ID.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with base resume data.

    Raises:
        NotFoundError: If resume not found or not owned by user.
    """
    resume = await _get_owned_resume(resume_id, user_id, db)
    return DataResponse(data=_resume_to_dict(resume))


@router.patch("/{resume_id}")
async def update_base_resume(
    resume_id: uuid.UUID,
    request: UpdateBaseResumeRequest,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Partially update a base resume.

    Args:
        resume_id: The base resume ID.
        request: The update request body (partial fields).
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with updated base resume.

    Raises:
        NotFoundError: If resume not found or not owned by user.
    """
    resume = await _get_owned_resume(resume_id, user_id, db)

    # Apply only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(resume, field, value)

    resume.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(resume)

    return DataResponse(data=_resume_to_dict(resume))


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_base_resume(
    resume_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> Response:
    """Archive a base resume (soft delete).

    REQ-002 §5.1: Base Resumes are never hard deleted — DELETE archives.

    Args:
        resume_id: The base resume ID.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        204 No Content on success.

    Raises:
        NotFoundError: If resume not found or not owned by user.
    """
    resume = await _get_owned_resume(resume_id, user_id, db)

    resume.status = _STATUS_ARCHIVED
    resume.archived_at = datetime.now(UTC)
    resume.updated_at = datetime.now(UTC)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{resume_id}/restore")
async def restore_base_resume(
    resume_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Restore an archived base resume to Active.

    REQ-002 §5.4: Restore sets status back to Active and clears archived_at.

    Args:
        resume_id: The base resume ID.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with restored base resume.

    Raises:
        NotFoundError: If resume not found or not owned by user.
        InvalidStateError: If resume is not in Archived status.
    """
    resume = await _get_owned_resume(resume_id, user_id, db)

    if resume.status != _STATUS_ARCHIVED:
        raise InvalidStateError("Only archived base resumes can be restored.")

    resume.status = _STATUS_ACTIVE
    resume.archived_at = None
    resume.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(resume)

    return DataResponse(data=_resume_to_dict(resume))


@router.post("/{resume_id}/render")
async def render_base_resume(
    resume_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> DataResponse[dict]:
    """Render (or re-render) the base resume PDF.

    REQ-012 §9.2: "Re-render PDF" button triggers PDF generation.
    Stores the rendered bytes in rendered_document and sets rendered_at.

    Args:
        resume_id: The base resume ID.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with updated base resume (includes new rendered_at).

    Raises:
        NotFoundError: If resume not found or not owned by user.
    """
    resume = await _get_owned_resume(resume_id, user_id, db)

    pdf_bytes = await render_base_resume_pdf(db, resume.id)
    resume.rendered_document = pdf_bytes
    resume.rendered_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(resume)

    return DataResponse(data=_resume_to_dict(resume))


@router.get("/{resume_id}/download")
async def download_base_resume(
    resume_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> StreamingResponse:
    """Download rendered anchor PDF for base resume.

    REQ-006 §5.2, §2.7: File download endpoint.

    Args:
        resume_id: The base resume ID to download.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        StreamingResponse with PDF binary and Content-Disposition header.

    Raises:
        NotFoundError: If resume not found, not owned by user, or no rendered document.
    """
    resume = await _get_owned_resume(resume_id, user_id, db)

    if not resume.rendered_document:
        raise NotFoundError("BaseResume", str(resume_id))

    # Security: sanitize filename to prevent header injection
    safe_filename = sanitize_filename_for_header(f"{resume.name.replace(' ', '_')}.pdf")

    return StreamingResponse(
        iter([resume.rendered_document]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


_DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@router.get("/{resume_id}/export/pdf")
async def export_base_resume_pdf(
    resume_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> Response:
    """Export base resume markdown as PDF download.

    REQ-025 §5.4: Renders markdown_content to PDF via ReportLab.

    Args:
        resume_id: The base resume ID to export.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        Response with PDF binary and Content-Disposition header.

    Raises:
        NotFoundError: If resume not found or not owned by user.
        InvalidStateError: If markdown_content is NULL.
    """
    resume = await _get_owned_resume(resume_id, user_id, db)

    if not resume.markdown_content:
        raise InvalidStateError(
            "Cannot export: resume has no markdown content. "
            "Generate or write content first."
        )

    pdf_bytes = render_pdf(resume.markdown_content)
    safe_filename = sanitize_filename_for_header(f"{resume.name.replace(' ', '_')}.pdf")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


@router.get("/{resume_id}/export/docx")
async def export_base_resume_docx(
    resume_id: uuid.UUID,
    user_id: CurrentUserId,
    db: DbSession,
) -> Response:
    """Export base resume markdown as DOCX download.

    REQ-025 §5.4: Renders markdown_content to DOCX via python-docx.

    Args:
        resume_id: The base resume ID to export.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        Response with DOCX binary and Content-Disposition header.

    Raises:
        NotFoundError: If resume not found or not owned by user.
        InvalidStateError: If markdown_content is NULL.
    """
    resume = await _get_owned_resume(resume_id, user_id, db)

    if not resume.markdown_content:
        raise InvalidStateError(
            "Cannot export: resume has no markdown content. "
            "Generate or write content first."
        )

    docx_bytes = render_docx(resume.markdown_content)
    safe_filename = sanitize_filename_for_header(
        f"{resume.name.replace(' ', '_')}.docx"
    )

    return Response(
        content=docx_bytes,
        media_type=_DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


@router.post("/{resume_id}/generate")
async def generate_resume(
    resume_id: uuid.UUID,
    request: GenerateResumeRequest,
    user_id: CurrentUserId,
    db: DbSession,
    provider: MeteredProvider,
    _balance: BalanceCheck,
) -> DataResponse[dict]:
    """Generate resume content via LLM or deterministic template fill.

    REQ-026 §4.6, §3.4: Forks on ``method`` parameter.
    - ``"ai"``: LLM-assisted generation (requires credits).
    - ``"template_fill"``: Deterministic fill (free, no LLM).

    Both paths save the result to ``resume.markdown_content``.

    Args:
        resume_id: The base resume ID.
        request: Generation request with method, options.
        user_id: Current authenticated user (injected).
        db: Database session (injected).
        provider: Metered LLM provider (injected via DI).
        _balance: Balance gate (injected, raises 402 if insufficient).

    Returns:
        DataResponse with GenerateResumeResponse fields.

    Raises:
        NotFoundError: If resume not found or not owned by user.
        ValidationError: If template not found or not resolvable.
        InsufficientBalanceError: If balance too low for AI method (402).
    """
    resume = await _get_owned_resume(resume_id, user_id, db)

    # Resolve template: request > resume's template_id
    template_id = request.template_id or resume.template_id
    if template_id is None:
        raise ValidationError(
            "A template is required for generation. "
            "Provide template_id in the request or set it on the resume."
        )

    # Access control: only system templates or user's own templates
    result = await db.execute(
        select(ResumeTemplate).where(
            ResumeTemplate.id == template_id,
            or_(
                ResumeTemplate.is_system.is_(True),
                ResumeTemplate.user_id == user_id,
            ),
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise NotFoundError("ResumeTemplate", str(template_id))

    if request.method == "template_fill":
        markdown = await template_fill(resume, template, db)
        model_used = None
        cost_cents = 0
    else:
        markdown, metadata = await llm_generate(
            resume=resume,
            template=template,
            session=db,
            provider=provider,
            page_limit=request.page_limit,
            emphasis=request.emphasis,
            include_sections=request.include_sections,
        )
        model_used = metadata.get("model")
        cost_cents = 0  # Metering handles billing; endpoint reports 0

    # Save generated content to resume
    resume.markdown_content = markdown
    resume.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(resume)

    word_count = len(markdown.split())

    response_data = GenerateResumeResponse(
        markdown_content=markdown,
        word_count=word_count,
        method=request.method,
        model_used=model_used,
        generation_cost_cents=cost_cents,
    )

    return DataResponse(data=response_data.model_dump())
