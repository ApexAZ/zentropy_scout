"""Scouter Agent LangGraph graph implementation.

REQ-007 §15.3 + REQ-015 §10: Graph Spec — Scouter Agent

LangGraph graph that orchestrates job discovery into the shared pool:
    [Trigger] → get_enabled_sources → fetch_sources →
        → merge_results → check_shared_pool → [conditional] →
            ├─ has_new_jobs → extract_skills → calculate_ghost_score →
            │     → save_to_pool → notify_surfacing_worker →
            │       invoke_strategist → update_poll_state → END
            └─ no_new_jobs → update_poll_state → END

Node Functions:
    - get_enabled_sources: Load user's enabled job sources
    - fetch_sources: Fetch jobs from each source (parallel via asyncio)
    - merge_results: Combine jobs from all sources
    - check_shared_pool: Check pool + create links for existing jobs
    - extract_skills: Extract skills/culture via LLM (Haiku)
    - calculate_ghost_score: Calculate ghost score for each job
    - save_to_pool: Save new jobs to shared pool + create persona links
    - notify_surfacing_worker: Signal that new jobs are available
    - invoke_strategist: Trigger Strategist for scoring
    - update_poll_state: Update polling timestamps
"""

import hashlib
import logging
import uuid
from datetime import UTC, date, datetime
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy import select

from app.adapters.sources.adzuna import AdzunaAdapter
from app.adapters.sources.base import JobSourceAdapter, SearchParams
from app.adapters.sources.remoteok import RemoteOKAdapter
from app.adapters.sources.themuse import TheMuseAdapter
from app.adapters.sources.usajobs import USAJobsAdapter
from app.agents.scouter import (
    calculate_next_poll_time,
    merge_results,
)
from app.agents.state import ScouterState
from app.core.database import async_session_factory
from app.core.llm_sanitization import sanitize_llm_input
from app.models.job_source import JobSource
from app.repositories.job_posting_repository import JobPostingRepository
from app.services.ghost_detection import calculate_ghost_score
from app.services.global_dedup_service import deduplicate_and_save
from app.services.scouter_errors import SourceError, is_retryable_error

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# WHY: Default polling frequency when not specified by user
_DEFAULT_POLLING_FREQUENCY = "daily"

# WHY: Max characters to send to LLM for skill extraction per REQ-007 §6.4
_MAX_DESCRIPTION_LENGTH = 15000

# WHY: Only auto-create JobSource rows for known adapters — prevents
# untrusted source names from polluting the job_sources table.
_KNOWN_SOURCE_NAMES = frozenset({"Adzuna", "RemoteOK", "TheMuse", "USAJobs"})


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
    truncated = description[:_MAX_DESCRIPTION_LENGTH]

    # REQ-015 §8.4: Sanitize on read — all pool content through
    # sanitize_llm_input() before any LLM prompt
    truncated = sanitize_llm_input(truncated)

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
# Helpers
# =============================================================================


def _compute_description_hash(text: str) -> str:
    """Compute SHA-256 hash of description text for dedup lookup."""
    return hashlib.sha256(text.encode()).hexdigest()


def _build_dedup_job_data(
    job: dict[str, Any],
    source_id: uuid.UUID,
) -> dict[str, Any]:
    """Transform a Scouter job dict into global dedup service input format.

    Args:
        job: Raw job dict from Scouter state.
        source_id: Resolved UUID of the job source.

    Returns:
        Dict compatible with deduplicate_and_save() job_data parameter.
    """
    description = job.get("description", "")
    return {
        "source_id": source_id,
        "job_title": job.get("title", ""),
        "company_name": job.get("company", ""),
        "description": description,
        "description_hash": _compute_description_hash(description),
        "first_seen_date": date.today(),
        "external_id": job.get("external_id"),
        "source_url": job.get("source_url"),
        "location": job.get("location"),
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "posted_date": job.get("posted_date"),
        "culture_text": job.get("culture_text"),
        "ghost_score": job.get("ghost_score"),
        "ghost_signals": job.get("ghost_signals"),
        "raw_text": job.get("description"),
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

    discovered_jobs_by_source: dict[str, list[dict[str, Any]]] = {}

    params = SearchParams(
        keywords=["software", "engineer"],
        remote_only=False,
        results_per_page=25,
    )

    for source_name in enabled_sources:
        adapter = get_source_adapter(source_name)
        if not adapter:
            logger.warning("Unknown source adapter: %s", source_name)
            continue

        try:
            raw_jobs = await adapter.fetch_jobs(params)

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
            logger.warning(
                "Source %s failed: %s (retryable: %s)",
                source_name,
                str(e),
                is_retryable_error(e),
            )
            error_sources.append(source_name)

        except Exception as e:  # noqa: BLE001
            logger.exception("Unexpected error fetching from %s: %s", source_name, e)
            error_sources.append(source_name)

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

    merged = merge_results(discovered) if isinstance(discovered, dict) else discovered

    return {
        **state,
        "discovered_jobs": merged,
    }


async def _check_single_job_in_pool(
    db: Any,  # AsyncSession
    job: dict[str, Any],
    source_id: uuid.UUID,
) -> tuple[bool, dict[str, Any]]:
    """Check if a single job exists in the shared pool.

    Two-tier lookup: source_id + external_id first, then description_hash.

    Args:
        db: Async database session.
        job: Job dict with external_id and description.
        source_id: Resolved source UUID.

    Returns:
        (is_existing, enriched_job) where enriched_job has source_id
        and optionally pool_job_posting_id if found in pool.
    """
    external_id = job.get("external_id", "")

    # Tier 1: source_id + external_id
    existing = None
    if external_id:
        existing = await JobPostingRepository.get_by_source_and_external_id(
            db, source_id=source_id, external_id=external_id
        )

    # Tier 2: description_hash
    if existing is None:
        description = job.get("description", "")
        if description:
            desc_hash = _compute_description_hash(description)
            existing = await JobPostingRepository.get_by_description_hash(db, desc_hash)

    if existing is not None:
        logger.debug(
            "Job %s from %s already in pool (id=%s)",
            external_id,
            job.get("source_name", ""),
            existing.id,
        )
        return True, {
            **job,
            "pool_job_posting_id": str(existing.id),
            "source_id": str(source_id),
        }

    return False, {**job, "source_id": str(source_id)}


async def check_shared_pool_node(state: ScouterState) -> ScouterState:
    """Check which fetched jobs already exist in the shared pool.

    REQ-015 §10.1 + §10.3: Replaces deduplicate_jobs.

    For each discovered job:
    - In-batch dedup first (same source_name + external_id)
    - Check pool by source_id + external_id, then by description_hash
    - If found → add to existing_pool_jobs (skip extraction)
    - If not found → add to processed_jobs (needs extraction)

    Existing pool jobs get persona_jobs links created in save_to_pool.

    Args:
        state: State with discovered_jobs list.

    Returns:
        State with processed_jobs (new) and existing_pool_jobs (found).
    """
    discovered = state.get("discovered_jobs", [])

    processed: list[dict[str, Any]] = []
    existing_pool: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    source_id_cache: dict[str, uuid.UUID] = {}

    async with async_session_factory() as db:
        for job in discovered:
            source_name = job.get("source_name", "")
            external_id = job.get("external_id", "")

            # In-batch dedup: skip duplicates within the same fetch
            key = (source_name, external_id)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Resolve source_name → source_id (cached per source)
            if source_name not in source_id_cache:
                resolved = await _resolve_source_id(db, source_name)
                if resolved is None:
                    processed.append(job)
                    continue
                source_id_cache[source_name] = resolved

            source_id = source_id_cache[source_name]
            is_existing, enriched_job = await _check_single_job_in_pool(
                db, job, source_id
            )

            if is_existing:
                existing_pool.append(enriched_job)
            else:
                processed.append(enriched_job)

    logger.info(
        "Pool check: %d existing, %d new (from %d discovered)",
        len(existing_pool),
        len(processed),
        len(discovered),
    )

    return {
        **state,
        "processed_jobs": processed,
        "existing_pool_jobs": existing_pool,
    }


async def _resolve_source_id(
    db: Any,  # AsyncSession
    source_name: str,
) -> uuid.UUID | None:
    """Look up or create a JobSource by name.

    Only auto-creates sources for names in _KNOWN_SOURCE_NAMES to prevent
    untrusted input from creating arbitrary source rows.

    Args:
        db: Async database session.
        source_name: Source name (e.g., "Adzuna").

    Returns:
        UUID of the source, or None if unknown and not in allowlist.
    """
    result = await db.execute(
        select(JobSource).where(JobSource.source_name == source_name)
    )
    source = result.scalar_one_or_none()
    if source is not None:
        return source.id  # type: ignore[no-any-return]

    # Only auto-create for known adapter sources
    if source_name not in _KNOWN_SOURCE_NAMES:
        logger.warning("Unknown source name, cannot auto-create: %s", source_name)
        return None

    source = JobSource(
        source_name=source_name,
        source_type="API",
        description=f"Jobs from {source_name}",
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return source.id


def check_new_jobs(state: ScouterState) -> str:
    """Route based on whether new jobs were found.

    REQ-007 §15.3: Conditional edge after pool check.

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

        except Exception as e:  # noqa: BLE001
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
            signals = await calculate_ghost_score(
                posted_date=None,
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

        except Exception as e:  # noqa: BLE001
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


async def _save_single_job(
    db: Any,  # AsyncSession
    job: dict[str, Any],
    persona_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str | None:
    """Save a single new job to the shared pool.

    Args:
        db: Async database session.
        job: Job dict with source_id and dedup-ready fields.
        persona_id: Persona UUID for the persona_jobs link.
        user_id: User UUID for ownership.

    Returns:
        Job posting ID string, or None on failure.
    """
    try:
        source_id = uuid.UUID(job["source_id"])
        job_data = _build_dedup_job_data(job, source_id)
        outcome = await deduplicate_and_save(
            db,
            job_data=job_data,
            persona_id=persona_id,
            user_id=user_id,
            discovery_method="scouter",
        )
        logger.debug(
            "Saved job %s: action=%s, id=%s",
            job.get("external_id"),
            outcome.action,
            outcome.job_posting.id,
        )
        return str(outcome.job_posting.id)
    except (ValueError, KeyError) as e:
        logger.warning("Invalid job data for %s: %s", job.get("external_id"), e)
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to save job %s: %s", job.get("external_id"), e)
        return None


async def _link_existing_job(
    db: Any,  # AsyncSession
    job: dict[str, Any],
    persona_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str | None:
    """Create persona_jobs link for an existing pool job.

    Args:
        db: Async database session.
        job: Job dict with pool_job_posting_id and source_id.
        persona_id: Persona UUID for the persona_jobs link.
        user_id: User UUID for ownership.

    Returns:
        Pool job posting ID string, or None on failure.
    """
    try:
        source_id = uuid.UUID(job["source_id"])
        job_data = _build_dedup_job_data(job, source_id)
        await deduplicate_and_save(
            db,
            job_data=job_data,
            persona_id=persona_id,
            user_id=user_id,
            discovery_method="scouter",
        )
        return job.get("pool_job_posting_id")
    except (ValueError, KeyError) as e:
        logger.warning(
            "Invalid data for pool job %s: %s",
            job.get("pool_job_posting_id"),
            e,
        )
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Failed to link pool job %s: %s",
            job.get("pool_job_posting_id"),
            e,
        )
        return None


async def save_to_pool_node(state: ScouterState) -> ScouterState:
    """Save new jobs to shared pool and create persona_jobs links.

    REQ-015 §10.1: Replaces save_jobs. Saves to shared job_postings
    table, then creates persona_jobs link for the discovering user.
    Also creates links for existing pool jobs found in check_shared_pool.

    Uses deduplicate_and_save() for race condition handling (UNIQUE
    constraint + savepoint recovery per REQ-015 §10.3).

    Args:
        state: State with processed_jobs and existing_pool_jobs.

    Returns:
        State with saved_job_ids list.
    """
    user_id_str = state.get("user_id", "")
    persona_id_str = state.get("persona_id", "")
    processed = state.get("processed_jobs", [])
    existing_pool = state.get("existing_pool_jobs", [])

    if not user_id_str or not persona_id_str:
        logger.warning("Missing user_id or persona_id in state")
        return {**state, "saved_job_ids": []}

    try:
        user_id = uuid.UUID(str(user_id_str))
        persona_id = uuid.UUID(str(persona_id_str))
    except ValueError:
        logger.warning("Invalid user_id or persona_id UUID format")
        return {**state, "saved_job_ids": []}

    saved_ids: list[str] = []

    async with async_session_factory() as db:
        for job in processed:
            job_id = await _save_single_job(db, job, persona_id, user_id)
            if job_id:
                saved_ids.append(job_id)

        for job in existing_pool:
            job_id = await _link_existing_job(db, job, persona_id, user_id)
            if job_id:
                saved_ids.append(job_id)

        try:
            await db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to commit pool save transaction")
            return {**state, "saved_job_ids": []}

    logger.info(
        "Pool save: %d new + %d existing = %d total",
        len(processed),
        len(existing_pool),
        len(saved_ids),
    )

    return {
        **state,
        "saved_job_ids": saved_ids,
    }


def notify_surfacing_worker_node(state: ScouterState) -> ScouterState:
    """Signal the pool surfacing worker that new jobs are available.

    REQ-015 §10.1: Triggers background surfacing for cross-user matching.

    The surfacing worker runs on a 15-minute interval and will pick up
    new jobs automatically. This node logs the event for observability.

    Args:
        state: State with saved_job_ids list.

    Returns:
        State unchanged.
    """
    saved_ids = state.get("saved_job_ids", [])
    if saved_ids:
        logger.info(
            "Surfacing notification: %d jobs available for cross-user matching",
            len(saved_ids),
        )

    return state


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
    frequency = state.get("polling_frequency", _DEFAULT_POLLING_FREQUENCY)
    now = datetime.now(UTC)
    next_poll = calculate_next_poll_time(now, frequency)

    return {
        **state,
        "last_polled_at": now,
        "next_poll_at": next_poll,
    }


# =============================================================================
# Graph Construction (REQ-007 §15.3 + REQ-015 §10)
# =============================================================================


def create_scouter_graph() -> StateGraph:
    """Create the Scouter Agent LangGraph graph.

    REQ-007 §15.3 + REQ-015 §10.1: Updated graph spec.

    Graph structure:
        get_enabled_sources → fetch_sources → merge_results →
        check_shared_pool → [conditional] →
            ├─ has_new_jobs → extract_skills → calculate_ghost_score →
            │     → save_to_pool → notify_surfacing_worker →
            │       invoke_strategist → update_poll_state → END
            └─ no_new_jobs → update_poll_state → END

    Returns:
        Configured StateGraph (not compiled).
    """
    graph = StateGraph(ScouterState)

    # Add nodes
    graph.add_node("get_enabled_sources", get_enabled_sources_node)
    graph.add_node("fetch_sources", fetch_sources_node)
    graph.add_node("merge_results", merge_results_node)
    graph.add_node("check_shared_pool", check_shared_pool_node)
    graph.add_node("extract_skills", extract_skills_node)
    graph.add_node("calculate_ghost_score", calculate_ghost_score_node)
    graph.add_node("save_to_pool", save_to_pool_node)
    graph.add_node("notify_surfacing_worker", notify_surfacing_worker_node)
    graph.add_node("invoke_strategist", invoke_strategist_node)
    graph.add_node("update_poll_state", update_poll_state_node)

    # Set entry point
    graph.set_entry_point("get_enabled_sources")

    # Linear flow: sources → fetch → merge → pool check
    graph.add_edge("get_enabled_sources", "fetch_sources")
    graph.add_edge("fetch_sources", "merge_results")
    graph.add_edge("merge_results", "check_shared_pool")

    # Conditional: check for new-to-pool jobs
    graph.add_conditional_edges(
        "check_shared_pool",
        check_new_jobs,
        {
            "has_new_jobs": "extract_skills",
            "no_new_jobs": "update_poll_state",
        },
    )

    # Processing pipeline (only if new jobs)
    graph.add_edge("extract_skills", "calculate_ghost_score")
    graph.add_edge("calculate_ghost_score", "save_to_pool")
    graph.add_edge("save_to_pool", "notify_surfacing_worker")
    graph.add_edge("notify_surfacing_worker", "invoke_strategist")
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
