"""Content utility functions for the Ghostwriter agent.

REQ-010 §6: Shared utility functions used across resume tailoring,
cover letter generation, and story selection. These are NOT simple regex —
they require LLM calls for semantic accuracy.

Functions:
    extract_keywords: Extract meaningful keywords from text via LLM.
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

    try:
        parsed = json.loads(response.content)
        if not isinstance(parsed, list):
            raise TypeError("Expected JSON array")
        return {k.lower() for k in parsed[:max_keywords] if isinstance(k, str)}
    except (json.JSONDecodeError, TypeError, AttributeError):
        # WHY fallback: LLM may return non-JSON occasionally.
        # Simple word split is better than nothing.
        logger.warning("extract_keywords: LLM returned invalid JSON, using fallback")
        words = text.lower().split()
        return set(words[:max_keywords])
