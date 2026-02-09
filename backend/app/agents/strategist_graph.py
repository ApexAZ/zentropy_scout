"""Strategist Agent LangGraph graph implementation.

REQ-007 §7: Strategist Agent — Applies scoring to discovered jobs.
REQ-007 §15.4: Graph Spec — Strategist Agent

10-node graph processing one job per invocation:

    load_persona_embeddings → check_embedding_freshness → [is_embedding_stale]
        ├─ "stale" → regenerate_embeddings → filter_non_negotiables
        └─ "fresh" → filter_non_negotiables

    filter_non_negotiables → [check_non_negotiables_pass]
        ├─ "pass" → generate_job_embeddings → calculate_fit_score →
        │           calculate_stretch_score → generate_rationale → save_scores
        └─ "fail" → save_scores

    save_scores → [check_auto_draft_threshold]
        ├─ "above_threshold" → trigger_ghostwriter → END
        └─ "below_threshold" → END

Architecture Decision: One Job Per Graph Invocation
    The filter_non_negotiables node has a binary conditional edge ("pass" → scoring
    pipeline, "fail" → save_scores). This only works for a single job. The score_jobs()
    convenience function loops and invokes the graph once per job.

Triggers (REQ-007 §7.1):
    - New job discovered by Scouter
    - Persona updated (triggers embedding regeneration)
    - Manual request ("Re-analyze job 123")
"""

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.state import ScoreResult, StrategistState

logger = logging.getLogger(__name__)


# =============================================================================
# Node Functions
# =============================================================================


def load_persona_embeddings_node(
    state: StrategistState,
) -> StrategistState:
    """Load persona embedding vectors.

    REQ-007 §15.4: Entry point — loads persona embeddings for scoring.

    Note: Placeholder. Actual implementation will fetch embeddings from the
    persona_embedding_generator service or cache.

    Args:
        state: State with persona_id.

    Returns:
        State with persona_embeddings dict populated.
    """
    persona_id = state.get("persona_id")
    logger.info("Loading persona embeddings for %s", persona_id)

    return {
        **state,
        "persona_embeddings": state.get("persona_embeddings", {}),
    }


def check_embedding_freshness_node(
    state: StrategistState,
) -> StrategistState:
    """Check if persona embeddings are fresh.

    REQ-007 §15.4: Prevents cold start problem by detecting stale embeddings.

    When Persona data changes, embeddings become stale. This node checks
    the embedding version against the persona's current version.

    Note: Placeholder version comparison. Actual implementation will fetch
    current version from the database.

    Args:
        state: State with persona_id and persona_embedding_version.

    Returns:
        State with embeddings_stale flag set.
    """
    state_version = state.get("persona_embedding_version", 0)
    # Placeholder: would fetch current version from DB
    current_version = state_version

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


def regenerate_embeddings_node(
    state: StrategistState,
) -> StrategistState:
    """Regenerate persona embeddings.

    REQ-007 §15.4: Regenerate embeddings when persona data changes.

    Note: Placeholder. Actual implementation will call
    persona_embedding_generator to regenerate vectors.

    Args:
        state: State with persona_id and stale embeddings.

    Returns:
        State with updated persona_embedding_version and fresh flag.
    """
    persona_id = state.get("persona_id")
    logger.info("Regenerating embeddings for persona %s", persona_id)

    new_version = state.get("persona_embedding_version", 0) + 1

    return {
        **state,
        "persona_embedding_version": new_version,
        "embeddings_stale": False,
    }


def filter_non_negotiables_node(
    state: StrategistState,
) -> StrategistState:
    """Apply non-negotiables filter to current job.

    REQ-007 §15.4: Pass/fail gate. Jobs that fail skip the scoring pipeline
    and go directly to save_scores with a filter reason.

    Note: Placeholder. Actual implementation will use
    non_negotiables_filter.filter_job() service.

    Args:
        state: State with current_job_id and persona_id.

    Returns:
        State with non_negotiables_passed and non_negotiables_reason set.
    """
    job_id = state.get("current_job_id")
    logger.info("Filtering non-negotiables for job %s", job_id)

    # Placeholder: assume all jobs pass
    return {
        **state,
        "non_negotiables_passed": True,
        "non_negotiables_reason": None,
    }


def generate_job_embeddings_node(
    state: StrategistState,
) -> StrategistState:
    """Generate embedding vectors for the current job.

    REQ-007 §15.4: Creates job requirement and culture embedding vectors
    for similarity comparison with persona embeddings.

    Note: Placeholder. Actual implementation will use the embedding
    provider to generate vectors from job posting text.

    Args:
        state: State with current_job_id.

    Returns:
        State with job_embeddings dict populated.
    """
    job_id = state.get("current_job_id")
    logger.info("Generating embeddings for job %s", job_id)

    return {
        **state,
        "job_embeddings": state.get("job_embeddings", {}),
    }


def calculate_fit_score_node(
    state: StrategistState,
) -> StrategistState:
    """Calculate Fit Score for current job.

    REQ-007 §15.4: Weighted score from 5 components (hard skills 40%,
    soft skills 15%, experience 25%, role title 10%, logistics 10%).

    Note: Placeholder. Actual implementation will use batch_scoring
    service with persona and job embeddings.

    Args:
        state: State with persona_embeddings and job_embeddings.

    Returns:
        State with fit_result populated.
    """
    job_id = state.get("current_job_id")
    logger.info("Calculating fit score for job %s", job_id)

    return {
        **state,
        "fit_result": None,
    }


def calculate_stretch_score_node(
    state: StrategistState,
) -> StrategistState:
    """Calculate Stretch Score for current job.

    REQ-007 §15.4: Growth opportunity score from 3 components
    (target role 50%, target skills 40%, growth trajectory 10%).

    Note: Placeholder. Actual implementation will use stretch_score
    service with persona targets and job data.

    Args:
        state: State with persona_embeddings and job_embeddings.

    Returns:
        State with stretch_result populated.
    """
    job_id = state.get("current_job_id")
    logger.info("Calculating stretch score for job %s", job_id)

    return {
        **state,
        "stretch_result": None,
    }


def generate_rationale_node(
    state: StrategistState,
) -> StrategistState:
    """Generate human-readable rationale for scores.

    REQ-007 §15.4: LLM call (Sonnet) to produce 2-3 sentence explanation
    of why the job scored as it did.

    Note: Placeholder. Actual implementation will call the LLM provider
    with score components and job/persona context.

    Args:
        state: State with fit_result and stretch_result.

    Returns:
        State with rationale string populated.
    """
    job_id = state.get("current_job_id")
    logger.info("Generating rationale for job %s", job_id)

    return {
        **state,
        "rationale": None,
    }


_MAX_RATIONALE_LENGTH = 2000
"""Maximum length for rationale/summary text in score_details JSONB."""


def _build_score_details(
    fit_result: dict[str, Any] | None,
    stretch_result: dict[str, Any] | None,
    rationale: str | None,
) -> dict[str, Any] | None:
    """Build score_details JSONB payload from pipeline state.

    REQ-012 Appendix A.3: Assembles component breakdowns and explanation
    into a single dict for the score_details JSONB column.

    Args:
        fit_result: Fit score result with total, components, weights.
        stretch_result: Stretch score result with total, components, weights.
        rationale: LLM-generated explanation string (truncated to 2000 chars).

    Returns:
        Dict suitable for JSONB storage, or None if no score data.
    """
    if fit_result is None and stretch_result is None:
        return None

    summary = (rationale or "")[:_MAX_RATIONALE_LENGTH]

    return {
        "fit": fit_result,
        "stretch": stretch_result,
        "explanation": {
            "summary": summary,
            "strengths": [],
            "gaps": [],
            "stretch_opportunities": [],
            "warnings": [],
        },
    }


def save_scores_node(state: StrategistState) -> StrategistState:
    """Assemble and save ScoreResult for current job.

    REQ-007 §15.4: Persists scores via PATCH /job-postings/{id}.
    Handles both scored jobs (with scores) and filtered jobs (with reason).

    Args:
        state: State with scoring pipeline results or filter reason.

    Returns:
        State with score_result assembled from pipeline fields.
    """
    job_id = state.get("current_job_id", "")
    non_neg_passed = state.get("non_negotiables_passed", False)

    fit_result = state.get("fit_result")
    stretch_result = state.get("stretch_result")

    fit_score: float | None = None
    stretch_score: float | None = None

    if non_neg_passed and fit_result is not None:
        fit_score = fit_result.get("total")
    if non_neg_passed and stretch_result is not None:
        stretch_score = stretch_result.get("total")

    # REQ-012 Appendix A.3: Build score_details for frontend drill-down
    score_details: dict[str, Any] | None = None
    if non_neg_passed:
        score_details = _build_score_details(
            fit_result, stretch_result, state.get("rationale")
        )

    score_result: ScoreResult = {
        "job_posting_id": job_id,
        "fit_score": fit_score,
        "stretch_score": stretch_score,
        "explanation": state.get("rationale") if non_neg_passed else None,
        "filtered_reason": (
            state.get("non_negotiables_reason") if not non_neg_passed else None
        ),
        "score_details": score_details,
    }

    # Consistency check: score_details totals must match aggregate columns
    if score_details is not None and fit_score is not None:
        details_fit = (score_details.get("fit") or {}).get("total")
        if details_fit is not None and details_fit != fit_score:
            logger.warning(
                "Score consistency mismatch for job %s: "
                "fit_score=%s, details.fit.total=%s",
                job_id,
                fit_score,
                details_fit,
            )

    logger.info("Scores saved for job %s", job_id)
    logger.debug(
        "Score details for job %s: fit=%s, stretch=%s, filtered=%s",
        job_id,
        fit_score,
        stretch_score,
        score_result.get("filtered_reason"),
    )

    return {
        **state,
        "score_result": score_result,
    }


def trigger_ghostwriter_node(
    state: StrategistState,
) -> StrategistState:
    """Trigger Ghostwriter for auto-draft.

    REQ-007 §15.4: Invoked when fit_score >= persona.auto_draft_threshold.
    Triggers the Ghostwriter agent to generate resume/cover letter.

    Note: Placeholder. Actual implementation will invoke the Ghostwriter
    sub-graph when it is implemented (Phase 2.7).

    Args:
        state: State with score_result above auto-draft threshold.

    Returns:
        State unchanged (side effect: Ghostwriter invocation).
    """
    job_id = state.get("current_job_id")
    score_result = state.get("score_result")
    fit_score = score_result.get("fit_score") if score_result else None

    logger.info(
        "Triggering Ghostwriter for job %s (fit_score=%s)",
        job_id,
        fit_score,
    )

    return state


# =============================================================================
# Routing Functions (§15.4)
# =============================================================================


def is_embedding_stale(state: StrategistState) -> str:
    """Route based on embedding freshness.

    REQ-007 §15.4: Check if persona embeddings need regeneration.

    Args:
        state: State with embeddings_stale flag.

    Returns:
        "stale" if embeddings need regeneration, "fresh" otherwise.
    """
    if state.get("embeddings_stale", False):
        return "stale"
    return "fresh"


def check_non_negotiables_pass(state: StrategistState) -> str:
    """Route based on non-negotiables filter result.

    REQ-007 §15.4: Jobs that fail skip scoring and go to save_scores.

    Args:
        state: State with non_negotiables_passed flag.

    Returns:
        "pass" if job passed filter, "fail" otherwise.
    """
    if state.get("non_negotiables_passed", False):
        return "pass"
    return "fail"


def check_auto_draft_threshold(state: StrategistState) -> str:
    """Route based on auto-draft threshold.

    REQ-007 §15.4: Trigger Ghostwriter when fit_score >= threshold.

    Args:
        state: State with score_result and auto_draft_threshold.

    Returns:
        "above_threshold" if fit_score >= threshold, "below_threshold" otherwise.
    """
    threshold = state.get("auto_draft_threshold")
    if threshold is None:
        return "below_threshold"

    score_result = state.get("score_result")
    if score_result is None:
        return "below_threshold"

    fit_score = score_result.get("fit_score")
    if fit_score is None:
        return "below_threshold"

    if fit_score >= threshold:
        return "above_threshold"
    return "below_threshold"


# =============================================================================
# Graph Construction (§15.4)
# =============================================================================


def create_strategist_graph() -> StateGraph:
    """Create the Strategist Agent LangGraph graph.

    REQ-007 §15.4: 10-node graph for per-job scoring pipeline.

    Graph structure:
        load_persona_embeddings → check_embedding_freshness → [is_embedding_stale]
            ├─ "stale" → regenerate_embeddings → filter_non_negotiables
            └─ "fresh" → filter_non_negotiables

        filter_non_negotiables → [check_non_negotiables_pass]
            ├─ "pass" → generate_job_embeddings → calculate_fit_score →
            │           calculate_stretch_score → generate_rationale → save_scores
            └─ "fail" → save_scores

        save_scores → [check_auto_draft_threshold]
            ├─ "above_threshold" → trigger_ghostwriter → END
            └─ "below_threshold" → END

    Returns:
        Configured StateGraph (not compiled).
    """
    graph = StateGraph(StrategistState)

    # Add nodes (10 total)
    graph.add_node("load_persona_embeddings", load_persona_embeddings_node)
    graph.add_node("check_embedding_freshness", check_embedding_freshness_node)
    graph.add_node("regenerate_embeddings", regenerate_embeddings_node)
    graph.add_node("filter_non_negotiables", filter_non_negotiables_node)
    graph.add_node("generate_job_embeddings", generate_job_embeddings_node)
    graph.add_node("calculate_fit_score", calculate_fit_score_node)
    graph.add_node("calculate_stretch_score", calculate_stretch_score_node)
    graph.add_node("generate_rationale", generate_rationale_node)
    graph.add_node("save_scores", save_scores_node)
    graph.add_node("trigger_ghostwriter", trigger_ghostwriter_node)

    # Entry point
    graph.set_entry_point("load_persona_embeddings")

    # Embedding freshness check (prevents cold start problem)
    graph.add_edge("load_persona_embeddings", "check_embedding_freshness")
    graph.add_conditional_edges(
        "check_embedding_freshness",
        is_embedding_stale,
        {
            "stale": "regenerate_embeddings",
            "fresh": "filter_non_negotiables",
        },
    )
    graph.add_edge("regenerate_embeddings", "filter_non_negotiables")

    # Non-negotiables filter (early exit for failed jobs)
    graph.add_conditional_edges(
        "filter_non_negotiables",
        check_non_negotiables_pass,
        {
            "pass": "generate_job_embeddings",  # nosec B105 — graph routing, not a password
            "fail": "save_scores",
        },
    )

    # Scoring pipeline
    graph.add_edge("generate_job_embeddings", "calculate_fit_score")
    graph.add_edge("calculate_fit_score", "calculate_stretch_score")
    graph.add_edge("calculate_stretch_score", "generate_rationale")
    graph.add_edge("generate_rationale", "save_scores")

    # Auto-draft trigger
    graph.add_conditional_edges(
        "save_scores",
        check_auto_draft_threshold,
        {
            "above_threshold": "trigger_ghostwriter",
            "below_threshold": END,
        },
    )
    graph.add_edge("trigger_ghostwriter", END)

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


_MAX_SCORE_JOBS = 500
"""Maximum number of jobs to score in a single call to score_jobs()."""


async def score_jobs(
    user_id: str,
    persona_id: str,
    job_ids: list[str],
    persona_embedding_version: int | None = None,
    auto_draft_threshold: int | None = None,
) -> list[ScoreResult]:
    """Score a list of jobs for a persona.

    Invokes the Strategist graph once per job. The graph processes a single
    job per invocation because the non-negotiables filter has a binary
    conditional edge (pass/fail) that only works for one job at a time.

    Args:
        user_id: User ID for tenant isolation.
        persona_id: Persona to score against.
        job_ids: List of job posting IDs to score.
        persona_embedding_version: Optional embedding version for freshness check.
        auto_draft_threshold: Optional threshold for auto-draft triggering.

    Returns:
        List of ScoreResult with scores for each job.

    Raises:
        ValueError: If job_ids exceeds _MAX_SCORE_JOBS or if user_id/persona_id
            are empty.

    Example:
        >>> results = await score_jobs("user-1", "persona-1", ["job-1", "job-2"])
        >>> for r in results:
        ...     print(f"{r['job_posting_id']}: fit={r['fit_score']}")
    """
    if not job_ids:
        return []

    if not user_id or not persona_id:
        raise ValueError("user_id and persona_id are required")

    if len(job_ids) > _MAX_SCORE_JOBS:
        raise ValueError(
            f"Batch size {len(job_ids)} exceeds maximum of {_MAX_SCORE_JOBS}"
        )

    graph = get_strategist_graph()
    results: list[ScoreResult] = []

    for job_id in job_ids:
        initial_state: StrategistState = {
            "user_id": user_id,
            "persona_id": persona_id,
            "current_job_id": job_id,
            "persona_embedding_version": persona_embedding_version,
            "auto_draft_threshold": auto_draft_threshold,
        }

        final_state = await graph.ainvoke(initial_state)

        score_result = final_state.get("score_result")
        if score_result is not None:
            results.append(score_result)

    return results
