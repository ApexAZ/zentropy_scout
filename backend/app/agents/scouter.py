"""Scouter Agent implementation.

REQ-007 §6: Scouter Agent

The Scouter Agent discovers job postings from external sources and prepares
them for scoring by the Strategist. It:
- Triggers on scheduled polls, manual refresh requests, or source additions
- Fetches jobs from enabled sources in parallel
- Extracts skills and culture text using LLM
- Calculates ghost scores
- Deduplicates and stores new jobs
- Invokes Strategist for scoring

Architecture:
    [Trigger] → get_enabled_sources → fetch_sources (parallel) →
        → merge_results → deduplicate_jobs → extract_skills →
        → calculate_ghost_score → save_jobs → invoke_strategist →
        → update_poll_state → [END]

Trigger Conditions (§6.1):
    - Scheduled poll: Based on Persona.polling_frequency
    - Manual refresh: User says "Find new jobs" or clicks refresh
    - Source added: User enables a new job source
"""

import re
from datetime import UTC, datetime

# =============================================================================
# Constants (§6.1)
# =============================================================================

# WHY: These patterns detect user intent to manually trigger job discovery.
# They're case-insensitive and match common variations of job search requests.
# Patterns are ordered by specificity (more specific first).
MANUAL_REFRESH_PATTERNS = [
    # Direct job search requests
    re.compile(r"find\s+(?:new\s+)?(?:me\s+)?(?:some\s+)?jobs?", re.IGNORECASE),
    re.compile(r"search\s+for\s+(?:new\s+)?(?:jobs?|opportunities)", re.IGNORECASE),
    re.compile(r"look\s+for\s+(?:new\s+)?(?:jobs?|positions)", re.IGNORECASE),
    # Refresh/update requests
    re.compile(r"refresh\s+(?:my\s+)?(?:job\s+)?(?:feed|list|jobs?)", re.IGNORECASE),
    re.compile(r"update\s+(?:my\s+)?(?:job\s+)?(?:feed|list|jobs?)", re.IGNORECASE),
    # Scan/check requests
    re.compile(r"scan\s+(?:for\s+)?(?:new\s+)?(?:jobs?|job\s+boards?)", re.IGNORECASE),
    re.compile(
        r"check\s+for\s+(?:new\s+)?(?:jobs?|opportunities|positions)", re.IGNORECASE
    ),
]


# =============================================================================
# Trigger Condition Functions (§6.1)
# =============================================================================


def should_poll(next_poll_at: datetime | None) -> bool:
    """Check if scheduled polling should trigger.

    REQ-007 §6.1: Scheduled poll based on Persona.polling_frequency.

    Args:
        next_poll_at: The scheduled time for next poll. None if never polled.

    Returns:
        True if polling should occur (time passed or never polled).
    """
    # Never polled before - should poll
    if next_poll_at is None:
        return True

    # Poll if scheduled time has passed
    now = datetime.now(UTC)
    return now >= next_poll_at


def is_manual_refresh_request(message: str) -> bool:
    """Check if user message is a manual job refresh request.

    REQ-007 §6.1: Manual refresh triggers when user explicitly requests
    job discovery (e.g., "Find new jobs", "Refresh my job feed").

    Args:
        message: User's message text.

    Returns:
        True if message matches a manual refresh pattern.
    """
    if not message:
        return False

    return any(pattern.search(message) for pattern in MANUAL_REFRESH_PATTERNS)


def is_source_added_trigger(
    previous_sources: list[str], current_sources: list[str]
) -> bool:
    """Check if a new source was added (trigger for immediate poll).

    REQ-007 §6.1: Source added triggers immediate polling when user
    enables a new job source.

    Args:
        previous_sources: List of previously enabled source names.
        current_sources: List of currently enabled source names.

    Returns:
        True if current_sources contains sources not in previous_sources.
    """
    previous_set = set(previous_sources)
    current_set = set(current_sources)

    # Check if any sources were added
    added_sources = current_set - previous_set
    return len(added_sources) > 0
