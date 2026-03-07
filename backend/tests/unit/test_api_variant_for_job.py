"""Tests for POST /api/v1/job-variants/create-for-job endpoint.

REQ-027 §3: Job Variant Creation — two paths (manual + AI tailoring).
REQ-027 §6.2: LLM tailoring prompt integration.
REQ-027 §7: Validation rules for variant creation.

Tests verify:
- Manual path: copies base resume markdown to new variant
- AI path: LLM tailors resume markdown for job fit
- Credit gating: AI path returns 402 when balance insufficient
- Validation: requires auth, valid base resume, valid job posting
- Approval: snapshots markdown_content on approval
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.resume_tailoring_service import ResumeTailoringError
from tests.conftest import TEST_JOB_SOURCE_ID, TEST_PERSONA_ID

_BASE_URL = "/api/v1/job-variants"
_CREATE_URL = f"{_BASE_URL}/create-for-job"
_SVC = "app.api.v1.job_variants"

_TAILORED_MARKDOWN = "# John Doe\n\n## Summary\n\nTailored for the role.\n"
_BASE_MARKDOWN = "# John Doe\n\n## Summary\n\nExperienced Python developer.\n"


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
        name="Python Dev Resume",
        role_type="Software Engineer",
        summary="Experienced Python developer.",
        markdown_content=_BASE_MARKDOWN,
        included_jobs=["job-1"],
        included_education=["edu-1"],
        included_certifications=[],
        skills_emphasis=["python", "fastapi"],
        job_bullet_selections={"job-1": ["b1"]},
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume


@pytest_asyncio.fixture
async def resume_no_markdown(db_session: AsyncSession):
    """Base resume without markdown_content."""
    from app.models.resume import BaseResume

    resume = BaseResume(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        name="No Markdown Resume",
        role_type="Product Manager",
        summary="Product manager summary.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume


@pytest_asyncio.fixture
async def job_posting(db_session: AsyncSession):
    """Job posting linked to test persona via PersonaJob."""
    from datetime import date

    from app.models.job_posting import JobPosting
    from app.models.persona_job import PersonaJob

    posting = JobPosting(
        id=uuid.uuid4(),
        source_id=TEST_JOB_SOURCE_ID,
        job_title="Senior Backend Engineer",
        company_name="Acme Corp",
        description="Looking for a senior backend engineer with Python expertise.",
        requirements="Python, FastAPI, PostgreSQL, 5+ years",
        first_seen_date=date(2026, 1, 15),
        description_hash="variant_test_hash",
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
    await db_session.commit()
    await db_session.refresh(posting)
    return posting


# =============================================================================
# Manual Path
# =============================================================================


class TestCreateForJobManual:
    """POST /api/v1/job-variants/create-for-job with method=manual."""

    @pytest.mark.asyncio
    async def test_manual_creates_variant_with_copied_markdown(
        self, client: AsyncClient, resume_with_markdown, job_posting
    ) -> None:
        """Manual path copies base resume markdown_content to the new variant."""
        payload = {
            "base_resume_id": str(resume_with_markdown.id),
            "job_posting_id": str(job_posting.id),
            "method": "manual",
        }
        resp = await client.post(_CREATE_URL, json=payload)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["markdown_content"] == _BASE_MARKDOWN
        assert data["status"] == "Draft"
        assert data["base_resume_id"] == str(resume_with_markdown.id)
        assert data["job_posting_id"] == str(job_posting.id)

    @pytest.mark.asyncio
    async def test_manual_auto_generates_summary(
        self, client: AsyncClient, resume_with_markdown, job_posting
    ) -> None:
        """Manual path auto-generates a summary from resume name and job title."""
        payload = {
            "base_resume_id": str(resume_with_markdown.id),
            "job_posting_id": str(job_posting.id),
            "method": "manual",
        }
        resp = await client.post(_CREATE_URL, json=payload)
        assert resp.status_code == 201
        summary = resp.json()["data"]["summary"]
        assert "Python Dev Resume" in summary
        assert "Senior Backend Engineer" in summary

    @pytest.mark.asyncio
    async def test_manual_no_markdown_creates_empty(
        self, client: AsyncClient, resume_no_markdown, job_posting
    ) -> None:
        """Manual path with no base markdown creates variant with null markdown."""
        payload = {
            "base_resume_id": str(resume_no_markdown.id),
            "job_posting_id": str(job_posting.id),
            "method": "manual",
        }
        resp = await client.post(_CREATE_URL, json=payload)
        assert resp.status_code == 201
        assert resp.json()["data"]["markdown_content"] is None

    @pytest.mark.asyncio
    async def test_manual_succeeds_with_zero_balance(
        self, client: AsyncClient, resume_with_markdown, job_posting
    ) -> None:
        """Manual path does not require credits — works even with zero balance."""
        original = settings.metering_enabled
        settings.metering_enabled = True
        try:
            from app.api.deps import require_sufficient_balance
            from app.core.errors import InsufficientBalanceError
            from app.main import app

            async def _raise_402() -> None:
                raise InsufficientBalanceError(
                    balance=Decimal("0.000000"),
                    minimum_required=Decimal("0.010000"),
                )

            app.dependency_overrides[require_sufficient_balance] = _raise_402
            try:
                payload = {
                    "base_resume_id": str(resume_with_markdown.id),
                    "job_posting_id": str(job_posting.id),
                    "method": "manual",
                }
                resp = await client.post(_CREATE_URL, json=payload)
                # Manual path should succeed despite zero balance
                assert resp.status_code == 201
            finally:
                app.dependency_overrides.pop(require_sufficient_balance, None)
        finally:
            settings.metering_enabled = original


# =============================================================================
# AI Path
# =============================================================================


class TestCreateForJobAI:
    """POST /api/v1/job-variants/create-for-job with method=ai."""

    @pytest.mark.asyncio
    async def test_ai_creates_variant_with_tailored_markdown(
        self,
        client: AsyncClient,
        resume_with_markdown,
        job_posting,
    ) -> None:
        """AI path calls LLM and saves tailored markdown to new variant."""
        with patch(
            f"{_SVC}.tailor_resume_markdown",
            new_callable=AsyncMock,
            return_value=(_TAILORED_MARKDOWN, {"model": "test-model"}),
        ) as mock_tailor:
            payload = {
                "base_resume_id": str(resume_with_markdown.id),
                "job_posting_id": str(job_posting.id),
                "method": "ai",
            }
            resp = await client.post(_CREATE_URL, json=payload)

        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["markdown_content"] == _TAILORED_MARKDOWN
        assert data["status"] == "Draft"
        mock_tailor.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ai_returns_502_on_tailoring_error(
        self, client: AsyncClient, resume_with_markdown, job_posting
    ) -> None:
        """AI path returns 502 when LLM tailoring fails."""
        with patch(
            f"{_SVC}.tailor_resume_markdown",
            new_callable=AsyncMock,
            side_effect=ResumeTailoringError("LLM call failed"),
        ):
            payload = {
                "base_resume_id": str(resume_with_markdown.id),
                "job_posting_id": str(job_posting.id),
                "method": "ai",
            }
            resp = await client.post(_CREATE_URL, json=payload)

        assert resp.status_code == 502
        body = resp.json()
        assert body["error"]["code"] == "RESUME_TAILORING_ERROR"

    @pytest.mark.asyncio
    async def test_ai_requires_base_resume_markdown(
        self, client: AsyncClient, resume_no_markdown, job_posting
    ) -> None:
        """AI path returns 400 when base resume has no markdown_content."""
        payload = {
            "base_resume_id": str(resume_no_markdown.id),
            "job_posting_id": str(job_posting.id),
            "method": "ai",
        }
        resp = await client.post(_CREATE_URL, json=payload)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_ai_returns_402_insufficient_credits(
        self, client: AsyncClient, resume_with_markdown, job_posting
    ) -> None:
        """AI path returns 402 when user has insufficient balance."""
        original = settings.metering_enabled
        settings.metering_enabled = True
        try:
            from app.api.deps import require_sufficient_balance
            from app.core.errors import InsufficientBalanceError
            from app.main import app

            async def _raise_402() -> None:
                raise InsufficientBalanceError(
                    balance=Decimal("0.000000"),
                    minimum_required=Decimal("0.010000"),
                )

            app.dependency_overrides[require_sufficient_balance] = _raise_402
            try:
                payload = {
                    "base_resume_id": str(resume_with_markdown.id),
                    "job_posting_id": str(job_posting.id),
                    "method": "ai",
                }
                resp = await client.post(_CREATE_URL, json=payload)
                assert resp.status_code == 402
            finally:
                app.dependency_overrides.pop(require_sufficient_balance, None)
        finally:
            settings.metering_enabled = original


# =============================================================================
# Validation
# =============================================================================


class TestCreateForJobValidation:
    """Validation tests for POST /api/v1/job-variants/create-for-job."""

    @pytest.mark.asyncio
    async def test_requires_auth(self, unauthenticated_client: AsyncClient) -> None:
        """Unauthenticated request returns 401."""
        resp = await unauthenticated_client.post(_CREATE_URL, json={"method": "manual"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_base_resume_returns_404(
        self, client: AsyncClient, job_posting
    ) -> None:
        """Non-existent base_resume_id returns 404."""
        payload = {
            "base_resume_id": str(uuid.uuid4()),
            "job_posting_id": str(job_posting.id),
            "method": "manual",
        }
        resp = await client.post(_CREATE_URL, json=payload)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_job_posting_returns_404(
        self, client: AsyncClient, resume_with_markdown
    ) -> None:
        """Non-existent job_posting_id returns 404."""
        payload = {
            "base_resume_id": str(resume_with_markdown.id),
            "job_posting_id": str(uuid.uuid4()),
            "method": "manual",
        }
        resp = await client.post(_CREATE_URL, json=payload)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_method_returns_400(
        self, client: AsyncClient, resume_with_markdown, job_posting
    ) -> None:
        """Invalid method value returns 400."""
        payload = {
            "base_resume_id": str(resume_with_markdown.id),
            "job_posting_id": str(job_posting.id),
            "method": "invalid",
        }
        resp = await client.post(_CREATE_URL, json=payload)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_method_returns_400(
        self, client: AsyncClient, resume_with_markdown, job_posting
    ) -> None:
        """Missing method field returns 400."""
        payload = {
            "base_resume_id": str(resume_with_markdown.id),
            "job_posting_id": str(job_posting.id),
        }
        resp = await client.post(_CREATE_URL, json=payload)
        assert resp.status_code == 400


# =============================================================================
# Approval Snapshots Markdown (REQ-027 §6.3)
# =============================================================================


class TestApprovalSnapshotsMarkdown:
    """POST /api/v1/job-variants/{id}/approve snapshots markdown_content."""

    @pytest.mark.asyncio
    async def test_approve_snapshots_markdown_content(
        self, client: AsyncClient, resume_with_markdown, job_posting
    ) -> None:
        """Approval copies variant's markdown_content to snapshot_markdown_content."""
        # Create variant with markdown via manual path
        create_resp = await client.post(
            _CREATE_URL,
            json={
                "base_resume_id": str(resume_with_markdown.id),
                "job_posting_id": str(job_posting.id),
                "method": "manual",
            },
        )
        variant_id = create_resp.json()["data"]["id"]

        # Approve
        approve_resp = await client.post(f"{_BASE_URL}/{variant_id}/approve")
        assert approve_resp.status_code == 200
        data = approve_resp.json()["data"]
        assert data["snapshot_markdown_content"] == _BASE_MARKDOWN

    @pytest.mark.asyncio
    async def test_approve_null_markdown_snapshots_null(
        self, client: AsyncClient, resume_no_markdown, job_posting
    ) -> None:
        """Approval with null markdown_content snapshots null."""
        create_resp = await client.post(
            _CREATE_URL,
            json={
                "base_resume_id": str(resume_no_markdown.id),
                "job_posting_id": str(job_posting.id),
                "method": "manual",
            },
        )
        variant_id = create_resp.json()["data"]["id"]

        approve_resp = await client.post(f"{_BASE_URL}/{variant_id}/approve")
        assert approve_resp.status_code == 200
        data = approve_resp.json()["data"]
        assert data["snapshot_markdown_content"] is None
