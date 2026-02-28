"""Tests for CreditRepository — atomic balance operations.

REQ-020 §4, §6.3: Verifies atomic debit/credit, overdraft prevention,
positive-amount guards, and reconciliation invariant.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import CreditTransaction
from app.models.user import User
from app.repositories.credit_repository import CreditRepository

# =============================================================================
# Helpers
# =============================================================================


async def _insert_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    amount_usd: Decimal = Decimal("10.000000"),
    transaction_type: str = "purchase",
) -> CreditTransaction:
    """Insert a credit transaction via ORM for test setup."""
    txn = CreditTransaction(
        user_id=user_id,
        amount_usd=amount_usd,
        transaction_type=transaction_type,
    )
    db.add(txn)
    await db.flush()
    await db.refresh(txn)
    return txn


async def _set_balance(db: AsyncSession, user_id: uuid.UUID, balance: Decimal) -> None:
    """Set a user's balance directly for test setup."""
    await db.execute(
        text("UPDATE users SET balance_usd = :balance WHERE id = :user_id"),
        {"balance": balance, "user_id": user_id},
    )


# =============================================================================
# TestAtomicDebit
# =============================================================================


class TestAtomicDebit:
    """Tests for CreditRepository.atomic_debit()."""

    async def test_debit_success_sufficient_balance(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Successful debit when balance is sufficient."""
        await _set_balance(db_session, user_a.id, Decimal("10.000000"))
        result = await CreditRepository.atomic_debit(
            db_session, user_id=user_a.id, amount=Decimal("3.000000")
        )
        assert result is True
        balance = await CreditRepository.get_balance(db_session, user_a.id)
        assert balance == Decimal("7.000000")

    async def test_debit_failure_insufficient_balance(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Returns False when balance is insufficient."""
        await _set_balance(db_session, user_a.id, Decimal("1.000000"))
        result = await CreditRepository.atomic_debit(
            db_session, user_id=user_a.id, amount=Decimal("5.000000")
        )
        assert result is False

    async def test_debit_failure_balance_unchanged(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Balance remains unchanged after failed debit."""
        await _set_balance(db_session, user_a.id, Decimal("1.000000"))
        await CreditRepository.atomic_debit(
            db_session, user_id=user_a.id, amount=Decimal("5.000000")
        )
        balance = await CreditRepository.get_balance(db_session, user_a.id)
        assert balance == Decimal("1.000000")

    async def test_debit_exact_balance(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Debit succeeds when amount equals balance exactly."""
        await _set_balance(db_session, user_a.id, Decimal("5.000000"))
        result = await CreditRepository.atomic_debit(
            db_session, user_id=user_a.id, amount=Decimal("5.000000")
        )
        assert result is True
        balance = await CreditRepository.get_balance(db_session, user_a.id)
        assert balance == Decimal("0.000000")


# =============================================================================
# TestAtomicCredit
# =============================================================================


class TestAtomicCredit:
    """Tests for CreditRepository.atomic_credit()."""

    async def test_credit_increases_balance(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Credit adds to the user's balance."""
        new_balance = await CreditRepository.atomic_credit(
            db_session, user_id=user_a.id, amount=Decimal("15.000000")
        )
        assert new_balance == Decimal("15.000000")

    async def test_credit_returns_new_balance(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Returns the balance after crediting."""
        await _set_balance(db_session, user_a.id, Decimal("5.000000"))
        new_balance = await CreditRepository.atomic_credit(
            db_session, user_id=user_a.id, amount=Decimal("10.000000")
        )
        assert new_balance == Decimal("15.000000")


# =============================================================================
# TestReconciliation
# =============================================================================


class TestReconciliation:
    """Tests for the SUM(transactions) == balance invariant."""

    async def test_sum_transactions_equals_balance(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """SUM(credit_transactions) must equal users.balance_usd."""
        # Purchase: +15.00
        await CreditRepository.atomic_credit(
            db_session, user_id=user_a.id, amount=Decimal("15.000000")
        )
        await _insert_transaction(
            db_session,
            user_a.id,
            amount_usd=Decimal("15.000000"),
            transaction_type="purchase",
        )

        # Debit: -3.50
        await CreditRepository.atomic_debit(
            db_session, user_id=user_a.id, amount=Decimal("3.500000")
        )
        await _insert_transaction(
            db_session,
            user_a.id,
            amount_usd=Decimal("-3.500000"),
            transaction_type="usage_debit",
        )

        # Debit: -1.25
        await CreditRepository.atomic_debit(
            db_session, user_id=user_a.id, amount=Decimal("1.250000")
        )
        await _insert_transaction(
            db_session,
            user_a.id,
            amount_usd=Decimal("-1.250000"),
            transaction_type="usage_debit",
        )

        # Verify invariant
        balance = await CreditRepository.get_balance(db_session, user_a.id)

        result = await db_session.execute(
            text(
                "SELECT SUM(amount_usd) FROM credit_transactions WHERE user_id = :uid"
            ),
            {"uid": user_a.id},
        )
        txn_sum = result.scalar_one()

        assert balance == txn_sum
        assert balance == Decimal("10.250000")


# =============================================================================
# TestAmountGuards
# =============================================================================


class TestAmountGuards:
    """Tests for positive-amount validation on atomic operations."""

    async def test_atomic_debit_rejects_zero(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """atomic_debit raises ValueError for zero amount."""
        with pytest.raises(ValueError, match="atomic_debit amount must be positive"):
            await CreditRepository.atomic_debit(
                db_session, user_id=user_a.id, amount=Decimal("0")
            )

    async def test_atomic_debit_rejects_negative(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """atomic_debit raises ValueError for negative amount."""
        with pytest.raises(ValueError, match="atomic_debit amount must be positive"):
            await CreditRepository.atomic_debit(
                db_session, user_id=user_a.id, amount=Decimal("-5.000000")
            )

    async def test_atomic_credit_rejects_zero(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """atomic_credit raises ValueError for zero amount."""
        with pytest.raises(ValueError, match="atomic_credit amount must be positive"):
            await CreditRepository.atomic_credit(
                db_session, user_id=user_a.id, amount=Decimal("0")
            )

    async def test_atomic_credit_rejects_negative(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """atomic_credit raises ValueError for negative amount."""
        with pytest.raises(ValueError, match="atomic_credit amount must be positive"):
            await CreditRepository.atomic_credit(
                db_session, user_id=user_a.id, amount=Decimal("-10.000000")
            )
