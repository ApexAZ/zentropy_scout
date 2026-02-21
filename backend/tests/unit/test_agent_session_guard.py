"""Structural guard tests for agent session isolation.

REQ-014 §7.3: Agents must NOT import AsyncSession directly. All agent
database access should go through TenantScopedSession or the API client.
These tests act as a guardrail against future regressions.

Tests verify:
- No agent file imports AsyncSession or AsyncEngine
- BaseAgentState includes user_id field
- All AgentAPIClient Protocol methods require user_id parameter
"""

import ast
import inspect
from pathlib import Path

import pytest

from app.agents.base import AgentAPIClient
from app.agents.state import BaseAgentState

_AGENTS_DIR = Path(__file__).resolve().parents[2] / "app" / "agents"

_FORBIDDEN_IMPORTS = frozenset({"AsyncSession", "AsyncEngine"})


# =============================================================================
# Raw Session Import Guard
# =============================================================================


class TestNoRawSessionInAgents:
    """Guard: agent files must not import AsyncSession or AsyncEngine."""

    def _get_agent_python_files(self) -> list[Path]:
        """Return all .py files in the agents directory tree."""
        return sorted(_AGENTS_DIR.rglob("*.py"))

    def test_agents_directory_exists(self) -> None:
        """Verify the agents directory exists (guard against path drift)."""
        assert _AGENTS_DIR.is_dir(), f"Expected agents dir: {_AGENTS_DIR}"

    def test_agents_directory_has_python_files(self) -> None:
        """Verify agents directory contains at least one .py file."""
        files = self._get_agent_python_files()
        assert len(files) > 0, (
            f"No .py files found in {_AGENTS_DIR} — guard tests would silently pass"
        )

    def test_no_async_session_import(self) -> None:
        """No agent file should import AsyncSession directly.

        Agents use the API-mediated pattern (AgentAPIClient) for all data
        access. Direct AsyncSession usage bypasses tenant isolation.
        """
        violations: list[str] = []

        for py_file in self._get_agent_python_files():
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.ImportFrom, ast.Import)):
                    for alias in node.names:
                        if alias.name in _FORBIDDEN_IMPORTS:
                            violations.append(
                                f"{py_file.name}:{node.lineno} imports {alias.name}"
                            )

        assert violations == [], (
            "Agent files must not import raw DB sessions. "
            "Use AgentAPIClient or TenantScopedSession instead.\n"
            "Violations:\n" + "\n".join(f"  - {v}" for v in violations)
        )


# =============================================================================
# BaseAgentState user_id
# =============================================================================


class TestAgentStateUserIdField:
    """Guard: BaseAgentState must include user_id for tenant scoping."""

    def test_base_state_has_user_id(self) -> None:
        """BaseAgentState includes user_id field."""
        annotations = BaseAgentState.__annotations__
        assert "user_id" in annotations, (
            "BaseAgentState must have 'user_id' field for tenant isolation"
        )

    def test_base_state_has_persona_id(self) -> None:
        """BaseAgentState includes persona_id field."""
        annotations = BaseAgentState.__annotations__
        assert "persona_id" in annotations, (
            "BaseAgentState must have 'persona_id' field for entity scoping"
        )


# =============================================================================
# AgentAPIClient user_id requirement
# =============================================================================


class TestAgentClientUserIdRequired:
    """Guard: all AgentAPIClient methods must require user_id parameter."""

    @pytest.mark.parametrize(
        "method_name",
        [
            name
            for name in dir(AgentAPIClient)
            if not name.startswith("_") and callable(getattr(AgentAPIClient, name))
        ],
    )
    def test_method_has_user_id_param(self, method_name: str) -> None:
        """Each AgentAPIClient method must accept a user_id parameter.

        This ensures tenant isolation is enforced at the protocol level.
        """
        method = getattr(AgentAPIClient, method_name)
        sig = inspect.signature(method)
        param_names = list(sig.parameters.keys())

        assert "user_id" in param_names, (
            f"AgentAPIClient.{method_name}() must accept 'user_id' parameter "
            f"for tenant isolation. Found params: {param_names}"
        )
