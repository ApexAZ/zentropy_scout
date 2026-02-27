"""Cover letter generation service.

REQ-010 §5.3: Cover Letter Generation.
REQ-007 §8.5: Cover Letter Generation.

Async service that:
1. Builds LLM messages from prompt templates
2. Calls the LLM provider (Sonnet-tier via TaskType.COVER_LETTER)
3. Parses XML response (<cover_letter> + <agent_reasoning>)
4. Returns a CoverLetterResult dataclass

Follows the same import pattern as ghost_detection.py:
uses factory.get_llm_provider() for the provider instance.
"""

import logging
import re
from dataclasses import dataclass

from app.core.errors import APIError
from app.prompts.ghostwriter import (
    COVER_LETTER_SYSTEM_PROMPT,
    build_cover_letter_prompt,
)
from app.providers import ProviderError, factory
from app.providers.llm.base import LLMMessage, TaskType
from app.schemas.prompt_params import JobContext, VoiceProfileData

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================


class CoverLetterGenerationError(APIError):
    """Error during cover letter generation.

    Raised when the LLM provider fails or returns an unusable response.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            code="COVER_LETTER_GENERATION_ERROR",
            message=message,
            status_code=500,
        )


@dataclass
class CoverLetterResult:
    """Result of cover letter generation.

    Attributes:
        content: The generated cover letter text (plain text).
        reasoning: Agent's reasoning for choices made.
        word_count: Number of words in the cover letter content.
        stories_used: Achievement story IDs that were referenced.
    """

    content: str
    reasoning: str
    word_count: int
    stories_used: list[str]


# =============================================================================
# XML Parsing
# =============================================================================

_COVER_LETTER_PATTERN = re.compile(
    r"<cover_letter>(.*?)</cover_letter>",
    re.DOTALL,
)
_REASONING_PATTERN = re.compile(
    r"<agent_reasoning>(.*?)</agent_reasoning>",
    re.DOTALL,
)


def _parse_cover_letter_response(content: str) -> tuple[str, str]:
    """Parse XML-structured LLM response into cover letter and reasoning.

    REQ-010 §5.3: Expects <cover_letter> and <agent_reasoning> blocks.

    Falls back to using the full content as cover letter text if XML tags
    are not found (defensive handling for inconsistent LLM output).

    Args:
        content: Raw LLM response content.

    Returns:
        Tuple of (cover_letter_text, reasoning_text).
    """
    cover_match = _COVER_LETTER_PATTERN.search(content)
    reasoning_match = _REASONING_PATTERN.search(content)

    cover_letter = cover_match.group(1).strip() if cover_match else content.strip()

    reasoning = reasoning_match.group(1).strip() if reasoning_match else ""

    return cover_letter, reasoning


# =============================================================================
# Service Function
# =============================================================================


async def generate_cover_letter(
    *,
    applicant_name: str,
    current_title: str,
    job: JobContext,
    voice: VoiceProfileData,
    stories: list[dict],
    stories_used: list[str],
) -> CoverLetterResult:
    """Generate a cover letter using the LLM provider.

    REQ-010 §5.3: Builds prompts, calls LLM (Sonnet-tier), parses XML response.

    Args:
        applicant_name: Full name of the applicant.
        current_title: Applicant's current job title.
        job: Job posting context (title, company, skills, culture, description).
        voice: Voice profile settings (tone, style, vocabulary, markers, etc.).
        stories: List of story dicts for prompt context.
        stories_used: Achievement story IDs being referenced.

    Returns:
        CoverLetterResult with content, reasoning, word_count, and stories_used.

    Raises:
        CoverLetterGenerationError: If the LLM provider fails or returns
            an empty response.
    """
    user_prompt = build_cover_letter_prompt(
        applicant_name=applicant_name,
        current_title=current_title,
        job=job,
        voice=voice,
        stories=stories,
    )

    messages = [
        LLMMessage(role="system", content=COVER_LETTER_SYSTEM_PROMPT),
        LLMMessage(  # nosemgrep: zentropy.llm-unsanitized-input  # sanitized inside build_cover_letter_prompt()
            role="user", content=user_prompt
        ),
    ]

    try:
        llm = factory.get_llm_provider()
        response = await llm.complete(
            messages=messages,
            task=TaskType.COVER_LETTER,
        )
    except ProviderError as e:
        logger.error("Cover letter generation failed: %s", e)
        raise CoverLetterGenerationError(
            "Cover letter generation failed. Please try again."
        ) from e

    raw_content = response.content
    if not raw_content:
        raise CoverLetterGenerationError(
            "LLM returned empty response for cover letter generation"
        )

    cover_letter_text, reasoning_text = _parse_cover_letter_response(raw_content)

    return CoverLetterResult(
        content=cover_letter_text,
        reasoning=reasoning_text,
        word_count=len(cover_letter_text.split()),
        stories_used=stories_used,
    )
