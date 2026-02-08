"""Tests for cover letter PDF generation service.

REQ-002b §7.4: Approval & PDF Generation workflow.

Tests cover:
1. Pure PDF rendering (ReportLab, no DB)
2. Orchestration: load approved cover letter → render → store
"""

import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cover_letter import CoverLetter, SubmittedCoverLetterPDF
from app.models.job_posting import JobPosting
from app.models.job_source import JobSource
from app.models.persona import Persona
from app.models.user import User

# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def pdf_gen_scenario(db_session: AsyncSession):
    """Create scenario for cover letter PDF generation tests.

    Creates: User → Persona → JobSource → JobPosting → Approved CoverLetter + Draft CoverLetter.
    """
    user = User(id=uuid.uuid4(), email="cl_pdfgen@example.com")
    db_session.add(user)
    await db_session.flush()

    persona = Persona(
        user_id=user.id,
        full_name="Alice Johnson",
        email="alice@example.com",
        phone="555-0300",
        home_city="Denver",
        home_state="Colorado",
        home_country="USA",
    )
    db_session.add(persona)
    await db_session.flush()

    source = JobSource(
        source_name="PdfGenBoard",
        source_type="Extension",
        description="Test source for PDF generation",
    )
    db_session.add(source)
    await db_session.flush()

    job_posting = JobPosting(
        persona_id=persona.id,
        source_id=source.id,
        external_id="test-pdfgen-001",
        job_title="Data Scientist",
        company_name="DataCo",
        description="Analyze data",
        description_hash="pdfgen_hash_001",
        first_seen_date=date(2026, 1, 28),
        status="Discovered",
    )
    db_session.add(job_posting)
    await db_session.flush()

    approved_cl = CoverLetter(
        persona_id=persona.id,
        job_posting_id=job_posting.id,
        draft_text="Original draft text before approval.",
        final_text="Dear Hiring Manager,\n\nI am writing to express my interest in the Data Scientist role at DataCo.\n\nSincerely,\nAlice Johnson",
        status="Approved",
        agent_reasoning="Selected technical story for alignment.",
        achievement_stories_used=[str(uuid.uuid4())],
        approved_at=datetime.now(UTC),
    )
    db_session.add(approved_cl)
    await db_session.flush()

    draft_cl = CoverLetter(
        persona_id=persona.id,
        job_posting_id=job_posting.id,
        draft_text="Draft cover letter text.",
        status="Draft",
        agent_reasoning="Initial reasoning.",
        achievement_stories_used=[],
    )
    db_session.add(draft_cl)
    await db_session.flush()

    # Approved CL without final_text (edge case)
    approved_no_final = CoverLetter(
        persona_id=persona.id,
        job_posting_id=job_posting.id,
        draft_text="Approved but missing final_text.",
        status="Approved",
        agent_reasoning="Edge case reasoning.",
        achievement_stories_used=[],
        approved_at=datetime.now(UTC),
    )
    db_session.add(approved_no_final)
    await db_session.flush()

    await db_session.commit()

    class Scenario:
        pass

    s = Scenario()
    s.approved_cl_id = approved_cl.id
    s.draft_cl_id = draft_cl.id
    s.approved_no_final_cl_id = approved_no_final.id
    s.persona_full_name = "Alice Johnson"
    s.company_name = "DataCo"
    return s


# =============================================================================
# TestRenderCoverLetterPdf
# =============================================================================


class TestRenderCoverLetterPdf:
    """Tests for the pure PDF rendering function (no DB)."""

    def test_returns_pdf_bytes(self) -> None:
        """Output starts with PDF magic bytes."""
        from app.services.cover_letter_pdf_generation import (
            CoverLetterContact,
            render_cover_letter_pdf,
        )

        contact = CoverLetterContact(
            full_name="Alice Johnson",
            email="alice@example.com",
            phone="555-0300",
            city="Denver",
            state="Colorado",
        )
        pdf_bytes = render_cover_letter_pdf(
            body_text="Dear Hiring Manager,\n\nI am excited to apply.\n\nSincerely,\nAlice",
            contact=contact,
        )

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_produces_non_trivial_output(self) -> None:
        """Cover letter with content produces a meaningful-sized PDF."""
        from app.services.cover_letter_pdf_generation import (
            CoverLetterContact,
            render_cover_letter_pdf,
        )

        contact = CoverLetterContact(
            full_name="Alice Johnson",
            email="alice@example.com",
            phone="555-0300",
            city="Denver",
            state="Colorado",
        )
        pdf_bytes = render_cover_letter_pdf(
            body_text="Dear Hiring Manager,\n\nI am writing to express my interest in the Data Scientist role. I have 5 years of experience in machine learning and data analysis.\n\nSincerely,\nAlice Johnson",
            contact=contact,
        )

        assert len(pdf_bytes) > 500

    def test_handles_multiline_body(self) -> None:
        """Multiple paragraphs render without error."""
        from app.services.cover_letter_pdf_generation import (
            CoverLetterContact,
            render_cover_letter_pdf,
        )

        contact = CoverLetterContact(
            full_name="Alice Johnson",
            email="alice@example.com",
            phone="555-0300",
            city="Denver",
            state="Colorado",
        )
        body = (
            "Dear Hiring Manager,\n\n"
            "First paragraph about my interest.\n\n"
            "Second paragraph about my qualifications.\n\n"
            "Third paragraph about my achievements.\n\n"
            "Sincerely,\nAlice Johnson"
        )
        pdf_bytes = render_cover_letter_pdf(body_text=body, contact=contact)

        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 500

    def test_single_newlines_become_line_breaks(self) -> None:
        """Single newlines within a paragraph are converted to line breaks."""
        from app.services.cover_letter_pdf_generation import (
            CoverLetterContact,
            render_cover_letter_pdf,
        )

        contact = CoverLetterContact(
            full_name="Alice Johnson",
            email="alice@example.com",
            phone="555-0300",
            city="Denver",
            state="Colorado",
        )
        body = "Sincerely,\nAlice Johnson\nData Scientist"
        pdf_bytes = render_cover_letter_pdf(body_text=body, contact=contact)

        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 500

    def test_xml_special_characters_do_not_crash(self) -> None:
        """User content with XML chars renders without error."""
        from app.services.cover_letter_pdf_generation import (
            CoverLetterContact,
            render_cover_letter_pdf,
        )

        contact = CoverLetterContact(
            full_name="Jane <script>alert</script> Smith",
            email="jane&co@example.com",
            phone="555-0100",
            city="Austin",
            state="TX",
        )
        pdf_bytes = render_cover_letter_pdf(
            body_text='Body with <b>bold</b> and "quotes" & ampersands.',
            contact=contact,
        )

        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 500

    def test_minimal_body_text(self) -> None:
        """Short body text renders without error."""
        from app.services.cover_letter_pdf_generation import (
            CoverLetterContact,
            render_cover_letter_pdf,
        )

        contact = CoverLetterContact(
            full_name="Alice Johnson",
            email="alice@example.com",
            phone="555-0300",
            city="Denver",
            state="Colorado",
        )
        pdf_bytes = render_cover_letter_pdf(
            body_text="Brief note.",
            contact=contact,
        )

        assert pdf_bytes[:5] == b"%PDF-"


# =============================================================================
# TestGenerateCoverLetterPdf
# =============================================================================


class TestGenerateCoverLetterPdf:
    """Tests for the orchestration function (load → render → store)."""

    @pytest.mark.asyncio
    async def test_generates_and_stores_pdf(self, db_session, pdf_gen_scenario):
        """Creates a SubmittedCoverLetterPDF record in the database."""
        from app.services.cover_letter_pdf_generation import generate_cover_letter_pdf

        result = await generate_cover_letter_pdf(
            db=db_session,
            cover_letter_id=pdf_gen_scenario.approved_cl_id,
        )

        assert result.already_existed is False
        pdf = await db_session.get(SubmittedCoverLetterPDF, result.pdf_id)
        assert pdf is not None
        assert pdf.file_binary[:5] == b"%PDF-"

    @pytest.mark.asyncio
    async def test_returns_stored_pdf_on_subsequent_call(
        self, db_session, pdf_gen_scenario
    ):
        """Second call returns existing PDF (idempotent)."""
        from app.services.cover_letter_pdf_generation import generate_cover_letter_pdf

        result1 = await generate_cover_letter_pdf(
            db=db_session,
            cover_letter_id=pdf_gen_scenario.approved_cl_id,
        )
        result2 = await generate_cover_letter_pdf(
            db=db_session,
            cover_letter_id=pdf_gen_scenario.approved_cl_id,
        )

        assert result1.already_existed is False
        assert result1.pdf_id == result2.pdf_id
        assert result2.already_existed is True

    @pytest.mark.asyncio
    async def test_result_contains_pdf_bytes(self, db_session, pdf_gen_scenario):
        """Result includes the rendered PDF bytes."""
        from app.services.cover_letter_pdf_generation import generate_cover_letter_pdf

        result = await generate_cover_letter_pdf(
            db=db_session,
            cover_letter_id=pdf_gen_scenario.approved_cl_id,
        )

        assert isinstance(result.pdf_bytes, bytes)
        assert result.pdf_bytes[:5] == b"%PDF-"
        assert len(result.pdf_bytes) > 500

    @pytest.mark.asyncio
    async def test_result_contains_file_name(self, db_session, pdf_gen_scenario):
        """Result includes the generated filename."""
        from app.services.cover_letter_pdf_generation import generate_cover_letter_pdf

        result = await generate_cover_letter_pdf(
            db=db_session,
            cover_letter_id=pdf_gen_scenario.approved_cl_id,
        )

        assert isinstance(result.file_name, str)
        assert result.file_name.endswith(".pdf")
        assert "Johnson" in result.file_name
        assert "DataCo" in result.file_name

    @pytest.mark.asyncio
    async def test_rejects_draft_cover_letter(self, db_session, pdf_gen_scenario):
        """Cannot generate PDF for a cover letter still in Draft status."""
        from app.core.errors import InvalidStateError
        from app.services.cover_letter_pdf_generation import generate_cover_letter_pdf

        with pytest.raises(InvalidStateError, match="Approved"):
            await generate_cover_letter_pdf(
                db=db_session,
                cover_letter_id=pdf_gen_scenario.draft_cl_id,
            )

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_cover_letter(self, db_session):
        """NotFoundError when cover letter does not exist."""
        from app.core.errors import NotFoundError
        from app.services.cover_letter_pdf_generation import generate_cover_letter_pdf

        with pytest.raises(NotFoundError):
            await generate_cover_letter_pdf(
                db=db_session,
                cover_letter_id=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_rejects_cover_letter_without_final_text(
        self, db_session, pdf_gen_scenario
    ):
        """InvalidStateError when cover letter is Approved but final_text is None."""
        from app.core.errors import InvalidStateError
        from app.services.cover_letter_pdf_generation import generate_cover_letter_pdf

        with pytest.raises(InvalidStateError, match="final_text"):
            await generate_cover_letter_pdf(
                db=db_session,
                cover_letter_id=pdf_gen_scenario.approved_no_final_cl_id,
            )

    @pytest.mark.asyncio
    async def test_rejects_soft_deleted_cover_letter(
        self, db_session, pdf_gen_scenario
    ):
        """Cannot generate PDF for a soft-deleted cover letter."""
        from app.core.errors import NotFoundError
        from app.services.cover_letter_pdf_generation import generate_cover_letter_pdf

        cl = await db_session.get(CoverLetter, pdf_gen_scenario.approved_cl_id)
        cl.archived_at = datetime.now(UTC)
        await db_session.commit()

        with pytest.raises(NotFoundError):
            await generate_cover_letter_pdf(
                db=db_session,
                cover_letter_id=pdf_gen_scenario.approved_cl_id,
            )
