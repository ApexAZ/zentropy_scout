"""Repository for StripePurchase operations.

REQ-029 §7.2, §7.3, §8.3: Provides CRUD, lifecycle transitions
(mark_completed, mark_refunded), and paginated queries for the
stripe_purchases table.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stripe import StripePurchase


class StripePurchaseRepository:
    """Stateless repository for StripePurchase operations.

    All methods are static — no instance state. Pass an AsyncSession
    for every call so the caller controls transaction boundaries.
    """

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        pack_id: uuid.UUID,
        stripe_session_id: str,
        stripe_customer_id: str,
        amount_cents: int,
        grant_cents: int,
    ) -> StripePurchase:
        """Create a pending StripePurchase record.

        REQ-029 §6.2: Called when a checkout session is created.

        Args:
            db: Async database session.
            user_id: Purchasing user.
            pack_id: FundingPack being purchased.
            stripe_session_id: Stripe Checkout Session ID (cs_xxx).
            stripe_customer_id: Stripe Customer ID (cus_xxx).
            amount_cents: Price snapshot in cents.
            grant_cents: Grant snapshot in cents.

        Returns:
            Created StripePurchase with status='pending'.
        """
        purchase = StripePurchase(
            user_id=user_id,
            pack_id=pack_id,
            stripe_session_id=stripe_session_id,
            stripe_customer_id=stripe_customer_id,
            amount_cents=amount_cents,
            grant_cents=grant_cents,
        )
        db.add(purchase)
        await db.flush()
        await db.refresh(purchase)
        return purchase

    @staticmethod
    async def find_by_session_id(
        db: AsyncSession, session_id: str
    ) -> StripePurchase | None:
        """Find a purchase by its Stripe session ID.

        Args:
            db: Async database session.
            session_id: Stripe Checkout Session ID (cs_xxx).

        Returns:
            StripePurchase if found, None otherwise.
        """
        stmt = select(StripePurchase).where(
            StripePurchase.stripe_session_id == session_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def find_by_payment_intent(
        db: AsyncSession, payment_intent_id: str
    ) -> StripePurchase | None:
        """Find a purchase by its Stripe payment intent ID.

        REQ-029 §7.3: Used by the charge.refunded handler to locate the
        original purchase.

        Args:
            db: Async database session.
            payment_intent_id: Stripe Payment Intent ID (pi_xxx).

        Returns:
            StripePurchase if found, None otherwise.
        """
        stmt = select(StripePurchase).where(
            StripePurchase.stripe_payment_intent == payment_intent_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def mark_completed(
        db: AsyncSession,
        *,
        stripe_session_id: str,
        stripe_payment_intent: str,
    ) -> bool:
        """Mark a pending purchase as completed after successful payment.

        REQ-029 §7.2: Called by the checkout.session.completed webhook
        handler. Only transitions purchases in 'pending' status — already
        completed or refunded purchases are silently skipped (defense
        against webhook replay).

        Args:
            db: Async database session.
            stripe_session_id: Stripe Checkout Session ID to match.
            stripe_payment_intent: Payment Intent ID from webhook payload.

        Returns:
            True if a purchase was updated, False if not found or not pending.
        """
        stmt = select(StripePurchase).where(
            StripePurchase.stripe_session_id == stripe_session_id,
            StripePurchase.status == "pending",
        )
        result = await db.execute(stmt)
        purchase = result.scalar_one_or_none()
        if purchase is None:
            return False
        purchase.status = "completed"
        purchase.stripe_payment_intent = stripe_payment_intent
        purchase.completed_at = datetime.now(UTC)
        await db.flush()
        return True

    @staticmethod
    async def mark_refunded(
        db: AsyncSession,
        *,
        purchase_id: uuid.UUID,
        refund_amount_cents: int,
        is_full_refund: bool,
    ) -> bool:
        """Update a completed purchase with refund information.

        REQ-029 §7.3: Called by the charge.refunded webhook handler.
        Only transitions purchases in 'completed' or 'partial_refund'
        status — pending or already fully refunded purchases are silently
        skipped (defense against out-of-order webhook delivery).

        Args:
            db: Async database session.
            purchase_id: Purchase to update.
            refund_amount_cents: Cumulative refund amount in cents.
            is_full_refund: True if the charge is fully refunded.

        Returns:
            True if a purchase was updated, False if not found or invalid state.
        """
        stmt = select(StripePurchase).where(
            StripePurchase.id == purchase_id,
            StripePurchase.status.in_(["completed", "partial_refund"]),
        )
        result = await db.execute(stmt)
        purchase = result.scalar_one_or_none()
        if purchase is None:
            return False
        purchase.refund_amount_cents = refund_amount_cents
        purchase.refunded_at = datetime.now(UTC)
        purchase.status = "refunded" if is_full_refund else "partial_refund"
        await db.flush()
        return True

    @staticmethod
    async def mark_expired(
        db: AsyncSession,
        *,
        stripe_session_id: str,
    ) -> bool:
        """Transition a pending purchase to expired status.

        REQ-030 §7.3 (F-07): Called by the checkout.session.expired
        webhook handler. Only transitions purchases in 'pending' status —
        completed or refunded purchases are silently skipped.

        Args:
            db: Async database session.
            stripe_session_id: Stripe Checkout Session ID to match.

        Returns:
            True if a purchase was updated, False if not found or not pending.
        """
        stmt = select(StripePurchase).where(
            StripePurchase.stripe_session_id == stripe_session_id,
            StripePurchase.status == "pending",
        )
        result = await db.execute(stmt)
        purchase = result.scalar_one_or_none()
        if purchase is None:
            return False
        purchase.status = "expired"
        await db.flush()
        return True

    @staticmethod
    async def get_user_purchases(
        db: AsyncSession,
        user_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[StripePurchase], int]:
        """List purchases for a user with pagination.

        REQ-029 §8.3: Supports paginated purchase history queries.

        Args:
            db: Async database session.
            user_id: User to query purchases for.
            offset: Number of records to skip.
            limit: Maximum records to return.

        Returns:
            Tuple of (purchases list, total count).
        """
        limit = min(limit, 100)
        conditions = [StripePurchase.user_id == user_id]

        count_stmt = select(func.count()).select_from(StripePurchase).where(*conditions)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        data_stmt = (
            select(StripePurchase)
            .where(*conditions)
            .order_by(StripePurchase.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(data_stmt)
        purchases = list(result.scalars().all())

        return purchases, total
