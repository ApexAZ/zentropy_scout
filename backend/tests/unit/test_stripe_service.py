"""Tests for Stripe service — get_or_create_customer.

REQ-029 §6.3: Verifies customer get-or-create logic and Stripe error mapping
for customer creation.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
import stripe as stripe_module
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.stripe_service import (
    StripeServiceError,
    get_or_create_customer,
)

# ===============================================================================
# Constants
# ===============================================================================

_TEST_EMAIL = "test@example.com"
_TEST_CUSTOMER_ID = "cus_test_abc123"


@pytest.fixture
def mock_stripe_client() -> MagicMock:
    """Create a mock StripeClient with v1 namespace."""
    client = MagicMock()
    client.v1.customers.create_async = AsyncMock()
    client.v1.checkout.sessions.create_async = AsyncMock()
    return client


# ===============================================================================
# get_or_create_customer — existing customer
# ===============================================================================


class TestGetOrCreateCustomerExisting:
    """When the user already has a stripe_customer_id."""

    async def test_returns_existing_customer_id(
        self, db_session: AsyncSession, mock_stripe_client: MagicMock
    ) -> None:
        """Should return existing customer ID without calling Stripe."""
        user = User(email=_TEST_EMAIL, stripe_customer_id=_TEST_CUSTOMER_ID)
        db_session.add(user)
        await db_session.flush()

        result = await get_or_create_customer(
            db_session,
            user_id=user.id,
            email=_TEST_EMAIL,
            stripe_client=mock_stripe_client,
        )

        assert result == _TEST_CUSTOMER_ID
        mock_stripe_client.v1.customers.create_async.assert_not_called()

    async def test_does_not_update_user_record(
        self, db_session: AsyncSession, mock_stripe_client: MagicMock
    ) -> None:
        """Should not modify the user record when customer already exists."""
        user = User(email=_TEST_EMAIL, stripe_customer_id=_TEST_CUSTOMER_ID)
        db_session.add(user)
        await db_session.flush()

        await get_or_create_customer(
            db_session,
            user_id=user.id,
            email=_TEST_EMAIL,
            stripe_client=mock_stripe_client,
        )

        await db_session.refresh(user)
        assert user.stripe_customer_id == _TEST_CUSTOMER_ID


# ===============================================================================
# get_or_create_customer — new customer
# ===============================================================================


class TestGetOrCreateCustomerNew:
    """When the user does not have a stripe_customer_id."""

    async def test_creates_stripe_customer(
        self, db_session: AsyncSession, mock_stripe_client: MagicMock
    ) -> None:
        """Should call Stripe API to create a new customer."""
        user = User(email=_TEST_EMAIL)
        db_session.add(user)
        await db_session.flush()

        new_customer = MagicMock()
        new_customer.id = _TEST_CUSTOMER_ID
        mock_stripe_client.v1.customers.create_async.return_value = new_customer

        result = await get_or_create_customer(
            db_session,
            user_id=user.id,
            email=_TEST_EMAIL,
            stripe_client=mock_stripe_client,
        )

        assert result == _TEST_CUSTOMER_ID
        mock_stripe_client.v1.customers.create_async.assert_called_once_with(
            params={
                "email": _TEST_EMAIL,
                "metadata": {"zentropy_user_id": str(user.id)},
            }
        )

    async def test_saves_customer_id_to_user(
        self, db_session: AsyncSession, mock_stripe_client: MagicMock
    ) -> None:
        """Should persist the new customer ID on the user record."""
        user = User(email=_TEST_EMAIL)
        db_session.add(user)
        await db_session.flush()

        new_customer = MagicMock()
        new_customer.id = _TEST_CUSTOMER_ID
        mock_stripe_client.v1.customers.create_async.return_value = new_customer

        await get_or_create_customer(
            db_session,
            user_id=user.id,
            email=_TEST_EMAIL,
            stripe_client=mock_stripe_client,
        )

        await db_session.refresh(user)
        assert user.stripe_customer_id == _TEST_CUSTOMER_ID

    async def test_stripe_api_error_raises_service_error(
        self, db_session: AsyncSession, mock_stripe_client: MagicMock
    ) -> None:
        """Should raise StripeServiceError when Stripe API fails."""
        user = User(email=_TEST_EMAIL)
        db_session.add(user)
        await db_session.flush()

        mock_stripe_client.v1.customers.create_async.side_effect = (
            stripe_module.APIConnectionError(message="Connection refused")
        )

        with pytest.raises(StripeServiceError, match="temporarily unavailable"):
            await get_or_create_customer(
                db_session,
                user_id=user.id,
                email=_TEST_EMAIL,
                stripe_client=mock_stripe_client,
            )
