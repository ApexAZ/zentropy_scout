"""Agent-to-user message creation.

REQ-007 §9.1: Agent-to-User Communication Patterns.

Defines six semantic message types that agents use to communicate with
users through the Chat Agent: progress update, result summary, action
confirmation, clarification request, HITL pause, and error explanation.

Graph nodes call ``create_agent_message`` to build typed messages, then
``format_for_state`` to convert them to the ``BaseAgentState.messages``
dict format for state updates.
"""

from dataclasses import dataclass
from enum import Enum

_MAX_CONTENT_LENGTH: int = 2000
"""Safety bound on message content length (defense-in-depth)."""

# =============================================================================
# Enums
# =============================================================================


class AgentMessageType(str, Enum):
    """Communication pattern types for agent-to-user messages.

    REQ-007 §9.1: Six patterns that agents use to interact with users
    through the Chat Agent.

    Values:
        PROGRESS_UPDATE: Real-time status during long-running operations.
        RESULT_SUMMARY: Condensed output after an operation completes.
        ACTION_CONFIRMATION: Acknowledgment of a completed user request.
        CLARIFICATION_REQUEST: Asking the user for additional input.
        HITL_PAUSE: Human-in-the-loop checkpoint for user review.
        ERROR_EXPLANATION: Graceful error reporting with context.
    """

    PROGRESS_UPDATE = "progress_update"
    RESULT_SUMMARY = "result_summary"
    ACTION_CONFIRMATION = "action_confirmation"
    CLARIFICATION_REQUEST = "clarification_request"
    HITL_PAUSE = "hitl_pause"
    ERROR_EXPLANATION = "error_explanation"


# =============================================================================
# Data Models
# =============================================================================


@dataclass(frozen=True)
class AgentMessage:
    """A typed agent-to-user message.

    REQ-007 §9.1: Pairs a communication pattern type with content text.

    Attributes:
        message_type: The communication pattern this message represents.
        content: The message text to display to the user.
    """

    message_type: AgentMessageType
    content: str


# =============================================================================
# Message Creation
# =============================================================================


def create_agent_message(
    *,
    message_type: AgentMessageType,
    content: str,
) -> AgentMessage:
    """Create a validated agent-to-user message.

    REQ-007 §9.1: Builds a typed message for any of the six
    communication patterns. Content is truncated to
    ``_MAX_CONTENT_LENGTH`` as a defense-in-depth measure against
    unbounded output.

    Args:
        message_type: The communication pattern type.
        content: The message text (truncated if over limit).

    Returns:
        Frozen AgentMessage ready for state insertion or SSE dispatch.
    """
    bounded_content = content[:_MAX_CONTENT_LENGTH]
    return AgentMessage(message_type=message_type, content=bounded_content)


# =============================================================================
# State Formatting
# =============================================================================


def format_for_state(message: AgentMessage) -> dict[str, str]:
    """Convert AgentMessage to BaseAgentState.messages dict format.

    Returns ``{"role": "assistant", "content": str}`` — matches the exact
    format used throughout the codebase for state message dicts
    (see ``BaseAgentState.messages`` in ``agents/state.py``).

    Args:
        message: The agent message to format.

    Returns:
        Dict with 'role' and 'content' keys for state insertion.
    """
    return {"role": "assistant", "content": message.content}
