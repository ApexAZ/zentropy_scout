"""Resume modification guardrails for variant validation.

REQ-010 §4.4: Modification Limits (Guardrails).

Validates that a JobVariant stays within allowed modification boundaries
relative to its BaseResume. Three automated checks prevent the Ghostwriter
from overstepping:

1. Bullet ID subset — variant bullets must exist in the base resume.
2. Summary length ±20% — prevents complete rewrites disguised as tailoring.
3. No new skills — variant summary skills must exist in the persona.

Pattern follows bullet_reordering.py: pure functions with pre-extracted data.
The caller (Ghostwriter agent) extracts bullet IDs, summary text, and
skills before calling these functions, keeping this module free of LLM
and DB dependencies.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

_MAX_BULLET_IDS: int = 5000
"""Maximum number of bullet IDs per set (base or variant)."""

_MAX_SKILLS: int = 1000
"""Maximum number of skills per set (variant or persona)."""

_MAX_SUMMARY_LENGTH: int = 50_000
"""Maximum character length for summary strings."""

_SUMMARY_LENGTH_TOLERANCE: float = 0.2
"""Allowed deviation from base summary word count (±20%)."""


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class VariantValidationData:
    """Pre-extracted data for variant modification validation.

    All fields are pre-computed by the caller — this dataclass is a pure data
    container with no extraction logic.

    Attributes:
        base_bullet_ids: Set of bullet IDs from the BaseResume
            (flattened from job_bullet_selections).
        variant_bullet_ids: Set of bullet IDs from the JobVariant
            (flattened from job_bullet_order).
        base_summary: The BaseResume professional summary text.
        variant_summary: The JobVariant tailored summary text.
        variant_summary_skills: Lowercased skill names extracted from the
            variant summary (via LLM, provided by the caller).
        persona_skill_names: Lowercased skill names from the Persona's
            complete skill set.
    """

    base_bullet_ids: set[str]
    variant_bullet_ids: set[str]
    base_summary: str
    variant_summary: str
    variant_summary_skills: set[str]
    persona_skill_names: set[str]


# =============================================================================
# Validation
# =============================================================================


def validate_variant_modifications(
    *,
    data: VariantValidationData,
) -> list[str]:
    """Validate that JobVariant modifications stay within allowed limits.

    REQ-010 §4.4: Three automated checks prevent the Ghostwriter from
    overstepping. The user trusts that their resume accurately reflects
    their experience.

    Args:
        data: Pre-extracted validation data from BaseResume, JobVariant,
            and Persona.

    Returns:
        List of violation messages. Empty list means the variant is valid.

    Raises:
        ValueError: If input sizes exceed safety bounds.
    """
    # Safety bounds
    if len(data.base_bullet_ids) > _MAX_BULLET_IDS:
        raise ValueError(
            f"base_bullet_ids has {len(data.base_bullet_ids)} items, "
            f"exceeds maximum of {_MAX_BULLET_IDS}"
        )
    if len(data.variant_bullet_ids) > _MAX_BULLET_IDS:
        raise ValueError(
            f"variant_bullet_ids has {len(data.variant_bullet_ids)} items, "
            f"exceeds maximum of {_MAX_BULLET_IDS}"
        )
    if len(data.variant_summary_skills) > _MAX_SKILLS:
        raise ValueError(
            f"variant_summary_skills has {len(data.variant_summary_skills)} items, "
            f"exceeds maximum of {_MAX_SKILLS}"
        )
    if len(data.persona_skill_names) > _MAX_SKILLS:
        raise ValueError(
            f"persona_skill_names has {len(data.persona_skill_names)} items, "
            f"exceeds maximum of {_MAX_SKILLS}"
        )
    if len(data.base_summary) > _MAX_SUMMARY_LENGTH:
        raise ValueError(
            f"base_summary has {len(data.base_summary)} characters, "
            f"exceeds maximum of {_MAX_SUMMARY_LENGTH}"
        )
    if len(data.variant_summary) > _MAX_SUMMARY_LENGTH:
        raise ValueError(
            f"variant_summary has {len(data.variant_summary)} characters, "
            f"exceeds maximum of {_MAX_SUMMARY_LENGTH}"
        )

    violations: list[str] = []

    # Check 1: Bullet ID Subset
    # All bullet IDs in the JobVariant must be a subset of those in the
    # BaseResume. New bullets not present in the base are a violation.
    new_bullets = data.variant_bullet_ids - data.base_bullet_ids
    if new_bullets:
        violations.append(f"Bullet IDs not in BaseResume: {sorted(new_bullets)}")

    # Check 2: Summary Length (±20%)
    # The variant summary word count must be within 20% of the base resume
    # summary word count. This prevents complete rewrites disguised as
    # "tailoring."
    base_words = len(data.base_summary.split())
    variant_words = len(data.variant_summary.split())

    if base_words == 0:
        # Base has no words — variant must also have no words
        if variant_words > 0:
            violations.append(
                f"Summary word count changed from 0 to {variant_words} "
                f"(base summary is empty)"
            )
    else:
        lower = base_words * (1.0 - _SUMMARY_LENGTH_TOLERANCE)
        upper = base_words * (1.0 + _SUMMARY_LENGTH_TOLERANCE)
        if variant_words < lower or variant_words > upper:
            violations.append(
                f"Summary word count {variant_words} is outside "
                f"±{_SUMMARY_LENGTH_TOLERANCE:.0%} of base ({base_words} words, "
                f"allowed {lower:.0f}–{upper:.0f})"
            )

    # Check 3: No New Skills
    # Skills extracted from the variant summary must be a subset of the
    # Persona's skill set. Any skills not in the Persona are a violation.
    new_skills = data.variant_summary_skills - data.persona_skill_names
    if new_skills:
        violations.append(f"Skills not in Persona: {sorted(new_skills)}")

    logger.debug(
        "Variant validation: %d violation(s) found",
        len(violations),
    )
    return violations
