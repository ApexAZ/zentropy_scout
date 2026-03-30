"""Tests for stale reservation sweep, drift detection, and worker lifecycle.

REQ-030 §11.1: Background sweep releases reservations that exceeded TTL.
REQ-030 §11.2: Balance/ledger drift detection.
REQ-030 §11.3: Settlement retry for stale reservations with response metadata.
REQ-030 §2.4: Configurable interval and TTL via settings.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_reservation import UsageReservation
from app.models.user import User
from app.services.admin.admin_config_service import AdminConfigService
from app.services.billing.metering_service import MeteringService
from app.services.billing.reservation_sweep import (
    ReservationSweepWorker,
    detect_held_balance_drift,
    sweep_stale_reservations,
)

_PATCH_SETTINGS = "app.services.billing.reservation_sweep.settings"
_PATCH_SWEEP = "app.services.billing.reservation_sweep.sweep_stale_reservations"
_PATCH_DRIFT = "app.services.billing.reservation_sweep.detect_balance_drift"
_PATCH_HELD_DRIFT = "app.services.billing.reservation_sweep.detect_held_balance_drift"
_PATCH_RETRY = "app.services.billing.reservation_sweep._attempt_settlement_retry"

_DEFAULT_TTL = 300

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DEFAULT_ESTIMATED = Decimal("0.050000")
_FAKE_SETTLE_COST = Decimal("0.003000")
_USER_BALANCE = Decimal("10.000000")
_USER_HELD = Decimal("0.100000")

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _seed_user(db: AsyncSession) -> User:
    """Create a test user with known balance and held balance."""
    user = User(
        id=TEST_USER_ID,
        email="sweep-test@example.com",
        name="Sweep Test User",
        balance_usd=_USER_BALANCE,
        held_balance_usd=_USER_HELD,
    )
    db.add(user)
    await db.flush()
    return user


async def _seed_reservation(
    db: AsyncSession,
    *,
    user_id: uuid.UUID = TEST_USER_ID,
    status: str = "held",
    estimated_cost: Decimal = _DEFAULT_ESTIMATED,
    created_at: datetime | None = None,
) -> UsageReservation:
    """Insert a reservation with optional overrides."""
    reservation = UsageReservation(
        user_id=user_id,
        estimated_cost_usd=estimated_cost,
        status=status,
        task_type="extraction",
        provider="claude",
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
    )
    db.add(reservation)
    await db.flush()

    # Override created_at after flush so server_default is bypassed
    if created_at is not None:
        await db.execute(
            text("UPDATE usage_reservations SET created_at = :ts WHERE id = :id"),
            {"ts": created_at, "id": reservation.id},
        )
        await db.refresh(reservation)

    return reservation


@pytest.fixture
def mock_session_factory() -> MagicMock:
    """Create a mock async session factory with context manager support."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return MagicMock(return_value=mock_session)


# ---------------------------------------------------------------------------
# sweep_stale_reservations tests
# ---------------------------------------------------------------------------


class TestSweepStaleReservations:
    """Tests for the sweep_stale_reservations function."""

    async def test_releases_stale_held_reservations(
        self, db_session: AsyncSession
    ) -> None:
        """Held reservation past TTL should become stale, held_balance decremented."""
        await _seed_user(db_session)
        stale_time = datetime.now(UTC) - timedelta(seconds=400)
        reservation = await _seed_reservation(db_session, created_at=stale_time)

        released = await sweep_stale_reservations(db_session, ttl_seconds=_DEFAULT_TTL)

        assert released == 1

        # Refresh via raw SQL since ORM object may be stale after raw UPDATE
        row = await db_session.execute(
            text("SELECT status, settled_at FROM usage_reservations WHERE id = :id"),
            {"id": reservation.id},
        )
        result = row.one()
        assert result.status == "stale"
        assert result.settled_at is not None

        # Verify held_balance decremented
        user = await db_session.get(User, TEST_USER_ID)
        assert user is not None
        expected_held = _USER_HELD - _DEFAULT_ESTIMATED
        assert user.held_balance_usd == expected_held

    async def test_ignores_recent_held_reservations(
        self, db_session: AsyncSession
    ) -> None:
        """Held reservation within TTL should NOT be released."""
        await _seed_user(db_session)
        recent_time = datetime.now(UTC) - timedelta(seconds=100)
        reservation = await _seed_reservation(db_session, created_at=recent_time)

        released = await sweep_stale_reservations(db_session, ttl_seconds=_DEFAULT_TTL)

        assert released == 0
        await db_session.refresh(reservation)
        assert reservation.status == "held"

    async def test_ignores_non_held_reservations(
        self, db_session: AsyncSession
    ) -> None:
        """Settled/released/stale reservations are not affected by sweep."""
        await _seed_user(db_session)
        old_time = datetime.now(UTC) - timedelta(seconds=600)

        for status in ("settled", "released", "stale"):
            await _seed_reservation(db_session, status=status, created_at=old_time)

        released = await sweep_stale_reservations(db_session, ttl_seconds=_DEFAULT_TTL)
        assert released == 0

    async def test_releases_multiple_stale_reservations(
        self, db_session: AsyncSession
    ) -> None:
        """Multiple stale reservations are all released in one sweep."""
        user = await _seed_user(db_session)
        # Set held balance to cover both reservations
        await db_session.execute(
            text("UPDATE users SET held_balance_usd = :amt WHERE id = :uid"),
            {"amt": Decimal("0.200000"), "uid": user.id},
        )
        stale_time = datetime.now(UTC) - timedelta(seconds=400)

        r1 = await _seed_reservation(db_session, created_at=stale_time)
        r2 = await _seed_reservation(db_session, created_at=stale_time)

        released = await sweep_stale_reservations(db_session, ttl_seconds=_DEFAULT_TTL)

        assert released == 2

        # Verify via raw SQL since ORM objects may be stale
        for r in (r1, r2):
            row = await db_session.execute(
                text("SELECT status FROM usage_reservations WHERE id = :id"),
                {"id": r.id},
            )
            assert row.scalar_one() == "stale"

    async def test_configurable_ttl(self, db_session: AsyncSession) -> None:
        """TTL parameter controls the cutoff age."""
        await _seed_user(db_session)
        # 200 seconds old — stale with 100s TTL, but not with 300s
        mid_time = datetime.now(UTC) - timedelta(seconds=200)
        await _seed_reservation(db_session, created_at=mid_time)

        assert await sweep_stale_reservations(db_session, ttl_seconds=_DEFAULT_TTL) == 0
        assert await sweep_stale_reservations(db_session, ttl_seconds=100) == 1

    async def test_returns_zero_when_no_stale(self, db_session: AsyncSession) -> None:
        """Returns 0 when there are no held reservations at all."""
        await _seed_user(db_session)
        released = await sweep_stale_reservations(db_session, ttl_seconds=_DEFAULT_TTL)
        assert released == 0


# ---------------------------------------------------------------------------
# Held-balance drift detection tests (AF-15)
# ---------------------------------------------------------------------------


class TestDetectHeldBalanceDrift:
    """Tests for detect_held_balance_drift function.

    AF-15: Compares users.held_balance_usd against SUM of estimated costs
    for active (status='held') reservations.
    """

    async def test_detects_drift_when_held_exceeds_reservations(
        self, db_session: AsyncSession
    ) -> None:
        """Drift detected when held_balance_usd > SUM of held reservation costs."""
        # User has held_balance=0.100000 but only one held reservation at 0.050000
        await _seed_user(db_session)
        await _seed_reservation(
            db_session, estimated_cost=_DEFAULT_ESTIMATED, status="held"
        )

        drifts = await detect_held_balance_drift(db_session)

        assert len(drifts) == 1
        assert drifts[0]["user_id"] == TEST_USER_ID
        assert drifts[0]["held_balance_usd"] == _USER_HELD
        assert drifts[0]["reservations_sum"] == _DEFAULT_ESTIMATED
        expected_drift = _USER_HELD - _DEFAULT_ESTIMATED
        assert drifts[0]["drift"] == expected_drift

    async def test_no_drift_when_values_match(self, db_session: AsyncSession) -> None:
        """No drift when held_balance_usd matches SUM of held reservations."""
        await _seed_user(db_session)
        # Set held_balance to exactly match the reservation
        await db_session.execute(
            text("UPDATE users SET held_balance_usd = :amt WHERE id = :uid"),
            {"amt": _DEFAULT_ESTIMATED, "uid": TEST_USER_ID},
        )
        await _seed_reservation(
            db_session, estimated_cost=_DEFAULT_ESTIMATED, status="held"
        )

        drifts = await detect_held_balance_drift(db_session)

        assert drifts == []

    async def test_zero_held_no_reservations_no_drift(
        self, db_session: AsyncSession
    ) -> None:
        """User with zero held_balance and no reservations produces no drift."""
        await _seed_user(db_session)
        await db_session.execute(
            text("UPDATE users SET held_balance_usd = 0 WHERE id = :uid"),
            {"uid": TEST_USER_ID},
        )

        drifts = await detect_held_balance_drift(db_session)

        assert drifts == []

    async def test_excludes_non_held_reservations(
        self, db_session: AsyncSession
    ) -> None:
        """Only 'held' reservations contribute to the sum; settled/released/stale are excluded."""
        await _seed_user(db_session)
        # Set held_balance to match one held reservation
        await db_session.execute(
            text("UPDATE users SET held_balance_usd = :amt WHERE id = :uid"),
            {"amt": _DEFAULT_ESTIMATED, "uid": TEST_USER_ID},
        )
        # One held reservation matching the balance
        await _seed_reservation(
            db_session, estimated_cost=_DEFAULT_ESTIMATED, status="held"
        )
        # Non-held reservations should not affect drift calculation
        for status in ("settled", "released", "stale"):
            await _seed_reservation(
                db_session, estimated_cost=_DEFAULT_ESTIMATED, status=status
            )

        drifts = await detect_held_balance_drift(db_session)

        assert drifts == []

    async def test_detects_negative_drift_when_reservations_exceed_held(
        self, db_session: AsyncSession
    ) -> None:
        """Drift detected when SUM of held reservations > held_balance_usd."""
        await _seed_user(db_session)
        # Set held_balance to 0.050000 but create two held reservations at 0.050000 each
        await db_session.execute(
            text("UPDATE users SET held_balance_usd = :amt WHERE id = :uid"),
            {"amt": _DEFAULT_ESTIMATED, "uid": TEST_USER_ID},
        )
        await _seed_reservation(
            db_session, estimated_cost=_DEFAULT_ESTIMATED, status="held"
        )
        await _seed_reservation(
            db_session, estimated_cost=_DEFAULT_ESTIMATED, status="held"
        )

        drifts = await detect_held_balance_drift(db_session)

        assert len(drifts) == 1
        expected_drift = _DEFAULT_ESTIMATED - (2 * _DEFAULT_ESTIMATED)
        assert drifts[0]["drift"] == expected_drift

    async def test_drift_logs_at_error_level(self, db_session: AsyncSession) -> None:
        """Drift detection logs at error level when drift is found."""
        await _seed_user(db_session)
        # User has held_balance=0.100000, no held reservations → drift
        await _seed_reservation(
            db_session, estimated_cost=_DEFAULT_ESTIMATED, status="settled"
        )

        with patch("app.services.billing.reservation_sweep.logger") as mock_logger:
            drifts = await detect_held_balance_drift(db_session)

        assert len(drifts) == 1
        mock_logger.error.assert_called_once()


# ---------------------------------------------------------------------------
# ReservationSweepWorker tests
# ---------------------------------------------------------------------------


class TestReservationSweepWorker:
    """Tests for the background worker lifecycle."""

    async def test_start_sets_running(self) -> None:
        """Worker.start() creates an asyncio task."""
        mock_factory = MagicMock()
        worker = ReservationSweepWorker(mock_factory, interval_seconds=60)

        with patch.object(worker, "_run_loop", new_callable=AsyncMock):
            worker.start()
            assert worker.is_running is True
            await worker.stop()

    async def test_stop_clears_running(self) -> None:
        """Worker.stop() cancels the task."""
        mock_factory = MagicMock()
        worker = ReservationSweepWorker(mock_factory, interval_seconds=60)

        with patch.object(worker, "_run_loop", new_callable=AsyncMock):
            worker.start()
            await worker.stop()
            assert worker.is_running is False

    async def test_run_once_calls_sweep_and_commits(
        self, mock_session_factory: MagicMock
    ) -> None:
        """run_once() opens a session, calls sweep, and commits."""
        mock_session = mock_session_factory.return_value
        worker = ReservationSweepWorker(mock_session_factory, interval_seconds=60)

        with (
            patch(
                _PATCH_SWEEP,
                new_callable=AsyncMock,
                return_value=3,
            ) as mock_sweep,
            patch(_PATCH_DRIFT, new_callable=AsyncMock),
            patch(_PATCH_HELD_DRIFT, new_callable=AsyncMock),
            patch(_PATCH_SETTINGS) as mock_settings,
        ):
            mock_settings.reservation_ttl_seconds = _DEFAULT_TTL
            released = await worker.run_once()

        assert released == 3
        mock_sweep.assert_called_once()
        assert mock_sweep.call_args.args[0] is mock_session
        assert mock_sweep.call_args.kwargs["ttl_seconds"] == _DEFAULT_TTL
        mock_session.commit.assert_awaited_once()

    async def test_run_once_uses_configured_ttl(
        self, mock_session_factory: MagicMock
    ) -> None:
        """run_once() passes the configured TTL from settings."""
        worker = ReservationSweepWorker(mock_session_factory, interval_seconds=60)

        with (
            patch(
                _PATCH_SWEEP,
                new_callable=AsyncMock,
                return_value=0,
            ) as mock_sweep,
            patch(_PATCH_DRIFT, new_callable=AsyncMock),
            patch(_PATCH_HELD_DRIFT, new_callable=AsyncMock),
            patch(_PATCH_SETTINGS) as mock_settings,
        ):
            mock_settings.reservation_ttl_seconds = 600
            await worker.run_once()

        assert mock_sweep.call_args.kwargs["ttl_seconds"] == 600

    async def test_run_once_calls_drift_detection(
        self, mock_session_factory: MagicMock
    ) -> None:
        """run_once() calls drift detection after sweep."""
        mock_session = mock_session_factory.return_value
        worker = ReservationSweepWorker(mock_session_factory, interval_seconds=60)

        with (
            patch(_PATCH_SWEEP, new_callable=AsyncMock, return_value=0),
            patch(_PATCH_DRIFT, new_callable=AsyncMock, return_value=[]) as mock_drift,
            patch(_PATCH_HELD_DRIFT, new_callable=AsyncMock),
            patch(_PATCH_SETTINGS) as mock_settings,
        ):
            mock_settings.reservation_ttl_seconds = _DEFAULT_TTL
            await worker.run_once()

        mock_drift.assert_called_once_with(mock_session)

    async def test_run_once_calls_held_drift_detection(
        self, mock_session_factory: MagicMock
    ) -> None:
        """AF-15: run_once() calls held-balance drift detection after sweep."""
        mock_session = mock_session_factory.return_value
        worker = ReservationSweepWorker(mock_session_factory, interval_seconds=60)

        with (
            patch(_PATCH_SWEEP, new_callable=AsyncMock, return_value=0),
            patch(_PATCH_DRIFT, new_callable=AsyncMock),
            patch(
                _PATCH_HELD_DRIFT, new_callable=AsyncMock, return_value=[]
            ) as mock_held_drift,
            patch(_PATCH_SETTINGS) as mock_settings,
        ):
            mock_settings.reservation_ttl_seconds = _DEFAULT_TTL
            await worker.run_once()

        mock_held_drift.assert_called_once_with(mock_session)

    async def test_double_start_is_noop(self) -> None:
        """Calling start() twice does not create duplicate tasks."""
        mock_factory = MagicMock()
        worker = ReservationSweepWorker(mock_factory, interval_seconds=60)

        with patch.object(worker, "_run_loop", new_callable=AsyncMock):
            worker.start()
            first_task = worker._task
            worker.start()  # Should be no-op
            assert worker._task is first_task
            assert worker.is_running is True
            await worker.stop()

    async def test_run_once_passes_metering_service_to_sweep(
        self, mock_session_factory: MagicMock
    ) -> None:
        """REQ-030 §11.3: run_once() constructs MeteringService and passes to sweep."""
        mock_session = mock_session_factory.return_value
        worker = ReservationSweepWorker(mock_session_factory, interval_seconds=60)

        with (
            patch(
                _PATCH_SWEEP,
                new_callable=AsyncMock,
                return_value=0,
            ) as mock_sweep,
            patch(_PATCH_DRIFT, new_callable=AsyncMock),
            patch(_PATCH_HELD_DRIFT, new_callable=AsyncMock),
            patch(_PATCH_SETTINGS) as mock_settings,
        ):
            mock_settings.reservation_ttl_seconds = _DEFAULT_TTL
            await worker.run_once()

        call_kwargs = mock_sweep.call_args.kwargs
        assert "metering_service" in call_kwargs
        # Verify MeteringService was constructed with the sweep's DB session
        assert call_kwargs["metering_service"]._db is mock_session


# ---------------------------------------------------------------------------
# Helpers for settlement retry tests
# ---------------------------------------------------------------------------


async def _add_response_metadata(
    db: AsyncSession,
    reservation: UsageReservation,
    *,
    model: str = "claude-sonnet-4-20250514",
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> None:
    """Add response metadata to a reservation (outbox pattern, §5.8)."""
    await db.execute(
        text(
            "UPDATE usage_reservations "
            "SET response_model = :model, response_input_tokens = :inp, "
            "    response_output_tokens = :out, call_completed_at = :ts "
            "WHERE id = :id"
        ),
        {
            "model": model,
            "inp": input_tokens,
            "out": output_tokens,
            "ts": datetime.now(UTC),
            "id": reservation.id,
        },
    )
    # Expire the specific reservation so next ORM access re-reads from DB
    # (raw SQL bypasses the identity map cache). Only expire the reservation,
    # not all objects — expiring the User triggers MissingGreenlet.
    db.expire(reservation)


# ---------------------------------------------------------------------------
# Settlement retry tests (REQ-030 §11.3)
# ---------------------------------------------------------------------------


class TestSweepSettlementRetry:
    """REQ-030 §11.3: Settlement retry for stale reservations with response metadata."""

    async def test_metadata_triggers_settlement_not_stale(
        self, db_session: AsyncSession
    ) -> None:
        """Stale reservation with response metadata → settled via retry (tier 1)."""
        await _seed_user(db_session)
        stale_time = datetime.now(UTC) - timedelta(seconds=400)
        reservation = await _seed_reservation(db_session, created_at=stale_time)
        await _add_response_metadata(db_session, reservation)

        # Mock MeteringService where settle() succeeds (simulates real settle)
        mock_metering = AsyncMock(spec=MeteringService)

        async def _fake_settle(
            reservation: UsageReservation,
            _provider: str,
            _model: str,
            _input_tokens: int,
            _output_tokens: int,
        ) -> None:
            now = datetime.now(UTC)
            await db_session.execute(
                text(
                    "UPDATE usage_reservations "
                    "SET status = 'settled', actual_cost_usd = :cost, "
                    "    settled_at = :now "
                    "WHERE id = :id AND status = 'held'"
                ),
                {"cost": _FAKE_SETTLE_COST, "now": now, "id": reservation.id},
            )
            await db_session.execute(
                text(
                    "UPDATE users SET balance_usd = balance_usd - :cost, "
                    "held_balance_usd = held_balance_usd - :est "
                    "WHERE id = :uid"
                ),
                {
                    "cost": _FAKE_SETTLE_COST,
                    "est": reservation.estimated_cost_usd,
                    "uid": reservation.user_id,
                },
            )
            reservation.status = "settled"
            reservation.actual_cost_usd = _FAKE_SETTLE_COST

        mock_metering.settle = AsyncMock(side_effect=_fake_settle)

        released = await sweep_stale_reservations(
            db_session,
            ttl_seconds=_DEFAULT_TTL,
            metering_service=mock_metering,
        )

        assert released == 1
        row = await db_session.execute(
            text("SELECT status FROM usage_reservations WHERE id = :id"),
            {"id": reservation.id},
        )
        assert row.scalar_one() == "settled"

    async def test_no_metadata_releases_as_stale(
        self, db_session: AsyncSession
    ) -> None:
        """Stale reservation without call_completed_at → normal stale release."""
        await _seed_user(db_session)
        stale_time = datetime.now(UTC) - timedelta(seconds=400)
        reservation = await _seed_reservation(db_session, created_at=stale_time)

        mock_metering = AsyncMock(spec=MeteringService)
        released = await sweep_stale_reservations(
            db_session,
            ttl_seconds=_DEFAULT_TTL,
            metering_service=mock_metering,
        )

        assert released == 1
        row = await db_session.execute(
            text("SELECT status FROM usage_reservations WHERE id = :id"),
            {"id": reservation.id},
        )
        assert row.scalar_one() == "stale"
        mock_metering.settle.assert_not_called()

    async def test_tier2_settles_at_estimated_cost_with_records(
        self, db_session: AsyncSession
    ) -> None:
        """Tier 1 fails (no pricing), tier 2 settles at estimated_cost with records."""
        user = await _seed_user(db_session)
        stale_time = datetime.now(UTC) - timedelta(seconds=400)
        reservation = await _seed_reservation(db_session, created_at=stale_time)
        await _add_response_metadata(db_session, reservation)

        # Real MeteringService with no pricing data → tier 1 fails
        admin_config = AdminConfigService(db_session)
        metering_service = MeteringService(db_session, admin_config)

        released = await sweep_stale_reservations(
            db_session,
            ttl_seconds=_DEFAULT_TTL,
            metering_service=metering_service,
        )

        assert released == 1

        # Verify settled at estimated cost
        row = await db_session.execute(
            text(
                "SELECT status, actual_cost_usd FROM usage_reservations WHERE id = :id"
            ),
            {"id": reservation.id},
        )
        result = row.one()
        assert result.status == "settled"
        assert result.actual_cost_usd == _DEFAULT_ESTIMATED

        # Verify LLMUsageRecord created with correct data
        usage_row = await db_session.execute(
            text(
                "SELECT provider, model, task_type, input_tokens, output_tokens, "
                "raw_cost_usd, billed_cost_usd, margin_multiplier "
                "FROM llm_usage_records WHERE user_id = :uid"
            ),
            {"uid": user.id},
        )
        usage = usage_row.one()
        assert usage.provider == "claude"
        assert usage.model == "claude-sonnet-4-20250514"
        assert usage.task_type == "extraction"
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.billed_cost_usd == _DEFAULT_ESTIMATED
        assert usage.margin_multiplier == Decimal("1.00")

        # Verify CreditTransaction debit
        txn_row = await db_session.execute(
            text(
                "SELECT amount_usd, transaction_type, description "
                "FROM credit_transactions "
                "WHERE user_id = :uid AND transaction_type = 'usage_debit'"
            ),
            {"uid": user.id},
        )
        txn = txn_row.one()
        assert txn.amount_usd == -_DEFAULT_ESTIMATED
        assert "sweep-estimated" in txn.description

        # Verify user balance decremented
        user_row = await db_session.execute(
            text("SELECT balance_usd, held_balance_usd FROM users WHERE id = :uid"),
            {"uid": user.id},
        )
        user_data = user_row.one()
        assert user_data.balance_usd == _USER_BALANCE - _DEFAULT_ESTIMATED
        assert user_data.held_balance_usd == _USER_HELD - _DEFAULT_ESTIMATED

    async def test_both_tiers_fail_releases_as_stale(
        self, db_session: AsyncSession
    ) -> None:
        """Both tiers fail → stale release (last resort)."""
        await _seed_user(db_session)
        stale_time = datetime.now(UTC) - timedelta(seconds=400)
        reservation = await _seed_reservation(db_session, created_at=stale_time)
        await _add_response_metadata(db_session, reservation)

        # Mock _attempt_settlement_retry to return False (both tiers failed)
        mock_metering = AsyncMock(spec=MeteringService)
        with patch(
            _PATCH_RETRY,
            new_callable=AsyncMock,
            return_value=False,
        ):
            released = await sweep_stale_reservations(
                db_session,
                ttl_seconds=_DEFAULT_TTL,
                metering_service=mock_metering,
            )

        assert released == 1
        row = await db_session.execute(
            text("SELECT status FROM usage_reservations WHERE id = :id"),
            {"id": reservation.id},
        )
        assert row.scalar_one() == "stale"

    async def test_no_metering_service_skips_retry(
        self, db_session: AsyncSession
    ) -> None:
        """metering_service=None → stale release even with metadata (backward compat)."""
        await _seed_user(db_session)
        stale_time = datetime.now(UTC) - timedelta(seconds=400)
        reservation = await _seed_reservation(db_session, created_at=stale_time)
        await _add_response_metadata(db_session, reservation)

        released = await sweep_stale_reservations(
            db_session,
            ttl_seconds=_DEFAULT_TTL,
        )

        assert released == 1
        row = await db_session.execute(
            text("SELECT status FROM usage_reservations WHERE id = :id"),
            {"id": reservation.id},
        )
        assert row.scalar_one() == "stale"
