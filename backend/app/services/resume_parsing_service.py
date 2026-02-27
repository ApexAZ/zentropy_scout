"""Resume parsing service — extract structured data from PDF resumes.

REQ-019 §6.2: Uses pdfplumber for text extraction and LLM (Gemini 2.5 Flash)
for structured parsing into persona data fields.

Pipeline:
1. Validate file size (≤10MB)
2. Extract text from PDF via pdfplumber (max 50 pages)
3. Sanitize and truncate extracted text
4. Send to LLM with structured extraction prompt
5. Parse JSON response into ResumeParseResult
"""

import json
from dataclasses import dataclass
from io import BytesIO

import pdfplumber
import structlog

from app.core.config import settings
from app.core.llm_sanitization import sanitize_llm_input
from app.providers.errors import ProviderError
from app.providers.llm.base import LLMMessage, LLMProvider, TaskType

logger = structlog.get_logger()

_SKIP_STEP_HINT = "You can skip this step and enter your info manually."
_EXTRACT_FAILURE_MSG = f"Could not extract text from this PDF. {_SKIP_STEP_HINT}"
_EMPTY_PDF_MSG = f"No text could be extracted from this PDF. {_SKIP_STEP_HINT}"
_PARSE_FAILURE_MSG = f"Could not parse resume content. {_SKIP_STEP_HINT}"

_MD_FENCE = "```"
_MD_FENCE_JSON = "```json"

_MAX_EXTRACTED_TEXT_LENGTH = 50_000
"""Safety cap on extracted text length before LLM prompt (chars)."""

_MAX_PDF_PAGES = 50
"""Safety cap on PDF page count to prevent DoS via crafted PDFs."""

_LOG_EXCERPT_LENGTH = 200
"""Max characters of exception messages logged (truncate attacker-controlled content)."""

_MAX_WORK_HISTORY_ENTRIES = 50
"""Safety cap on work history entries from LLM response."""

_MAX_EDUCATION_ENTRIES = 20
"""Safety cap on education entries from LLM response."""

_MAX_SKILLS_ENTRIES = 100
"""Safety cap on skills entries from LLM response."""

_MAX_CERTIFICATIONS_ENTRIES = 50
"""Safety cap on certifications entries from LLM response."""

# REQ-019 §8.1: System prompt for resume parsing
RESUME_PARSE_SYSTEM_PROMPT = """\
You are an expert resume parser. Extract structured data from the resume text below.

Rules:
1. Extract ALL work history entries, even if formatting is inconsistent
2. For each skill, infer proficiency from context (years of experience, role seniority)
3. Normalize date formats to YYYY-MM
4. If a field is ambiguous or missing, use null rather than guessing
5. For voice_suggestions, analyze the writing style:
   - writing_style: How are accomplishments presented? \
(results-focused, narrative, technical, concise)
   - vocabulary_level: What level of language is used? \
(technical, accessible, business)
   - personality_markers: What traits come through? \
(e.g., "collaborative", "independent contributor")
   - confidence: How confident are you in these assessments? (0.0-1.0)

Output ONLY valid JSON matching the schema. No markdown, no explanation."""

_USER_PROMPT_TEMPLATE = """\
Resume text:
{extracted_text}

Parse this resume into structured JSON with these keys:
basic_info, work_history, education, skills, certifications, voice_suggestions"""


# =============================================================================
# Result dataclasses
# =============================================================================


@dataclass(frozen=True)
class VoiceSuggestions:
    """Voice profile inference from resume writing style.

    REQ-019 §6.2: If confidence >= 0.7, pre-populate voice profile form.
    """

    writing_style: str
    vocabulary_level: str
    personality_markers: str
    confidence: float


@dataclass(frozen=True)
class ResumeParseResult:
    """Structured resume data extracted from PDF.

    REQ-019 §6.2: Output schema for the resume parsing pipeline.
    """

    basic_info: dict
    work_history: tuple[dict, ...]
    education: tuple[dict, ...]
    skills: tuple[dict, ...]
    certifications: tuple[dict, ...]
    voice_suggestions: VoiceSuggestions | None
    raw_text: str


# =============================================================================
# Service
# =============================================================================


class ResumeParsingService:
    """Parses uploaded resumes into structured persona data.

    REQ-019 §6.2: Pipeline uses pdfplumber for text extraction and
    LLM for structured JSON parsing.
    """

    async def parse_resume(
        self,
        pdf_content: bytes,
        provider: LLMProvider,
    ) -> ResumeParseResult:
        """Parse a PDF resume into structured persona data.

        Args:
            pdf_content: Raw PDF file bytes.
            provider: LLM provider for structured parsing.

        Returns:
            ResumeParseResult with extracted fields.

        Raises:
            ValueError: File too large, corrupt PDF, empty PDF, or parse failure.
        """
        self._validate_size(pdf_content)
        raw_text = self._extract_text(pdf_content)
        return await self._parse_with_llm(raw_text, provider)

    def _validate_size(self, pdf_content: bytes) -> None:
        """Reject files exceeding the configured size limit.

        Args:
            pdf_content: Raw PDF bytes.

        Raises:
            ValueError: If file exceeds size limit.
        """
        max_bytes = settings.resume_parse_max_size_mb * 1024 * 1024
        if len(pdf_content) > max_bytes:
            raise ValueError(
                f"File exceeds {settings.resume_parse_max_size_mb} MB limit."
            )

    def _extract_text(self, pdf_content: bytes) -> str:
        """Extract text from PDF using pdfplumber.

        Args:
            pdf_content: Raw PDF bytes.

        Returns:
            Extracted text from all pages (truncated to safety cap).

        Raises:
            ValueError: If PDF cannot be read or contains no text.
        """
        try:
            with pdfplumber.open(BytesIO(pdf_content)) as pdf:
                if len(pdf.pages) > _MAX_PDF_PAGES:
                    raise ValueError(
                        f"PDF has too many pages ({len(pdf.pages)}). "
                        f"Maximum: {_MAX_PDF_PAGES} pages."
                    )
                pages = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
        except ValueError:
            raise
        except (MemoryError, RecursionError):
            raise
        except Exception as exc:
            logger.warning(
                "PDF text extraction failed",
                error=str(exc)[:_LOG_EXCERPT_LENGTH],
            )
            raise ValueError(_EXTRACT_FAILURE_MSG) from exc

        if not pages:
            raise ValueError(_EMPTY_PDF_MSG)

        return "\n".join(pages)

    async def _parse_with_llm(
        self,
        raw_text: str,
        provider: LLMProvider,
    ) -> ResumeParseResult:
        """Send extracted text to LLM for structured parsing.

        Args:
            raw_text: Extracted resume text.
            provider: LLM provider instance.

        Returns:
            ResumeParseResult with parsed fields.

        Raises:
            ValueError: If LLM call fails or response is unparseable.
        """
        truncated = raw_text[:_MAX_EXTRACTED_TEXT_LENGTH]
        safe_text = sanitize_llm_input(truncated)
        user_prompt = _USER_PROMPT_TEMPLATE.format(extracted_text=safe_text)

        try:
            response = await provider.complete(
                messages=[
                    LLMMessage(role="system", content=RESUME_PARSE_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=user_prompt),
                ],
                task=TaskType.RESUME_PARSING,
                json_mode=True,
            )
        except ProviderError as exc:
            logger.warning(
                "LLM resume parsing failed",
                error=str(exc)[:_LOG_EXCERPT_LENGTH],
            )
            raise ValueError(_PARSE_FAILURE_MSG) from exc

        return self._parse_response(response.content, raw_text)

    def _parse_response(
        self,
        content: str | None,
        raw_text: str,
    ) -> ResumeParseResult:
        """Parse LLM JSON response into ResumeParseResult.

        Args:
            content: Raw LLM response text.
            raw_text: Original extracted text (stored in result).

        Returns:
            ResumeParseResult with parsed fields.

        Raises:
            ValueError: If response is None or invalid JSON.
        """
        if not content:
            raise ValueError(_PARSE_FAILURE_MSG)

        text = self._strip_markdown_fences(content)

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Failed to parse LLM JSON response",
                error=str(exc)[:_LOG_EXCERPT_LENGTH],
            )
            raise ValueError(_PARSE_FAILURE_MSG) from exc

        voice = self._parse_voice_suggestions(data.get("voice_suggestions"))

        basic_info = data.get("basic_info", {})
        if not isinstance(basic_info, dict):
            basic_info = {}

        return ResumeParseResult(
            basic_info=basic_info,
            work_history=tuple(
                data.get("work_history", [])[:_MAX_WORK_HISTORY_ENTRIES]
            ),
            education=tuple(data.get("education", [])[:_MAX_EDUCATION_ENTRIES]),
            skills=tuple(data.get("skills", [])[:_MAX_SKILLS_ENTRIES]),
            certifications=tuple(
                data.get("certifications", [])[:_MAX_CERTIFICATIONS_ENTRIES]
            ),
            voice_suggestions=voice,
            raw_text=raw_text,
        )

    @staticmethod
    def _strip_markdown_fences(content: str) -> str:
        """Remove markdown code fences from LLM response."""
        text = content.strip()
        if text.startswith(_MD_FENCE_JSON):
            text = text[len(_MD_FENCE_JSON) :].strip()
            if text.endswith(_MD_FENCE):
                text = text[: -len(_MD_FENCE)].strip()
        elif text.startswith(_MD_FENCE):
            text = text[len(_MD_FENCE) :].strip()
            if text.endswith(_MD_FENCE):
                text = text[: -len(_MD_FENCE)].strip()
        return text

    @staticmethod
    def _parse_voice_suggestions(voice_data: object) -> VoiceSuggestions | None:
        """Parse voice suggestions dict into VoiceSuggestions if valid."""
        if not isinstance(voice_data, dict) or "confidence" not in voice_data:
            return None
        try:
            confidence = max(0.0, min(1.0, float(voice_data.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confidence = 0.0
        return VoiceSuggestions(
            writing_style=str(voice_data.get("writing_style", "")),
            vocabulary_level=str(voice_data.get("vocabulary_level", "")),
            personality_markers=str(voice_data.get("personality_markers", "")),
            confidence=confidence,
        )
