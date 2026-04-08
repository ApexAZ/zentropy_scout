"""Poll scheduler background worker.

REQ-034 §7.2: asyncio background task that reads next_poll_at from
PollingConfiguration and triggers polls on schedule. Wakes every 30
minutes, queries due personas, and dispatches polls with a concurrency
limit of 5 via asyncio.Semaphore.

Coordinates with:
  - discovery/poll_execution.py — imports execute_persona_poll
  - models/persona.py — Persona (onboarding_complete, polling_frequency)
  - models/job_source.py — PollingConfiguration (next_poll_at)

Called by: app/main.py (FastAPI lifespan event) and unit tests.
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.job_source import PollingConfiguration
from app.models.persona import Persona
from app.services.discovery.job_fetch_service import PollResult
from app.services.discovery.poll_execution import execute_persona_poll

logger = logging.getLogger(__name__)

# REQ-034 §7.2: Check every 30 minutes
DEFAULT_INTERVAL_SECONDS = 30 * 60

# REQ-034 §7.2: Limit concurrent persona polls to avoid DB contention
_MAX_CONCURRENT_POLLS = 5

# REQ-034 §7.2: First-run lookback window to catch missed polls
_CATCHUP_LOOKBACK = timedelta(hours=24)

# Cap due personas per pass to bound memory and execution time.
# Overflow is caught on the next scheduler cycle.
_MAX_DUE_PER_PASS = 100


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DueItem:
    """Lightweight tuple of fields needed to poll a single persona."""

    persona_id: UUID
    user_id: UUID
    polling_frequency: str
    last_poll_at: datetime | None


@dataclass
class SchedulerPassResult:
    """Statistics from a single scheduler pass.

    Attributes:
        personas_polled: Number of personas successfully polled.
        personas_failed: Number of personas whose poll raised an exception.
        total_new_jobs: Sum of new_job_count across all successful polls.
        started_at: When this pass began.
        finished_at: When this pass completed.
    """

    personas_polled: int
    personas_failed: int
    total_new_jobs: int
    started_at: datetime
    finished_at: datetime


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


class PollSchedulerWorker:
    """Background worker that triggers scheduled polls for due personas.

    REQ-034 §7.2: Reads PollingConfiguration.next_poll_at and fires
    JobFetchService.run_poll() for each due persona. Concurrency capped
    at 5 via asyncio.Semaphore. First run looks back 24hrs.

    Lifecycle:
    - start() creates an asyncio task that runs the polling loop.
    - stop() cancels the task and waits for graceful shutdown.
    - run_once() executes a single pass (for testing).

    Args:
        session_factory: Async session factory for DB access.
        interval_seconds: Seconds between scheduler passes.
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
        """Start the background polling loop.

        Creates an asyncio task. No-op if already running.
        Must be called from an async context (running event loop).
        """
        if self.is_running:
            logger.warning("Poll scheduler worker already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Poll scheduler worker started (interval=%ds)", self._interval_seconds
        )

    async def stop(self) -> None:
        """Stop the background polling loop.

        Cancels the task and waits for it to finish.
        """
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        logger.info("Poll scheduler worker stopped")

    async def run_once(self) -> SchedulerPassResult:
        """Execute a single scheduler pass.

        Queries due personas, polls each with concurrency limit,
        and tallies results.

        Returns:
            SchedulerPassResult with per-pass statistics.
        """
        started_at = datetime.now(UTC)
        due_items = await self._get_due_personas()

        if not due_items:
            finished = datetime.now(UTC)
            self._last_run_at = finished
            return SchedulerPassResult(
                personas_polled=0,
                personas_failed=0,
                total_new_jobs=0,
                started_at=started_at,
                finished_at=finished,
            )

        sem = asyncio.Semaphore(_MAX_CONCURRENT_POLLS)

        async def _poll_with_limit(item: _DueItem) -> PollResult:
            async with sem:
                return await self._poll_persona(item)

        results = await asyncio.gather(
            *[_poll_with_limit(item) for item in due_items],
            return_exceptions=True,
        )

        polled = 0
        failed = 0
        new_jobs = 0
        for item, r in zip(due_items, results, strict=True):
            if isinstance(r, BaseException):
                failed += 1
                logger.error("Poll failed for persona %s: %s", item.persona_id, r)
            else:
                polled += 1
                new_jobs += r.new_job_count

        finished = datetime.now(UTC)
        self._last_run_at = finished
        return SchedulerPassResult(
            personas_polled=polled,
            personas_failed=failed,
            total_new_jobs=new_jobs,
            started_at=started_at,
            finished_at=finished,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Background loop: run_once → sleep → repeat."""
        try:
            while self._running:
                try:
                    result = await self.run_once()
                    logger.info(
                        "Scheduler pass: %d polled, %d failed, %d new jobs",
                        result.personas_polled,
                        result.personas_failed,
                        result.total_new_jobs,
                    )
                # WHY BLE001: The scheduler loop must never crash — individual
                # pass errors are logged and the loop continues.
                except Exception:  # noqa: BLE001
                    logger.exception("Error in scheduler pass")
                await asyncio.sleep(self._interval_seconds)
        except asyncio.CancelledError:
            logger.debug("Scheduler loop cancelled")
            raise

    async def _get_due_personas(self) -> list[_DueItem]:
        """Query personas due for polling.

        REQ-034 §7.2: Filters onboarding_complete, excludes Manual Only.
        First run: 24hr lookback + NULL next_poll_at. Subsequent: all overdue.
        Ordered by next_poll_at ASC, capped at _MAX_DUE_PER_PASS.
        """
        now = datetime.now(UTC)
        is_first_run = self._last_run_at is None

        async with self._session_factory() as db:
            stmt = (
                select(
                    Persona.id,
                    Persona.user_id,
                    Persona.polling_frequency,
                    PollingConfiguration.last_poll_at,
                )
                .outerjoin(
                    PollingConfiguration,
                    PollingConfiguration.persona_id == Persona.id,
                )
                .where(
                    Persona.onboarding_complete == true(),
                    Persona.polling_frequency != "Manual Only",
                )
            )

            if is_first_run:
                lookback = now - _CATCHUP_LOOKBACK
                stmt = stmt.where(
                    or_(
                        and_(
                            PollingConfiguration.next_poll_at <= now,
                            PollingConfiguration.next_poll_at >= lookback,
                        ),
                        PollingConfiguration.next_poll_at.is_(None),
                    )
                )
            else:
                stmt = stmt.where(PollingConfiguration.next_poll_at <= now)

            stmt = stmt.order_by(PollingConfiguration.next_poll_at.asc()).limit(
                _MAX_DUE_PER_PASS
            )

            result = await db.execute(stmt)
            rows = result.all()

        return [
            _DueItem(
                persona_id=row[0],
                user_id=row[1],
                polling_frequency=row[2],
                last_poll_at=row[3],
            )
            for row in rows
        ]

    async def _poll_persona(self, item: _DueItem) -> PollResult:
        """Delegate to execute_persona_poll with fault-isolated session."""
        return await execute_persona_poll(self._session_factory, item)
