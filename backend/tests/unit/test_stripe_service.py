"""Tests for Stripe service — get_or_create_customer.

REQ-029 §6.3: Verifies customer get-or-create logic and Stripe error mapping
for customer creation.
REQ-030 §8.1: Verifies savepoint-scoped rollback on IntegrityError (race
condition) preserves session state.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import stripe as stripe_module
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.billing.stripe_service import (
    StripeServiceError,
    get_or_create_customer,
)

# ===============================================================================
# Constants
# ===============================================================================

_TEST_EMAIL = "test@example.com"
_TEST_CUSTOMER_ID = "cus_test_abc123"
_WINNER_CUSTOMER_ID = "cus_winner_xyz"


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


# ===============================================================================
# get_or_create_customer — race condition (REQ-030 §8.1)
# ===============================================================================


def _make_race_session_mock() -> tuple[AsyncMock, AsyncMock]:
    """Create a mock session that raises IntegrityError on flush inside savepoint."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.flush = AsyncMock(side_effect=IntegrityError("duplicate key", {}, None))  # pyright: ignore[reportArgumentType]
    mock_nested = AsyncMock()
    mock_nested.__aenter__ = AsyncMock(return_value=mock_nested)
    mock_nested.__aexit__ = AsyncMock(return_value=False)
    mock_db.begin_nested.return_value = mock_nested
    return mock_db, mock_nested


class TestGetOrCreateCustomerRaceCondition:
    """REQ-030 §8.1: Savepoint-scoped rollback on IntegrityError."""

    async def test_savepoint_preserves_session_state(
        self, db_session: AsyncSession, mock_stripe_client: MagicMock
    ) -> None:
        """IntegrityError inside savepoint must not roll back prior session work.

        Creates a "bystander" user (simulating caller's earlier DB work),
        then triggers a real UNIQUE constraint violation. With savepoint,
        the bystander survives; with full rollback, it would be lost.
        """
        # Bystander: represents caller's earlier DB work
        bystander = User(email="bystander@example.com")
        db_session.add(bystander)
        await db_session.flush()
        bystander_id = bystander.id

        # Target user (no customer_id)
        user = User(email=_TEST_EMAIL)
        db_session.add(user)
        await db_session.flush()

        # Conflict user — already has _TEST_CUSTOMER_ID
        conflict_user = User(
            email="conflict@example.com",
            stripe_customer_id=_TEST_CUSTOMER_ID,
        )
        db_session.add(conflict_user)
        await db_session.flush()

        # Mock Stripe to return the conflicting customer ID
        new_customer = MagicMock()
        new_customer.id = _TEST_CUSTOMER_ID  # Collides with conflict_user
        mock_stripe_client.v1.customers.create_async.return_value = new_customer

        # Function will raise StripeServiceError (no winner for this user)
        with pytest.raises(StripeServiceError):
            await get_or_create_customer(
                db_session,
                user_id=user.id,
                email=_TEST_EMAIL,
                stripe_client=mock_stripe_client,
            )

        # Bystander must survive — proves savepoint scoped the rollback
        result = await db_session.execute(select(User).where(User.id == bystander_id))
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.email == "bystander@example.com"

    async def test_race_returns_winners_customer_id(
        self, mock_stripe_client: MagicMock
    ) -> None:
        """When another request wins the race, return the winner's customer ID.

        Uses a mock session because simulating a concurrent transaction
        (the winner) requires control over what get_by_id returns after
        the IntegrityError.
        """
        user_id = uuid.uuid4()

        # First get_by_id: user has no customer_id yet
        initial_user = MagicMock()
        initial_user.stripe_customer_id = None

        # Second get_by_id (after IntegrityError): winner set the ID
        winner_user = MagicMock()
        winner_user.stripe_customer_id = _WINNER_CUSTOMER_ID

        # Mock Stripe API
        new_customer = MagicMock()
        new_customer.id = _TEST_CUSTOMER_ID
        mock_stripe_client.v1.customers.create_async.return_value = new_customer

        mock_db, _mock_nested = _make_race_session_mock()

        with patch(
            "app.services.billing.stripe_service.UserRepository.get_by_id",
            side_effect=[initial_user, winner_user],
        ):
            result = await get_or_create_customer(
                mock_db,
                user_id=user_id,
                email=_TEST_EMAIL,
                stripe_client=mock_stripe_client,
            )

        assert result == _WINNER_CUSTOMER_ID
        mock_db.begin_nested.assert_called_once()

    async def test_race_no_winner_raises_service_error(
        self, mock_stripe_client: MagicMock
    ) -> None:
        """When IntegrityError occurs but no winner is found, raise StripeServiceError."""
        user_id = uuid.uuid4()

        initial_user = MagicMock()
        initial_user.stripe_customer_id = None

        # After race, user still has no customer_id (unexpected state)
        orphan_user = MagicMock()
        orphan_user.stripe_customer_id = None

        new_customer = MagicMock()
        new_customer.id = _TEST_CUSTOMER_ID
        mock_stripe_client.v1.customers.create_async.return_value = new_customer

        mock_db, _mock_nested = _make_race_session_mock()

        with (
            patch(
                "app.services.billing.stripe_service.UserRepository.get_by_id",
                side_effect=[initial_user, orphan_user],
            ),
            pytest.raises(StripeServiceError),
        ):
            await get_or_create_customer(
                mock_db,
                user_id=user_id,
                email=_TEST_EMAIL,
                stripe_client=mock_stripe_client,
            )
