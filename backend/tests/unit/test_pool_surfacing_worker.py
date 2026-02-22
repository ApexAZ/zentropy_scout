"""Tests for pool surfacing worker lifecycle.

REQ-015 §7.1: asyncio background task lifecycle (start/stop/run_once).
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.pool_surfacing_service import SurfacingPassResult
from app.services.pool_surfacing_worker import (
    _INITIAL_LOOKBACK,
    DEFAULT_INTERVAL_SECONDS,
    PoolSurfacingWorker,
)

_PATCH_RUN_SURFACING = "app.services.pool_surfacing_worker.run_surfacing_pass"


def _make_pass_result(**overrides: int) -> SurfacingPassResult:
    """Create a SurfacingPassResult with sensible defaults."""
    now = datetime.now(UTC)
    defaults = {
        "jobs_processed": 5,
        "links_created": 2,
        "links_skipped_threshold": 3,
        "links_skipped_existing": 0,
        "started_at": now,
        "finished_at": now,
    }
    defaults.update(overrides)
    return SurfacingPassResult(**defaults)


@pytest.fixture
def mock_session_factory() -> MagicMock:
    """Create a mock async session factory with context manager support."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=mock_session)


class TestWorkerLifecycle:
    """Tests for PoolSurfacingWorker start/stop."""

    async def test_start_sets_running(self) -> None:
        mock_factory = MagicMock()
        worker = PoolSurfacingWorker(mock_factory, interval_seconds=60)

        with patch.object(worker, "_run_loop", new_callable=AsyncMock):
            await worker.start()
            assert worker.is_running is True
            await worker.stop()

    async def test_stop_clears_running(self) -> None:
        mock_factory = MagicMock()
        worker = PoolSurfacingWorker(mock_factory, interval_seconds=60)

        with patch.object(worker, "_run_loop", new_callable=AsyncMock):
            await worker.start()
            await worker.stop()
            assert worker.is_running is False

    async def test_start_is_idempotent(self) -> None:
        mock_factory = MagicMock()
        worker = PoolSurfacingWorker(mock_factory, interval_seconds=60)

        with patch.object(worker, "_run_loop", new_callable=AsyncMock):
            await worker.start()
            await worker.start()  # Second call should be no-op
            assert worker.is_running is True
            await worker.stop()

    async def test_stop_without_start_is_safe(self) -> None:
        mock_factory = MagicMock()
        worker = PoolSurfacingWorker(mock_factory, interval_seconds=60)
        await worker.stop()  # Should not raise

    async def test_default_interval(self) -> None:
        mock_factory = MagicMock()
        worker = PoolSurfacingWorker(mock_factory)
        assert worker._interval_seconds == DEFAULT_INTERVAL_SECONDS


class TestWorkerRunOnce:
    """Tests for PoolSurfacingWorker.run_once()."""

    async def test_run_once_calls_surfacing_pass(
        self, mock_session_factory: MagicMock
    ) -> None:
        mock_result = _make_pass_result()
        worker = PoolSurfacingWorker(mock_session_factory, interval_seconds=60)

        with patch(
            _PATCH_RUN_SURFACING,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_pass:
            result = await worker.run_once()

        assert result == mock_result
        mock_pass.assert_called_once()

    async def test_run_once_updates_last_run_at(
        self, mock_session_factory: MagicMock
    ) -> None:
        mock_result = _make_pass_result()
        worker = PoolSurfacingWorker(mock_session_factory, interval_seconds=60)

        assert worker.last_run_at is None

        with patch(
            _PATCH_RUN_SURFACING,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            await worker.run_once()

        assert worker.last_run_at == mock_result.finished_at

    async def test_first_run_uses_initial_lookback(
        self, mock_session_factory: MagicMock
    ) -> None:
        mock_result = _make_pass_result()
        worker = PoolSurfacingWorker(mock_session_factory, interval_seconds=60)

        with patch(
            _PATCH_RUN_SURFACING,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_pass:
            before = datetime.now(UTC)
            await worker.run_once()

        # The 'since' should be approximately now - 24 hours
        call_kwargs = mock_pass.call_args
        since_arg = call_kwargs.kwargs["since"]
        expected_earliest = before - _INITIAL_LOOKBACK - timedelta(seconds=5)
        assert since_arg >= expected_earliest

    async def test_subsequent_run_uses_last_run_timestamp(
        self, mock_session_factory: MagicMock
    ) -> None:
        mock_result = _make_pass_result()
        worker = PoolSurfacingWorker(mock_session_factory, interval_seconds=60)

        with patch(
            _PATCH_RUN_SURFACING,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            await worker.run_once()  # Sets last_run_at

        with patch(
            _PATCH_RUN_SURFACING,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_pass:
            await worker.run_once()  # Should use last_run_at as 'since'

        call_kwargs = mock_pass.call_args
        since_arg = call_kwargs.kwargs["since"]
        assert since_arg == mock_result.finished_at
