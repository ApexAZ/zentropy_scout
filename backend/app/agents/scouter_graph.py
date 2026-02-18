"""Scouter Agent LangGraph graph implementation.

REQ-007 §15.3: Graph Spec — Scouter Agent

LangGraph graph that orchestrates job discovery:
    [Trigger] → get_enabled_sources → fetch_sources →
        → merge_results → deduplicate_jobs → [conditional] →
            ├─ has_new_jobs → extract_skills → calculate_ghost_score →
            │     → save_jobs → invoke_strategist → update_poll_state → END
            └─ no_new_jobs → update_poll_state → END

Node Functions:
    - get_enabled_sources: Load user's enabled job sources
    - fetch_sources: Fetch jobs from each source (parallel via asyncio)
    - merge_results: Combine jobs from all sources
    - deduplicate_jobs: Remove duplicates using deduplication service
    - extract_skills: Extract skills/culture via LLM (Haiku)
    - calculate_ghost_score: Calculate ghost score for each job
    - save_jobs: Persist jobs via API
    - invoke_strategist: Trigger Strategist for scoring
    - update_poll_state: Update polling timestamps
"""

import logging
from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, StateGraph

from app.adapters.sources.adzuna import AdzunaAdapter
from app.adapters.sources.base import JobSourceAdapter, SearchParams
from app.adapters.sources.remoteok import RemoteOKAdapter
from app.adapters.sources.themuse import TheMuseAdapter
from app.adapters.sources.usajobs import USAJobsAdapter
from app.agents.base import get_agent_client
from app.agents.scouter import (
    calculate_next_poll_time,
    merge_results,
)
from app.agents.state import ScouterState
from app.services.ghost_detection import calculate_ghost_score
from app.services.scouter_errors import SourceError, is_retryable_error

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# WHY: Default polling frequency when not specified by user
DEFAULT_POLLING_FREQUENCY = "daily"

# WHY: Max characters to send to LLM for skill extraction per REQ-007 §6.4
MAX_DESCRIPTION_LENGTH = 15000


# =============================================================================
# Source Adapter Registry
# =============================================================================


def get_source_adapter(source_name: str) -> JobSourceAdapter | None:
    """Get the adapter instance for a source name.

    Args:
        source_name: Canonical source name (e.g., "Adzuna", "RemoteOK").

    Returns:
        Adapter instance or None if source unknown.
    """
    adapters: dict[str, type[JobSourceAdapter]] = {
        "Adzuna": AdzunaAdapter,
        "RemoteOK": RemoteOKAdapter,
        "TheMuse": TheMuseAdapter,
        "USAJobs": USAJobsAdapter,
    }

    adapter_class = adapters.get(source_name)
    if adapter_class:
        return adapter_class()
    return None


# =============================================================================
# Skill Extraction Service
# =============================================================================


def extract_skills_and_culture(
    description: str,
) -> dict[str, Any]:
    """Extract skills and culture text from job description.

    REQ-007 §6.4: Use LLM to extract required/preferred skills and culture signals.

    Args:
        description: Job description text (will be truncated to 15k chars).

    Returns:
        Dict with required_skills, preferred_skills, and culture_text.

    Note:
        This is a placeholder. Full implementation will use LLM provider.
        For now, returns empty extraction to allow graph testing.
    """
    # WHY: Truncate to 15k chars per REQ-007 §6.4 note
    truncated = description[:MAX_DESCRIPTION_LENGTH]

    # PLACEHOLDER: Actual LLM extraction will be implemented in a future task.
    # This allows the graph to function without LLM dependency for testing.
    logger.debug(
        "Skill extraction placeholder called (description length: %d)",
        len(truncated),
    )

    return {
        "required_skills": [],
        "preferred_skills": [],
        "culture_text": None,
    }


# =============================================================================
# Node Functions
# =============================================================================


def get_enabled_sources_node(state: ScouterState) -> ScouterState:
    """Load user's enabled job sources.

    REQ-007 §6.2: Step 1 - Get enabled sources.

    This node currently passes through the sources from state.
    In production, it would fetch from user_source_preferences via API.

    Args:
        state: Current scouter state with enabled_sources.

    Returns:
        State unchanged (sources already in state from trigger).
    """
    # WHY: In production, this would fetch from API:
    #   client = get_agent_client()
    #   prefs = await client.list_user_source_preferences(state["user_id"])
    #   return {**state, "enabled_sources": [p["source_name"] for p in prefs["data"]]}
    # For now, sources are passed in via state initialization.
    return state


async def fetch_sources_node(state: ScouterState) -> ScouterState:
    """Fetch jobs from all enabled sources.

    REQ-007 §6.2: Step 2 - Parallel fetch from sources.
    REQ-007 §6.7: Fail-forward - continue with other sources on error.

    Args:
        state: State with enabled_sources list.

    Returns:
        State with discovered_jobs dict keyed by source name.
    """
    enabled_sources = state.get("enabled_sources", [])
    error_sources = list(state.get("error_sources", []))

    # WHY: Use dict to track jobs by source for merge step
    discovered_jobs_by_source: dict[str, list[dict[str, Any]]] = {}

    # WHY: Search params would be derived from persona preferences via API.
    # Using placeholder values until persona integration is complete.
    params = SearchParams(
        keywords=["software", "engineer"],
        remote_only=False,
        results_per_page=25,
    )

    # Fetch from each source
    for source_name in enabled_sources:
        adapter = get_source_adapter(source_name)
        if not adapter:
            logger.warning("Unknown source adapter: %s", source_name)
            continue

        try:
            raw_jobs = await adapter.fetch_jobs(params)

            # Convert RawJob objects to dicts for state storage
            discovered_jobs_by_source[source_name] = [
                {
                    "external_id": job.external_id,
                    "title": job.title,
                    "company": job.company,
                    "description": job.description,
                    "source_url": job.source_url,
                    "location": job.location,
                    "salary_min": job.salary_min,
                    "salary_max": job.salary_max,
                    "posted_date": job.posted_date,
                    "source_name": source_name,
                }
                for job in raw_jobs
            ]

            logger.info(
                "Fetched %d jobs from %s",
                len(raw_jobs),
                source_name,
            )

        except SourceError as e:
            # WHY: Fail-forward per REQ-007 §6.7 - record error, continue
            logger.warning(
                "Source %s failed: %s (retryable: %s)",
                source_name,
                str(e),
                is_retryable_error(e),
            )
            error_sources.append(source_name)

        except Exception as e:
            # WHY: Catch unexpected errors (network issues, parsing failures, etc.)
            # to prevent full batch failure. Fail-forward per REQ-007 §6.7.
            logger.exception("Unexpected error fetching from %s: %s", source_name, e)
            error_sources.append(source_name)

    # Return updated state
    return {
        **state,
        "discovered_jobs": discovered_jobs_by_source,  # type: ignore[typeddict-item]
        "error_sources": error_sources,
    }


def merge_results_node(state: ScouterState) -> ScouterState:
    """Merge job results from multiple sources into single list.

    REQ-007 §6.2: Step 3 - Normalize to common schema.

    Args:
        state: State with discovered_jobs dict.

    Returns:
        State with discovered_jobs as flat list.
    """
    discovered: Any = state.get("discovered_jobs", {})

    # Handle both dict (from fetch) and list (already merged) formats
    merged = merge_results(discovered) if isinstance(discovered, dict) else discovered

    return {
        **state,
        "discovered_jobs": merged,
    }


def deduplicate_jobs_node(state: ScouterState) -> ScouterState:
    """Remove duplicate jobs using deduplication service.

    REQ-007 §6.6: Deduplication logic.

    Args:
        state: State with discovered_jobs list.

    Returns:
        State with processed_jobs (unique jobs only).
    """
    discovered = state.get("discovered_jobs", [])
    processed: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

    for job in discovered:
        # Create unique key (source + external_id)
        key = (job.get("source_name", ""), job.get("external_id", ""))

        if key in seen_keys:
            continue

        # WHY: Check against existing jobs in DB would happen here
        # For now, just dedupe within the batch
        # Full implementation would call: is_duplicate(job, existing_jobs)

        seen_keys.add(key)
        processed.append(job)

    return {
        **state,
        "processed_jobs": processed,
    }


def check_new_jobs(state: ScouterState) -> str:
    """Route based on whether new jobs were found.

    REQ-007 §15.3: Conditional edge after deduplication.

    Args:
        state: State with processed_jobs list.

    Returns:
        "has_new_jobs" or "no_new_jobs" for routing.
    """
    processed = state.get("processed_jobs", [])
    return "has_new_jobs" if len(processed) > 0 else "no_new_jobs"


def extract_skills_node(state: ScouterState) -> ScouterState:
    """Extract skills and culture from job descriptions.

    REQ-007 §6.4: LLM-based skill extraction.

    Args:
        state: State with processed_jobs list.

    Returns:
        State with processed_jobs enhanced with extracted skills.
    """
    processed = state.get("processed_jobs", [])
    enhanced: list[dict[str, Any]] = []

    for job in processed:
        description = job.get("description", "")

        try:
            extraction = extract_skills_and_culture(description)

            enhanced.append(
                {
                    **job,
                    "required_skills": extraction.get("required_skills", []),
                    "preferred_skills": extraction.get("preferred_skills", []),
                    "culture_text": extraction.get("culture_text"),
                }
            )

        except Exception as e:
            # WHY: Fail-forward - store job without skills, flag for retry
            logger.warning(
                "Skill extraction failed for job %s: %s",
                job.get("external_id"),
                e,
            )
            enhanced.append(
                {
                    **job,
                    "required_skills": [],
                    "preferred_skills": [],
                    "culture_text": None,
                    "extraction_failed": True,
                }
            )

    return {
        **state,
        "processed_jobs": enhanced,
    }


async def calculate_ghost_score_node(state: ScouterState) -> ScouterState:
    """Calculate ghost score for each job.

    REQ-007 §6.5: Ghost detection.

    Args:
        state: State with processed_jobs list.

    Returns:
        State with processed_jobs enhanced with ghost_score.
    """
    processed = state.get("processed_jobs", [])
    enhanced: list[dict[str, Any]] = []

    for job in processed:
        try:
            # Call ghost detection service
            signals = await calculate_ghost_score(
                posted_date=None,  # Would parse from job["posted_date"]
                first_seen_date=None,
                repost_count=0,
                salary_min=job.get("salary_min"),
                salary_max=job.get("salary_max"),
                application_deadline=job.get("application_deadline"),
                location=job.get("location"),
                seniority_level=job.get("seniority_level"),
                years_experience_min=job.get("years_experience_min"),
                description=job.get("description", ""),
            )

            enhanced.append(
                {
                    **job,
                    "ghost_score": signals.ghost_score,
                    "ghost_signals": signals.to_dict(),
                }
            )

        except Exception as e:
            # WHY: Fail-forward - continue without ghost score
            logger.warning(
                "Ghost score calculation failed for job %s: %s",
                job.get("external_id"),
                e,
            )
            enhanced.append(
                {
                    **job,
                    "ghost_score": None,
                    "ghost_signals": None,
                }
            )

    return {
        **state,
        "processed_jobs": enhanced,
    }


async def save_jobs_node(state: ScouterState) -> ScouterState:
    """Save processed jobs via API.

    REQ-007 §6.2: Step 5 - POST /job-postings.

    Args:
        state: State with processed_jobs list.

    Returns:
        State with saved_job_ids list.
    """
    user_id = state.get("user_id", "")
    processed = state.get("processed_jobs", [])
    saved_ids: list[str] = []

    client = get_agent_client()

    for job in processed:
        try:
            # Build job posting data
            job_data = {
                "url": job.get("source_url"),
                "raw_text": job.get("description"),
                "job_title": job.get("title"),
                "company_name": job.get("company"),
                "location": job.get("location"),
                "salary_min": job.get("salary_min"),
                "salary_max": job.get("salary_max"),
                "source_name": job.get("source_name"),
                "external_id": job.get("external_id"),
                "required_skills": job.get("required_skills", []),
                "preferred_skills": job.get("preferred_skills", []),
                "culture_text": job.get("culture_text"),
                "ghost_score": job.get("ghost_score"),
                "ghost_signals": job.get("ghost_signals"),
            }

            result = await client.create_job_posting(user_id, job_data)
            job_id = result.get("data", {}).get("id")
            if job_id:
                saved_ids.append(job_id)

        except Exception as e:
            # WHY: Log and continue - don't fail entire batch
            logger.warning(
                "Failed to save job %s: %s",
                job.get("external_id"),
                e,
            )

    return {
        **state,
        "saved_job_ids": saved_ids,
    }


def invoke_strategist_node(state: ScouterState) -> ScouterState:
    """Invoke Strategist agent for scoring saved jobs.

    REQ-007 §15.3: Sub-graph invocation.

    Note: This is a placeholder. Actual sub-graph invocation will be
    implemented when the Strategist agent is complete (Phase 2.6).

    Args:
        state: State with saved_job_ids list.

    Returns:
        State unchanged (placeholder).
    """
    # WHY: Placeholder for sub-graph invocation.
    # Will invoke Strategist graph with jobs_to_score = saved_job_ids
    saved_ids = state.get("saved_job_ids", [])
    if saved_ids:
        logger.info(
            "Would invoke Strategist for %d jobs (placeholder)",
            len(saved_ids),
        )

    return state


def update_poll_state_node(state: ScouterState) -> ScouterState:
    """Update polling timestamps after completion.

    REQ-007 §6.2: Step 7 - PATCH /polling-configuration.

    Args:
        state: State with polling_frequency.

    Returns:
        State with last_polled_at and next_poll_at updated.
    """
    frequency = state.get("polling_frequency", DEFAULT_POLLING_FREQUENCY)
    now = datetime.now(UTC)
    next_poll = calculate_next_poll_time(now, frequency)  # type: ignore[arg-type]

    # WHY: In production, would call API to persist:
    #   await client.update_polling_configuration(...)

    return {
        **state,
        "last_polled_at": now,
        "next_poll_at": next_poll,
    }


# =============================================================================
# Graph Construction (§15.3)
# =============================================================================


def create_scouter_graph() -> StateGraph:
    """Create the Scouter Agent LangGraph graph.

    REQ-007 §15.3: Graph Spec — Scouter Agent

    Graph structure:
        get_enabled_sources → fetch_sources → merge_results →
        deduplicate_jobs → [conditional] →
            ├─ has_new_jobs → extract_skills → calculate_ghost_score →
            │     → save_jobs → invoke_strategist → update_poll_state → END
            └─ no_new_jobs → update_poll_state → END

    Returns:
        Configured StateGraph (not compiled).
    """
    graph = StateGraph(ScouterState)

    # Add nodes
    graph.add_node("get_enabled_sources", get_enabled_sources_node)
    graph.add_node("fetch_sources", fetch_sources_node)
    graph.add_node("merge_results", merge_results_node)
    graph.add_node("deduplicate_jobs", deduplicate_jobs_node)
    graph.add_node("extract_skills", extract_skills_node)
    graph.add_node("calculate_ghost_score", calculate_ghost_score_node)
    graph.add_node("save_jobs", save_jobs_node)
    graph.add_node("invoke_strategist", invoke_strategist_node)
    graph.add_node("update_poll_state", update_poll_state_node)

    # Set entry point
    graph.set_entry_point("get_enabled_sources")

    # Linear flow: sources → fetch → merge → dedupe
    graph.add_edge("get_enabled_sources", "fetch_sources")
    graph.add_edge("fetch_sources", "merge_results")
    graph.add_edge("merge_results", "deduplicate_jobs")

    # Conditional: check for new jobs
    graph.add_conditional_edges(
        "deduplicate_jobs",
        check_new_jobs,
        {
            "has_new_jobs": "extract_skills",
            "no_new_jobs": "update_poll_state",
        },
    )

    # Processing pipeline (only if new jobs)
    graph.add_edge("extract_skills", "calculate_ghost_score")
    graph.add_edge("calculate_ghost_score", "save_jobs")
    graph.add_edge("save_jobs", "invoke_strategist")
    graph.add_edge("invoke_strategist", "update_poll_state")

    # End
    graph.add_edge("update_poll_state", END)

    return graph


# =============================================================================
# Singleton Graph Instance
# =============================================================================

_scouter_graph: StateGraph | None = None


def get_scouter_graph() -> StateGraph:
    """Get the compiled scouter graph.

    Returns a singleton compiled graph instance for use in the API.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    global _scouter_graph
    if _scouter_graph is None:
        _scouter_graph = create_scouter_graph().compile()  # type: ignore[assignment]
    return _scouter_graph  # type: ignore[return-value]


def reset_scouter_graph() -> None:
    """Reset the scouter graph singleton.

    Useful for testing to ensure clean state.
    """
    global _scouter_graph
    _scouter_graph = None
