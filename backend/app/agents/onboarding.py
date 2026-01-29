"""Onboarding Agent implementation.

REQ-007 §5: Onboarding Agent

The Onboarding Agent guides new users through persona creation via a structured
interview. It:
- Triggers for new users or incomplete onboarding
- Walks through interview steps (resume upload → basic info → work history → ...)
- Handles HITL checkpoints at each step
- Supports skipping optional sections
- Can be re-invoked for partial profile updates

Architecture:
    [Trigger] → check_resume_upload → gather_basic_info → gather_work_history →
        → gather_education → gather_skills → gather_certifications →
        → gather_stories → gather_non_negotiables → gather_growth_targets →
        → derive_voice_profile → review_persona → setup_base_resume →
        → complete_onboarding → [END]

    Each step pauses for HITL via wait_for_input node.

Interview Steps (§5.2):
    - resume_upload: Optional resume upload, extract data
    - basic_info: Name, email, phone, location, URLs
    - work_history: Confirm/expand extracted jobs
    - education: Optional education entries
    - skills: Rate proficiency, add missing
    - certifications: Optional certifications
    - achievement_stories: 3-5 STAR format stories
    - non_negotiables: Remote, salary, filters
    - growth_targets: Target roles, skills to learn
    - voice_profile: Derive writing style from conversation
    - review: User reviews gathered data
    - base_resume_setup: Create initial BaseResume
"""

import re

from langgraph.graph import END, StateGraph

from app.agents.state import CheckpointReason, OnboardingState

# =============================================================================
# Constants (§5.2)
# =============================================================================

# WHY: Ordered list defines the interview flow state machine. Each step must
# complete (or be skipped) before proceeding to the next.
ONBOARDING_STEPS = [
    "resume_upload",
    "basic_info",
    "work_history",
    "education",
    "skills",
    "certifications",
    "achievement_stories",
    "non_negotiables",
    "growth_targets",
    "voice_profile",
    "review",
    "base_resume_setup",
]

# WHY: These sections can be skipped by the user. Education and certifications
# are optional because not all users have formal education or certs. Resume upload
# is optional because users can provide all info via interview.
OPTIONAL_SECTIONS = {
    "resume_upload",
    "education",
    "certifications",
}

# WHY: Required fields for each step. Used to determine when a step is complete.
REQUIRED_FIELDS: dict[str, list[str]] = {
    "basic_info": ["full_name", "email", "phone", "location"],
    "work_history": ["entries"],  # At least 1 job entry
    "skills": ["skills"],  # At least 1 skill
    "achievement_stories": ["stories"],  # At least 1 story
    "non_negotiables": ["remote_preference"],  # At minimum
    "growth_targets": ["target_roles"],  # At minimum
    "voice_profile": ["tone"],  # At minimum
}

# Patterns for detecting update requests (§5.1)
UPDATE_REQUEST_PATTERNS = [
    re.compile(r"update\s+(?:my\s+)?(?:profile|info)", re.IGNORECASE),
    re.compile(
        r"(?:add|edit|change)\s+(?:my\s+)?(?:skills?|experience)", re.IGNORECASE
    ),
    re.compile(
        r"(?:add|edit|change)\s+(?:a\s+)?(?:new\s+)?(?:skill|job|story)", re.IGNORECASE
    ),
    re.compile(r"change\s+my\s+(?:salary|location|preferences)", re.IGNORECASE),
]


# =============================================================================
# Trigger Conditions (§5.1)
# =============================================================================


def should_start_onboarding(
    *,
    persona_exists: bool,
    onboarding_complete: bool,
) -> bool:
    """Check if onboarding should auto-start.

    REQ-007 §5.1: Trigger Conditions

    Triggers when:
    - New user (no persona exists)
    - User has persona but onboarding_complete is False (incomplete)

    Does NOT trigger when:
    - User has persona with onboarding_complete = True

    Args:
        persona_exists: Whether user has a persona record.
        onboarding_complete: Whether onboarding is marked complete.

    Returns:
        True if onboarding should start/resume.
    """
    # No persona → definitely need onboarding
    if not persona_exists:
        return True

    # Has persona but incomplete → resume
    return not onboarding_complete


def is_update_request(message: str) -> bool:
    """Check if a message is a profile update request.

    REQ-007 §5.1: Trigger Conditions

    Users can trigger partial re-interview by saying things like:
    - "Update my profile"
    - "Add a new skill"
    - "Change my salary requirement"

    Args:
        message: User's message text.

    Returns:
        True if message indicates an update request.
    """
    return any(pattern.search(message) for pattern in UPDATE_REQUEST_PATTERNS)


# =============================================================================
# Interview Flow (§5.2)
# =============================================================================


def get_next_step(current_step: str) -> str | None:
    """Get the next step in the onboarding flow.

    Args:
        current_step: Current step name.

    Returns:
        Next step name, or None if at the end.
    """
    try:
        current_index = ONBOARDING_STEPS.index(current_step)
        if current_index < len(ONBOARDING_STEPS) - 1:
            return ONBOARDING_STEPS[current_index + 1]
        return None
    except ValueError:
        return None


def is_step_optional(step: str) -> bool:
    """Check if a step can be skipped.

    Args:
        step: Step name.

    Returns:
        True if the step is optional.
    """
    return step in OPTIONAL_SECTIONS


# =============================================================================
# Step Behaviors (§5.3)
# =============================================================================


def gather_basic_info(state: OnboardingState) -> OnboardingState:
    """Gather basic contact information.

    REQ-007 §5.3.2: Basic Info Step

    Gathers: full_name, email, phone, location, linkedin_url, portfolio_url

    Args:
        state: Current onboarding state.

    Returns:
        Updated state with gathered data or HITL flags set.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    gathered = dict(state.get("gathered_data", {}))
    basic_info = gathered.get("basic_info", {})

    # Check if we have a response to process
    user_response = state.get("user_response")
    pending_question = state.get("pending_question")

    if user_response and pending_question:
        # Determine which field this response is for
        if "name" in pending_question.lower():
            basic_info["full_name"] = user_response
            # Ask for email next
            new_state[
                "pending_question"
            ] = "What's the best email for job applications?"
            new_state["user_response"] = None
        elif "email" in pending_question.lower():
            basic_info["email"] = user_response
            new_state["pending_question"] = "And your phone number?"
            new_state["user_response"] = None
        elif "phone" in pending_question.lower():
            basic_info["phone"] = user_response
            new_state[
                "pending_question"
            ] = "Where are you located? (City, State/Country)"
            new_state["user_response"] = None
        elif (
            "location" in pending_question.lower()
            or "located" in pending_question.lower()
        ):
            basic_info["location"] = user_response
            # Optional fields - we can ask or skip
            new_state["pending_question"] = None
            new_state["user_response"] = None

        gathered["basic_info"] = basic_info
        new_state["gathered_data"] = gathered

        # If we have all required fields, we're done
        required = REQUIRED_FIELDS.get("basic_info", [])
        if all(basic_info.get(field) for field in required):
            new_state["requires_human_input"] = False
            return new_state

    # No response yet or still need more info - ask first question
    if not basic_info.get("full_name"):
        new_state[
            "pending_question"
        ] = "What's your full name as you'd like it on applications?"
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value
        new_state["gathered_data"] = gathered
        return new_state

    # If we get here but still need input, set HITL
    if new_state.get("pending_question"):
        new_state["requires_human_input"] = True
        new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value

    return new_state


def check_step_complete(state: OnboardingState) -> str:
    """Check if the current step is complete.

    REQ-007 §5.2: Determines routing after each step:
    - "needs_input": Step requires more user input
    - "skip_requested": User wants to skip (optional sections only)
    - "complete": Step has all required data

    Args:
        state: Current onboarding state.

    Returns:
        Routing decision string.
    """
    current_step = state.get("current_step", "")
    user_response = state.get("user_response", "")

    # Check for skip request on optional sections
    if (
        user_response
        and user_response.lower().strip() == "skip"
        and is_step_optional(current_step)
    ):
        return "skip_requested"

    # Check if HITL is needed (still waiting for input)
    if state.get("requires_human_input"):
        return "needs_input"

    # Check if we have all required data for this step
    gathered = state.get("gathered_data", {})
    step_data = gathered.get(current_step, {})
    required = REQUIRED_FIELDS.get(current_step, [])

    if required:
        if all(step_data.get(field) for field in required):
            return "complete"
        return "needs_input"

    # Steps without specific requirements are complete if they ran
    return "complete"


def wait_for_input(state: OnboardingState) -> OnboardingState:
    """HITL checkpoint node - pauses for user input.

    REQ-007 §5.4: Checkpoint Handling

    This node is reached when a step needs user input. It ensures
    HITL flags are set so the graph checkpoints and waits.

    Args:
        state: Current onboarding state.

    Returns:
        State with HITL flags set.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["requires_human_input"] = True
    new_state["checkpoint_reason"] = CheckpointReason.CLARIFICATION_NEEDED.value

    # Add the pending question to messages for display
    pending = state.get("pending_question")
    if pending:
        messages = list(state.get("messages", []))
        # Only add if not already the last message
        if not messages or messages[-1].get("content") != pending:
            messages.append(
                {
                    "role": "assistant",
                    "content": pending,
                }
            )
            new_state["messages"] = messages

    return new_state


def handle_skip(state: OnboardingState) -> OnboardingState:
    """Handle skip request for optional sections.

    REQ-007 §5.4: Checkpoint Handling

    Adds the current step to skipped_sections list.

    Args:
        state: Current onboarding state.

    Returns:
        State with step added to skipped_sections.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    current_step = state.get("current_step", "")
    skipped = list(state.get("skipped_sections", []))

    if current_step not in skipped:
        skipped.append(current_step)

    new_state["skipped_sections"] = skipped
    new_state["user_response"] = None
    new_state["pending_question"] = None

    return new_state


# =============================================================================
# Placeholder Step Nodes (§5.3)
# =============================================================================

# WHY: These are placeholder implementations. Full implementations will use
# LLM calls for conversational gathering (§5.6 Prompt Templates) and API calls
# to persist data (AgentAPIClient). For MVP, we test the graph structure first.


def check_resume_upload(state: OnboardingState) -> OnboardingState:
    """Check for resume upload step.

    Placeholder: Full implementation will handle file upload and extraction.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "resume_upload"
    return new_state


def gather_work_history(state: OnboardingState) -> OnboardingState:
    """Gather work history step.

    Placeholder: Full implementation will expand job entries.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "work_history"
    return new_state


def gather_education(state: OnboardingState) -> OnboardingState:
    """Gather education step.

    Placeholder: Full implementation will gather education entries.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "education"
    return new_state


def gather_skills(state: OnboardingState) -> OnboardingState:
    """Gather skills step.

    Placeholder: Full implementation will rate proficiency.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "skills"
    return new_state


def gather_certifications(state: OnboardingState) -> OnboardingState:
    """Gather certifications step.

    Placeholder: Full implementation will gather certs.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "certifications"
    return new_state


def gather_stories(state: OnboardingState) -> OnboardingState:
    """Gather achievement stories step.

    Placeholder: Full implementation will gather STAR stories.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "achievement_stories"
    return new_state


def gather_non_negotiables(state: OnboardingState) -> OnboardingState:
    """Gather non-negotiables step.

    Placeholder: Full implementation will gather filters.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "non_negotiables"
    return new_state


def gather_growth_targets(state: OnboardingState) -> OnboardingState:
    """Gather growth targets step.

    Placeholder: Full implementation will gather target roles.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "growth_targets"
    return new_state


def derive_voice_profile(state: OnboardingState) -> OnboardingState:
    """Derive voice profile step.

    Placeholder: Full implementation will analyze conversation style.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "voice_profile"
    return new_state


def review_persona(state: OnboardingState) -> OnboardingState:
    """Review gathered persona step.

    Placeholder: Full implementation will present summary.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "review"
    return new_state


def setup_base_resume(state: OnboardingState) -> OnboardingState:
    """Setup base resume step.

    Placeholder: Full implementation will create BaseResume.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["current_step"] = "base_resume_setup"
    return new_state


def complete_onboarding(state: OnboardingState) -> OnboardingState:
    """Complete onboarding step.

    Marks onboarding as complete and clears HITL flags.
    """
    new_state: OnboardingState = dict(state)  # type: ignore[assignment]
    new_state["requires_human_input"] = False
    new_state["checkpoint_reason"] = None
    new_state["pending_question"] = None

    # Add completion message
    messages = list(state.get("messages", []))
    messages.append(
        {
            "role": "assistant",
            "content": "Great! Your profile is all set up. You can now start discovering job opportunities!",
        }
    )
    new_state["messages"] = messages

    return new_state


# =============================================================================
# Graph Construction (§15.2)
# =============================================================================


def create_onboarding_graph() -> StateGraph:
    """Create the Onboarding Agent LangGraph graph.

    REQ-007 §15.2: Graph Spec - Onboarding Agent

    Graph structure follows the interview flow with HITL checkpoints.
    Each step can pause for user input via wait_for_input node.

    Returns:
        Configured StateGraph (not compiled).
    """
    graph = StateGraph(OnboardingState)

    # Add step nodes
    graph.add_node("check_resume_upload", check_resume_upload)
    graph.add_node("gather_basic_info", gather_basic_info)
    graph.add_node("gather_work_history", gather_work_history)
    graph.add_node("gather_education", gather_education)
    graph.add_node("gather_skills", gather_skills)
    graph.add_node("gather_certifications", gather_certifications)
    graph.add_node("gather_stories", gather_stories)
    graph.add_node("gather_non_negotiables", gather_non_negotiables)
    graph.add_node("gather_growth_targets", gather_growth_targets)
    graph.add_node("derive_voice_profile", derive_voice_profile)
    graph.add_node("review_persona", review_persona)
    graph.add_node("setup_base_resume", setup_base_resume)
    graph.add_node("complete_onboarding", complete_onboarding)

    # HITL checkpoint node
    graph.add_node("wait_for_input", wait_for_input)

    # Skip handler
    graph.add_node("handle_skip", handle_skip)

    # Set entry point
    graph.set_entry_point("check_resume_upload")

    # Define step transitions
    # WHY: Each step has conditional edges to handle:
    # - needs_input → wait_for_input → back to step
    # - skip_requested → handle_skip → next step
    # - complete → next step

    step_pairs = [
        ("check_resume_upload", "gather_basic_info"),
        ("gather_basic_info", "gather_work_history"),
        ("gather_work_history", "gather_education"),
        ("gather_education", "gather_skills"),
        ("gather_skills", "gather_certifications"),
        ("gather_certifications", "gather_stories"),
        ("gather_stories", "gather_non_negotiables"),
        ("gather_non_negotiables", "gather_growth_targets"),
        ("gather_growth_targets", "derive_voice_profile"),
        ("derive_voice_profile", "review_persona"),
        ("review_persona", "setup_base_resume"),
        ("setup_base_resume", "complete_onboarding"),
    ]

    # Add conditional edges for each step
    for from_step, to_step in step_pairs:
        graph.add_conditional_edges(
            from_step,
            check_step_complete,
            {
                "needs_input": "wait_for_input",
                "skip_requested": "handle_skip",
                "complete": to_step,
            },
        )
        # wait_for_input returns to the step it came from
        # WHY: After user provides input, we re-run the step to process it
        graph.add_edge("wait_for_input", from_step)
        # handle_skip proceeds to next step
        graph.add_edge("handle_skip", to_step)

    # Final step goes to END
    graph.add_edge("complete_onboarding", END)

    return graph


# Compiled graph singleton
_onboarding_graph: StateGraph | None = None


def get_onboarding_graph() -> StateGraph:
    """Get the compiled onboarding graph.

    Returns a singleton compiled graph instance for use in the API.

    Returns:
        Compiled StateGraph ready for invocation.
    """
    global _onboarding_graph
    if _onboarding_graph is None:
        _onboarding_graph = create_onboarding_graph().compile()
    return _onboarding_graph
