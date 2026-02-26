"""Pool surfacing background worker.

REQ-015 §7.1: asyncio background task via FastAPI lifespan event.
Runs the surfacing pass on a configurable interval (~15 min).
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.pool_surfacing_service import SurfacingPassResult, run_surfacing_pass

logger = logging.getLogger(__name__)

# Default interval: 15 minutes (REQ-015 §7.1)
DEFAULT_INTERVAL_SECONDS = 15 * 60

# On first run, look back 24 hours to catch up on missed jobs.
_INITIAL_LOOKBACK = timedelta(hours=24)


class PoolSurfacingWorker:
    """Background worker that periodically surfaces pool jobs to personas.

    Lifecycle:
    - start() creates an asyncio task that runs the surfacing loop.
    - stop() cancels the task and waits for graceful shutdown.
    - run_once() executes a single pass (for testing).

    Args:
        session_factory: Async session factory for DB access.
        interval_seconds: Seconds between surfacing passes.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._interval_seconds = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._last_run_at: datetime | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Whether the background task is currently active."""
        return self._running and self._task is not None and not self._task.done()

    @property
    def last_run_at(self) -> datetime | None:
        """Timestamp of the most recent completed pass."""
        return self._last_run_at

    def start(self) -> None:
        """Start the background surfacing loop.

        Creates an asyncio task. No-op if already running.
        Must be called from an async context (running event loop).
        """
        if self.is_running:
            logger.warning("Pool surfacing worker already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Pool surfacing worker started (interval=%ds)", self._interval_seconds
        )

    async def stop(self) -> None:
        """Stop the background surfacing loop.

        Cancels the task and waits for it to finish.
        """
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        logger.info("Pool surfacing worker stopped")

    async def run_once(self) -> SurfacingPassResult:
        """Execute a single surfacing pass.

        Useful for testing without starting the full loop.

        Returns:
            SurfacingPassResult with statistics from the pass.
        """
        since = self._get_since()
        async with self._session_factory() as db:
            result = await run_surfacing_pass(db, since=since)
        self._last_run_at = result.finished_at
        return result

    async def _run_loop(self) -> None:
        """Background loop: sleep → run_surfacing_pass → repeat."""
        try:
            while self._running:
                try:
                    result = await self.run_once()
                    logger.info(
                        "Surfacing pass: %d jobs, %d links created",
                        result.jobs_processed,
                        result.links_created,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Error in surfacing pass")
                await asyncio.sleep(self._interval_seconds)
        except asyncio.CancelledError:
            logger.debug("Surfacing loop cancelled")
            raise

    def _get_since(self) -> datetime:
        """Determine the 'since' timestamp for the next pass."""
        if self._last_run_at is not None:
            return self._last_run_at
        return datetime.now(UTC) - _INITIAL_LOOKBACK
