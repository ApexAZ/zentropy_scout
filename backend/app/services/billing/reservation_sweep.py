"""Stale reservation sweep and balance drift detection background worker.

REQ-030 §11.1: Background task that releases held reservations exceeding
the TTL. Reservations stuck in 'held' status (e.g., due to process crash
or settlement failure) are released by decrementing held_balance_usd and
updating status to 'stale'.

REQ-030 §11.2: Balance/ledger drift detection. Compares users.balance_usd
against SUM(credit_transactions.amount_usd) and logs any drift exceeding
the threshold at error level.

REQ-030 §11.3: Settlement retry for stale reservations with response
metadata (outbox pattern). Before releasing, attempts settlement via
MeteringService.settle() (tier 1), then at estimated cost (tier 2),
then falls back to stale release (tier 3, last resort).

AF-15: Held-balance drift detection. Compares users.held_balance_usd
against SUM(usage_reservations.estimated_cost_usd WHERE status='held').

REQ-030 §2.4: Runs every RESERVATION_SWEEP_INTERVAL_SECONDS (default 300).
TTL controlled by RESERVATION_TTL_SECONDS (default 300).

Coordinates with:
  - admin/admin_config_service.py — imports AdminConfigService for pricing lookups
  - billing/metering_service.py — imports MeteringService for settlement retry

Called by: app/main.py (FastAPI lifespan event) and unit tests.
"""

import asyncio
import contextlib
import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import select, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.usage_reservation import UsageReservation
from app.services.admin.admin_config_service import AdminConfigService
from app.services.billing.metering_service import MeteringService

logger = logging.getLogger(__name__)

_SWEEP_BATCH_LIMIT = 100
_TIER1_SUCCESS_LOG = (
    "Settlement retry (tier 1) succeeded for reservation %s (user %s, $%s)"
)
_TIER2_SUCCESS_LOG = (
    "Settlement retry (tier 2/estimated) succeeded for reservation %s (user %s, $%s)"
)
_TIER2_FAILED_LOG = (
    "Settlement retry (tier 2) failed for reservation %s — "
    "falling through to stale release"
)
_SETTLED_MARGIN = Decimal("1.00")


async def _attempt_settlement_retry(
    db: AsyncSession,
    reservation: UsageReservation,
    metering_service: MeteringService,
) -> bool:
    """Attempt settlement for a stale reservation with response metadata.

    REQ-030 §11.3: Three-tier fallback:
    1. MeteringService.settle() with stored response data.
    2. Settle at estimated cost with inline SQL.
    3. Returns False → caller falls through to stale release.

    Args:
        db: Async database session (same as sweep's session).
        reservation: Stale reservation with call_completed_at IS NOT NULL.
        metering_service: For tier-1 settlement via standard pricing.

    Returns:
        True if settlement succeeded (tier 1 or 2), False for stale release.
    """
    # Guard: metadata columns guaranteed non-NULL by
    # ck_reservation_response_metadata_complete, but mypy can't see DB constraints
    if (
        reservation.provider is None
        or reservation.response_model is None
        or reservation.response_input_tokens is None
        or reservation.response_output_tokens is None
    ):
        logger.warning(
            "Reservation %s has incomplete metadata — skipping retry",
            reservation.id,
        )
        return False

    # Tier 1: settle() with stored response data
    try:
        await metering_service.settle(
            reservation=reservation,
            provider=reservation.provider,
            model=reservation.response_model,
            input_tokens=reservation.response_input_tokens,
            output_tokens=reservation.response_output_tokens,
        )
    except Exception:
        logger.exception(
            "Settlement retry (tier 1) error for reservation %s",
            reservation.id,
        )

    # Refresh from DB — settle() may have partially modified ORM state
    await db.refresh(reservation)

    if reservation.status == "settled":
        logger.info(
            _TIER1_SUCCESS_LOG,
            reservation.id,
            reservation.user_id,
            reservation.actual_cost_usd,
        )
        return True

    # Tier 2: settle at estimated cost with inline SQL
    try:
        async with db.begin_nested():
            now = datetime.now(UTC)
            usage_id = uuid.uuid4()
            txn_id = uuid.uuid4()
            billed_cost = reservation.estimated_cost_usd

            # Insert LLMUsageRecord
            await db.execute(
                text(
                    "INSERT INTO llm_usage_records "
                    "(id, user_id, provider, model, task_type, "
                    "input_tokens, output_tokens, raw_cost_usd, "
                    "billed_cost_usd, margin_multiplier) "
                    "VALUES (:id, :uid, :prov, :model, :task, "
                    ":inp, :out, :raw, :billed, :margin)"
                ),
                {
                    "id": usage_id,
                    "uid": reservation.user_id,
                    "prov": reservation.provider,
                    "model": reservation.response_model,
                    "task": reservation.task_type,
                    "inp": reservation.response_input_tokens,
                    "out": reservation.response_output_tokens,
                    "raw": billed_cost,
                    "billed": billed_cost,
                    "margin": _SETTLED_MARGIN,
                },
            )

            # Insert CreditTransaction (debit)
            await db.execute(
                text(
                    "INSERT INTO credit_transactions "
                    "(id, user_id, amount_usd, transaction_type, "
                    "reference_id, description) "
                    "VALUES (:id, :uid, :amount, 'usage_debit', "
                    ":ref, :desc)"
                ),
                {
                    "id": txn_id,
                    "uid": reservation.user_id,
                    "amount": -billed_cost,
                    "ref": str(usage_id),
                    "desc": (
                        f"{reservation.provider}/{reservation.response_model}"
                        f" - {reservation.task_type} (sweep-estimated)"
                    ),
                },
            )

            # Debit balance + release hold (AF-02: RETURNING for overdraft detection)
            bal_result = await db.execute(
                text(
                    "UPDATE users "
                    "SET balance_usd = balance_usd - :cost, "
                    "    held_balance_usd = held_balance_usd - :estimated "
                    "WHERE id = :uid "
                    "RETURNING balance_usd"
                ),
                {
                    "cost": billed_cost,
                    "estimated": reservation.estimated_cost_usd,
                    "uid": reservation.user_id,
                },
            )
            new_balance: Decimal = bal_result.scalar_one()
            if new_balance < 0:
                logger.error(
                    "Balance overdraft after tier-2 settlement: user %s, "
                    "reservation %s, debit $%s, new balance $%s",
                    reservation.user_id,
                    reservation.id,
                    billed_cost,
                    new_balance,
                )

            # Update reservation to settled (conditional guard)
            updated = cast(
                CursorResult[Any],
                await db.execute(
                    text(
                        "UPDATE usage_reservations "
                        "SET status = 'settled', actual_cost_usd = :cost, "
                        "    settled_at = :now "
                        "WHERE id = :id AND status = 'held'"
                    ),
                    {
                        "cost": billed_cost,
                        "now": now,
                        "id": reservation.id,
                    },
                ),
            )
            if updated.rowcount == 0:
                logger.warning(
                    "Reservation %s already handled during tier 2 — "
                    "savepoint will roll back",
                    reservation.id,
                )
                msg = f"Reservation {reservation.id} already handled"
                raise RuntimeError(msg)

            # Sync ORM state
            reservation.status = "settled"
            reservation.actual_cost_usd = billed_cost
            reservation.settled_at = now

        logger.warning(
            _TIER2_SUCCESS_LOG,
            reservation.id,
            reservation.user_id,
            billed_cost,
        )
        return True

    except Exception:
        logger.exception(
            _TIER2_FAILED_LOG,
            reservation.id,
        )

    return False


async def sweep_stale_reservations(
    db: AsyncSession,
    *,
    ttl_seconds: int = 300,
    metering_service: MeteringService | None = None,
) -> int:
    """Release reservations that exceeded TTL without settlement.

    REQ-030 §11.1: For each stale reservation, atomically decrements
    held_balance_usd and updates status to 'stale'.

    REQ-030 §11.3: If response metadata exists (call_completed_at IS NOT
    NULL) and metering_service is available, attempts settlement retry
    before stale release. Three-tier fallback: settle at actual cost →
    settle at estimated cost → release as stale.

    Args:
        db: Async database session.
        ttl_seconds: Maximum age in seconds for held reservations.
        metering_service: For settlement retry (tier 1). None disables retry.

    Returns:
        Number of stale reservations processed (settled + released).
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

    processed = 0
    for reservation in stale:
        # REQ-030 §11.3: Attempt settlement retry if response metadata exists
        if (
            metering_service is not None
            and reservation.call_completed_at is not None
            and await _attempt_settlement_retry(db, reservation, metering_service)
        ):
            processed += 1
            continue

        # Tier 3 / default: release as stale
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

                processed += 1
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
    return processed


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


async def detect_held_balance_drift(
    db: AsyncSession,
) -> list[dict[str, object]]:
    """Detect drift between users.held_balance_usd and held reservation sum.

    AF-15: Compares cached held balance against the sum of estimated costs
    for all active (status='held') reservations. Any absolute drift exceeding
    the threshold is logged at error level.

    Args:
        db: Async database session.

    Returns:
        List of drift records (user_id, held_balance_usd, reservations_sum, drift).
        Empty list if no drift detected.
    """
    result = await db.execute(
        text(
            "SELECT u.id AS user_id, u.held_balance_usd, "
            "COALESCE(SUM(ur.estimated_cost_usd), 0) AS reservations_sum, "
            "u.held_balance_usd - COALESCE(SUM(ur.estimated_cost_usd), 0) AS drift "
            "FROM users u "
            "LEFT JOIN usage_reservations ur "
            "ON ur.user_id = u.id AND ur.status = 'held' "
            "GROUP BY u.id "
            "HAVING ABS(u.held_balance_usd "
            "- COALESCE(SUM(ur.estimated_cost_usd), 0)) > :threshold"
        ),
        {"threshold": _DRIFT_THRESHOLD},
    )
    rows = result.mappings().all()

    drifts: list[dict[str, object]] = []
    for row in rows:
        drifts.append(
            {
                "user_id": row["user_id"],
                "held_balance_usd": row["held_balance_usd"],
                "reservations_sum": row["reservations_sum"],
                "drift": row["drift"],
            }
        )
        logger.error(
            "Held-balance/reservation drift detected for user %s: "
            "held=$%s, reservations=$%s, drift=$%s",
            row["user_id"],
            row["held_balance_usd"],
            row["reservations_sum"],
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

        REQ-030 §11.3: Constructs MeteringService for settlement retry.

        Returns:
            Number of stale reservations processed (settled + released).
        """
        async with self._session_factory() as db:
            admin_config = AdminConfigService(db)
            metering_service = MeteringService(db, admin_config)
            released = await sweep_stale_reservations(
                db,
                ttl_seconds=settings.reservation_ttl_seconds,
                metering_service=metering_service,
            )
            await db.commit()

        # Drift checks use a separate session (read-only, no writes)
        async with self._session_factory() as db:
            await detect_balance_drift(db)
            await detect_held_balance_drift(db)

        return released

    async def _run_loop(self) -> None:
        """Background loop: sleep → sweep → repeat."""
        try:
            while self._running:
                try:
                    processed = await self.run_once()
                    if processed > 0:
                        logger.info(
                            "Sweep pass: processed %d stale reservations",
                            processed,
                        )
                except Exception:  # noqa: BLE001
                    logger.exception("Error in reservation sweep pass")
                await asyncio.sleep(self._interval_seconds)
        except asyncio.CancelledError:
            logger.debug("Reservation sweep loop cancelled")
            raise
