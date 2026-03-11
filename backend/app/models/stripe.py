"""Stripe purchase tracking model.

REQ-029 §4.3: StripePurchase tracks Stripe checkout sessions from creation
through completion to potential refund. Separate from the append-only
credit_transactions ledger to allow mutable status lifecycle tracking.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

_DEFAULT_UUID = text("gen_random_uuid()")


class StripePurchase(Base, TimestampMixin):
    """Tracks Stripe checkout session lifecycle.

    Records are created when a checkout session is initiated (status='pending')
    and updated when webhooks confirm payment or refund. Snapshot fields
    (amount_cents, grant_cents) capture values at session creation time.

    Attributes:
        id: UUID primary key.
        user_id: FK to users table.
        pack_id: FK to funding_packs table.
        stripe_session_id: Stripe Checkout Session ID (cs_xxx). Unique.
        stripe_customer_id: Stripe Customer ID (cus_xxx).
        stripe_payment_intent: Payment Intent ID (pi_xxx). Set by webhook.
        amount_cents: Price in cents at time of purchase (snapshot).
        grant_cents: Grant amount in cents at time of purchase (snapshot).
        currency: ISO 4217 currency code. Default 'usd'.
        status: Lifecycle state: pending | completed | refunded | partial_refund.
        completed_at: Timestamp when webhook confirmed payment.
        refunded_at: Timestamp when refund webhook received.
        refund_amount_cents: Cumulative refund amount in cents.
        created_at: Record creation timestamp (from TimestampMixin).
        updated_at: Last modification timestamp (from TimestampMixin).
    """

    __tablename__ = "stripe_purchases"
    __table_args__ = (
        CheckConstraint(
            "amount_cents > 0",
            name="ck_stripe_purchases_amount_positive",
        ),
        CheckConstraint(
            "grant_cents > 0",
            name="ck_stripe_purchases_grant_positive",
        ),
        CheckConstraint(
            "refund_amount_cents >= 0",
            name="ck_stripe_purchases_refund_nonneg",
        ),
        CheckConstraint(
            "status IN ('pending', 'completed', 'refunded', 'partial_refund')",
            name="ck_stripe_purchases_status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pack_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("funding_packs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    stripe_session_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    stripe_customer_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    stripe_payment_intent: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    grant_cents: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default=text("'usd'"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    refund_amount_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
