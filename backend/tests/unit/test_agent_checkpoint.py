"""Tests for LangGraph checkpointing and HITL utilities.

REQ-007 §3.3: Checkpointing & HITL

These tests verify:
- PostgreSQL checkpointer can be configured
- Graph builder utilities work correctly
- HITL interrupt/resume patterns work
"""

from app.agents.checkpoint import (
    create_checkpointer,
    create_graph_config,
    request_human_input,
    resume_from_checkpoint,
)
from app.agents.state import BaseAgentState, CheckpointReason

# =============================================================================
# Checkpointer Tests
# =============================================================================


class TestCreateCheckpointer:
    """Tests for checkpointer creation."""

    def test_returns_checkpointer_instance(self):
        """create_checkpointer returns a checkpointer object."""
        checkpointer = create_checkpointer()
        assert checkpointer is not None

    def test_checkpointer_has_get_method(self):
        """Checkpointer must support async get for retrieving state."""
        checkpointer = create_checkpointer()
        assert hasattr(checkpointer, "aget") or hasattr(checkpointer, "get")

    def test_checkpointer_has_put_method(self):
        """Checkpointer must support async put for storing state."""
        checkpointer = create_checkpointer()
        assert hasattr(checkpointer, "aput") or hasattr(checkpointer, "put")


# =============================================================================
# Graph Config Tests
# =============================================================================


class TestCreateGraphConfig:
    """Tests for graph configuration."""

    def test_returns_config_dict(self):
        """create_graph_config returns a configuration dict."""
        config = create_graph_config(
            thread_id="test-thread-123",
            user_id="user-456",
        )
        assert isinstance(config, dict)

    def test_config_has_thread_id(self):
        """Config must include thread_id for checkpoint identification."""
        config = create_graph_config(
            thread_id="test-thread-123",
            user_id="user-456",
        )
        assert config.get("configurable", {}).get("thread_id") == "test-thread-123"

    def test_config_includes_user_id(self):
        """Config must include user_id for tenant isolation."""
        config = create_graph_config(
            thread_id="test-thread-123",
            user_id="user-456",
        )
        assert config.get("configurable", {}).get("user_id") == "user-456"


# =============================================================================
# HITL Utilities Tests
# =============================================================================


class TestRequestHumanInput:
    """Tests for HITL interrupt utility."""

    def test_sets_requires_human_input_flag(self):
        """request_human_input sets requires_human_input to True."""
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

        result = request_human_input(
            state,
            reason=CheckpointReason.APPROVAL_NEEDED,
            message="Please approve the generated content.",
        )

        assert result["requires_human_input"] is True

    def test_sets_checkpoint_reason(self):
        """request_human_input sets the checkpoint reason."""
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

        result = request_human_input(
            state,
            reason=CheckpointReason.CLARIFICATION_NEEDED,
            message="Which job are you interested in?",
        )

        assert (
            result["checkpoint_reason"] == CheckpointReason.CLARIFICATION_NEEDED.value
        )

    def test_adds_message_to_conversation(self):
        """request_human_input adds the prompt to messages."""
        state: BaseAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [{"role": "user", "content": "Hello"}],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": False,
            "checkpoint_reason": None,
        }

        result = request_human_input(
            state,
            reason=CheckpointReason.APPROVAL_NEEDED,
            message="Please approve the generated content.",
        )

        assert len(result["messages"]) == 2
        assert result["messages"][-1]["role"] == "assistant"
        assert (
            result["messages"][-1]["content"] == "Please approve the generated content."
        )


class TestResumeFromCheckpoint:
    """Tests for checkpoint resumption utility."""

    def test_clears_requires_human_input_flag(self):
        """resume_from_checkpoint clears the HITL flag."""
        state: BaseAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [
                {"role": "assistant", "content": "Please approve the content."}
            ],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": True,
            "checkpoint_reason": CheckpointReason.APPROVAL_NEEDED.value,
        }

        result = resume_from_checkpoint(
            state,
            user_response="Approved!",
        )

        assert result["requires_human_input"] is False

    def test_clears_checkpoint_reason(self):
        """resume_from_checkpoint clears the checkpoint reason."""
        state: BaseAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": True,
            "checkpoint_reason": CheckpointReason.APPROVAL_NEEDED.value,
        }

        result = resume_from_checkpoint(
            state,
            user_response="Approved!",
        )

        assert result["checkpoint_reason"] is None

    def test_adds_user_response_to_messages(self):
        """resume_from_checkpoint adds user response to messages."""
        state: BaseAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [
                {"role": "assistant", "content": "Please approve the content."}
            ],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": True,
            "checkpoint_reason": CheckpointReason.APPROVAL_NEEDED.value,
        }

        result = resume_from_checkpoint(
            state,
            user_response="Looks good, approved!",
        )

        assert len(result["messages"]) == 2
        assert result["messages"][-1]["role"] == "user"
        assert result["messages"][-1]["content"] == "Looks good, approved!"

    def test_sets_current_message(self):
        """resume_from_checkpoint sets current_message to user response."""
        state: BaseAgentState = {
            "user_id": "user-123",
            "persona_id": "persona-456",
            "messages": [],
            "current_message": None,
            "tool_calls": [],
            "tool_results": [],
            "next_action": None,
            "requires_human_input": True,
            "checkpoint_reason": CheckpointReason.CLARIFICATION_NEEDED.value,
        }

        result = resume_from_checkpoint(
            state,
            user_response="The software engineer position",
        )

        assert result["current_message"] == "The software engineer position"
