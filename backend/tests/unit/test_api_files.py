"""Tests for File Upload/Download API endpoints.

REQ-006 §2.7: File handling endpoints.

These tests verify:
- Resume file upload (POST /api/v1/resume-files)
- Submitted resume PDF download (GET /api/v1/submitted-resume-pdfs/{id}/download)
- Submitted cover letter PDF download (GET /api/v1/submitted-cover-letter-pdfs/{id}/download)
- Base resume download (GET /api/v1/base-resumes/{id}/download)
"""

import io
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_USER_ID

# =============================================================================
# Fixtures for File Tests
# =============================================================================


@pytest_asyncio.fixture
async def persona_for_files(db_session: AsyncSession):
    """Create a persona for file tests."""
    from app.models import Persona

    persona = Persona(
        id=uuid.uuid4(),
        user_id=TEST_USER_ID,
        full_name="Test User",
        email="testpersona@example.com",
        phone="555-555-5555",
        home_city="San Francisco",
        home_state="California",
        home_country="USA",
    )
    db_session.add(persona)
    await db_session.commit()
    await db_session.refresh(persona)
    return persona


@pytest_asyncio.fixture
async def resume_file_in_db(db_session: AsyncSession, persona_for_files):
    """Create a resume file in the database."""
    from app.models import ResumeFile

    resume_file = ResumeFile(
        id=uuid.uuid4(),
        persona_id=persona_for_files.id,
        file_name="test_resume.pdf",
        file_type="PDF",
        file_size_bytes=1024,
        file_binary=b"%PDF-1.4 test content",
        is_active=True,
    )
    db_session.add(resume_file)
    await db_session.commit()
    await db_session.refresh(resume_file)
    return resume_file


@pytest_asyncio.fixture
async def base_resume_with_pdf(db_session: AsyncSession, persona_for_files):
    """Create a base resume with rendered PDF."""
    from app.models import BaseResume

    base_resume = BaseResume(
        id=uuid.uuid4(),
        persona_id=persona_for_files.id,
        name="Software Engineer Resume",
        role_type="Software Engineer",
        summary="Experienced software engineer...",
        rendered_document=b"%PDF-1.4 base resume content",
        rendered_at=datetime.now(UTC),
    )
    db_session.add(base_resume)
    await db_session.commit()
    await db_session.refresh(base_resume)
    return base_resume


@pytest_asyncio.fixture
async def submitted_resume_pdf(db_session: AsyncSession, base_resume_with_pdf):
    """Create a submitted resume PDF."""
    from app.models import SubmittedResumePDF

    submitted_pdf = SubmittedResumePDF(
        id=uuid.uuid4(),
        application_id=None,  # Orphaned for test
        resume_source_type="Base",
        resume_source_id=base_resume_with_pdf.id,
        file_name="submitted_resume.pdf",
        file_binary=b"%PDF-1.4 submitted resume content",
    )
    db_session.add(submitted_pdf)
    await db_session.commit()
    await db_session.refresh(submitted_pdf)
    return submitted_pdf


@pytest_asyncio.fixture
async def submitted_cover_letter_pdf(db_session: AsyncSession, persona_for_files):
    """Create a submitted cover letter PDF."""
    from app.models import CoverLetter, JobPosting, SubmittedCoverLetterPDF
    from app.models.job_source import JobSource

    # Create a job source first
    job_source = JobSource(
        id=uuid.uuid4(),
        source_name="TestSource",
        source_type="Manual",  # Must match CHECK constraint
        description="Test job source",
        is_active=True,
    )
    db_session.add(job_source)
    await db_session.flush()

    # Create a job posting
    from datetime import date

    job_posting = JobPosting(
        id=uuid.uuid4(),
        persona_id=persona_for_files.id,
        source_id=job_source.id,
        job_title="Software Engineer",
        company_name="Test Company",
        description="Looking for a software engineer to join our team.",
        first_seen_date=date.today(),
        description_hash="abc123hash",
    )
    db_session.add(job_posting)
    await db_session.flush()

    # Create a cover letter
    cover_letter = CoverLetter(
        id=uuid.uuid4(),
        persona_id=persona_for_files.id,
        job_posting_id=job_posting.id,
        draft_text="Dear Hiring Manager...",
        status="Draft",
    )
    db_session.add(cover_letter)
    await db_session.flush()

    # Create submitted PDF
    submitted_pdf = SubmittedCoverLetterPDF(
        id=uuid.uuid4(),
        cover_letter_id=cover_letter.id,
        application_id=None,  # Orphaned for test
        file_name="submitted_cover_letter.pdf",
        file_binary=b"%PDF-1.4 cover letter content",
    )
    db_session.add(submitted_pdf)
    await db_session.commit()
    await db_session.refresh(submitted_pdf)
    return submitted_pdf


# =============================================================================
# Resume File Upload Tests
# =============================================================================


class TestResumeFileUpload:
    """Tests for POST /api/v1/resume-files."""

    @pytest.mark.asyncio
    async def test_upload_requires_auth(self, unauthenticated_client: AsyncClient):
        """Upload should return 401 without authentication."""
        files = {"file": ("test.pdf", b"content", "application/pdf")}
        response = await unauthenticated_client.post(
            "/api/v1/resume-files",
            files=files,
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_pdf_success(
        self,
        client: AsyncClient,
        persona_for_files,
    ):
        """Upload PDF file returns 200 with file metadata."""
        pdf_content = b"%PDF-1.4 test pdf content"
        files = {"file": ("resume.pdf", io.BytesIO(pdf_content), "application/pdf")}
        data = {"persona_id": str(persona_for_files.id)}

        # Mock magic to return PDF MIME type
        with patch("app.core.file_validation.magic.from_buffer") as mock_magic:
            mock_magic.return_value = "application/pdf"
            response = await client.post(
                "/api/v1/resume-files",
                files=files,
                data=data,
            )

        assert response.status_code == 200
        result = response.json()
        assert "data" in result
        assert result["data"]["file_name"] == "resume.pdf"
        assert result["data"]["file_type"] == "PDF"
        assert result["data"]["file_size_bytes"] == len(pdf_content)
        assert "id" in result["data"]

    @pytest.mark.asyncio
    async def test_upload_docx_success(
        self,
        client: AsyncClient,
        persona_for_files,
    ):
        """Upload DOCX file returns 200 with file metadata."""
        # DOCX magic bytes (PK zip header)
        docx_content = b"PK\x03\x04test docx content"
        files = {
            "file": (
                "resume.docx",
                io.BytesIO(docx_content),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        data = {"persona_id": str(persona_for_files.id)}

        # Mock magic to return DOCX MIME type
        docx_mime = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        with patch("app.core.file_validation.magic.from_buffer") as mock_magic:
            mock_magic.return_value = docx_mime
            response = await client.post(
                "/api/v1/resume-files",
                files=files,
                data=data,
            )

        assert response.status_code == 200
        result = response.json()
        assert result["data"]["file_name"] == "resume.docx"
        assert result["data"]["file_type"] == "DOCX"

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(
        self,
        client: AsyncClient,
        persona_for_files,
    ):
        """Upload non-PDF/DOCX file returns 400."""
        files = {"file": ("resume.txt", b"plain text", "text/plain")}
        data = {"persona_id": str(persona_for_files.id)}

        # Mock magic to return text/plain (not allowed)
        with patch("app.core.file_validation.magic.from_buffer") as mock_magic:
            mock_magic.return_value = "text/plain"
            response = await client.post(
                "/api/v1/resume-files",
                files=files,
                data=data,
            )

        assert response.status_code == 400
        result = response.json()
        assert result["error"]["code"] == "VALIDATION_ERROR"
        assert "Invalid file content" in result["error"]["message"]

    @pytest.mark.asyncio
    async def test_upload_missing_persona_id(
        self,
        client: AsyncClient,
    ):
        """Upload without persona_id returns 400 (validation error)."""
        files = {"file": ("resume.pdf", b"%PDF-1.4 content", "application/pdf")}

        response = await client.post(
            "/api/v1/resume-files",
            files=files,
        )

        # Validation errors return 400 (bad request)
        # Note: Could also be 422 depending on FastAPI version/config
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_upload_persona_not_found(
        self,
        client: AsyncClient,
    ):
        """Upload with non-existent persona returns 404."""
        files = {"file": ("resume.pdf", b"%PDF-1.4 content", "application/pdf")}
        data = {"persona_id": str(uuid.uuid4())}

        # Mock magic to return PDF (file validation passes, but persona not found)
        with patch("app.core.file_validation.magic.from_buffer") as mock_magic:
            mock_magic.return_value = "application/pdf"
            response = await client.post(
                "/api/v1/resume-files",
                files=files,
                data=data,
            )

        assert response.status_code == 404
        result = response.json()
        assert result["error"]["code"] == "NOT_FOUND"


# =============================================================================
# Submitted Resume PDF Download Tests
# =============================================================================


class TestSubmittedResumePDFDownload:
    """Tests for GET /api/v1/submitted-resume-pdfs/{id}/download."""

    @pytest.mark.asyncio
    async def test_download_requires_auth(self, unauthenticated_client: AsyncClient):
        """Download should return 401 without authentication."""
        pdf_id = uuid.uuid4()
        response = await unauthenticated_client.get(
            f"/api/v1/submitted-resume-pdfs/{pdf_id}/download"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_download_success(
        self,
        client: AsyncClient,
        submitted_resume_pdf,
    ):
        """Download returns PDF binary with correct headers."""
        response = await client.get(
            f"/api/v1/submitted-resume-pdfs/{submitted_resume_pdf.id}/download"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert "submitted_resume.pdf" in response.headers["content-disposition"]
        assert response.content == b"%PDF-1.4 submitted resume content"

    @pytest.mark.asyncio
    async def test_download_not_found(
        self,
        client: AsyncClient,
    ):
        """Download non-existent PDF returns 404."""
        pdf_id = uuid.uuid4()
        response = await client.get(f"/api/v1/submitted-resume-pdfs/{pdf_id}/download")

        assert response.status_code == 404


# =============================================================================
# Submitted Cover Letter PDF Download Tests
# =============================================================================


class TestSubmittedCoverLetterPDFDownload:
    """Tests for GET /api/v1/submitted-cover-letter-pdfs/{id}/download."""

    @pytest.mark.asyncio
    async def test_download_requires_auth(self, unauthenticated_client: AsyncClient):
        """Download should return 401 without authentication."""
        pdf_id = uuid.uuid4()
        response = await unauthenticated_client.get(
            f"/api/v1/submitted-cover-letter-pdfs/{pdf_id}/download"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_download_success(
        self,
        client: AsyncClient,
        submitted_cover_letter_pdf,
    ):
        """Download returns PDF binary with correct headers."""
        response = await client.get(
            f"/api/v1/submitted-cover-letter-pdfs/{submitted_cover_letter_pdf.id}/download"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert "submitted_cover_letter.pdf" in response.headers["content-disposition"]
        assert response.content == b"%PDF-1.4 cover letter content"

    @pytest.mark.asyncio
    async def test_download_not_found(
        self,
        client: AsyncClient,
    ):
        """Download non-existent PDF returns 404."""
        pdf_id = uuid.uuid4()
        response = await client.get(
            f"/api/v1/submitted-cover-letter-pdfs/{pdf_id}/download"
        )

        assert response.status_code == 404


# =============================================================================
# Base Resume Download Tests
# =============================================================================


class TestBaseResumeDownload:
    """Tests for GET /api/v1/base-resumes/{id}/download."""

    @pytest.mark.asyncio
    async def test_download_requires_auth(self, unauthenticated_client: AsyncClient):
        """Download should return 401 without authentication."""
        resume_id = uuid.uuid4()
        response = await unauthenticated_client.get(
            f"/api/v1/base-resumes/{resume_id}/download"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_download_success(
        self,
        client: AsyncClient,
        base_resume_with_pdf,
    ):
        """Download returns PDF binary with correct headers."""
        response = await client.get(
            f"/api/v1/base-resumes/{base_resume_with_pdf.id}/download"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert response.content == b"%PDF-1.4 base resume content"

    @pytest.mark.asyncio
    async def test_download_not_found(
        self,
        client: AsyncClient,
    ):
        """Download non-existent resume returns 404."""
        resume_id = uuid.uuid4()
        response = await client.get(f"/api/v1/base-resumes/{resume_id}/download")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_no_rendered_document(
        self,
        client: AsyncClient,
        persona_for_files,
        db_session: AsyncSession,
    ):
        """Download resume without rendered document returns 404."""
        from app.models import BaseResume

        # Create base resume without rendered_document
        base_resume = BaseResume(
            id=uuid.uuid4(),
            persona_id=persona_for_files.id,
            name="Unrendered Resume",
            role_type="Software Engineer",
            summary="Test summary",
            rendered_document=None,
            rendered_at=None,
        )
        db_session.add(base_resume)
        await db_session.commit()

        response = await client.get(f"/api/v1/base-resumes/{base_resume.id}/download")

        assert response.status_code == 404


# =============================================================================
# Resume File List/Get Tests
# =============================================================================


class TestResumeFileList:
    """Tests for GET /api/v1/resume-files (list user's resume files)."""

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, unauthenticated_client: AsyncClient):
        """List should return 401 without authentication."""
        response = await unauthenticated_client.get("/api/v1/resume-files")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_returns_user_files(
        self,
        client: AsyncClient,
        resume_file_in_db,
    ):
        """List returns files for current user only."""
        response = await client.get("/api/v1/resume-files")

        assert response.status_code == 200
        result = response.json()
        assert "data" in result
        assert len(result["data"]) == 1
        assert result["data"][0]["file_name"] == resume_file_in_db.file_name


class TestResumeFileGet:
    """Tests for GET /api/v1/resume-files/{id}."""

    @pytest.mark.asyncio
    async def test_get_requires_auth(self, unauthenticated_client: AsyncClient):
        """Get should return 401 without authentication."""
        file_id = uuid.uuid4()
        response = await unauthenticated_client.get(f"/api/v1/resume-files/{file_id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_success(
        self,
        client: AsyncClient,
        resume_file_in_db,
    ):
        """Get returns file metadata (not binary)."""
        response = await client.get(f"/api/v1/resume-files/{resume_file_in_db.id}")

        assert response.status_code == 200
        result = response.json()
        assert result["data"]["file_name"] == "test_resume.pdf"
        assert result["data"]["file_type"] == "PDF"
        # Binary should NOT be in response
        assert "file_binary" not in result["data"]

    @pytest.mark.asyncio
    async def test_get_not_found(
        self,
        client: AsyncClient,
    ):
        """Get non-existent file returns 404."""
        file_id = uuid.uuid4()
        response = await client.get(f"/api/v1/resume-files/{file_id}")

        assert response.status_code == 404


class TestResumeFileDownload:
    """Tests for GET /api/v1/resume-files/{id}/download."""

    @pytest.mark.asyncio
    async def test_download_requires_auth(self, unauthenticated_client: AsyncClient):
        """Download should return 401 without authentication."""
        file_id = uuid.uuid4()
        response = await unauthenticated_client.get(
            f"/api/v1/resume-files/{file_id}/download"
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_download_success(
        self,
        client: AsyncClient,
        resume_file_in_db,
    ):
        """Download returns file binary with correct headers."""
        response = await client.get(
            f"/api/v1/resume-files/{resume_file_in_db.id}/download"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert "test_resume.pdf" in response.headers["content-disposition"]
        assert response.content == b"%PDF-1.4 test content"

    @pytest.mark.asyncio
    async def test_download_not_found(
        self,
        client: AsyncClient,
    ):
        """Download non-existent file returns 404."""
        file_id = uuid.uuid4()
        response = await client.get(f"/api/v1/resume-files/{file_id}/download")

        assert response.status_code == 404
