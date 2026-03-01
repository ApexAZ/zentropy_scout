"""Repository for credit transaction operations.

REQ-020 §4, §8: Provides database access for the credit_transactions table
and atomic balance operations on the users table.
"""

import uuid
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import func, select, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import CreditTransaction
from app.models.user import User


class CreditRepository:
    """Stateless repository for CreditTransaction and balance operations.

    All methods are static — no instance state. Pass an AsyncSession
    for every call so the caller controls transaction boundaries.
    """

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        amount_usd: Decimal,
        transaction_type: str,
        reference_id: str | None = None,
        description: str | None = None,
    ) -> CreditTransaction:
        """Create a new credit transaction.

        Args:
            db: Async database session.
            user_id: Account owner.
            amount_usd: Signed amount (+credit, -debit).
            transaction_type: One of purchase, usage_debit, admin_grant, refund.
            reference_id: Links to source (usage record ID, Stripe session, etc.).
            description: Human-readable description.

        Returns:
            Created CreditTransaction with database-generated fields.
        """
        txn = CreditTransaction(
            user_id=user_id,
            amount_usd=amount_usd,
            transaction_type=transaction_type,
            reference_id=reference_id,
            description=description,
        )
        db.add(txn)
        await db.flush()
        await db.refresh(txn)
        return txn

    @staticmethod
    async def list_by_user(
        db: AsyncSession,
        user_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 50,
        transaction_type: str | None = None,
    ) -> tuple[list[CreditTransaction], int]:
        """List credit transactions for a user with pagination.

        Args:
            db: Async database session.
            user_id: User to query transactions for.
            offset: Number of records to skip.
            limit: Maximum records to return.
            transaction_type: Optional filter (purchase, usage_debit, etc.).

        Returns:
            Tuple of (transactions list, total count).
        """
        conditions = [CreditTransaction.user_id == user_id]
        if transaction_type is not None:
            conditions.append(CreditTransaction.transaction_type == transaction_type)

        count_stmt = (
            select(func.count()).select_from(CreditTransaction).where(*conditions)
        )
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        data_stmt = (
            select(CreditTransaction)
            .where(*conditions)
            .order_by(CreditTransaction.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(data_stmt)
        txns = list(result.scalars().all())

        return txns, total

    @staticmethod
    async def get_balance(db: AsyncSession, user_id: uuid.UUID) -> Decimal:
        """Read the user's current balance.

        Args:
            db: Async database session.
            user_id: User to query balance for.

        Returns:
            Current balance in USD.
        """
        stmt = select(User.balance_usd).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def atomic_debit(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        amount: Decimal,
    ) -> bool:
        """Atomically debit a user's balance.

        REQ-020 §6.3: Uses WHERE balance >= amount to prevent overdraft.

        Args:
            db: Async database session.
            user_id: User to debit.
            amount: Amount to debit (positive value).

        Returns:
            True if debit succeeded, False if insufficient balance.

        Raises:
            ValueError: If amount is not positive.
        """
        if amount <= Decimal("0"):
            raise ValueError("atomic_debit amount must be positive")
        result = cast(
            CursorResult[Any],
            await db.execute(
                text(
                    "UPDATE users SET balance_usd = balance_usd - :amount "
                    "WHERE id = :user_id AND balance_usd >= :amount"
                ),
                {"amount": amount, "user_id": user_id},
            ),
        )
        rows_updated: int = result.rowcount
        return rows_updated > 0

    @staticmethod
    async def atomic_credit(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        amount: Decimal,
    ) -> Decimal:
        """Atomically credit a user's balance.

        Args:
            db: Async database session.
            user_id: User to credit.
            amount: Amount to add (positive value).

        Returns:
            New balance after crediting.

        Raises:
            ValueError: If amount is not positive.
        """
        if amount <= Decimal("0"):
            raise ValueError("atomic_credit amount must be positive")
        result = await db.execute(
            text(
                "UPDATE users SET balance_usd = balance_usd + :amount "
                "WHERE id = :user_id RETURNING balance_usd"
            ),
            {"amount": amount, "user_id": user_id},
        )
        new_balance: Decimal = result.scalar_one()
        return new_balance
