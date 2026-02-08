"""Cover letter PDF generation service.

REQ-002b §7.4: Approval & PDF Generation workflow.

Renders cover letter final_text into a PDF document using ReportLab Platypus,
then stores it as an immutable SubmittedCoverLetterPDF record.

Two rendering paths:
1. Pure render: body_text + contact → PDF bytes (no DB)
2. Orchestration: load approved CoverLetter → render → store via cover_letter_pdf_storage

Public API:
- render_cover_letter_pdf    — pure render: text → PDF bytes
- generate_cover_letter_pdf  — orchestration: load + render + store
"""

import io
import uuid
from dataclasses import dataclass
from xml.sax.saxutils import (
    escape as _xml_escape,  # nosec B406 — output escaping, not XML parsing
)

from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.errors import InvalidStateError, NotFoundError
from app.models.cover_letter import CoverLetter
from app.services.cover_letter_pdf_storage import (
    get_existing_cover_letter_pdf,
    store_cover_letter_pdf,
)

# =============================================================================
# Data Structures
# =============================================================================


@dataclass(frozen=True)
class CoverLetterContact:
    """Contact information for the cover letter header."""

    full_name: str
    email: str
    phone: str
    city: str
    state: str


@dataclass(frozen=True)
class GenerateCoverLetterPdfResult:
    """Result of generating a cover letter PDF.

    Attributes:
        pdf_id: UUID of the SubmittedCoverLetterPDF record.
        file_name: Generated filename for the PDF.
        pdf_bytes: The rendered PDF binary data.
        already_existed: True if an existing PDF was returned (idempotent).
    """

    pdf_id: uuid.UUID
    file_name: str
    pdf_bytes: bytes
    already_existed: bool


# =============================================================================
# Styles
# =============================================================================

_MARGIN_SIDE = 0.75 * inch
_MARGIN_TOP = 0.75 * inch
_MARGIN_BOTTOM = 0.75 * inch
_PARAGRAPH_SPACING = 6


def _build_styles() -> dict[str, ParagraphStyle]:
    """Build custom paragraph styles for cover letter rendering."""
    base = getSampleStyleSheet()

    return {
        "name": ParagraphStyle(
            "LetterName",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "contact": ParagraphStyle(
            "LetterContact",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "LetterBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=_PARAGRAPH_SPACING,
        ),
    }


# =============================================================================
# Public API — Pure Rendering
# =============================================================================


def render_cover_letter_pdf(
    body_text: str,
    contact: CoverLetterContact,
) -> bytes:
    """Render cover letter text into a PDF document.

    Uses ReportLab Platypus with standard Helvetica fonts.
    Returns raw PDF bytes suitable for BYTEA storage.

    Args:
        body_text: The final cover letter text (may contain newlines for paragraphs).
        contact: Contact information for the header.

    Returns:
        PDF file as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=_MARGIN_SIDE,
        rightMargin=_MARGIN_SIDE,
        topMargin=_MARGIN_TOP,
        bottomMargin=_MARGIN_BOTTOM,
    )

    styles = _build_styles()
    elements: list[object] = []

    # WHY _xml_escape: ReportLab Paragraph interprets XML/HTML markup.
    # All user-controlled strings must be escaped to prevent PDF injection.
    esc = _xml_escape

    # --- Header ---
    elements.append(Paragraph(esc(contact.full_name), styles["name"]))

    contact_parts = [esc(contact.email), esc(contact.phone)]
    if contact.city:
        location = esc(contact.city)
        if contact.state:
            location = f"{location}, {esc(contact.state)}"
        contact_parts.append(location)

    elements.append(Paragraph(" | ".join(contact_parts), styles["contact"]))
    elements.append(
        HRFlowable(
            width="100%",
            thickness=0.5,
            color="black",
            spaceAfter=_PARAGRAPH_SPACING,
        )
    )
    elements.append(Spacer(1, _PARAGRAPH_SPACING))

    # --- Body ---
    # Split on double-newlines for paragraph breaks; single newlines become <br/>
    paragraphs = body_text.split("\n\n")
    for para in paragraphs:
        cleaned = para.strip()
        if cleaned:
            # Convert single newlines to <br/> for line breaks within a paragraph
            html_text = esc(cleaned).replace("\n", "<br/>")
            elements.append(Paragraph(html_text, styles["body"]))

    doc.build(elements)
    return buffer.getvalue()


# =============================================================================
# Public API — Orchestration
# =============================================================================


async def generate_cover_letter_pdf(
    db: AsyncSession,
    cover_letter_id: uuid.UUID,
) -> GenerateCoverLetterPdfResult:
    """Generate and store a PDF for an approved cover letter.

    Loads the cover letter with persona info, renders the PDF from final_text,
    and stores it as an immutable SubmittedCoverLetterPDF record.

    Idempotent: if a PDF already exists, returns the stored version.

    Args:
        db: Database session.
        cover_letter_id: The approved CoverLetter to generate a PDF for.

    Returns:
        GenerateCoverLetterPdfResult with PDF record details and bytes.

    Raises:
        NotFoundError: If cover letter does not exist or is soft-deleted.
        InvalidStateError: If cover letter is not Approved or has no final_text.
    """
    # Load cover letter with persona for contact info
    result = await db.execute(
        select(CoverLetter)
        .options(joinedload(CoverLetter.persona))
        .where(CoverLetter.id == cover_letter_id)
    )
    cover_letter = result.unique().scalar_one_or_none()

    if cover_letter is None:
        raise NotFoundError("CoverLetter", str(cover_letter_id))

    if cover_letter.is_archived:
        raise NotFoundError("CoverLetter", str(cover_letter_id))

    if cover_letter.status != "Approved":
        raise InvalidStateError(
            f"Cover letter must be Approved to generate PDF. "
            f"Current status: '{cover_letter.status}'."
        )

    if not cover_letter.final_text or not cover_letter.final_text.strip():
        raise InvalidStateError(
            "Cover letter final_text must be set before generating PDF."
        )

    # Check for existing PDF (idempotent)
    existing = await get_existing_cover_letter_pdf(db, cover_letter_id)
    if existing is not None:
        return GenerateCoverLetterPdfResult(
            pdf_id=existing.id,
            file_name=existing.file_name,
            pdf_bytes=existing.file_binary,
            already_existed=True,
        )

    # Build contact info from persona
    persona = cover_letter.persona
    contact = CoverLetterContact(
        full_name=persona.full_name,
        email=persona.email,
        phone=persona.phone,
        city=persona.home_city,
        state=persona.home_state,
    )

    # Render PDF
    pdf_bytes = render_cover_letter_pdf(
        body_text=cover_letter.final_text,
        contact=contact,
    )

    # Store via cover_letter_pdf_storage
    store_result = await store_cover_letter_pdf(
        db=db,
        cover_letter_id=cover_letter_id,
        pdf_bytes=pdf_bytes,
    )

    return GenerateCoverLetterPdfResult(
        pdf_id=store_result.pdf_id,
        file_name=store_result.file_name,
        pdf_bytes=pdf_bytes,
        already_existed=store_result.already_existed,
    )
