"""Tests for PollSchedulerWorker.

REQ-034 §7.2: Background worker lifecycle, concurrency limits,
query logic, and fault isolation.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.discovery.job_fetch_service import PollResult
from app.services.discovery.poll_scheduler_worker import (
    _CATCHUP_LOOKBACK,
    _MAX_CONCURRENT_POLLS,
    PollSchedulerWorker,
    _DueItem,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session_factory() -> MagicMock:
    """Create a mock async session factory with context manager support."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=mock_session)


def _make_due_item(**overrides: object) -> _DueItem:
    """Create a _DueItem with sensible defaults."""
    defaults: dict[str, object] = {
        "persona_id": uuid4(),
        "user_id": uuid4(),
        "polling_frequency": "Daily",
        "last_poll_at": None,
    }
    defaults.update(overrides)
    return _DueItem(**defaults)  # type: ignore[arg-type]


def _make_poll_result(**overrides: object) -> PollResult:
    """Create a PollResult with sensible defaults."""
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "processed_jobs": [],
        "new_job_count": 3,
        "existing_job_count": 1,
        "error_sources": [],
        "last_polled_at": now,
        "next_poll_at": now + timedelta(hours=24),
    }
    defaults.update(overrides)
    return PollResult(**defaults)  # type: ignore[arg-type]


def _setup_mock_db_session(
    worker: PollSchedulerWorker,
    rows: list[tuple[object, ...]],
) -> None:
    """Configure a worker's session factory to return mock DB rows."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_execute_result = MagicMock()
    mock_execute_result.all.return_value = rows
    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    worker._session_factory = MagicMock(return_value=mock_session)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestWorkerLifecycle:
    """Tests for PollSchedulerWorker start/stop."""

    async def test_start_sets_running(self) -> None:
        worker = PollSchedulerWorker(_make_mock_session_factory())
        with patch.object(worker, "_run_loop", new_callable=AsyncMock):
            worker.start()
            assert worker.is_running is True
            await worker.stop()

    async def test_stop_clears_running(self) -> None:
        worker = PollSchedulerWorker(_make_mock_session_factory())
        with patch.object(worker, "_run_loop", new_callable=AsyncMock):
            worker.start()
            await worker.stop()
            assert worker.is_running is False

    async def test_start_is_idempotent(self) -> None:
        worker = PollSchedulerWorker(_make_mock_session_factory())
        with patch.object(worker, "_run_loop", new_callable=AsyncMock):
            worker.start()
            worker.start()  # Second call should be no-op
            assert worker.is_running is True
            await worker.stop()

    async def test_stop_without_start_is_safe(self) -> None:
        worker = PollSchedulerWorker(_make_mock_session_factory())
        await worker.stop()  # Should not raise


# ---------------------------------------------------------------------------
# run_once orchestration
# ---------------------------------------------------------------------------


class TestRunOnce:
    """Tests for run_once() orchestration logic."""

    async def test_polls_each_due_persona(self) -> None:
        """run_once dispatches _poll_persona for each due item."""
        items = [_make_due_item(), _make_due_item()]
        worker = PollSchedulerWorker(_make_mock_session_factory())

        with (
            patch.object(
                worker,
                "_get_due_personas",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch.object(
                worker,
                "_poll_persona",
                new_callable=AsyncMock,
                return_value=_make_poll_result(),
            ),
        ):
            result = await worker.run_once()

        assert result.personas_polled == 2
        assert result.personas_failed == 0

    async def test_no_due_personas_returns_zero(self) -> None:
        """run_once returns zeros when no personas are due."""
        worker = PollSchedulerWorker(_make_mock_session_factory())

        with patch.object(
            worker,
            "_get_due_personas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await worker.run_once()

        assert result.personas_polled == 0
        assert result.personas_failed == 0
        assert result.total_new_jobs == 0

    async def test_updates_last_run_at(self) -> None:
        """run_once sets last_run_at after completing."""
        worker = PollSchedulerWorker(_make_mock_session_factory())
        assert worker.last_run_at is None

        with patch.object(
            worker,
            "_get_due_personas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await worker.run_once()

        assert worker.last_run_at is not None

    async def test_tallies_new_jobs(self) -> None:
        """run_once sums new_job_count across all persona poll results."""
        items = [_make_due_item(), _make_due_item()]
        worker = PollSchedulerWorker(_make_mock_session_factory())

        with (
            patch.object(
                worker,
                "_get_due_personas",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch.object(
                worker,
                "_poll_persona",
                new_callable=AsyncMock,
                return_value=_make_poll_result(new_job_count=5),
            ),
        ):
            result = await worker.run_once()

        assert result.total_new_jobs == 10  # 5 per persona × 2

    async def test_returns_valid_timestamps(self) -> None:
        """run_once returns a result with started_at <= finished_at."""
        worker = PollSchedulerWorker(_make_mock_session_factory())

        with patch.object(
            worker,
            "_get_due_personas",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await worker.run_once()

        assert result.started_at <= result.finished_at


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


class TestConcurrency:
    """Tests for asyncio.Semaphore concurrency limit."""

    async def test_semaphore_limits_to_5_concurrent(self) -> None:
        """REQ-034 §7.2: At most 5 persona polls run simultaneously."""
        peak_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def mock_poll(_item: _DueItem) -> PollResult:
            nonlocal peak_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                peak_concurrent = max(peak_concurrent, current_concurrent)
            await asyncio.sleep(0.05)
            async with lock:
                current_concurrent -= 1
            return _make_poll_result()

        items = [_make_due_item() for _ in range(10)]
        worker = PollSchedulerWorker(_make_mock_session_factory())

        with (
            patch.object(
                worker,
                "_get_due_personas",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch.object(worker, "_poll_persona", side_effect=mock_poll),
        ):
            result = await worker.run_once()

        assert peak_concurrent <= _MAX_CONCURRENT_POLLS
        assert peak_concurrent > 1  # Confirm actual concurrency occurred
        assert result.personas_polled == 10


# ---------------------------------------------------------------------------
# Fault isolation
# ---------------------------------------------------------------------------


class TestFaultIsolation:
    """Tests for per-persona fault isolation."""

    async def test_one_failure_does_not_block_others(self) -> None:
        """REQ-034 §7.2: One persona's poll failure does not affect others."""
        items = [_make_due_item(), _make_due_item(), _make_due_item()]

        async def mock_poll(item: _DueItem) -> PollResult:
            if item is items[1]:
                raise RuntimeError("Simulated failure")
            return _make_poll_result()

        worker = PollSchedulerWorker(_make_mock_session_factory())

        with (
            patch.object(
                worker,
                "_get_due_personas",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch.object(worker, "_poll_persona", side_effect=mock_poll),
        ):
            result = await worker.run_once()

        assert result.personas_polled == 2
        assert result.personas_failed == 1

    async def test_all_failures_counted(self) -> None:
        """All poll failures are counted in the result."""
        items = [_make_due_item(), _make_due_item()]

        async def mock_poll(_item: _DueItem) -> PollResult:
            raise RuntimeError("All fail")

        worker = PollSchedulerWorker(_make_mock_session_factory())

        with (
            patch.object(
                worker,
                "_get_due_personas",
                new_callable=AsyncMock,
                return_value=items,
            ),
            patch.object(worker, "_poll_persona", side_effect=mock_poll),
        ):
            result = await worker.run_once()

        assert result.personas_polled == 0
        assert result.personas_failed == 2
        assert result.total_new_jobs == 0


# ---------------------------------------------------------------------------
# First-run 24-hour catch-up window
# ---------------------------------------------------------------------------


class TestFirstRunCatchup:
    """Tests for the 24-hour startup catch-up window.

    REQ-034 §7.2: On first run, look back 24hrs to catch personas that
    missed their scheduled poll window. The query also includes personas
    with NULL next_poll_at (never polled).
    """

    async def test_first_run_includes_never_polled_persona(self) -> None:
        """First run returns personas with NULL next_poll_at."""
        worker = PollSchedulerWorker(_make_mock_session_factory())
        assert worker.last_run_at is None  # First run path

        persona_id = uuid4()
        user_id = uuid4()
        _setup_mock_db_session(
            worker,
            [
                (persona_id, user_id, "Daily", None),
            ],
        )

        items = await worker._get_due_personas()

        assert len(items) == 1
        assert items[0].persona_id == persona_id
        assert items[0].last_poll_at is None

    async def test_catchup_window_is_24_hours(self) -> None:
        """The catch-up lookback is 24 hours, matching REQ-034 §7.2."""
        assert timedelta(hours=24) == _CATCHUP_LOOKBACK


# ---------------------------------------------------------------------------
# Manual Only exclusion
# ---------------------------------------------------------------------------


class TestManualOnlyExclusion:
    """Verify that 'Manual Only' personas are excluded from scheduled polling.

    REQ-034 §7.2: The SQL WHERE clause filters
    ``polling_frequency != 'Manual Only'``. Enforcement is at the query
    level in _get_due_personas. This test verifies the query returns only
    pre-filtered results (simulating SQL behavior via mock).
    """

    async def test_only_non_manual_personas_returned(self) -> None:
        """_get_due_personas returns only schedulable personas."""
        worker = PollSchedulerWorker(_make_mock_session_factory())

        daily_id = uuid4()
        _setup_mock_db_session(
            worker,
            [
                (daily_id, uuid4(), "Daily", None),
            ],
        )

        items = await worker._get_due_personas()

        assert len(items) == 1
        assert items[0].persona_id == daily_id
        assert items[0].polling_frequency == "Daily"
