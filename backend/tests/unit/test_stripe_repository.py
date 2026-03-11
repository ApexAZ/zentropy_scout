"""Tests for StripePurchaseRepository + CreditRepository.find_by_stripe_event_id.

REQ-029 §7.2, §7.3, §8.3: Verifies CRUD operations for stripe_purchases,
lifecycle transitions (mark_completed, mark_refunded), paginated queries,
and idempotency lookup via stripe_event_id on credit_transactions.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import FundingPack
from app.models.stripe import StripePurchase
from app.models.user import User
from app.repositories.credit_repository import CreditRepository
from app.repositories.stripe_repository import StripePurchaseRepository

# ===============================================================================
# Helpers
# ===============================================================================


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


async def _create_purchase(
    db: AsyncSession,
    user_id: uuid.UUID,
    pack_id: uuid.UUID,
    *,
    stripe_session_id: str | None = None,
    stripe_customer_id: str = "cus_test_abc123",
    amount_cents: int = 500,
    grant_cents: int = 50000,
) -> StripePurchase:
    """Insert a StripePurchase via the repository."""
    return await StripePurchaseRepository.create(
        db,
        user_id=user_id,
        pack_id=pack_id,
        stripe_session_id=stripe_session_id or f"cs_test_{uuid.uuid4().hex[:12]}",
        stripe_customer_id=stripe_customer_id,
        amount_cents=amount_cents,
        grant_cents=grant_cents,
    )


# =============================================================================
# StripePurchaseRepository.create
# =============================================================================


class TestCreate:
    """Tests for StripePurchaseRepository.create()."""

    async def test_creates_purchase_with_all_fields(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Creates a StripePurchase with all required fields populated."""
        pack = await _create_funding_pack(db_session)
        purchase = await StripePurchaseRepository.create(
            db_session,
            user_id=user_a.id,
            pack_id=pack.id,
            stripe_session_id="cs_test_create_001",
            stripe_customer_id="cus_test_create_001",
            amount_cents=1000,
            grant_cents=100000,
        )
        assert purchase.id is not None
        assert purchase.user_id == user_a.id
        assert purchase.pack_id == pack.id
        assert purchase.stripe_session_id == "cs_test_create_001"
        assert purchase.stripe_customer_id == "cus_test_create_001"
        assert purchase.amount_cents == 1000
        assert purchase.grant_cents == 100000
        assert purchase.status == "pending"
        assert purchase.currency == "usd"
        assert purchase.refund_amount_cents == 0
        assert purchase.created_at is not None

    async def test_defaults_status_to_pending(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """New purchases default to 'pending' status."""
        pack = await _create_funding_pack(db_session)
        purchase = await _create_purchase(db_session, user_a.id, pack.id)
        assert purchase.status == "pending"
        assert purchase.stripe_payment_intent is None
        assert purchase.completed_at is None


# =============================================================================
# StripePurchaseRepository.find_by_session_id
# =============================================================================


class TestFindBySessionId:
    """Tests for StripePurchaseRepository.find_by_session_id()."""

    async def test_returns_purchase_for_existing_session(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Returns the purchase matching a known stripe_session_id."""
        pack = await _create_funding_pack(db_session)
        created = await _create_purchase(
            db_session, user_a.id, pack.id, stripe_session_id="cs_test_find_001"
        )
        found = await StripePurchaseRepository.find_by_session_id(
            db_session, "cs_test_find_001"
        )
        assert found is not None
        assert found.id == created.id

    async def test_returns_none_for_unknown_session(
        self, db_session: AsyncSession
    ) -> None:
        """Returns None when no purchase matches the session ID."""
        found = await StripePurchaseRepository.find_by_session_id(
            db_session, "cs_test_nonexistent"
        )
        assert found is None


# =============================================================================
# StripePurchaseRepository.find_by_payment_intent
# =============================================================================


class TestFindByPaymentIntent:
    """Tests for StripePurchaseRepository.find_by_payment_intent()."""

    async def test_returns_purchase_for_existing_intent(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Returns the purchase matching a known stripe_payment_intent."""
        pack = await _create_funding_pack(db_session)
        purchase = await _create_purchase(db_session, user_a.id, pack.id)
        # Simulate webhook setting payment_intent
        await StripePurchaseRepository.mark_completed(
            db_session,
            stripe_session_id=purchase.stripe_session_id,
            stripe_payment_intent="pi_test_find_001",
        )
        found = await StripePurchaseRepository.find_by_payment_intent(
            db_session, "pi_test_find_001"
        )
        assert found is not None
        assert found.id == purchase.id

    async def test_returns_none_for_unknown_intent(
        self, db_session: AsyncSession
    ) -> None:
        """Returns None when no purchase matches the payment intent."""
        found = await StripePurchaseRepository.find_by_payment_intent(
            db_session, "pi_test_nonexistent"
        )
        assert found is None


# =============================================================================
# StripePurchaseRepository.mark_completed
# =============================================================================


class TestMarkCompleted:
    """Tests for StripePurchaseRepository.mark_completed()."""

    async def test_updates_status_to_completed(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Sets status to 'completed', stores payment_intent and completed_at."""
        pack = await _create_funding_pack(db_session)
        purchase = await _create_purchase(
            db_session, user_a.id, pack.id, stripe_session_id="cs_test_complete_001"
        )
        updated = await StripePurchaseRepository.mark_completed(
            db_session,
            stripe_session_id="cs_test_complete_001",
            stripe_payment_intent="pi_test_complete_001",
        )
        assert updated is True
        await db_session.refresh(purchase)
        assert purchase.status == "completed"
        assert purchase.stripe_payment_intent == "pi_test_complete_001"
        assert purchase.completed_at is not None

    async def test_completed_at_has_timezone(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """completed_at is timezone-aware."""
        pack = await _create_funding_pack(db_session)
        purchase = await _create_purchase(
            db_session, user_a.id, pack.id, stripe_session_id="cs_test_complete_tz"
        )
        await StripePurchaseRepository.mark_completed(
            db_session,
            stripe_session_id="cs_test_complete_tz",
            stripe_payment_intent="pi_test_tz",
        )
        await db_session.refresh(purchase)
        assert purchase.completed_at.tzinfo is not None

    async def test_skips_already_completed_purchase(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Returns False and no-ops for a purchase already in 'completed' status."""
        pack = await _create_funding_pack(db_session)
        purchase = await _create_purchase(
            db_session, user_a.id, pack.id, stripe_session_id="cs_test_already_done"
        )
        # First completion
        await StripePurchaseRepository.mark_completed(
            db_session,
            stripe_session_id="cs_test_already_done",
            stripe_payment_intent="pi_test_first",
        )
        # Second attempt (replay) — should be skipped
        updated = await StripePurchaseRepository.mark_completed(
            db_session,
            stripe_session_id="cs_test_already_done",
            stripe_payment_intent="pi_test_second",
        )
        assert updated is False
        await db_session.refresh(purchase)
        assert purchase.stripe_payment_intent == "pi_test_first"

    async def test_returns_false_for_unknown_session(
        self, db_session: AsyncSession
    ) -> None:
        """Returns False when no purchase matches the session ID."""
        updated = await StripePurchaseRepository.mark_completed(
            db_session,
            stripe_session_id="cs_test_nonexistent",
            stripe_payment_intent="pi_test_ghost",
        )
        assert updated is False


# =============================================================================
# StripePurchaseRepository.mark_refunded
# =============================================================================


class TestMarkRefunded:
    """Tests for StripePurchaseRepository.mark_refunded()."""

    async def test_full_refund_sets_refunded_status(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Full refund sets status='refunded' and refunded_at."""
        pack = await _create_funding_pack(db_session)
        purchase = await _create_purchase(db_session, user_a.id, pack.id)
        await StripePurchaseRepository.mark_completed(
            db_session,
            stripe_session_id=purchase.stripe_session_id,
            stripe_payment_intent="pi_test_refund_full",
        )
        await StripePurchaseRepository.mark_refunded(
            db_session,
            purchase_id=purchase.id,
            refund_amount_cents=500,
            is_full_refund=True,
        )
        await db_session.refresh(purchase)
        assert purchase.status == "refunded"
        assert purchase.refund_amount_cents == 500
        assert purchase.refunded_at is not None

    async def test_partial_refund_sets_partial_status(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Partial refund sets status='partial_refund'."""
        pack = await _create_funding_pack(db_session)
        purchase = await _create_purchase(
            db_session, user_a.id, pack.id, amount_cents=1000
        )
        await StripePurchaseRepository.mark_completed(
            db_session,
            stripe_session_id=purchase.stripe_session_id,
            stripe_payment_intent="pi_test_refund_partial",
        )
        await StripePurchaseRepository.mark_refunded(
            db_session,
            purchase_id=purchase.id,
            refund_amount_cents=300,
            is_full_refund=False,
        )
        await db_session.refresh(purchase)
        assert purchase.status == "partial_refund"
        assert purchase.refund_amount_cents == 300
        assert purchase.refunded_at is not None

    async def test_cumulative_partial_refund_updates_amount(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Second partial refund updates cumulative refund_amount_cents."""
        pack = await _create_funding_pack(db_session)
        purchase = await _create_purchase(
            db_session, user_a.id, pack.id, amount_cents=1000
        )
        await StripePurchaseRepository.mark_completed(
            db_session,
            stripe_session_id=purchase.stripe_session_id,
            stripe_payment_intent="pi_test_cumulative",
        )
        # First partial refund: 300 cents
        await StripePurchaseRepository.mark_refunded(
            db_session,
            purchase_id=purchase.id,
            refund_amount_cents=300,
            is_full_refund=False,
        )
        # Second partial refund: 700 cents cumulative (full)
        await StripePurchaseRepository.mark_refunded(
            db_session,
            purchase_id=purchase.id,
            refund_amount_cents=700,
            is_full_refund=True,
        )
        await db_session.refresh(purchase)
        assert purchase.status == "refunded"
        assert purchase.refund_amount_cents == 700

    async def test_skips_pending_purchase(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Returns False for a purchase still in 'pending' status."""
        pack = await _create_funding_pack(db_session)
        purchase = await _create_purchase(db_session, user_a.id, pack.id)
        # Try to refund without completing first
        updated = await StripePurchaseRepository.mark_refunded(
            db_session,
            purchase_id=purchase.id,
            refund_amount_cents=500,
            is_full_refund=True,
        )
        assert updated is False
        await db_session.refresh(purchase)
        assert purchase.status == "pending"

    async def test_skips_already_fully_refunded(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Returns False for a purchase already in 'refunded' status."""
        pack = await _create_funding_pack(db_session)
        purchase = await _create_purchase(db_session, user_a.id, pack.id)
        await StripePurchaseRepository.mark_completed(
            db_session,
            stripe_session_id=purchase.stripe_session_id,
            stripe_payment_intent="pi_test_double_refund",
        )
        # First full refund
        await StripePurchaseRepository.mark_refunded(
            db_session,
            purchase_id=purchase.id,
            refund_amount_cents=500,
            is_full_refund=True,
        )
        # Second attempt — should be skipped
        updated = await StripePurchaseRepository.mark_refunded(
            db_session,
            purchase_id=purchase.id,
            refund_amount_cents=500,
            is_full_refund=True,
        )
        assert updated is False


# =============================================================================
# StripePurchaseRepository.get_user_purchases
# =============================================================================


class TestGetUserPurchases:
    """Tests for StripePurchaseRepository.get_user_purchases()."""

    async def test_returns_purchases_for_user(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Returns all purchases for the specified user."""
        pack = await _create_funding_pack(db_session)
        await _create_purchase(db_session, user_a.id, pack.id)
        await _create_purchase(db_session, user_a.id, pack.id)
        purchases, total = await StripePurchaseRepository.get_user_purchases(
            db_session, user_a.id
        )
        assert len(purchases) == 2
        assert total == 2

    async def test_pagination(self, db_session: AsyncSession, user_a: User) -> None:
        """Pagination returns correct subset and total count."""
        pack = await _create_funding_pack(db_session)
        for _ in range(5):
            await _create_purchase(db_session, user_a.id, pack.id)
        purchases, total = await StripePurchaseRepository.get_user_purchases(
            db_session, user_a.id, offset=0, limit=3
        )
        assert len(purchases) == 3
        assert total == 5

    async def test_ordered_by_created_at_desc(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Results ordered by created_at descending (newest first)."""
        pack = await _create_funding_pack(db_session)
        # Create with explicit timestamps to guarantee ordering
        p_old = StripePurchase(
            user_id=user_a.id,
            pack_id=pack.id,
            stripe_session_id="cs_test_old",
            stripe_customer_id="cus_test_order",
            amount_cents=500,
            grant_cents=50000,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        p_new = StripePurchase(
            user_id=user_a.id,
            pack_id=pack.id,
            stripe_session_id="cs_test_new",
            stripe_customer_id="cus_test_order",
            amount_cents=500,
            grant_cents=50000,
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
        db_session.add_all([p_old, p_new])
        await db_session.flush()
        await db_session.refresh(p_old)
        await db_session.refresh(p_new)

        purchases, _ = await StripePurchaseRepository.get_user_purchases(
            db_session, user_a.id
        )
        # Most recent should be first
        assert purchases[0].id == p_new.id
        assert purchases[1].id == p_old.id

    async def test_cross_user_isolation(
        self, db_session: AsyncSession, user_a: User, other_user: User
    ) -> None:
        """Purchases from other users are not returned."""
        pack = await _create_funding_pack(db_session)
        await _create_purchase(db_session, user_a.id, pack.id)
        await _create_purchase(db_session, other_user.id, pack.id)
        purchases, total = await StripePurchaseRepository.get_user_purchases(
            db_session, user_a.id
        )
        assert len(purchases) == 1
        assert total == 1

    async def test_empty_result(self, db_session: AsyncSession, user_a: User) -> None:
        """No purchases returns empty list and zero count."""
        purchases, total = await StripePurchaseRepository.get_user_purchases(
            db_session, user_a.id
        )
        assert purchases == []
        assert total == 0


# =============================================================================
# CreditRepository.find_by_stripe_event_id
# =============================================================================


class TestFindByStripeEventId:
    """Tests for CreditRepository.find_by_stripe_event_id().

    REQ-029 §7.2: Idempotency lookup — webhook handlers check whether
    an event has already been processed by searching for its stripe_event_id.
    """

    async def test_returns_transaction_with_matching_event_id(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Returns the CreditTransaction matching a known stripe_event_id."""
        txn = await CreditRepository.create(
            db_session,
            user_id=user_a.id,
            amount_usd=Decimal("5.000000"),
            transaction_type="purchase",
            reference_id="cs_test_evt",
            description="Test purchase",
            stripe_event_id="evt_test_find_001",
        )
        found = await CreditRepository.find_by_stripe_event_id(
            db_session, "evt_test_find_001"
        )
        assert found is not None
        assert found.id == txn.id

    async def test_returns_none_for_unknown_event_id(
        self, db_session: AsyncSession
    ) -> None:
        """Returns None when no transaction matches the event ID."""
        found = await CreditRepository.find_by_stripe_event_id(
            db_session, "evt_test_nonexistent"
        )
        assert found is None

    async def test_returns_none_when_no_events_have_stripe_event_id(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Returns None even when transactions exist but none have stripe_event_id."""
        await CreditRepository.create(
            db_session,
            user_id=user_a.id,
            amount_usd=Decimal("5.000000"),
            transaction_type="purchase",
        )
        found = await CreditRepository.find_by_stripe_event_id(
            db_session, "evt_test_any"
        )
        assert found is None
