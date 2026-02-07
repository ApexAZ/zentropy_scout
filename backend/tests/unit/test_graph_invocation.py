"""Tests for graph invocation patterns.

REQ-007 §15.6: Graph Invocation Patterns.

Tests the Chat Agent's sub-graph delegation: how it constructs target
agent state from its own state, invokes the sub-graph, and captures
the result in tool_results.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.chat import delegate_ghostwriter, delegate_onboarding
from app.agents.state import ChatAgentState

_USER_ID = "user-123"
_PERSONA_ID = "persona-456"
_JOB_ID = "job-789"
_PATCH_GENERATE_MATERIALS = "app.agents.chat.generate_materials"
_PATCH_GET_ONBOARDING_GRAPH = "app.agents.chat.get_onboarding_graph"


def _make_chat_state(
    *,
    user_id: str = _USER_ID,
    persona_id: str = _PERSONA_ID,
    target_job_id: str | None = _JOB_ID,
    current_message: str | None = "Draft materials for this job",
) -> ChatAgentState:
    """Build a minimal ChatAgentState for delegation tests."""
    return {
        "user_id": user_id,
        "persona_id": persona_id,
        "messages": [{"role": "user", "content": "Help me"}],
        "current_message": current_message,
        "tool_calls": [],
        "tool_results": [],
        "next_action": None,
        "requires_human_input": False,
        "checkpoint_reason": None,
        "classified_intent": None,
        "target_job_id": target_job_id,
    }


# =============================================================================
# delegate_ghostwriter
# =============================================================================


class TestDelegateGhostwriter:
    """delegate_ghostwriter invokes Ghostwriter sub-graph via generate_materials."""

    @pytest.mark.asyncio
    async def test_calls_generate_materials_with_mapped_state(self) -> None:
        """Passes user_id, persona_id, job_posting_id, and trigger_type."""
        mock_gen = AsyncMock(return_value={"generated_resume": "resume"})
        with patch(_PATCH_GENERATE_MATERIALS, mock_gen):
            await delegate_ghostwriter(_make_chat_state())

        mock_gen.assert_called_once_with(
            user_id=_USER_ID,
            persona_id=_PERSONA_ID,
            job_posting_id=_JOB_ID,
            trigger_type="manual_request",
        )

    @pytest.mark.asyncio
    async def test_success_populates_tool_results(self) -> None:
        """Successful invocation stores completed status and content flags."""
        mock_gen = AsyncMock(
            return_value={
                "generated_resume": {"content": "tailored resume"},
                "generated_cover_letter": {"content": "cover letter"},
            }
        )
        with patch(_PATCH_GENERATE_MATERIALS, mock_gen):
            result = await delegate_ghostwriter(_make_chat_state())

        tool_results = result["tool_results"]
        assert len(tool_results) == 1
        assert tool_results[0]["tool"] == "invoke_ghostwriter"
        assert tool_results[0]["error"] is None
        assert tool_results[0]["result"]["status"] == "completed"
        assert tool_results[0]["result"]["has_resume"] is True
        assert tool_results[0]["result"]["has_cover_letter"] is True

    @pytest.mark.asyncio
    async def test_partial_generation_flags(self) -> None:
        """Reports has_resume=True, has_cover_letter=False for resume-only."""
        mock_gen = AsyncMock(
            return_value={
                "generated_resume": {"content": "resume"},
                "generated_cover_letter": None,
            }
        )
        with patch(_PATCH_GENERATE_MATERIALS, mock_gen):
            result = await delegate_ghostwriter(_make_chat_state())

        data = result["tool_results"][0]["result"]
        assert data["has_resume"] is True
        assert data["has_cover_letter"] is False

    @pytest.mark.asyncio
    async def test_missing_target_job_returns_error(self) -> None:
        """Missing target_job_id produces an error without calling sub-graph."""
        mock_gen = AsyncMock()
        with patch(_PATCH_GENERATE_MATERIALS, mock_gen):
            result = await delegate_ghostwriter(_make_chat_state(target_job_id=None))

        mock_gen.assert_not_called()
        tool_results = result["tool_results"]
        assert len(tool_results) == 1
        assert tool_results[0]["error"] is not None
        assert "job" in tool_results[0]["error"].lower()

    @pytest.mark.asyncio
    async def test_exception_returns_safe_error_message(self) -> None:
        """Sub-graph exception does not leak internals to user."""
        mock_gen = AsyncMock(side_effect=RuntimeError("DB connection refused"))
        with patch(_PATCH_GENERATE_MATERIALS, mock_gen):
            result = await delegate_ghostwriter(_make_chat_state())

        tool_results = result["tool_results"]
        assert len(tool_results) == 1
        assert tool_results[0]["tool"] == "invoke_ghostwriter"
        assert tool_results[0]["result"] is None
        # Error message must be generic — no internal details leaked
        assert "DB connection refused" not in tool_results[0]["error"]
        assert tool_results[0]["error"] is not None

    @pytest.mark.asyncio
    async def test_does_not_mutate_input_state(self) -> None:
        """Delegate returns new state, does not mutate the input."""
        state = _make_chat_state()
        original_results = state["tool_results"]
        mock_gen = AsyncMock(return_value={"generated_resume": "r"})
        with patch(_PATCH_GENERATE_MATERIALS, mock_gen):
            result = await delegate_ghostwriter(state)

        assert result is not state
        assert state["tool_results"] is original_results
        assert len(original_results) == 0


# =============================================================================
# delegate_onboarding
# =============================================================================


class TestDelegateOnboarding:
    """delegate_onboarding invokes Onboarding sub-graph."""

    @pytest.mark.asyncio
    async def test_invokes_onboarding_graph(self) -> None:
        """Calls ainvoke on the compiled onboarding graph."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "current_step": "complete",
                "gathered_data": {"basic_info": {}},
            }
        )
        with patch(_PATCH_GET_ONBOARDING_GRAPH, return_value=mock_graph):
            await delegate_onboarding(_make_chat_state())

        mock_graph.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_maps_fields_to_onboarding_state(self) -> None:
        """Passes user_id, persona_id, messages, and current_message."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={})
        with patch(_PATCH_GET_ONBOARDING_GRAPH, return_value=mock_graph):
            await delegate_onboarding(_make_chat_state())

        call_args = mock_graph.ainvoke.call_args[0][0]
        assert call_args["user_id"] == _USER_ID
        assert call_args["persona_id"] == _PERSONA_ID
        assert call_args["messages"] == [{"role": "user", "content": "Help me"}]
        assert call_args["current_message"] == "Draft materials for this job"

    @pytest.mark.asyncio
    async def test_success_populates_tool_results(self) -> None:
        """Successful invocation stores result in tool_results."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={"current_step": "complete"})
        with patch(_PATCH_GET_ONBOARDING_GRAPH, return_value=mock_graph):
            result = await delegate_onboarding(_make_chat_state())

        tool_results = result["tool_results"]
        assert len(tool_results) == 1
        assert tool_results[0]["tool"] == "invoke_onboarding"
        assert tool_results[0]["error"] is None
        assert tool_results[0]["result"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_exception_returns_safe_error_message(self) -> None:
        """Sub-graph exception does not leak internals to user."""
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(
            side_effect=RuntimeError("Internal error details")
        )
        with patch(_PATCH_GET_ONBOARDING_GRAPH, return_value=mock_graph):
            result = await delegate_onboarding(_make_chat_state())

        tool_results = result["tool_results"]
        assert len(tool_results) == 1
        assert tool_results[0]["tool"] == "invoke_onboarding"
        assert tool_results[0]["result"] is None
        # Error message must be generic — no internal details leaked
        assert "Internal error details" not in tool_results[0]["error"]
        assert tool_results[0]["error"] is not None

    @pytest.mark.asyncio
    async def test_does_not_mutate_input_state(self) -> None:
        """Delegate returns new state, does not mutate the input."""
        state = _make_chat_state()
        original_results = state["tool_results"]
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(return_value={})
        with patch(_PATCH_GET_ONBOARDING_GRAPH, return_value=mock_graph):
            result = await delegate_onboarding(state)

        assert result is not state
        assert state["tool_results"] is original_results
        assert len(original_results) == 0
