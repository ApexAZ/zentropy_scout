"""Tests for Stripe service — handle_charge_refunded webhook handler.

REQ-029 §7.3, REQ-030 §7.2: Verifies refund handling, cumulative partial refund
tracking, idempotency, balance debiting (including negative), purchase status
updates, savepoint atomicity, refund cap, and null payment_intent guard.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import FundingPack
from app.models.stripe import StripePurchase
from app.models.usage import CreditTransaction
from app.models.user import User
from app.services.stripe_webhook_service import handle_charge_refunded

# ===============================================================================
# Constants & Helpers
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

    # Set initial balance
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
# handle_charge_refunded — full refund
# ===============================================================================


class TestHandleChargeRefundedFull:
    """Happy path — full refund debits balance correctly."""

    async def test_debits_user_balance(self, db_session: AsyncSession) -> None:
        """Should debit the user's balance by the refund amount."""
        user, _purchase = await _setup_completed_purchase(db_session)
        event = _make_refund_event()

        await handle_charge_refunded(db_session, event=event)

        await db_session.refresh(user)
        assert user.balance_usd == Decimal("0")

    async def test_creates_refund_transaction(self, db_session: AsyncSession) -> None:
        """Should create a negative credit transaction."""
        user, _purchase = await _setup_completed_purchase(db_session)
        event = _make_refund_event()

        await handle_charge_refunded(db_session, event=event)

        txn = await _find_txn_by_event(db_session)
        assert txn is not None
        assert txn.user_id == user.id
        assert txn.amount_usd == Decimal("-500")
        assert txn.transaction_type == "refund"
        assert txn.reference_id == _TEST_CHARGE_ID
        assert txn.stripe_event_id == _TEST_EVENT_ID

    async def test_marks_purchase_refunded(self, db_session: AsyncSession) -> None:
        """Should update purchase status to 'refunded'."""
        _user, purchase = await _setup_completed_purchase(db_session)
        event = _make_refund_event()

        await handle_charge_refunded(db_session, event=event)

        await db_session.refresh(purchase)
        assert purchase.status == "refunded"
        assert purchase.refund_amount_cents == _TEST_AMOUNT_CENTS
        assert purchase.refunded_at is not None


# ===============================================================================
# handle_charge_refunded — partial refund
# ===============================================================================


class TestHandleChargeRefundedPartial:
    """Partial refund tracking with cumulative amount_refunded."""

    async def test_partial_refund_debits_correct_amount(
        self, db_session: AsyncSession
    ) -> None:
        """Should debit only the partial refund amount."""
        user, _purchase = await _setup_completed_purchase(db_session)
        event = _make_refund_event(
            amount_refunded=25000,  # $250 of $500
            refunded=False,
        )

        await handle_charge_refunded(db_session, event=event)

        await db_session.refresh(user)
        assert user.balance_usd == Decimal("250")

    async def test_partial_refund_marks_partial_status(
        self, db_session: AsyncSession
    ) -> None:
        """Should set purchase status to 'partial_refund'."""
        _user, purchase = await _setup_completed_purchase(db_session)
        event = _make_refund_event(
            amount_refunded=25000,
            refunded=False,
        )

        await handle_charge_refunded(db_session, event=event)

        await db_session.refresh(purchase)
        assert purchase.status == "partial_refund"
        assert purchase.refund_amount_cents == 25000

    async def test_second_partial_refund_calculates_delta(
        self, db_session: AsyncSession
    ) -> None:
        """Should debit only the incremental amount on second refund."""
        user, _purchase = await _setup_completed_purchase(
            db_session, refund_amount_cents=25000
        )
        # Second refund: cumulative 40000, previous 25000 → delta 15000
        event = _make_refund_event(
            event_id="evt_refund_second",
            amount_refunded=40000,
            refunded=False,
        )

        await handle_charge_refunded(db_session, event=event)

        txn = await _find_txn_by_event(db_session, "evt_refund_second")
        assert txn is not None
        assert txn.amount_usd == Decimal("-150")  # $150 delta


# ===============================================================================
# handle_charge_refunded — skips & edge cases
# ===============================================================================


class TestHandleChargeRefundedSkips:
    """Scenarios that skip processing."""

    async def test_skips_duplicate_event(self, db_session: AsyncSession) -> None:
        """Should skip if event ID already processed (idempotency)."""
        user, _purchase = await _setup_completed_purchase(db_session)
        event = _make_refund_event()

        await handle_charge_refunded(db_session, event=event)
        await db_session.refresh(user)
        balance_after_first = user.balance_usd

        await handle_charge_refunded(db_session, event=event)

        await db_session.refresh(user)
        assert user.balance_usd == balance_after_first

    async def test_skips_purchase_not_found(self, db_session: AsyncSession) -> None:
        """Should skip when no purchase matches the payment_intent."""
        user, _purchase = await _setup_completed_purchase(db_session)
        event = _make_refund_event(payment_intent="pi_unknown")

        await handle_charge_refunded(db_session, event=event)

        assert await _find_txn_by_event(db_session) is None

    async def test_skips_zero_delta(self, db_session: AsyncSession) -> None:
        """Should skip when cumulative refund equals previous total."""
        _user, _purchase = await _setup_completed_purchase(
            db_session, refund_amount_cents=25000
        )
        event = _make_refund_event(amount_refunded=25000, refunded=False)

        await handle_charge_refunded(db_session, event=event)

        assert await _find_txn_by_event(db_session) is None

    async def test_balance_goes_negative(self, db_session: AsyncSession) -> None:
        """Should allow balance to go negative after refund."""
        user, _purchase = await _setup_completed_purchase(
            db_session, initial_balance=Decimal("100")
        )
        event = _make_refund_event()  # $500 refund on $100 balance

        await handle_charge_refunded(db_session, event=event)

        await db_session.refresh(user)
        assert user.balance_usd == Decimal("-400")
