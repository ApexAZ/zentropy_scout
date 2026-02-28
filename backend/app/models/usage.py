"""Token metering ORM models — append-only, no TimestampMixin.

REQ-020 §4.2–§4.3: LLMUsageRecord tracks every LLM/embedding API call.
CreditTransaction is an append-only ledger of all balance changes.
Both tables are immutable — records are never updated or deleted.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_DEFAULT_UUID = text("gen_random_uuid()")


class LLMUsageRecord(Base):
    """Records every individual LLM and embedding API call.

    Attributes:
        id: UUID primary key.
        user_id: FK to users table.
        provider: Provider name (claude, openai, gemini).
        model: Exact model identifier used.
        task_type: TaskType enum value (extraction, cover_letter, etc.).
        input_tokens: Input/prompt tokens consumed.
        output_tokens: Output/completion tokens consumed.
        raw_cost_usd: Raw provider cost before margin.
        billed_cost_usd: User-facing cost after margin.
        margin_multiplier: Margin at time of call (immutable snapshot).
        created_at: When the call was made.
    """

    __tablename__ = "llm_usage_records"
    __table_args__ = (
        CheckConstraint("input_tokens >= 0", name="ck_usage_input_tokens_nonneg"),
        CheckConstraint("output_tokens >= 0", name="ck_usage_output_tokens_nonneg"),
        CheckConstraint("raw_cost_usd >= 0", name="ck_usage_raw_cost_nonneg"),
        CheckConstraint("billed_cost_usd >= 0", name="ck_usage_billed_cost_nonneg"),
        CheckConstraint("margin_multiplier > 0", name="ck_usage_margin_positive"),
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
    )
    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    raw_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
    )
    billed_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
    )
    margin_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class CreditTransaction(Base):
    """Append-only ledger of all balance changes.

    Positive amounts = credits (purchases, grants, refunds).
    Negative amounts = debits (usage charges).

    Attributes:
        id: UUID primary key.
        user_id: FK to users table.
        amount_usd: Signed amount (+credit, -debit).
        transaction_type: One of purchase, usage_debit, admin_grant, refund.
        reference_id: Links to source (usage record ID, Stripe session, etc.).
        description: Human-readable description.
        created_at: Transaction timestamp.
    """

    __tablename__ = "credit_transactions"
    __table_args__ = (
        CheckConstraint(
            "transaction_type IN ('purchase', 'usage_debit', 'admin_grant', 'refund')",
            name="ck_credit_txn_type_valid",
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
    )
    amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
    )
    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    reference_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
