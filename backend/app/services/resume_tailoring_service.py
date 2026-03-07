"""Resume tailoring service — LLM-assisted resume tailoring for job variants.

REQ-027 §6.2: Calls LLM to tailor a base resume's markdown for a specific
job posting. Uses RESUME_TAILORING_SYSTEM_PROMPT with TaskType.RESUME_TAILORING.
"""

import logging
import re

from app.core.errors import APIError
from app.prompts.ghostwriter import (
    RESUME_TAILORING_SYSTEM_PROMPT,
    build_resume_tailoring_prompt,
)
from app.providers.errors import ProviderError
from app.providers.llm.base import LLMMessage, LLMProvider, TaskType

logger = logging.getLogger(__name__)

_TAILORED_RESUME_RE = re.compile(r"<tailored_resume>(.*?)</tailored_resume>", re.DOTALL)


class ResumeTailoringError(APIError):
    """Raised when LLM resume tailoring fails."""

    def __init__(self, message: str) -> None:
        super().__init__(
            code="RESUME_TAILORING_ERROR",
            message=message,
            status_code=502,
        )


async def tailor_resume_markdown(
    *,
    resume_markdown: str,
    job_title: str,
    company_name: str,
    description: str,
    requirements: str,
    provider: LLMProvider,
) -> tuple[str, dict]:
    """Tailor resume markdown for a specific job posting via LLM.

    REQ-027 §6.2: Builds prompt with resume markdown and job data, calls LLM,
    extracts tailored markdown from response.

    Args:
        resume_markdown: The base resume's markdown content.
        job_title: Target job posting title.
        company_name: Company name from job posting.
        description: Job description text.
        requirements: Job requirements text.
        provider: LLM provider (metered for billing).

    Returns:
        Tuple of (tailored_markdown, metadata_dict).

    Raises:
        ResumeTailoringError: If LLM call fails or returns empty/unparseable.
    """
    user_prompt = build_resume_tailoring_prompt(
        resume_markdown=resume_markdown,
        job_title=job_title,
        company_name=company_name,
        description_excerpt=description,
        requirements=requirements,
    )

    messages = [
        LLMMessage(role="system", content=RESUME_TAILORING_SYSTEM_PROMPT),
        LLMMessage(  # nosemgrep: zentropy.llm-unsanitized-input  # sanitized inside build_resume_tailoring_prompt()
            role="user", content=user_prompt
        ),
    ]

    try:
        response = await provider.complete(
            messages=messages,
            task=TaskType.RESUME_TAILORING,
        )
    except ProviderError as e:
        logger.error("Resume tailoring failed: %s", e)
        raise ResumeTailoringError("Resume tailoring failed. Please try again.") from e

    raw_content = response.content
    if not raw_content:
        raise ResumeTailoringError("LLM returned empty response for resume tailoring.")

    # Extract tailored resume from XML tags
    match = _TAILORED_RESUME_RE.search(raw_content)
    tailored_markdown = match.group(1).strip() if match else raw_content

    metadata = {
        "model": response.model,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
    }

    return tailored_markdown, metadata
