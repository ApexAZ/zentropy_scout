"""Tests for Stripe service — handle_checkout_completed webhook handler.

REQ-029 §7.2, §13.2: Verifies checkout completion handling, idempotency,
metadata validation, balance crediting, and purchase status updates.
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import FundingPack
from app.models.stripe import StripePurchase
from app.models.usage import CreditTransaction
from app.models.user import User
from app.services.stripe_webhook_service import handle_checkout_completed

# ===============================================================================
# Constants & Helpers
# ===============================================================================

_TEST_EVENT_ID = "evt_test_abc123"
_TEST_SESSION_ID = "cs_test_xyz789"
_TEST_CUSTOMER_ID = "cus_test_abc123"
_TEST_PAYMENT_INTENT = "pi_test_abc123"
_TEST_EMAIL = "test@example.com"
_TEST_GRANT_CENTS = 50000  # $500.00
_TEST_GRANT_USD = Decimal(_TEST_GRANT_CENTS) / Decimal(100)


def _make_event(
    *,
    event_id: str = _TEST_EVENT_ID,
    session_id: str = _TEST_SESSION_ID,
    customer_id: str = _TEST_CUSTOMER_ID,
    payment_intent: str = _TEST_PAYMENT_INTENT,
    payment_status: str = "paid",
    metadata: dict[str, str] | None = None,
) -> MagicMock:
    """Build a mock Stripe checkout.session.completed event."""
    event = MagicMock()
    event.id = event_id
    # Stripe types event.data.object as dict[str, Any]
    event.data.object = {
        "id": session_id,
        "customer": customer_id,
        "payment_intent": payment_intent,
        "payment_status": payment_status,
        "metadata": metadata or {},
    }
    return event


async def _setup_user_and_purchase(
    db_session: AsyncSession,
    *,
    grant_cents: int = _TEST_GRANT_CENTS,
) -> tuple[User, FundingPack, StripePurchase]:
    """Create user, pack, and pending purchase for webhook tests."""
    user = User(email=_TEST_EMAIL, stripe_customer_id=_TEST_CUSTOMER_ID)
    db_session.add(user)
    await db_session.flush()

    pack = FundingPack(
        id=uuid.uuid4(),
        name="Starter",
        price_cents=500,
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
        stripe_session_id=_TEST_SESSION_ID,
        stripe_customer_id=_TEST_CUSTOMER_ID,
        amount_cents=500,
        grant_cents=grant_cents,
    )
    db_session.add(purchase)
    await db_session.flush()

    return user, pack, purchase


def _default_metadata(user: User, pack: FundingPack) -> dict[str, str]:
    """Build standard metadata dict for a checkout event."""
    return {
        "user_id": str(user.id),
        "pack_id": str(pack.id),
        "grant_cents": str(_TEST_GRANT_CENTS),
    }


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
# handle_checkout_completed — success
# ===============================================================================


class TestHandleCheckoutCompletedSuccess:
    """Happy path — paid session credits balance correctly."""

    async def test_credits_user_balance(self, db_session: AsyncSession) -> None:
        """Should atomically credit the user's balance."""
        user, pack, _purchase = await _setup_user_and_purchase(db_session)
        event = _make_event(metadata=_default_metadata(user, pack))

        await handle_checkout_completed(db_session, event=event)

        await db_session.refresh(user)
        assert user.balance_usd == _TEST_GRANT_USD

    async def test_creates_purchase_credit_transaction(
        self, db_session: AsyncSession
    ) -> None:
        """Should create a credit transaction with correct fields."""
        user, pack, _purchase = await _setup_user_and_purchase(db_session)
        event = _make_event(metadata=_default_metadata(user, pack))

        await handle_checkout_completed(db_session, event=event)

        txn = await _find_txn_by_event(db_session)
        assert txn is not None
        assert txn.user_id == user.id
        assert txn.amount_usd == _TEST_GRANT_USD
        assert txn.transaction_type == "purchase"
        assert txn.reference_id == _TEST_SESSION_ID
        assert txn.stripe_event_id == _TEST_EVENT_ID
        assert txn.description == "Funding pack purchase"

    async def test_marks_purchase_completed(self, db_session: AsyncSession) -> None:
        """Should update the StripePurchase record to completed."""
        user, pack, purchase = await _setup_user_and_purchase(db_session)
        event = _make_event(metadata=_default_metadata(user, pack))

        await handle_checkout_completed(db_session, event=event)

        await db_session.refresh(purchase)
        assert purchase.status == "completed"
        assert purchase.stripe_payment_intent == _TEST_PAYMENT_INTENT
        assert purchase.completed_at is not None

    async def test_credit_and_balance_are_atomic(
        self, db_session: AsyncSession
    ) -> None:
        """If atomic_credit fails after create flushes, neither persists.

        The savepoint in _process_checkout_completed must roll back the
        CreditTransaction record when the balance update raises. The outer
        handler must not raise (REQ-029 §7.4 "never raise" contract).
        """
        user, pack, _purchase = await _setup_user_and_purchase(db_session)
        event = _make_event(metadata=_default_metadata(user, pack))

        with patch(
            "app.services.stripe_webhook_service.CreditRepository.atomic_credit",
            side_effect=RuntimeError("simulated failure"),
        ):
            await handle_checkout_completed(db_session, event=event)

        # CreditTransaction must not exist — savepoint rolled it back
        assert await _find_txn_by_event(db_session) is None

        # Balance must remain unchanged
        await db_session.refresh(user)
        assert user.balance_usd == Decimal("0")


# ===============================================================================
# handle_checkout_completed — idempotency & skips
# ===============================================================================


class TestHandleCheckoutCompletedSkips:
    """Scenarios that skip processing (REQ-029 §13.2)."""

    async def test_skips_unpaid_session(self, db_session: AsyncSession) -> None:
        """Should skip sessions with payment_status != 'paid'."""
        user, pack, _purchase = await _setup_user_and_purchase(db_session)
        event = _make_event(
            payment_status="unpaid",
            metadata=_default_metadata(user, pack),
        )

        await handle_checkout_completed(db_session, event=event)

        await db_session.refresh(user)
        assert user.balance_usd == Decimal("0")

    async def test_skips_duplicate_event(self, db_session: AsyncSession) -> None:
        """Should skip if event ID already processed (idempotency)."""
        user, pack, _purchase = await _setup_user_and_purchase(db_session)
        event = _make_event(metadata=_default_metadata(user, pack))

        # Process once
        await handle_checkout_completed(db_session, event=event)
        await db_session.refresh(user)
        balance_after_first = user.balance_usd

        # Process again with same event ID
        await handle_checkout_completed(db_session, event=event)

        await db_session.refresh(user)
        assert user.balance_usd == balance_after_first  # No double-credit

    async def test_skips_missing_metadata(self, db_session: AsyncSession) -> None:
        """Should skip when metadata is missing required fields."""
        _user, _pack, _purchase = await _setup_user_and_purchase(db_session)
        event = _make_event(metadata={})

        await handle_checkout_completed(db_session, event=event)

        assert await _find_txn_by_event(db_session) is None

    async def test_skips_user_not_found(self, db_session: AsyncSession) -> None:
        """Should skip when user_id in metadata doesn't exist in DB."""
        _user, _pack, _purchase = await _setup_user_and_purchase(db_session)
        fake_user_id = uuid.uuid4()
        event = _make_event(
            metadata={
                "user_id": str(fake_user_id),
                "pack_id": str(uuid.uuid4()),
                "grant_cents": str(_TEST_GRANT_CENTS),
            },
        )

        await handle_checkout_completed(db_session, event=event)

        assert await _find_txn_by_event(db_session) is None

    async def test_skips_invalid_metadata_values(
        self, db_session: AsyncSession
    ) -> None:
        """Should skip when metadata has non-UUID user_id."""
        _user, _pack, _purchase = await _setup_user_and_purchase(db_session)
        event = _make_event(
            metadata={
                "user_id": "not-a-uuid",
                "pack_id": "also-not-a-uuid",
                "grant_cents": "abc",
            },
        )

        await handle_checkout_completed(db_session, event=event)

        assert await _find_txn_by_event(db_session) is None

    async def test_skips_zero_grant_cents(self, db_session: AsyncSession) -> None:
        """Should skip when grant_cents is zero (non-positive)."""
        user, pack, _purchase = await _setup_user_and_purchase(db_session)
        event = _make_event(
            metadata={
                "user_id": str(user.id),
                "pack_id": str(pack.id),
                "grant_cents": "0",
            },
        )

        await handle_checkout_completed(db_session, event=event)

        await db_session.refresh(user)
        assert user.balance_usd == Decimal("0")
        assert await _find_txn_by_event(db_session) is None

    async def test_skips_negative_grant_cents(self, db_session: AsyncSession) -> None:
        """Should skip when grant_cents is negative."""
        user, pack, _purchase = await _setup_user_and_purchase(db_session)
        event = _make_event(
            metadata={
                "user_id": str(user.id),
                "pack_id": str(pack.id),
                "grant_cents": "-500",
            },
        )

        await handle_checkout_completed(db_session, event=event)

        await db_session.refresh(user)
        assert user.balance_usd == Decimal("0")
        assert await _find_txn_by_event(db_session) is None
