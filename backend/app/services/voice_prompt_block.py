"""Voice profile system prompt block builder.

REQ-010 §3.3: Voice Profile System Prompt Block.

Generates the <voice_profile> XML block that is included in ALL content
generation prompts (cover letters, resume tailoring, summaries). This is the
canonical template — context-specific prompts may adapt the surrounding
structure, but the voice block itself is standardized here.

WHY SHARED UTILITY: Every generation prompt needs the same voice profile block.
Centralizing it prevents drift between prompt variants and ensures consistent
voice application across all generated content.

WHY PURE FUNCTION: Accepts primitive inputs (strings + lists) rather than ORM
models. The caller extracts fields from VoiceProfile before calling. This keeps
the function testable and decoupled from data access.
"""

from app.core.llm_sanitization import sanitize_llm_input

# =============================================================================
# Constants
# =============================================================================

_MAX_WRITING_SAMPLE_LENGTH = 3000
"""Maximum characters for writing sample in the prompt block."""

_MAX_FIELD_LENGTH = 500
"""Maximum characters for variable-length prompt fields."""

_MAX_PHRASES_COUNT = 20
"""Maximum number of sample phrases or avoid terms to include."""

_DEFAULT_UNSPECIFIED = "None specified"
"""Fallback text when optional voice profile fields are empty."""

_VOICE_PROFILE_TEMPLATE = """<voice_profile>
You are writing as {persona_name}. Match their voice exactly.

TONE: {tone}
SENTENCE STYLE: {sentence_style}
VOCABULARY: {vocabulary_level}
PERSONALITY: {personality_markers}

PREFERRED PHRASES (use these patterns):
{preferred_phrases}

NEVER USE THESE WORDS/PHRASES:
{things_to_avoid}

Read their existing writing samples to internalize their voice:
<writing_sample>
{writing_sample_text}
</writing_sample>
</voice_profile>"""


# =============================================================================
# List Formatting Helpers
# =============================================================================


def _format_sample_phrases(phrases: list[str] | None) -> str:
    """Format sample phrases as newline-dash list per §3.3 template.

    Args:
        phrases: List of preferred phrase patterns, or None.

    Returns:
        Formatted string with each phrase on a dash-prefixed line,
        or "None provided" if empty/None.
    """
    if not phrases:
        return "None provided"

    sanitized = [
        sanitize_llm_input(p.strip()[:_MAX_FIELD_LENGTH])
        for p in phrases[:_MAX_PHRASES_COUNT]
        if p.strip()
    ]
    if not sanitized:
        return "None provided"

    return "\n".join(f"- {phrase}" for phrase in sanitized)


def _format_things_to_avoid(terms: list[str] | None) -> str:
    """Format things-to-avoid as comma-separated list per §3.3 template.

    Args:
        terms: List of blacklisted terms, or None.

    Returns:
        Comma-separated string of terms, or "None specified" if empty/None.
    """
    if not terms:
        return _DEFAULT_UNSPECIFIED

    sanitized = [
        sanitize_llm_input(t.strip()[:_MAX_FIELD_LENGTH])
        for t in terms[:_MAX_PHRASES_COUNT]
        if t.strip()
    ]
    if not sanitized:
        return _DEFAULT_UNSPECIFIED

    return ", ".join(sanitized)


# =============================================================================
# Main Function
# =============================================================================


def build_voice_profile_block(
    *,
    persona_name: str,
    tone: str,
    sentence_style: str,
    vocabulary_level: str,
    personality_markers: str | None = None,
    sample_phrases: list[str] | None = None,
    things_to_avoid: list[str] | None = None,
    writing_sample_text: str | None = None,
) -> str:
    """Build the <voice_profile> prompt block for content generation.

    REQ-010 §3.3: This block is included in ALL content generation prompts.
    It operationalizes the three voice application rules from §3.2:
    - Rule 1: NEVER USE section enforces blacklist (also validated programmatically)
    - Rule 2: PREFERRED PHRASES section provides structural templates
    - Rule 3: SENTENCE STYLE field constrains output structure

    All string parameters are sanitized via sanitize_llm_input() to mitigate
    prompt injection, since voice profile data may include user-provided text.

    Args:
        persona_name: Full name of the persona (e.g., "Jane Smith").
        tone: Overall emotional register for generated content.
        sentence_style: Structural preferences (length, voice).
        vocabulary_level: Word choice guidance (technical vs plain).
        personality_markers: Distinctive characteristics to reproduce, or None.
        sample_phrases: Preferred phrase patterns as templates, or None/empty.
        things_to_avoid: Blacklisted words/phrases for absolute exclusion, or None/empty.
        writing_sample_text: Raw text for voice derivation by LLM, or None.

    Returns:
        Formatted <voice_profile> XML block string ready for prompt embedding.
    """
    # Truncate writing sample to respect size limits
    sample_text = (writing_sample_text or "No sample provided")[
        :_MAX_WRITING_SAMPLE_LENGTH
    ]

    return _VOICE_PROFILE_TEMPLATE.format(
        persona_name=sanitize_llm_input(persona_name[:_MAX_FIELD_LENGTH]),
        tone=sanitize_llm_input(tone[:_MAX_FIELD_LENGTH]),
        sentence_style=sanitize_llm_input(sentence_style[:_MAX_FIELD_LENGTH]),
        vocabulary_level=sanitize_llm_input(vocabulary_level[:_MAX_FIELD_LENGTH]),
        personality_markers=sanitize_llm_input(
            (personality_markers or _DEFAULT_UNSPECIFIED)[:_MAX_FIELD_LENGTH]
        ),
        preferred_phrases=_format_sample_phrases(sample_phrases),
        things_to_avoid=_format_things_to_avoid(things_to_avoid),
        writing_sample_text=sanitize_llm_input(sample_text),
    )
