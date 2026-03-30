"""Persona change detection during content generation.

REQ-010 §8.3: Persona Changed During Generation.

During the 10-30s generation window, the user's persona may be updated.
This module detects the change by comparing ``persona.updated_at``
timestamps before and after generation, then returns a structured result
with a warning while preserving the generated content.
"""

from dataclasses import dataclass
from datetime import datetime

_WARNING_MESSAGE: str = (
    "Your profile was updated during generation. "
    "Want to regenerate with your latest information?"
)
"""User-facing warning when persona changes mid-generation (REQ-010 §8.3)."""


@dataclass(frozen=True)
class PersonaChangeResult:
    """Result of checking for persona changes during content generation.

    REQ-010 §8.3: Captures the persona change detection outcome in a
    single immutable result. Generated content is always preserved.

    Attributes:
        persona_changed: True if persona was modified during generation.
        warning: User-facing warning message when persona_changed is True.
    """

    persona_changed: bool
    warning: str | None


def check_persona_changed(
    *,
    original_updated_at: datetime,
    current_updated_at: datetime,
) -> PersonaChangeResult:
    """Compare persona timestamps to detect changes during generation.

    REQ-010 §8.3: The graph node snapshots ``persona.updated_at`` before
    generation and re-fetches it after. This pure function compares the
    two timestamps. If they differ, the persona was modified mid-generation.

    Generated content is never discarded — the warning prompts the user
    to optionally regenerate with their latest information.

    Args:
        original_updated_at: Snapshot of persona.updated_at before generation.
        current_updated_at: Re-fetched persona.updated_at after generation.

    Returns:
        PersonaChangeResult with persona_changed=True and warning if
        timestamps differ.
    """
    changed = original_updated_at != current_updated_at
    return PersonaChangeResult(
        persona_changed=changed,
        warning=_WARNING_MESSAGE if changed else None,
    )
