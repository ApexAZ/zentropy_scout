"""Usage reservation model for pre-debit metering.

REQ-030 §4.2: UsageReservation tracks estimated cost holds placed before
LLM API calls. Reservations are created as 'held', then settled (success),
released (LLM failure), or marked stale (TTL exceeded).

REQ-030 §5.8: Response metadata columns (response_model, response_input_tokens,
response_output_tokens, call_completed_at) support the outbox pattern for
settlement retry — persisted after a successful LLM call, before settle().
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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


class UsageReservation(Base):
    """Pre-debit cost reservation for LLM API calls.

    Created before an LLM call with worst-case estimated cost.
    Settled after the call with actual cost, or released on failure.

    Attributes:
        id: UUID primary key.
        user_id: FK to users table.
        estimated_cost_usd: Worst-case cost from input + output ceilings x prices x margin.
        actual_cost_usd: Real cost set at settlement. NULL until settled.
        status: held | settled | released | stale.
        task_type: TaskType enum value (extraction, cover_letter, etc.).
        provider: Provider name, set at settlement.
        model: Model identifier, set at settlement.
        max_tokens: Upper bound used for cost estimation.
        created_at: When the reservation was created.
        settled_at: When settlement or release occurred.
        response_model: Exact model from LLM response (outbox pattern, §5.8).
        response_input_tokens: Actual input tokens from LLM response.
        response_output_tokens: Actual output tokens from LLM response.
        call_completed_at: When the LLM/embedding call succeeded.
    """

    __tablename__ = "usage_reservations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('held', 'settled', 'released', 'stale')",
            name="ck_reservation_status_valid",
        ),
        CheckConstraint(
            "estimated_cost_usd > 0",
            name="ck_reservation_estimated_positive",
        ),
        CheckConstraint(
            "actual_cost_usd IS NULL OR actual_cost_usd >= 0",
            name="ck_reservation_actual_nonneg",
        ),
        CheckConstraint(
            "response_input_tokens IS NULL OR response_input_tokens >= 0",
            name="ck_reservation_resp_input_tokens_nonneg",
        ),
        CheckConstraint(
            "response_output_tokens IS NULL OR response_output_tokens >= 0",
            name="ck_reservation_resp_output_tokens_nonneg",
        ),
        CheckConstraint(
            "(call_completed_at IS NULL AND response_model IS NULL "
            "AND response_input_tokens IS NULL AND response_output_tokens IS NULL) "
            "OR (call_completed_at IS NOT NULL AND response_model IS NOT NULL "
            "AND response_input_tokens IS NOT NULL AND response_output_tokens IS NOT NULL)",
            name="ck_reservation_response_metadata_complete",
        ),
        Index(
            "ix_reservation_user_status",
            "user_id",
            "status",
        ),
        Index(
            "ix_reservation_stale_sweep",
            "created_at",
            postgresql_where=text("status = 'held'"),
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
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
    )
    actual_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'held'"),
    )
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    provider: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    max_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # REQ-030 §5.8: Response metadata for settlement retry (outbox pattern).
    # Populated after successful LLM/embedding call, before settle().
    response_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    response_input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    response_output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    call_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
