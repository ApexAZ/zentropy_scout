"""Agent-to-agent handoff creation.

REQ-007 §9.2: Agent-to-Agent Communication Patterns.

Defines three inter-agent communication patterns that model how agents
invoke each other: pipeline (Scouter→Strategist), conditional
(Strategist→Ghostwriter when score exceeds threshold), and delegation
(Chat→Any Agent via sub-graph invocation).

Graph nodes call ``create_agent_handoff`` to build typed handoff records,
then ``format_for_state`` to convert them to a dict for state updates
and logging.
"""

from dataclasses import dataclass
from enum import Enum

_MAX_PAYLOAD_SUMMARY_LENGTH: int = 500
"""Safety bound on payload summary length (defense-in-depth)."""

# =============================================================================
# Enums
# =============================================================================


class AgentHandoffType(str, Enum):
    """Communication pattern types for agent-to-agent handoffs.

    REQ-007 §9.2: Three patterns that agents use to invoke each other.

    Values:
        SCOUTER_TO_STRATEGIST: Direct function call after job discovery.
        STRATEGIST_TO_GHOSTWRITER: Conditional trigger when score exceeds
            the user's auto-draft threshold.
        CHAT_TO_AGENT: LangGraph sub-graph invocation initiated by user
            through the Chat Agent.
    """

    SCOUTER_TO_STRATEGIST = "scouter_to_strategist"
    STRATEGIST_TO_GHOSTWRITER = "strategist_to_ghostwriter"
    CHAT_TO_AGENT = "chat_to_agent"


# =============================================================================
# Data Models
# =============================================================================


@dataclass(frozen=True)
class AgentHandoff:
    """A typed agent-to-agent handoff record.

    REQ-007 §9.2: Captures the communication pattern, the agents involved,
    and a human-readable summary of the data being passed.

    Attributes:
        handoff_type: The communication pattern this handoff represents.
        source_agent: The agent initiating the handoff.
        target_agent: The agent receiving the handoff.
        payload_summary: Human-readable description of the data being passed.
    """

    handoff_type: AgentHandoffType
    source_agent: str
    target_agent: str
    payload_summary: str


# =============================================================================
# Handoff Creation
# =============================================================================


def create_agent_handoff(
    *,
    handoff_type: AgentHandoffType,
    source_agent: str,
    target_agent: str,
    payload_summary: str,
) -> AgentHandoff:
    """Create a validated agent-to-agent handoff record.

    REQ-007 §9.2: Builds a typed handoff for any of the three
    communication patterns. Payload summary is truncated to
    ``_MAX_PAYLOAD_SUMMARY_LENGTH`` as a defense-in-depth measure
    against unbounded internal data.

    Args:
        handoff_type: The communication pattern type.
        source_agent: Name of the agent initiating the handoff.
        target_agent: Name of the agent receiving the handoff.
        payload_summary: Description of data being passed (truncated
            if over limit).

    Returns:
        Frozen AgentHandoff ready for state insertion or logging.
    """
    bounded_summary = payload_summary[:_MAX_PAYLOAD_SUMMARY_LENGTH]
    return AgentHandoff(
        handoff_type=handoff_type,
        source_agent=source_agent,
        target_agent=target_agent,
        payload_summary=bounded_summary,
    )


# =============================================================================
# State Formatting
# =============================================================================


def format_for_state(handoff: AgentHandoff) -> dict[str, str]:
    """Convert AgentHandoff to a dict for state updates and logging.

    Returns a dict with ``handoff_type``, ``source_agent``,
    ``target_agent``, and ``payload_summary`` keys — suitable for
    insertion into agent state or structured logging.

    Args:
        handoff: The agent handoff to format.

    Returns:
        Dict with four string keys for state insertion.
    """
    return {
        "handoff_type": handoff.handoff_type.value,
        "source_agent": handoff.source_agent,
        "target_agent": handoff.target_agent,
        "payload_summary": handoff.payload_summary,
    }
