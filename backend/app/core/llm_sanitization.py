"""LLM input sanitization for prompt injection prevention.

Security: Mitigates prompt injection attacks by filtering suspicious patterns
before user-provided text is embedded in LLM prompts.

This is defense-in-depth, not a complete solution. LLM prompts should also
use clear delimiters and system-level guardrails where available.
"""

import re
import unicodedata

# =============================================================================
# Confusable Character Mapping (Cyrillic/Greek → Latin)
# =============================================================================

# Characters from Cyrillic and Greek that are visually identical to Latin letters.
# NFKC normalization does NOT handle cross-script confusables, so we map them
# explicitly. Only characters that are near-identical in common fonts are included.
# Source: Unicode TR39 (Security Mechanisms) confusable mappings.
_CONFUSABLE_MAP: dict[int, str] = {
    # Cyrillic lowercase → Latin
    0x0430: "a",  # а → a
    0x0441: "c",  # с → c
    0x0435: "e",  # е → e
    0x0456: "i",  # і → i (Ukrainian)
    0x0458: "j",  # ј → j (Serbian)
    0x043E: "o",  # о → o
    0x0440: "p",  # р → p
    0x0455: "s",  # ѕ → s (Macedonian)
    0x0445: "x",  # х → x
    0x0443: "y",  # у → y
    0x04CF: "l",  # ӏ → l (Palochka)
    # Cyrillic uppercase → Latin
    0x0410: "A",  # А → A
    0x0412: "B",  # В → B
    0x0421: "C",  # С → C
    0x0415: "E",  # Е → E
    0x041D: "H",  # Н → H
    0x0406: "I",  # І → I
    0x0408: "J",  # Ј → J
    0x041A: "K",  # К → K
    0x041C: "M",  # М → M
    0x041E: "O",  # О → O
    0x0420: "P",  # Р → P
    0x0405: "S",  # Ѕ → S
    0x0422: "T",  # Т → T
    0x0425: "X",  # Х → X
    0x0423: "Y",  # У → Y
    # Greek uppercase → Latin (lowercase Greek letters have distinct shapes)
    0x0391: "A",  # Α → A
    0x0392: "B",  # Β → B
    0x0395: "E",  # Ε → E
    0x0397: "H",  # Η → H
    0x0399: "I",  # Ι → I
    0x039A: "K",  # Κ → K
    0x039C: "M",  # Μ → M
    0x039D: "N",  # Ν → N
    0x039F: "O",  # Ο → O
    0x03A1: "P",  # Ρ → P
    0x03A4: "T",  # Τ → T
    0x03A5: "Y",  # Υ → Y
    0x03A7: "X",  # Χ → X
    0x0396: "Z",  # Ζ → Z
    # Greek lowercase (visually similar)
    0x03BF: "o",  # ο → o
    0x03C5: "u",  # υ → u (upsilon)
}

_CONFUSABLE_TRANS = str.maketrans(_CONFUSABLE_MAP)

# =============================================================================
# Unicode Stripping Patterns
# =============================================================================

# Zero-width Unicode characters that can be used to bypass regex filters.
# These are invisible in rendered text but break pattern matching if not stripped.
_ZERO_WIDTH_PATTERN = re.compile(
    "["
    "\u00ad"  # Soft hyphen
    "\u034f"  # Combining grapheme joiner
    "\u061c"  # Arabic letter mark
    "\u180e"  # Mongolian vowel separator (reclassified Zs in Unicode 6.3, still strip)
    "\u200b-\u200f"  # Zero-width space, non-joiner, joiner, LRM, RLM
    "\u202a-\u202e"  # BiDi embedding controls (LRE, RLE, PDF, LRO, RLO)
    "\u2060-\u2064"  # Word joiner, invisible operators
    "\u2066-\u2069"  # BiDi isolate controls (LRI, RLI, FSI, PDI)
    "\ufe00-\ufe0f"  # Variation selectors (invisible glyph modifiers)
    "\ufeff"  # BOM / zero-width no-break space
    "\ufff9-\ufffb"  # Interlinear annotation anchor/separator/terminator
    "\U000e0001"  # Language tag
    "\U000e0020-\U000e007f"  # Tag characters
    "\U000e0100-\U000e01ef"  # Variation selectors supplement
    "]"
)

# Replacement tokens for sanitized content
_REPLACEMENT_TAG = "[TAG]"
_REPLACEMENT_FILTERED = "[FILTERED]"
_REPLACEMENT_FILTERED_COLON = "[FILTERED]:"

# Patterns that indicate prompt injection attempts
# Each tuple: (pattern, replacement, flags)
_INJECTION_PATTERNS: list[tuple[str, str, int]] = [
    # System prompt override attempts (at line start or after escape sequences)
    (r"^\s*SYSTEM\s*:", _REPLACEMENT_FILTERED_COLON, re.IGNORECASE | re.MULTILINE),
    (r"(?:\\n)+\s*SYSTEM\s*:", "\\n" + _REPLACEMENT_FILTERED_COLON, re.IGNORECASE),
    # Role tag injections (XML-style)
    (r"<\s*/?\s*system\s*>", _REPLACEMENT_TAG, re.IGNORECASE),
    (r"<\s*/?\s*user\s*>", _REPLACEMENT_TAG, re.IGNORECASE),
    (r"<\s*/?\s*assistant\s*>", _REPLACEMENT_TAG, re.IGNORECASE),
    # Application structural XML tags (prompt structure injection prevention).
    # Tags with underscores are internal prompt tags (e.g., <voice_profile>,
    # <writing_sample>, <job_posting>). Standard HTML tags don't use underscores.
    # Allows optional attributes before closing > to prevent attribute bypass.
    (r"<\s*/?\s*[a-z]+(?:_[a-z]+)+(?:\s[^>]*)?\s*>", _REPLACEMENT_TAG, re.IGNORECASE),
    # Known single-word structural tags that don't have underscores.
    # Maintain this list when adding new non-underscore tags to prompt templates.
    # Current: applicant (ghostwriter_prompts.py:83), sample (ghostwriter_prompts.py:78)
    (r"<\s*/?\s*applicant(?:\s[^>]*)?\s*>", _REPLACEMENT_TAG, re.IGNORECASE),
    (r"<\s*/?\s*sample(?:\s[^>]*)?\s*>", _REPLACEMENT_TAG, re.IGNORECASE),
    # ChatML-style role injections
    (r"<\|system\|>", _REPLACEMENT_TAG, re.IGNORECASE),
    (r"<\|user\|>", _REPLACEMENT_TAG, re.IGNORECASE),
    (r"<\|assistant\|>", _REPLACEMENT_TAG, re.IGNORECASE),
    (r"<\|im_start\|>", _REPLACEMENT_TAG, re.IGNORECASE),
    (r"<\|im_end\|>", _REPLACEMENT_TAG, re.IGNORECASE),
    # Instruction override attempts
    (
        r"ignore\s+(all\s+)?previous\s+instructions?",
        _REPLACEMENT_FILTERED,
        re.IGNORECASE,
    ),
    (r"disregard\s+(all\s+)?(prior|previous)", _REPLACEMENT_FILTERED, re.IGNORECASE),
    (r"forget\s+everything", _REPLACEMENT_FILTERED, re.IGNORECASE),
    (r"new\s+instructions?\s*:", _REPLACEMENT_FILTERED_COLON, re.IGNORECASE),
    # Instruction delimiters that might confuse the model
    (r"###\s*instruction\s*###", _REPLACEMENT_FILTERED, re.IGNORECASE),
    (r"\[INST\]", _REPLACEMENT_FILTERED, re.IGNORECASE),
    (r"\[/INST\]", _REPLACEMENT_FILTERED, re.IGNORECASE),
    # Anthropic/Claude-specific role markers
    (r"^\s*Human\s*:", _REPLACEMENT_FILTERED_COLON, re.IGNORECASE | re.MULTILINE),
    (r"^\s*Assistant\s*:", _REPLACEMENT_FILTERED_COLON, re.IGNORECASE | re.MULTILINE),
    (r"^\s*\[H\]\s*:", _REPLACEMENT_FILTERED_COLON, re.IGNORECASE | re.MULTILINE),
    (r"^\s*\[A\]\s*:", _REPLACEMENT_FILTERED_COLON, re.IGNORECASE | re.MULTILINE),
]

# Unicode categories for combining marks to strip after NFD decomposition.
# Uses category-based detection instead of fixed ranges to cover all blocks:
# Mn (Mark, nonspacing) and Me (Mark, enclosing) across the entire Unicode space.
_COMBINING_MARK_CATEGORIES = frozenset(("Mn", "Me"))

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

    # Normalize Unicode to prevent compatibility-form bypass attacks
    # NFKC converts fullwidth/styled variants (e.g., Ａ → A, 𝐒 → S)
    result = unicodedata.normalize("NFKC", result)

    # Strip zero-width Unicode characters that could bypass regex filters.
    # Must happen before pattern matching so "S\u200bY\u200bS..." becomes "SYS..."
    result = _ZERO_WIDTH_PATTERN.sub("", result)

    # Decompose to NFD so ALL combining marks become separate codepoints.
    # NFKC precomposes some letter+mark pairs (Y+grave → Ỳ), which would
    # survive a combining mark strip. NFD reverses this: Ỳ → Y+\u0300.
    result = unicodedata.normalize("NFD", result)

    # Strip ALL combining marks (Unicode categories Mn/Me). After NFD, all
    # accents are separate combining characters. Category-based detection covers
    # all Unicode blocks (Diacritical Marks, Supplement, Extended, Symbols, etc.).
    # This catches malicious insertions (S\u0300Y\u0300S... to bypass "SYSTEM")
    # and normalizes accented text to base forms (é → e).
    result = "".join(
        ch
        for ch in result
        if unicodedata.category(ch) not in _COMBINING_MARK_CATEGORIES
    )

    # Map Cyrillic/Greek confusable characters to their Latin equivalents.
    # NFKC does NOT handle cross-script homoglyphs (Cyrillic а ≠ Latin a).
    result = result.translate(_CONFUSABLE_TRANS)

    # Remove control characters (keep \t, \n, \r which are common in text)
    result = _CONTROL_CHAR_PATTERN.sub("", result)

    # Apply injection pattern filters
    for pattern, replacement, flags in _INJECTION_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=flags)

    # Recompose to NFC for clean output (base characters without combining marks)
    result = unicodedata.normalize("NFC", result)

    return result
