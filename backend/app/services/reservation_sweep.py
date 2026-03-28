"""Stale reservation sweep and balance drift detection background worker.

REQ-030 §11.1: Background task that releases held reservations exceeding
the TTL. Reservations stuck in 'held' status (e.g., due to process crash
or settlement failure) are released by decrementing held_balance_usd and
updating status to 'stale'.

REQ-030 §11.2: Balance/ledger drift detection. Compares users.balance_usd
against SUM(credit_transactions.amount_usd) and logs any drift exceeding
the threshold at error level.

REQ-030 §2.4: Runs every RESERVATION_SWEEP_INTERVAL_SECONDS (default 300).
TTL controlled by RESERVATION_TTL_SECONDS (default 300).
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import select, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.usage_reservation import UsageReservation

logger = logging.getLogger(__name__)

_SWEEP_BATCH_LIMIT = 100


async def sweep_stale_reservations(
    db: AsyncSession,
    *,
    ttl_seconds: int = 300,
) -> int:
    """Release reservations that exceeded TTL without settlement.

    REQ-030 §11.1: For each stale reservation, atomically decrements
    held_balance_usd and updates status to 'stale'.

    Args:
        db: Async database session.
        ttl_seconds: Maximum age in seconds for held reservations.

    Returns:
        Number of stale reservations released.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=ttl_seconds)
    now = datetime.now(UTC)
    stmt = (
        select(UsageReservation)
        .where(
            UsageReservation.status == "held",
            UsageReservation.created_at < cutoff,
        )
        .with_for_update(skip_locked=True)
        .limit(_SWEEP_BATCH_LIMIT)
    )
    result = await db.execute(stmt)
    stale = result.scalars().all()

    released = 0
    for reservation in stale:
        try:
            async with db.begin_nested():
                # Conditional update prevents double-release
                updated = cast(
                    CursorResult[Any],
                    await db.execute(
                        text(
                            "UPDATE usage_reservations "
                            "SET status = 'stale', settled_at = :now "
                            "WHERE id = :id AND status = 'held'"
                        ),
                        {"now": now, "id": reservation.id},
                    ),
                )
                if updated.rowcount == 0:
                    continue  # Already settled/released by another process

                bal_result = cast(
                    CursorResult[Any],
                    await db.execute(
                        text(
                            "UPDATE users "
                            "SET held_balance_usd = held_balance_usd - :amount "
                            "WHERE id = :user_id"
                        ),
                        {
                            "amount": reservation.estimated_cost_usd,
                            "user_id": reservation.user_id,
                        },
                    ),
                )
                if bal_result.rowcount == 0:
                    logger.error(
                        "Balance decrement failed for reservation %s: "
                        "user %s not found",
                        reservation.id,
                        reservation.user_id,
                    )

                released += 1
                logger.warning(
                    "Released stale reservation %s for user %s (held $%s for %s)",
                    reservation.id,
                    reservation.user_id,
                    reservation.estimated_cost_usd,
                    reservation.task_type,
                )
        except Exception:
            logger.exception("Failed to release reservation %s", reservation.id)

    await db.flush()
    return released


_DRIFT_THRESHOLD = Decimal("0.000001")


async def detect_balance_drift(
    db: AsyncSession,
) -> list[dict[str, object]]:
    """Detect drift between users.balance_usd and credit_transactions ledger.

    REQ-030 §11.2: Compares cached balance against the ledger sum for each
    user. Any absolute drift exceeding the threshold is logged at error level.

    Args:
        db: Async database session.

    Returns:
        List of drift records (user_id, balance_usd, ledger_sum, drift).
        Empty list if no drift detected.
    """
    result = await db.execute(
        text(
            "SELECT u.id AS user_id, u.balance_usd, "
            "COALESCE(SUM(ct.amount_usd), 0) AS ledger_sum, "
            "u.balance_usd - COALESCE(SUM(ct.amount_usd), 0) AS drift "
            "FROM users u "
            "LEFT JOIN credit_transactions ct ON ct.user_id = u.id "
            "GROUP BY u.id "
            "HAVING ABS(u.balance_usd - COALESCE(SUM(ct.amount_usd), 0)) "
            "> :threshold"
        ),
        {"threshold": _DRIFT_THRESHOLD},
    )
    rows = result.mappings().all()

    drifts: list[dict[str, object]] = []
    for row in rows:
        drifts.append(
            {
                "user_id": row["user_id"],
                "balance_usd": row["balance_usd"],
                "ledger_sum": row["ledger_sum"],
                "drift": row["drift"],
            }
        )
        logger.error(
            "Balance/ledger drift detected for user %s: "
            "balance=$%s, ledger=$%s, drift=$%s",
            row["user_id"],
            row["balance_usd"],
            row["ledger_sum"],
            row["drift"],
        )

    return drifts


class ReservationSweepWorker:
    """Background worker that periodically sweeps stale reservations.

    Lifecycle mirrors PoolSurfacingWorker:
    - start() creates an asyncio task running the sweep loop.
    - stop() cancels the task and waits for graceful shutdown.
    - run_once() executes a single sweep pass (for testing).

    Args:
        session_factory: Async session factory for DB access.
        interval_seconds: Seconds between sweep passes.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        interval_seconds: int | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._interval_seconds = (
            interval_seconds
            if interval_seconds is not None
            else settings.reservation_sweep_interval_seconds
        )
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Whether the background task is currently active."""
        return self._running and self._task is not None and not self._task.done()

    def start(self) -> None:
        """Start the background sweep loop.

        Creates an asyncio task. No-op if already running.
        """
        if self.is_running:
            logger.warning("Reservation sweep worker already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Reservation sweep worker started (interval=%ds, ttl=%ds)",
            self._interval_seconds,
            settings.reservation_ttl_seconds,
        )

    async def stop(self) -> None:
        """Stop the background sweep loop.

        Cancels the task and waits for it to finish.
        """
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None
        logger.info("Reservation sweep worker stopped")

    async def run_once(self) -> int:
        """Execute a single sweep pass and drift check.

        Returns:
            Number of stale reservations released.
        """
        async with self._session_factory() as db:
            released = await sweep_stale_reservations(
                db, ttl_seconds=settings.reservation_ttl_seconds
            )
            await db.commit()

        # Drift check uses a separate session (read-only, no writes)
        async with self._session_factory() as db:
            await detect_balance_drift(db)

        return released

    async def _run_loop(self) -> None:
        """Background loop: sleep → sweep → repeat."""
        try:
            while self._running:
                try:
                    released = await self.run_once()
                    if released > 0:
                        logger.info(
                            "Sweep pass: released %d stale reservations",
                            released,
                        )
                except Exception:  # noqa: BLE001
                    logger.exception("Error in reservation sweep pass")
                await asyncio.sleep(self._interval_seconds)
        except asyncio.CancelledError:
            logger.debug("Reservation sweep loop cancelled")
            raise
