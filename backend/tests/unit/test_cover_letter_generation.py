"""Tests for cover letter generation service.

REQ-010 §5.3: Cover Letter Generation.
REQ-007 §8.5: Cover Letter Generation.

Tests verify:
- LLM provider is called with correct TaskType
- System + user messages are built from prompt builders
- XML response parsing (cover_letter and agent_reasoning)
- Fallback when XML tags are missing
- Error handling for provider failures and empty responses
- Result contains content, reasoning, word_count, stories_used
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.providers import ProviderError
from app.providers.llm.base import LLMResponse, TaskType
from app.schemas.prompt_params import JobContext, VoiceProfileData
from app.services.cover_letter_generation import (
    CoverLetterGenerationError,
    CoverLetterResult,
    generate_cover_letter,
)

# =============================================================================
# Fixtures
# =============================================================================


def _make_llm_response(content: str) -> LLMResponse:
    """Create a mock LLMResponse with the given content."""
    return LLMResponse(
        content=content,
        model="claude-3-5-sonnet-20241022",
        input_tokens=500,
        output_tokens=300,
        finish_reason="stop",
        latency_ms=1200.0,
    )


def _default_kwargs() -> dict:
    """Return default keyword arguments for generate_cover_letter."""
    return {
        "applicant_name": "Jane Smith",
        "current_title": "Software Engineer",
        "job": JobContext(
            job_title="Senior Developer",
            company_name="Acme Corp",
            top_skills="Python, React, AWS",
            culture_signals="Collaborative team, remote-first",
            description_excerpt="We are looking for a senior developer to join...",
        ),
        "voice": VoiceProfileData(
            tone="Professional yet warm",
            sentence_style="Concise",
            vocabulary_level="Technical",
            personality_markers="Detail-oriented",
            preferred_phrases="I bring experience in",
            things_to_avoid="synergy, leverage",
            writing_sample="In my previous role...",
        ),
        "stories": [
            {
                "title": "Led Migration",
                "rationale": "Matches AWS skill",
                "context": "Company needed AWS migration",
                "action": "Led team of 5",
                "outcome": "Reduced costs 40%",
            },
        ],
        "stories_used": ["story-1"],
    }


_XML_RESPONSE = """<cover_letter>
Dear Hiring Manager,

I was excited to see the Senior Developer position at Acme Corp. Your commitment
to collaborative, remote-first work resonates with my own values.

In my current role as a Software Engineer, I led a team of 5 engineers through
a cloud migration to AWS that reduced infrastructure costs by 40%. This experience
taught me how to balance technical excellence with practical outcomes.

I would love to bring my expertise in Python, React, and AWS to your team. Could we
schedule a call this week to discuss how I can contribute to Acme Corp's mission?

Best regards,
Jane Smith
</cover_letter>

<agent_reasoning>
I chose the cloud migration story because it directly demonstrates AWS expertise,
which is a key requirement. I emphasized cost reduction to show concrete impact.
</agent_reasoning>"""

_NO_XML_RESPONSE = """Dear Hiring Manager,

I was excited to see the Senior Developer position at Acme Corp.

Best regards,
Jane Smith"""


# =============================================================================
# Service Call Tests
# =============================================================================


class TestGenerateCoverLetter:
    """Tests for generate_cover_letter service function."""

    @pytest.mark.asyncio
    async def test_calls_provider_with_cover_letter_task_type(self) -> None:
        """Service should call LLM provider with TaskType.COVER_LETTER."""

        mock_provider = AsyncMock()
        mock_provider.complete.return_value = _make_llm_response(_XML_RESPONSE)

        with patch(
            "app.services.cover_letter_generation.factory.get_llm_provider",
            return_value=mock_provider,
        ):
            await generate_cover_letter(**_default_kwargs())

        call_kwargs = mock_provider.complete.call_args
        assert call_kwargs[1]["task"] == TaskType.COVER_LETTER

    @pytest.mark.asyncio
    async def test_builds_system_and_user_messages(self) -> None:
        """Service should build system + user messages for LLM call."""

        mock_provider = AsyncMock()
        mock_provider.complete.return_value = _make_llm_response(_XML_RESPONSE)

        with patch(
            "app.services.cover_letter_generation.factory.get_llm_provider",
            return_value=mock_provider,
        ):
            await generate_cover_letter(**_default_kwargs())

        call_kwargs = mock_provider.complete.call_args
        messages = call_kwargs[1]["messages"]
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"

    @pytest.mark.asyncio
    async def test_returns_cover_letter_result(self) -> None:
        """Service should return a CoverLetterResult dataclass."""

        mock_provider = AsyncMock()
        mock_provider.complete.return_value = _make_llm_response(_XML_RESPONSE)

        with patch(
            "app.services.cover_letter_generation.factory.get_llm_provider",
            return_value=mock_provider,
        ):
            result = await generate_cover_letter(**_default_kwargs())

        assert isinstance(result, CoverLetterResult)

    @pytest.mark.asyncio
    async def test_result_contains_content_field(self) -> None:
        """Result content should contain the cover letter text."""

        mock_provider = AsyncMock()
        mock_provider.complete.return_value = _make_llm_response(_XML_RESPONSE)

        with patch(
            "app.services.cover_letter_generation.factory.get_llm_provider",
            return_value=mock_provider,
        ):
            result = await generate_cover_letter(**_default_kwargs())

        assert "Dear Hiring Manager" in result.content
        assert "Jane Smith" in result.content

    @pytest.mark.asyncio
    async def test_result_contains_reasoning_field(self) -> None:
        """Result reasoning should contain the agent reasoning text."""

        mock_provider = AsyncMock()
        mock_provider.complete.return_value = _make_llm_response(_XML_RESPONSE)

        with patch(
            "app.services.cover_letter_generation.factory.get_llm_provider",
            return_value=mock_provider,
        ):
            result = await generate_cover_letter(**_default_kwargs())

        assert "cloud migration story" in result.reasoning

    @pytest.mark.asyncio
    async def test_result_contains_stories_used(self) -> None:
        """Result should contain stories_used from the input."""

        mock_provider = AsyncMock()
        mock_provider.complete.return_value = _make_llm_response(_XML_RESPONSE)

        with patch(
            "app.services.cover_letter_generation.factory.get_llm_provider",
            return_value=mock_provider,
        ):
            result = await generate_cover_letter(**_default_kwargs())

        assert result.stories_used == ["story-1"]

    @pytest.mark.asyncio
    async def test_result_calculates_word_count(self) -> None:
        """Result word_count should be calculated from content."""

        mock_provider = AsyncMock()
        mock_provider.complete.return_value = _make_llm_response(_XML_RESPONSE)

        with patch(
            "app.services.cover_letter_generation.factory.get_llm_provider",
            return_value=mock_provider,
        ):
            result = await generate_cover_letter(**_default_kwargs())

        assert result.word_count > 0
        # Word count should match actual content words
        expected_count = len(result.content.split())
        assert result.word_count == expected_count


# =============================================================================
# XML Parsing Tests
# =============================================================================


class TestXmlParsing:
    """Tests for XML response parsing behavior."""

    @pytest.mark.asyncio
    async def test_extracts_cover_letter_from_xml(self) -> None:
        """Should extract content from <cover_letter> tags."""

        mock_provider = AsyncMock()
        mock_provider.complete.return_value = _make_llm_response(_XML_RESPONSE)

        with patch(
            "app.services.cover_letter_generation.factory.get_llm_provider",
            return_value=mock_provider,
        ):
            result = await generate_cover_letter(**_default_kwargs())

        # Should extract content between tags, not include the tags themselves
        assert "<cover_letter>" not in result.content
        assert "</cover_letter>" not in result.content
        assert "Dear Hiring Manager" in result.content

    @pytest.mark.asyncio
    async def test_extracts_agent_reasoning_from_xml(self) -> None:
        """Should extract reasoning from <agent_reasoning> tags."""

        mock_provider = AsyncMock()
        mock_provider.complete.return_value = _make_llm_response(_XML_RESPONSE)

        with patch(
            "app.services.cover_letter_generation.factory.get_llm_provider",
            return_value=mock_provider,
        ):
            result = await generate_cover_letter(**_default_kwargs())

        assert "<agent_reasoning>" not in result.reasoning
        assert "</agent_reasoning>" not in result.reasoning

    @pytest.mark.asyncio
    async def test_fallback_when_no_xml_tags(self) -> None:
        """When no XML tags found, use full content as cover letter."""

        mock_provider = AsyncMock()
        mock_provider.complete.return_value = _make_llm_response(_NO_XML_RESPONSE)

        with patch(
            "app.services.cover_letter_generation.factory.get_llm_provider",
            return_value=mock_provider,
        ):
            result = await generate_cover_letter(**_default_kwargs())

        assert "Dear Hiring Manager" in result.content
        assert result.reasoning == ""


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in cover letter generation."""

    @pytest.mark.asyncio
    async def test_provider_error_raises_generation_error(self) -> None:
        """ProviderError should be wrapped in CoverLetterGenerationError."""

        mock_provider = AsyncMock()
        mock_provider.complete.side_effect = ProviderError("API unavailable")

        with (
            patch(
                "app.services.cover_letter_generation.factory.get_llm_provider",
                return_value=mock_provider,
            ),
            pytest.raises(CoverLetterGenerationError, match="Please try again"),
        ):
            await generate_cover_letter(**_default_kwargs())

    @pytest.mark.asyncio
    async def test_empty_response_raises_generation_error(self) -> None:
        """Empty LLM response content should raise CoverLetterGenerationError."""

        mock_provider = AsyncMock()
        mock_provider.complete.return_value = _make_llm_response("")

        with (
            patch(
                "app.services.cover_letter_generation.factory.get_llm_provider",
                return_value=mock_provider,
            ),
            pytest.raises(CoverLetterGenerationError, match="empty"),
        ):
            await generate_cover_letter(**_default_kwargs())

    @pytest.mark.asyncio
    async def test_none_response_raises_generation_error(self) -> None:
        """None LLM response content should raise CoverLetterGenerationError."""

        mock_provider = AsyncMock()
        mock_provider.complete.return_value = LLMResponse(
            content=None,
            model="claude-3-5-sonnet-20241022",
            input_tokens=500,
            output_tokens=0,
            finish_reason="stop",
            latency_ms=1200.0,
        )

        with (
            patch(
                "app.services.cover_letter_generation.factory.get_llm_provider",
                return_value=mock_provider,
            ),
            pytest.raises(CoverLetterGenerationError, match="empty"),
        ):
            await generate_cover_letter(**_default_kwargs())

    @pytest.mark.asyncio
    async def test_generation_error_is_exception(self) -> None:
        """CoverLetterGenerationError should be a standard Exception."""

        error = CoverLetterGenerationError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"
