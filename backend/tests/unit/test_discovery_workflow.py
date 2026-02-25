"""Tests for the Discovery Workflow service.

REQ-003 §13.1: Workflow — Discovery Flow.

The Discovery Workflow orchestrates:
1. Trigger detection (scheduled, manual, source added)
2. JobFetchService invocation (replaced scouter graph in REQ-016)
3. Result presentation (sorted by Fit Score)
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

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
from app.services.job_fetch_service import PollResult

# S1192: Duplicated source name and patch path strings
_SOURCE_ADZUNA = "Adzuna"
_SOURCE_REMOTEOK = "RemoteOK"
_JOB_FETCH_SERVICE = "app.services.discovery_workflow.JobFetchService"

# =============================================================================
# Trigger Detection Tests (REQ-003 §13.1)
# =============================================================================


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
            previous_sources=[_SOURCE_ADZUNA],
            current_sources=[_SOURCE_ADZUNA, _SOURCE_REMOTEOK],
        )

        assert trigger.trigger_type == TriggerType.SOURCE_ADDED
        assert trigger.previous_sources == [_SOURCE_ADZUNA]
        assert trigger.current_sources == [_SOURCE_ADZUNA, _SOURCE_REMOTEOK]


class TestCheckTriggerConditions:
    """Tests for check_trigger_conditions function."""

    def test_scheduled_trigger_when_poll_time_passed(self) -> None:
        """Returns SCHEDULED trigger when next_poll_at has passed."""
        past_time = datetime.now(UTC) - timedelta(hours=1)

        trigger = check_trigger_conditions(
            next_poll_at=past_time,
            user_message=None,
            previous_sources=[_SOURCE_ADZUNA],
            current_sources=[_SOURCE_ADZUNA],
        )

        assert trigger is not None
        assert trigger.trigger_type == TriggerType.SCHEDULED

    def test_manual_trigger_when_user_requests_jobs(self) -> None:
        """Returns MANUAL trigger when user message matches refresh pattern."""
        trigger = check_trigger_conditions(
            next_poll_at=datetime.now(UTC) + timedelta(hours=12),
            user_message="Find new jobs for me",
            previous_sources=[_SOURCE_ADZUNA],
            current_sources=[_SOURCE_ADZUNA],
        )

        assert trigger is not None
        assert trigger.trigger_type == TriggerType.MANUAL

    def test_source_added_trigger_when_new_source_enabled(self) -> None:
        """Returns SOURCE_ADDED trigger when new source added."""
        trigger = check_trigger_conditions(
            next_poll_at=datetime.now(UTC) + timedelta(hours=12),
            user_message=None,
            previous_sources=[_SOURCE_ADZUNA],
            current_sources=[_SOURCE_ADZUNA, _SOURCE_REMOTEOK],
        )

        assert trigger is not None
        assert trigger.trigger_type == TriggerType.SOURCE_ADDED

    def test_no_trigger_when_no_conditions_met(self) -> None:
        """Returns None when no trigger conditions are met."""
        trigger = check_trigger_conditions(
            next_poll_at=datetime.now(UTC) + timedelta(hours=12),
            user_message="Hello, how are you?",
            previous_sources=[_SOURCE_ADZUNA],
            current_sources=[_SOURCE_ADZUNA],
        )

        assert trigger is None

    def test_manual_trigger_takes_priority_over_scheduled(self) -> None:
        """Manual trigger takes priority when both conditions met."""
        past_time = datetime.now(UTC) - timedelta(hours=1)

        trigger = check_trigger_conditions(
            next_poll_at=past_time,
            user_message="Find me jobs",
            previous_sources=[_SOURCE_ADZUNA],
            current_sources=[_SOURCE_ADZUNA],
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
            sources_queried=[_SOURCE_ADZUNA],
            error_sources=[],
        )

        assert result.jobs == jobs
        assert result.total_discovered == 2
        assert result.sources_queried == [_SOURCE_ADZUNA]

    def test_result_tracks_error_sources(self) -> None:
        """DiscoveryResult tracks sources that failed."""
        result = DiscoveryResult(
            jobs=[],
            total_discovered=0,
            sources_queried=[_SOURCE_ADZUNA, _SOURCE_REMOTEOK],
            error_sources=[_SOURCE_REMOTEOK],
        )

        assert _SOURCE_REMOTEOK in result.error_sources


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
            sources_queried=[_SOURCE_ADZUNA],
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
            sources_queried=[_SOURCE_ADZUNA],
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
            sources_queried=[_SOURCE_ADZUNA, _SOURCE_REMOTEOK],
            error_sources=[],
        )

        assert result.total_discovered == 2

    def test_includes_sources_queried(self) -> None:
        """Sources queried list is preserved."""
        result = format_discovery_results(
            jobs=[],
            sources_queried=[_SOURCE_ADZUNA, _SOURCE_REMOTEOK, "TheMuse"],
            error_sources=[],
        )

        assert result.sources_queried == [_SOURCE_ADZUNA, _SOURCE_REMOTEOK, "TheMuse"]


# =============================================================================
# Workflow Execution Tests (REQ-003 §13.1)
# =============================================================================


class TestRunDiscovery:
    """Tests for run_discovery function.

    REQ-003 §13.1 + REQ-016 §6.2: Full discovery workflow execution
    via JobFetchService.
    """

    @pytest.fixture
    def mock_db(self) -> AsyncMock:
        """Mock async database session."""
        return AsyncMock()

    @pytest.fixture
    def user_id(self) -> UUID:
        """Stable user UUID."""
        return uuid4()

    @pytest.fixture
    def persona_id(self) -> UUID:
        """Stable persona UUID."""
        return uuid4()

    @pytest.fixture
    def _make_poll_result(self) -> Callable[..., PollResult]:
        """Factory for PollResult with sensible defaults."""

        def _make(
            processed_jobs: list[dict[str, Any]] | None = None,
            new_job_count: int = 0,
            existing_job_count: int = 0,
            error_sources: list[str] | None = None,
        ) -> PollResult:
            return PollResult(
                processed_jobs=processed_jobs or [],
                new_job_count=new_job_count,
                existing_job_count=existing_job_count,
                error_sources=error_sources or [],
            )

        return _make

    async def test_invokes_service_when_trigger_exists(
        self,
        mock_db,
        user_id,
        persona_id,
        _make_poll_result,
    ) -> None:
        """JobFetchService.run_poll is called when trigger conditions are met."""
        trigger = DiscoveryTrigger(
            trigger_type=TriggerType.MANUAL,
            user_message="Find jobs",
        )

        poll_result = _make_poll_result(
            processed_jobs=[
                {"id": "1", "title": "Job A", "fit_score": 85},
            ],
            new_job_count=1,
        )

        with patch(
            _JOB_FETCH_SERVICE,
        ) as mock_cls:
            mock_cls.return_value.run_poll = AsyncMock(return_value=poll_result)
            result = await run_discovery(
                db=mock_db,
                user_id=user_id,
                persona_id=persona_id,
                enabled_sources=[_SOURCE_ADZUNA],
                trigger=trigger,
            )

        mock_cls.return_value.run_poll.assert_called_once()
        assert result.total_discovered == 1

    async def test_returns_empty_result_when_no_trigger(
        self,
        mock_db,
        user_id,
        persona_id,
    ) -> None:
        """Returns empty result when no trigger provided."""
        result = await run_discovery(
            db=mock_db,
            user_id=user_id,
            persona_id=persona_id,
            enabled_sources=[_SOURCE_ADZUNA],
            trigger=None,
        )

        assert result.total_discovered == 0
        assert result.jobs == []

    async def test_result_includes_error_sources_from_service(
        self,
        mock_db,
        user_id,
        persona_id,
        _make_poll_result,
    ) -> None:
        """Error sources from JobFetchService are included in result."""
        trigger = DiscoveryTrigger(
            trigger_type=TriggerType.SCHEDULED,
            next_poll_at=datetime.now(UTC) - timedelta(hours=1),
        )

        poll_result = _make_poll_result(error_sources=[_SOURCE_REMOTEOK])

        with patch(
            _JOB_FETCH_SERVICE,
        ) as mock_cls:
            mock_cls.return_value.run_poll = AsyncMock(return_value=poll_result)
            result = await run_discovery(
                db=mock_db,
                user_id=user_id,
                persona_id=persona_id,
                enabled_sources=[_SOURCE_ADZUNA, _SOURCE_REMOTEOK],
                trigger=trigger,
            )

        assert _SOURCE_REMOTEOK in result.error_sources

    async def test_jobs_sorted_by_fit_score_in_result(
        self,
        mock_db,
        user_id,
        persona_id,
        _make_poll_result,
    ) -> None:
        """Jobs in result are sorted by fit_score descending."""
        trigger = DiscoveryTrigger(
            trigger_type=TriggerType.MANUAL,
            user_message="Search for jobs",
        )

        poll_result = _make_poll_result(
            processed_jobs=[
                {"id": "1", "title": "Job A", "fit_score": 70},
                {"id": "2", "title": "Job B", "fit_score": 95},
                {"id": "3", "title": "Job C", "fit_score": 82},
            ],
            new_job_count=3,
        )

        with patch(
            _JOB_FETCH_SERVICE,
        ) as mock_cls:
            mock_cls.return_value.run_poll = AsyncMock(return_value=poll_result)
            result = await run_discovery(
                db=mock_db,
                user_id=user_id,
                persona_id=persona_id,
                enabled_sources=[_SOURCE_ADZUNA],
                trigger=trigger,
            )

        assert result.jobs[0]["fit_score"] == 95
        assert result.jobs[1]["fit_score"] == 82
        assert result.jobs[2]["fit_score"] == 70

    async def test_passes_correct_params_to_service(
        self,
        mock_db,
        user_id,
        persona_id,
        _make_poll_result,
    ) -> None:
        """JobFetchService is constructed with correct db/user/persona."""
        trigger = DiscoveryTrigger(
            trigger_type=TriggerType.MANUAL,
            user_message="Find jobs",
        )

        poll_result = _make_poll_result()

        with patch(
            _JOB_FETCH_SERVICE,
        ) as mock_cls:
            mock_cls.return_value.run_poll = AsyncMock(return_value=poll_result)
            await run_discovery(
                db=mock_db,
                user_id=user_id,
                persona_id=persona_id,
                enabled_sources=[_SOURCE_ADZUNA, _SOURCE_REMOTEOK],
                trigger=trigger,
            )

        # Verify constructor received correct params
        mock_cls.assert_called_once_with(
            db=mock_db,
            user_id=user_id,
            persona_id=persona_id,
        )

        # Verify run_poll received sources
        mock_cls.return_value.run_poll.assert_called_once_with(
            enabled_sources=[_SOURCE_ADZUNA, _SOURCE_REMOTEOK],
            polling_frequency="daily",
        )

    async def test_forwards_polling_frequency_to_service(
        self,
        mock_db,
        user_id,
        persona_id,
        _make_poll_result,
    ) -> None:
        """Custom polling_frequency is forwarded to run_poll."""
        trigger = DiscoveryTrigger(
            trigger_type=TriggerType.SCHEDULED,
            next_poll_at=datetime.now(UTC) - timedelta(hours=1),
        )

        poll_result = _make_poll_result()

        with patch(
            _JOB_FETCH_SERVICE,
        ) as mock_cls:
            mock_cls.return_value.run_poll = AsyncMock(return_value=poll_result)
            await run_discovery(
                db=mock_db,
                user_id=user_id,
                persona_id=persona_id,
                enabled_sources=[_SOURCE_ADZUNA],
                trigger=trigger,
                polling_frequency="weekly",
            )

        mock_cls.return_value.run_poll.assert_called_once_with(
            enabled_sources=[_SOURCE_ADZUNA],
            polling_frequency="weekly",
        )
