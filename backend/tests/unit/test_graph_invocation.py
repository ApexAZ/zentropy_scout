"""Tests for graph invocation patterns.

REQ-007 §15.6 / REQ-018 §7: Graph Invocation Patterns.

Tests the Chat Agent's sub-graph delegation: how it constructs target
agent state from its own state, invokes the service/sub-graph, and
captures the result in tool_results.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.chat import delegate_ghostwriter, delegate_onboarding
from app.agents.state import ChatAgentState

_USER_ID = "user-123"
_PERSONA_ID = "persona-456"
_JOB_ID = "job-789"
_PATCH_CONTENT_GEN_SERVICE = (
    "app.services.content_generation_service.ContentGenerationService"
)


def _mock_generation_result(*, cover_letter: object = None) -> MagicMock:
    """Build a mock GenerationResult with the given cover_letter."""
    result = MagicMock()
    result.cover_letter = cover_letter
    return result


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
    """delegate_ghostwriter invokes ContentGenerationService."""

    @pytest.mark.asyncio
    async def test_calls_generate_with_mapped_state(self) -> None:
        """Passes user_id, persona_id, and job_posting_id to service."""
        mock_service = MagicMock()
        mock_service.generate = AsyncMock(return_value=_mock_generation_result())
        with patch(_PATCH_CONTENT_GEN_SERVICE, return_value=mock_service):
            await delegate_ghostwriter(_make_chat_state())

        mock_service.generate.assert_called_once_with(
            user_id=_USER_ID,
            persona_id=_PERSONA_ID,
            job_posting_id=_JOB_ID,
        )

    @pytest.mark.asyncio
    async def test_success_populates_tool_results(self) -> None:
        """Successful invocation stores completed status and content flags."""
        mock_service = MagicMock()
        mock_service.generate = AsyncMock(
            return_value=_mock_generation_result(cover_letter={"content": "cl"})
        )
        with patch(_PATCH_CONTENT_GEN_SERVICE, return_value=mock_service):
            result = await delegate_ghostwriter(_make_chat_state())

        tool_results = result["tool_results"]
        assert len(tool_results) == 1
        assert tool_results[0]["tool"] == "invoke_ghostwriter"
        assert tool_results[0]["error"] is None
        assert tool_results[0]["result"]["status"] == "completed"
        assert tool_results[0]["result"]["has_cover_letter"] is True

    @pytest.mark.asyncio
    async def test_no_cover_letter_flag(self) -> None:
        """Reports has_cover_letter=False when cover letter is None."""
        mock_service = MagicMock()
        mock_service.generate = AsyncMock(
            return_value=_mock_generation_result(cover_letter=None)
        )
        with patch(_PATCH_CONTENT_GEN_SERVICE, return_value=mock_service):
            result = await delegate_ghostwriter(_make_chat_state())

        data = result["tool_results"][0]["result"]
        assert data["has_cover_letter"] is False

    @pytest.mark.asyncio
    async def test_missing_target_job_returns_error(self) -> None:
        """Missing target_job_id produces an error without calling service."""
        mock_service = MagicMock()
        mock_service.generate = AsyncMock()
        with patch(_PATCH_CONTENT_GEN_SERVICE, return_value=mock_service):
            result = await delegate_ghostwriter(_make_chat_state(target_job_id=None))

        mock_service.generate.assert_not_called()
        tool_results = result["tool_results"]
        assert len(tool_results) == 1
        assert tool_results[0]["error"] is not None
        assert "job" in tool_results[0]["error"].lower()

    @pytest.mark.asyncio
    async def test_exception_returns_safe_error_message(self) -> None:
        """Service exception does not leak internals to user."""
        mock_service = MagicMock()
        mock_service.generate = AsyncMock(
            side_effect=RuntimeError("DB connection refused")
        )
        with patch(_PATCH_CONTENT_GEN_SERVICE, return_value=mock_service):
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
        mock_service = MagicMock()
        mock_service.generate = AsyncMock(return_value=_mock_generation_result())
        with patch(_PATCH_CONTENT_GEN_SERVICE, return_value=mock_service):
            result = await delegate_ghostwriter(state)

        assert result is not state
        assert state["tool_results"] is original_results
        assert len(original_results) == 0


# =============================================================================
# delegate_onboarding
# =============================================================================


class TestDelegateOnboarding:
    """delegate_onboarding returns redirect messages (REQ-019 §5)."""

    def test_update_request_with_section_returns_specific_redirect(self) -> None:
        """Update request with detected section returns section-specific message."""
        state = _make_chat_state(current_message="Change my salary requirement")
        result = delegate_onboarding(state)

        tool_results = result["tool_results"]
        assert tool_results[0]["tool"] == "invoke_onboarding"
        assert tool_results[0]["result"]["status"] == "redirected"
        assert "non negotiables" in tool_results[0]["result"]["message"].lower()
        assert "Persona Management" in tool_results[0]["result"]["message"]

    def test_update_request_without_section_returns_generic_redirect(
        self,
    ) -> None:
        """Update request without detectable section returns generic message."""
        state = _make_chat_state(current_message="Edit my experience")
        result = delegate_onboarding(state)

        tool_results = result["tool_results"]
        assert tool_results[0]["result"]["status"] == "redirected"
        assert "Persona Management" in tool_results[0]["result"]["message"]

    def test_non_update_request_redirects_to_wizard(self) -> None:
        """Non-update onboarding request redirects to setup wizard."""
        state = _make_chat_state(current_message="Start onboarding")
        result = delegate_onboarding(state)

        tool_results = result["tool_results"]
        assert tool_results[0]["result"]["status"] == "redirected"
        assert "wizard" in tool_results[0]["result"]["message"].lower()

    def test_populates_tool_results_without_error(self) -> None:
        """Redirect always returns successfully with no error."""
        state = _make_chat_state(current_message="Change my salary requirement")
        result = delegate_onboarding(state)

        tool_results = result["tool_results"]
        assert len(tool_results) == 1
        assert tool_results[0]["error"] is None

    def test_does_not_mutate_input_state(self) -> None:
        """Delegate returns new state, does not mutate the input."""
        state = _make_chat_state(current_message="Change my salary requirement")
        original_results = state["tool_results"]

        result = delegate_onboarding(state)

        assert result is not state
        assert state["tool_results"] is original_results
        assert len(original_results) == 0
