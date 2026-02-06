"""LLM input sanitization for prompt injection prevention.

Security: Mitigates prompt injection attacks by filtering suspicious patterns
before user-provided text is embedded in LLM prompts.

This is defense-in-depth, not a complete solution. LLM prompts should also
use clear delimiters and system-level guardrails where available.

Known limitation: Cyrillic/Greek homoglyph characters (e.g., Cyrillic 'а' vs
Latin 'a') are NOT normalized by NFKC and could bypass pattern matching.
Addressing this would require Unicode confusable mapping or script detection.
"""

import re
import unicodedata

# Zero-width Unicode characters that can be used to bypass regex filters.
# These are invisible in rendered text but break pattern matching if not stripped.
_ZERO_WIDTH_PATTERN = re.compile(
    "["
    "\u00ad"  # Soft hyphen
    "\u034f"  # Combining grapheme joiner
    "\u061c"  # Arabic letter mark
    "\u180e"  # Mongolian vowel separator (reclassified Zs in Unicode 6.3, still strip)
    "\u200b-\u200f"  # Zero-width space, non-joiner, joiner, LRM, RLM
    "\u2060-\u2064"  # Word joiner, invisible operators
    "\ufe00-\ufe0f"  # Variation selectors (invisible glyph modifiers)
    "\ufeff"  # BOM / zero-width no-break space
    "]"
)

# Patterns that indicate prompt injection attempts
# Each tuple: (pattern, replacement, flags)
_INJECTION_PATTERNS: list[tuple[str, str, int]] = [
    # System prompt override attempts (at line start or after escape sequences)
    (r"^\s*SYSTEM\s*:", "[FILTERED]:", re.IGNORECASE | re.MULTILINE),
    (r"(?:\\n)+\s*SYSTEM\s*:", "\\n[FILTERED]:", re.IGNORECASE),
    # Role tag injections (XML-style)
    (r"<\s*/?\s*system\s*>", "[TAG]", re.IGNORECASE),
    (r"<\s*/?\s*user\s*>", "[TAG]", re.IGNORECASE),
    (r"<\s*/?\s*assistant\s*>", "[TAG]", re.IGNORECASE),
    # Application structural XML tags (prompt structure injection prevention).
    # Tags with underscores are internal prompt tags (e.g., <voice_profile>,
    # <writing_sample>, <job_posting>). Standard HTML tags don't use underscores.
    # Allows optional attributes before closing > to prevent attribute bypass.
    (r"<\s*/?\s*[a-z]+(?:_[a-z]+)+(?:\s[^>]*)?\s*>", "[TAG]", re.IGNORECASE),
    # Known single-word structural tags that don't have underscores.
    # Maintain this list when adding new non-underscore tags to prompt templates.
    # Current: applicant (ghostwriter_prompts.py:83), sample (ghostwriter_prompts.py:78)
    (r"<\s*/?\s*applicant(?:\s[^>]*)?\s*>", "[TAG]", re.IGNORECASE),
    (r"<\s*/?\s*sample(?:\s[^>]*)?\s*>", "[TAG]", re.IGNORECASE),
    # ChatML-style role injections
    (r"<\|system\|>", "[TAG]", re.IGNORECASE),
    (r"<\|user\|>", "[TAG]", re.IGNORECASE),
    (r"<\|assistant\|>", "[TAG]", re.IGNORECASE),
    (r"<\|im_start\|>", "[TAG]", re.IGNORECASE),
    (r"<\|im_end\|>", "[TAG]", re.IGNORECASE),
    # Instruction override attempts
    (r"ignore\s+(all\s+)?previous\s+instructions?", "[FILTERED]", re.IGNORECASE),
    (r"disregard\s+(all\s+)?(prior|previous)", "[FILTERED]", re.IGNORECASE),
    (r"forget\s+everything", "[FILTERED]", re.IGNORECASE),
    (r"new\s+instructions?\s*:", "[FILTERED]:", re.IGNORECASE),
    # Instruction delimiters that might confuse the model
    (r"###\s*instruction\s*###", "[FILTERED]", re.IGNORECASE),
    (r"\[INST\]", "[FILTERED]", re.IGNORECASE),
    (r"\[/INST\]", "[FILTERED]", re.IGNORECASE),
    # Anthropic/Claude-specific role markers
    (r"^\s*Human\s*:", "[FILTERED]:", re.IGNORECASE | re.MULTILINE),
    (r"^\s*Assistant\s*:", "[FILTERED]:", re.IGNORECASE | re.MULTILINE),
    (r"^\s*\[H\]\s*:", "[FILTERED]:", re.IGNORECASE | re.MULTILINE),
    (r"^\s*\[A\]\s*:", "[FILTERED]:", re.IGNORECASE | re.MULTILINE),
]

# Control characters to remove (except common whitespace)
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_llm_input(text: str) -> str:
    """Sanitize user-provided text before embedding in LLM prompts.

    Security: Filters patterns commonly used in prompt injection attacks.
    This is defense-in-depth - not a guarantee against all injection.

    WHY FILTER VS ESCAPE:
    - Escaping doesn't work well with LLMs (they understand meaning, not syntax)
    - Filtering removes suspicious patterns while preserving legitimate content
    - Replacement with [FILTERED] makes sanitization visible for debugging

    Args:
        text: Raw user-provided text (e.g., job posting content).

    Returns:
        Sanitized text with injection patterns neutralized.
    """
    if not text:
        return text

    result = text

    # Normalize Unicode to prevent homoglyph bypass attacks
    # NFKC converts lookalike characters (e.g., Cyrillic 'а' -> ASCII 'a')
    result = unicodedata.normalize("NFKC", result)

    # Strip zero-width Unicode characters that could bypass regex filters.
    # Must happen before pattern matching so "S\u200bY\u200bS..." becomes "SYS..."
    result = _ZERO_WIDTH_PATTERN.sub("", result)

    # Remove control characters (keep \t, \n, \r which are common in text)
    result = _CONTROL_CHAR_PATTERN.sub("", result)

    # Apply injection pattern filters
    for pattern, replacement, flags in _INJECTION_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=flags)

    return result
