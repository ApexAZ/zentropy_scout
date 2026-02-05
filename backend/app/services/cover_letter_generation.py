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

from app.agents.ghostwriter_prompts import (
    COVER_LETTER_SYSTEM_PROMPT,
    build_cover_letter_prompt,
)
from app.providers import ProviderError, factory
from app.providers.llm.base import LLMMessage, TaskType

logger = logging.getLogger(__name__)


# =============================================================================
# Types
# =============================================================================


class CoverLetterGenerationError(Exception):
    """Error during cover letter generation.

    Raised when the LLM provider fails or returns an unusable response.
    """

    pass


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
    r"<cover_letter>\s*(.*?)\s*</cover_letter>",
    re.DOTALL,
)
_REASONING_PATTERN = re.compile(
    r"<agent_reasoning>\s*(.*?)\s*</agent_reasoning>",
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
    job_title: str,
    company_name: str,
    top_skills: str,
    culture_signals: str,
    description_excerpt: str,
    tone: str,
    sentence_style: str,
    vocabulary_level: str,
    personality_markers: str,
    preferred_phrases: str,
    things_to_avoid: str,
    writing_sample: str,
    stories: list[dict],
    stories_used: list[str],
) -> CoverLetterResult:
    """Generate a cover letter using the LLM provider.

    REQ-010 §5.3: Builds prompts, calls LLM (Sonnet-tier), parses XML response.

    Args:
        applicant_name: Full name of the applicant.
        current_title: Applicant's current job title.
        job_title: Title of the target job posting.
        company_name: Company offering the position.
        top_skills: Formatted string of top required skills.
        culture_signals: Culture information from the job posting.
        description_excerpt: Raw job description text.
        tone: Voice profile tone setting.
        sentence_style: Voice profile sentence style.
        vocabulary_level: Voice profile vocabulary level.
        personality_markers: Voice profile personality markers.
        preferred_phrases: Phrases the applicant likes to use.
        things_to_avoid: Words/phrases the applicant wants to avoid.
        writing_sample: Sample of the applicant's writing.
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
        job_title=job_title,
        company_name=company_name,
        top_skills=top_skills,
        culture_signals=culture_signals,
        description_excerpt=description_excerpt,
        tone=tone,
        sentence_style=sentence_style,
        vocabulary_level=vocabulary_level,
        personality_markers=personality_markers,
        preferred_phrases=preferred_phrases,
        things_to_avoid=things_to_avoid,
        writing_sample=writing_sample,
        stories=stories,
    )

    messages = [
        LLMMessage(role="system", content=COVER_LETTER_SYSTEM_PROMPT),
        LLMMessage(role="user", content=user_prompt),
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
