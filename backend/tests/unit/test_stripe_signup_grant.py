"""Tests for Stripe service — grant_signup_credits.

REQ-029 §12, REQ-021 §8: Verifies signup grant crediting, idempotency,
configurable amount via system_config, and disabled-grant handling.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import SystemConfig
from app.models.usage import CreditTransaction
from app.models.user import User
from app.services.billing.stripe_service import grant_signup_credits

# ===============================================================================
# Constants & Helpers
# ===============================================================================

_TEST_EMAIL = "test@example.com"


async def _create_user(db_session: AsyncSession) -> User:
    """Create a test user with zero balance."""
    user = User(email=_TEST_EMAIL)
    db_session.add(user)
    await db_session.flush()
    return user


async def _set_signup_grant_cents(db_session: AsyncSession, value: int) -> None:
    """Set the signup_grant_cents system config value."""
    existing = await db_session.get(SystemConfig, "signup_grant_cents")
    if existing:
        existing.value = str(value)
    else:
        db_session.add(
            SystemConfig(
                key="signup_grant_cents",
                value=str(value),
                description="Signup grant amount in cents",
            )
        )
    await db_session.flush()


async def _find_signup_grant_txn(
    db_session: AsyncSession, user: User
) -> CreditTransaction | None:
    """Find the signup_grant transaction for a user."""
    stmt = select(CreditTransaction).where(
        CreditTransaction.user_id == user.id,
        CreditTransaction.transaction_type == "signup_grant",
    )
    result = await db_session.execute(stmt)
    return result.scalar_one_or_none()


# ===============================================================================
# grant_signup_credits — success
# ===============================================================================


class TestGrantSignupCreditsSuccess:
    """Happy path — grants credits to new users."""

    async def test_credits_user_balance(self, db_session: AsyncSession) -> None:
        """Should credit the user's balance with the signup grant."""
        user = await _create_user(db_session)
        await _set_signup_grant_cents(db_session, 10)  # $0.10

        await grant_signup_credits(db_session, user_id=user.id)

        await db_session.refresh(user)
        assert user.balance_usd == Decimal("0.1")

    async def test_creates_signup_grant_transaction(
        self, db_session: AsyncSession
    ) -> None:
        """Should create a credit transaction with correct fields."""
        user = await _create_user(db_session)
        await _set_signup_grant_cents(db_session, 10)

        await grant_signup_credits(db_session, user_id=user.id)

        txn = await _find_signup_grant_txn(db_session, user)
        assert txn is not None
        assert txn.amount_usd == Decimal("0.1")
        assert txn.transaction_type == "signup_grant"
        assert txn.description == "Welcome bonus — free starter balance"

    async def test_converts_cents_to_usd(self, db_session: AsyncSession) -> None:
        """Should correctly convert cents to USD (e.g. 500 → $5.00)."""
        user = await _create_user(db_session)
        await _set_signup_grant_cents(db_session, 500)

        await grant_signup_credits(db_session, user_id=user.id)

        await db_session.refresh(user)
        assert user.balance_usd == Decimal("5")


# ===============================================================================
# grant_signup_credits — idempotency & skips
# ===============================================================================


class TestGrantSignupCreditsSkips:
    """Scenarios that skip granting."""

    async def test_skips_duplicate_grant(self, db_session: AsyncSession) -> None:
        """Should skip if user already has a signup_grant transaction."""
        user = await _create_user(db_session)
        await _set_signup_grant_cents(db_session, 10)

        await grant_signup_credits(db_session, user_id=user.id)
        await db_session.refresh(user)
        balance_after_first = user.balance_usd

        await grant_signup_credits(db_session, user_id=user.id)

        await db_session.refresh(user)
        assert user.balance_usd == balance_after_first

    async def test_skips_when_grant_is_zero(self, db_session: AsyncSession) -> None:
        """Should skip when signup_grant_cents is 0 (grants disabled)."""
        user = await _create_user(db_session)
        await _set_signup_grant_cents(db_session, 0)

        await grant_signup_credits(db_session, user_id=user.id)

        await db_session.refresh(user)
        assert user.balance_usd == Decimal("0")
        assert await _find_signup_grant_txn(db_session, user) is None

    async def test_skips_when_config_missing(self, db_session: AsyncSession) -> None:
        """Should skip when signup_grant_cents key is missing (default 0)."""
        user = await _create_user(db_session)
        # No system_config row for signup_grant_cents

        await grant_signup_credits(db_session, user_id=user.id)

        await db_session.refresh(user)
        assert user.balance_usd == Decimal("0")
        assert await _find_signup_grant_txn(db_session, user) is None
