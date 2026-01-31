"""Tests for the Discovery Workflow service.

REQ-003 §13.1: Workflow — Discovery Flow.

The Discovery Workflow orchestrates:
1. Trigger detection (scheduled, manual, source added)
2. Scouter graph invocation
3. Result presentation (sorted by Fit Score)
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.discovery_workflow import (
    DiscoveryResult,
    DiscoveryTrigger,
    TriggerType,
    check_trigger_conditions,
    format_discovery_results,
    run_discovery,
    should_run_discovery,
)

# =============================================================================
# Trigger Detection Tests (REQ-003 §13.1)
# =============================================================================


class TestTriggerType:
    """Tests for TriggerType enum."""

    def test_trigger_types_exist(self) -> None:
        """All trigger types from REQ-007 §6.1 are defined."""
        assert TriggerType.SCHEDULED is not None
        assert TriggerType.MANUAL is not None
        assert TriggerType.SOURCE_ADDED is not None


class TestDiscoveryTrigger:
    """Tests for DiscoveryTrigger dataclass."""

    def test_scheduled_trigger_creation(self) -> None:
        """Scheduled trigger includes next_poll_at."""
        trigger = DiscoveryTrigger(
            trigger_type=TriggerType.SCHEDULED,
            next_poll_at=datetime.now(UTC),
        )

        assert trigger.trigger_type == TriggerType.SCHEDULED
        assert trigger.next_poll_at is not None
        assert trigger.user_message is None
        assert trigger.previous_sources is None

    def test_manual_trigger_creation(self) -> None:
        """Manual trigger includes user message."""
        trigger = DiscoveryTrigger(
            trigger_type=TriggerType.MANUAL,
            user_message="Find me some jobs",
        )

        assert trigger.trigger_type == TriggerType.MANUAL
        assert trigger.user_message == "Find me some jobs"

    def test_source_added_trigger_creation(self) -> None:
        """Source added trigger includes previous and current sources."""
        trigger = DiscoveryTrigger(
            trigger_type=TriggerType.SOURCE_ADDED,
            previous_sources=["Adzuna"],
            current_sources=["Adzuna", "RemoteOK"],
        )

        assert trigger.trigger_type == TriggerType.SOURCE_ADDED
        assert trigger.previous_sources == ["Adzuna"]
        assert trigger.current_sources == ["Adzuna", "RemoteOK"]


class TestCheckTriggerConditions:
    """Tests for check_trigger_conditions function."""

    def test_scheduled_trigger_when_poll_time_passed(self) -> None:
        """Returns SCHEDULED trigger when next_poll_at has passed."""
        past_time = datetime.now(UTC) - timedelta(hours=1)

        trigger = check_trigger_conditions(
            next_poll_at=past_time,
            user_message=None,
            previous_sources=["Adzuna"],
            current_sources=["Adzuna"],
        )

        assert trigger is not None
        assert trigger.trigger_type == TriggerType.SCHEDULED

    def test_manual_trigger_when_user_requests_jobs(self) -> None:
        """Returns MANUAL trigger when user message matches refresh pattern."""
        trigger = check_trigger_conditions(
            next_poll_at=datetime.now(UTC) + timedelta(hours=12),
            user_message="Find new jobs for me",
            previous_sources=["Adzuna"],
            current_sources=["Adzuna"],
        )

        assert trigger is not None
        assert trigger.trigger_type == TriggerType.MANUAL

    def test_source_added_trigger_when_new_source_enabled(self) -> None:
        """Returns SOURCE_ADDED trigger when new source added."""
        trigger = check_trigger_conditions(
            next_poll_at=datetime.now(UTC) + timedelta(hours=12),
            user_message=None,
            previous_sources=["Adzuna"],
            current_sources=["Adzuna", "RemoteOK"],
        )

        assert trigger is not None
        assert trigger.trigger_type == TriggerType.SOURCE_ADDED

    def test_no_trigger_when_no_conditions_met(self) -> None:
        """Returns None when no trigger conditions are met."""
        trigger = check_trigger_conditions(
            next_poll_at=datetime.now(UTC) + timedelta(hours=12),
            user_message="Hello, how are you?",
            previous_sources=["Adzuna"],
            current_sources=["Adzuna"],
        )

        assert trigger is None

    def test_manual_trigger_takes_priority_over_scheduled(self) -> None:
        """Manual trigger takes priority when both conditions met."""
        past_time = datetime.now(UTC) - timedelta(hours=1)

        trigger = check_trigger_conditions(
            next_poll_at=past_time,
            user_message="Find me jobs",
            previous_sources=["Adzuna"],
            current_sources=["Adzuna"],
        )

        # WHY: Manual trigger takes priority because user explicitly requested
        assert trigger is not None
        assert trigger.trigger_type == TriggerType.MANUAL


class TestShouldRunDiscovery:
    """Tests for should_run_discovery function."""

    def test_returns_true_when_trigger_exists(self) -> None:
        """Returns True when any trigger condition is met."""
        trigger = DiscoveryTrigger(
            trigger_type=TriggerType.SCHEDULED,
            next_poll_at=datetime.now(UTC) - timedelta(hours=1),
        )

        result = should_run_discovery(trigger)

        assert result is True

    def test_returns_false_when_no_trigger(self) -> None:
        """Returns False when no trigger provided."""
        result = should_run_discovery(None)

        assert result is False


# =============================================================================
# Result Formatting Tests (REQ-003 §13.1)
# =============================================================================


class TestDiscoveryResult:
    """Tests for DiscoveryResult dataclass."""

    def test_result_contains_jobs_sorted_by_fit_score(self) -> None:
        """DiscoveryResult holds jobs list sorted by fit score."""
        jobs = [
            {"id": "1", "title": "Job A", "fit_score": 85},
            {"id": "2", "title": "Job B", "fit_score": 92},
        ]

        result = DiscoveryResult(
            jobs=jobs,
            total_discovered=2,
            sources_queried=["Adzuna"],
            error_sources=[],
        )

        assert result.jobs == jobs
        assert result.total_discovered == 2
        assert result.sources_queried == ["Adzuna"]

    def test_result_tracks_error_sources(self) -> None:
        """DiscoveryResult tracks sources that failed."""
        result = DiscoveryResult(
            jobs=[],
            total_discovered=0,
            sources_queried=["Adzuna", "RemoteOK"],
            error_sources=["RemoteOK"],
        )

        assert "RemoteOK" in result.error_sources


class TestFormatDiscoveryResults:
    """Tests for format_discovery_results function."""

    def test_sorts_jobs_by_fit_score_descending(self) -> None:
        """Jobs are sorted by fit_score descending (highest first)."""
        jobs: list[dict[str, Any]] = [
            {"id": "1", "title": "Job A", "fit_score": 75},
            {"id": "2", "title": "Job B", "fit_score": 92},
            {"id": "3", "title": "Job C", "fit_score": 85},
        ]

        result = format_discovery_results(
            jobs=jobs,
            sources_queried=["Adzuna"],
            error_sources=[],
        )

        # Jobs should be ordered by fit_score descending
        assert result.jobs[0]["fit_score"] == 92
        assert result.jobs[1]["fit_score"] == 85
        assert result.jobs[2]["fit_score"] == 75

    def test_handles_jobs_without_fit_score(self) -> None:
        """Jobs without fit_score sort to end (score of 0)."""
        jobs: list[dict[str, Any]] = [
            {"id": "1", "title": "Job A", "fit_score": 75},
            {"id": "2", "title": "Job B"},  # No fit_score
            {"id": "3", "title": "Job C", "fit_score": 85},
        ]

        result = format_discovery_results(
            jobs=jobs,
            sources_queried=["Adzuna"],
            error_sources=[],
        )

        # Job without fit_score should be last
        assert result.jobs[0]["fit_score"] == 85
        assert result.jobs[1]["fit_score"] == 75
        assert result.jobs[2].get("fit_score") is None

    def test_counts_total_discovered(self) -> None:
        """Total discovered count is set correctly."""
        jobs: list[dict[str, Any]] = [
            {"id": "1", "title": "Job A"},
            {"id": "2", "title": "Job B"},
        ]

        result = format_discovery_results(
            jobs=jobs,
            sources_queried=["Adzuna", "RemoteOK"],
            error_sources=[],
        )

        assert result.total_discovered == 2

    def test_includes_sources_queried(self) -> None:
        """Sources queried list is preserved."""
        result = format_discovery_results(
            jobs=[],
            sources_queried=["Adzuna", "RemoteOK", "TheMuse"],
            error_sources=[],
        )

        assert result.sources_queried == ["Adzuna", "RemoteOK", "TheMuse"]


# =============================================================================
# Workflow Execution Tests (REQ-003 §13.1)
# =============================================================================


class TestRunDiscovery:
    """Tests for run_discovery function.

    REQ-003 §13.1: Full discovery workflow execution.
    """

    @pytest.mark.asyncio
    async def test_invokes_scouter_graph_when_trigger_exists(self) -> None:
        """Scouter graph is invoked when trigger conditions are met."""
        trigger = DiscoveryTrigger(
            trigger_type=TriggerType.MANUAL,
            user_message="Find jobs",
        )

        # Mock the scouter graph execution
        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "processed_jobs": [
                    {"id": "1", "title": "Job A", "fit_score": 85},
                ],
                "enabled_sources": ["Adzuna"],
                "error_sources": [],
            }
        )

        with patch(
            "app.services.discovery_workflow.get_scouter_graph",
            return_value=mock_graph,
        ):
            result = await run_discovery(
                user_id="user-123",
                persona_id="persona-456",
                enabled_sources=["Adzuna"],
                trigger=trigger,
            )

        # Graph should have been invoked
        mock_graph.ainvoke.assert_called_once()
        assert result is not None
        assert result.total_discovered == 1

    @pytest.mark.asyncio
    async def test_returns_empty_result_when_no_trigger(self) -> None:
        """Returns empty result when no trigger provided."""
        result = await run_discovery(
            user_id="user-123",
            persona_id="persona-456",
            enabled_sources=["Adzuna"],
            trigger=None,
        )

        assert result is not None
        assert result.total_discovered == 0
        assert result.jobs == []

    @pytest.mark.asyncio
    async def test_result_includes_error_sources_from_graph(self) -> None:
        """Error sources from graph execution are included in result."""
        trigger = DiscoveryTrigger(
            trigger_type=TriggerType.SCHEDULED,
            next_poll_at=datetime.now(UTC) - timedelta(hours=1),
        )

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "processed_jobs": [],
                "enabled_sources": ["Adzuna", "RemoteOK"],
                "error_sources": ["RemoteOK"],
            }
        )

        with patch(
            "app.services.discovery_workflow.get_scouter_graph",
            return_value=mock_graph,
        ):
            result = await run_discovery(
                user_id="user-123",
                persona_id="persona-456",
                enabled_sources=["Adzuna", "RemoteOK"],
                trigger=trigger,
            )

        assert "RemoteOK" in result.error_sources

    @pytest.mark.asyncio
    async def test_jobs_sorted_by_fit_score_in_result(self) -> None:
        """Jobs in result are sorted by fit_score descending."""
        trigger = DiscoveryTrigger(
            trigger_type=TriggerType.MANUAL,
            user_message="Search for jobs",
        )

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "processed_jobs": [
                    {"id": "1", "title": "Job A", "fit_score": 70},
                    {"id": "2", "title": "Job B", "fit_score": 95},
                    {"id": "3", "title": "Job C", "fit_score": 82},
                ],
                "enabled_sources": ["Adzuna"],
                "error_sources": [],
            }
        )

        with patch(
            "app.services.discovery_workflow.get_scouter_graph",
            return_value=mock_graph,
        ):
            result = await run_discovery(
                user_id="user-123",
                persona_id="persona-456",
                enabled_sources=["Adzuna"],
                trigger=trigger,
            )

        # Jobs should be sorted by fit_score descending
        assert result.jobs[0]["fit_score"] == 95
        assert result.jobs[1]["fit_score"] == 82
        assert result.jobs[2]["fit_score"] == 70

    @pytest.mark.asyncio
    async def test_creates_initial_state_for_graph(self) -> None:
        """Graph is invoked with correct initial state."""
        trigger = DiscoveryTrigger(
            trigger_type=TriggerType.MANUAL,
            user_message="Find jobs",
        )

        mock_graph = MagicMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "processed_jobs": [],
                "enabled_sources": ["Adzuna"],
                "error_sources": [],
            }
        )

        with patch(
            "app.services.discovery_workflow.get_scouter_graph",
            return_value=mock_graph,
        ):
            await run_discovery(
                user_id="user-123",
                persona_id="persona-456",
                enabled_sources=["Adzuna", "RemoteOK"],
                trigger=trigger,
            )

        # Verify the state passed to graph
        call_args = mock_graph.ainvoke.call_args
        state = call_args[0][0]

        assert state["user_id"] == "user-123"
        assert state["persona_id"] == "persona-456"
        assert state["enabled_sources"] == ["Adzuna", "RemoteOK"]
