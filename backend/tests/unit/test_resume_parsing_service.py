"""Tests for resume parsing service.

REQ-019 §6–§7: ResumeParsingService extracts structured persona data
from PDF resumes using pdfplumber for text extraction and LLM for
structured parsing.

Tests verify:
- PDF text extraction via pdfplumber
- LLM-based structured parsing of resume text
- Output schema: basic_info, work_history, education, skills, certifications, voice_suggestions
- Voice confidence threshold (≥0.7 for pre-population)
- File size validation (10MB limit)
- PDF page count limit (50 pages)
- Text length cap before LLM call (50k chars)
- Error handling for corrupt PDFs, LLM failures, malformed responses
- Input sanitization before LLM calls
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.llm.base import LLMResponse, TaskType
from app.services.resume_parsing_service import (
    _MAX_EXTRACTED_TEXT_LENGTH,
    _MAX_PDF_PAGES,
    RESUME_PARSE_SYSTEM_PROMPT,
    ResumeParseResult,
    ResumeParsingService,
    VoiceSuggestions,
)


def _make_llm_response(data: dict) -> LLMResponse:
    """Build a mock LLMResponse with JSON content."""
    return LLMResponse(
        content=json.dumps(data),
        model="gemini-2.5-flash",
        input_tokens=100,
        output_tokens=200,
        finish_reason="stop",
        latency_ms=500.0,
    )


def _full_resume_data() -> dict:
    """Return a complete resume parse response matching REQ-019 §6.2 schema."""
    return {
        "basic_info": {
            "full_name": "Jane Smith",
            "email": "jane@example.com",
            "phone": "555-0100",
            "location": "San Francisco, CA",
            "linkedin_url": "https://linkedin.com/in/janesmith",
            "portfolio_url": "https://janesmith.dev",
        },
        "work_history": [
            {
                "job_title": "Senior Software Engineer",
                "company_name": "TechCorp",
                "start_date": "2020-03",
                "end_date": None,
                "is_current": True,
                "bullets": [
                    "Led migration to microservices",
                    "Reduced deploy time by 40%",
                ],
            },
            {
                "job_title": "Software Engineer",
                "company_name": "StartupInc",
                "start_date": "2017-06",
                "end_date": "2020-02",
                "is_current": False,
                "bullets": ["Built REST API serving 10k req/s"],
            },
        ],
        "education": [
            {
                "institution": "MIT",
                "degree": "B.S.",
                "field_of_study": "Computer Science",
                "graduation_date": "2017-05",
            }
        ],
        "skills": [
            {
                "name": "Python",
                "type": "Hard",
                "proficiency": "Expert",
            },
            {
                "name": "Leadership",
                "type": "Soft",
                "proficiency": "Proficient",
            },
        ],
        "certifications": [
            {
                "name": "AWS Solutions Architect",
                "issuer": "Amazon",
                "date_obtained": "2021-09",
            }
        ],
        "voice_suggestions": {
            "writing_style": "results-focused",
            "vocabulary_level": "technical",
            "personality_markers": "collaborative, data-driven",
            "confidence": 0.85,
        },
    }


_FAKE_PDF_BYTES = b"%PDF-1.4 fake pdf content for testing"
_PATCH_PDFPLUMBER = "app.services.resume_parsing_service.pdfplumber"
_PATCH_SANITIZE = "app.services.resume_parsing_service.sanitize_llm_input"


def _mock_pdfplumber_pages(
    texts: list[str | None],
) -> MagicMock:
    """Build a mock pdfplumber.open() context manager with given page texts."""
    pages = []
    for text in texts:
        page = MagicMock()
        page.extract_text.return_value = text
        pages.append(page)

    mock_pdf = MagicMock()
    mock_pdf.pages = pages
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)

    mock_module = MagicMock()
    mock_module.open.return_value = mock_pdf
    return mock_module


def _mock_pdfplumber(text: str = "Jane Smith\nSenior Engineer") -> MagicMock:
    """Build a single-page mock pdfplumber."""
    return _mock_pdfplumber_pages([text])


# =============================================================================
# ResumeParseResult dataclass
# =============================================================================


class TestResumeParseResult:
    """ResumeParseResult holds structured resume data."""

    def test_result_has_all_fields(self) -> None:
        """Result contains all required schema fields."""
        result = ResumeParseResult(
            basic_info={"full_name": "Test"},
            work_history=(),
            education=(),
            skills=(),
            certifications=(),
            voice_suggestions=None,
            raw_text="Resume text",
        )
        assert result.basic_info == {"full_name": "Test"}
        assert result.work_history == ()
        assert result.raw_text == "Resume text"

    def test_result_is_frozen(self) -> None:
        """ResumeParseResult is immutable."""
        result = ResumeParseResult(
            basic_info={},
            work_history=(),
            education=(),
            skills=(),
            certifications=(),
            voice_suggestions=None,
            raw_text="",
        )
        with pytest.raises(AttributeError):
            result.raw_text = "changed"  # type: ignore[misc]


# =============================================================================
# VoiceSuggestions dataclass
# =============================================================================


class TestVoiceSuggestions:
    """VoiceSuggestions captures voice profile inference."""

    def test_high_confidence_is_usable(self) -> None:
        """Confidence >= 0.7 means voice data should pre-populate form."""
        voice = VoiceSuggestions(
            writing_style="results-focused",
            vocabulary_level="technical",
            personality_markers="collaborative",
            confidence=0.85,
        )
        assert voice.confidence >= 0.7

    def test_low_confidence_below_threshold(self) -> None:
        """Confidence < 0.7 means voice data should NOT pre-populate."""
        voice = VoiceSuggestions(
            writing_style="concise",
            vocabulary_level="accessible",
            personality_markers="independent",
            confidence=0.4,
        )
        assert voice.confidence < 0.7

    @pytest.mark.asyncio
    async def test_out_of_range_confidence_is_clamped(self) -> None:
        """LLM returning confidence > 1.0 is clamped to 1.0."""
        data = _full_resume_data()
        data["voice_suggestions"]["confidence"] = 999.9
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(return_value=_make_llm_response(data))

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        assert result.voice_suggestions is not None
        assert result.voice_suggestions.confidence == 1.0


# =============================================================================
# PDF text extraction
# =============================================================================


class TestPDFTextExtraction:
    """Tests for pdfplumber-based PDF text extraction."""

    @pytest.mark.asyncio
    async def test_extracts_text_from_pdf(self) -> None:
        """Extracts text from all pages and joins them."""
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=_make_llm_response(_full_resume_data())
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber("Page 1 text")),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        assert result.raw_text == "Page 1 text"

    @pytest.mark.asyncio
    async def test_joins_multiple_pages(self) -> None:
        """Joins text from multiple PDF pages with newlines."""
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=_make_llm_response(_full_resume_data())
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber_pages(["Page 1", "Page 2"])),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        assert "Page 1" in result.raw_text
        assert "Page 2" in result.raw_text

    @pytest.mark.asyncio
    async def test_skips_pages_with_no_text(self) -> None:
        """Pages returning None are skipped."""
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=_make_llm_response(_full_resume_data())
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber_pages(["Content", None])),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        assert result.raw_text == "Content"


# =============================================================================
# LLM structured parsing
# =============================================================================


class TestLLMParsing:
    """Tests for LLM-based structured resume parsing."""

    @pytest.mark.asyncio
    async def test_sends_resume_parsing_task_type(self) -> None:
        """Uses TaskType.RESUME_PARSING for model routing."""
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=_make_llm_response(_full_resume_data())
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        call_kwargs = mock_provider.complete.call_args
        assert call_kwargs.kwargs["task"] == TaskType.RESUME_PARSING
        assert call_kwargs.kwargs["json_mode"] is True

    @pytest.mark.asyncio
    async def test_includes_system_prompt(self) -> None:
        """System prompt contains resume parser instructions."""
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=_make_llm_response(_full_resume_data())
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        messages = mock_provider.complete.call_args.kwargs["messages"]
        system_msg = messages[0]
        assert system_msg.role == "system"
        assert system_msg.content == RESUME_PARSE_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_sanitizes_extracted_text(self) -> None:
        """Extracted text is sanitized before embedding in LLM prompt."""
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=_make_llm_response(_full_resume_data())
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber("raw <script>alert</script>")),
            patch(_PATCH_SANITIZE, return_value="sanitized text") as mock_sanitize,
        ):
            service = ResumeParsingService()
            await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        mock_sanitize.assert_called_once()
        user_msg = mock_provider.complete.call_args.kwargs["messages"][1]
        assert "sanitized text" in user_msg.content

    @pytest.mark.asyncio
    async def test_truncates_text_before_llm(self) -> None:
        """Text exceeding _MAX_EXTRACTED_TEXT_LENGTH is truncated."""
        long_text = "A" * (_MAX_EXTRACTED_TEXT_LENGTH + 5000)
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=_make_llm_response(_full_resume_data())
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber(long_text)),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x) as mock_sanitize,
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        # Sanitize receives truncated text
        sanitized_input = mock_sanitize.call_args[0][0]
        assert len(sanitized_input) == _MAX_EXTRACTED_TEXT_LENGTH
        # But raw_text in result keeps full text
        assert len(result.raw_text) == _MAX_EXTRACTED_TEXT_LENGTH + 5000

    @pytest.mark.asyncio
    async def test_parses_full_response_into_result(self) -> None:
        """Complete LLM response is parsed into ResumeParseResult fields."""
        data = _full_resume_data()
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(return_value=_make_llm_response(data))

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        assert result.basic_info["full_name"] == "Jane Smith"
        assert len(result.work_history) == 2
        assert result.work_history[0]["job_title"] == "Senior Software Engineer"
        assert len(result.education) == 1
        assert len(result.skills) == 2
        assert len(result.certifications) == 1
        assert result.voice_suggestions is not None
        assert result.voice_suggestions.confidence == 0.85

    @pytest.mark.asyncio
    async def test_voice_suggestions_populated_when_present(self) -> None:
        """Voice suggestions parsed into VoiceSuggestions dataclass."""
        data = _full_resume_data()
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(return_value=_make_llm_response(data))

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        voice = result.voice_suggestions
        assert voice is not None
        assert voice.writing_style == "results-focused"
        assert voice.vocabulary_level == "technical"
        assert voice.personality_markers == "collaborative, data-driven"

    @pytest.mark.asyncio
    async def test_voice_suggestions_none_when_missing(self) -> None:
        """Voice suggestions are None when LLM omits them."""
        data = _full_resume_data()
        del data["voice_suggestions"]
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(return_value=_make_llm_response(data))

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        assert result.voice_suggestions is None


# =============================================================================
# Error handling
# =============================================================================


class TestErrorHandling:
    """Tests for graceful error handling."""

    @pytest.mark.asyncio
    async def test_corrupt_pdf_raises_value_error(self) -> None:
        """Corrupt PDF content raises ValueError with user-safe message."""
        mock_plumber = MagicMock()
        mock_plumber.open.side_effect = Exception("Not a valid PDF")

        mock_provider = AsyncMock()

        with patch(_PATCH_PDFPLUMBER, mock_plumber):
            service = ResumeParsingService()
            with pytest.raises(ValueError, match="Could not extract text"):
                await service.parse_resume(b"not a pdf", mock_provider)

    @pytest.mark.asyncio
    async def test_empty_pdf_raises_value_error(self) -> None:
        """PDF with no extractable text raises ValueError."""
        mock_provider = AsyncMock()

        with patch(_PATCH_PDFPLUMBER, _mock_pdfplumber_pages([None])):
            service = ResumeParsingService()
            with pytest.raises(ValueError, match="No text could be extracted"):
                await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

    @pytest.mark.asyncio
    async def test_llm_failure_raises_value_error(self) -> None:
        """LLM provider error raises ValueError with safe message."""
        from app.providers.errors import ProviderError

        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(side_effect=ProviderError("API key invalid"))

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            with pytest.raises(ValueError, match="Could not parse resume"):
                await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

    @pytest.mark.asyncio
    async def test_llm_failure_does_not_leak_internals(self) -> None:
        """Error message from LLM failure does not contain provider details."""
        from app.providers.errors import ProviderError

        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            side_effect=ProviderError("secret-api-key-12345")
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            with pytest.raises(ValueError) as exc_info:
                await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        assert "secret-api-key" not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_malformed_json_raises_value_error(self) -> None:
        """Malformed JSON from LLM raises ValueError."""
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=LLMResponse(
                content="not valid json {{{",
                model="test",
                input_tokens=10,
                output_tokens=10,
                finish_reason="stop",
                latency_ms=100.0,
            )
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            with pytest.raises(ValueError, match="Could not parse resume"):
                await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

    @pytest.mark.asyncio
    async def test_missing_fields_get_defaults(self) -> None:
        """Missing fields in LLM response get safe defaults."""
        minimal_data = {
            "basic_info": {"full_name": "Test User"},
        }
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=_make_llm_response(minimal_data)
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        assert result.basic_info["full_name"] == "Test User"
        assert result.work_history == ()
        assert result.education == ()
        assert result.skills == ()
        assert result.certifications == ()
        assert result.voice_suggestions is None

    @pytest.mark.asyncio
    async def test_oversized_work_history_is_capped(self) -> None:
        """Work history arrays from LLM exceeding the cap are truncated."""
        from app.services.resume_parsing_service import _MAX_WORK_HISTORY_ENTRIES

        data = _full_resume_data()
        data["work_history"] = [
            {"job_title": f"Job {i}", "company_name": f"Co {i}"}
            for i in range(_MAX_WORK_HISTORY_ENTRIES + 20)
        ]
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(return_value=_make_llm_response(data))

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        assert len(result.work_history) == _MAX_WORK_HISTORY_ENTRIES

    @pytest.mark.asyncio
    async def test_oversized_skills_is_capped(self) -> None:
        """Skills arrays from LLM exceeding the cap are truncated."""
        from app.services.resume_parsing_service import _MAX_SKILLS_ENTRIES

        data = _full_resume_data()
        data["skills"] = [
            {"name": f"Skill {i}", "type": "Hard", "proficiency": "Proficient"}
            for i in range(_MAX_SKILLS_ENTRIES + 50)
        ]
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(return_value=_make_llm_response(data))

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        assert len(result.skills) == _MAX_SKILLS_ENTRIES

    @pytest.mark.asyncio
    async def test_non_dict_basic_info_gets_default(self) -> None:
        """Non-dict basic_info from LLM is replaced with empty dict."""
        data = _full_resume_data()
        data["basic_info"] = "not a dict"
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(return_value=_make_llm_response(data))

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        assert result.basic_info == {}

    @pytest.mark.asyncio
    async def test_memory_error_propagates(self) -> None:
        """MemoryError from PDF processing is not caught."""
        mock_plumber = MagicMock()
        mock_plumber.open.side_effect = MemoryError("out of memory")

        mock_provider = AsyncMock()

        with patch(_PATCH_PDFPLUMBER, mock_plumber):
            service = ResumeParsingService()
            with pytest.raises(MemoryError):
                await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)


# =============================================================================
# File size validation
# =============================================================================


class TestFileSizeValidation:
    """Tests for file size limit enforcement."""

    @pytest.mark.asyncio
    async def test_oversized_file_raises_value_error(self) -> None:
        """Files exceeding 10MB are rejected before processing."""
        oversized_content = b"x" * (11 * 1024 * 1024)  # 11MB
        mock_provider = AsyncMock()

        service = ResumeParsingService()
        with pytest.raises(ValueError, match="exceeds.*10.*MB"):
            await service.parse_resume(oversized_content, mock_provider)

    @pytest.mark.asyncio
    async def test_file_at_limit_is_accepted(self) -> None:
        """Files exactly at 10MB are accepted."""
        content = b"x" * (10 * 1024 * 1024)  # Exactly 10MB
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=_make_llm_response(_full_resume_data())
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(content, mock_provider)

        assert result.basic_info is not None


# =============================================================================
# PDF page count limit
# =============================================================================


class TestPageCountLimit:
    """Tests for page count safety cap."""

    @pytest.mark.asyncio
    async def test_too_many_pages_raises_value_error(self) -> None:
        """PDFs with more than _MAX_PDF_PAGES pages are rejected."""
        texts = ["page"] * (_MAX_PDF_PAGES + 1)
        mock_provider = AsyncMock()

        with patch(_PATCH_PDFPLUMBER, _mock_pdfplumber_pages(texts)):
            service = ResumeParsingService()
            with pytest.raises(ValueError, match="too many pages"):
                await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

    @pytest.mark.asyncio
    async def test_pages_at_limit_accepted(self) -> None:
        """PDFs with exactly _MAX_PDF_PAGES pages are accepted."""
        texts = ["page"] * _MAX_PDF_PAGES
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=_make_llm_response(_full_resume_data())
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber_pages(texts)),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        assert result.basic_info is not None


# =============================================================================
# JSON response parsing edge cases
# =============================================================================


class TestResponseParsing:
    """Tests for parsing various LLM response formats."""

    @pytest.mark.asyncio
    async def test_handles_markdown_wrapped_json(self) -> None:
        """LLM response wrapped in markdown code blocks is still parsed."""
        data = _full_resume_data()
        wrapped = f"```json\n{json.dumps(data)}\n```"
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=LLMResponse(
                content=wrapped,
                model="test",
                input_tokens=10,
                output_tokens=10,
                finish_reason="stop",
                latency_ms=100.0,
            )
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            result = await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)

        assert result.basic_info["full_name"] == "Jane Smith"

    @pytest.mark.asyncio
    async def test_null_content_raises_value_error(self) -> None:
        """LLM returning None content raises ValueError."""
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(
            return_value=LLMResponse(
                content=None,
                model="test",
                input_tokens=10,
                output_tokens=10,
                finish_reason="stop",
                latency_ms=100.0,
            )
        )

        with (
            patch(_PATCH_PDFPLUMBER, _mock_pdfplumber()),
            patch(_PATCH_SANITIZE, side_effect=lambda x: x),
        ):
            service = ResumeParsingService()
            with pytest.raises(ValueError, match="Could not parse resume"):
                await service.parse_resume(_FAKE_PDF_BYTES, mock_provider)
