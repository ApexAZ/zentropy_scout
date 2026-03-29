"""Tests for checkout.session.expired webhook handler.

REQ-030 §7.3 (F-07): Verifies that expired Stripe checkout sessions
transition pending purchases to 'expired' status. No balance changes.
"""

import uuid
from unittest.mock import MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import FundingPack
from app.models.stripe import StripePurchase
from app.models.user import User
from app.services.stripe_webhook_service import handle_checkout_expired

# ===============================================================================
# Constants & Helpers
# ===============================================================================

_TEST_EVENT_ID = "evt_expired_abc123"
_TEST_SESSION_ID = "cs_test_xyz789"
_TEST_CUSTOMER_ID = "cus_test_abc123"
_TEST_EMAIL = "test@example.com"


def _make_expired_event(
    *,
    event_id: str = _TEST_EVENT_ID,
    session_id: str = _TEST_SESSION_ID,
) -> MagicMock:
    """Build a mock Stripe checkout.session.expired event."""
    event = MagicMock()
    event.id = event_id
    event.data.object = {
        "id": session_id,
    }
    return event


async def _setup_pending_purchase(
    db_session: AsyncSession,
    *,
    session_id: str = _TEST_SESSION_ID,
    status: str = "pending",
) -> tuple[User, StripePurchase]:
    """Create user and a purchase with the given status."""
    user = User(email=_TEST_EMAIL, stripe_customer_id=_TEST_CUSTOMER_ID)
    db_session.add(user)
    await db_session.flush()

    pack = FundingPack(
        id=uuid.uuid4(),
        name="Starter",
        price_cents=500,
        grant_cents=500,
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
        stripe_session_id=session_id,
        stripe_customer_id=_TEST_CUSTOMER_ID,
        amount_cents=500,
        grant_cents=500,
        status=status,
    )
    db_session.add(purchase)
    await db_session.flush()

    return user, purchase


# ===============================================================================
# handle_checkout_expired — happy path
# ===============================================================================


class TestHandleCheckoutExpired:
    """REQ-030 §7.3: Expired sessions transition pending→expired."""

    async def test_pending_purchase_transitions_to_expired(
        self, db_session: AsyncSession
    ) -> None:
        """Pending purchase should be marked as 'expired'."""
        _user, purchase = await _setup_pending_purchase(db_session)
        event = _make_expired_event()

        await handle_checkout_expired(db_session, event=event)

        await db_session.refresh(purchase)
        assert purchase.status == "expired"

    async def test_no_balance_changes(self, db_session: AsyncSession) -> None:
        """Expired session should not affect user balance."""
        user, _purchase = await _setup_pending_purchase(db_session)
        event = _make_expired_event()

        await handle_checkout_expired(db_session, event=event)

        await db_session.refresh(user)
        assert user.balance_usd == 0


# ===============================================================================
# handle_checkout_expired — skip cases
# ===============================================================================


class TestHandleCheckoutExpiredSkips:
    """Scenarios that skip processing — non-pending purchases."""

    async def test_completed_purchase_not_affected(
        self, db_session: AsyncSession
    ) -> None:
        """Completed purchase should not be changed to expired."""
        _user, purchase = await _setup_pending_purchase(db_session, status="completed")
        event = _make_expired_event()

        await handle_checkout_expired(db_session, event=event)

        await db_session.refresh(purchase)
        assert purchase.status == "completed"

    async def test_refunded_purchase_not_affected(
        self, db_session: AsyncSession
    ) -> None:
        """Refunded purchase should not be changed to expired."""
        _user, purchase = await _setup_pending_purchase(db_session, status="refunded")
        event = _make_expired_event()

        await handle_checkout_expired(db_session, event=event)

        await db_session.refresh(purchase)
        assert purchase.status == "refunded"

    async def test_unknown_session_is_noop(self, db_session: AsyncSession) -> None:
        """Unknown session ID should not raise — handler is no-op."""
        _user, _purchase = await _setup_pending_purchase(db_session)
        event = _make_expired_event(session_id="cs_nonexistent")

        await handle_checkout_expired(db_session, event=event)
        # No exception = pass


# ===============================================================================
# handle_checkout_expired — error handling
# ===============================================================================


class TestHandleCheckoutExpiredErrorHandling:
    """Never-raise contract: errors are logged, not raised."""

    async def test_exception_is_caught_and_logged(
        self, db_session: AsyncSession
    ) -> None:
        """Handler catches exceptions and logs them (never-raise contract)."""
        event = _make_expired_event()

        with (
            patch(
                "app.services.stripe_webhook_service.StripePurchaseRepository.mark_expired",
                side_effect=RuntimeError("simulated DB failure"),
            ),
            patch("app.services.stripe_webhook_service.logger") as mock_logger,
        ):
            await handle_checkout_expired(db_session, event=event)

        mock_logger.exception.assert_called_once()
        log_args = mock_logger.exception.call_args
        assert _TEST_EVENT_ID in log_args[0][1]
