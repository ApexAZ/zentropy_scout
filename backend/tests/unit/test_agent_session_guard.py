"""Structural guard tests for agent session isolation.

REQ-014 §7.3: Agents must NOT import AsyncSession directly. All agent
database access should go through TenantScopedSession or the API client.
These tests act as a guardrail against future regressions.

Tests verify:
- No agent file imports AsyncSession or AsyncEngine
"""

import ast
from pathlib import Path

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
