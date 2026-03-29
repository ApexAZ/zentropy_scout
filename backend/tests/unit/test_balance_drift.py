"""Tests for balance/ledger drift detection.

REQ-030 §11.2: Detects mismatch between users.balance_usd
and SUM(credit_transactions.amount_usd).
"""

import uuid
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import CreditTransaction
from app.models.user import User
from app.services.reservation_sweep import detect_balance_drift

_USER_BALANCE = Decimal("10.000000")

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _seed_user(db: AsyncSession) -> User:
    """Create a test user with known balance."""
    user = User(
        id=TEST_USER_ID,
        email="drift-test@example.com",
        name="Drift Test User",
        balance_usd=_USER_BALANCE,
        held_balance_usd=Decimal("0.000000"),
    )
    db.add(user)
    await db.flush()
    return user


async def _seed_credit_transaction(
    db: AsyncSession,
    *,
    user_id: uuid.UUID = TEST_USER_ID,
    amount_usd: Decimal,
    transaction_type: str = "purchase",
) -> CreditTransaction:
    """Insert a credit transaction."""
    txn = CreditTransaction(
        user_id=user_id,
        amount_usd=amount_usd,
        transaction_type=transaction_type,
        description="test transaction",
    )
    db.add(txn)
    await db.flush()
    return txn


class TestDetectBalanceDrift:
    """Tests for the detect_balance_drift function."""

    async def test_no_drift_returns_empty(self, db_session: AsyncSession) -> None:
        """When balance matches ledger sum, no drift is detected."""
        await _seed_user(db_session)
        await _seed_credit_transaction(db_session, amount_usd=_USER_BALANCE)

        drifts = await detect_balance_drift(db_session)

        assert drifts == []

    async def test_detects_positive_drift(self, db_session: AsyncSession) -> None:
        """When balance_usd > ledger sum, drift is detected."""
        await _seed_user(db_session)
        # Ledger has only 5.00 but balance is 10.00 → drift of +5.00
        await _seed_credit_transaction(db_session, amount_usd=Decimal("5.000000"))

        drifts = await detect_balance_drift(db_session)

        assert len(drifts) == 1
        assert drifts[0]["user_id"] == TEST_USER_ID
        assert drifts[0]["balance_usd"] == _USER_BALANCE
        assert drifts[0]["ledger_sum"] == Decimal("5.000000")
        assert drifts[0]["drift"] == Decimal("5.000000")

    async def test_detects_negative_drift(self, db_session: AsyncSession) -> None:
        """When balance_usd < ledger sum, drift is detected."""
        await _seed_user(db_session)
        # Ledger has 15.00 but balance is 10.00 → drift of -5.00
        await _seed_credit_transaction(db_session, amount_usd=Decimal("15.000000"))

        drifts = await detect_balance_drift(db_session)

        assert len(drifts) == 1
        assert drifts[0]["drift"] == Decimal("-5.000000")

    async def test_drift_at_threshold_not_reported(
        self, db_session: AsyncSession
    ) -> None:
        """Drift exactly at threshold (0.000001) is not reported (> not >=)."""
        await _seed_user(db_session)
        # Seed transaction 0.000001 less than balance — drift is exactly at threshold
        await _seed_credit_transaction(
            db_session, amount_usd=_USER_BALANCE - Decimal("0.000001")
        )
        # The HAVING clause uses > (strict), so exactly-at-threshold is excluded.
        # Numeric(10,6) stores 6 decimal places, so the drift of 0.000001
        # is NOT > 0.000001, and should be excluded.

        drifts = await detect_balance_drift(db_session)
        assert drifts == []

    async def test_user_with_no_transactions_and_zero_balance(
        self, db_session: AsyncSession
    ) -> None:
        """User with zero balance and no transactions has no drift."""
        user = User(
            id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            email="zero@example.com",
            name="Zero Balance User",
            balance_usd=Decimal("0.000000"),
            held_balance_usd=Decimal("0.000000"),
        )
        db_session.add(user)
        await db_session.flush()

        drifts = await detect_balance_drift(db_session)
        assert drifts == []

    async def test_user_with_no_transactions_and_nonzero_balance(
        self, db_session: AsyncSession
    ) -> None:
        """User with balance but no ledger entries has drift."""
        await _seed_user(db_session)

        drifts = await detect_balance_drift(db_session)

        assert len(drifts) == 1
        assert drifts[0]["user_id"] == TEST_USER_ID
        assert drifts[0]["ledger_sum"] == Decimal("0")
        assert drifts[0]["drift"] == _USER_BALANCE

    async def test_drift_logs_at_error_level(self, db_session: AsyncSession) -> None:
        """Drift detection logs each drifted user at error level."""
        await _seed_user(db_session)
        # No transactions — balance of 10.00 is all drift

        with patch("app.services.reservation_sweep.logger") as mock_logger:
            await detect_balance_drift(db_session)

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert str(TEST_USER_ID) in str(call_args)
