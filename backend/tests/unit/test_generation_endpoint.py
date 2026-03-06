"""Tests for POST /api/v1/base-resumes/{id}/generate endpoint.

REQ-026 §4.6: Generation API — fork on method (ai vs template_fill).
REQ-026 §3.4: Deterministic template fill (free path).
REQ-026 §8: Validation — page_limit 1-3, credits required for LLM.

Tests verify:
- Template fill happy path — calls template_fill(), saves markdown
- AI generation happy path — calls llm_generate(), saves markdown
- AI generation returns 402 when credits insufficient
- Returns 404 for nonexistent resume
- Returns 400 for invalid page_limit
- Returns 400 when template not resolvable
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from tests.conftest import TEST_PERSONA_ID

_URL = "/api/v1/base-resumes"
_SVC = "app.api.v1.base_resumes"

_GENERATED_MARKDOWN = "# John Doe\n\n## Summary\n\nExperienced developer.\n"


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def resume_for_generation(db_session: AsyncSession):
    """Base resume with template_id set, no markdown_content yet."""
    from app.models.resume import BaseResume
    from app.models.resume_template import ResumeTemplate

    template = ResumeTemplate(
        id=uuid.uuid4(),
        name="Test Template",
        markdown_content="# {full_name}\n\n{summary}\n",
        is_system=True,
    )
    db_session.add(template)
    await db_session.flush()

    resume = BaseResume(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        name="Gen Test Resume",
        role_type="Software Engineer",
        summary="Test summary.",
        template_id=template.id,
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume, template


@pytest_asyncio.fixture
async def resume_no_template(db_session: AsyncSession):
    """Base resume with no template_id set."""
    from app.models.resume import BaseResume

    resume = BaseResume(
        id=uuid.uuid4(),
        persona_id=TEST_PERSONA_ID,
        name="No Template Resume",
        role_type="Product Manager",
        summary="No template.",
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)
    return resume


# =============================================================================
# Template Fill Path
# =============================================================================


class TestGenerateTemplateFill:
    """POST /api/v1/base-resumes/{id}/generate with method=template_fill."""

    @pytest.mark.asyncio
    async def test_template_fill_happy_path(
        self, client: AsyncClient, resume_for_generation, db_session: AsyncSession
    ) -> None:
        """Template fill calls service and saves markdown_content."""
        resume, template = resume_for_generation

        with patch(
            f"{_SVC}.template_fill",
            new_callable=AsyncMock,
            return_value=_GENERATED_MARKDOWN,
        ) as mock_fill:
            resp = await client.post(
                f"{_URL}/{resume.id}/generate",
                json={
                    "method": "template_fill",
                    "template_id": str(template.id),
                },
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["markdown_content"] == _GENERATED_MARKDOWN
        assert data["method"] == "template_fill"
        assert data["model_used"] is None
        assert data["generation_cost_cents"] == 0
        assert data["word_count"] > 0
        mock_fill.assert_awaited_once()

        # Verify content was saved to DB
        await db_session.refresh(resume)
        assert resume.markdown_content == _GENERATED_MARKDOWN

    @pytest.mark.asyncio
    async def test_template_fill_uses_resume_template_when_no_template_id(
        self, client: AsyncClient, resume_for_generation
    ) -> None:
        """When template_id not in request, uses resume's existing template_id."""
        resume, _template = resume_for_generation

        with patch(
            f"{_SVC}.template_fill",
            new_callable=AsyncMock,
            return_value=_GENERATED_MARKDOWN,
        ):
            resp = await client.post(
                f"{_URL}/{resume.id}/generate",
                json={"method": "template_fill"},
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_template_fill_returns_400_when_no_template(
        self, client: AsyncClient, resume_no_template
    ) -> None:
        """Template fill requires a template (from request or resume)."""
        resp = await client.post(
            f"{_URL}/{resume_no_template.id}/generate",
            json={"method": "template_fill"},
        )
        assert resp.status_code == 400


# =============================================================================
# AI Generation Path
# =============================================================================


class TestGenerateAI:
    """POST /api/v1/base-resumes/{id}/generate with method=ai."""

    @pytest.mark.asyncio
    async def test_ai_generation_happy_path(
        self, client: AsyncClient, resume_for_generation, db_session: AsyncSession
    ) -> None:
        """AI generation calls llm_generate and saves markdown_content."""
        resume, template = resume_for_generation
        metadata = {
            "model": "claude-sonnet-4-20250514",
            "input_tokens": 500,
            "output_tokens": 200,
            "word_count": 42,
        }

        with patch(
            f"{_SVC}.llm_generate",
            new_callable=AsyncMock,
            return_value=(_GENERATED_MARKDOWN, metadata),
        ) as mock_gen:
            resp = await client.post(
                f"{_URL}/{resume.id}/generate",
                json={
                    "method": "ai",
                    "template_id": str(template.id),
                    "page_limit": 2,
                    "emphasis": "technical",
                    "include_sections": ["summary", "experience", "skills"],
                },
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["markdown_content"] == _GENERATED_MARKDOWN
        assert data["method"] == "ai"
        assert data["model_used"] == "claude-sonnet-4-20250514"
        assert data["word_count"] > 0
        mock_gen.assert_awaited_once()

        # Verify saved to DB
        await db_session.refresh(resume)
        assert resume.markdown_content == _GENERATED_MARKDOWN

    @pytest.mark.asyncio
    async def test_ai_generation_returns_402_when_insufficient_credits(
        self, client: AsyncClient, resume_for_generation
    ) -> None:
        """AI generation requires credits — returns 402 when insufficient."""
        resume, template = resume_for_generation

        # Enable metering to activate BalanceCheck
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
                resp = await client.post(
                    f"{_URL}/{resume.id}/generate",
                    json={
                        "method": "ai",
                        "template_id": str(template.id),
                    },
                )
                assert resp.status_code == 402
            finally:
                app.dependency_overrides.pop(require_sufficient_balance, None)
        finally:
            settings.metering_enabled = original


# =============================================================================
# Validation
# =============================================================================


class TestGenerateValidation:
    """Validation tests for POST /api/v1/base-resumes/{id}/generate."""

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_resume(
        self, client: AsyncClient
    ) -> None:
        """Unknown resume ID returns 404."""
        fake_id = uuid.uuid4()
        resp = await client.post(
            f"{_URL}/{fake_id}/generate",
            json={"method": "template_fill"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_page_limit_zero(
        self, client: AsyncClient, resume_for_generation
    ) -> None:
        """page_limit must be 1-3."""
        resume, template = resume_for_generation
        resp = await client.post(
            f"{_URL}/{resume.id}/generate",
            json={
                "method": "ai",
                "template_id": str(template.id),
                "page_limit": 0,
            },
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_page_limit_four(
        self, client: AsyncClient, resume_for_generation
    ) -> None:
        """page_limit must be 1-3."""
        resume, template = resume_for_generation
        resp = await client.post(
            f"{_URL}/{resume.id}/generate",
            json={
                "method": "ai",
                "template_id": str(template.id),
                "page_limit": 4,
            },
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_method(
        self, client: AsyncClient, resume_for_generation
    ) -> None:
        """Method must be 'ai' or 'template_fill'."""
        resume, _template = resume_for_generation
        resp = await client.post(
            f"{_URL}/{resume.id}/generate",
            json={"method": "invalid_method"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_template_id(
        self, client: AsyncClient, resume_for_generation
    ) -> None:
        """Template ID must reference an existing template."""
        resume, _template = resume_for_generation
        fake_template_id = uuid.uuid4()
        resp = await client.post(
            f"{_URL}/{resume.id}/generate",
            json={
                "method": "template_fill",
                "template_id": str(fake_template_id),
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_for_other_users_private_template(
        self, client: AsyncClient, resume_for_generation, db_session: AsyncSession
    ) -> None:
        """Cannot use another user's private template (IDOR prevention)."""
        from app.models import User
        from app.models.resume_template import ResumeTemplate
        from tests.conftest import USER_B_ID

        # Ensure User B exists for FK constraint
        existing = await db_session.get(User, USER_B_ID)
        if not existing:
            db_session.add(User(id=USER_B_ID, email="userb@example.com"))
            await db_session.flush()

        other_user_template = ResumeTemplate(
            id=uuid.uuid4(),
            name="Private Template",
            markdown_content="# Private\n",
            is_system=False,
            user_id=USER_B_ID,
        )
        db_session.add(other_user_template)
        await db_session.commit()

        resume, _template = resume_for_generation
        resp = await client.post(
            f"{_URL}/{resume.id}/generate",
            json={
                "method": "template_fill",
                "template_id": str(other_user_template.id),
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_defaults_page_limit_to_one(
        self, client: AsyncClient, resume_for_generation
    ) -> None:
        """page_limit defaults to 1 when not provided."""
        resume, template = resume_for_generation

        with patch(
            f"{_SVC}.llm_generate",
            new_callable=AsyncMock,
            return_value=(
                _GENERATED_MARKDOWN,
                {
                    "model": "test",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "word_count": 5,
                },
            ),
        ) as mock_gen:
            resp = await client.post(
                f"{_URL}/{resume.id}/generate",
                json={
                    "method": "ai",
                    "template_id": str(template.id),
                },
            )

        assert resp.status_code == 200
        call_kwargs = mock_gen.call_args.kwargs
        assert call_kwargs["page_limit"] == 1
