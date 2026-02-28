"""Tests for CreditRepository — CRUD + balance read.

REQ-020 §4, §8: Verifies create, list with pagination/filters,
and balance reads. Atomic debit/credit and reconciliation tests
are in test_credit_repository_balance.py.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

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
    amount_usd=Decimal("10.000000"),
    transaction_type="purchase",
    reference_id=None,
    description=None,
    created_at=None,
) -> CreditTransaction:
    """Insert a credit transaction via ORM for test setup."""
    kwargs: dict[str, object] = {
        "user_id": user_id,
        "amount_usd": amount_usd,
        "transaction_type": transaction_type,
        "reference_id": reference_id,
        "description": description,
    }
    if created_at is not None:
        kwargs["created_at"] = created_at
    txn = CreditTransaction(**kwargs)
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
# TestCreate
# =============================================================================


class TestCreate:
    """Tests for CreditRepository.create()."""

    async def test_creates_purchase_transaction(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Creates a positive (purchase) transaction."""
        txn = await CreditRepository.create(
            db_session,
            user_id=user_a.id,
            amount_usd=Decimal("15.000000"),
            transaction_type="purchase",
            reference_id="cs_test_123",
            description="Standard Credit Pack",
        )
        assert txn.id is not None
        assert txn.user_id == user_a.id
        assert txn.amount_usd == Decimal("15.000000")
        assert txn.transaction_type == "purchase"
        assert txn.reference_id == "cs_test_123"
        assert txn.description == "Standard Credit Pack"

    async def test_creates_debit_transaction(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Creates a negative (usage_debit) transaction."""
        txn = await CreditRepository.create(
            db_session,
            user_id=user_a.id,
            amount_usd=Decimal("-0.003640"),
            transaction_type="usage_debit",
            reference_id="usage-uuid-here",
            description="claude/claude-3-5-haiku-20241022 - extraction",
        )
        assert txn.amount_usd == Decimal("-0.003640")
        assert txn.transaction_type == "usage_debit"

    async def test_reference_id_nullable(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """reference_id and description are optional."""
        txn = await CreditRepository.create(
            db_session,
            user_id=user_a.id,
            amount_usd=Decimal("5.000000"),
            transaction_type="admin_grant",
        )
        assert txn.reference_id is None
        assert txn.description is None


# =============================================================================
# TestListByUser
# =============================================================================


class TestListByUser:
    """Tests for CreditRepository.list_by_user()."""

    async def test_returns_transactions_for_user(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Returns all transactions for the specified user."""
        await _insert_transaction(db_session, user_a.id)
        await _insert_transaction(
            db_session,
            user_a.id,
            amount_usd=Decimal("-0.003640"),
            transaction_type="usage_debit",
        )
        txns, total = await CreditRepository.list_by_user(db_session, user_a.id)
        assert len(txns) == 2
        assert total == 2

    async def test_pagination(self, db_session: AsyncSession, user_a: User) -> None:
        """Pagination returns correct subset and total count."""
        for _ in range(5):
            await _insert_transaction(db_session, user_a.id)
        txns, total = await CreditRepository.list_by_user(
            db_session, user_a.id, offset=0, limit=3
        )
        assert len(txns) == 3
        assert total == 5

    async def test_filter_by_transaction_type(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Filters by transaction_type."""
        await _insert_transaction(db_session, user_a.id, transaction_type="purchase")
        await _insert_transaction(
            db_session,
            user_a.id,
            transaction_type="usage_debit",
            amount_usd=Decimal("-0.010000"),
        )
        await _insert_transaction(db_session, user_a.id, transaction_type="purchase")
        txns, total = await CreditRepository.list_by_user(
            db_session, user_a.id, transaction_type="purchase"
        )
        assert len(txns) == 2
        assert total == 2

    async def test_ordered_by_created_at_desc(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Results ordered by created_at descending."""
        t_old = await _insert_transaction(
            db_session,
            user_a.id,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        t_new = await _insert_transaction(
            db_session,
            user_a.id,
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
        txns, _ = await CreditRepository.list_by_user(db_session, user_a.id)
        assert txns[0].id == t_new.id
        assert txns[1].id == t_old.id

    async def test_cross_user_isolation(
        self, db_session: AsyncSession, user_a: User, other_user: User
    ) -> None:
        """Transactions from other users are not returned."""
        await _insert_transaction(db_session, user_a.id)
        await _insert_transaction(db_session, other_user.id)
        txns, total = await CreditRepository.list_by_user(db_session, user_a.id)
        assert len(txns) == 1
        assert total == 1

    async def test_empty_result(self, db_session: AsyncSession, user_a: User) -> None:
        """No transactions returns empty list and zero count."""
        txns, total = await CreditRepository.list_by_user(db_session, user_a.id)
        assert txns == []
        assert total == 0


# =============================================================================
# TestGetBalance
# =============================================================================


class TestGetBalance:
    """Tests for CreditRepository.get_balance()."""

    async def test_default_balance_is_zero(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """New user starts with $0.00 balance."""
        balance = await CreditRepository.get_balance(db_session, user_a.id)
        assert balance == Decimal("0.000000")

    async def test_returns_current_balance(
        self, db_session: AsyncSession, user_a: User
    ) -> None:
        """Returns the user's current balance."""
        await _set_balance(db_session, user_a.id, Decimal("15.500000"))
        balance = await CreditRepository.get_balance(db_session, user_a.id)
        assert balance == Decimal("15.500000")
