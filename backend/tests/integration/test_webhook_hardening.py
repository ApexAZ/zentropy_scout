"""Integration tests for webhook & Stripe service hardening.

REQ-030 §15.2: Refund savepoint rollback (§7.2a), expired checkout transition
(§7.3), and customer creation race condition (§8.1). Uses real PostgreSQL
database with savepoint isolation.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import FundingPack
from app.models.stripe import StripePurchase
from app.models.usage import CreditTransaction
from app.models.user import User
from app.services.billing.stripe_service import (
    StripeServiceError,
    get_or_create_customer,
)
from app.services.billing.stripe_webhook_service import (
    handle_charge_refunded,
    handle_checkout_expired,
)

_CUSTOMER_ID = "cus_int_wh_001"
_CONFLICTING_CUSTOMER_ID = "cus_taken"
_PAYMENT_INTENT = "pi_int_wh_001"
_SESSION_ID = "cs_int_wh_001"
_INITIAL_BALANCE = Decimal("500.000000")
_EXPIRED_BALANCE = Decimal("100.000000")
_AMOUNT_CENTS = 50000  # $500.00
_ZERO = Decimal("0.000000")


def _make_refund_event(
    *,
    event_id: str = "evt_refund_int_001",
    charge_id: str = "ch_int_001",
    payment_intent: str | None = _PAYMENT_INTENT,
    amount_refunded: int = _AMOUNT_CENTS,
    refunded: bool = True,
) -> MagicMock:
    """Build a mock Stripe charge.refunded event."""
    event = MagicMock()
    event.id = event_id
    event.data.object = {
        "id": charge_id,
        "amount": _AMOUNT_CENTS,
        "amount_refunded": amount_refunded,
        "refunded": refunded,
        "payment_intent": payment_intent,
        "customer": _CUSTOMER_ID,
    }
    return event


def _make_expired_event(
    *,
    event_id: str = "evt_expired_int_001",
    session_id: str = _SESSION_ID,
) -> MagicMock:
    """Build a mock Stripe checkout.session.expired event."""
    event = MagicMock()
    event.id = event_id
    event.data.object = {"id": session_id}
    return event


async def _seed_user_with_balance(
    db: AsyncSession,
    *,
    email: str = "webhook-int@example.com",
    balance: Decimal = _INITIAL_BALANCE,
) -> User:
    """Insert a test user with known balance and Stripe customer ID."""
    user = User(email=email, stripe_customer_id=_CUSTOMER_ID)
    db.add(user)
    await db.flush()
    await db.execute(
        text("UPDATE users SET balance_usd = :balance WHERE id = :uid"),
        {"balance": balance, "uid": user.id},
    )
    await db.refresh(user)
    return user


async def _seed_purchase(
    db: AsyncSession,
    user: User,
    *,
    status: str = "pending",
    session_id: str = _SESSION_ID,
) -> StripePurchase:
    """Insert a funding pack and purchase with the given status."""
    pack = FundingPack(
        id=uuid.uuid4(),
        name="Integration Test Pack",
        price_cents=_AMOUNT_CENTS,
        grant_cents=_AMOUNT_CENTS,
        stripe_price_id="price_int_wh_test",
        display_order=1,
        is_active=True,
        description="Integration test pack",
    )
    db.add(pack)
    await db.flush()

    purchase = StripePurchase(
        user_id=user.id,
        pack_id=pack.id,
        stripe_session_id=session_id,
        stripe_customer_id=_CUSTOMER_ID,
        stripe_payment_intent=_PAYMENT_INTENT if status == "completed" else None,
        amount_cents=_AMOUNT_CENTS,
        grant_cents=_AMOUNT_CENTS,
        status=status,
    )
    db.add(purchase)
    await db.flush()
    return purchase


# ===========================================================================
# Refund Savepoint Rollback (REQ-030 §7.2a / F-03)
# ===========================================================================


@pytest.mark.asyncio
class TestRefundSavepointRollback:
    """REQ-030 §7.2a, §15.2: Savepoint isolates failed refund operations."""

    async def test_failed_refund_then_successful_retry(
        self, db_session: AsyncSession
    ) -> None:
        """Session survives savepoint rollback and processes subsequent refund.

        First attempt: mark_refunded fails mid-savepoint → all three operations
        (credit create, balance debit, purchase update) roll back. Second
        attempt: succeeds normally. Proves PostgreSQL savepoint properly
        isolated the failure without corrupting the session.
        """
        user = await _seed_user_with_balance(db_session)
        purchase = await _seed_purchase(db_session, user, status="completed")

        # First attempt: simulate failure in mark_refunded
        event_fail = _make_refund_event(event_id="evt_fail_int")
        with patch(
            "app.services.billing.stripe_webhook_service"
            ".StripePurchaseRepository.mark_refunded",
            side_effect=RuntimeError("simulated DB failure"),
        ):
            await handle_charge_refunded(db_session, event=event_fail)

        # No credit transaction from failed attempt
        fail_result = await db_session.execute(
            select(CreditTransaction).where(
                CreditTransaction.stripe_event_id == "evt_fail_int"
            )
        )
        assert fail_result.scalar_one_or_none() is None

        # Balance unchanged after failed attempt
        await db_session.refresh(user)
        assert user.balance_usd == _INITIAL_BALANCE

        # Second attempt: succeeds (different event ID for idempotency)
        event_ok = _make_refund_event(event_id="evt_ok_int")
        await handle_charge_refunded(db_session, event=event_ok)
        await db_session.flush()

        # Credit transaction created
        ok_result = await db_session.execute(
            select(CreditTransaction).where(
                CreditTransaction.stripe_event_id == "evt_ok_int"
            )
        )
        txn = ok_result.scalar_one()
        assert txn.amount_usd == -_INITIAL_BALANCE

        # Balance debited to zero
        await db_session.refresh(user)
        assert user.balance_usd == _ZERO

        # Purchase marked refunded
        await db_session.refresh(purchase)
        assert purchase.status == "refunded"


# ===========================================================================
# Expired Checkout Transition (REQ-030 §7.3 / F-07)
# ===========================================================================


@pytest.mark.asyncio
class TestExpiredCheckoutTransition:
    """REQ-030 §7.3, §15.2: Expired checkout transitions pending→expired."""

    async def test_pending_purchase_marked_expired_no_balance_change(
        self, db_session: AsyncSession
    ) -> None:
        """Expired session transitions pending purchase, balance stays intact."""
        user = await _seed_user_with_balance(db_session, balance=_EXPIRED_BALANCE)
        purchase = await _seed_purchase(db_session, user)

        event = _make_expired_event()
        await handle_checkout_expired(db_session, event=event)
        await db_session.flush()

        # Purchase transitioned to expired
        await db_session.refresh(purchase)
        assert purchase.status == "expired"

        # Balance unchanged — expired sessions create no financial impact
        await db_session.refresh(user)
        assert user.balance_usd == _EXPIRED_BALANCE

        # No credit transactions created
        txn_count = await db_session.execute(
            text("SELECT COUNT(*) FROM credit_transactions WHERE user_id = :uid"),
            {"uid": user.id},
        )
        assert txn_count.scalar_one() == 0


# ===========================================================================
# Customer Creation Savepoint (REQ-030 §8.1 / F-11)
# ===========================================================================


@pytest.mark.asyncio
class TestCustomerCreationSavepoint:
    """REQ-030 §8.1, §15.2: begin_nested() scopes IntegrityError on UNIQUE."""

    async def test_savepoint_isolates_unique_violation_session_survives(
        self, db_session: AsyncSession
    ) -> None:
        """UNIQUE violation inside begin_nested() leaves session usable.

        user_a owns a conflicting stripe_customer_id. user_b's
        get_or_create_customer call returns the same ID from Stripe →
        UNIQUE violation → IntegrityError inside begin_nested(). The
        savepoint rolls back only the flush, not the outer transaction.
        Session remains usable for subsequent write operations.
        """
        # User A already holds the conflicting customer ID
        user_a = User(
            email="holder@example.com",
            stripe_customer_id=_CONFLICTING_CUSTOMER_ID,
        )
        db_session.add(user_a)
        await db_session.flush()

        # User B wants a Stripe customer (no existing ID)
        user_b = User(email="requester@example.com")
        db_session.add(user_b)
        await db_session.flush()
        user_b_id = user_b.id

        # Mock Stripe API to return the conflicting customer ID
        mock_client = MagicMock()
        mock_customer = MagicMock()
        mock_customer.id = _CONFLICTING_CUSTOMER_ID
        mock_client.v1.customers.create_async = AsyncMock(return_value=mock_customer)

        # get_or_create_customer hits UNIQUE constraint → StripeServiceError
        # (user_b still has no customer_id after recovery read)
        with pytest.raises(StripeServiceError):
            await get_or_create_customer(
                db_session,
                user_id=user_b_id,
                email="requester@example.com",
                stripe_client=mock_client,
            )

        # Session must still be usable — verify with a WRITE operation.
        # Without begin_nested(), this would fail with
        # "transaction is inactive due to a previous exception".
        post_error_user = User(email="post-error@example.com")
        db_session.add(post_error_user)
        await db_session.flush()

        result = await db_session.execute(
            select(User).where(User.email == "post-error@example.com")
        )
        assert result.scalar_one() is not None

        # Original users are intact — savepoint didn't corrupt prior state
        result_a = await db_session.execute(select(User).where(User.id == user_a.id))
        assert result_a.scalar_one().stripe_customer_id == _CONFLICTING_CUSTOMER_ID
