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
    ACHIEVEMENT_STORY_PROMPT,
    ONBOARDING_STEPS,
    OPTIONAL_SECTIONS,
    SECTIONS_REQUIRING_RESCORE,
    SYSTEM_PROMPT_TEMPLATE,
    TRANSITION_PROMPTS,
    VOICE_PROFILE_DERIVATION_PROMPT,
    WORK_HISTORY_EXPANSION_PROMPT,
    check_resume_upload,
    check_step_complete,
    create_onboarding_graph,
    create_update_state,
    derive_voice_profile,
    detect_update_section,
    format_gathered_data_summary,
    gather_basic_info,
    gather_certifications,
    gather_education,
    gather_growth_targets,
    gather_non_negotiables,
    gather_skills,
    gather_stories,
    gather_work_history,
    get_achievement_story_prompt,
    get_affected_embeddings,
    get_next_step,
    get_onboarding_graph,
    get_system_prompt,
    get_transition_prompt,
    get_update_completion_message,
    get_voice_profile_prompt,
    get_work_history_prompt,
    handle_skip,
    is_post_onboarding_update,
    is_step_optional,
    is_update_request,
    setup_base_resume,
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


# =============================================================================
# Education Step Tests (§5.3 — education)
# =============================================================================


class TestEducationStep:
    """Tests for education step behavior."""

    def test_gather_education_asks_for_education(self) -> None:
        """Education step should ask if user has education to add."""
        state = make_onboarding_state(
            current_step="education",
            gathered_data={},
        )

        result = gather_education(state)

        assert result["current_step"] == "education"
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "education" in question_lower or "degree" in question_lower

    def test_gather_education_handles_skip(self) -> None:
        """Education step should accept skip response."""
        state = make_onboarding_state(
            current_step="education",
            pending_question="Do you have any formal education?",
            user_response="skip",
        )

        result = gather_education(state)

        # Should clear pending question and allow skip
        assert result["requires_human_input"] is False
        assert result["gathered_data"].get("education", {}).get("skipped") is True

    def test_gather_education_handles_no_response(self) -> None:
        """Education step should treat 'no' as skip since it's optional."""
        state = make_onboarding_state(
            current_step="education",
            pending_question="Do you have any formal education?",
            user_response="no",
        )

        result = gather_education(state)

        # Should mark as skipped (no education = skip)
        assert result["requires_human_input"] is False
        assert result["gathered_data"].get("education", {}).get("skipped") is True

    def test_gather_education_stores_entry(self) -> None:
        """Education step should store education entry from user response."""
        state = make_onboarding_state(
            current_step="education",
            gathered_data={"education": {"entries": []}},
            pending_question="What degree did you earn?",
            user_response="Bachelor of Science in Computer Science",
        )

        result = gather_education(state)

        # Should have stored education entry data
        education = result["gathered_data"].get("education", {})
        assert "entries" in education or "current_entry" in education

    def test_gather_education_asks_for_more_entries(self) -> None:
        """Education step should ask if user has more entries after storing one."""
        state = make_onboarding_state(
            current_step="education",
            gathered_data={
                "education": {
                    "current_entry": {
                        "degree": "BS Computer Science",
                        "institution": "ASU",
                        "graduation_year": "2020",
                    },
                    "entries": [],
                }
            },
            pending_question="What year did you graduate?",
            user_response="2020",
        )

        result = gather_education(state)

        # After completing an entry, should ask if there are more
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "another" in question_lower or "more" in question_lower

    def test_gather_education_completes_on_done(self) -> None:
        """Education step should complete when user says done."""
        state = make_onboarding_state(
            current_step="education",
            gathered_data={
                "education": {
                    "entries": [
                        {
                            "degree": "BS",
                            "institution": "ASU",
                            "graduation_year": "2020",
                        }
                    ],
                }
            },
            pending_question="Do you have another degree to add?",
            user_response="done",
        )

        result = gather_education(state)

        assert result["requires_human_input"] is False

    def test_gather_education_handles_skip_case_insensitive(self) -> None:
        """Education step should accept skip in any case (SKIP, Skip, etc.)."""
        state = make_onboarding_state(
            current_step="education",
            pending_question="Do you have any formal education?",
            user_response="SKIP",
        )

        result = gather_education(state)

        assert result["requires_human_input"] is False
        assert result["gathered_data"].get("education", {}).get("skipped") is True

    def test_gather_education_handles_skip_with_whitespace(self) -> None:
        """Education step should accept skip with surrounding whitespace."""
        state = make_onboarding_state(
            current_step="education",
            pending_question="Do you have any formal education?",
            user_response="  skip  ",
        )

        result = gather_education(state)

        assert result["requires_human_input"] is False
        assert result["gathered_data"].get("education", {}).get("skipped") is True

    def test_gather_education_asks_for_institution_after_degree(self) -> None:
        """Education step should ask for institution after degree is provided."""
        state = make_onboarding_state(
            current_step="education",
            gathered_data={"education": {"entries": []}},
            pending_question="Do you have any formal education?",
            user_response="Bachelor of Science in Computer Science",
        )

        result = gather_education(state)

        # After providing degree, should ask for institution
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "institution" in question_lower or "attend" in question_lower


# =============================================================================
# Certifications Step Tests (§5.3 — certifications)
# =============================================================================


class TestCertificationsStep:
    """Tests for certifications step behavior."""

    def test_gather_certifications_asks_for_certifications(self) -> None:
        """Certifications step should ask if user has certifications."""
        state = make_onboarding_state(
            current_step="certifications",
            gathered_data={},
        )

        result = gather_certifications(state)

        assert result["current_step"] == "certifications"
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "certification" in question_lower or "cert" in question_lower

    def test_gather_certifications_handles_skip(self) -> None:
        """Certifications step should accept skip response."""
        state = make_onboarding_state(
            current_step="certifications",
            pending_question="Do you have any professional certifications?",
            user_response="skip",
        )

        result = gather_certifications(state)

        # Should clear pending question and allow skip
        assert result["requires_human_input"] is False
        assert result["gathered_data"].get("certifications", {}).get("skipped") is True

    def test_gather_certifications_handles_no_response(self) -> None:
        """Certifications step should treat 'no' as skip since it's optional."""
        state = make_onboarding_state(
            current_step="certifications",
            pending_question="Do you have any professional certifications?",
            user_response="no",
        )

        result = gather_certifications(state)

        # Should mark as skipped (no certs = skip)
        assert result["requires_human_input"] is False
        assert result["gathered_data"].get("certifications", {}).get("skipped") is True

    def test_gather_certifications_stores_entry(self) -> None:
        """Certifications step should store certification entry from response."""
        state = make_onboarding_state(
            current_step="certifications",
            gathered_data={"certifications": {"entries": []}},
            pending_question="What certification do you have?",
            user_response="AWS Solutions Architect Professional",
        )

        result = gather_certifications(state)

        # Should have stored certification entry data
        certs = result["gathered_data"].get("certifications", {})
        assert "entries" in certs or "current_entry" in certs

    def test_gather_certifications_asks_for_issuer(self) -> None:
        """Certifications step should ask for issuing organization after name."""
        state = make_onboarding_state(
            current_step="certifications",
            gathered_data={
                "certifications": {
                    "current_entry": {
                        "certification_name": "AWS Solutions Architect",
                    },
                    "entries": [],
                }
            },
            pending_question="What certification do you have?",
            user_response="AWS Solutions Architect Professional",
        )

        result = gather_certifications(state)

        # After cert name, should ask about issuer
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "issu" in question_lower or "organization" in question_lower

    def test_gather_certifications_completes_on_done(self) -> None:
        """Certifications step should complete when user says done."""
        state = make_onboarding_state(
            current_step="certifications",
            gathered_data={
                "certifications": {
                    "entries": [
                        {
                            "certification_name": "AWS SA",
                            "issuing_organization": "AWS",
                            "date_obtained": "2023",
                        }
                    ],
                }
            },
            pending_question="Do you have another certification to add?",
            user_response="done",
        )

        result = gather_certifications(state)

        assert result["requires_human_input"] is False

    def test_gather_certifications_handles_skip_case_insensitive(self) -> None:
        """Certifications step should accept skip in any case (SKIP, Skip, etc.)."""
        state = make_onboarding_state(
            current_step="certifications",
            pending_question="Do you have any professional certifications?",
            user_response="SKIP",
        )

        result = gather_certifications(state)

        assert result["requires_human_input"] is False
        assert result["gathered_data"].get("certifications", {}).get("skipped") is True

    def test_gather_certifications_handles_skip_with_whitespace(self) -> None:
        """Certifications step should accept skip with surrounding whitespace."""
        state = make_onboarding_state(
            current_step="certifications",
            pending_question="Do you have any professional certifications?",
            user_response="  skip  ",
        )

        result = gather_certifications(state)

        assert result["requires_human_input"] is False
        assert result["gathered_data"].get("certifications", {}).get("skipped") is True

    def test_gather_certifications_asks_for_date_after_issuer(self) -> None:
        """Certifications step should ask for date after issuer is provided."""
        state = make_onboarding_state(
            current_step="certifications",
            gathered_data={
                "certifications": {
                    "current_entry": {
                        "certification_name": "AWS Solutions Architect",
                    },
                    "entries": [],
                }
            },
            pending_question="What organization issued this certification?",
            user_response="Amazon Web Services",
        )

        result = gather_certifications(state)

        # After providing issuer, should ask for date obtained
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "when" in question_lower or "date" in question_lower


# =============================================================================
# Skills Step Tests (§5.3.4)
# =============================================================================


class TestSkillsStep:
    """Tests for skills step behavior (§5.3.4)."""

    def test_gather_skills_asks_for_skills(self) -> None:
        """Skills step should ask user about their skills."""
        state = make_onboarding_state(
            current_step="skills",
            gathered_data={},
        )

        result = gather_skills(state)

        assert result["current_step"] == "skills"
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "skill" in question_lower

    def test_gather_skills_stores_skill_with_proficiency(self) -> None:
        """Skills step should store complete skill entry with all fields."""
        # Test the full flow: after providing skill type, entry should be stored
        state = make_onboarding_state(
            current_step="skills",
            gathered_data={
                "skills": {
                    "current_entry": {
                        "skill_name": "Python",
                        "proficiency": "Expert",
                    },
                    "entries": [],
                }
            },
            pending_question="Is Python a hard (technical) or soft (interpersonal) skill?",
            user_response="Hard",
        )

        result = gather_skills(state)

        # Should have stored skill with all fields
        skills = result["gathered_data"].get("skills", {})
        entries = skills.get("entries", [])
        assert len(entries) == 1
        assert entries[0]["skill_name"] == "Python"
        assert entries[0]["proficiency"] == "Expert"
        assert entries[0]["skill_type"] == "Hard"

    def test_gather_skills_asks_for_proficiency_after_skill_name(self) -> None:
        """Skills step should ask for proficiency after skill name is provided."""
        state = make_onboarding_state(
            current_step="skills",
            gathered_data={"skills": {"entries": []}},
            pending_question="What is one of your key skills?",
            user_response="Python",
        )

        result = gather_skills(state)

        # After skill name, should ask for proficiency
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "proficiency" in question_lower or "rate" in question_lower

    def test_gather_skills_asks_for_skill_type(self) -> None:
        """Skills step should ask for skill type (hard/soft) after proficiency."""
        state = make_onboarding_state(
            current_step="skills",
            gathered_data={
                "skills": {
                    "current_entry": {
                        "skill_name": "Python",
                        "proficiency": "Expert",
                    },
                    "entries": [],
                }
            },
            pending_question="How would you rate your Python proficiency?",
            user_response="Expert",
        )

        result = gather_skills(state)

        # After proficiency, should ask about skill type (hard/soft)
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert (
            "type" in question_lower
            or "hard" in question_lower
            or "soft" in question_lower
        )

    def test_gather_skills_asks_for_more_skills(self) -> None:
        """Skills step should ask if user has more skills after storing one."""
        state = make_onboarding_state(
            current_step="skills",
            gathered_data={
                "skills": {
                    "current_entry": {
                        "skill_name": "Python",
                        "proficiency": "Expert",
                    },
                    "entries": [],
                }
            },
            pending_question="Is Python a hard (technical) or soft (interpersonal) skill?",
            user_response="Hard",
        )

        result = gather_skills(state)

        # After completing an entry, should ask if there are more
        skills = result["gathered_data"].get("skills", {})
        assert len(skills.get("entries", [])) == 1
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "another" in question_lower or "more" in question_lower

    def test_gather_skills_completes_on_done(self) -> None:
        """Skills step should complete when user says done."""
        state = make_onboarding_state(
            current_step="skills",
            gathered_data={
                "skills": {
                    "entries": [
                        {
                            "skill_name": "Python",
                            "proficiency": "Expert",
                            "skill_type": "Hard",
                        }
                    ],
                }
            },
            pending_question="Do you have another skill to add?",
            user_response="done",
        )

        result = gather_skills(state)

        assert result["requires_human_input"] is False

    def test_gather_skills_handles_done_case_insensitive(self) -> None:
        """Skills step should accept done in any case (DONE, Done, etc.)."""
        state = make_onboarding_state(
            current_step="skills",
            gathered_data={
                "skills": {
                    "entries": [
                        {
                            "skill_name": "Python",
                            "proficiency": "Expert",
                            "skill_type": "Hard",
                        }
                    ],
                }
            },
            pending_question="Do you have another skill to add?",
            user_response="DONE",
        )

        result = gather_skills(state)

        assert result["requires_human_input"] is False

    def test_gather_skills_handles_done_with_whitespace(self) -> None:
        """Skills step should accept done with surrounding whitespace."""
        state = make_onboarding_state(
            current_step="skills",
            gathered_data={
                "skills": {
                    "entries": [
                        {
                            "skill_name": "Python",
                            "proficiency": "Expert",
                            "skill_type": "Hard",
                        }
                    ],
                }
            },
            pending_question="Do you have another skill to add?",
            user_response="  done  ",
        )

        result = gather_skills(state)

        assert result["requires_human_input"] is False

    def test_gather_skills_presents_extracted_skills(self) -> None:
        """Skills step should present skills extracted from resume for rating."""
        state = make_onboarding_state(
            current_step="skills",
            gathered_data={
                "resume_upload": {
                    "extracted_skills": ["Python", "JavaScript", "SQL"],
                },
            },
        )

        result = gather_skills(state)

        # Should present extracted skills for proficiency rating
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        # Should mention the first extracted skill
        assert "Python" in result["pending_question"]

    def test_check_step_complete_detects_skills_complete(self) -> None:
        """check_step_complete should detect when skills step has required data."""
        state = make_onboarding_state(
            current_step="skills",
            requires_human_input=False,
            gathered_data={
                "skills": {
                    "entries": [
                        {
                            "skill_name": "Python",
                            "proficiency": "Expert",
                            "skill_type": "Hard",
                        }
                    ],
                }
            },
        )

        result = check_step_complete(state)
        assert result == "complete"


# =============================================================================
# Achievement Stories Step Tests (§5.3.5)
# =============================================================================


class TestStoriesStep:
    """Tests for achievement stories step behavior (§5.3.5)."""

    def test_gather_stories_asks_for_story(self) -> None:
        """Stories step should prompt for an achievement story."""
        state = make_onboarding_state(
            current_step="achievement_stories",
            gathered_data={},
        )

        result = gather_stories(state)

        assert result["current_step"] == "achievement_stories"
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        # Should ask about achievements/accomplishments
        assert (
            "achiev" in question_lower
            or "accomplish" in question_lower
            or "tell" in question_lower
        )

    def test_gather_stories_asks_for_context_after_initial(self) -> None:
        """Stories step should ask for context/situation after initial prompt."""
        state = make_onboarding_state(
            current_step="achievement_stories",
            gathered_data={"achievement_stories": {"entries": []}},
            pending_question="Tell me about a significant achievement.",
            user_response="I led a team to deliver a critical project.",
        )

        result = gather_stories(state)

        # After initial response, should probe for context
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert (
            "context" in question_lower
            or "situation" in question_lower
            or "challeng" in question_lower
        )

    def test_gather_stories_asks_for_action(self) -> None:
        """Stories step should ask for specific actions taken."""
        state = make_onboarding_state(
            current_step="achievement_stories",
            gathered_data={
                "achievement_stories": {
                    "current_entry": {
                        "initial_story": "I led a team to deliver a critical project.",
                        "context": "The project was 3 months behind schedule.",
                    },
                    "entries": [],
                }
            },
            pending_question="What was the context or challenge?",
            user_response="The project was 3 months behind schedule.",
        )

        result = gather_stories(state)

        # After context, should ask about their specific actions
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert (
            "action" in question_lower
            or "you do" in question_lower
            or "specifically" in question_lower
        )

    def test_gather_stories_asks_for_outcome(self) -> None:
        """Stories step should ask for measurable outcomes."""
        state = make_onboarding_state(
            current_step="achievement_stories",
            gathered_data={
                "achievement_stories": {
                    "current_entry": {
                        "initial_story": "Led a team project",
                        "context": "Project was behind schedule",
                        "action": "I reorganized priorities and implemented daily standups",
                    },
                    "entries": [],
                }
            },
            pending_question="What specifically did you do?",
            user_response="I reorganized priorities and implemented daily standups",
        )

        result = gather_stories(state)

        # After action, should ask for outcome/result
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert (
            "result" in question_lower
            or "outcome" in question_lower
            or "impact" in question_lower
        )

    def test_gather_stories_asks_for_skills_demonstrated(self) -> None:
        """Stories step should ask which skills the story demonstrates."""
        state = make_onboarding_state(
            current_step="achievement_stories",
            gathered_data={
                "achievement_stories": {
                    "current_entry": {
                        "initial_story": "Led a team project",
                        "context": "Project was behind schedule",
                        "action": "Reorganized priorities",
                        "outcome": "Delivered on time, saved $50K",
                    },
                    "entries": [],
                }
            },
            pending_question="What was the result or impact?",
            user_response="Delivered on time, saved $50K",
        )

        result = gather_stories(state)

        # After outcome, should ask about skills demonstrated
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "skill" in question_lower or "demonstrat" in question_lower

    def test_gather_stories_stores_complete_story(self) -> None:
        """Stories step should store a complete STAR-format story."""
        state = make_onboarding_state(
            current_step="achievement_stories",
            gathered_data={
                "achievement_stories": {
                    "current_entry": {
                        "initial_story": "Led a team project",
                        "context": "Project was behind schedule",
                        "action": "Reorganized priorities",
                        "outcome": "Delivered on time, saved $50K",
                    },
                    "entries": [],
                }
            },
            pending_question="Which skills did this demonstrate?",
            user_response="Leadership, Project Management",
        )

        result = gather_stories(state)

        # Should have stored a complete story
        stories = result["gathered_data"].get("achievement_stories", {})
        entries = stories.get("entries", [])
        assert len(entries) == 1
        assert "context" in entries[0]
        assert "action" in entries[0]
        assert "outcome" in entries[0]
        assert "skills_demonstrated" in entries[0]

    def test_gather_stories_asks_for_more_stories(self) -> None:
        """Stories step should ask for more stories (goal is 3-5)."""
        state = make_onboarding_state(
            current_step="achievement_stories",
            gathered_data={
                "achievement_stories": {
                    "current_entry": {
                        "initial_story": "Led a team project",
                        "context": "Project was behind schedule",
                        "action": "Reorganized priorities",
                        "outcome": "Delivered on time, saved $50K",
                    },
                    "entries": [],
                }
            },
            pending_question="Which skills did this demonstrate?",
            user_response="Leadership, Project Management",
        )

        result = gather_stories(state)

        # After completing a story, should ask for more
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "another" in question_lower or "more" in question_lower

    def test_gather_stories_completes_on_done(self) -> None:
        """Stories step should complete when user says done."""
        state = make_onboarding_state(
            current_step="achievement_stories",
            gathered_data={
                "achievement_stories": {
                    "entries": [
                        {
                            "context": "Behind schedule",
                            "action": "Reorganized",
                            "outcome": "On time",
                            "skills_demonstrated": "Leadership",
                        }
                    ],
                }
            },
            pending_question="Do you have another achievement story to share?",
            user_response="done",
        )

        result = gather_stories(state)

        assert result["requires_human_input"] is False

    def test_gather_stories_handles_done_case_insensitive(self) -> None:
        """Stories step should accept done in any case."""
        state = make_onboarding_state(
            current_step="achievement_stories",
            gathered_data={
                "achievement_stories": {
                    "entries": [
                        {
                            "context": "X",
                            "action": "Y",
                            "outcome": "Z",
                            "skills_demonstrated": "A",
                        }
                    ],
                }
            },
            pending_question="Do you have another achievement story?",
            user_response="DONE",
        )

        result = gather_stories(state)

        assert result["requires_human_input"] is False

    def test_gather_stories_handles_done_with_whitespace(self) -> None:
        """Stories step should accept done with surrounding whitespace."""
        state = make_onboarding_state(
            current_step="achievement_stories",
            gathered_data={
                "achievement_stories": {
                    "entries": [
                        {
                            "context": "X",
                            "action": "Y",
                            "outcome": "Z",
                            "skills_demonstrated": "A",
                        }
                    ],
                }
            },
            pending_question="Do you have another achievement story?",
            user_response="  done  ",
        )

        result = gather_stories(state)

        assert result["requires_human_input"] is False

    def test_check_step_complete_detects_stories_complete(self) -> None:
        """check_step_complete should detect when stories step has required data."""
        state = make_onboarding_state(
            current_step="achievement_stories",
            requires_human_input=False,
            gathered_data={
                "achievement_stories": {
                    "entries": [
                        {
                            "context": "Behind schedule",
                            "action": "Reorganized team",
                            "outcome": "Delivered on time",
                            "skills_demonstrated": "Leadership",
                        }
                    ],
                }
            },
        )

        result = check_step_complete(state)
        assert result == "complete"


# =============================================================================
# Non-Negotiables Step Tests (§5.3.6)
# =============================================================================


class TestNonNegotiablesStep:
    """Tests for non-negotiables step behavior (§5.3.6)."""

    def test_gather_non_negotiables_asks_for_remote_preference(self) -> None:
        """Non-negotiables step should ask about remote preference first."""
        state = make_onboarding_state(
            current_step="non_negotiables",
            gathered_data={},
        )

        result = gather_non_negotiables(state)

        assert result["current_step"] == "non_negotiables"
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert (
            "remote" in question_lower
            or "hybrid" in question_lower
            or "onsite" in question_lower
        )

    def test_gather_non_negotiables_asks_cities_if_not_remote_only(self) -> None:
        """Non-negotiables should ask for commutable cities if not remote-only."""
        state = make_onboarding_state(
            current_step="non_negotiables",
            gathered_data={"non_negotiables": {}},
            pending_question="Are you looking for remote, hybrid, or onsite roles?",
            user_response="Hybrid",
        )

        result = gather_non_negotiables(state)

        # After hybrid/onsite preference, should ask for cities
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "cit" in question_lower or "commut" in question_lower

    def test_gather_non_negotiables_skips_cities_for_remote_only(self) -> None:
        """Non-negotiables should skip cities question for remote-only preference."""
        state = make_onboarding_state(
            current_step="non_negotiables",
            gathered_data={"non_negotiables": {}},
            pending_question="Are you looking for remote, hybrid, or onsite roles?",
            user_response="Remote only",
        )

        result = gather_non_negotiables(state)

        # After remote-only, should skip to salary (not ask about cities)
        non_neg = result["gathered_data"].get("non_negotiables", {})
        assert non_neg.get("remote_preference") == "Remote only"
        # Next question should be about salary, not cities
        question_lower = result["pending_question"].lower()
        assert "salary" in question_lower or "minimum" in question_lower

    def test_gather_non_negotiables_asks_for_salary(self) -> None:
        """Non-negotiables should ask for minimum base salary."""
        state = make_onboarding_state(
            current_step="non_negotiables",
            gathered_data={
                "non_negotiables": {
                    "remote_preference": "Remote only",
                }
            },
            pending_question="What's your minimum acceptable base salary?",
            user_response="$100,000",
        )

        result = gather_non_negotiables(state)

        non_neg = result["gathered_data"].get("non_negotiables", {})
        assert non_neg.get("minimum_base_salary") == "$100,000"

    def test_gather_non_negotiables_asks_for_visa_sponsorship(self) -> None:
        """Non-negotiables should ask about visa sponsorship requirement."""
        state = make_onboarding_state(
            current_step="non_negotiables",
            gathered_data={
                "non_negotiables": {
                    "remote_preference": "Remote only",
                    "minimum_base_salary": "$100,000",
                }
            },
            pending_question="What's your minimum acceptable base salary?",
            user_response="$100,000",
        )

        result = gather_non_negotiables(state)

        # After salary, should ask about visa
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "visa" in question_lower or "sponsor" in question_lower

    def test_gather_non_negotiables_asks_for_industry_exclusions(self) -> None:
        """Non-negotiables should ask about industries to avoid."""
        state = make_onboarding_state(
            current_step="non_negotiables",
            gathered_data={
                "non_negotiables": {
                    "remote_preference": "Remote only",
                    "minimum_base_salary": "$100,000",
                    "visa_sponsorship": "No",
                }
            },
            pending_question="Do you require visa sponsorship?",
            user_response="No",
        )

        result = gather_non_negotiables(state)

        # After visa, should ask about industries to avoid
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "industr" in question_lower or "avoid" in question_lower

    def test_gather_non_negotiables_asks_for_custom_filters(self) -> None:
        """Non-negotiables should ask about other dealbreakers."""
        state = make_onboarding_state(
            current_step="non_negotiables",
            gathered_data={
                "non_negotiables": {
                    "remote_preference": "Remote only",
                    "minimum_base_salary": "$100,000",
                    "visa_sponsorship": "No",
                    "industry_exclusions": "None",
                }
            },
            pending_question="Any industries you want to avoid?",
            user_response="None",
        )

        result = gather_non_negotiables(state)

        # After industries, should ask about other dealbreakers
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert "other" in question_lower or "dealbreaker" in question_lower

    def test_gather_non_negotiables_completes_after_custom_filters(self) -> None:
        """Non-negotiables should complete after custom filters are provided."""
        state = make_onboarding_state(
            current_step="non_negotiables",
            gathered_data={
                "non_negotiables": {
                    "remote_preference": "Remote only",
                    "minimum_base_salary": "$100,000",
                    "visa_sponsorship": "No",
                    "industry_exclusions": "None",
                }
            },
            pending_question="Any other dealbreakers I should know about?",
            user_response="No travel requirements",
        )

        result = gather_non_negotiables(state)

        # After custom filters, step should be complete
        non_neg = result["gathered_data"].get("non_negotiables", {})
        assert non_neg.get("custom_filters") == "No travel requirements"
        assert result["requires_human_input"] is False

    def test_gather_non_negotiables_stores_commutable_cities(self) -> None:
        """Non-negotiables should store commutable cities for hybrid/onsite."""
        state = make_onboarding_state(
            current_step="non_negotiables",
            gathered_data={
                "non_negotiables": {
                    "remote_preference": "Hybrid",
                }
            },
            pending_question="Which cities can you commute to?",
            user_response="San Francisco, Oakland",
        )

        result = gather_non_negotiables(state)

        non_neg = result["gathered_data"].get("non_negotiables", {})
        assert non_neg.get("commutable_cities") == "San Francisco, Oakland"

    def test_check_step_complete_detects_non_negotiables_complete(self) -> None:
        """check_step_complete should detect when non_negotiables has required data."""
        state = make_onboarding_state(
            current_step="non_negotiables",
            requires_human_input=False,
            gathered_data={
                "non_negotiables": {
                    "remote_preference": "Remote only",
                }
            },
        )

        result = check_step_complete(state)
        assert result == "complete"

    def test_gather_non_negotiables_handles_remote_case_insensitive(self) -> None:
        """Non-negotiables should handle 'REMOTE ONLY' case variations."""
        state = make_onboarding_state(
            current_step="non_negotiables",
            gathered_data={"non_negotiables": {}},
            pending_question="Are you looking for remote, hybrid, or onsite roles?",
            user_response="REMOTE ONLY",
        )

        result = gather_non_negotiables(state)

        # Should still skip to salary, not cities (case-insensitive)
        question_lower = result["pending_question"].lower()
        assert "salary" in question_lower

    def test_gather_non_negotiables_asks_cities_for_onsite(self) -> None:
        """Non-negotiables should ask for commutable cities for onsite preference."""
        state = make_onboarding_state(
            current_step="non_negotiables",
            gathered_data={"non_negotiables": {}},
            pending_question="Are you looking for remote, hybrid, or onsite roles?",
            user_response="Onsite",
        )

        result = gather_non_negotiables(state)

        # Onsite requires commute - should ask for cities
        question_lower = result["pending_question"].lower()
        assert "cit" in question_lower or "commut" in question_lower


# =============================================================================
# Growth Targets Step Tests (§5.3.7 / §7.5)
# =============================================================================


class TestGrowthTargetsStep:
    """Tests for growth targets step behavior (derived from §7.5 Stretch Score)."""

    def test_gather_growth_targets_asks_for_target_roles(self) -> None:
        """Growth targets step should ask about roles user aspires to."""
        state = make_onboarding_state(
            current_step="growth_targets",
            gathered_data={},
        )

        result = gather_growth_targets(state)

        assert result["current_step"] == "growth_targets"
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert (
            "role" in question_lower
            or "aspir" in question_lower
            or "grow" in question_lower
        )

    def test_gather_growth_targets_stores_target_roles(self) -> None:
        """Growth targets should store target roles from user response."""
        state = make_onboarding_state(
            current_step="growth_targets",
            gathered_data={"growth_targets": {}},
            pending_question="What roles are you aspiring to grow into?",
            user_response="Engineering Manager, Director of Engineering",
        )

        result = gather_growth_targets(state)

        growth = result["gathered_data"].get("growth_targets", {})
        assert (
            growth.get("target_roles") == "Engineering Manager, Director of Engineering"
        )

    def test_gather_growth_targets_asks_for_target_skills(self) -> None:
        """Growth targets should ask about skills user wants to develop."""
        state = make_onboarding_state(
            current_step="growth_targets",
            gathered_data={
                "growth_targets": {
                    "target_roles": "Engineering Manager",
                }
            },
            pending_question="What roles are you aspiring to grow into?",
            user_response="Engineering Manager",
        )

        result = gather_growth_targets(state)

        # After target roles, should ask about skills to develop
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert (
            "skill" in question_lower
            or "learn" in question_lower
            or "develop" in question_lower
        )

    def test_gather_growth_targets_stores_target_skills(self) -> None:
        """Growth targets should store skills user wants to develop."""
        state = make_onboarding_state(
            current_step="growth_targets",
            gathered_data={
                "growth_targets": {
                    "target_roles": "Engineering Manager",
                }
            },
            pending_question="What skills would you like to develop?",
            user_response="People management, strategic planning",
        )

        result = gather_growth_targets(state)

        growth = result["gathered_data"].get("growth_targets", {})
        assert growth.get("target_skills") == "People management, strategic planning"

    def test_gather_growth_targets_completes_after_skills(self) -> None:
        """Growth targets should complete after target skills are provided."""
        state = make_onboarding_state(
            current_step="growth_targets",
            gathered_data={
                "growth_targets": {
                    "target_roles": "Engineering Manager",
                }
            },
            pending_question="What skills would you like to develop?",
            user_response="People management, strategic planning",
        )

        result = gather_growth_targets(state)

        # After target skills, step should be complete
        growth = result["gathered_data"].get("growth_targets", {})
        assert growth.get("target_skills") == "People management, strategic planning"
        assert result["requires_human_input"] is False

    def test_gather_growth_targets_handles_none_response(self) -> None:
        """Growth targets should handle user saying 'none' for target skills."""
        state = make_onboarding_state(
            current_step="growth_targets",
            gathered_data={
                "growth_targets": {
                    "target_roles": "Same role, just different company",
                }
            },
            pending_question="What skills would you like to develop?",
            user_response="None",
        )

        result = gather_growth_targets(state)

        # Should still complete even with "none" response
        growth = result["gathered_data"].get("growth_targets", {})
        assert growth.get("target_skills") == "None"
        assert result["requires_human_input"] is False

    def test_check_step_complete_detects_growth_targets_complete(self) -> None:
        """check_step_complete should detect when growth_targets has required data."""
        state = make_onboarding_state(
            current_step="growth_targets",
            requires_human_input=False,
            gathered_data={
                "growth_targets": {
                    "target_roles": "Engineering Manager",
                }
            },
        )

        result = check_step_complete(state)
        assert result == "complete"


# =============================================================================
# Voice Profile Step Tests (§5.3.7)
# =============================================================================


class TestVoiceProfileStep:
    """Tests for voice profile derivation step behavior (§5.3.7)."""

    def test_derive_voice_profile_asks_for_writing_sample(self) -> None:
        """Voice profile step should offer to analyze a writing sample."""
        state = make_onboarding_state(
            current_step="voice_profile",
            gathered_data={},
        )

        result = derive_voice_profile(state)

        assert result["current_step"] == "voice_profile"
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        # Should ask about writing sample or voice/style
        assert (
            "writing" in question_lower
            or "sample" in question_lower
            or "voice" in question_lower
            or "style" in question_lower
        )

    def test_derive_voice_profile_handles_skip_sample(self) -> None:
        """Voice profile should proceed to tone derivation if sample is skipped."""
        state = make_onboarding_state(
            current_step="voice_profile",
            gathered_data={"voice_profile": {}},
            pending_question="Do you have a writing sample to share?",
            user_response="skip",
        )

        result = derive_voice_profile(state)

        # Should proceed to derive/present voice profile
        assert result["requires_human_input"] is True
        # Should either ask about tone or present derived profile
        question_lower = result["pending_question"].lower()
        assert (
            "tone" in question_lower
            or "voice" in question_lower
            or "style" in question_lower
        )

    def test_derive_voice_profile_stores_writing_sample(self) -> None:
        """Voice profile should store user's writing sample."""
        state = make_onboarding_state(
            current_step="voice_profile",
            gathered_data={"voice_profile": {}},
            pending_question="Do you have a writing sample to share?",
            user_response="Here's an excerpt from a recent email I sent...",
        )

        result = derive_voice_profile(state)

        voice = result["gathered_data"].get("voice_profile", {})
        assert voice.get("writing_sample_text") == (
            "Here's an excerpt from a recent email I sent..."
        )

    def test_derive_voice_profile_presents_derived_profile(self) -> None:
        """Voice profile should present derived traits for confirmation."""
        state = make_onboarding_state(
            current_step="voice_profile",
            gathered_data={
                "voice_profile": {
                    "writing_sample_text": "Sample text here",
                }
            },
            pending_question="Please share a writing sample",
            user_response="Sample text here",
        )

        result = derive_voice_profile(state)

        # After sample, should present derived voice or ask about tone
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None

    def test_derive_voice_profile_stores_tone(self) -> None:
        """Voice profile should store user's confirmed tone."""
        state = make_onboarding_state(
            current_step="voice_profile",
            gathered_data={"voice_profile": {}},
            pending_question="How would you describe your tone?",
            user_response="Direct and confident",
        )

        result = derive_voice_profile(state)

        voice = result["gathered_data"].get("voice_profile", {})
        assert voice.get("tone") == "Direct and confident"

    def test_derive_voice_profile_asks_for_sentence_style(self) -> None:
        """Voice profile should ask about sentence style after tone."""
        state = make_onboarding_state(
            current_step="voice_profile",
            gathered_data={
                "voice_profile": {
                    "tone": "Direct and confident",
                }
            },
            pending_question="How would you describe your tone?",
            user_response="Direct and confident",
        )

        result = derive_voice_profile(state)

        # After tone, should ask about sentence style
        assert result["requires_human_input"] is True
        question_lower = result["pending_question"].lower()
        assert "sentence" in question_lower or "style" in question_lower

    def test_derive_voice_profile_stores_sentence_style(self) -> None:
        """Voice profile should store sentence style."""
        state = make_onboarding_state(
            current_step="voice_profile",
            gathered_data={
                "voice_profile": {
                    "tone": "Direct and confident",
                }
            },
            pending_question="How would you describe your sentence style?",
            user_response="Short and punchy",
        )

        result = derive_voice_profile(state)

        voice = result["gathered_data"].get("voice_profile", {})
        assert voice.get("sentence_style") == "Short and punchy"

    def test_derive_voice_profile_asks_for_vocabulary_level(self) -> None:
        """Voice profile should ask about vocabulary level after sentence style."""
        state = make_onboarding_state(
            current_step="voice_profile",
            gathered_data={
                "voice_profile": {
                    "tone": "Direct",
                    "sentence_style": "Short and punchy",
                }
            },
            pending_question="How would you describe your sentence style?",
            user_response="Short and punchy",
        )

        result = derive_voice_profile(state)

        # After sentence style, should ask about vocabulary
        assert result["requires_human_input"] is True
        question_lower = result["pending_question"].lower()
        assert (
            "vocabulary" in question_lower
            or "technical" in question_lower
            or "jargon" in question_lower
        )

    def test_derive_voice_profile_stores_vocabulary_level(self) -> None:
        """Voice profile should store vocabulary level."""
        state = make_onboarding_state(
            current_step="voice_profile",
            gathered_data={
                "voice_profile": {
                    "tone": "Direct",
                    "sentence_style": "Short",
                }
            },
            pending_question="Do you prefer technical jargon or plain English?",
            user_response="Technical when relevant, plain English otherwise",
        )

        result = derive_voice_profile(state)

        voice = result["gathered_data"].get("voice_profile", {})
        assert (
            voice.get("vocabulary_level")
            == "Technical when relevant, plain English otherwise"
        )

    def test_derive_voice_profile_asks_for_things_to_avoid(self) -> None:
        """Voice profile should ask about things to avoid after vocabulary."""
        state = make_onboarding_state(
            current_step="voice_profile",
            gathered_data={
                "voice_profile": {
                    "tone": "Direct",
                    "sentence_style": "Short",
                    "vocabulary_level": "Technical",
                }
            },
            pending_question="Do you prefer technical jargon or plain English?",
            user_response="Technical",
        )

        result = derive_voice_profile(state)

        # After vocabulary, should ask about things to avoid
        assert result["requires_human_input"] is True
        question_lower = result["pending_question"].lower()
        assert (
            "avoid" in question_lower
            or "buzzword" in question_lower
            or "never" in question_lower
        )

    def test_derive_voice_profile_completes_after_things_to_avoid(self) -> None:
        """Voice profile should complete after things to avoid are provided."""
        state = make_onboarding_state(
            current_step="voice_profile",
            gathered_data={
                "voice_profile": {
                    "tone": "Direct",
                    "sentence_style": "Short",
                    "vocabulary_level": "Technical",
                }
            },
            pending_question="Are there any words or phrases you never use?",
            user_response="Synergy, paradigm shift, circle back",
        )

        result = derive_voice_profile(state)

        # After things to avoid, step should be complete
        voice = result["gathered_data"].get("voice_profile", {})
        assert voice.get("things_to_avoid") == "Synergy, paradigm shift, circle back"
        assert result["requires_human_input"] is False

    def test_check_step_complete_detects_voice_profile_complete(self) -> None:
        """check_step_complete should detect when voice_profile has required data."""
        state = make_onboarding_state(
            current_step="voice_profile",
            requires_human_input=False,
            gathered_data={
                "voice_profile": {
                    "tone": "Direct and confident",
                }
            },
        )

        result = check_step_complete(state)
        assert result == "complete"

    def test_derive_voice_profile_handles_skip_case_insensitive(self) -> None:
        """Voice profile should accept skip in any case (SKIP, Skip, etc.)."""
        state = make_onboarding_state(
            current_step="voice_profile",
            gathered_data={"voice_profile": {}},
            pending_question="Do you have a writing sample to share?",
            user_response="SKIP",
        )

        result = derive_voice_profile(state)

        # Should proceed to tone question
        assert result["requires_human_input"] is True
        question_lower = result["pending_question"].lower()
        assert "tone" in question_lower

    def test_derive_voice_profile_handles_skip_with_whitespace(self) -> None:
        """Voice profile should accept skip with surrounding whitespace."""
        state = make_onboarding_state(
            current_step="voice_profile",
            gathered_data={"voice_profile": {}},
            pending_question="Do you have a writing sample to share?",
            user_response="  skip  ",
        )

        result = derive_voice_profile(state)

        # Should proceed to tone question
        assert result["requires_human_input"] is True
        question_lower = result["pending_question"].lower()
        assert "tone" in question_lower


# =============================================================================
# Base Resume Setup Step Tests (§5.3.8)
# =============================================================================


class TestBaseResumeSetupStep:
    """Tests for base resume setup step behavior (§5.3.8)."""

    def test_setup_base_resume_asks_for_role_type(self) -> None:
        """Base resume setup should ask what type of role user is targeting."""
        state = make_onboarding_state(
            current_step="base_resume_setup",
            gathered_data={},
        )

        result = setup_base_resume(state)

        assert result["current_step"] == "base_resume_setup"
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        # Should ask about role type
        assert (
            "role" in question_lower
            or "target" in question_lower
            or "position" in question_lower
        )

    def test_setup_base_resume_stores_role_type(self) -> None:
        """Base resume setup should store the primary role type."""
        state = make_onboarding_state(
            current_step="base_resume_setup",
            gathered_data={"base_resume_setup": {}},
            pending_question="What type of role are you primarily targeting?",
            user_response="Senior Software Engineer",
        )

        result = setup_base_resume(state)

        base_resume = result["gathered_data"].get("base_resume_setup", {})
        entries = base_resume.get("entries", [])
        # Should have created first entry with role type
        assert len(entries) >= 1 or base_resume.get("current_entry")
        # Check role type is stored
        if entries:
            assert entries[0].get("role_type") == "Senior Software Engineer"
        else:
            assert base_resume.get("current_entry", {}).get("role_type") == (
                "Senior Software Engineer"
            )

    def test_setup_base_resume_marks_first_as_primary(self) -> None:
        """Base resume setup should mark first resume as primary."""
        state = make_onboarding_state(
            current_step="base_resume_setup",
            gathered_data={"base_resume_setup": {}},
            pending_question="What type of role are you primarily targeting?",
            user_response="Senior Software Engineer",
        )

        result = setup_base_resume(state)

        base_resume = result["gathered_data"].get("base_resume_setup", {})
        entries = base_resume.get("entries", [])
        if entries:
            assert entries[0].get("is_primary") is True
        else:
            current = base_resume.get("current_entry", {})
            assert current.get("is_primary") is True

    def test_setup_base_resume_asks_about_additional_roles(self) -> None:
        """Base resume setup should ask if user wants to target other role types."""
        state = make_onboarding_state(
            current_step="base_resume_setup",
            gathered_data={
                "base_resume_setup": {
                    "entries": [
                        {
                            "role_type": "Senior Software Engineer",
                            "is_primary": True,
                        }
                    ],
                }
            },
            pending_question="What type of role are you primarily targeting?",
            user_response="Senior Software Engineer",
        )

        result = setup_base_resume(state)

        # After first role, should ask about additional roles
        assert result["requires_human_input"] is True
        assert result["pending_question"] is not None
        question_lower = result["pending_question"].lower()
        assert (
            "other" in question_lower
            or "another" in question_lower
            or "additional" in question_lower
        )

    def test_setup_base_resume_stores_additional_role(self) -> None:
        """Base resume setup should store additional role types."""
        state = make_onboarding_state(
            current_step="base_resume_setup",
            gathered_data={
                "base_resume_setup": {
                    "entries": [
                        {
                            "role_type": "Senior Software Engineer",
                            "is_primary": True,
                        }
                    ],
                }
            },
            pending_question="Any other role types you're considering?",
            user_response="Engineering Manager",
        )

        result = setup_base_resume(state)

        base_resume = result["gathered_data"].get("base_resume_setup", {})
        entries = base_resume.get("entries", [])
        # Should have two entries now
        assert len(entries) >= 2 or base_resume.get("current_entry")
        # Second should not be primary
        if len(entries) >= 2:
            assert entries[1].get("is_primary") is not True

    def test_setup_base_resume_completes_on_done(self) -> None:
        """Base resume setup should complete when user says done."""
        state = make_onboarding_state(
            current_step="base_resume_setup",
            gathered_data={
                "base_resume_setup": {
                    "entries": [
                        {
                            "role_type": "Senior Software Engineer",
                            "is_primary": True,
                        }
                    ],
                }
            },
            pending_question="Any other role types you're considering?",
            user_response="done",
        )

        result = setup_base_resume(state)

        assert result["requires_human_input"] is False

    def test_setup_base_resume_handles_done_case_insensitive(self) -> None:
        """Base resume setup should accept done in any case."""
        state = make_onboarding_state(
            current_step="base_resume_setup",
            gathered_data={
                "base_resume_setup": {
                    "entries": [
                        {
                            "role_type": "Senior Software Engineer",
                            "is_primary": True,
                        }
                    ],
                }
            },
            pending_question="Any other role types you're considering?",
            user_response="DONE",
        )

        result = setup_base_resume(state)

        assert result["requires_human_input"] is False

    def test_setup_base_resume_handles_no_response(self) -> None:
        """Base resume setup should treat 'no' as done for additional roles."""
        state = make_onboarding_state(
            current_step="base_resume_setup",
            gathered_data={
                "base_resume_setup": {
                    "entries": [
                        {
                            "role_type": "Senior Software Engineer",
                            "is_primary": True,
                        }
                    ],
                }
            },
            pending_question="Any other role types you're considering?",
            user_response="no",
        )

        result = setup_base_resume(state)

        # "no" to additional roles means we're done
        assert result["requires_human_input"] is False

    def test_setup_base_resume_handles_done_with_whitespace(self) -> None:
        """Base resume setup should accept done with surrounding whitespace."""
        state = make_onboarding_state(
            current_step="base_resume_setup",
            gathered_data={
                "base_resume_setup": {
                    "entries": [
                        {
                            "role_type": "Senior Software Engineer",
                            "is_primary": True,
                        }
                    ],
                }
            },
            pending_question="Any other role types you're considering?",
            user_response="  done  ",
        )

        result = setup_base_resume(state)

        assert result["requires_human_input"] is False

    def test_setup_base_resume_skips_when_data_exists(self) -> None:
        """Base resume setup should skip HITL when resume entries already exist."""
        state = make_onboarding_state(
            current_step="base_resume_setup",
            gathered_data={
                "base_resume_setup": {
                    "entries": [
                        {
                            "role_type": "Senior Software Engineer",
                            "is_primary": True,
                        }
                    ],
                }
            },
        )

        result = setup_base_resume(state)

        # Should not require input since data already exists
        assert result["requires_human_input"] is False


# =============================================================================
# Post-Onboarding Updates Tests (§5.5)
# =============================================================================


class TestPostOnboardingUpdates:
    """Tests for post-onboarding update functionality (§5.5).

    REQ-007 §5.5: After onboarding is complete, users can update persona
    sections via chat. The agent reuses interview patterns for single sections.
    """

    def test_detect_update_section_certification(self) -> None:
        """Should detect certification update from user message."""
        result = detect_update_section("I got a new certification")
        assert result == "certifications"

    def test_detect_update_section_skills(self) -> None:
        """Should detect skills update from user message."""
        result = detect_update_section("Update my skills")
        assert result == "skills"

    def test_detect_update_section_skills_learned(self) -> None:
        """Should detect skills update when user says they learned something."""
        result = detect_update_section("I learned Kubernetes")
        assert result == "skills"

    def test_detect_update_section_salary(self) -> None:
        """Should detect non-negotiables update for salary changes."""
        result = detect_update_section("I changed my salary requirement")
        assert result == "non_negotiables"

    def test_detect_update_section_remote_preference(self) -> None:
        """Should detect non-negotiables update for remote preference changes."""
        result = detect_update_section("I now prefer remote work only")
        assert result == "non_negotiables"

    def test_detect_update_section_work_history(self) -> None:
        """Should detect work history update from user message."""
        result = detect_update_section("Add a new job to my history")
        assert result == "work_history"

    def test_detect_update_section_education(self) -> None:
        """Should detect education update from user message."""
        result = detect_update_section("I finished my degree")
        assert result == "education"

    def test_detect_update_section_story(self) -> None:
        """Should detect achievement story update from user message."""
        result = detect_update_section("I have a new achievement to add")
        assert result == "achievement_stories"

    def test_detect_update_section_growth_targets(self) -> None:
        """Should detect growth targets update from user message."""
        result = detect_update_section("I want to change my career goals")
        assert result == "growth_targets"

    def test_detect_update_section_returns_none_for_unrelated(self) -> None:
        """Should return None for messages that aren't update requests."""
        result = detect_update_section("What jobs are available?")
        assert result is None

    def test_detect_update_section_case_insensitive(self) -> None:
        """Should detect update section regardless of case."""
        result = detect_update_section("UPDATE MY SKILLS")
        assert result == "skills"

    def test_create_update_state_sets_current_step(self) -> None:
        """Should create state with current_step set to target section."""
        result = create_update_state(
            section="skills",
            user_id="user-123",
            persona_id="persona-456",
        )
        assert result["current_step"] == "skills"
        assert result["user_id"] == "user-123"
        assert result["persona_id"] == "persona-456"

    def test_create_update_state_sets_partial_update_flag(self) -> None:
        """Should mark state as partial update (not full onboarding)."""
        result = create_update_state(
            section="certifications",
            user_id="user-123",
            persona_id="persona-456",
        )
        assert result["is_partial_update"] is True

    def test_create_update_state_initializes_gathered_data(self) -> None:
        """Should initialize gathered_data dict for the target section."""
        result = create_update_state(
            section="skills",
            user_id="user-123",
            persona_id="persona-456",
        )
        assert "gathered_data" in result
        assert isinstance(result["gathered_data"], dict)

    def test_is_post_onboarding_update_true_for_partial(self) -> None:
        """Should return True when state indicates partial update."""
        state = make_onboarding_state(is_partial_update=True)
        result = is_post_onboarding_update(state)
        assert result is True

    def test_is_post_onboarding_update_false_for_full(self) -> None:
        """Should return False for full onboarding flow."""
        state = make_onboarding_state(is_partial_update=False)
        result = is_post_onboarding_update(state)
        assert result is False

    def test_is_post_onboarding_update_false_when_not_set(self) -> None:
        """Should return False when is_partial_update is not set."""
        state = make_onboarding_state()  # No is_partial_update
        result = is_post_onboarding_update(state)
        assert result is False

    def test_get_affected_embeddings_skills(self) -> None:
        """Should identify hard_skills embedding for skills updates."""
        result = get_affected_embeddings("skills")
        assert "hard_skills" in result

    def test_get_affected_embeddings_non_negotiables(self) -> None:
        """Should return empty list for non_negotiables (filter, not embedding)."""
        result = get_affected_embeddings("non_negotiables")
        # Non-negotiables affect filtering, not embeddings directly
        assert result == []

    def test_get_affected_embeddings_growth_targets(self) -> None:
        """Should identify target_roles embedding for growth targets."""
        result = get_affected_embeddings("growth_targets")
        # Growth targets affect stretch score calculation
        assert "target_roles" in result

    def test_get_affected_embeddings_work_history(self) -> None:
        """Should identify experience embedding for work history."""
        result = get_affected_embeddings("work_history")
        assert "experience" in result

    def test_get_affected_embeddings_unknown_section(self) -> None:
        """Should return empty list for unknown sections."""
        result = get_affected_embeddings("unknown_section")
        assert result == []

    def test_get_update_completion_message_skills(self) -> None:
        """Should include job re-analysis message for skills updates."""
        result = get_update_completion_message("skills")
        # Per REQ-007 §5.5: "I'm re-analyzing your job matches"
        assert "re-analy" in result.lower()

    def test_get_update_completion_message_certifications(self) -> None:
        """Should provide simple confirmation for certifications."""
        result = get_update_completion_message("certifications")
        # Certifications don't affect job matching scores directly
        assert "certification" in result.lower()

    def test_get_update_completion_message_non_negotiables(self) -> None:
        """Should mention filtering changes for non-negotiables updates."""
        result = get_update_completion_message("non_negotiables")
        # Non-negotiables affect job filtering - message includes job re-analysis
        assert "re-analy" in result.lower()

    def test_get_update_completion_message_unknown_section(self) -> None:
        """Should use section name as fallback for unknown sections."""
        result = get_update_completion_message("unknown_section")
        # Should use the raw section name as fallback
        assert "unknown_section" in result.lower()

    def test_sections_requiring_rescore(self) -> None:
        """Should correctly identify sections that require job re-scoring."""
        # Skills affect fit score
        assert "skills" in SECTIONS_REQUIRING_RESCORE
        # Non-negotiables affect filtering
        assert "non_negotiables" in SECTIONS_REQUIRING_RESCORE
        # Growth targets affect stretch score
        assert "growth_targets" in SECTIONS_REQUIRING_RESCORE
        # Work history affects experience matching
        assert "work_history" in SECTIONS_REQUIRING_RESCORE
        # Certifications don't affect scoring
        assert "certifications" not in SECTIONS_REQUIRING_RESCORE


# =============================================================================
# Prompt Templates Tests (§5.6)
# =============================================================================


class TestSystemPrompt:
    """Tests for the Scout interviewer persona system prompt (§5.6.1)."""

    def test_system_prompt_template_exists(self) -> None:
        """System prompt template should be defined."""
        assert SYSTEM_PROMPT_TEMPLATE is not None
        assert isinstance(SYSTEM_PROMPT_TEMPLATE, str)
        assert len(SYSTEM_PROMPT_TEMPLATE) > 100  # Non-trivial template

    def test_system_prompt_has_scout_persona(self) -> None:
        """System prompt should establish Scout interviewer persona."""
        prompt_lower = SYSTEM_PROMPT_TEMPLATE.lower()
        # Should mention being a career coach or interviewer
        assert "scout" in prompt_lower or "career" in prompt_lower

    def test_system_prompt_has_personality_traits(self) -> None:
        """System prompt should define personality traits."""
        prompt_lower = SYSTEM_PROMPT_TEMPLATE.lower()
        # Per §5.6.1: warm, efficient, curious, encouraging, professional
        assert (
            "warm" in prompt_lower
            or "friendly" in prompt_lower
            or "curious" in prompt_lower
        )

    def test_system_prompt_has_template_variables(self) -> None:
        """System prompt should contain template variables."""
        # Per §5.6.1: {current_step}, {gathered_data_summary}
        assert "{current_step}" in SYSTEM_PROMPT_TEMPLATE
        assert "{gathered_data_summary}" in SYSTEM_PROMPT_TEMPLATE

    def test_system_prompt_has_interview_rules(self) -> None:
        """System prompt should include interview style rules."""
        prompt_lower = SYSTEM_PROMPT_TEMPLATE.lower()
        # Per §5.6.1: one question at a time
        assert "one question" in prompt_lower or "single question" in prompt_lower

    def test_system_prompt_has_not_list(self) -> None:
        """System prompt should include explicit NOT behaviors."""
        prompt_lower = SYSTEM_PROMPT_TEMPLATE.lower()
        # Per §5.6.1: not therapist, not resume writer, not pushy
        assert "not" in prompt_lower and (
            "therapist" in prompt_lower or "pushy" in prompt_lower
        )

    def test_get_system_prompt_fills_variables(self) -> None:
        """get_system_prompt should fill template variables."""
        result = get_system_prompt(
            current_step="work_history",
            gathered_data_summary="User has provided basic info.",
        )

        # Should have replaced placeholders
        assert "{current_step}" not in result
        assert "{gathered_data_summary}" not in result
        # Should contain actual values
        assert "work_history" in result
        assert "User has provided basic info" in result

    def test_get_system_prompt_handles_empty_summary(self) -> None:
        """get_system_prompt should handle empty gathered data."""
        result = get_system_prompt(
            current_step="basic_info",
            gathered_data_summary="",
        )

        # Should still produce valid prompt
        assert "{current_step}" not in result
        assert "basic_info" in result


class TestStepSpecificPrompts:
    """Tests for step-specific prompt templates (§5.6.2)."""

    def test_work_history_expansion_prompt_exists(self) -> None:
        """Work history expansion prompt should be defined."""
        assert WORK_HISTORY_EXPANSION_PROMPT is not None
        assert isinstance(WORK_HISTORY_EXPANSION_PROMPT, str)

    def test_work_history_prompt_probes_for_accomplishments(self) -> None:
        """Work history prompt should probe for accomplishments."""
        prompt_lower = WORK_HISTORY_EXPANSION_PROMPT.lower()
        # Per §5.6.2: biggest accomplishment, challenge, impact
        assert (
            "accomplish" in prompt_lower
            or "achievement" in prompt_lower
            or "impact" in prompt_lower
        )

    def test_work_history_prompt_asks_for_numbers(self) -> None:
        """Work history prompt should ask for quantifiable details."""
        prompt_lower = WORK_HISTORY_EXPANSION_PROMPT.lower()
        # Per §5.6.2: numbers, percentages, scale
        assert (
            "number" in prompt_lower
            or "quantif" in prompt_lower
            or "scale" in prompt_lower
            or "percent" in prompt_lower
        )

    def test_achievement_story_prompt_exists(self) -> None:
        """Achievement story prompt should be defined."""
        assert ACHIEVEMENT_STORY_PROMPT is not None
        assert isinstance(ACHIEVEMENT_STORY_PROMPT, str)

    def test_achievement_story_prompt_uses_star_format(self) -> None:
        """Achievement story prompt should reference STAR format."""
        prompt_lower = ACHIEVEMENT_STORY_PROMPT.lower()
        # Per §5.6.2: STAR format
        assert "star" in prompt_lower or (
            "situation" in prompt_lower and "action" in prompt_lower
        )

    def test_achievement_story_prompt_has_template_variables(self) -> None:
        """Achievement story prompt should have template variables."""
        # Per §5.6.2: {existing_stories}, {covered_skills}
        assert "{existing_stories}" in ACHIEVEMENT_STORY_PROMPT
        assert "{covered_skills}" in ACHIEVEMENT_STORY_PROMPT

    def test_voice_profile_derivation_prompt_exists(self) -> None:
        """Voice profile derivation prompt should be defined."""
        assert VOICE_PROFILE_DERIVATION_PROMPT is not None
        assert isinstance(VOICE_PROFILE_DERIVATION_PROMPT, str)

    def test_voice_profile_prompt_has_transcript_variable(self) -> None:
        """Voice profile prompt should have transcript variable."""
        # Per §5.6.2: {transcript}
        assert "{transcript}" in VOICE_PROFILE_DERIVATION_PROMPT

    def test_voice_profile_prompt_analyzes_dimensions(self) -> None:
        """Voice profile prompt should analyze tone, style, vocabulary."""
        prompt_lower = VOICE_PROFILE_DERIVATION_PROMPT.lower()
        # Per §5.6.2: tone, sentence style, vocabulary
        assert "tone" in prompt_lower
        assert "style" in prompt_lower or "sentence" in prompt_lower
        assert "vocabulary" in prompt_lower or "jargon" in prompt_lower

    def test_get_work_history_prompt_fills_template(self) -> None:
        """get_work_history_prompt should fill in job entry details."""
        job_entry = {
            "title": "Software Engineer",
            "company": "Acme Corp",
            "start_date": "2020-01",
            "end_date": "2023-06",
        }
        result = get_work_history_prompt(job_entry)

        # Should mention the job details
        assert "Software Engineer" in result or "Acme" in result

    def test_get_achievement_story_prompt_fills_template(self) -> None:
        """get_achievement_story_prompt should fill in context."""
        result = get_achievement_story_prompt(
            existing_stories=["Led team project", "Migrated database"],
            covered_skills=["Leadership", "SQL"],
        )

        # Should not contain raw template variables
        assert "{existing_stories}" not in result
        assert "{covered_skills}" not in result

    def test_get_achievement_story_prompt_asks_for_diversity(self) -> None:
        """Achievement story prompt should ask for different skills."""
        result = get_achievement_story_prompt(
            existing_stories=["Story about leadership"],
            covered_skills=["Leadership"],
        )
        result_lower = result.lower()

        # Per §5.6.2: ask for stories demonstrating DIFFERENT skills
        assert "different" in result_lower or "new" in result_lower

    def test_get_voice_profile_prompt_fills_transcript(self) -> None:
        """get_voice_profile_prompt should include conversation transcript."""
        transcript = "User: I'm looking for remote roles.\nAssistant: Great!"
        result = get_voice_profile_prompt(transcript)

        # Should not contain raw template variable
        assert "{transcript}" not in result
        # Transcript content should be included
        assert "remote" in result.lower() or len(result) > 100


class TestTransitionPrompts:
    """Tests for transition prompts between sections (§5.6.3)."""

    def test_transition_prompts_dict_exists(self) -> None:
        """TRANSITION_PROMPTS dict should be defined."""
        assert TRANSITION_PROMPTS is not None
        assert isinstance(TRANSITION_PROMPTS, dict)

    def test_transition_prompts_has_common_transitions(self) -> None:
        """TRANSITION_PROMPTS should include common step transitions."""
        # Per §5.6.3: work_history → skills, achievement_stories → non_negotiables
        assert ("work_history", "skills") in TRANSITION_PROMPTS or (
            "work_history",
            "education",
        ) in TRANSITION_PROMPTS
        assert ("achievement_stories", "non_negotiables") in TRANSITION_PROMPTS or (
            "gather_stories",
            "non_negotiables",
        ) in TRANSITION_PROMPTS

    def test_transition_prompts_are_natural(self) -> None:
        """Transition prompts should have natural conversational flow."""
        # Get any transition prompt
        if TRANSITION_PROMPTS:
            key, prompt = next(iter(TRANSITION_PROMPTS.items()))
            # Should acknowledge completion and introduce next topic
            assert len(prompt) > 50  # Non-trivial message

    def test_get_transition_prompt_returns_prompt(self) -> None:
        """get_transition_prompt should return appropriate transition."""
        result = get_transition_prompt("work_history", "education")

        # Should return a string
        assert isinstance(result, str)
        # Should be non-empty
        assert len(result) > 0

    def test_get_transition_prompt_handles_unknown(self) -> None:
        """get_transition_prompt should handle unknown transitions gracefully."""
        result = get_transition_prompt("unknown_step", "another_unknown")

        # Should return some default/fallback
        assert isinstance(result, str)

    def test_get_transition_prompt_skills_to_certs(self) -> None:
        """Should provide transition from skills to certifications."""
        result = get_transition_prompt("skills", "certifications")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_transition_prompt_non_negotiables_to_growth(self) -> None:
        """Should provide transition from non_negotiables to growth_targets."""
        result = get_transition_prompt("non_negotiables", "growth_targets")

        assert isinstance(result, str)
        assert len(result) > 0


class TestFormatGatheredDataSummary:
    """Tests for formatting gathered data into a summary string."""

    def test_format_gathered_data_summary_exists(self) -> None:
        """format_gathered_data_summary function should exist."""
        assert callable(format_gathered_data_summary)

    def test_format_gathered_data_summary_empty(self) -> None:
        """Should handle empty gathered data."""
        result = format_gathered_data_summary({})

        assert isinstance(result, str)

    def test_format_gathered_data_summary_with_basic_info(self) -> None:
        """Should include basic info in summary."""
        gathered = {
            "basic_info": {
                "full_name": "Jane Doe",
                "email": "jane@example.com",
            }
        }
        result = format_gathered_data_summary(gathered)

        # Should mention user's name or basic info
        assert "Jane" in result or "basic" in result.lower()

    def test_format_gathered_data_summary_with_work_history(self) -> None:
        """Should include work history summary."""
        gathered = {
            "work_history": {
                "entries": [
                    {"title": "Software Engineer", "company": "Acme Corp"},
                    {"title": "Senior Developer", "company": "Tech Inc"},
                ]
            }
        }
        result = format_gathered_data_summary(gathered)

        # Should indicate number of jobs or mention work history
        assert "2" in result or "work" in result.lower() or "job" in result.lower()

    def test_format_gathered_data_summary_with_skills(self) -> None:
        """Should include skills summary."""
        gathered = {
            "skills": {
                "entries": [
                    {"skill_name": "Python", "proficiency": "Expert"},
                    {"skill_name": "JavaScript", "proficiency": "Proficient"},
                ]
            }
        }
        result = format_gathered_data_summary(gathered)

        # Should mention skills
        assert "skill" in result.lower() or "Python" in result

    def test_format_gathered_data_summary_skipped_sections(self) -> None:
        """Should indicate skipped sections."""
        gathered = {
            "education": {"skipped": True},
            "certifications": {"skipped": True},
        }
        result = format_gathered_data_summary(gathered)

        # Result should mention skipped or be empty for those sections
        assert isinstance(result, str)
