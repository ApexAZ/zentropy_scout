"""File Upload/Download API router.

REQ-006 §2.7, §5.2: File handling endpoints.
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user_id
from app.core.responses import DataResponse

router = APIRouter()


# =============================================================================
# Resume Files (upload)
# =============================================================================

resume_files_router = APIRouter()


@resume_files_router.post("")
async def upload_resume_file(
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> DataResponse[dict]:
    """Upload original resume file during onboarding.

    REQ-006 §2.7: File upload stored as BYTEA in PostgreSQL.
    """
    return DataResponse(data={"file_id": None, "status": "uploaded"})


# =============================================================================
# Submitted Resume PDFs (download)
# =============================================================================

submitted_resume_pdfs_router = APIRouter()


@submitted_resume_pdfs_router.get("/{pdf_id}/download")
async def download_submitted_resume_pdf(
    pdf_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> StreamingResponse:
    """Download submitted resume PDF.

    REQ-006 §5.2: Immutable PDF stored at application submission time.
    """
    return StreamingResponse(
        iter([b""]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=submitted_resume.pdf"},
    )


# =============================================================================
# Submitted Cover Letter PDFs (download)
# =============================================================================

submitted_cover_letter_pdfs_router = APIRouter()


@submitted_cover_letter_pdfs_router.get("/{pdf_id}/download")
async def download_submitted_cover_letter_pdf(
    pdf_id: uuid.UUID,  # noqa: ARG001
    _user_id: uuid.UUID = Depends(get_current_user_id),  # noqa: B008
) -> StreamingResponse:
    """Download submitted cover letter PDF.

    REQ-006 §5.2: Immutable PDF stored at application submission time.
    """
    return StreamingResponse(
        iter([b""]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=submitted_cover_letter.pdf"
        },
    )
