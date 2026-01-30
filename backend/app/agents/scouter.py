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
from datetime import UTC, datetime, timedelta
from typing import Any

# WHY: Job data from external sources (Adzuna, RemoteOK, etc.) has varying
# schemas that we normalize during processing. Using Any for raw job dicts
# is intentional - strict typing happens when we create JobPosting models.
# ScouterState uses dict[str, Any] because it's a TypedDict defined in
# app/agents/state.py - we use dict here to avoid circular imports.

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


# =============================================================================
# Polling Flow Functions (§6.2)
# =============================================================================

# WHY: Polling frequency intervals. These are used to calculate when the next
# poll should occur based on user's preferred frequency setting.
POLLING_FREQUENCY_INTERVALS: dict[str, timedelta] = {
    "twice_daily": timedelta(hours=12),
    "daily": timedelta(hours=24),
    "weekly": timedelta(days=7),
}

# WHY: Default interval when frequency is unknown or invalid.
DEFAULT_POLLING_INTERVAL = timedelta(hours=24)


def merge_results(
    source_results: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Merge job results from multiple sources into a single list.

    REQ-007 §6.2: After parallel fetch, normalize to common schema.

    Each job is annotated with its source_name so we can track origin
    for deduplication and also_found_on logic.

    Args:
        source_results: Dict mapping source name to list of jobs from that source.
            E.g., {"Adzuna": [{...}, {...}], "RemoteOK": [{...}]}

    Returns:
        Flattened list of all jobs with source_name field added.
    """
    merged: list[dict[str, Any]] = []

    for source_name, jobs in source_results.items():
        for job in jobs:
            # WHY: Add source_name to track job origin for deduplication
            # and also_found_on logic in later processing steps.
            merged.append({**job, "source_name": source_name})

    return merged


def calculate_next_poll_time(current_time: datetime, frequency: str) -> datetime:
    """Calculate the next scheduled poll time based on frequency.

    REQ-007 §6.2: Update polling state after poll completes.

    Args:
        current_time: The current time (typically when poll completed).
        frequency: Polling frequency ("twice_daily", "daily", "weekly").

    Returns:
        The datetime when the next poll should occur.
    """
    interval = POLLING_FREQUENCY_INTERVALS.get(frequency, DEFAULT_POLLING_INTERVAL)
    return current_time + interval


def create_scouter_state(
    user_id: str,
    persona_id: str,
    enabled_sources: list[str],
) -> dict[str, Any]:
    """Create initial ScouterState for a polling run.

    REQ-007 §6.2: Initialize state before starting polling flow.

    Args:
        user_id: The user's ID.
        persona_id: The persona's ID.
        enabled_sources: List of enabled source names to poll.

    Returns:
        Initial ScouterState dict ready for the polling flow.
    """
    return {
        "user_id": user_id,
        "persona_id": persona_id,
        "enabled_sources": enabled_sources,
        "discovered_jobs": [],
        "processed_jobs": [],
        "error_sources": [],
    }


def record_source_error(
    state: dict[str, Any],
    source_name: str,
) -> dict[str, Any]:
    """Record a source that failed during polling.

    REQ-007 §6.2: Track sources with errors for user feedback.

    Args:
        state: Current ScouterState.
        source_name: Name of the source that encountered an error.

    Returns:
        Updated state with error recorded (immutable update pattern).
    """
    # WHY: Check for existing to prevent duplicates (idempotent operation)
    if source_name in state["error_sources"]:
        return state

    return {
        **state,
        "error_sources": [*state["error_sources"], source_name],
    }
