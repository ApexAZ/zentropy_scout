"""Discovery Workflow service for job discovery orchestration.

REQ-003 §13.1: Workflow — Discovery Flow.

The Discovery Workflow orchestrates the full job discovery process:
1. Trigger detection (scheduled, manual, source added)
2. JobFetchService invocation (replaced scouter graph in REQ-016)
3. Result presentation (sorted by Fit Score)

This service ties together trigger detection functions from scouter.py
with the JobFetchService pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

# WHY Any: Job data flows through multiple layers (source adapters,
# services, API endpoints) with varying schemas. Using dict[str, Any]
# provides flexibility while strict typing happens when creating
# JobPosting models at persistence.
from app.agents.scouter import (
    is_manual_refresh_request,
    is_source_added_trigger,
    should_poll,
)
from app.services.job_fetch_service import JobFetchService

# =============================================================================
# Enums
# =============================================================================


class TriggerType(Enum):
    """Types of discovery triggers.

    REQ-007 §6.1: Trigger Conditions.
    """

    # Scheduled poll based on Persona.polling_frequency
    SCHEDULED = "scheduled"

    # User explicitly requested job discovery
    MANUAL = "manual"

    # User enabled a new job source
    SOURCE_ADDED = "source_added"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class DiscoveryTrigger:
    """Detected trigger for discovery workflow.

    Captures which trigger condition was met and relevant context.

    Attributes:
        trigger_type: Type of trigger detected.
        next_poll_at: Scheduled poll time (for SCHEDULED trigger).
        user_message: User's message text (for MANUAL trigger).
        previous_sources: Previous enabled sources (for SOURCE_ADDED trigger).
        current_sources: Current enabled sources (for SOURCE_ADDED trigger).
    """

    trigger_type: TriggerType
    next_poll_at: datetime | None = None
    user_message: str | None = None
    previous_sources: list[str] | None = None
    current_sources: list[str] | None = None


@dataclass
class DiscoveryResult:
    """Result of discovery workflow execution.

    REQ-003 §13.1: Present matches sorted by Fit Score.

    Attributes:
        jobs: List of discovered jobs sorted by fit_score descending.
        total_discovered: Total number of jobs discovered.
        sources_queried: List of sources that were queried.
        error_sources: List of sources that encountered errors.
    """

    jobs: list[dict[str, Any]]
    total_discovered: int
    sources_queried: list[str]
    error_sources: list[str] = field(default_factory=list)


# =============================================================================
# Trigger Detection Functions
# =============================================================================


def check_trigger_conditions(
    next_poll_at: datetime | None,
    user_message: str | None,
    previous_sources: list[str],
    current_sources: list[str],
) -> DiscoveryTrigger | None:
    """Check all trigger conditions and return the active trigger.

    REQ-007 §6.1: Trigger conditions for Scouter Agent.

    Priority order (highest to lowest):
    1. MANUAL - User explicitly requested discovery
    2. SOURCE_ADDED - User enabled a new source
    3. SCHEDULED - Poll time has passed

    Args:
        next_poll_at: Scheduled time for next poll (None if never polled).
        user_message: User's message (None if no message).
        previous_sources: Previously enabled source names.
        current_sources: Currently enabled source names.

    Returns:
        DiscoveryTrigger if any condition is met, None otherwise.
    """
    # WHY: Manual trigger takes priority because user explicitly requested
    if user_message and is_manual_refresh_request(user_message):
        return DiscoveryTrigger(
            trigger_type=TriggerType.MANUAL,
            user_message=user_message,
        )

    # WHY: Source added is immediate trigger
    if is_source_added_trigger(previous_sources, current_sources):
        return DiscoveryTrigger(
            trigger_type=TriggerType.SOURCE_ADDED,
            previous_sources=previous_sources,
            current_sources=current_sources,
        )

    # WHY: Scheduled poll is lowest priority
    if should_poll(next_poll_at):
        return DiscoveryTrigger(
            trigger_type=TriggerType.SCHEDULED,
            next_poll_at=next_poll_at,
        )

    return None


def should_run_discovery(trigger: DiscoveryTrigger | None) -> bool:
    """Check if discovery should run based on trigger.

    Args:
        trigger: Detected trigger or None.

    Returns:
        True if discovery should run, False otherwise.
    """
    return trigger is not None


# =============================================================================
# Result Formatting Functions
# =============================================================================


def format_discovery_results(
    jobs: list[dict[str, Any]],
    sources_queried: list[str],
    error_sources: list[str],
) -> DiscoveryResult:
    """Format discovery results for presentation.

    REQ-003 §13.1: Present matches sorted by Fit Score.

    Args:
        jobs: List of discovered jobs (unsorted).
        sources_queried: List of sources that were queried.
        error_sources: List of sources that had errors.

    Returns:
        DiscoveryResult with jobs sorted by fit_score descending.
    """
    # WHY: Sort by fit_score descending. Jobs without fit_score sort to end (0).
    sorted_jobs = sorted(
        jobs,
        key=lambda j: j.get("fit_score") or 0,
        reverse=True,
    )

    return DiscoveryResult(
        jobs=sorted_jobs,
        total_discovered=len(jobs),
        sources_queried=sources_queried,
        error_sources=error_sources,
    )


# =============================================================================
# Workflow Execution
# =============================================================================


async def run_discovery(
    db: AsyncSession,
    user_id: UUID,
    persona_id: UUID,
    enabled_sources: list[str],
    trigger: DiscoveryTrigger | None,
    polling_frequency: str = "daily",
) -> DiscoveryResult:
    """Run the full discovery workflow.

    REQ-003 §13.1 + REQ-016 §6.2: Discovery Flow.

    Orchestrates:
    1. Check if discovery should run based on trigger
    2. Invoke JobFetchService pipeline (fetch, merge, pool, enrich, save)
    3. Format and return results sorted by Fit Score

    Args:
        db: Async database session.
        user_id: The user's UUID.
        persona_id: The persona's UUID.
        enabled_sources: List of enabled source names.
        trigger: Detected trigger (or None to skip discovery).
        polling_frequency: "twice_daily", "daily", or "weekly".

    Returns:
        DiscoveryResult with discovered jobs sorted by fit_score.
    """
    # WHY: Early return if no trigger - avoid unnecessary service execution
    if not should_run_discovery(trigger):
        return DiscoveryResult(
            jobs=[],
            total_discovered=0,
            sources_queried=enabled_sources,
            error_sources=[],
        )

    # Run the fetch pipeline via JobFetchService
    service = JobFetchService(db=db, user_id=user_id, persona_id=persona_id)
    poll_result = await service.run_poll(
        enabled_sources=enabled_sources,
        polling_frequency=polling_frequency,
    )

    # Format and return results
    return format_discovery_results(
        jobs=poll_result.processed_jobs,
        sources_queried=enabled_sources,
        error_sources=poll_result.error_sources,
    )
