"""Tests for StripePurchase ORM model.

REQ-029 §4.3: Verifies StripePurchase model fields, defaults, constraints,
foreign key behavior, and lifecycle transitions.

User.stripe_customer_id and CreditTransaction.stripe_event_id tests live
in test_metering_models.py alongside related model tests.
"""

import uuid
from datetime import UTC

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import FundingPack
from app.models.stripe import StripePurchase
from app.models.user import User

# Fixed test UUIDs
_MISSING_USER_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_funding_pack(db: AsyncSession) -> FundingPack:
    """Create a FundingPack for FK references in StripePurchase tests."""
    pack = FundingPack(
        name="Test Pack",
        price_cents=500,
        grant_cents=50000,
        stripe_price_id="price_test_123",
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
    """Create StripePurchase with sensible defaults for testing."""
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
# StripePurchase model (REQ-029 §4.3)
# ---------------------------------------------------------------------------


class TestStripePurchase:
    """REQ-029 §4.3: StripePurchase ORM model."""

    @pytest.mark.asyncio
    async def test_create_with_required_fields(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """StripePurchase inserts with all required fields."""
        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(test_user.id, pack.id)
        db_session.add(purchase)
        await db_session.flush()
        await db_session.refresh(purchase)

        assert purchase.id is not None
        assert purchase.user_id == test_user.id
        assert purchase.pack_id == pack.id
        assert purchase.stripe_customer_id == "cus_test_abc123"
        assert purchase.amount_cents == 500
        assert purchase.grant_cents == 50000
        assert purchase.created_at is not None
        assert purchase.updated_at is not None

    @pytest.mark.asyncio
    async def test_default_status_pending(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """New purchases default to 'pending' status."""
        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(test_user.id, pack.id)
        db_session.add(purchase)
        await db_session.flush()
        await db_session.refresh(purchase)

        assert purchase.status == "pending"

    @pytest.mark.asyncio
    async def test_default_currency_usd(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Currency defaults to 'usd'."""
        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(test_user.id, pack.id)
        db_session.add(purchase)
        await db_session.flush()
        await db_session.refresh(purchase)

        assert purchase.currency == "usd"

    @pytest.mark.asyncio
    async def test_default_refund_amount_zero(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """refund_amount_cents defaults to 0."""
        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(test_user.id, pack.id)
        db_session.add(purchase)
        await db_session.flush()
        await db_session.refresh(purchase)

        assert purchase.refund_amount_cents == 0

    @pytest.mark.asyncio
    async def test_nullable_fields_default_to_none(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Optional fields default to None."""
        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(test_user.id, pack.id)
        db_session.add(purchase)
        await db_session.flush()
        await db_session.refresh(purchase)

        assert purchase.stripe_payment_intent is None
        assert purchase.completed_at is None
        assert purchase.refunded_at is None

    @pytest.mark.asyncio
    async def test_stripe_session_id_unique(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """stripe_session_id UNIQUE constraint prevents duplicates."""
        pack = await _create_funding_pack(db_session)
        p1 = _make_purchase(test_user.id, pack.id, stripe_session_id="cs_test_dup")
        p2 = _make_purchase(test_user.id, pack.id, stripe_session_id="cs_test_dup")
        db_session.add(p1)
        await db_session.flush()

        db_session.add(p2)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_invalid_status(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint rejects invalid status values."""
        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(test_user.id, pack.id, status="invalid")
        db_session.add(purchase)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_negative_amount_cents(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint rejects negative amount_cents."""
        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(test_user.id, pack.id, amount_cents=-100)
        db_session.add(purchase)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_zero_grant_cents(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint rejects zero grant_cents."""
        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(test_user.id, pack.id, grant_cents=0)
        db_session.add(purchase)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_rejects_negative_refund_amount(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """CHECK constraint rejects negative refund_amount_cents."""
        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(test_user.id, pack.id, refund_amount_cents=-1)
        db_session.add(purchase)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_fk_rejects_invalid_user_id(self, db_session: AsyncSession) -> None:
        """FK constraint rejects non-existent user_id."""
        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(_MISSING_USER_ID, pack.id)
        db_session.add(purchase)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_fk_rejects_invalid_pack_id(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """FK constraint rejects non-existent pack_id."""
        missing_pack_id = uuid.UUID("88888888-8888-8888-8888-888888888888")
        purchase = _make_purchase(test_user.id, missing_pack_id)
        db_session.add(purchase)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_fk_cascade_on_user_delete(self, db_session: AsyncSession) -> None:
        """Purchases are deleted when parent user is deleted."""
        user = User(email="cascade-test-stripe@example.com")
        db_session.add(user)
        await db_session.flush()

        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(user.id, pack.id)
        db_session.add(purchase)
        await db_session.flush()
        purchase_id = purchase.id

        await db_session.delete(user)
        await db_session.flush()

        result = await db_session.execute(
            text("SELECT id FROM stripe_purchases WHERE id = :id"),
            {"id": purchase_id},
        )
        assert result.fetchone() is None

    @pytest.mark.asyncio
    async def test_fk_restrict_on_pack_delete(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """RESTRICT prevents deleting a FundingPack with purchase history."""
        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(test_user.id, pack.id)
        db_session.add(purchase)
        await db_session.flush()

        await db_session.delete(pack)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_completed_purchase_lifecycle(
        self, db_session: AsyncSession, test_user: User
    ) -> None:
        """Purchase can transition from pending to completed with payment intent."""
        from datetime import datetime

        pack = await _create_funding_pack(db_session)
        purchase = _make_purchase(test_user.id, pack.id)
        db_session.add(purchase)
        await db_session.flush()

        # Simulate webhook completion
        purchase.status = "completed"
        purchase.stripe_payment_intent = "pi_test_abc123"
        purchase.completed_at = datetime.now(UTC)
        await db_session.flush()
        await db_session.refresh(purchase)

        assert purchase.status == "completed"
        assert purchase.stripe_payment_intent == "pi_test_abc123"
        assert purchase.completed_at is not None
