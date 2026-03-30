"""Tests for UsageReservation ORM model and billing hardening model changes.

REQ-030 §4.1: held_balance_usd on User.
REQ-030 §4.2: UsageReservation table with constraints and indexes.
REQ-030 §4.3: grant_cents type alignment (BigInteger -> Integer).
REQ-030 §7.3: 'expired' status on StripePurchase.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import FundingPack
from app.models.stripe import StripePurchase
from app.models.usage_reservation import UsageReservation
from app.models.user import User

_MISSING_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
_ZERO_USD = Decimal("0.000000")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_reservation(user_id: uuid.UUID, **overrides: object) -> UsageReservation:
    """Create UsageReservation with sensible defaults for testing."""
    defaults: dict[str, object] = {
        "user_id": user_id,
        "estimated_cost_usd": Decimal("0.005000"),
        "task_type": "extraction",
    }
    defaults.update(overrides)
    return UsageReservation(**defaults)


async def _create_funding_pack(db: AsyncSession) -> FundingPack:
    """Create a FundingPack for FK references."""
    pack = FundingPack(
        name="Test Pack",
        price_cents=500,
        grant_cents=50000,
        stripe_price_id="price_test_res_123",
        display_order=1,
        is_active=True,
        description="A test funding pack",
    )
    db.add(pack)
    await db.flush()
    return pack


def _make_purchase(
    user_id: uuid.UUID, pack_id: uuid.UUID, **overrides: object
) -> StripePurchase:
    """Create StripePurchase with sensible defaults."""
    defaults: dict[str, object] = {
        "user_id": user_id,
        "pack_id": pack_id,
        "stripe_session_id": f"cs_test_{uuid.uuid4().hex[:12]}",
        "stripe_customer_id": "cus_test_abc123",
        "amount_cents": 500,
        "grant_cents": 50000,
    }
    defaults.update(overrides)
    return StripePurchase(**defaults)


# ---------------------------------------------------------------------------
# UsageReservation model (REQ-030 §4.2)
# ---------------------------------------------------------------------------


class TestUsageReservation:
    """REQ-030 §4.2: UsageReservation ORM model."""

    @pytest.mark.asyncio
    async def test_create_with_required_fields(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """UsageReservation inserts with all required fields."""
        reservation = _make_reservation(test_user.id)
        db_session.add(reservation)
        await db_session.flush()
        await db_session.refresh(reservation)

        assert reservation.id is not None
        assert reservation.user_id == test_user.id
        assert reservation.estimated_cost_usd == Decimal("0.005000")
        assert reservation.task_type == "extraction"
        assert reservation.created_at is not None

    @pytest.mark.asyncio
    async def test_default_status_held(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """New reservations default to 'held' status."""
        reservation = _make_reservation(test_user.id)
        db_session.add(reservation)
        await db_session.flush()
        await db_session.refresh(reservation)

        assert reservation.status == "held"

    @pytest.mark.asyncio
    async def test_nullable_fields_default_to_none(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Optional fields default to None."""
        reservation = _make_reservation(test_user.id)
        db_session.add(reservation)
        await db_session.flush()
        await db_session.refresh(reservation)

        assert reservation.actual_cost_usd is None
        assert reservation.provider is None
        assert reservation.model is None
        assert reservation.max_tokens is None
        assert reservation.settled_at is None

    @pytest.mark.asyncio
    async def test_rejects_invalid_status(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint rejects invalid status values."""
        reservation = _make_reservation(test_user.id, status="invalid")
        db_session.add(reservation)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_accepts_all_valid_statuses(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint accepts held, settled, released, stale."""
        statuses = ("held", "settled", "released", "stale")
        reservations = [_make_reservation(test_user.id, status=s) for s in statuses]
        db_session.add_all(reservations)
        await db_session.flush()
        for reservation, expected in zip(reservations, statuses, strict=True):
            await db_session.refresh(reservation)
            assert reservation.status == expected

    @pytest.mark.asyncio
    async def test_rejects_zero_estimated_cost(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint rejects zero estimated_cost_usd."""
        reservation = _make_reservation(test_user.id, estimated_cost_usd=_ZERO_USD)
        db_session.add(reservation)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_negative_estimated_cost(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint rejects negative estimated_cost_usd."""
        reservation = _make_reservation(
            test_user.id, estimated_cost_usd=Decimal("-0.001000")
        )
        db_session.add(reservation)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_negative_actual_cost(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint rejects negative actual_cost_usd."""
        reservation = _make_reservation(
            test_user.id, actual_cost_usd=Decimal("-0.001000")
        )
        db_session.add(reservation)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_accepts_zero_actual_cost(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Zero actual_cost_usd is valid (e.g., free-tier call)."""
        reservation = _make_reservation(test_user.id, actual_cost_usd=_ZERO_USD)
        db_session.add(reservation)
        await db_session.flush()
        await db_session.refresh(reservation)

        assert reservation.actual_cost_usd == _ZERO_USD

    @pytest.mark.asyncio
    async def test_fk_rejects_invalid_user_id(self, db_session: AsyncSession) -> None:
        """FK constraint rejects non-existent user_id."""
        reservation = _make_reservation(_MISSING_USER_ID)
        db_session.add(reservation)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_fk_cascade_on_user_delete(self, db_session: AsyncSession) -> None:
        """Reservations are deleted when parent user is deleted."""
        user = User(email="cascade-test-reservation@example.com")
        db_session.add(user)
        await db_session.flush()

        reservation = _make_reservation(user.id)
        db_session.add(reservation)
        await db_session.flush()
        reservation_id = reservation.id

        await db_session.delete(user)
        await db_session.flush()

        result = await db_session.execute(
            text("SELECT id FROM usage_reservations WHERE id = :id"),
            {"id": reservation_id},
        )
        assert result.fetchone() is None

    @pytest.mark.asyncio
    async def test_settle_transition(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Reservation can transition from held to settled with actual cost."""
        from datetime import UTC, datetime

        reservation = _make_reservation(test_user.id)
        db_session.add(reservation)
        await db_session.flush()

        reservation.status = "settled"
        reservation.actual_cost_usd = Decimal("0.003200")
        reservation.provider = "claude"
        reservation.model = "claude-sonnet-4-20250514"
        reservation.max_tokens = 4096
        reservation.settled_at = datetime.now(UTC)
        await db_session.flush()
        await db_session.refresh(reservation)

        assert reservation.status == "settled"
        assert reservation.actual_cost_usd == Decimal("0.003200")
        assert reservation.provider == "claude"
        assert reservation.max_tokens == 4096
        assert reservation.settled_at is not None


# ---------------------------------------------------------------------------
# User.held_balance_usd (REQ-030 §4.1)
# ---------------------------------------------------------------------------


class TestUserHeldBalance:
    """REQ-030 §4.1: held_balance_usd on User model."""

    @pytest.mark.asyncio
    async def test_held_balance_defaults_to_zero(
        self, db_session: AsyncSession
    ) -> None:
        """held_balance_usd defaults to 0.000000."""
        user = User(email="held-balance-default@example.com")
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        assert user.held_balance_usd == _ZERO_USD

    @pytest.mark.asyncio
    async def test_held_balance_rejects_negative(
        self, db_session: AsyncSession
    ) -> None:
        """CHECK constraint rejects negative held_balance_usd."""
        user = User(
            email="held-balance-negative@example.com",
            held_balance_usd=Decimal("-0.001000"),
        )
        db_session.add(user)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_held_balance_accepts_positive(
        self, db_session: AsyncSession
    ) -> None:
        """held_balance_usd accepts positive values."""
        user = User(
            email="held-balance-positive@example.com",
            held_balance_usd=Decimal("1.500000"),
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        assert user.held_balance_usd == Decimal("1.500000")


# ---------------------------------------------------------------------------
# StripePurchase 'expired' status (REQ-030 §7.3)
# ---------------------------------------------------------------------------


class TestStripePurchaseExpiredStatus:
    """REQ-030 §7.3: 'expired' status on StripePurchase."""

    @pytest.mark.asyncio
    async def test_accepts_expired_status(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint accepts 'expired' as a valid status."""
        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(test_user.id, pack.id, status="expired")
        db_session.add(purchase)
        await db_session.flush()
        await db_session.refresh(purchase)

        assert purchase.status == "expired"

    @pytest.mark.asyncio
    async def test_pending_to_expired_transition(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Purchase can transition from pending to expired."""
        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(test_user.id, pack.id)
        db_session.add(purchase)
        await db_session.flush()
        assert purchase.status == "pending"

        purchase.status = "expired"
        await db_session.flush()
        await db_session.refresh(purchase)

        assert purchase.status == "expired"
