"""Admin configuration ORM models.

REQ-022 §4.1–§4.6: Models for the admin pricing dashboard and model registry.
Five tables: ModelRegistry, PricingConfig, TaskRoutingConfig, CreditPack,
SystemConfig. These replace hardcoded pricing dicts and routing tables with
admin-configurable database records.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

_DEFAULT_UUID = text("gen_random_uuid()")


class ModelRegistry(Base, TimestampMixin):
    """Canonical list of available LLM and embedding models.

    Calls to models not in this table (or inactive) are blocked.

    Attributes:
        id: UUID primary key.
        provider: Provider identifier (claude, openai, gemini).
        model: Exact model identifier (e.g. claude-3-5-haiku-20241022).
        display_name: Human-friendly name for admin UI.
        model_type: 'llm' for completion models, 'embedding' for embeddings.
        is_active: Soft-disable. Inactive models blocked like unregistered.
    """

    __tablename__ = "model_registry"
    __table_args__ = (
        UniqueConstraint("provider", "model", name="uq_model_registry_provider_model"),
        CheckConstraint(
            "model_type IN ('llm', 'embedding')",
            name="ck_model_registry_model_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    model_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="llm",
        server_default=text("'llm'"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )


class PricingConfig(Base, TimestampMixin):
    """Per-model pricing with individual margins and effective dates.

    Allows scheduling future pricing changes via effective_date.

    Attributes:
        id: UUID primary key.
        provider: Provider identifier.
        model: Model identifier (matches model_registry.model).
        input_cost_per_1k: Raw provider cost per 1,000 input tokens (USD).
        output_cost_per_1k: Raw provider cost per 1,000 output tokens (USD).
        margin_multiplier: Per-model margin (e.g. 1.30, 3.00).
        effective_date: Date this pricing becomes active.
    """

    __tablename__ = "pricing_config"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "model",
            "effective_date",
            name="uq_pricing_config_provider_model_date",
        ),
        CheckConstraint(
            "margin_multiplier > 0",
            name="ck_pricing_config_margin_positive",
        ),
        CheckConstraint(
            "input_cost_per_1k >= 0",
            name="ck_pricing_config_input_cost_nonneg",
        ),
        CheckConstraint(
            "output_cost_per_1k >= 0",
            name="ck_pricing_config_output_cost_nonneg",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    input_cost_per_1k: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
    )
    output_cost_per_1k: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
    )
    margin_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
    )
    effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )


class TaskRoutingConfig(Base, TimestampMixin):
    """Maps task types to models per provider.

    Replaces the hardcoded DEFAULT_*_ROUTING dicts in adapters.
    Fallback order: exact (provider, task_type) -> (provider, '_default').

    Attributes:
        id: UUID primary key.
        provider: Provider identifier.
        task_type: TaskType enum value or '_default' for fallback.
        model: Target model identifier.
    """

    __tablename__ = "task_routing_config"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "task_type",
            name="uq_task_routing_config_provider_task",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )


class CreditPack(Base, TimestampMixin):
    """Admin-configurable credit pack definitions.

    Consumed by Stripe integration (REQ-021) for checkout sessions.

    Attributes:
        id: UUID primary key.
        name: Pack display name (e.g. Starter, Standard, Pro).
        price_cents: USD price in cents (500 = $5.00).
        credit_amount: Abstract credits granted.
        stripe_price_id: Stripe Price ID. Nullable until REQ-021.
        display_order: Sort order in frontend purchase UI.
        is_active: Soft-disable without deleting.
        description: Short description for UI.
        highlight_label: Optional badge (e.g. Most Popular, Best Value).
    """

    __tablename__ = "credit_packs"
    __table_args__ = (
        CheckConstraint(
            "price_cents > 0",
            name="ck_credit_packs_price_positive",
        ),
        CheckConstraint(
            "credit_amount > 0",
            name="ck_credit_packs_amount_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=_DEFAULT_UUID,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    price_cents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    credit_amount: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    stripe_price_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    highlight_label: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )


class SystemConfig(Base, TimestampMixin):
    """Key-value store for global settings.

    Uses VARCHAR key as PK (not UUID). Application layer parses values
    to typed representations.

    Attributes:
        key: Setting key (PK). Convention: snake_case.
        value: Setting value as string.
        description: Human-readable description for admin UI.
    """

    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
