"""Agent source selection service.

REQ-003 §4.3: Agent Source Selection.

Prioritizes job sources based on user's Persona attributes:
- remote_preference = "Remote Only" → prioritize RemoteOK
- target_roles includes government → prioritize USAJobs
- General → all enabled sources

The agent explains its reasoning to the user for transparency.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

# =============================================================================
# Enums
# =============================================================================


class SourcePriority(Enum):
    """Priority level for a job source.

    REQ-003 §4.3: Used to indicate why a source was prioritized.
    """

    HIGH = "high"
    NORMAL = "normal"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SourceSelectionResult:
    """Result of source selection with prioritization and reasoning.

    REQ-003 §4.3: Agent explains reasoning to user.

    Attributes:
        prioritized_sources: Ordered list of sources to query (highest priority first).
        reasoning: Human-readable explanation of source selection.
        priorities: Mapping of source name to priority level.
    """

    prioritized_sources: list[str]
    reasoning: str
    priorities: dict[str, SourcePriority]


# =============================================================================
# Helper Functions
# =============================================================================


# WHY Any: target_roles can be str or dict with title/sector fields (flexible
# schema from persona JSONB column). We check both formats at runtime.
def _detect_government_interest(target_roles: list[Any] | None) -> bool:
    """Check if target_roles indicate government sector interest.

    Args:
        target_roles: List of target roles (strings or dicts with title/sector).

    Returns:
        True if any role indicates government interest.
    """
    if not target_roles:
        return False

    # WHY: target_roles can be either simple strings or dicts with sector/title.
    # We check both the role text and explicit sector field for flexibility.
    government_keywords = {"government", "federal", "public sector", "usajobs"}

    for role in target_roles:
        if isinstance(role, str):
            # Simple string role
            if any(kw in role.lower() for kw in government_keywords):
                return True
        elif isinstance(role, dict):
            # Dict with title/sector fields
            title = str(role.get("title", "")).lower()
            sector = str(role.get("sector", "")).lower()
            if any(kw in title for kw in government_keywords) or any(
                kw in sector for kw in government_keywords
            ):
                return True

    return False


# =============================================================================
# Main Function
# =============================================================================


# WHY Any: Same as above - target_roles from persona JSONB can be str or dict.
def prioritize_sources(
    enabled_sources: list[str],
    remote_preference: str,
    target_roles: list[Any] | None,
) -> SourceSelectionResult:
    """Prioritize job sources based on Persona attributes.

    REQ-003 §4.3: Agent selects sources based on Persona.

    Priority rules:
    - remote_preference = "Remote Only" → prioritize RemoteOK
    - target_roles includes government → prioritize USAJobs
    - Otherwise → all enabled sources in original order

    Args:
        enabled_sources: List of source names the user has enabled.
        remote_preference: User's remote work preference ("Remote Only", etc.).
        target_roles: User's target job roles (may include government sector).

    Returns:
        SourceSelectionResult with prioritized sources and reasoning.
    """
    if not enabled_sources:
        return SourceSelectionResult(
            prioritized_sources=[],
            reasoning="No job sources are currently enabled.",
            priorities={},
        )

    # Track which sources to prioritize and why
    high_priority: list[str] = []
    reasons: list[str] = []
    priorities: dict[str, SourcePriority] = {}

    # Check remote-only preference
    is_remote_only = remote_preference == "Remote Only"
    if is_remote_only and "RemoteOK" in enabled_sources:
        high_priority.append("RemoteOK")
        reasons.append(
            "Prioritizing RemoteOK because your preference is remote-only work."
        )

    # Check government interest
    has_government_interest = _detect_government_interest(target_roles)
    if has_government_interest and "USAJobs" in enabled_sources:
        high_priority.append("USAJobs")
        reasons.append(
            "Prioritizing USAJobs because your target roles include government positions."
        )

    # Build prioritized list: high priority first, then remaining in original order
    remaining_sources = [s for s in enabled_sources if s not in high_priority]
    prioritized = high_priority + remaining_sources

    # Assign priority levels
    for source in prioritized:
        if source in high_priority:
            priorities[source] = SourcePriority.HIGH
        else:
            priorities[source] = SourcePriority.NORMAL

    # Build reasoning message
    if reasons:
        reasoning = " ".join(reasons)
    else:
        reasoning = (
            f"Searching all {len(enabled_sources)} enabled sources: "
            f"{', '.join(enabled_sources)}."
        )

    return SourceSelectionResult(
        prioritized_sources=prioritized,
        reasoning=reasoning,
        priorities=priorities,
    )
