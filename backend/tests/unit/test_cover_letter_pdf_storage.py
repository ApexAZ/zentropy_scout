"""Tests for cover letter PDF storage service.

REQ-002b §4.2: SubmittedCoverLetterPDF immutable storage.

Tests the service functions for creating, retrieving, and managing
SubmittedCoverLetterPDF records in the database.
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
async def cl_scenario(db_session: AsyncSession):
    """Create a complete scenario for cover letter PDF storage tests.

    Creates: User → Persona → JobSource → JobPosting → CoverLetter (Approved).

    Returns:
        Namespace with entity IDs and the db session.
    """
    user = User(id=uuid.uuid4(), email="cl_pdf@example.com")
    db_session.add(user)
    await db_session.flush()

    persona = Persona(
        user_id=user.id,
        full_name="Jane Smith",
        email="jane@example.com",
        phone="555-0100",
        home_city="Portland",
        home_state="Oregon",
        home_country="USA",
    )
    db_session.add(persona)
    await db_session.flush()

    source = JobSource(
        source_name="TestBoard",
        source_type="Extension",
        description="Test source",
    )
    db_session.add(source)
    await db_session.flush()

    job_posting = JobPosting(
        source_id=source.id,
        external_id="test-cl-001",
        job_title="Senior Engineer",
        company_name="Acme Corp",
        description="Build things",
        description_hash="cl_hash_001",
        first_seen_date=date(2026, 1, 20),
    )
    db_session.add(job_posting)
    await db_session.flush()

    cover_letter = CoverLetter(
        persona_id=persona.id,
        job_posting_id=job_posting.id,
        draft_text="Dear Hiring Manager, I am excited to apply...",
        final_text="Dear Hiring Manager, I am thrilled to apply...",
        status="Approved",
        agent_reasoning="Selected leadership story for alignment.",
        achievement_stories_used=[str(uuid.uuid4())],
        approved_at=datetime.now(UTC),
    )
    db_session.add(cover_letter)
    await db_session.flush()

    # Also create a Draft cover letter for guard tests
    draft_cover_letter = CoverLetter(
        persona_id=persona.id,
        job_posting_id=job_posting.id,
        draft_text="Draft content here.",
        status="Draft",
        agent_reasoning="Draft reasoning.",
        achievement_stories_used=[],
    )
    db_session.add(draft_cover_letter)
    await db_session.flush()

    await db_session.commit()

    class Scenario:
        pass

    s = Scenario()
    s.user_id = user.id
    s.persona_id = persona.id
    s.persona_full_name = "Jane Smith"
    s.company_name = "Acme Corp"
    s.job_posting_id = job_posting.id
    s.cover_letter_id = cover_letter.id
    s.draft_cover_letter_id = draft_cover_letter.id
    return s


_FAKE_PDF_BYTES = b"%PDF-1.4 fake cover letter pdf content"
"""Minimal PDF-like bytes for testing storage."""


# =============================================================================
# TestStoreCoverLetterPdf
# =============================================================================


class TestStoreCoverLetterPdf:
    """Tests for store_cover_letter_pdf."""

    @pytest.mark.asyncio
    async def test_stores_pdf_bytes(self, db_session, cl_scenario):
        """Stored PDF record contains the exact bytes provided."""
        from app.services.cover_letter_pdf_storage import store_cover_letter_pdf

        result = await store_cover_letter_pdf(
            db=db_session,
            cover_letter_id=cl_scenario.cover_letter_id,
            pdf_bytes=_FAKE_PDF_BYTES,
        )

        pdf = await db_session.get(SubmittedCoverLetterPDF, result.pdf_id)
        assert pdf is not None
        assert pdf.file_binary == _FAKE_PDF_BYTES

    @pytest.mark.asyncio
    async def test_generates_filename_from_persona_and_company(
        self, db_session, cl_scenario
    ):
        """Filename is derived from persona name and company name."""
        from app.services.cover_letter_pdf_storage import store_cover_letter_pdf

        result = await store_cover_letter_pdf(
            db=db_session,
            cover_letter_id=cl_scenario.cover_letter_id,
            pdf_bytes=_FAKE_PDF_BYTES,
        )

        pdf = await db_session.get(SubmittedCoverLetterPDF, result.pdf_id)
        assert pdf is not None
        assert "Smith" in pdf.file_name
        assert "Acme_Corp" in pdf.file_name
        assert pdf.file_name.endswith(".pdf")

    @pytest.mark.asyncio
    async def test_returns_existing_when_already_stored(self, db_session, cl_scenario):
        """Second call returns existing PDF instead of creating duplicate."""
        from app.services.cover_letter_pdf_storage import store_cover_letter_pdf

        result1 = await store_cover_letter_pdf(
            db=db_session,
            cover_letter_id=cl_scenario.cover_letter_id,
            pdf_bytes=_FAKE_PDF_BYTES,
        )
        result2 = await store_cover_letter_pdf(
            db=db_session,
            cover_letter_id=cl_scenario.cover_letter_id,
            pdf_bytes=b"different bytes should be ignored",
        )

        assert result1.pdf_id == result2.pdf_id
        assert result2.already_existed is True

    @pytest.mark.asyncio
    async def test_rejects_draft_cover_letter(self, db_session, cl_scenario):
        """Cannot store PDF for a cover letter that is still Draft."""
        from app.core.errors import InvalidStateError
        from app.services.cover_letter_pdf_storage import store_cover_letter_pdf

        with pytest.raises(InvalidStateError, match="Approved"):
            await store_cover_letter_pdf(
                db=db_session,
                cover_letter_id=cl_scenario.draft_cover_letter_id,
                pdf_bytes=_FAKE_PDF_BYTES,
            )

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_cover_letter(self, db_session):
        """NotFoundError when cover letter does not exist."""
        from app.core.errors import NotFoundError
        from app.services.cover_letter_pdf_storage import store_cover_letter_pdf

        with pytest.raises(NotFoundError):
            await store_cover_letter_pdf(
                db=db_session,
                cover_letter_id=uuid.uuid4(),
                pdf_bytes=_FAKE_PDF_BYTES,
            )

    @pytest.mark.asyncio
    async def test_stores_generated_at_timestamp(self, db_session, cl_scenario):
        """PDF record has a generated_at timestamp set by server default."""
        from app.services.cover_letter_pdf_storage import store_cover_letter_pdf

        result = await store_cover_letter_pdf(
            db=db_session,
            cover_letter_id=cl_scenario.cover_letter_id,
            pdf_bytes=_FAKE_PDF_BYTES,
        )

        pdf = await db_session.get(SubmittedCoverLetterPDF, result.pdf_id)
        assert pdf is not None
        assert pdf.generated_at is not None

    @pytest.mark.asyncio
    async def test_result_contains_expected_data(self, db_session, cl_scenario):
        """Result contains pdf_id, file_name, and already_existed flag."""
        from app.services.cover_letter_pdf_storage import store_cover_letter_pdf

        result = await store_cover_letter_pdf(
            db=db_session,
            cover_letter_id=cl_scenario.cover_letter_id,
            pdf_bytes=_FAKE_PDF_BYTES,
        )

        assert isinstance(result.pdf_id, uuid.UUID)
        assert isinstance(result.file_name, str)
        assert result.already_existed is False

    @pytest.mark.asyncio
    async def test_application_id_is_null_initially(self, db_session, cl_scenario):
        """Stored PDF has application_id=NULL before application creation."""
        from app.services.cover_letter_pdf_storage import store_cover_letter_pdf

        result = await store_cover_letter_pdf(
            db=db_session,
            cover_letter_id=cl_scenario.cover_letter_id,
            pdf_bytes=_FAKE_PDF_BYTES,
        )

        pdf = await db_session.get(SubmittedCoverLetterPDF, result.pdf_id)
        assert pdf is not None
        assert pdf.application_id is None


# =============================================================================
# TestGetExistingCoverLetterPdf
# =============================================================================


class TestGetExistingCoverLetterPdf:
    """Tests for get_existing_cover_letter_pdf."""

    @pytest.mark.asyncio
    async def test_returns_pdf_when_exists(self, db_session, cl_scenario):
        """Returns the stored PDF for a cover letter."""
        from app.services.cover_letter_pdf_storage import (
            get_existing_cover_letter_pdf,
            store_cover_letter_pdf,
        )

        store_result = await store_cover_letter_pdf(
            db=db_session,
            cover_letter_id=cl_scenario.cover_letter_id,
            pdf_bytes=_FAKE_PDF_BYTES,
        )

        pdf = await get_existing_cover_letter_pdf(
            db=db_session,
            cover_letter_id=cl_scenario.cover_letter_id,
        )

        assert pdf is not None
        assert pdf.id == store_result.pdf_id
        assert pdf.file_binary == _FAKE_PDF_BYTES

    @pytest.mark.asyncio
    async def test_returns_none_when_no_pdf(self, db_session, cl_scenario):
        """Returns None when no PDF has been generated yet."""
        from app.services.cover_letter_pdf_storage import get_existing_cover_letter_pdf

        pdf = await get_existing_cover_letter_pdf(
            db=db_session,
            cover_letter_id=cl_scenario.cover_letter_id,
        )

        assert pdf is None

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_cover_letter(self, db_session):
        """Returns None for a cover letter ID that does not exist."""
        from app.services.cover_letter_pdf_storage import get_existing_cover_letter_pdf

        pdf = await get_existing_cover_letter_pdf(
            db=db_session,
            cover_letter_id=uuid.uuid4(),
        )

        assert pdf is None


# =============================================================================
# TestGenerateCoverLetterFilename
# =============================================================================


class TestGenerateCoverLetterFilename:
    """Tests for _generate_cover_letter_filename helper."""

    def test_generates_last_first_format_when_full_name(self):
        """Filename uses Last_First format for two-part names."""
        from app.services.cover_letter_pdf_storage import (
            _generate_cover_letter_filename,
        )

        result = _generate_cover_letter_filename("Jane Smith", "Acme Corp")
        assert result == "Smith_Jane_Cover_Letter_Acme_Corp.pdf"

    def test_removes_special_characters_when_present(self):
        """Non-ASCII and punctuation characters are stripped."""
        from app.services.cover_letter_pdf_storage import (
            _generate_cover_letter_filename,
        )

        result = _generate_cover_letter_filename("José María", "O'Brien & Associates")
        assert "/" not in result
        assert "'" not in result
        assert "&" not in result
        assert result.endswith(".pdf")

    def test_uses_single_name_when_no_space(self):
        """Single-word names appear in filename without splitting."""
        from app.services.cover_letter_pdf_storage import (
            _generate_cover_letter_filename,
        )

        result = _generate_cover_letter_filename("Madonna", "TechCo")
        assert "Madonna" in result
        assert "TechCo" in result
        assert result.endswith(".pdf")

    def test_strips_path_traversal_characters(self):
        """Path traversal sequences are removed from filename."""
        from app.services.cover_letter_pdf_storage import (
            _generate_cover_letter_filename,
        )

        result = _generate_cover_letter_filename("Jane ../Smith", "../../etc/passwd")
        assert "../" not in result
        assert "/" not in result
        assert "\\" not in result
        assert result.endswith(".pdf")

    def test_strips_control_characters_when_present(self):
        """Control characters (newlines, null bytes) are removed."""
        from app.services.cover_letter_pdf_storage import (
            _generate_cover_letter_filename,
        )

        result = _generate_cover_letter_filename("Jane\r\nSmith", "Acme\x00Corp")
        assert "\r" not in result
        assert "\n" not in result
        assert "\x00" not in result
        assert result.endswith(".pdf")


# =============================================================================
# TestStoreCoverLetterPdfValidation
# =============================================================================


class TestStoreCoverLetterPdfValidation:
    """Security validation tests for store_cover_letter_pdf."""

    @pytest.mark.asyncio
    async def test_rejects_empty_pdf_bytes(self, db_session, cl_scenario):
        """Empty bytes are rejected with ValidationError."""
        from app.core.errors import ValidationError
        from app.services.cover_letter_pdf_storage import store_cover_letter_pdf

        with pytest.raises(ValidationError, match="empty"):
            await store_cover_letter_pdf(
                db=db_session,
                cover_letter_id=cl_scenario.cover_letter_id,
                pdf_bytes=b"",
            )

    @pytest.mark.asyncio
    async def test_rejects_oversized_pdf_bytes(self, db_session, cl_scenario):
        """PDF bytes exceeding max size are rejected."""
        from app.services.cover_letter_pdf_storage import (
            _MAX_PDF_SIZE_BYTES,
            store_cover_letter_pdf,
        )

        oversized = b"x" * (_MAX_PDF_SIZE_BYTES + 1)

        from app.core.errors import ValidationError

        with pytest.raises(ValidationError, match="size"):
            await store_cover_letter_pdf(
                db=db_session,
                cover_letter_id=cl_scenario.cover_letter_id,
                pdf_bytes=oversized,
            )
