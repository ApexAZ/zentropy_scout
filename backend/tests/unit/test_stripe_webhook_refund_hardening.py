"""Tests for charge.refunded handler hardening — REQ-030 §7.2.

Savepoint atomicity (F-03), refund cap (F-04), null payment_intent guard (F-05).
Split from test_stripe_webhook_refund.py to stay under the 300-line limit.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import FundingPack
from app.models.stripe import StripePurchase
from app.models.usage import CreditTransaction
from app.models.user import User
from app.services.billing.stripe_webhook_service import handle_charge_refunded

# ===============================================================================
# Constants & Helpers (duplicated from test_stripe_webhook_refund.py)
# ===============================================================================

_TEST_EVENT_ID = "evt_refund_abc123"
_TEST_CHARGE_ID = "ch_test_abc123"
_TEST_CUSTOMER_ID = "cus_test_abc123"
_TEST_PAYMENT_INTENT = "pi_test_abc123"
_TEST_EMAIL = "test@example.com"
_TEST_AMOUNT_CENTS = 50000  # $500.00 original charge
_INITIAL_BALANCE = Decimal("500")


def _make_refund_event(
    *,
    event_id: str = _TEST_EVENT_ID,
    charge_id: str = _TEST_CHARGE_ID,
    customer_id: str = _TEST_CUSTOMER_ID,
    payment_intent: str | None = _TEST_PAYMENT_INTENT,
    amount: int = _TEST_AMOUNT_CENTS,
    amount_refunded: int = _TEST_AMOUNT_CENTS,
    refunded: bool = True,
) -> MagicMock:
    """Build a mock Stripe charge.refunded event."""
    event = MagicMock()
    event.id = event_id
    event.data.object = {
        "id": charge_id,
        "amount": amount,
        "amount_refunded": amount_refunded,
        "refunded": refunded,
        "payment_intent": payment_intent,
        "customer": customer_id,
    }
    return event


async def _setup_completed_purchase(
    db_session: AsyncSession,
    *,
    amount_cents: int = _TEST_AMOUNT_CENTS,
    grant_cents: int = _TEST_AMOUNT_CENTS,
    initial_balance: Decimal = _INITIAL_BALANCE,
    refund_amount_cents: int = 0,
) -> tuple[User, StripePurchase]:
    """Create user with balance and a completed purchase."""
    user = User(email=_TEST_EMAIL, stripe_customer_id=_TEST_CUSTOMER_ID)
    db_session.add(user)
    await db_session.flush()

    await db_session.execute(
        text("UPDATE users SET balance_usd = :balance WHERE id = :user_id"),
        {"balance": initial_balance, "user_id": user.id},
    )

    pack = FundingPack(
        id=uuid.uuid4(),
        name="Starter",
        price_cents=amount_cents,
        grant_cents=grant_cents,
        stripe_price_id="price_test_starter",
        display_order=1,
        is_active=True,
        description="Starter pack",
    )
    db_session.add(pack)
    await db_session.flush()

    purchase = StripePurchase(
        user_id=user.id,
        pack_id=pack.id,
        stripe_session_id="cs_test_xyz789",
        stripe_customer_id=_TEST_CUSTOMER_ID,
        stripe_payment_intent=_TEST_PAYMENT_INTENT,
        amount_cents=amount_cents,
        grant_cents=grant_cents,
        status="completed",
        refund_amount_cents=refund_amount_cents,
    )
    db_session.add(purchase)
    await db_session.flush()

    return user, purchase


async def _find_txn_by_event(
    db_session: AsyncSession,
    event_id: str = _TEST_EVENT_ID,
) -> CreditTransaction | None:
    """Query CreditTransaction by stripe_event_id."""
    stmt = select(CreditTransaction).where(
        CreditTransaction.stripe_event_id == event_id
    )
    result = await db_session.execute(stmt)
    return result.scalar_one_or_none()


# ===============================================================================
# handle_charge_refunded — savepoint atomicity (REQ-030 §7.2a / F-03)
# ===============================================================================


class TestRefundSavepointAtomicity:
    """REQ-030 §7.2a: All refund operations wrapped in begin_nested()."""

    async def test_savepoint_rollback_no_orphaned_txn(
        self, db_session: AsyncSession
    ) -> None:
        """If mark_refunded fails, credit txn and balance debit roll back.

        Without savepoint, CreditRepository.create + atomic_refund_debit
        would persist even when mark_refunded raises — leaving an orphaned
        credit transaction and incorrect balance.
        """
        user, _purchase = await _setup_completed_purchase(db_session)
        event = _make_refund_event()

        with patch(
            "app.services.billing.stripe_webhook_service.StripePurchaseRepository.mark_refunded",
            side_effect=RuntimeError("simulated DB failure"),
        ):
            # Handler catches all exceptions (never-raise contract)
            await handle_charge_refunded(db_session, event=event)

        # No credit transaction should exist — savepoint rolled back
        txn = await _find_txn_by_event(db_session)
        assert txn is None

        # Balance should be unchanged
        await db_session.refresh(user)
        assert user.balance_usd == _INITIAL_BALANCE


# ===============================================================================
# handle_charge_refunded — refund cap (REQ-030 §7.2b / F-04)
# ===============================================================================


class TestRefundCap:
    """REQ-030 §7.2b: Cap total_refunded_cents at purchase.amount_cents."""

    async def test_refund_capped_at_purchase_amount(
        self, db_session: AsyncSession
    ) -> None:
        """Stripe sends amount_refunded > amount_cents — cap prevents over-debit.

        purchase.amount_cents=500 ($5.00), charge.amount_refunded=99999 ($999.99).
        Without cap: debit $999.99. With cap: debit $5.00.
        """
        user, _purchase = await _setup_completed_purchase(
            db_session,
            amount_cents=500,
            grant_cents=500,
            initial_balance=_INITIAL_BALANCE,
        )
        event = _make_refund_event(
            amount=500,
            amount_refunded=99999,  # Corrupted/unexpected: exceeds original
            refunded=True,
        )

        await handle_charge_refunded(db_session, event=event)

        txn = await _find_txn_by_event(db_session)
        assert txn is not None
        # Capped at $5.00 (500 cents), not $999.99
        assert txn.amount_usd == Decimal("-5")

        await db_session.refresh(user)
        assert user.balance_usd == Decimal("495")

    async def test_normal_refund_not_affected_by_cap(
        self, db_session: AsyncSession
    ) -> None:
        """Normal refund (amount_refunded <= amount_cents) is unchanged."""
        user, _purchase = await _setup_completed_purchase(
            db_session,
            amount_cents=500,
            grant_cents=500,
            initial_balance=_INITIAL_BALANCE,
        )
        event = _make_refund_event(
            amount=500,
            amount_refunded=250,  # Normal partial refund
            refunded=False,
        )

        await handle_charge_refunded(db_session, event=event)

        txn = await _find_txn_by_event(db_session)
        assert txn is not None
        assert txn.amount_usd == Decimal("-2.50")


# ===============================================================================
# handle_charge_refunded — null payment_intent guard (REQ-030 §7.2c / F-05)
# ===============================================================================


class TestNullPaymentIntentGuard:
    """REQ-030 §7.2c: Skip processing when payment_intent is null."""

    async def test_null_payment_intent_skips_processing(
        self, db_session: AsyncSession
    ) -> None:
        """Null payment_intent returns early — no DB changes."""
        user, _purchase = await _setup_completed_purchase(db_session)
        event = _make_refund_event(payment_intent=None)

        await handle_charge_refunded(db_session, event=event)

        txn = await _find_txn_by_event(db_session)
        assert txn is None
        await db_session.refresh(user)
        assert user.balance_usd == _INITIAL_BALANCE

    async def test_null_payment_intent_logs_error(
        self, db_session: AsyncSession
    ) -> None:
        """Null payment_intent logs an error with event ID."""
        _user, _purchase = await _setup_completed_purchase(db_session)
        event = _make_refund_event(payment_intent=None)

        with patch("app.services.billing.stripe_webhook_service.logger") as mock_logger:
            await handle_charge_refunded(db_session, event=event)

        mock_logger.error.assert_called_once()
        log_args = mock_logger.error.call_args
        assert "null payment_intent" in log_args[0][0]
        assert log_args[0][1] == _TEST_EVENT_ID
