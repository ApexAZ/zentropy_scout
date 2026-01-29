"""Tests for the Onboarding Agent.

REQ-007 §5: Onboarding Agent

Tests verify:
- Trigger condition detection (new user, incomplete onboarding, update request)
- Interview flow state machine
- Step behaviors
- Checkpoint handling (HITL)
- Post-onboarding updates
"""

from app.agents.onboarding import (
    ONBOARDING_STEPS,
    OPTIONAL_SECTIONS,
    check_resume_upload,
    check_step_complete,
    create_onboarding_graph,
    gather_basic_info,
    gather_work_history,
    get_next_step,
    get_onboarding_graph,
    handle_skip,
    is_step_optional,
    is_update_request,
    should_start_onboarding,
    wait_for_input,
)
from app.agents.state import CheckpointReason, OnboardingState


def make_onboarding_state(**overrides: object) -> OnboardingState:
    """Create a base OnboardingState with optional overrides.

    Reduces test boilerplate by providing sensible defaults.

    Args:
        **overrides: Key-value pairs to override default state values.

    Returns:
        OnboardingState with defaults and any provided overrides applied.
    """
    base: OnboardingState = {
        "user_id": "user-123",
        "persona_id": "persona-456",
        "messages": [],
        "current_message": None,
        "tool_calls": [],
        "tool_results": [],
        "next_action": None,
        "requires_human_input": False,
        "checkpoint_reason": None,
        "current_step": "basic_info",
        "gathered_data": {},
        "skipped_sections": [],
        "pending_question": None,
        "user_response": None,
    }
    for key, value in overrides.items():
        base[key] = value  # type: ignore[literal-required]
    return base


# =============================================================================
# Trigger Condition Tests (§5.1)
# =============================================================================


class TestTriggerConditions:
    """Tests for onboarding trigger condition detection."""

    def test_should_start_onboarding_for_new_user(self) -> None:
        """New user with no persona should trigger onboarding."""

        # New user has no persona
        result = should_start_onboarding(
            persona_exists=False,
            onboarding_complete=False,
        )

        assert result is True

    def test_should_resume_onboarding_for_incomplete(self) -> None:
        """User with incomplete onboarding should resume."""

        result = should_start_onboarding(
            persona_exists=True,
            onboarding_complete=False,
        )

        assert result is True

    def test_should_not_start_onboarding_when_complete(self) -> None:
        """User with completed onboarding should not auto-start."""

        result = should_start_onboarding(
            persona_exists=True,
            onboarding_complete=True,
        )

        assert result is False

    def test_is_update_request_detects_profile_update(self) -> None:
        """'Update my profile' should be detected as update request."""

        result = is_update_request("Update my profile")
        assert result is True

    def test_is_update_request_detects_skill_update(self) -> None:
        """'Add a new skill' should be detected as update request."""

        result = is_update_request("I want to add a new skill")
        assert result is True

    def test_is_update_request_rejects_unrelated(self) -> None:
        """Unrelated messages should not be detected as update requests."""

        result = is_update_request("Show me new jobs")
        assert result is False


# =============================================================================
# Interview Flow Tests (§5.2)
# =============================================================================


class TestInterviewFlow:
    """Tests for interview flow state machine."""

    def test_onboarding_steps_are_ordered(self) -> None:
        """Onboarding steps should follow the defined order."""

        expected_order = [
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

        assert expected_order == ONBOARDING_STEPS

    def test_get_next_step_returns_next_in_sequence(self) -> None:
        """get_next_step should return the next step in the flow."""

        assert get_next_step("resume_upload") == "basic_info"
        assert get_next_step("basic_info") == "work_history"
        assert get_next_step("review") == "base_resume_setup"

    def test_get_next_step_returns_none_at_end(self) -> None:
        """get_next_step should return None at the end of the flow."""

        result = get_next_step("base_resume_setup")
        assert result is None

    def test_optional_sections_are_defined(self) -> None:
        """Optional sections should be defined (can be skipped)."""

        # Per REQ-007 §5.2: education and certifications are optional
        assert "education" in OPTIONAL_SECTIONS
        assert "certifications" in OPTIONAL_SECTIONS
        # resume_upload is technically optional (can skip)
        assert "resume_upload" in OPTIONAL_SECTIONS

    def test_get_next_step_returns_none_for_invalid_step(self) -> None:
        """get_next_step should return None for an invalid step name."""
        result = get_next_step("invalid_step_name")
        assert result is None

    def test_is_step_optional_returns_true_for_optional(self) -> None:
        """is_step_optional should return True for optional sections."""
        assert is_step_optional("education") is True
        assert is_step_optional("certifications") is True
        assert is_step_optional("resume_upload") is True

    def test_is_step_optional_returns_false_for_required(self) -> None:
        """is_step_optional should return False for required sections."""
        assert is_step_optional("basic_info") is False
        assert is_step_optional("work_history") is False
        assert is_step_optional("skills") is False


# =============================================================================
# Step Behavior Tests (§5.3)
# =============================================================================


class TestStepBehaviors:
    """Tests for individual step behavior functions."""

    def test_gather_basic_info_asks_for_name(self) -> None:
        """Basic info step should start by asking for name."""

        state: OnboardingState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "current_step": "basic_info",
            "gathered_data": {},
            "skipped_sections": [],
            "pending_question": None,
            "user_response": None,
        }

        result = gather_basic_info(state)

        # Should ask for name and set HITL
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        assert "name" in result["pending_question"].lower()

    def test_gather_basic_info_stores_response(self) -> None:
        """Basic info step should store user's name response."""

        state: OnboardingState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "current_step": "basic_info",
            "gathered_data": {},
            "skipped_sections": [],
            "pending_question": "What's your full name?",
            "user_response": "John Doe",
        }

        result = gather_basic_info(state)

        # Should store the name
        assert "basic_info" in result["gathered_data"]
        assert result["gathered_data"]["basic_info"]["full_name"] == "John Doe"

    def test_check_step_complete_detects_incomplete(self) -> None:
        """check_step_complete should return 'needs_input' when data missing."""

        state: OnboardingState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": True,
            "checkpoint_reason": CheckpointReason.CLARIFICATION_NEEDED.value,
            "current_step": "basic_info",
            "gathered_data": {},
            "skipped_sections": [],
            "pending_question": "What's your full name?",
            "user_response": None,
        }

        result = check_step_complete(state)
        assert result == "needs_input"

    def test_check_step_complete_detects_skip(self) -> None:
        """check_step_complete should detect skip request for optional sections."""

        state: OnboardingState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "current_step": "education",
            "gathered_data": {},
            "skipped_sections": [],
            "pending_question": None,
            "user_response": "skip",
        }

        result = check_step_complete(state)
        assert result == "skip_requested"

    def test_check_step_complete_detects_complete(self) -> None:
        """check_step_complete should detect when step has required data."""

        state: OnboardingState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "current_step": "basic_info",
            "gathered_data": {
                "basic_info": {
                    "full_name": "John Doe",
                    "email": "john@example.com",
                    "phone": "555-1234",
                    "location": "New York, NY",
                }
            },
            "skipped_sections": [],
            "pending_question": None,
            "user_response": None,
        }

        result = check_step_complete(state)
        assert result == "complete"

    def test_skip_not_allowed_for_required_sections(self) -> None:
        """Skip request on required section should NOT return skip_requested."""
        state: OnboardingState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "current_step": "basic_info",  # Required section
            "gathered_data": {},
            "skipped_sections": [],
            "pending_question": None,
            "user_response": "skip",
        }

        result = check_step_complete(state)
        # Should NOT return skip_requested for non-optional section
        assert result != "skip_requested"


# =============================================================================
# Checkpoint Handling Tests (§5.4)
# =============================================================================


class TestCheckpointHandling:
    """Tests for HITL checkpoint handling."""

    def test_wait_for_input_sets_hitl_flags(self) -> None:
        """wait_for_input node should set HITL flags."""

        state: OnboardingState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "current_step": "basic_info",
            "gathered_data": {},
            "skipped_sections": [],
            "pending_question": "What's your full name?",
            "user_response": None,
        }

        result = wait_for_input(state)

        assert result["requires_human_input"] is True
        assert (
            result["checkpoint_reason"] == CheckpointReason.CLARIFICATION_NEEDED.value
        )

    def test_handle_skip_adds_to_skipped_sections(self) -> None:
        """Skipping a section should add it to skipped_sections."""

        state: OnboardingState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
            "current_step": "education",
            "gathered_data": {},
            "skipped_sections": [],
            "pending_question": None,
            "user_response": None,
        }

        result = handle_skip(state)

        assert "education" in result["skipped_sections"]


# =============================================================================
# Graph Structure Tests (§15.2)
# =============================================================================


class TestOnboardingGraphStructure:
    """Tests for Onboarding Agent graph structure."""

    def test_graph_has_required_nodes(self) -> None:
        """Onboarding graph should have all required step nodes."""

        graph = create_onboarding_graph()

        # Core step nodes
        expected_nodes = [
            "check_resume_upload",
            "gather_basic_info",
            "gather_work_history",
            "gather_education",
            "gather_skills",
            "gather_certifications",
            "gather_stories",
            "gather_non_negotiables",
            "gather_growth_targets",
            "derive_voice_profile",
            "review_persona",
            "setup_base_resume",
            "complete_onboarding",
            "wait_for_input",
            "handle_skip",
        ]

        for node in expected_nodes:
            assert node in graph.nodes, f"Missing node: {node}"

    def test_graph_has_entry_point(self) -> None:
        """Onboarding graph should have entry point at check_resume_upload."""

        graph = create_onboarding_graph()
        compiled = graph.compile()
        graph_draw = compiled.get_graph()

        edges = list(graph_draw.edges)
        start_edge = next((e for e in edges if e[0] == "__start__"), None)
        assert start_edge is not None
        assert start_edge[1] == "check_resume_upload"

    def test_graph_compiles_successfully(self) -> None:
        """Onboarding graph should compile without errors."""

        graph = create_onboarding_graph()
        compiled = graph.compile()

        assert compiled is not None

    def test_get_onboarding_graph_returns_singleton(self) -> None:
        """get_onboarding_graph should return the same compiled graph."""

        graph1 = get_onboarding_graph()
        graph2 = get_onboarding_graph()

        assert graph1 is graph2


# =============================================================================
# Resume Upload Step Tests (§5.3.1)
# =============================================================================


class TestResumeUploadStep:
    """Tests for resume upload step behavior (§5.3.1)."""

    def test_check_resume_upload_asks_for_resume(self) -> None:
        """Resume upload step should ask if user has a resume."""
        state = make_onboarding_state(current_step="resume_upload")

        result = check_resume_upload(state)

        assert result["current_step"] == "resume_upload"
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        assert "resume" in result["pending_question"].lower()

    def test_check_resume_upload_handles_skip(self) -> None:
        """Resume upload step should accept skip response."""
        state = make_onboarding_state(
            current_step="resume_upload",
            pending_question="Do you have an existing resume?",
            user_response="skip",
        )

        result = check_resume_upload(state)

        # Should clear pending question and allow skip
        assert result["requires_human_input"] is False
        # gathered_data for resume_upload should indicate skipped
        assert result["gathered_data"].get("resume_upload", {}).get("skipped") is True

    def test_check_resume_upload_handles_yes_response(self) -> None:
        """Resume upload step should prompt for file when user says yes."""
        state = make_onboarding_state(
            current_step="resume_upload",
            pending_question="Do you have an existing resume?",
            user_response="yes",
        )

        result = check_resume_upload(state)

        # Should ask for file upload
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        assert "upload" in result["pending_question"].lower()


# =============================================================================
# Work History Step Tests (§5.3.3)
# =============================================================================


class TestWorkHistoryStep:
    """Tests for work history step behavior (§5.3.3)."""

    def test_gather_work_history_asks_for_job_when_no_data(self) -> None:
        """Work history should ask for job details when starting fresh."""
        state = make_onboarding_state(
            current_step="work_history",
            gathered_data={},
        )

        result = gather_work_history(state)

        assert result["current_step"] == "work_history"
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        # Should ask about most recent job
        question_lower = result["pending_question"].lower()
        assert "job" in question_lower or "role" in question_lower

    def test_gather_work_history_presents_extracted_jobs(self) -> None:
        """Work history should present extracted jobs from resume."""
        extracted_jobs = [
            {
                "title": "Software Engineer",
                "company": "Tech Corp",
                "start_date": "2020-01",
                "end_date": "2023-06",
            }
        ]
        state = make_onboarding_state(
            current_step="work_history",
            gathered_data={
                "resume_upload": {"extracted_jobs": extracted_jobs},
            },
        )

        result = gather_work_history(state)

        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        # Should reference the extracted job for confirmation
        question_lower = result["pending_question"].lower()
        assert "software engineer" in question_lower or "confirm" in question_lower

    def test_gather_work_history_stores_job_entry(self) -> None:
        """Work history should store confirmed job entry."""
        state = make_onboarding_state(
            current_step="work_history",
            gathered_data={"work_history": {"entries": []}},
            pending_question="What was your job title?",
            user_response="Senior Developer at Acme Inc from 2021 to 2024",
        )

        result = gather_work_history(state)

        # Should have stored job entry data
        work_history = result["gathered_data"].get("work_history", {})
        assert "entries" in work_history or "current_entry" in work_history

    def test_gather_work_history_asks_for_accomplishments(self) -> None:
        """Work history should ask for bullet expansion after basic info."""
        state = make_onboarding_state(
            current_step="work_history",
            gathered_data={
                "work_history": {
                    "current_entry": {
                        "title": "Developer",
                        "company": "TechCo",
                        "start_date": "2020",
                        "end_date": "2023",
                    },
                    "entries": [],
                }
            },
            pending_question="What dates did you work there?",
            user_response="2020 to 2023",
        )

        result = gather_work_history(state)

        # After basic job info, should ask about accomplishments
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        accomplishment_keywords = ["accomplish", "achieve", "tell me more", "bullet"]
        assert any(
            keyword in question_lower for keyword in accomplishment_keywords
        ), f"Expected accomplishment question, got: {result['pending_question']}"

    def test_gather_work_history_complete_with_entries(self) -> None:
        """Work history step should be complete when entries have bullets."""
        state = make_onboarding_state(
            current_step="work_history",
            gathered_data={
                "work_history": {
                    "entries": [
                        {
                            "title": "Developer",
                            "company": "TechCo",
                            "start_date": "2020",
                            "end_date": "2023",
                            "bullets": ["Led team of 5 developers"],
                        }
                    ],
                }
            },
            pending_question=None,
            user_response=None,
            requires_human_input=False,
        )

        # check_step_complete should return complete
        result = check_step_complete(state)
        assert result == "complete"

    def test_gather_work_history_completes_on_done(self) -> None:
        """Work history should complete when user says done."""
        state = make_onboarding_state(
            current_step="work_history",
            gathered_data={
                "work_history": {
                    "entries": [{"title": "Dev", "bullets": ["Did stuff"]}],
                }
            },
            pending_question="Do you have another job to add?",
            user_response="done",
        )

        result = gather_work_history(state)

        assert result["requires_human_input"] is False

    def test_check_resume_upload_skips_when_data_exists(self) -> None:
        """Resume upload should skip HITL when resume data already gathered."""
        state = make_onboarding_state(
            current_step="resume_upload",
            gathered_data={
                "resume_upload": {"skipped": True},
            },
        )

        result = check_resume_upload(state)

        # Should not require input since data already exists
        assert result["requires_human_input"] is False
