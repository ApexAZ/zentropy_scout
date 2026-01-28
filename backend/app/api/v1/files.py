"""File Upload/Download API router.

REQ-006 §2.7, §5.2: File handling endpoints.

All files are stored as BYTEA in PostgreSQL (no S3, no filesystem paths).
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.core.database import get_db
from app.core.errors import NotFoundError, ValidationError
from app.core.responses import DataResponse, ListResponse
from app.models import BaseResume, Persona, ResumeFile
from app.models.cover_letter import SubmittedCoverLetterPDF
from app.models.resume import SubmittedResumePDF

router = APIRouter()


# =============================================================================
# Resume Files (upload, list, get, download)
# =============================================================================

resume_files_router = APIRouter()


@resume_files_router.post("")
async def upload_resume_file(
    file: UploadFile = File(...),  # noqa: B008
    persona_id: uuid.UUID = Form(...),  # noqa: B008
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DataResponse[dict]:
    """Upload original resume file during onboarding.

    REQ-006 §2.7: File upload stored as BYTEA in PostgreSQL.

    Args:
        file: The uploaded file (PDF or DOCX).
        persona_id: The persona to associate the file with.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with file metadata (id, file_name, file_type, etc.).

    Raises:
        NotFoundError: If persona not found or not owned by user.
        ValidationError: If file type is not PDF or DOCX.
    """
    # Verify persona exists and belongs to user
    result = await db.execute(
        select(Persona).where(Persona.id == persona_id, Persona.user_id == user_id)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise NotFoundError("Persona", str(persona_id))

    # Determine file type from extension
    filename = file.filename or "unknown"
    extension = filename.rsplit(".", 1)[-1].upper() if "." in filename else ""

    if extension == "PDF":
        file_type = "PDF"
    elif extension == "DOCX":
        file_type = "DOCX"
    else:
        raise ValidationError(
            message=f"Invalid file type '{extension}'. Allowed: PDF, DOCX",
            details=[{"field": "file", "error": "INVALID_FILE_TYPE"}],
        )

    # Read file content
    content = await file.read()

    # Create resume file record
    resume_file = ResumeFile(
        persona_id=persona_id,
        file_name=filename,
        file_type=file_type,
        file_size_bytes=len(content),
        file_binary=content,
        is_active=True,
    )
    db.add(resume_file)
    await db.commit()
    await db.refresh(resume_file)

    return DataResponse(
        data={
            "id": str(resume_file.id),
            "file_name": resume_file.file_name,
            "file_type": resume_file.file_type,
            "file_size_bytes": resume_file.file_size_bytes,
            "uploaded_at": resume_file.uploaded_at.isoformat(),
            "is_active": resume_file.is_active,
        }
    )


@resume_files_router.get("")
async def list_resume_files(
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ListResponse[dict]:
    """List resume files for current user.

    REQ-006 §5.2: Filter by user's personas.

    Args:
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        ListResponse with file metadata (no binary content).
    """
    # Get files from user's personas
    result = await db.execute(
        select(ResumeFile)
        .join(Persona, ResumeFile.persona_id == Persona.id)
        .where(Persona.user_id == user_id)
        .order_by(ResumeFile.uploaded_at.desc())
    )
    files = result.scalars().all()

    return ListResponse(
        data=[
            {
                "id": str(f.id),
                "persona_id": str(f.persona_id),
                "file_name": f.file_name,
                "file_type": f.file_type,
                "file_size_bytes": f.file_size_bytes,
                "uploaded_at": f.uploaded_at.isoformat(),
                "is_active": f.is_active,
            }
            for f in files
        ],
        meta={"total": len(files), "page": 1, "per_page": len(files)},
    )


@resume_files_router.get("/{file_id}")
async def get_resume_file(
    file_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> DataResponse[dict]:
    """Get resume file metadata by ID.

    Args:
        file_id: The file ID to retrieve.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        DataResponse with file metadata (no binary content).

    Raises:
        NotFoundError: If file not found or not owned by user.
    """
    result = await db.execute(
        select(ResumeFile)
        .join(Persona, ResumeFile.persona_id == Persona.id)
        .where(ResumeFile.id == file_id, Persona.user_id == user_id)
    )
    resume_file = result.scalar_one_or_none()
    if not resume_file:
        raise NotFoundError("ResumeFile", str(file_id))

    return DataResponse(
        data={
            "id": str(resume_file.id),
            "persona_id": str(resume_file.persona_id),
            "file_name": resume_file.file_name,
            "file_type": resume_file.file_type,
            "file_size_bytes": resume_file.file_size_bytes,
            "uploaded_at": resume_file.uploaded_at.isoformat(),
            "is_active": resume_file.is_active,
        }
    )


@resume_files_router.get("/{file_id}/download")
async def download_resume_file(
    file_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> StreamingResponse:
    """Download resume file binary.

    REQ-006 §2.7: File download from BYTEA column.

    Args:
        file_id: The file ID to download.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        StreamingResponse with file binary and Content-Disposition header.

    Raises:
        NotFoundError: If file not found or not owned by user.
    """
    result = await db.execute(
        select(ResumeFile)
        .join(Persona, ResumeFile.persona_id == Persona.id)
        .where(ResumeFile.id == file_id, Persona.user_id == user_id)
    )
    resume_file = result.scalar_one_or_none()
    if not resume_file:
        raise NotFoundError("ResumeFile", str(file_id))

    # Determine media type
    media_type = (
        "application/pdf"
        if resume_file.file_type == "PDF"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    return StreamingResponse(
        iter([resume_file.file_binary]),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{resume_file.file_name}"'
        },
    )


# =============================================================================
# Submitted Resume PDFs (download)
# =============================================================================

submitted_resume_pdfs_router = APIRouter()


@submitted_resume_pdfs_router.get("/{pdf_id}/download")
async def download_submitted_resume_pdf(
    pdf_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> StreamingResponse:
    """Download submitted resume PDF.

    REQ-006 §5.2: Immutable PDF stored at application submission time.

    Args:
        pdf_id: The PDF ID to download.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        StreamingResponse with PDF binary and Content-Disposition header.

    Raises:
        NotFoundError: If PDF not found or not owned by user.
    """
    # Query PDF and verify ownership through resume source
    # SubmittedResumePDF -> BaseResume -> Persona -> User
    # or SubmittedResumePDF -> JobVariant -> BaseResume -> Persona -> User
    result = await db.execute(
        select(SubmittedResumePDF).where(SubmittedResumePDF.id == pdf_id)
    )
    pdf = result.scalar_one_or_none()

    if not pdf:
        raise NotFoundError("SubmittedResumePDF", str(pdf_id))

    # Verify ownership through BaseResume
    if pdf.resume_source_type == "Base":
        base_result = await db.execute(
            select(BaseResume)
            .join(Persona, BaseResume.persona_id == Persona.id)
            .where(BaseResume.id == pdf.resume_source_id, Persona.user_id == user_id)
        )
        if not base_result.scalar_one_or_none():
            raise NotFoundError("SubmittedResumePDF", str(pdf_id))
    else:
        # Variant - check through JobVariant -> BaseResume
        from app.models.resume import JobVariant

        variant_result = await db.execute(
            select(JobVariant)
            .join(BaseResume, JobVariant.base_resume_id == BaseResume.id)
            .join(Persona, BaseResume.persona_id == Persona.id)
            .where(JobVariant.id == pdf.resume_source_id, Persona.user_id == user_id)
        )
        if not variant_result.scalar_one_or_none():
            raise NotFoundError("SubmittedResumePDF", str(pdf_id))

    return StreamingResponse(
        iter([pdf.file_binary]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf.file_name}"'},
    )


# =============================================================================
# Submitted Cover Letter PDFs (download)
# =============================================================================

submitted_cover_letter_pdfs_router = APIRouter()


@submitted_cover_letter_pdfs_router.get("/{pdf_id}/download")
async def download_submitted_cover_letter_pdf(
    pdf_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> StreamingResponse:
    """Download submitted cover letter PDF.

    REQ-006 §5.2: Immutable PDF stored at application submission time.

    Args:
        pdf_id: The PDF ID to download.
        user_id: Current authenticated user (injected).
        db: Database session (injected).

    Returns:
        StreamingResponse with PDF binary and Content-Disposition header.

    Raises:
        NotFoundError: If PDF not found or not owned by user.
    """
    from app.models.cover_letter import CoverLetter

    # Query PDF and verify ownership through cover letter -> persona
    result = await db.execute(
        select(SubmittedCoverLetterPDF)
        .join(CoverLetter, SubmittedCoverLetterPDF.cover_letter_id == CoverLetter.id)
        .join(Persona, CoverLetter.persona_id == Persona.id)
        .where(SubmittedCoverLetterPDF.id == pdf_id, Persona.user_id == user_id)
    )
    pdf = result.scalar_one_or_none()

    if not pdf:
        raise NotFoundError("SubmittedCoverLetterPDF", str(pdf_id))

    return StreamingResponse(
        iter([pdf.file_binary]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf.file_name}"'},
    )
