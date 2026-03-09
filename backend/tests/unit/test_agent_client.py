"""Tests for Agent API client abstraction.

REQ-006 §2.3: API-Mediated Agents

Tests verify:
- Factory function returns singleton and resets correctly
"""

from collections.abc import Generator

import pytest

from app.agents.base import (
    get_agent_client,
    reset_agent_client,
)


@pytest.fixture(autouse=True)
def reset_singleton() -> Generator[None, None, None]:
    """Reset the agent client singleton before each test."""
    reset_agent_client()
    yield
    reset_agent_client()


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestGetAgentClient:
    """Tests for get_agent_client factory function."""

    def test_returns_singleton(self):
        """Factory returns the same instance on subsequent calls."""
        client1 = get_agent_client()
        client2 = get_agent_client()
        assert client1 is client2

    def test_reset_clears_singleton(self):
        """reset_agent_client clears the singleton."""
        client1 = get_agent_client()
        reset_agent_client()
        client2 = get_agent_client()
        assert client1 is not client2
