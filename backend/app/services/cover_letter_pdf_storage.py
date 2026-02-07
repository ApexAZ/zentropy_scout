"""Cover letter PDF storage service.

REQ-002b §4.2: SubmittedCoverLetterPDF immutable storage.

Provides functions to store and retrieve cover letter PDFs as immutable
BYTEA records in PostgreSQL. PDFs are created when a user downloads an
approved cover letter, and linked to an Application when the user marks
"Applied".

Public API:
- store_cover_letter_pdf    — create SubmittedCoverLetterPDF (idempotent)
- get_existing_cover_letter_pdf — retrieve existing PDF for a cover letter
"""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.errors import InvalidStateError, NotFoundError, ValidationError
from app.models.cover_letter import CoverLetter, SubmittedCoverLetterPDF

# =============================================================================
# Result Dataclass
# =============================================================================


@dataclass(frozen=True)
class StoreCoverLetterPdfResult:
    """Result of storing a cover letter PDF.

    Attributes:
        pdf_id: UUID of the SubmittedCoverLetterPDF record.
        file_name: Generated filename for the PDF.
        already_existed: True if an existing PDF was returned (idempotent).
    """

    pdf_id: uuid.UUID
    file_name: str
    already_existed: bool


# =============================================================================
# Public API
# =============================================================================


async def store_cover_letter_pdf(
    db: AsyncSession,
    cover_letter_id: uuid.UUID,
    pdf_bytes: bytes,
) -> StoreCoverLetterPdfResult:
    """Store a cover letter PDF as an immutable SubmittedCoverLetterPDF.

    Validates that the cover letter exists and is Approved. If a submitted
    PDF already exists for this cover letter, returns the existing record
    (idempotent — subsequent downloads return the stored version).

    Args:
        db: Database session.
        cover_letter_id: The approved CoverLetter to generate a PDF for.
        pdf_bytes: The rendered PDF binary data.

    Returns:
        StoreCoverLetterPdfResult with PDF record details.

    Raises:
        NotFoundError: If cover letter does not exist.
        InvalidStateError: If cover letter is not Approved.
        ValidationError: If pdf_bytes is empty or exceeds size limit.
    """
    # Validate PDF bytes before doing any DB work
    if not pdf_bytes:
        raise ValidationError("PDF content is empty.")
    if len(pdf_bytes) > _MAX_PDF_SIZE_BYTES:
        raise ValidationError(
            f"PDF exceeds maximum size of {_MAX_PDF_SIZE_BYTES // (1024 * 1024)} MB."
        )

    # Load cover letter with persona and job posting for filename generation
    result = await db.execute(
        select(CoverLetter)
        .options(
            joinedload(CoverLetter.persona),
            joinedload(CoverLetter.job_posting),
        )
        .where(CoverLetter.id == cover_letter_id)
    )
    cover_letter = result.unique().scalar_one_or_none()

    if cover_letter is None:
        raise NotFoundError("CoverLetter", str(cover_letter_id))

    if cover_letter.status != "Approved":
        raise InvalidStateError(
            f"Cover letter must be Approved to generate PDF. "
            f"Current status: '{cover_letter.status}'."
        )

    # Check for existing submitted PDF (idempotent)
    existing = await get_existing_cover_letter_pdf(db, cover_letter_id)
    if existing is not None:
        return StoreCoverLetterPdfResult(
            pdf_id=existing.id,
            file_name=existing.file_name,
            already_existed=True,
        )

    # Generate filename from persona name and company name
    persona_name = cover_letter.persona.full_name if cover_letter.persona else "Unknown"
    company_name = (
        cover_letter.job_posting.company_name if cover_letter.job_posting else "Unknown"
    )
    file_name = _generate_cover_letter_filename(persona_name, company_name)

    # Create immutable PDF record
    pdf_record = SubmittedCoverLetterPDF(
        cover_letter_id=cover_letter_id,
        file_name=file_name,
        file_binary=pdf_bytes,
    )
    db.add(pdf_record)
    await db.flush()
    await db.refresh(pdf_record)
    await db.commit()

    return StoreCoverLetterPdfResult(
        pdf_id=pdf_record.id,
        file_name=pdf_record.file_name,
        already_existed=False,
    )


async def get_existing_cover_letter_pdf(
    db: AsyncSession,
    cover_letter_id: uuid.UUID,
) -> SubmittedCoverLetterPDF | None:
    """Get existing submitted PDF for a cover letter.

    Args:
        db: Database session.
        cover_letter_id: The cover letter to check.

    Returns:
        SubmittedCoverLetterPDF if one exists, None otherwise.
    """
    result = await db.execute(
        select(SubmittedCoverLetterPDF)
        .where(SubmittedCoverLetterPDF.cover_letter_id == cover_letter_id)
        .order_by(SubmittedCoverLetterPDF.generated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# =============================================================================
# Constants
# =============================================================================

_MAX_PDF_SIZE_BYTES: int = 25 * 1024 * 1024
"""Maximum PDF size (25 MB). Cover letters are typically small (~50 KB)."""

# =============================================================================
# Helpers
# =============================================================================

# Security: ASCII-only allowlist prevents Unicode confusables and ensures
# filenames are safe for HTTP Content-Disposition headers.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_ALLOWED_CHARS = re.compile(r"[^a-zA-Z0-9\s\-_]")
_WHITESPACE = re.compile(r"\s+")


def _generate_cover_letter_filename(
    persona_name: str,
    company_name: str,
) -> str:
    """Generate a clean filename for a cover letter PDF.

    Format: {Last}_{First}_Cover_Letter_{Company}.pdf

    Special characters are removed and spaces replaced with underscores.

    Args:
        persona_name: Full name of the persona (e.g., "Jane Smith").
        company_name: Company name from job posting (e.g., "Acme Corp").

    Returns:
        Sanitized filename string ending in .pdf.
    """
    parts = persona_name.strip().split()
    if len(parts) >= 2:
        last = parts[-1]
        first = parts[0]
        name_part = f"{last}_{first}"
    else:
        name_part = parts[0] if parts else "Unknown"

    company_part = _sanitize_for_filename(company_name)
    name_part = _sanitize_for_filename(name_part)

    return f"{name_part}_Cover_Letter_{company_part}.pdf"


def _sanitize_for_filename(text: str) -> str:
    """Remove special characters and normalize whitespace for filenames.

    Security: Strips control characters first (prevents header injection),
    then applies ASCII-only allowlist (prevents path traversal and Unicode
    confusable attacks).

    Args:
        text: Raw text to sanitize.

    Returns:
        Filename-safe ASCII string with underscores replacing spaces.
    """
    cleaned = _CONTROL_CHARS.sub("", text)
    cleaned = _ALLOWED_CHARS.sub("", cleaned)
    cleaned = _WHITESPACE.sub("_", cleaned.strip())
    return cleaned or "Unknown"
