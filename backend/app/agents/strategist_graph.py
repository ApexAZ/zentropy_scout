"""Strategist Agent LangGraph graph implementation.

REQ-007 §7: Strategist Agent — Applies scoring to discovered jobs.
REQ-007 §15.4: Graph Spec — Strategist Agent

LangGraph graph that orchestrates job scoring:
    [Trigger] → check_embeddings → [conditional] →
        ├─ stale → regenerate_embeddings → score_jobs_loop
        └─ fresh → score_jobs_loop

    score_jobs_loop:
        → filter_non_negotiables → [conditional] →
            ├─ passed → calculate_scores → update_job → [more_jobs?] →
            │     ├─ yes → score_jobs_loop
            │     └─ no → END
            └─ filtered → record_filtered → [more_jobs?] →
                  ├─ yes → score_jobs_loop
                  └─ no → END

Triggers (REQ-007 §7.1):
    - New job discovered by Scouter
    - Persona updated (triggers embedding regeneration)
    - Manual request ("Re-analyze job 123")
"""

import logging

from langgraph.graph import END, StateGraph

from app.agents.state import ScoreResult, StrategistState

logger = logging.getLogger(__name__)


# =============================================================================
# Node Functions
# =============================================================================


async def initialize_node(state: StrategistState) -> StrategistState:
    """Initialize state for scoring run.

    REQ-007 §7.1: Prepare state for scoring.

    Args:
        state: Initial state with user_id, persona_id, and jobs_to_score.

    Returns:
        State with initialized scored_jobs and filtered_jobs lists.
    """
    logger.info(
        "Strategist initialized for user %s with %d jobs",
        state.get("user_id"),
        len(state.get("jobs_to_score", [])),
    )

    return {
        **state,
        "scored_jobs": state.get("scored_jobs", []),
        "filtered_jobs": state.get("filtered_jobs", []),
    }


async def check_embeddings_node(state: StrategistState) -> StrategistState:
    """Check if persona embeddings are fresh.

    REQ-007 §7.1: Detect stale embeddings and flag for regeneration.

    When Persona data changes, embeddings become stale. This node checks
    the embedding version against the persona's current version.

    Args:
        state: State with persona_id and persona_embedding_version.

    Returns:
        State with embeddings_stale flag set.
    """
    # WHY: In production, would fetch current version from API:
    #   current_version = await client.get_persona_embedding_version(persona_id)
    # For now, assume embeddings are fresh (version check placeholder)
    state_version = state.get("persona_embedding_version", 0)
    current_version = state_version  # Placeholder - would fetch from DB

    embeddings_stale = state_version < current_version

    logger.debug(
        "Embedding check: state_version=%d, current_version=%d, stale=%s",
        state_version,
        current_version,
        embeddings_stale,
    )

    return {
        **state,
        "embeddings_stale": embeddings_stale,
    }


def route_by_embedding_freshness(state: StrategistState) -> str:
    """Route based on embedding freshness.

    Args:
        state: State with embeddings_stale flag.

    Returns:
        "regenerate_embeddings" if stale, "filter_and_score" otherwise.
    """
    if state.get("embeddings_stale", False):
        return "regenerate_embeddings"
    return "filter_and_score"


async def regenerate_embeddings_node(state: StrategistState) -> StrategistState:
    """Regenerate persona embeddings.

    REQ-007 §7.1: Regenerate embeddings when persona data changes.

    Args:
        state: State with persona_id.

    Returns:
        State with updated persona_embedding_version.
    """
    persona_id = state.get("persona_id")
    logger.info("Regenerating embeddings for persona %s", persona_id)

    # WHY: In production, would call API to regenerate:
    #   new_version = await client.regenerate_persona_embeddings(persona_id)
    # For now, increment version as placeholder
    new_version = state.get("persona_embedding_version", 0) + 1

    return {
        **state,
        "persona_embedding_version": new_version,
        "embeddings_stale": False,
    }


async def filter_and_score_node(state: StrategistState) -> StrategistState:
    """Filter non-negotiables and calculate scores for all jobs.

    REQ-007 §7.2-7.5: Complete scoring flow.

    This node:
    1. Applies non-negotiables filter to each job
    2. Calculates fit and stretch scores for passing jobs
    3. Records filter reasons for failing jobs

    Args:
        state: State with jobs_to_score.

    Returns:
        State with scored_jobs and filtered_jobs populated.
    """
    jobs_to_score = state.get("jobs_to_score", [])
    persona_id = state.get("persona_id")
    _user_id = state.get("user_id")  # Will be used for API calls in production

    if not jobs_to_score:
        logger.info("No jobs to score")
        return state

    logger.info("Scoring %d jobs for persona %s", len(jobs_to_score), persona_id)

    scored_jobs: list[ScoreResult] = []
    filtered_jobs: list[str] = []

    # WHY: In production, would batch process via services:
    #   1. Fetch persona and job data from API
    #   2. Apply non-negotiables filter
    #   3. Call batch_score_jobs for passing jobs
    #
    # For MVP, we process each job and populate placeholder scores
    # The actual scoring integration will use the services implemented
    # in Phase 2.5 (REQ-008)

    for job_id in jobs_to_score:
        # Placeholder: In production, would:
        # 1. Fetch job posting data
        # 2. Apply non_negotiables_filter.filter_job(persona, job)
        # 3. If passes, calculate scores via batch_scoring service

        # For now, create placeholder result
        # Real implementation will integrate with:
        # - app.services.non_negotiables_filter
        # - app.services.batch_scoring
        # - app.services.fit_score
        # - app.services.stretch_score

        result: ScoreResult = {
            "job_posting_id": job_id,
            "fit_score": None,  # Will be populated by scoring service
            "stretch_score": None,  # Will be populated by scoring service
            "explanation": None,  # Will be generated by LLM
            "filtered_reason": None,
        }

        # Placeholder: assume all jobs pass for now
        # Real implementation will check non-negotiables
        scored_jobs.append(result)

    logger.info(
        "Scoring complete: %d scored, %d filtered",
        len(scored_jobs),
        len(filtered_jobs),
    )

    return {
        **state,
        "scored_jobs": scored_jobs,
        "filtered_jobs": filtered_jobs,
    }


async def update_jobs_node(state: StrategistState) -> StrategistState:
    """Update job postings with calculated scores.

    REQ-007 §7.2: Step 5 - PATCH /job-postings/{id}.

    Args:
        state: State with scored_jobs.

    Returns:
        State unchanged (side effect: jobs updated via API).
    """
    scored_jobs = state.get("scored_jobs", [])

    if not scored_jobs:
        logger.info("No jobs to update")
        return state

    logger.info("Updating %d job postings with scores", len(scored_jobs))

    # WHY: In production, would call API to update each job:
    #   for result in scored_jobs:
    #       await client.update_job_posting(
    #           result["job_posting_id"],
    #           fit_score=result["fit_score"],
    #           stretch_score=result["stretch_score"],
    #           score_explanation=result["explanation"],
    #           failed_non_negotiables=result["filtered_reason"],
    #       )

    return state


# =============================================================================
# Graph Construction (§15.4)
# =============================================================================


def create_strategist_graph() -> StateGraph:
    """Create the Strategist Agent LangGraph graph.

    REQ-007 §15.4: Graph Spec — Strategist Agent

    Graph structure:
        initialize → check_embeddings → [conditional] →
            ├─ stale → regenerate_embeddings → filter_and_score → update_jobs → END
            └─ fresh → filter_and_score → update_jobs → END

    Returns:
        Configured StateGraph (not compiled).
    """
    graph = StateGraph(StrategistState)

    # Add nodes
    graph.add_node("initialize", initialize_node)
    graph.add_node("check_embeddings", check_embeddings_node)
    graph.add_node("regenerate_embeddings", regenerate_embeddings_node)
    graph.add_node("filter_and_score", filter_and_score_node)
    graph.add_node("update_jobs", update_jobs_node)

    # Set entry point
    graph.set_entry_point("initialize")

    # Linear flow: initialize → check_embeddings
    graph.add_edge("initialize", "check_embeddings")

    # Conditional: check embedding freshness
    graph.add_conditional_edges(
        "check_embeddings",
        route_by_embedding_freshness,
        {
            "regenerate_embeddings": "regenerate_embeddings",
            "filter_and_score": "filter_and_score",
        },
    )

    # After regeneration, proceed to scoring
    graph.add_edge("regenerate_embeddings", "filter_and_score")

    # After scoring, update jobs
    graph.add_edge("filter_and_score", "update_jobs")

    # End
    graph.add_edge("update_jobs", END)

    return graph


# =============================================================================
# Singleton Graph Instance
# =============================================================================

_strategist_graph: StateGraph | None = None


def get_strategist_graph() -> StateGraph:
    """Get the compiled strategist graph.

    Returns a singleton compiled graph instance for use in the API.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    global _strategist_graph
    if _strategist_graph is None:
        _strategist_graph = create_strategist_graph().compile()
    return _strategist_graph


def reset_strategist_graph() -> None:
    """Reset the strategist graph singleton.

    Useful for testing to ensure clean state.
    """
    global _strategist_graph
    _strategist_graph = None


# =============================================================================
# Convenience Functions
# =============================================================================


async def score_jobs(
    user_id: str,
    persona_id: str,
    job_ids: list[str],
    persona_embedding_version: int | None = None,
) -> list[ScoreResult]:
    """Score a list of jobs for a persona.

    Convenience function that invokes the Strategist graph.

    Args:
        user_id: User ID for tenant isolation.
        persona_id: Persona to score against.
        job_ids: List of job posting IDs to score.
        persona_embedding_version: Optional embedding version for freshness check.

    Returns:
        List of ScoreResult with scores for each job.

    Example:
        >>> results = await score_jobs("user-1", "persona-1", ["job-1", "job-2"])
        >>> for r in results:
        ...     print(f"{r['job_posting_id']}: fit={r['fit_score']}")
    """
    initial_state: StrategistState = {
        "user_id": user_id,
        "persona_id": persona_id,
        "jobs_to_score": job_ids,
        "persona_embedding_version": persona_embedding_version,
        "scored_jobs": [],
        "filtered_jobs": [],
    }

    graph = get_strategist_graph()
    final_state = await graph.ainvoke(initial_state)

    return final_state.get("scored_jobs", [])
