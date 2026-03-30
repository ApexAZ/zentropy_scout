"""Tests for Stripe service — create_checkout_session.

REQ-029 §6.2, §13.3: Verifies checkout session creation, pack validation,
pending purchase recording, and Stripe error mapping.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import stripe as stripe_module
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateError, ValidationError
from app.models.admin_config import FundingPack
from app.models.stripe import StripePurchase
from app.models.user import User
from app.services.billing.stripe_service import (
    StripeServiceError,
    create_checkout_session,
)

# ===============================================================================
# Constants & Fixtures
# ===============================================================================

_TEST_EMAIL = "test@example.com"
_TEST_CUSTOMER_ID = "cus_test_abc123"
_TEST_SESSION_ID = "cs_test_xyz789"
_TEST_SESSION_URL = "https://checkout.stripe.com/c/pay/cs_test_xyz789"


@pytest.fixture
def mock_stripe_client() -> MagicMock:
    """Create a mock StripeClient with v1 namespace."""
    client = MagicMock()
    client.v1.customers.create_async = AsyncMock()
    client.v1.checkout.sessions.create_async = AsyncMock()
    return client


@pytest.fixture
def funding_pack() -> FundingPack:
    """Create a FundingPack instance (not persisted)."""
    return FundingPack(
        id=uuid.uuid4(),
        name="Starter",
        price_cents=500,
        grant_cents=50000,
        stripe_price_id="price_test_starter",
        display_order=1,
        is_active=True,
        description="Starter pack",
    )


async def _create_user_and_pack(
    db_session: AsyncSession,
    pack: FundingPack,
    *,
    stripe_customer_id: str | None = _TEST_CUSTOMER_ID,
) -> User:
    """Create a user (optionally with customer ID) and persist the pack."""
    user = User(email=_TEST_EMAIL, stripe_customer_id=stripe_customer_id)
    db_session.add(user)
    await db_session.flush()
    db_session.add(pack)
    await db_session.flush()
    return user


def _mock_session(client: MagicMock) -> MagicMock:
    """Configure mock StripeClient to return a checkout session."""
    session = MagicMock()
    session.id = _TEST_SESSION_ID
    session.url = _TEST_SESSION_URL
    client.v1.checkout.sessions.create_async.return_value = session
    return session


# ===============================================================================
# create_checkout_session — success
# ===============================================================================


class TestCreateCheckoutSessionSuccess:
    """Happy path — valid pack, session created."""

    async def test_returns_url_and_session_id(
        self,
        db_session: AsyncSession,
        mock_stripe_client: MagicMock,
        funding_pack: FundingPack,
    ) -> None:
        """Should return (session.url, session.id) tuple."""
        user = await _create_user_and_pack(db_session, funding_pack)
        _mock_session(mock_stripe_client)

        url, session_id = await create_checkout_session(
            db_session,
            user_id=user.id,
            user_email=_TEST_EMAIL,
            pack=funding_pack,
            stripe_client=mock_stripe_client,
        )

        assert url == _TEST_SESSION_URL
        assert session_id == _TEST_SESSION_ID

    async def test_creates_pending_purchase_record(
        self,
        db_session: AsyncSession,
        mock_stripe_client: MagicMock,
        funding_pack: FundingPack,
    ) -> None:
        """Should record a pending StripePurchase in the database."""
        user = await _create_user_and_pack(db_session, funding_pack)
        _mock_session(mock_stripe_client)

        await create_checkout_session(
            db_session,
            user_id=user.id,
            user_email=_TEST_EMAIL,
            pack=funding_pack,
            stripe_client=mock_stripe_client,
        )

        stmt = select(StripePurchase).where(
            StripePurchase.stripe_session_id == _TEST_SESSION_ID
        )
        result = await db_session.execute(stmt)
        purchase = result.scalar_one()

        assert purchase.user_id == user.id
        assert purchase.pack_id == funding_pack.id
        assert purchase.amount_cents == funding_pack.price_cents
        assert purchase.grant_cents == funding_pack.grant_cents
        assert purchase.stripe_customer_id == _TEST_CUSTOMER_ID
        assert purchase.status == "pending"

    async def test_passes_correct_metadata_to_stripe(
        self,
        db_session: AsyncSession,
        mock_stripe_client: MagicMock,
        funding_pack: FundingPack,
    ) -> None:
        """Should include user_id, pack_id, grant_cents in session metadata."""
        user = await _create_user_and_pack(db_session, funding_pack)
        _mock_session(mock_stripe_client)

        await create_checkout_session(
            db_session,
            user_id=user.id,
            user_email=_TEST_EMAIL,
            pack=funding_pack,
            stripe_client=mock_stripe_client,
        )

        call_kwargs = mock_stripe_client.v1.checkout.sessions.create_async.call_args
        params = call_kwargs.kwargs["params"]
        assert params["metadata"]["user_id"] == str(user.id)
        assert params["metadata"]["pack_id"] == str(funding_pack.id)
        assert params["metadata"]["grant_cents"] == str(funding_pack.grant_cents)
        assert params["mode"] == "payment"
        assert params["customer"] == _TEST_CUSTOMER_ID

    async def test_uses_existing_customer(
        self,
        db_session: AsyncSession,
        mock_stripe_client: MagicMock,
        funding_pack: FundingPack,
    ) -> None:
        """Should reuse existing stripe_customer_id without calling Stripe."""
        user = await _create_user_and_pack(db_session, funding_pack)
        _mock_session(mock_stripe_client)

        await create_checkout_session(
            db_session,
            user_id=user.id,
            user_email=_TEST_EMAIL,
            pack=funding_pack,
            stripe_client=mock_stripe_client,
        )

        mock_stripe_client.v1.customers.create_async.assert_not_called()

    async def test_creates_customer_when_none_exists(
        self,
        db_session: AsyncSession,
        mock_stripe_client: MagicMock,
        funding_pack: FundingPack,
    ) -> None:
        """Should create a new Stripe customer when user has none."""
        user = await _create_user_and_pack(
            db_session, funding_pack, stripe_customer_id=None
        )

        new_customer = MagicMock()
        new_customer.id = _TEST_CUSTOMER_ID
        mock_stripe_client.v1.customers.create_async.return_value = new_customer
        _mock_session(mock_stripe_client)

        await create_checkout_session(
            db_session,
            user_id=user.id,
            user_email=_TEST_EMAIL,
            pack=funding_pack,
            stripe_client=mock_stripe_client,
        )

        mock_stripe_client.v1.customers.create_async.assert_called_once()


# ===============================================================================
# create_checkout_session — validation errors
# ===============================================================================


class TestCreateCheckoutSessionValidation:
    """Validation errors — invalid pack state."""

    async def test_pack_without_stripe_price_id_raises(
        self,
        db_session: AsyncSession,
        mock_stripe_client: MagicMock,
    ) -> None:
        """Should raise ValidationError when pack has no stripe_price_id."""
        user = User(email=_TEST_EMAIL)
        db_session.add(user)
        await db_session.flush()

        pack = FundingPack(
            id=uuid.uuid4(),
            name="No Price",
            price_cents=500,
            grant_cents=50000,
            stripe_price_id=None,
            display_order=1,
            is_active=True,
        )
        db_session.add(pack)
        await db_session.flush()

        with pytest.raises(ValidationError, match="stripe_price_id"):
            await create_checkout_session(
                db_session,
                user_id=user.id,
                user_email=_TEST_EMAIL,
                pack=pack,
                stripe_client=mock_stripe_client,
            )

    async def test_inactive_pack_raises(
        self,
        db_session: AsyncSession,
        mock_stripe_client: MagicMock,
    ) -> None:
        """Should raise InvalidStateError when pack is inactive."""
        user = User(email=_TEST_EMAIL)
        db_session.add(user)
        await db_session.flush()

        pack = FundingPack(
            id=uuid.uuid4(),
            name="Inactive",
            price_cents=500,
            grant_cents=50000,
            stripe_price_id="price_test_inactive",
            display_order=1,
            is_active=False,
        )
        db_session.add(pack)
        await db_session.flush()

        with pytest.raises(InvalidStateError, match="not active"):
            await create_checkout_session(
                db_session,
                user_id=user.id,
                user_email=_TEST_EMAIL,
                pack=pack,
                stripe_client=mock_stripe_client,
            )


# ===============================================================================
# create_checkout_session — Stripe error mapping
# ===============================================================================


class TestCreateCheckoutSessionStripeErrors:
    """Stripe API errors mapped to StripeServiceError (REQ-029 §13.3)."""

    @pytest.mark.parametrize(
        ("exc", "match"),
        [
            (stripe_module.RateLimitError(message="x"), "busy"),
            (
                stripe_module.AuthenticationError(message="x"),
                "temporarily unavailable",
            ),
            (
                stripe_module.APIConnectionError(message="x"),
                "temporarily unavailable",
            ),
            (
                stripe_module.InvalidRequestError(message="x", param="p"),
                "error",
            ),
            (stripe_module.StripeError(message="x"), "error"),
        ],
        ids=[
            "rate-limit",
            "auth",
            "connection",
            "invalid-request",
            "generic",
        ],
    )
    async def test_stripe_error_maps_to_user_safe_message(
        self,
        db_session: AsyncSession,
        mock_stripe_client: MagicMock,
        funding_pack: FundingPack,
        exc: stripe_module.StripeError,
        match: str,
    ) -> None:
        """Each Stripe error type maps to the correct user-safe message."""
        user = await _create_user_and_pack(db_session, funding_pack)

        mock_stripe_client.v1.checkout.sessions.create_async.side_effect = exc

        with pytest.raises(StripeServiceError, match=match):
            await create_checkout_session(
                db_session,
                user_id=user.id,
                user_email=_TEST_EMAIL,
                pack=funding_pack,
                stripe_client=mock_stripe_client,
            )

    async def test_stripe_error_does_not_leak_details(
        self,
        db_session: AsyncSession,
        mock_stripe_client: MagicMock,
        funding_pack: FundingPack,
    ) -> None:
        """Error message should NOT contain Stripe internal details."""
        user = await _create_user_and_pack(db_session, funding_pack)

        mock_stripe_client.v1.checkout.sessions.create_async.side_effect = (
            stripe_module.InvalidRequestError(
                message="No such price: 'price_XXXSECRET'",
                param="line_items[0][price]",
            )
        )

        with pytest.raises(StripeServiceError) as exc_info:
            await create_checkout_session(
                db_session,
                user_id=user.id,
                user_email=_TEST_EMAIL,
                pack=funding_pack,
                stripe_client=mock_stripe_client,
            )

        # User-safe message must not contain Stripe internals
        assert "price_XXXSECRET" not in exc_info.value.message
        assert "line_items" not in exc_info.value.message
