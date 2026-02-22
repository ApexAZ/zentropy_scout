"""Tests for agent-to-user message creation.

REQ-007 §9.1: Agent-to-User Communication Patterns.

Tests the semantic message layer that classifies agent-to-user messages
by pattern type (progress update, result summary, action confirmation,
clarification request, HITL pause, error explanation).
"""

import json
from dataclasses import replace

from app.services.agent_message import (
    _MAX_CONTENT_LENGTH,
    AgentMessage,
    AgentMessageType,
    create_agent_message,
    format_for_state,
)

_CONTENT_SEARCHING = "Searching..."
_ROLE_ASSISTANT = "assistant"

# =============================================================================
# AgentMessageType Enum
# =============================================================================


class TestAgentMessageType:
    """AgentMessageType has the 6 REQ-007 §9.1 communication patterns."""

    def test_specific_values(self) -> None:
        """Each member has the expected snake_case string value."""
        assert AgentMessageType.PROGRESS_UPDATE.value == "progress_update"
        assert AgentMessageType.RESULT_SUMMARY.value == "result_summary"
        assert AgentMessageType.ACTION_CONFIRMATION.value == "action_confirmation"
        assert AgentMessageType.CLARIFICATION_REQUEST.value == "clarification_request"
        assert AgentMessageType.HITL_PAUSE.value == "hitl_pause"
        assert AgentMessageType.ERROR_EXPLANATION.value == "error_explanation"

    def test_json_serializable(self) -> None:
        """Enum values serialize to JSON without custom encoder."""
        for member in AgentMessageType:
            result = json.dumps({"type": member})
            assert member.value in result


# =============================================================================
# AgentMessage Structure
# =============================================================================


class TestAgentMessageStructure:
    """AgentMessage is a frozen dataclass with message_type and content."""

    def test_fields_accessible(self) -> None:
        """Both fields are accessible after construction."""
        msg = AgentMessage(
            message_type=AgentMessageType.PROGRESS_UPDATE,
            content=_CONTENT_SEARCHING,
        )
        assert msg.message_type == AgentMessageType.PROGRESS_UPDATE
        assert msg.content == _CONTENT_SEARCHING

    def test_preserves_original_values(self) -> None:
        """Modifying a copy preserves the original message values."""
        msg = AgentMessage(
            message_type=AgentMessageType.PROGRESS_UPDATE,
            content=_CONTENT_SEARCHING,
        )
        updated = replace(msg, content="Modified")
        assert msg.content == _CONTENT_SEARCHING
        assert updated.content == "Modified"


# =============================================================================
# create_agent_message — Per-Type Tests
# =============================================================================


class TestCreateProgressUpdate:
    """create_agent_message with PROGRESS_UPDATE type."""

    def test_correct_type(self) -> None:
        """Message has PROGRESS_UPDATE type."""
        msg = create_agent_message(
            message_type=AgentMessageType.PROGRESS_UPDATE,
            content="Searching Adzuna...",
        )
        assert msg.message_type == AgentMessageType.PROGRESS_UPDATE

    def test_content_preserved(self) -> None:
        """Content is stored verbatim when within length limit."""
        msg = create_agent_message(
            message_type=AgentMessageType.PROGRESS_UPDATE,
            content="Searching Adzuna... Found 12 new jobs. Scoring...",
        )
        assert msg.content == "Searching Adzuna... Found 12 new jobs. Scoring..."


class TestCreateResultSummary:
    """create_agent_message with RESULT_SUMMARY type."""

    def test_correct_type(self) -> None:
        """Message has RESULT_SUMMARY type."""
        msg = create_agent_message(
            message_type=AgentMessageType.RESULT_SUMMARY,
            content="Found 8 matches above your threshold.",
        )
        assert msg.message_type == AgentMessageType.RESULT_SUMMARY

    def test_content_preserved(self) -> None:
        """Content is stored verbatim when within length limit."""
        msg = create_agent_message(
            message_type=AgentMessageType.RESULT_SUMMARY,
            content="Found 8 matches above your threshold. Top 3: ...",
        )
        assert msg.content == "Found 8 matches above your threshold. Top 3: ..."


class TestCreateActionConfirmation:
    """create_agent_message with ACTION_CONFIRMATION type."""

    def test_correct_type(self) -> None:
        """Message has ACTION_CONFIRMATION type."""
        msg = create_agent_message(
            message_type=AgentMessageType.ACTION_CONFIRMATION,
            content="Done! I've favorited the Scrum Master role.",
        )
        assert msg.message_type == AgentMessageType.ACTION_CONFIRMATION

    def test_content_preserved(self) -> None:
        """Content is stored verbatim when within length limit."""
        msg = create_agent_message(
            message_type=AgentMessageType.ACTION_CONFIRMATION,
            content="Done! I've favorited the Scrum Master role at Acme.",
        )
        assert msg.content == "Done! I've favorited the Scrum Master role at Acme."


class TestCreateClarificationRequest:
    """create_agent_message with CLARIFICATION_REQUEST type."""

    def test_correct_type(self) -> None:
        """Message has CLARIFICATION_REQUEST type."""
        msg = create_agent_message(
            message_type=AgentMessageType.CLARIFICATION_REQUEST,
            content="Which job would you like materials for?",
        )
        assert msg.message_type == AgentMessageType.CLARIFICATION_REQUEST

    def test_content_preserved(self) -> None:
        """Content is stored verbatim when within length limit."""
        msg = create_agent_message(
            message_type=AgentMessageType.CLARIFICATION_REQUEST,
            content="Which job would you like me to draft materials for?",
        )
        assert msg.content == "Which job would you like me to draft materials for?"


class TestCreateHitlPause:
    """create_agent_message with HITL_PAUSE type."""

    def test_correct_type(self) -> None:
        """Message has HITL_PAUSE type."""
        msg = create_agent_message(
            message_type=AgentMessageType.HITL_PAUSE,
            content="I've drafted your cover letter.",
        )
        assert msg.message_type == AgentMessageType.HITL_PAUSE

    def test_content_preserved(self) -> None:
        """Content is stored verbatim when within length limit."""
        msg = create_agent_message(
            message_type=AgentMessageType.HITL_PAUSE,
            content="I've drafted your cover letter. Ready for review?",
        )
        assert msg.content == "I've drafted your cover letter. Ready for review?"


class TestCreateErrorExplanation:
    """create_agent_message with ERROR_EXPLANATION type."""

    def test_correct_type(self) -> None:
        """Message has ERROR_EXPLANATION type."""
        msg = create_agent_message(
            message_type=AgentMessageType.ERROR_EXPLANATION,
            content="Couldn't reach Adzuna (API timeout).",
        )
        assert msg.message_type == AgentMessageType.ERROR_EXPLANATION

    def test_content_preserved(self) -> None:
        """Content is stored verbatim when within length limit."""
        msg = create_agent_message(
            message_type=AgentMessageType.ERROR_EXPLANATION,
            content="Couldn't reach Adzuna (API timeout). Checked other sources.",
        )
        assert (
            msg.content == "Couldn't reach Adzuna (API timeout). Checked other sources."
        )


# =============================================================================
# format_for_state
# =============================================================================


class TestFormatForState:
    """format_for_state converts AgentMessage to state dict format."""

    def test_role_is_assistant(self) -> None:
        """Output dict always has role 'assistant'."""
        msg = create_agent_message(
            message_type=AgentMessageType.PROGRESS_UPDATE,
            content="Working...",
        )
        result = format_for_state(msg)
        assert result["role"] == _ROLE_ASSISTANT

    def test_content_matches(self) -> None:
        """Output dict content matches the message content."""
        msg = create_agent_message(
            message_type=AgentMessageType.RESULT_SUMMARY,
            content="Found 5 jobs.",
        )
        result = format_for_state(msg)
        assert result["content"] == "Found 5 jobs."

    def test_all_types_produce_valid_dicts(self) -> None:
        """Every message type produces a valid state dict."""
        for msg_type in AgentMessageType:
            msg = create_agent_message(
                message_type=msg_type,
                content=f"Test content for {msg_type.value}",
            )
            result = format_for_state(msg)
            assert isinstance(result, dict)
            assert result["role"] == _ROLE_ASSISTANT
            assert result["content"] == f"Test content for {msg_type.value}"


# =============================================================================
# Defense-in-Depth — Content Truncation
# =============================================================================


class TestDefenseInDepth:
    """Content truncation protects against unbounded output."""

    def test_within_limit_preserved(self) -> None:
        """Content shorter than max is preserved exactly."""
        short = "Hello" * 100  # 500 chars
        msg = create_agent_message(
            message_type=AgentMessageType.PROGRESS_UPDATE,
            content=short,
        )
        assert msg.content == short
        assert len(msg.content) == 500

    def test_at_boundary_preserved(self) -> None:
        """Content exactly at max length is preserved."""
        exact = "x" * _MAX_CONTENT_LENGTH
        msg = create_agent_message(
            message_type=AgentMessageType.PROGRESS_UPDATE,
            content=exact,
        )
        assert msg.content == exact
        assert len(msg.content) == _MAX_CONTENT_LENGTH

    def test_one_over_truncated(self) -> None:
        """Content one character over max is truncated to max."""
        over_by_one = "x" * (_MAX_CONTENT_LENGTH + 1)
        msg = create_agent_message(
            message_type=AgentMessageType.PROGRESS_UPDATE,
            content=over_by_one,
        )
        assert len(msg.content) == _MAX_CONTENT_LENGTH

    def test_large_content_truncated(self) -> None:
        """Content well over max is truncated to max."""
        huge = "a" * 10000
        msg = create_agent_message(
            message_type=AgentMessageType.ERROR_EXPLANATION,
            content=huge,
        )
        assert len(msg.content) == _MAX_CONTENT_LENGTH
        assert msg.content == "a" * _MAX_CONTENT_LENGTH


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge cases for agent message creation."""

    def test_empty_content(self) -> None:
        """Empty string content is accepted."""
        msg = create_agent_message(
            message_type=AgentMessageType.PROGRESS_UPDATE,
            content="",
        )
        assert msg.content == ""

    def test_whitespace_content(self) -> None:
        """Whitespace-only content is preserved (no implicit stripping)."""
        msg = create_agent_message(
            message_type=AgentMessageType.PROGRESS_UPDATE,
            content="   ",
        )
        assert msg.content == "   "
