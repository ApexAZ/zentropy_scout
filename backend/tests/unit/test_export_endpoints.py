"""Tests for markdown export API endpoints — PDF and DOCX.

REQ-025 §5.4: Export base resumes and job variants as PDF/DOCX.
REQ-025 §8: Export requires markdown_content to be present.

Tests verify:
- GET /api/v1/base-resumes/{id}/export/pdf
- GET /api/v1/base-resumes/{id}/export/docx
- GET /api/v1/job-variants/{id}/export/pdf
- GET /api/v1/job-variants/{id}/export/docx
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_JOB_SOURCE_ID, TEST_PERSONA_ID

_RESUME_URL = "/api/v1/base-resumes"
_VARIANT_URL = "/api/v1/job-variants"

_SAMPLE_MARKDOWN = "# John Doe\n\n## Summary\n\nExperienced engineer.\n"


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def resume_with_markdown(db_session: AsyncSession):
    """Base resume with markdown_content populated."""
    from app.models.resume import BaseResume

    resume = BaseResume(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        name="Export Test Resume",
        role_type="Software Engineer",
        summary="Test summary.",
        markdown_content=_SAMPLE_MARKDOWN,
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume


@pytest_asyncio.fixture
async def resume_without_markdown(db_session: AsyncSession):
    """Base resume with markdown_content NULL."""
    from app.models.resume import BaseResume

    resume = BaseResume(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        name="No Markdown Resume",
        role_type="Product Manager",
        summary="Legacy resume.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume


@pytest_asyncio.fixture
async def variant_with_markdown(db_session: AsyncSession, resume_with_markdown):
    """Job variant with markdown_content populated."""
    from datetime import date

    from app.models.job_posting import JobPosting
    from app.models.persona_job import PersonaJob
    from app.models.resume import JobVariant

    posting = JobPosting(
        id=uuid.uuid4(),
        source_id=TEST_JOB_SOURCE_ID,
        job_title="Senior Engineer",
        company_name="Export Corp",
        description="Looking for an engineer.",
        first_seen_date=date(2026, 1, 15),
        description_hash="export_test_hash",
    )
    db_session.add(posting)
    await db_session.flush()

    pj = PersonaJob(
        persona_id=TEST_PERSONA_ID,
        job_posting_id=posting.id,
        status="Discovered",
        discovery_method="manual",
    )
    db_session.add(pj)
    await db_session.flush()

    variant = JobVariant(
        id=uuid.uuid4(),
        base_resume_id=resume_with_markdown.id,
        job_posting_id=posting.id,
        summary="Tailored for export test.",
        markdown_content=_SAMPLE_MARKDOWN,
    )
    db_session.add(variant)
    await db_session.commit()
    await db_session.refresh(variant)
    return variant


@pytest_asyncio.fixture
async def variant_without_markdown(db_session: AsyncSession, resume_without_markdown):
    """Job variant with markdown_content NULL."""
    from datetime import date

    from app.models.job_posting import JobPosting
    from app.models.persona_job import PersonaJob
    from app.models.resume import JobVariant

    posting = JobPosting(
        id=uuid.uuid4(),
        source_id=TEST_JOB_SOURCE_ID,
        job_title="PM Role",
        company_name="No MD Corp",
        description="Looking for a PM.",
        first_seen_date=date(2026, 2, 1),
        description_hash="no_md_variant_hash",
    )
    db_session.add(posting)
    await db_session.flush()

    pj = PersonaJob(
        persona_id=TEST_PERSONA_ID,
        job_posting_id=posting.id,
        status="Discovered",
        discovery_method="manual",
    )
    db_session.add(pj)
    await db_session.flush()

    variant = JobVariant(
        id=uuid.uuid4(),
        base_resume_id=resume_without_markdown.id,
        job_posting_id=posting.id,
        summary="No markdown content.",
    )
    db_session.add(variant)
    await db_session.commit()
    await db_session.refresh(variant)
    return variant


# =============================================================================
# Base Resume Export — PDF
# =============================================================================


class TestBaseResumeExportPdf:
    """GET /api/v1/base-resumes/{id}/export/pdf."""

    @pytest.mark.asyncio
    async def test_exports_valid_pdf(
        self, client: AsyncClient, resume_with_markdown
    ) -> None:
        """Happy path: returns PDF bytes with correct headers."""
        resp = await client.get(f"{_RESUME_URL}/{resume_with_markdown.id}/export/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "attachment" in resp.headers["content-disposition"]
        assert resp.content[:5] == b"%PDF-"

    @pytest.mark.asyncio
    async def test_returns_422_when_no_markdown(
        self, client: AsyncClient, resume_without_markdown
    ) -> None:
        """Export requires markdown_content (REQ-025 §8)."""
        resp = await client.get(
            f"{_RESUME_URL}/{resume_without_markdown.id}/export/pdf"
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_resume(
        self, client: AsyncClient
    ) -> None:
        """Unknown resume ID returns 404."""
        fake_id = uuid.uuid4()
        resp = await client.get(f"{_RESUME_URL}/{fake_id}/export/pdf")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_filename_contains_resume_name(
        self, client: AsyncClient, resume_with_markdown
    ) -> None:
        """Content-Disposition filename includes resume name and .pdf extension."""
        resp = await client.get(f"{_RESUME_URL}/{resume_with_markdown.id}/export/pdf")
        disposition = resp.headers["content-disposition"]
        assert "Export_Test_Resume" in disposition
        assert ".pdf" in disposition


# =============================================================================
# Base Resume Export — DOCX
# =============================================================================


class TestBaseResumeExportDocx:
    """GET /api/v1/base-resumes/{id}/export/docx."""

    @pytest.mark.asyncio
    async def test_exports_valid_docx(
        self, client: AsyncClient, resume_with_markdown
    ) -> None:
        """Happy path: returns DOCX bytes with correct headers."""
        resp = await client.get(f"{_RESUME_URL}/{resume_with_markdown.id}/export/docx")
        assert resp.status_code == 200
        assert (
            resp.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert "attachment" in resp.headers["content-disposition"]
        assert resp.content[:2] == b"PK"  # DOCX is a ZIP file

    @pytest.mark.asyncio
    async def test_returns_422_when_no_markdown(
        self, client: AsyncClient, resume_without_markdown
    ) -> None:
        """Export requires markdown_content (REQ-025 §8)."""
        resp = await client.get(
            f"{_RESUME_URL}/{resume_without_markdown.id}/export/docx"
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_filename_contains_resume_name(
        self, client: AsyncClient, resume_with_markdown
    ) -> None:
        """Content-Disposition filename includes resume name and .docx extension."""
        resp = await client.get(f"{_RESUME_URL}/{resume_with_markdown.id}/export/docx")
        disposition = resp.headers["content-disposition"]
        assert "Export_Test_Resume" in disposition
        assert ".docx" in disposition


# =============================================================================
# Job Variant Export — PDF
# =============================================================================


class TestJobVariantExportPdf:
    """GET /api/v1/job-variants/{id}/export/pdf."""

    @pytest.mark.asyncio
    async def test_exports_valid_pdf(
        self, client: AsyncClient, variant_with_markdown
    ) -> None:
        """Happy path: returns PDF bytes with correct headers."""
        resp = await client.get(f"{_VARIANT_URL}/{variant_with_markdown.id}/export/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert "attachment" in resp.headers["content-disposition"]
        assert resp.content[:5] == b"%PDF-"

    @pytest.mark.asyncio
    async def test_returns_422_when_no_markdown(
        self, client: AsyncClient, variant_without_markdown
    ) -> None:
        """Export requires markdown_content (REQ-025 §8)."""
        resp = await client.get(
            f"{_VARIANT_URL}/{variant_without_markdown.id}/export/pdf"
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_variant(
        self, client: AsyncClient
    ) -> None:
        """Unknown variant ID returns 404."""
        fake_id = uuid.uuid4()
        resp = await client.get(f"{_VARIANT_URL}/{fake_id}/export/pdf")
        assert resp.status_code == 404


# =============================================================================
# Job Variant Export — DOCX
# =============================================================================


class TestJobVariantExportDocx:
    """GET /api/v1/job-variants/{id}/export/docx."""

    @pytest.mark.asyncio
    async def test_exports_valid_docx(
        self, client: AsyncClient, variant_with_markdown
    ) -> None:
        """Happy path: returns DOCX bytes with correct headers."""
        resp = await client.get(
            f"{_VARIANT_URL}/{variant_with_markdown.id}/export/docx"
        )
        assert resp.status_code == 200
        assert (
            resp.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert "attachment" in resp.headers["content-disposition"]
        assert resp.content[:2] == b"PK"

    @pytest.mark.asyncio
    async def test_returns_422_when_no_markdown(
        self, client: AsyncClient, variant_without_markdown
    ) -> None:
        """Export requires markdown_content (REQ-025 §8)."""
        resp = await client.get(
            f"{_VARIANT_URL}/{variant_without_markdown.id}/export/docx"
        )
        assert resp.status_code == 422
