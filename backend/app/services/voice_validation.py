"""Voice application rules for content generation.

REQ-010 §3.2: Voice Application Rules

Provides validation functions that enforce user voice preferences on generated
content. Currently implements Rule 1 (blacklist enforcement). Rules 2 and 3
(sample phrase templates, sentence style matching) are enforced via LLM prompts
in the voice profile system prompt block (§3.3).

WHY PURE FUNCTION: Accepts primitive inputs (text + list) rather than ORM
models. This keeps the function testable and decoupled from data access —
the caller extracts things_to_avoid from VoiceProfile before calling.
"""

import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Main Function
# =============================================================================


def validate_no_blacklist(text: str, things_to_avoid: list[str]) -> list[str]:
    """Check text for blacklisted terms and return violations.

    REQ-010 §3.2 Rule 1: User explicitly said they don't want these words.
    No exceptions — any match is a violation.

    Matching is case-insensitive and substring-based. Each unique blacklisted
    term found produces exactly one violation, regardless of how many times
    it appears in the text.

    Args:
        text: Generated text to validate.
        things_to_avoid: Blacklisted terms from VoiceProfile.things_to_avoid.

    Returns:
        List of violation messages. Empty list means text is clean.
        Violation messages contain the original user-supplied term text;
        callers must escape before rendering in HTML or log format strings.
    """
    if not text or not things_to_avoid:
        return []

    violations: list[str] = []
    text_lower = text.lower()
    seen_terms: set[str] = set()

    for term in things_to_avoid:
        term_stripped = term.strip()
        if not term_stripped:
            continue

        term_key = term_stripped.lower()
        if term_key in seen_terms:
            continue
        seen_terms.add(term_key)

        if term_key in text_lower:
            violations.append(f"Contains blacklisted term: '{term_stripped}'")

    return violations
