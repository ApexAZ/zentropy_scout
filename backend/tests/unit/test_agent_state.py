"""Tests for LangGraph agent state schemas.

REQ-007 §3.2: State Schema
REQ-007 §3.3: Checkpointing & HITL

These tests verify:
- BaseAgentState has all required fields
- Agent-specific state schemas extend BaseAgentState correctly
- State validation works as expected
- Checkpoint utilities work correctly
"""

from typing import get_type_hints

from app.agents.state import (
    BaseAgentState,
    ChatAgentState,
    CheckpointReason,
    GhostwriterState,
    OnboardingState,
    ScouterState,
    StrategistState,
)

# =============================================================================
# BaseAgentState Tests
# =============================================================================


class TestBaseAgentState:
    """Tests for the base agent state schema."""

    def test_has_user_context_fields(self):
        """BaseAgentState must have user_id and persona_id fields."""
        hints = get_type_hints(BaseAgentState)
        assert "user_id" in hints
        assert "persona_id" in hints

    def test_has_conversation_fields(self):
        """BaseAgentState must have messages and current_message fields."""
        hints = get_type_hints(BaseAgentState)
        assert "messages" in hints
        assert "current_message" in hints

    def test_has_tool_execution_fields(self):
        """BaseAgentState must have tool_calls and tool_results fields."""
        hints = get_type_hints(BaseAgentState)
        assert "tool_calls" in hints
        assert "tool_results" in hints

    def test_has_control_flow_fields(self):
        """BaseAgentState must have HITL and control flow fields."""
        hints = get_type_hints(BaseAgentState)
        assert "next_action" in hints
        assert "requires_human_input" in hints
        assert "checkpoint_reason" in hints

    def test_can_instantiate_with_minimal_fields(self):
        """BaseAgentState can be created with required fields."""
        state: BaseAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
        }
        assert state["user_id"] == "user-123"
        assert state["requires_human_input"] is False


# =============================================================================
# CheckpointReason Tests
# =============================================================================


class TestCheckpointReason:
    """Tests for checkpoint reason enumeration."""

    def test_has_approval_needed(self):
        """CheckpointReason must have APPROVAL_NEEDED."""
        assert hasattr(CheckpointReason, "APPROVAL_NEEDED")

    def test_has_clarification_needed(self):
        """CheckpointReason must have CLARIFICATION_NEEDED."""
        assert hasattr(CheckpointReason, "CLARIFICATION_NEEDED")

    def test_has_long_running_task(self):
        """CheckpointReason must have LONG_RUNNING_TASK."""
        assert hasattr(CheckpointReason, "LONG_RUNNING_TASK")

    def test_has_error(self):
        """CheckpointReason must have ERROR."""
        assert hasattr(CheckpointReason, "ERROR")


# =============================================================================
# ChatAgentState Tests
# =============================================================================


class TestChatAgentState:
    """Tests for the chat agent state schema."""

    def test_extends_base_state(self):
        """ChatAgentState must include all BaseAgentState fields."""
        base_hints = get_type_hints(BaseAgentState)
        chat_hints = get_type_hints(ChatAgentState)

        for field in base_hints:
            assert field in chat_hints, f"ChatAgentState missing field: {field}"

    def test_has_intent_field(self):
        """ChatAgentState must have classified_intent field."""
        hints = get_type_hints(ChatAgentState)
        assert "classified_intent" in hints

    def test_has_target_fields(self):
        """ChatAgentState must have target_job_id for delegation."""
        hints = get_type_hints(ChatAgentState)
        assert "target_job_id" in hints


# =============================================================================
# OnboardingState Tests
# =============================================================================


class TestOnboardingState:
    """Tests for the onboarding agent state schema."""

    def test_extends_base_state(self):
        """OnboardingState must include all BaseAgentState fields."""
        base_hints = get_type_hints(BaseAgentState)
        onboarding_hints = get_type_hints(OnboardingState)

        for field in base_hints:
            assert field in onboarding_hints, f"OnboardingState missing field: {field}"

    def test_has_step_tracking(self):
        """OnboardingState must have current_step for resume."""
        hints = get_type_hints(OnboardingState)
        assert "current_step" in hints

    def test_has_gathered_data(self):
        """OnboardingState must have gathered_data for accumulated responses."""
        hints = get_type_hints(OnboardingState)
        assert "gathered_data" in hints

    def test_has_skip_tracking(self):
        """OnboardingState must have skipped_sections."""
        hints = get_type_hints(OnboardingState)
        assert "skipped_sections" in hints


# =============================================================================
# ScouterState Tests
# =============================================================================


class TestScouterState:
    """Tests for the scouter agent state schema."""

    def test_extends_base_state(self):
        """ScouterState must include all BaseAgentState fields."""
        base_hints = get_type_hints(BaseAgentState)
        scouter_hints = get_type_hints(ScouterState)

        for field in base_hints:
            assert field in scouter_hints, f"ScouterState missing field: {field}"

    def test_has_source_tracking(self):
        """ScouterState must have enabled_sources field."""
        hints = get_type_hints(ScouterState)
        assert "enabled_sources" in hints

    def test_has_discovered_jobs(self):
        """ScouterState must have discovered_jobs field."""
        hints = get_type_hints(ScouterState)
        assert "discovered_jobs" in hints


# =============================================================================
# StrategistState Tests
# =============================================================================


class TestStrategistState:
    """Tests for the strategist agent state schema."""

    def test_extends_base_state(self):
        """StrategistState must include all BaseAgentState fields."""
        base_hints = get_type_hints(BaseAgentState)
        strategist_hints = get_type_hints(StrategistState)

        for field in base_hints:
            assert field in strategist_hints, f"StrategistState missing field: {field}"

    def test_has_embedding_version_tracking(self):
        """StrategistState must track embedding versions for freshness."""
        hints = get_type_hints(StrategistState)
        assert "persona_embedding_version" in hints

    def test_has_jobs_to_score(self):
        """StrategistState must have jobs_to_score field."""
        hints = get_type_hints(StrategistState)
        assert "jobs_to_score" in hints

    def test_has_scored_jobs(self):
        """StrategistState must have scored_jobs field."""
        hints = get_type_hints(StrategistState)
        assert "scored_jobs" in hints


# =============================================================================
# GhostwriterState Tests
# =============================================================================


class TestGhostwriterState:
    """Tests for the ghostwriter agent state schema."""

    def test_extends_base_state(self):
        """GhostwriterState must include all BaseAgentState fields."""
        base_hints = get_type_hints(BaseAgentState)
        ghostwriter_hints = get_type_hints(GhostwriterState)

        for field in base_hints:
            assert (
                field in ghostwriter_hints
            ), f"GhostwriterState missing field: {field}"

    def test_has_job_posting_id(self):
        """GhostwriterState must have job_posting_id field."""
        hints = get_type_hints(GhostwriterState)
        assert "job_posting_id" in hints

    def test_has_selected_base_resume(self):
        """GhostwriterState must have selected_base_resume_id field."""
        hints = get_type_hints(GhostwriterState)
        assert "selected_base_resume_id" in hints

    def test_has_existing_variant_tracking(self):
        """GhostwriterState must track existing variants (race condition prevention)."""
        hints = get_type_hints(GhostwriterState)
        assert "existing_variant_id" in hints

    def test_has_generation_outputs(self):
        """GhostwriterState must have fields for generated content."""
        hints = get_type_hints(GhostwriterState)
        assert "generated_resume" in hints
        assert "generated_cover_letter" in hints
