"""Content utility functions for the Ghostwriter agent.

REQ-010 §6: Shared utility functions used across resume tailoring,
cover letter generation, and story selection. These are NOT simple regex —
they require LLM calls for semantic accuracy.

Functions:
    extract_keywords: Extract meaningful keywords from text via LLM.
    extract_skills_from_text: Extract skill mentions from free text via LLM.
    has_metrics: Fast synchronous metric detection via string scan.
    extract_metrics: Regex fast path + LLM slow path for metric extraction.
"""

import hashlib
import json
import logging
import re

from app.core.llm_sanitization import sanitize_llm_input
from app.providers.factory import get_llm_provider
from app.providers.llm.base import LLMMessage, LLMProvider, TaskType

logger = logging.getLogger(__name__)

_EXPECTED_JSON_ARRAY = "Expected JSON array"


async def extract_keywords(
    text: str,
    max_keywords: int = 20,
    provider: LLMProvider | None = None,
) -> set[str]:
    """Extract meaningful keywords from text using LLM.

    WHY: Regex/NLTK miss semantic meaning. "distributed systems" should be
    one keyword, not two. "K8s" should normalize to "Kubernetes".

    Args:
        text: Source text (job description, resume summary, etc.)
        max_keywords: Maximum keywords to return.
        provider: Optional LLM provider. Falls back to factory if None.

    Returns:
        Set of lowercase normalized keywords.

    Raises:
        ProviderError: If the LLM API call fails after retries.
    """
    if not text.strip():
        return set()

    llm = provider or get_llm_provider()
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
            LLMMessage(  # nosemgrep: zentropy.llm-fstring-in-message  # safe_text sanitized on line 51
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
            raise TypeError(_EXPECTED_JSON_ARRAY)
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
    provider: LLMProvider | None = None,
) -> set[str]:
    """Extract skill mentions from free text using LLM.

    WHY: Skills appear in many forms. "Led Python development" contains
    "Python" and "Leadership". Regex can't reliably extract these.

    Args:
        text: Text to analyze (job description, bullet point, etc.)
        persona_skills: Optional set of known skills to bias extraction toward.
            When provided, up to 30 skills are included as hints in the prompt.
        provider: Optional LLM provider. Falls back to factory if None.

    Returns:
        Set of lowercase skill names found.

    Raises:
        ProviderError: If the LLM API call fails after retries.
    """
    if not text.strip():
        return set()

    llm = provider or get_llm_provider()
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
            LLMMessage(  # nosemgrep: zentropy.llm-fstring-in-message  # skill_hint sanitized on lines 119,124
                role="system",
                content=f"""Identify skills mentioned in the text.

RULES:
1. Include both explicit ("Python") and implicit ("led the team" → leadership)
2. Normalize to standard names (JS → JavaScript, ML → Machine Learning)
3. Include soft skills (communication, leadership, problem-solving)
4. Lowercase everything
5. Output as JSON array only{skill_hint}""",
            ),
            LLMMessage(  # nosemgrep: zentropy.llm-fstring-in-message  # safe_text sanitized on line 119
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
            raise TypeError(_EXPECTED_JSON_ARRAY)
        return {s.lower() for s in parsed if isinstance(s, str)}
    except (json.JSONDecodeError, TypeError, AttributeError):
        logger.warning(
            "extract_skills_from_text: LLM returned invalid JSON, returning empty set"
        )
        return set()


# =============================================================================
# Metrics Detection & Extraction (REQ-010 §6.4)
# =============================================================================

# Suffixes that indicate a metric when preceded by a digit.
_METRICS_SUFFIXES = frozenset("%xX")

# Regex patterns for extracting metric values from text.
# Patterns are ordered from most specific to least to avoid false positives.
# All patterns avoid .* to prevent catastrophic backtracking (S5852).
_EXTRACTION_PATTERNS = [
    re.compile(r"\$\d[\d,]*(?:\.\d+)?[KMBkmb]?"),  # $1.2M, $500K, $100
    re.compile(r"\d+%"),  # 40%
    re.compile(r"\d+x\b", re.IGNORECASE),  # 10x, 3X
    re.compile(r"\d+\s*(?:users|customers|clients|engineers|teams)", re.IGNORECASE),
]


def has_metrics(text: str) -> bool:
    """Check if text contains quantified metrics.

    REQ-010 §6.4: Fast synchronous check using string scan.
    Detects dollar amounts ($100), percentages (40%), multipliers (3x),
    and significant numbers (2+ consecutive digits).

    WHY string scan over regex: Avoids catastrophic backtracking (S5852)
    while still catching the common cases. Moved from story_selection.py
    to content_utils.py for shared use across services.

    Args:
        text: Text to check for metrics patterns.

    Returns:
        True if metrics pattern found.
    """
    consecutive_digits = 0
    for i, c in enumerate(text):
        if c.isdigit():
            consecutive_digits += 1
            if consecutive_digits >= 2:
                return True
        else:
            if consecutive_digits > 0 and c in _METRICS_SUFFIXES:
                return True
            consecutive_digits = 0
            if c == "$" and i + 1 < len(text) and text[i + 1].isdigit():
                return True
    return False


async def extract_metrics(text: str, provider: LLMProvider | None = None) -> list[str]:
    """Extract specific metric values from text.

    REQ-010 §6.4: Two-phase approach:
    1. Fast path: regex patterns extract obvious metrics (no LLM call).
    2. Slow path: LLM fallback for subtle metrics ("tripled", "doubled").

    WHY: Need to verify metrics in generated content match source.
    "Reduced costs by 40%" should extract "40%" for comparison.

    Args:
        text: Text to extract metric values from.
        provider: Optional LLM provider. Falls back to factory if None.

    Returns:
        List of metric strings found (e.g., ["40%", "$1.2M", "500 users"]).
    """
    if not text.strip():
        return []

    # Fast path: regex extraction
    metrics: list[str] = []
    for pattern in _EXTRACTION_PATTERNS:
        matches = pattern.findall(text)
        metrics.extend(matches)

    if metrics:
        return list(dict.fromkeys(metrics))

    # Slow path: LLM for subtle metrics
    llm = provider or get_llm_provider()
    safe_text = sanitize_llm_input(text[:1000])

    response = await llm.complete(
        task=TaskType.EXTRACTION,
        messages=[
            LLMMessage(
                role="system",
                content="""Extract quantified metrics from the text.

Look for: percentages, dollar amounts, user counts, time savings,
multipliers (10x), team sizes, etc.

Output as JSON array of strings. If no metrics found, output [].
Example: ["40%", "$1.2M", "500 users", "3x faster"]""",
            ),
            LLMMessage(  # nosemgrep: zentropy.llm-fstring-in-message  # safe_text sanitized on line 246
                role="user",
                content=f"Extract metrics from:\n\n{safe_text}",
            ),
        ],
        max_tokens=200,
    )

    if response.content is None:
        logger.warning("extract_metrics: LLM returned no content")
        return []

    try:
        parsed = json.loads(response.content)
        if not isinstance(parsed, list):
            raise TypeError(_EXPECTED_JSON_ARRAY)
        return [m for m in parsed if isinstance(m, str)]
    except (json.JSONDecodeError, TypeError, AttributeError):
        logger.warning("extract_metrics: LLM returned invalid JSON")
        return []


# =============================================================================
# Session-Scoped Caching (REQ-010 §6.5)
# =============================================================================
# WHY: Job descriptions and persona data don't change during a generation
# session. Caching prevents redundant LLM calls when the same text is
# processed by multiple pipeline stages.


_MAX_CACHE_SIZE = 500


def text_hash(text: str) -> str:
    """Generate cache key from text content.

    WHY MD5: Speed over security — this is a cache key, not a cryptographic
    hash. 16 hex chars = 64-bit collision space (birthday bound ~2^32),
    acceptable for in-process cache keys.

    Args:
        text: Input text to hash.

    Returns:
        16-character hex string (truncated MD5).
    """
    return hashlib.md5(text.encode(), usedforsecurity=False).hexdigest()[:16]


_keyword_cache: dict[str, set[str]] = {}
_skills_cache: dict[str, set[str]] = {}
_metrics_cache: dict[str, list[str]] = {}


def clear_content_caches() -> None:
    """Clear all content extraction caches.

    Call between generation sessions to release memory and prevent
    stale results from persisting across sessions.
    """
    _keyword_cache.clear()
    _skills_cache.clear()
    _metrics_cache.clear()


def _evict_oldest(cache: dict, max_size: int = _MAX_CACHE_SIZE) -> None:
    """Remove oldest entries if cache exceeds max size."""
    while len(cache) > max_size:
        cache.pop(next(iter(cache)))


async def extract_keywords_cached(
    text: str,
    max_keywords: int = 20,
    provider: LLMProvider | None = None,
) -> set[str]:
    """Cached version of extract_keywords.

    Args:
        text: Source text (job description, resume summary, etc.)
        max_keywords: Maximum keywords to return.
        provider: Optional LLM provider (falls through to extract_keywords).

    Returns:
        Set of lowercase normalized keywords.

    Raises:
        ProviderError: If the LLM API call fails after retries.
    """
    if not text.strip():
        return set()

    cache_key = f"kw:{text_hash(text)}:{max_keywords}"

    if cache_key in _keyword_cache:
        return set(_keyword_cache[cache_key])

    result = await extract_keywords(text, max_keywords, provider=provider)
    _keyword_cache[cache_key] = result
    _evict_oldest(_keyword_cache)
    return set(result)


async def extract_skills_cached(
    text: str,
    persona_skills: set[str] | None = None,
    provider: LLMProvider | None = None,
) -> set[str]:
    """Cached version of extract_skills_from_text.

    Args:
        text: Text to analyze (job description, bullet point, etc.)
        persona_skills: Optional set of known skills to bias extraction toward.
        provider: Optional LLM provider (falls through to extract_skills_from_text).

    Returns:
        Set of lowercase skill names found.

    Raises:
        ProviderError: If the LLM API call fails after retries.
    """
    if not text.strip():
        return set()

    skills_part = ",".join(sorted(persona_skills)) if persona_skills else ""
    cache_key = f"sk:{text_hash(text)}:{text_hash(skills_part)}"

    if cache_key in _skills_cache:
        return set(_skills_cache[cache_key])

    result = await extract_skills_from_text(text, persona_skills, provider=provider)
    _skills_cache[cache_key] = result
    _evict_oldest(_skills_cache)
    return set(result)


async def extract_metrics_cached(
    text: str,
    provider: LLMProvider | None = None,
) -> list[str]:
    """Cached version of extract_metrics.

    Args:
        text: Text to extract metric values from.
        provider: Optional LLM provider (falls through to extract_metrics).

    Returns:
        List of metric strings found.

    Raises:
        ProviderError: If the LLM API call fails after retries.
    """
    if not text.strip():
        return []

    cache_key = f"mt:{text_hash(text)}"

    if cache_key in _metrics_cache:
        return list(_metrics_cache[cache_key])

    result = await extract_metrics(text, provider=provider)
    _metrics_cache[cache_key] = result
    _evict_oldest(_metrics_cache)
    return list(result)
