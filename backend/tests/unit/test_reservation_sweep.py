"""Tests for stale reservation sweep and worker lifecycle.

REQ-030 §11.1: Background sweep releases reservations that exceeded TTL.
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
from app.services.reservation_sweep import (
    ReservationSweepWorker,
    sweep_stale_reservations,
)

_PATCH_SETTINGS = "app.services.reservation_sweep.settings"
_PATCH_SWEEP = "app.services.reservation_sweep.sweep_stale_reservations"

_DEFAULT_TTL = 300

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DEFAULT_ESTIMATED = Decimal("0.050000")
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
            patch(_PATCH_SETTINGS) as mock_settings,
        ):
            mock_settings.reservation_ttl_seconds = _DEFAULT_TTL
            released = await worker.run_once()

        assert released == 3
        mock_sweep.assert_called_once_with(mock_session, ttl_seconds=_DEFAULT_TTL)
        mock_session.commit.assert_awaited_once()

    async def test_run_once_uses_configured_ttl(
        self, mock_session_factory: MagicMock
    ) -> None:
        """run_once() passes the configured TTL from settings."""
        mock_session = mock_session_factory.return_value
        worker = ReservationSweepWorker(mock_session_factory, interval_seconds=60)

        with (
            patch(
                _PATCH_SWEEP,
                new_callable=AsyncMock,
                return_value=0,
            ) as mock_sweep,
            patch(_PATCH_SETTINGS) as mock_settings,
        ):
            mock_settings.reservation_ttl_seconds = 600
            await worker.run_once()

        mock_sweep.assert_called_once_with(mock_session, ttl_seconds=600)

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
