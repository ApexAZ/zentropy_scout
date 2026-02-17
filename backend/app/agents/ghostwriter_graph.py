"""Ghostwriter Agent LangGraph graph implementation.

REQ-007 §8: Ghostwriter Agent — Generates tailored application materials.
REQ-007 §15.5: Graph Spec — Ghostwriter Agent

9-node graph with duplicate prevention and conditional tailoring:

    check_existing_variant → [route_existing_variant]
        ├─ "none_exists" → select_base_resume
        ├─ "draft_exists" → handle_duplicate → END
        └─ "approved_exists" → handle_duplicate → END

    select_base_resume → evaluate_tailoring_need → [needs_tailoring]
        ├─ "needs_tailoring" → create_job_variant → select_achievement_stories
        └─ "no_tailoring" → select_achievement_stories

    select_achievement_stories → generate_cover_letter →
        check_job_still_active → [is_job_active]
        ├─ "active" → present_for_review → END
        └─ "expired" → present_for_review → END  (with warning)

Architecture Decision: Single Job Per Invocation
    The graph processes one job posting at a time. The generate_materials()
    convenience function handles input validation and invocation.

Triggers (REQ-007 §8.1):
    - Auto-draft: fit_score >= persona.auto_draft_threshold
    - Manual request: User says "Draft materials for this job"
    - Regeneration: User says "Try a different approach"
"""

import logging

from langgraph.graph import END, StateGraph

from app.agents.ghostwriter import TriggerType
from app.agents.state import (
    GeneratedContent,
    GhostwriterState,
    ScoredStoryDetail,
    TailoringAnalysis,
)
from app.schemas.prompt_params import JobContext, VoiceProfileData
from app.services.reasoning_explanation import ReasoningStory, format_agent_reasoning
from app.services.story_selection import select_achievement_stories
from app.services.tailoring_decision import evaluate_tailoring_need

_VALID_TRIGGER_TYPES = {t.value for t in TriggerType}

logger = logging.getLogger(__name__)


# =============================================================================
# Node Functions (§15.5)
# =============================================================================


def check_existing_variant_node(
    state: GhostwriterState,
) -> GhostwriterState:
    """Check for existing JobVariant to prevent duplicates.

    REQ-007 §8.2: Before generating, check for existing JobVariants.
    REQ-007 §10.4.2: Race condition prevention.

    Note: Placeholder. Actual implementation will query
    GET /job-variants?job_posting_id= to check for existing variants.

    Args:
        state: State with job_posting_id and optional existing_variant_id.

    Returns:
        State with existing_variant_status set (None, "draft", or "approved").
    """
    job_id = state.get("job_posting_id")
    existing_id = state.get("existing_variant_id")

    logger.info(
        "Checking existing variant for job %s (existing_id=%s)",
        job_id,
        existing_id,
    )

    # Placeholder: assume no existing variant
    return {
        **state,
        "existing_variant_status": None,
    }


def handle_duplicate_node(
    state: GhostwriterState,
) -> GhostwriterState:
    """Handle duplicate JobVariant scenario.

    REQ-007 §8.2: When an existing variant is found, inform the user
    with an appropriate message based on the variant's status.

    - Draft exists: "I'm already working on this. Want me to start fresh?"
    - Approved exists: "You already have an approved resume for this job."

    Args:
        state: State with existing_variant_status ("draft" or "approved").

    Returns:
        State with duplicate_message set.
    """
    status = state.get("existing_variant_status")
    job_id = state.get("job_posting_id")

    if status == "approved":
        message = "You already have an approved resume for this job."
    else:
        message = "I'm already working on this. Want me to start fresh?"

    logger.info(
        "Duplicate variant found for job %s (status=%s)",
        job_id,
        status,
    )

    return {
        **state,
        "duplicate_message": message,
    }


def select_base_resume_node(
    state: GhostwriterState,
) -> GhostwriterState:
    """Select the best base resume for the target job.

    REQ-007 §8.3: Match role_type to job, fall back to is_primary.

    Note: Placeholder. Actual implementation will fetch base resumes
    and match role_type to job title.

    Args:
        state: State with persona_id and job_posting_id.

    Returns:
        State with selected_base_resume_id populated.
    """
    persona_id = state.get("persona_id")
    job_id = state.get("job_posting_id")

    logger.info(
        "Selecting base resume for persona %s, job %s",
        persona_id,
        job_id,
    )

    # Placeholder: no selection yet
    return {
        **state,
        "selected_base_resume_id": None,
    }


def evaluate_tailoring_need_node(
    state: GhostwriterState,
) -> GhostwriterState:
    """Evaluate whether the base resume needs tailoring for this job.

    REQ-007 §8.4: Check keyword gaps, bullet relevance, summary alignment.
    REQ-010 §4.1: Calls the tailoring decision service with pre-extracted data.

    Currently invoked with empty keyword/skill sets. Real data will be provided
    once the API client and extraction functions (REQ-010 §6.x) are implemented.

    Args:
        state: State with selected_base_resume_id and job_posting_id.

    Returns:
        State with tailoring_needed bool and tailoring_analysis dict.
    """
    job_id = state.get("job_posting_id")
    resume_id = state.get("selected_base_resume_id")

    logger.info(
        "Evaluating tailoring need for job %s (resume=%s)",
        job_id,
        resume_id,
    )

    # Placeholder inputs — real data arrives when §6.x extraction is done
    decision = evaluate_tailoring_need(
        job_keywords=set(),
        summary_keywords=set(),
        bullet_skills=[],
        fit_score=0.0,
    )

    tailoring_analysis: TailoringAnalysis = {
        "action": decision.action,
        "signals": [
            {"type": s.type, "priority": s.priority, "detail": s.detail}
            for s in decision.signals
        ],
        "reasoning": decision.reasoning,
    }

    return {
        **state,
        "tailoring_needed": decision.action == "create_variant",
        "tailoring_analysis": tailoring_analysis,
    }


def create_job_variant_node(
    state: GhostwriterState,
) -> GhostwriterState:
    """Create a tailored JobVariant from the base resume.

    REQ-007 §8.4: Reorder bullets, adjust summary, highlight relevant skills.
    REQ-007 §15.5: LLM call for content generation.

    Note: Placeholder. Actual implementation will call the LLM to create
    a tailored version and POST /job-variants.

    Args:
        state: State with selected_base_resume_id and job_posting_id.

    Returns:
        State with generated_resume populated.
    """
    job_id = state.get("job_posting_id")
    resume_id = state.get("selected_base_resume_id")

    logger.info(
        "Creating job variant for job %s from resume %s",
        job_id,
        resume_id,
    )

    # Placeholder: no content generated yet
    return {
        **state,
        "generated_resume": None,
    }


def select_achievement_stories_node(
    state: GhostwriterState,
) -> GhostwriterState:
    """Select achievement stories for the cover letter.

    REQ-007 §8.6: Match stories to job requirements, prefer recent and
    quantified stories, avoid repetition from recent applications.

    Delegates to the story_selection service with pre-extracted data.
    Currently invoked with empty data; real data arrives when the API
    client and repository layer are wired to fetch persona stories,
    job skills, and recent application usage.

    Args:
        state: State with persona_id and job_posting_id.

    Returns:
        State with selected_stories list populated (story IDs).
    """
    persona_id = state.get("persona_id")
    job_id = state.get("job_posting_id")

    logger.info(
        "Selecting achievement stories for persona %s, job %s",
        persona_id,
        job_id,
    )

    # Placeholder inputs — real data arrives when API client is wired
    # to fetch persona.achievement_stories, job.extracted_skills, etc.
    scored = select_achievement_stories(
        stories=[],
        job_skills=set(),
    )

    story_details: list[ScoredStoryDetail] = [
        {"story_id": s.story_id, "title": s.title, "rationale": s.rationale}
        for s in scored
    ]

    return {
        **state,
        "selected_stories": [s.story_id for s in scored],
        "scored_story_details": story_details,
    }


async def generate_cover_letter_node(
    state: GhostwriterState,
) -> GhostwriterState:
    """Generate a cover letter with voice profile.

    REQ-007 §8.5: Apply voice profile, reference selected stories,
    align with job keywords. Uses Sonnet-tier model for writing quality.
    REQ-007 §15.5: LLM call (Sonnet).

    Calls the cover letter generation service with placeholder values for
    fields not yet populated (voice profile, persona details). Real data
    arrives when upstream nodes (§3.x voice profile, API client) are wired.

    Args:
        state: State with persona_id, job_posting_id, and selected_stories.

    Returns:
        State with generated_cover_letter populated as GeneratedContent dict.
    """
    # Lazy import to break circular dependency:
    # cover_letter_generation → ghostwriter_prompts → agents/__init__ → ghostwriter_graph
    from app.services.cover_letter_generation import generate_cover_letter

    job_id = state.get("job_posting_id")
    stories = state.get("selected_stories", [])

    logger.info(
        "Generating cover letter for job %s (stories=%d)",
        job_id,
        len(stories),
    )

    # Placeholder values — real data arrives when API client is wired
    result = await generate_cover_letter(
        applicant_name="",
        current_title="",
        job=JobContext(
            job_title="",
            company_name="",
            top_skills="",
            culture_signals="",
            description_excerpt="",
        ),
        voice=VoiceProfileData(
            tone="",
            sentence_style="",
            vocabulary_level="",
            personality_markers="",
            preferred_phrases="",
            things_to_avoid="",
            writing_sample="",
        ),
        stories=[],
        stories_used=stories,
    )

    generated: GeneratedContent = {
        "content": result.content,
        "reasoning": result.reasoning,
        "stories_used": result.stories_used,
    }

    return {
        **state,
        "generated_cover_letter": generated,
    }


def check_job_still_active_node(
    state: GhostwriterState,
) -> GhostwriterState:
    """Check if the target job posting is still active.

    REQ-007 §10.4.3: Handle expired job during draft scenario.
    REQ-007 §15.5: Check before presenting to user.

    Note: Placeholder. Actual implementation will query the job posting
    status from the API.

    Args:
        state: State with job_posting_id.

    Returns:
        State with job_active flag set.
    """
    job_id = state.get("job_posting_id")

    logger.info("Checking if job %s is still active", job_id)

    # Placeholder: assume job is still active
    return {
        **state,
        "job_active": True,
    }


def present_for_review_node(
    state: GhostwriterState,
) -> GhostwriterState:
    """Present generated materials for user review.

    REQ-007 §8.7: Show variant diff, cover letter draft, explain reasoning.
    REQ-010 §9: Builds combined reasoning explanation from tailoring and stories.
    Sets requires_human_input=True for HITL checkpoint.

    If the job has expired, adds a review_warning so the user knows.

    Args:
        state: State with generated content, scored story details, tailoring
            analysis, and job_active status.

    Returns:
        State with agent_reasoning, requires_human_input=True, and optional
        review_warning.
    """
    job_id = state.get("job_posting_id")
    job_active = state.get("job_active", True)

    logger.info("Presenting materials for review (job=%s)", job_id)

    review_warning: str | None = None
    if not job_active:
        review_warning = (
            "Note: This job posting appears to have expired. "
            "You can still review the materials, but the posting "
            "may no longer be accepting applications."
        )

    # Build reasoning explanation (REQ-010 §9)
    tailoring = state.get("tailoring_analysis")
    tailoring_action = tailoring["action"] if tailoring else "use_base"
    signal_details = [
        s["detail"] for s in (tailoring.get("signals", []) if tailoring else [])
    ]

    story_details = state.get("scored_story_details", [])
    reasoning_stories = [
        ReasoningStory(title=sd["title"], rationale=sd["rationale"])
        for sd in story_details
    ]

    # Placeholder job_title/company_name — real data arrives when API
    # client is wired to fetch job posting details into state.
    agent_reasoning = format_agent_reasoning(
        job_title="",
        company_name="",
        tailoring_action=tailoring_action,
        tailoring_signal_details=signal_details,
        stories=reasoning_stories,
    )

    return {
        **state,
        "requires_human_input": True,
        "review_warning": review_warning,
        "agent_reasoning": agent_reasoning,
    }


# =============================================================================
# Routing Functions (§15.5)
# =============================================================================


def route_existing_variant(state: GhostwriterState) -> str:
    """Route based on existing variant status.

    REQ-007 §8.2: Duplicate prevention routing.

    Args:
        state: State with existing_variant_status.

    Returns:
        "none_exists" if no variant, "draft_exists" or "approved_exists" otherwise.
    """
    status = state.get("existing_variant_status")
    if status is None:
        return "none_exists"
    if status == "draft":
        return "draft_exists"
    return "approved_exists"


def needs_tailoring(state: GhostwriterState) -> str:
    """Route based on tailoring evaluation result.

    REQ-007 §8.4: Check if BaseResume needs modification for this job.

    Args:
        state: State with tailoring_needed flag.

    Returns:
        "needs_tailoring" if tailoring needed, "no_tailoring" otherwise.
    """
    if state.get("tailoring_needed", False):
        return "needs_tailoring"
    return "no_tailoring"


def is_job_active(state: GhostwriterState) -> str:
    """Route based on job posting active status.

    REQ-007 §15.5: Both active and expired jobs proceed to present_for_review,
    but expired jobs get a warning message.

    Args:
        state: State with job_active flag.

    Returns:
        "active" if job is still active, "expired" otherwise.
    """
    if state.get("job_active", True):
        return "active"
    return "expired"


# =============================================================================
# Graph Construction (§15.5)
# =============================================================================


def create_ghostwriter_graph() -> StateGraph:
    """Create the Ghostwriter Agent LangGraph graph.

    REQ-007 §15.5: 9-node graph for content generation with duplicate prevention.

    Graph structure:
        check_existing_variant → [route_existing_variant]
            ├─ "none_exists" → select_base_resume
            ├─ "draft_exists" → handle_duplicate → END
            └─ "approved_exists" → handle_duplicate → END

        select_base_resume → evaluate_tailoring_need → [needs_tailoring]
            ├─ "needs_tailoring" → create_job_variant → select_achievement_stories
            └─ "no_tailoring" → select_achievement_stories

        select_achievement_stories → generate_cover_letter →
            check_job_still_active → [is_job_active]
            ├─ "active" → present_for_review → END
            └─ "expired" → present_for_review → END

    Returns:
        Configured StateGraph (not compiled).
    """
    graph = StateGraph(GhostwriterState)

    # Add nodes (9 total)
    graph.add_node("check_existing_variant", check_existing_variant_node)
    graph.add_node("handle_duplicate", handle_duplicate_node)
    graph.add_node("select_base_resume", select_base_resume_node)
    graph.add_node("evaluate_tailoring_need", evaluate_tailoring_need_node)
    graph.add_node("create_job_variant", create_job_variant_node)
    graph.add_node("select_achievement_stories", select_achievement_stories_node)
    graph.add_node("generate_cover_letter", generate_cover_letter_node)
    graph.add_node("check_job_still_active", check_job_still_active_node)
    graph.add_node("present_for_review", present_for_review_node)

    # Entry point
    graph.set_entry_point("check_existing_variant")

    # Duplicate prevention (critical! — REQ-007 §8.2, §10.4.2)
    graph.add_conditional_edges(
        "check_existing_variant",
        route_existing_variant,
        {
            "none_exists": "select_base_resume",
            "draft_exists": "handle_duplicate",
            "approved_exists": "handle_duplicate",
        },
    )
    graph.add_edge("handle_duplicate", END)

    # Generation flow
    graph.add_edge("select_base_resume", "evaluate_tailoring_need")
    graph.add_conditional_edges(
        "evaluate_tailoring_need",
        needs_tailoring,
        {
            "needs_tailoring": "create_job_variant",
            "no_tailoring": "select_achievement_stories",
        },
    )
    graph.add_edge("create_job_variant", "select_achievement_stories")
    graph.add_edge("select_achievement_stories", "generate_cover_letter")

    # Check job status before presenting (§15.5 spec has conditional edge;
    # both routes converge to present_for_review, but expired adds a warning)
    graph.add_edge("generate_cover_letter", "check_job_still_active")
    graph.add_conditional_edges(
        "check_job_still_active",
        is_job_active,
        {
            "active": "present_for_review",
            "expired": "present_for_review",
        },
    )
    graph.add_edge("present_for_review", END)

    return graph


# =============================================================================
# Singleton Graph Instance
# =============================================================================

_ghostwriter_graph: StateGraph | None = None


def get_ghostwriter_graph() -> StateGraph:
    """Get the compiled ghostwriter graph.

    Returns a singleton compiled graph instance for use in the API.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    global _ghostwriter_graph  # noqa: PLW0603
    if _ghostwriter_graph is None:
        _ghostwriter_graph = create_ghostwriter_graph().compile()  # type: ignore[assignment]
    return _ghostwriter_graph  # type: ignore[return-value]


def reset_ghostwriter_graph() -> None:
    """Reset the ghostwriter graph singleton.

    Useful for testing to ensure clean state.
    """
    global _ghostwriter_graph  # noqa: PLW0603
    _ghostwriter_graph = None


# =============================================================================
# Convenience Functions
# =============================================================================


async def generate_materials(
    user_id: str,
    persona_id: str,
    job_posting_id: str,
    trigger_type: str,
    feedback: str | None = None,
    existing_variant_id: str | None = None,
) -> GhostwriterState:
    """Generate tailored materials for a job posting.

    Invokes the Ghostwriter graph once for a single job. Validates inputs
    and constructs the initial state before graph invocation.

    Args:
        user_id: User ID for tenant isolation.
        persona_id: Persona to generate materials for.
        job_posting_id: Target job posting ID.
        trigger_type: How the Ghostwriter was triggered.
            Values: "auto_draft", "manual_request", "regeneration".
        feedback: User feedback for regeneration (only for "regeneration" trigger).
        existing_variant_id: Known existing variant ID for race condition prevention.

    Returns:
        Final GhostwriterState with generated_resume and generated_cover_letter.

    Raises:
        ValueError: If user_id, persona_id, or job_posting_id are empty.

    Example:
        >>> result = await generate_materials(
        ...     "user-1", "persona-1", "job-1", "manual_request"
        ... )
        >>> print(result.get("generated_cover_letter"))
    """
    if not user_id:
        raise ValueError("user_id is required")

    if not persona_id:
        raise ValueError("persona_id is required")

    if not job_posting_id:
        raise ValueError("job_posting_id is required")

    if trigger_type not in _VALID_TRIGGER_TYPES:
        raise ValueError(
            f"trigger_type must be one of {_VALID_TRIGGER_TYPES}, got {trigger_type!r}"
        )

    graph = get_ghostwriter_graph()

    initial_state: GhostwriterState = {
        "user_id": user_id,
        "persona_id": persona_id,
        "job_posting_id": job_posting_id,
        "trigger_type": trigger_type,
        "feedback": feedback,
        "existing_variant_id": existing_variant_id,
    }

    final_state = await graph.ainvoke(initial_state)  # type: ignore[attr-defined]

    return final_state  # type: ignore[no-any-return]
