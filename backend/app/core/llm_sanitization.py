"""LLM input sanitization for prompt injection prevention.

Security: Mitigates prompt injection attacks by filtering suspicious patterns
before user-provided text is embedded in LLM prompts.

This is defense-in-depth, not a complete solution. LLM prompts should also
use clear delimiters and system-level guardrails where available.
"""

import re
import unicodedata

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

    # Remove control characters (keep \t, \n, \r which are common in text)
    result = _CONTROL_CHAR_PATTERN.sub("", result)

    # Apply injection pattern filters
    for pattern, replacement, flags in _INJECTION_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=flags)

    return result
