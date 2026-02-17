"""Property-based fuzz tests for LLM sanitization pipeline.

Security: Uses Hypothesis to generate random Unicode text and verify
invariants that must hold for ANY input, not just hand-crafted examples.
These complement the example-based tests in test_llm_sanitization.py.

Phase 13.2: Hypothesis property-based fuzz testing for LLM sanitization.
"""

import re
import unicodedata

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.core.llm_sanitization import (
    _COMBINING_MARK_CATEGORIES,
    _CONTROL_CHAR_PATTERN,
    _MAX_FEEDBACK_LENGTH,
    _ZERO_WIDTH_PATTERN,
    sanitize_llm_input,
    sanitize_user_feedback,
)

# =============================================================================
# Strategies
# =============================================================================

# Broad Unicode text excluding surrogates (which Python can't represent in str)
unicode_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0,
    max_size=500,
)

# ASCII-only text for roundtrip testing
ascii_text = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=0,
    max_size=500,
)

# Text likely to contain injection-adjacent patterns.
# Includes ASCII injection keywords, zero-width chars, combining marks,
# and Cyrillic/Greek confusables from _CONFUSABLE_MAP.
injection_adjacent_text = st.text(
    alphabet=st.sampled_from(
        list("SYSTEMsystemUSERuserassistantASSISTANTHumanhumanINST")
        + list(":< >/|_[]\n\t`#")
        + [
            "\u200b",  # zero-width space
            "\u200c",  # ZWNJ
            "\u200d",  # ZWJ
            "\u0300",  # combining grave
            "\u0301",  # combining acute
            "\u0430",  # Cyrillic a
            "\u0435",  # Cyrillic e
            "\u043e",  # Cyrillic o
            "\u0455",  # Cyrillic s
            "\u0440",  # Cyrillic p
            "\u0441",  # Cyrillic c
            "\u0443",  # Cyrillic y
            "\u0456",  # Cyrillic i
            "\u043c",  # Cyrillic m (lowercase)
            "\u0410",  # Cyrillic A
            "\u0415",  # Cyrillic E
            "\u041c",  # Cyrillic M
            "\u0422",  # Cyrillic T
            "\u0405",  # Cyrillic S
            "\u0423",  # Cyrillic Y
            "\ufeff",  # BOM
            "\u00ad",  # soft hyphen
        ]
    ),
    min_size=0,
    max_size=200,
)

# Longer text for feedback truncation testing
long_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=400,
    max_size=2000,
)

# =============================================================================
# Shared assertion helpers (avoid duplicating regex patterns across tests)
# =============================================================================

# Pre-compiled patterns used in multiple property tests
_SYSTEM_COLON_RE = re.compile(r"^\s*SYSTEM\s*:", re.IGNORECASE | re.MULTILINE)
_ROLE_TAG_RES = [
    re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE),
    re.compile(r"<\s*/?\s*user\s*>", re.IGNORECASE),
    re.compile(r"<\s*/?\s*assistant\s*>", re.IGNORECASE),
]
_UNDERSCORE_TAG_RE = re.compile(
    r"<\s*/?\s*[a-z]+(?:_[a-z]+)+(?:\s[^>]*)?\s*>", re.IGNORECASE
)
_APPLICANT_SAMPLE_RE = re.compile(
    r"<\s*/?\s*(?:applicant|sample)(?:\s[^>]*)?\s*>", re.IGNORECASE
)
_CHATML_MARKERS = (
    "<|system|>",
    "<|user|>",
    "<|assistant|>",
    "<|im_start|>",
    "<|im_end|>",
)
_AUTHORITY_KEYWORD_RE = re.compile(
    r"(?:IMPORTANT|OVERRIDE|CRITICAL|URGENT|WARNING|ATTENTION|PRIORITY"
    r"|MUST|MANDATORY|REQUIRED)\s*:",
    re.IGNORECASE,
)


def _assert_no_forbidden_patterns(result: str) -> None:
    """Assert no injection patterns remain in sanitized output."""
    # System prompt override
    assert not _SYSTEM_COLON_RE.search(result)
    # Role XML tags
    for pattern in _ROLE_TAG_RES:
        assert not pattern.search(result)
    # ChatML markers
    lower = result.lower()
    for marker in _CHATML_MARKERS:
        assert marker not in lower
    # Underscore structural tags
    assert not _UNDERSCORE_TAG_RE.search(result)
    # Single-word structural tags
    assert not _APPLICANT_SAMPLE_RE.search(result)
    # Instruction overrides
    assert not re.search(
        r"ignore\s+(all\s+)?previous\s+instructions?", result, re.IGNORECASE
    )
    assert not re.search(r"forget\s+everything", result, re.IGNORECASE)
    assert not re.search(r"new\s+instructions?\s*:", result, re.IGNORECASE)
    assert not re.search(
        r"disregard\s+(all\s+)?(prior|previous)", result, re.IGNORECASE
    )
    # [INST]/[/INST] delimiters
    assert not re.search(r"\[INST\]", result, re.IGNORECASE)
    assert not re.search(r"\[/INST\]", result, re.IGNORECASE)
    # ###instruction### delimiter
    assert not re.search(r"###\s*instruction\s*###", result, re.IGNORECASE)
    # Anthropic/Claude role markers
    assert not re.search(r"^\s*Human\s*:", result, re.IGNORECASE | re.MULTILINE)
    assert not re.search(r"^\s*Assistant\s*:", result, re.IGNORECASE | re.MULTILINE)
    assert not re.search(r"^\s*\[H\]\s*:", result, re.IGNORECASE | re.MULTILINE)
    assert not re.search(r"^\s*\[A\]\s*:", result, re.IGNORECASE | re.MULTILINE)


# =============================================================================
# Property Tests: sanitize_llm_input
# =============================================================================


class TestSanitizeLLMInputProperties:
    """Property-based invariants for the core sanitization pipeline."""

    @given(unicode_text)
    @settings(max_examples=500)
    def test_idempotent(self, text: str) -> None:
        """Sanitizing twice yields the same result as sanitizing once.

        This is critical: if the output changes on re-sanitization, it means
        the first pass left something that triggers further filtering.
        """
        once = sanitize_llm_input(text)
        twice = sanitize_llm_input(once)
        assert once == twice

    @given(unicode_text)
    @settings(max_examples=500)
    def test_output_is_nfc_normalized(self, text: str) -> None:
        """Output is always in NFC form (canonical composition).

        The pipeline ends with NFC normalization. This ensures consistent
        string representation for downstream consumers.
        """
        result = sanitize_llm_input(text)
        assert result == unicodedata.normalize("NFC", result)

    @given(unicode_text)
    @settings(max_examples=500)
    def test_no_zero_width_characters(self, text: str) -> None:
        """Output never contains zero-width Unicode characters.

        These invisible characters could be used to bypass regex-based filters
        downstream. The pipeline strips them all.
        """
        result = sanitize_llm_input(text)
        assert _ZERO_WIDTH_PATTERN.search(result) is None

    @given(unicode_text)
    @settings(max_examples=500)
    def test_no_combining_marks(self, text: str) -> None:
        """Output contains no combining marks (Unicode categories Mn/Me).

        After NFD decomposition and combining mark stripping, no standalone
        combining marks should remain. NFC recomposition at the end handles
        any remaining sequences.
        """
        result = sanitize_llm_input(text)
        for ch in result:
            assert unicodedata.category(ch) not in _COMBINING_MARK_CATEGORIES, (
                f"Combining mark U+{ord(ch):04X} ({unicodedata.name(ch, '?')}) "
                f"found in output"
            )

    @given(unicode_text)
    @settings(max_examples=500)
    def test_no_control_characters(self, text: str) -> None:
        """Output contains no control characters (except tab, newline, CR).

        Control chars are stripped to prevent hidden payloads.
        """
        result = sanitize_llm_input(text)
        assert _CONTROL_CHAR_PATTERN.search(result) is None

    @given(unicode_text)
    @settings(max_examples=500)
    def test_no_forbidden_patterns(self, text: str) -> None:
        """Output never contains any injection patterns.

        Covers all filtered patterns: SYSTEM:, role XML tags, ChatML markers,
        underscore structural tags, <applicant>/<sample>, instruction overrides,
        [INST]/[/INST], ###instruction###, and Human:/Assistant:/[H]:/[A]:.
        """
        result = sanitize_llm_input(text)
        _assert_no_forbidden_patterns(result)

    @given(unicode_text)
    @settings(max_examples=500)
    def test_returns_string(self, text: str) -> None:
        """Output is always a string (never None or other type)."""
        result = sanitize_llm_input(text)
        assert isinstance(result, str)

    @given(injection_adjacent_text)
    @settings(max_examples=1000)
    def test_injection_adjacent_idempotent(self, text: str) -> None:
        """Idempotence holds for injection-adjacent character combinations.

        This uses a focused alphabet of characters that commonly appear in
        injection attempts, increasing the chance of finding edge cases
        where normalization + filtering interact unexpectedly.
        """
        once = sanitize_llm_input(text)
        twice = sanitize_llm_input(once)
        assert once == twice

    @given(injection_adjacent_text)
    @settings(max_examples=1000)
    def test_injection_adjacent_no_forbidden_output(self, text: str) -> None:
        """Injection-adjacent inputs never produce forbidden patterns.

        Uses a focused alphabet with injection-relevant ASCII, zero-width
        chars, combining marks, and Cyrillic/Greek confusables.
        """
        result = sanitize_llm_input(text)
        _assert_no_forbidden_patterns(result)


# =============================================================================
# Property Tests: sanitize_user_feedback
# =============================================================================


class TestSanitizeUserFeedbackProperties:
    """Property-based invariants for feedback sanitization."""

    @given(unicode_text)
    @settings(max_examples=500)
    def test_feedback_idempotent(self, text: str) -> None:
        """Sanitizing feedback twice yields the same result as once."""
        once = sanitize_user_feedback(text)
        twice = sanitize_user_feedback(once)
        assert once == twice

    @given(unicode_text)
    @settings(max_examples=500)
    def test_feedback_respects_max_length(self, text: str) -> None:
        """Feedback output never exceeds MAX_FEEDBACK_LENGTH."""
        result = sanitize_user_feedback(text)
        assert len(result) <= _MAX_FEEDBACK_LENGTH

    @given(long_text)
    @settings(max_examples=200)
    def test_long_feedback_truncated(self, text: str) -> None:
        """Long feedback is always truncated to at most 500 characters."""
        result = sanitize_user_feedback(text)
        assert len(result) <= _MAX_FEEDBACK_LENGTH

    @given(unicode_text)
    @settings(max_examples=500)
    def test_feedback_output_is_nfc(self, text: str) -> None:
        """Feedback output is always in NFC form."""
        result = sanitize_user_feedback(text)
        assert result == unicodedata.normalize("NFC", result)

    @given(unicode_text)
    @settings(max_examples=500)
    def test_feedback_no_authority_keywords(self, text: str) -> None:
        """Feedback output never contains authority keywords with colons."""
        result = sanitize_user_feedback(text)
        assert not _AUTHORITY_KEYWORD_RE.search(result)

    @given(unicode_text)
    @settings(max_examples=500)
    def test_feedback_no_fenced_injection_blocks(self, text: str) -> None:
        """Feedback output never contains ```system/instructions/prompt blocks."""
        result = sanitize_user_feedback(text)
        assert not re.search(
            r"```\s*(?:system|instructions?|prompt|rules)",
            result,
            re.IGNORECASE,
        )

    @given(unicode_text)
    @settings(max_examples=500)
    def test_feedback_no_ignore_above_prior(self, text: str) -> None:
        """Feedback output never contains 'ignore above/prior' patterns."""
        result = sanitize_user_feedback(text)
        assert not re.search(r"ignore\s+(all\s+)?(above|prior)", result, re.IGNORECASE)
        assert not re.search(r"disregard\s+(all\s+)?above", result, re.IGNORECASE)

    @given(unicode_text)
    @settings(max_examples=500)
    def test_feedback_inherits_llm_input_guarantees(self, text: str) -> None:
        """Feedback output inherits all sanitize_llm_input guarantees.

        Since sanitize_user_feedback calls sanitize_llm_input internally,
        all its invariants should also hold.
        """
        result = sanitize_user_feedback(text)
        # No zero-width chars
        assert _ZERO_WIDTH_PATTERN.search(result) is None
        # No combining marks
        for ch in result:
            assert unicodedata.category(ch) not in _COMBINING_MARK_CATEGORIES
        # No control chars
        assert _CONTROL_CHAR_PATTERN.search(result) is None


# =============================================================================
# Edge Case Properties
# =============================================================================


class TestEdgeCaseProperties:
    """Property tests for edge cases and boundary conditions."""

    def test_empty_string_passthrough(self) -> None:
        """Empty string returns empty string for both functions."""
        assert sanitize_llm_input("") == ""
        assert sanitize_user_feedback("") == ""

    @given(ascii_text)
    @settings(max_examples=500)
    def test_safe_ascii_roundtrip(self, text: str) -> None:
        """Pure printable ASCII without injection keywords passes unchanged.

        Uses assume() to discard inputs that contain injection-triggering
        substrings, then verifies the pipeline is a no-op for safe content.
        """
        lower = text.lower()
        skip_triggers = [
            "system:",
            "system >",
            "<system",
            "<user",
            "<assistant",
            "ignore",
            "disregard",
            "forget everything",
            "new instruction",
            "[inst]",
            "[/inst]",
            "human:",
            "assistant:",
            "[h]:",
            "[a]:",
            "<|",
            "###instruction###",
            "<applicant",
            "<sample",
        ]
        assume(not any(trigger in lower for trigger in skip_triggers))
        assume(not re.search(r"<\s*/?\s*[a-z]+_[a-z]+", text, re.IGNORECASE))

        result = sanitize_llm_input(text)
        assert result == text

    @given(
        st.text(
            min_size=1,
            max_size=1,
            alphabet=st.characters(blacklist_categories=("Cs",)),
        )
    )
    @settings(max_examples=1000)
    def test_single_character_no_crash(self, text: str) -> None:
        """Single-character inputs never cause an error."""
        result = sanitize_llm_input(text)
        assert isinstance(result, str)

    @given(unicode_text)
    @settings(max_examples=300)
    def test_output_length_bounded(self, text: str) -> None:
        """Output length is bounded: at most input length + constant overhead.

        Replacement tokens like [FILTERED] or [TAG] can make the output
        longer than input in some cases. The key invariant is that growth
        is bounded and the pipeline always terminates.
        """
        result = sanitize_llm_input(text)
        assert len(result) < len(text) + 1000
