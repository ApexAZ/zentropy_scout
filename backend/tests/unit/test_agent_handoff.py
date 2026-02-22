"""Tests for agent-to-agent handoff creation.

REQ-007 §9.2: Agent-to-Agent Communication Patterns.

Tests the internal handoff layer that models the three inter-agent
communication patterns: Scouter→Strategist (pipeline), Strategist→Ghostwriter
(conditional on threshold), and Chat→Any Agent (sub-graph delegation).
"""

import json
from dataclasses import replace

from app.services.agent_handoff import (
    _MAX_PAYLOAD_SUMMARY_LENGTH,
    AgentHandoff,
    AgentHandoffType,
    create_agent_handoff,
    format_for_state,
)

_AGENT_SCOUTER = "scouter"
_AGENT_STRATEGIST = "strategist"
_AGENT_GHOSTWRITER = "ghostwriter"
_AGENT_CHAT = "chat"
_AGENT_ONBOARDING = "onboarding"
_PAYLOAD_SCORING = "3 new jobs ready for scoring"


def _make_handoff(
    handoff_type: AgentHandoffType = AgentHandoffType.SCOUTER_TO_STRATEGIST,
    source_agent: str = _AGENT_SCOUTER,
    target_agent: str = _AGENT_STRATEGIST,
    payload_summary: str = _PAYLOAD_SCORING,
) -> AgentHandoff:
    """Build a handoff with sensible defaults for concise tests."""
    return create_agent_handoff(
        handoff_type=handoff_type,
        source_agent=source_agent,
        target_agent=target_agent,
        payload_summary=payload_summary,
    )


# =============================================================================
# AgentHandoffType Enum
# =============================================================================


class TestAgentHandoffType:
    """AgentHandoffType has the 3 REQ-007 §9.2 communication patterns."""

    def test_specific_values(self) -> None:
        """Each member has the expected snake_case string value."""
        assert AgentHandoffType.SCOUTER_TO_STRATEGIST.value == "scouter_to_strategist"
        assert (
            AgentHandoffType.STRATEGIST_TO_GHOSTWRITER.value
            == "strategist_to_ghostwriter"
        )
        assert AgentHandoffType.CHAT_TO_AGENT.value == "chat_to_agent"

    def test_json_serializable(self) -> None:
        """Enum values serialize to JSON without custom encoder."""
        for member in AgentHandoffType:
            result = json.dumps({"type": member})
            assert member.value in result


# =============================================================================
# AgentHandoff Structure
# =============================================================================


class TestAgentHandoffStructure:
    """AgentHandoff is a frozen dataclass with four fields."""

    def test_fields_accessible(self) -> None:
        """All four fields are accessible after construction."""
        handoff = AgentHandoff(
            handoff_type=AgentHandoffType.SCOUTER_TO_STRATEGIST,
            source_agent=_AGENT_SCOUTER,
            target_agent=_AGENT_STRATEGIST,
            payload_summary=_PAYLOAD_SCORING,
        )
        assert handoff.handoff_type == AgentHandoffType.SCOUTER_TO_STRATEGIST
        assert handoff.source_agent == _AGENT_SCOUTER
        assert handoff.target_agent == _AGENT_STRATEGIST
        assert handoff.payload_summary == _PAYLOAD_SCORING

    def test_preserves_original_values(self) -> None:
        """Modifying a copy preserves the original handoff values."""
        handoff = AgentHandoff(
            handoff_type=AgentHandoffType.SCOUTER_TO_STRATEGIST,
            source_agent=_AGENT_SCOUTER,
            target_agent=_AGENT_STRATEGIST,
            payload_summary=_PAYLOAD_SCORING,
        )
        updated = replace(handoff, source_agent=_AGENT_CHAT)
        assert handoff.source_agent == _AGENT_SCOUTER
        assert updated.source_agent == _AGENT_CHAT


# =============================================================================
# create_agent_handoff — Per-Type Tests
# =============================================================================


class TestCreateScouterToStrategist:
    """create_agent_handoff with SCOUTER_TO_STRATEGIST type."""

    def test_correct_type(self) -> None:
        """Handoff has SCOUTER_TO_STRATEGIST type."""
        handoff = _make_handoff(payload_summary="5 new jobs discovered from Adzuna")
        assert handoff.handoff_type == AgentHandoffType.SCOUTER_TO_STRATEGIST

    def test_agents_preserved(self) -> None:
        """Source and target agent names are stored verbatim."""
        handoff = _make_handoff()
        assert handoff.source_agent == _AGENT_SCOUTER
        assert handoff.target_agent == _AGENT_STRATEGIST

    def test_payload_preserved(self) -> None:
        """Payload summary is stored verbatim when within length limit."""
        handoff = _make_handoff(payload_summary="5 new jobs discovered from Adzuna")
        assert handoff.payload_summary == "5 new jobs discovered from Adzuna"


class TestCreateStrategistToGhostwriter:
    """create_agent_handoff with STRATEGIST_TO_GHOSTWRITER type."""

    def test_correct_type(self) -> None:
        """Handoff has STRATEGIST_TO_GHOSTWRITER type."""
        handoff = _make_handoff(
            handoff_type=AgentHandoffType.STRATEGIST_TO_GHOSTWRITER,
            source_agent=_AGENT_STRATEGIST,
            target_agent=_AGENT_GHOSTWRITER,
            payload_summary="Job job-456 scored 95, above threshold 90",
        )
        assert handoff.handoff_type == AgentHandoffType.STRATEGIST_TO_GHOSTWRITER

    def test_agents_preserved(self) -> None:
        """Source and target agent names are stored verbatim."""
        handoff = _make_handoff(
            handoff_type=AgentHandoffType.STRATEGIST_TO_GHOSTWRITER,
            source_agent=_AGENT_STRATEGIST,
            target_agent=_AGENT_GHOSTWRITER,
        )
        assert handoff.source_agent == _AGENT_STRATEGIST
        assert handoff.target_agent == _AGENT_GHOSTWRITER

    def test_payload_preserved(self) -> None:
        """Payload summary is stored verbatim when within length limit."""
        handoff = _make_handoff(
            handoff_type=AgentHandoffType.STRATEGIST_TO_GHOSTWRITER,
            source_agent=_AGENT_STRATEGIST,
            target_agent=_AGENT_GHOSTWRITER,
            payload_summary="Job job-456 scored 95, above threshold 90",
        )
        assert handoff.payload_summary == "Job job-456 scored 95, above threshold 90"


class TestCreateChatToAgent:
    """create_agent_handoff with CHAT_TO_AGENT type."""

    def test_correct_type(self) -> None:
        """Handoff has CHAT_TO_AGENT type."""
        handoff = _make_handoff(
            handoff_type=AgentHandoffType.CHAT_TO_AGENT,
            source_agent=_AGENT_CHAT,
            target_agent=_AGENT_GHOSTWRITER,
            payload_summary="User requested materials for job-789",
        )
        assert handoff.handoff_type == AgentHandoffType.CHAT_TO_AGENT

    def test_agents_preserved(self) -> None:
        """Source and target agent names are stored verbatim."""
        handoff = _make_handoff(
            handoff_type=AgentHandoffType.CHAT_TO_AGENT,
            source_agent=_AGENT_CHAT,
            target_agent=_AGENT_ONBOARDING,
        )
        assert handoff.source_agent == _AGENT_CHAT
        assert handoff.target_agent == _AGENT_ONBOARDING

    def test_payload_preserved(self) -> None:
        """Payload summary is stored verbatim when within length limit."""
        handoff = _make_handoff(
            handoff_type=AgentHandoffType.CHAT_TO_AGENT,
            source_agent=_AGENT_CHAT,
            target_agent=_AGENT_SCOUTER,
            payload_summary="User triggered immediate job search",
        )
        assert handoff.payload_summary == "User triggered immediate job search"

    def test_different_targets(self) -> None:
        """Chat can delegate to different target agents."""
        for target in (_AGENT_ONBOARDING, _AGENT_SCOUTER, _AGENT_GHOSTWRITER):
            handoff = _make_handoff(
                handoff_type=AgentHandoffType.CHAT_TO_AGENT,
                source_agent=_AGENT_CHAT,
                target_agent=target,
                payload_summary=f"Delegating to {target}",
            )
            assert handoff.target_agent == target


# =============================================================================
# format_for_state
# =============================================================================


class TestFormatForState:
    """format_for_state converts AgentHandoff to state dict format."""

    def test_handoff_type_value(self) -> None:
        """Output dict has handoff_type as the enum string value."""
        result = format_for_state(_make_handoff())
        assert result["handoff_type"] == "scouter_to_strategist"

    def test_source_agent_matches(self) -> None:
        """Output dict source_agent matches the handoff source."""
        handoff = _make_handoff(
            handoff_type=AgentHandoffType.CHAT_TO_AGENT,
            source_agent=_AGENT_CHAT,
            target_agent=_AGENT_GHOSTWRITER,
        )
        result = format_for_state(handoff)
        assert result["source_agent"] == _AGENT_CHAT

    def test_target_agent_matches(self) -> None:
        """Output dict target_agent matches the handoff target."""
        handoff = _make_handoff(
            handoff_type=AgentHandoffType.STRATEGIST_TO_GHOSTWRITER,
            source_agent=_AGENT_STRATEGIST,
            target_agent=_AGENT_GHOSTWRITER,
        )
        result = format_for_state(handoff)
        assert result["target_agent"] == _AGENT_GHOSTWRITER

    def test_payload_summary_matches(self) -> None:
        """Output dict payload_summary matches the handoff payload."""
        handoff = _make_handoff(payload_summary="5 jobs from LinkedIn")
        result = format_for_state(handoff)
        assert result["payload_summary"] == "5 jobs from LinkedIn"

    def test_exactly_four_keys(self) -> None:
        """Output dict has exactly the four expected keys."""
        result = format_for_state(_make_handoff())
        assert set(result.keys()) == {
            "handoff_type",
            "source_agent",
            "target_agent",
            "payload_summary",
        }

    def test_all_types_produce_valid_dicts(self) -> None:
        """Every handoff type produces a valid state dict."""
        pairs = [
            (AgentHandoffType.SCOUTER_TO_STRATEGIST, _AGENT_SCOUTER, _AGENT_STRATEGIST),
            (
                AgentHandoffType.STRATEGIST_TO_GHOSTWRITER,
                _AGENT_STRATEGIST,
                _AGENT_GHOSTWRITER,
            ),
            (AgentHandoffType.CHAT_TO_AGENT, _AGENT_CHAT, _AGENT_GHOSTWRITER),
        ]
        for handoff_type, source, target in pairs:
            handoff = _make_handoff(
                handoff_type=handoff_type,
                source_agent=source,
                target_agent=target,
                payload_summary=f"Test for {handoff_type.value}",
            )
            result = format_for_state(handoff)
            assert isinstance(result, dict)
            assert result["handoff_type"] == handoff_type.value
            assert result["source_agent"] == source
            assert result["target_agent"] == target


# =============================================================================
# Defense-in-Depth — Payload Truncation
# =============================================================================


class TestDefenseInDepth:
    """Payload summary truncation protects against unbounded internal data."""

    def test_within_limit_preserved(self) -> None:
        """Payload shorter than max is preserved exactly."""
        short = "job-" * 50  # 200 chars
        handoff = _make_handoff(payload_summary=short)
        assert handoff.payload_summary == short
        assert len(handoff.payload_summary) == 200

    def test_at_boundary_preserved(self) -> None:
        """Payload exactly at max length is preserved."""
        exact = "x" * _MAX_PAYLOAD_SUMMARY_LENGTH
        handoff = _make_handoff(payload_summary=exact)
        assert handoff.payload_summary == exact
        assert len(handoff.payload_summary) == _MAX_PAYLOAD_SUMMARY_LENGTH

    def test_one_over_truncated(self) -> None:
        """Payload one character over max is truncated to max."""
        over_by_one = "x" * (_MAX_PAYLOAD_SUMMARY_LENGTH + 1)
        handoff = _make_handoff(payload_summary=over_by_one)
        assert len(handoff.payload_summary) == _MAX_PAYLOAD_SUMMARY_LENGTH

    def test_large_payload_truncated(self) -> None:
        """Payload well over max is truncated to max."""
        huge = "a" * 5000
        handoff = _make_handoff(
            handoff_type=AgentHandoffType.STRATEGIST_TO_GHOSTWRITER,
            source_agent=_AGENT_STRATEGIST,
            target_agent=_AGENT_GHOSTWRITER,
            payload_summary=huge,
        )
        assert len(handoff.payload_summary) == _MAX_PAYLOAD_SUMMARY_LENGTH
        assert handoff.payload_summary == "a" * _MAX_PAYLOAD_SUMMARY_LENGTH


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge cases for agent handoff creation."""

    def test_empty_payload(self) -> None:
        """Empty string payload is accepted."""
        handoff = _make_handoff(payload_summary="")
        assert handoff.payload_summary == ""

    def test_whitespace_payload(self) -> None:
        """Whitespace-only payload is preserved (no implicit stripping)."""
        handoff = _make_handoff(
            handoff_type=AgentHandoffType.CHAT_TO_AGENT,
            source_agent=_AGENT_CHAT,
            target_agent=_AGENT_GHOSTWRITER,
            payload_summary="   ",
        )
        assert handoff.payload_summary == "   "
