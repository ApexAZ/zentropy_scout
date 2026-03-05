"""Tests for resume_generation_service.llm_generate() — LLM-assisted generation.

REQ-026 §4.4: LLM generation gathers persona data, builds prompt with
template structure + persona + voice profile + generation options, calls
LLM via MeteredLLMProvider, returns (markdown, metadata).

Tests verify:
- llm_generate() calls gather_base_resume_content for persona data
- llm_generate() calls build_resume_generation_prompt with correct args
- llm_generate() calls provider.complete() with RESUME_TAILORING task
- llm_generate() returns (markdown_content, metadata) tuple
- Metadata includes model, token counts, word count
- Provider errors propagate as ResumeGenerationError
- Empty LLM response raises ResumeGenerationError
"""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.providers.errors import ProviderError
from app.providers.llm.base import TaskType
from app.services.pdf_generation import (
    ResumeCertificationEntry,
    ResumeContactInfo,
    ResumeContent,
    ResumeEducationEntry,
    ResumeJobEntry,
    ResumeSkillEntry,
)
from app.services.resume_generation_service import (
    ResumeGenerationError,
    llm_generate,
)

# Module path for patching
_MODULE = "app.services.resume_generation_service"
_MOCK_VOICE_BLOCK = "<voice_profile>...</voice_profile>"
_MOCK_PROMPT = "mocked prompt"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_content() -> ResumeContent:
    """Build a ResumeContent with sensible defaults."""
    return ResumeContent(
        contact=ResumeContactInfo(
            full_name="Jane Doe",
            email="jane@example.com",
            phone="555-0100",
            city="Denver",
            state="CO",
            linkedin_url="linkedin.com/in/janedoe",
            portfolio_url=None,
        ),
        summary="Experienced software engineer with 10 years in backend systems.",
        jobs=[
            ResumeJobEntry(
                job_title="Senior Engineer",
                company_name="Acme Corp",
                location="Denver, CO",
                start_date=date(2020, 3, 1),
                end_date=None,
                is_current=True,
                bullets=["Led backend migration", "Improved API latency by 40%"],
            ),
        ],
        education=[
            ResumeEducationEntry(
                degree="B.S. Computer Science",
                institution="State University",
                field_of_study="Computer Science",
                graduation_year=2018,
            ),
        ],
        certifications=[
            ResumeCertificationEntry(
                certification_name="AWS Solutions Architect",
                issuing_organization="Amazon",
                date_obtained=date(2021, 6, 15),
            ),
        ],
        skills=[
            ResumeSkillEntry(
                skill_name="Python", skill_type="technical", category="Languages"
            ),
            ResumeSkillEntry(
                skill_name="PostgreSQL",
                skill_type="technical",
                category="Databases",
            ),
        ],
    )


@dataclass
class FakeLLMResponse:
    """Minimal LLM response for testing."""

    content: str | None
    model: str = "claude-sonnet-4-20250514"
    input_tokens: int = 500
    output_tokens: int = 300
    finish_reason: str = "stop"
    latency_ms: float = 1200.0
    tool_calls: list[object] | None = None


def _make_provider(
    response_content: str = "# Jane Doe\n\n## Summary\nGenerated resume content.",
) -> AsyncMock:
    """Build a mock LLM provider that returns a canned response."""
    provider = AsyncMock()
    provider.complete = AsyncMock(
        return_value=FakeLLMResponse(content=response_content)
    )
    provider.provider_name = "claude"
    return provider


@dataclass
class FakeVoiceProfile:
    """Minimal voice profile for testing."""

    tone: str = "professional"
    sentence_style: str = "concise"
    vocabulary_level: str = "formal"
    personality_markers: str = "confident, analytical"
    sample_phrases: list[str] | None = None
    things_to_avoid: list[str] | None = None
    writing_sample_text: str | None = None


_DEFAULT_OPTIONS: dict = {
    "page_limit": 1,
    "emphasis": "balanced",
    "include_sections": ["summary", "experience", "education", "skills"],
}


@contextmanager
def _patch_llm_deps(
    content: ResumeContent,
) -> Generator[dict[str, AsyncMock], None, None]:
    """Patch all llm_generate dependencies, yielding named mocks."""
    voice = FakeVoiceProfile()
    with (
        patch(
            f"{_MODULE}.gather_base_resume_content", return_value=content
        ) as mock_gather,
        patch(f"{_MODULE}._get_voice_profile", return_value=voice),
        patch(f"{_MODULE}.build_voice_profile_block", return_value=_MOCK_VOICE_BLOCK),
        patch(
            f"{_MODULE}.build_resume_generation_prompt", return_value=_MOCK_PROMPT
        ) as mock_build,
    ):
        yield {"gather": mock_gather, "build_prompt": mock_build}


async def _generate(
    provider: AsyncMock, content: ResumeContent | None = None, **overrides: object
) -> tuple[str, dict]:
    """Run llm_generate with patched dependencies."""
    if content is None:
        content = _make_content()
    opts = {**_DEFAULT_OPTIONS, **overrides}
    with _patch_llm_deps(content):
        return await llm_generate(
            resume=AsyncMock(id="resume-1"),
            template=AsyncMock(
                markdown_content="# {full_name}\n\n## Summary\n\n## Experience"
            ),
            session=AsyncMock(),
            provider=provider,
            **opts,
        )


# ---------------------------------------------------------------------------
# Happy Path
# ---------------------------------------------------------------------------


class TestLlmGenerateHappyPath:
    """Verify llm_generate() orchestrates correctly."""

    async def test_returns_markdown_and_metadata(self) -> None:
        provider = _make_provider()
        markdown, metadata = await _generate(provider)

        assert markdown == "# Jane Doe\n\n## Summary\nGenerated resume content."
        assert metadata["model"] == "claude-sonnet-4-20250514"
        assert metadata["input_tokens"] == 500
        assert metadata["output_tokens"] == 300

    async def test_calls_provider_with_resume_tailoring_task(self) -> None:
        provider = _make_provider()
        await _generate(provider)

        provider.complete.assert_called_once()
        call_kwargs = provider.complete.call_args
        assert call_kwargs.kwargs["task"] == TaskType.RESUME_TAILORING

    async def test_metadata_includes_word_count(self) -> None:
        provider = _make_provider("# Jane Doe\n\nThree word summary.")
        _, metadata = await _generate(provider)

        assert "word_count" in metadata
        assert metadata["word_count"] > 0

    async def test_gathers_persona_data(self) -> None:
        content = _make_content()
        provider = _make_provider()
        with _patch_llm_deps(content) as mocks:
            await llm_generate(
                resume=AsyncMock(id="resume-1"),
                template=AsyncMock(markdown_content="# Resume"),
                session=AsyncMock(),
                provider=provider,
                **_DEFAULT_OPTIONS,
            )
        mocks["gather"].assert_called_once()

    async def test_builds_prompt_with_persona_data(self) -> None:
        content = _make_content()
        provider = _make_provider()
        with _patch_llm_deps(content) as mocks:
            await llm_generate(
                resume=AsyncMock(id="resume-1"),
                template=AsyncMock(markdown_content="# Resume"),
                session=AsyncMock(),
                provider=provider,
                **_DEFAULT_OPTIONS,
            )
        call_kwargs = mocks["build_prompt"].call_args.kwargs
        assert call_kwargs["persona_name"] == "Jane Doe"
        assert call_kwargs["page_limit"] == 1
        assert call_kwargs["emphasis"] == "balanced"


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


class TestLlmGenerateErrors:
    """Verify error conditions are handled correctly."""

    async def test_empty_response_raises_error(self) -> None:
        provider = _make_provider()
        provider.complete = AsyncMock(return_value=FakeLLMResponse(content=None))

        with pytest.raises(ResumeGenerationError):
            await _generate(provider)

    async def test_empty_string_response_raises_error(self) -> None:
        provider = _make_provider()
        provider.complete = AsyncMock(return_value=FakeLLMResponse(content=""))

        with pytest.raises(ResumeGenerationError):
            await _generate(provider)

    async def test_provider_error_raises_resume_generation_error(self) -> None:
        provider = _make_provider()
        provider.complete = AsyncMock(side_effect=ProviderError("LLM failed"))

        with pytest.raises(ResumeGenerationError):
            await _generate(provider)
