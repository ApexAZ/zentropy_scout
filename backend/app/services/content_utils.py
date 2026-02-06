"""Content utility functions for the Ghostwriter agent.

REQ-010 §6: Shared utility functions used across resume tailoring,
cover letter generation, and story selection. These are NOT simple regex —
they require LLM calls for semantic accuracy.

Functions:
    extract_keywords: Extract meaningful keywords from text via LLM.
    extract_skills_from_text: Extract skill mentions from free text via LLM.
"""

import json
import logging

from app.core.llm_sanitization import sanitize_llm_input
from app.providers.factory import get_llm_provider
from app.providers.llm.base import LLMMessage, TaskType

logger = logging.getLogger(__name__)


async def extract_keywords(
    text: str,
    max_keywords: int = 20,
) -> set[str]:
    """Extract meaningful keywords from text using LLM.

    WHY: Regex/NLTK miss semantic meaning. "distributed systems" should be
    one keyword, not two. "K8s" should normalize to "Kubernetes".

    Args:
        text: Source text (job description, resume summary, etc.)
        max_keywords: Maximum keywords to return.

    Returns:
        Set of lowercase normalized keywords.

    Raises:
        ProviderError: If the LLM API call fails after retries.
    """
    if not text.strip():
        return set()

    llm = get_llm_provider()
    safe_text = sanitize_llm_input(text[:2000])

    response = await llm.complete(
        task=TaskType.EXTRACTION,
        messages=[
            LLMMessage(
                role="system",
                content="""Extract the most important keywords from the text.

RULES:
1. Include technical skills, tools, methodologies
2. Normalize variants (K8s -> Kubernetes, JS -> JavaScript)
3. Keep multi-word terms together ("distributed systems", not "distributed" + "systems")
4. Lowercase everything
5. Output as JSON array only, no other text

Example: ["kubernetes", "python", "distributed systems", "team leadership"]""",
            ),
            LLMMessage(
                role="user",
                content=f"Extract keywords from:\n\n{safe_text}",
            ),
        ],
        max_tokens=500,
    )

    if response.content is None:
        logger.warning("extract_keywords: LLM returned no content, using fallback")
        words = safe_text.lower().split()
        return set(words[:max_keywords])

    try:
        parsed = json.loads(response.content)
        if not isinstance(parsed, list):
            raise TypeError("Expected JSON array")
        return {k.lower() for k in parsed[:max_keywords] if isinstance(k, str)}
    except (json.JSONDecodeError, TypeError, AttributeError):
        # WHY fallback: LLM may return non-JSON occasionally.
        # Simple word split is better than nothing.
        logger.warning("extract_keywords: LLM returned invalid JSON, using fallback")
        words = safe_text.lower().split()
        return set(words[:max_keywords])


async def extract_skills_from_text(
    text: str,
    persona_skills: set[str] | None = None,
) -> set[str]:
    """Extract skill mentions from free text using LLM.

    WHY: Skills appear in many forms. "Led Python development" contains
    "Python" and "Leadership". Regex can't reliably extract these.

    Args:
        text: Text to analyze (job description, bullet point, etc.)
        persona_skills: Optional set of known skills to bias extraction toward.
            When provided, up to 30 skills are included as hints in the prompt.

    Returns:
        Set of lowercase skill names found.

    Raises:
        ProviderError: If the LLM API call fails after retries.
    """
    if not text.strip():
        return set()

    llm = get_llm_provider()
    safe_text = sanitize_llm_input(text[:1500])

    skill_hint = ""
    if persona_skills:
        sanitized_skills = [
            sanitize_llm_input(skill[:100]) for skill in list(persona_skills)[:30]
        ]
        skill_hint = f"\n\nKnown skills to look for: {', '.join(sanitized_skills)}"

    response = await llm.complete(
        task=TaskType.EXTRACTION,
        messages=[
            LLMMessage(
                role="system",
                content=f"""Identify skills mentioned in the text.

RULES:
1. Include both explicit ("Python") and implicit ("led the team" → leadership)
2. Normalize to standard names (JS → JavaScript, ML → Machine Learning)
3. Include soft skills (communication, leadership, problem-solving)
4. Lowercase everything
5. Output as JSON array only{skill_hint}""",
            ),
            LLMMessage(
                role="user",
                content=f"Extract skills from:\n\n{safe_text}",
            ),
        ],
        max_tokens=300,
    )

    if response.content is None:
        logger.warning("extract_skills_from_text: LLM returned no content")
        return set()

    try:
        parsed = json.loads(response.content)
        if not isinstance(parsed, list):
            raise TypeError("Expected JSON array")
        return {s.lower() for s in parsed if isinstance(s, str)}
    except (json.JSONDecodeError, TypeError, AttributeError):
        logger.warning(
            "extract_skills_from_text: LLM returned invalid JSON, returning empty set"
        )
        return set()
