"""Admin configuration service — read-side lookups.

REQ-022 §6.1–§6.3: Reads admin-managed configuration from database.
Provides pricing lookup (with effective dates), task routing (with fallback),
model registration checks, and system config accessors.

This is the READ-SIDE service used by MeteringService and MeteredLLMProvider
during normal operation. The WRITE-SIDE service (AdminManagementService) is
separate and used only by admin endpoints.
"""

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import (
    ModelRegistry,
    PricingConfig,
    SystemConfig,
    TaskRoutingConfig,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PricingResult:
    """Effective pricing for a model.

    Attributes:
        input_cost_per_1k: Raw provider cost per 1,000 input tokens (USD).
        output_cost_per_1k: Raw provider cost per 1,000 output tokens (USD).
        margin_multiplier: Per-model margin multiplier.
        effective_date: Date this pricing became active.
    """

    input_cost_per_1k: Decimal
    output_cost_per_1k: Decimal
    margin_multiplier: Decimal
    effective_date: date


class AdminConfigService:
    """Reads admin-managed configuration from database.

    REQ-022 §6.2: Provides pricing, routing, model registration, and
    system config lookups for the metering and LLM pipeline.

    Args:
        db: Async database session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_pricing(self, provider: str, model: str) -> PricingResult | None:
        """Get effective pricing for a model.

        REQ-022 §4.3: Returns the pricing_config row with the latest
        effective_date <= today for the given (provider, model).

        Args:
            provider: Provider identifier (claude, openai, gemini).
            model: Exact model identifier.

        Returns:
            PricingResult or None if no effective pricing exists.
        """
        stmt = (
            select(PricingConfig)
            .where(
                PricingConfig.provider == provider,
                PricingConfig.model == model,
                PricingConfig.effective_date <= date.today(),
            )
            .order_by(PricingConfig.effective_date.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        return PricingResult(
            input_cost_per_1k=row.input_cost_per_1k,
            output_cost_per_1k=row.output_cost_per_1k,
            margin_multiplier=row.margin_multiplier,
            effective_date=row.effective_date,
        )

    async def get_model_for_task(self, provider: str, task_type: str) -> str | None:
        """Get the routed model for a task type.

        REQ-022 §4.4: Lookup order:
        1. Exact match: (provider, task_type)
        2. Fallback: (provider, '_default')

        Args:
            provider: Provider identifier.
            task_type: TaskType enum value.

        Returns:
            Model identifier string, or None if no routing exists.
        """
        # Step 1: Try exact match
        stmt = select(TaskRoutingConfig.model).where(
            TaskRoutingConfig.provider == provider,
            TaskRoutingConfig.task_type == task_type,
        )
        result = await self._db.execute(stmt)
        model = result.scalar_one_or_none()
        if model is not None:
            return model

        # Step 2: Fallback to _default
        stmt = select(TaskRoutingConfig.model).where(
            TaskRoutingConfig.provider == provider,
            TaskRoutingConfig.task_type == "_default",
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def is_model_registered(self, provider: str, model: str) -> bool:
        """Check if model is in registry and active.

        REQ-022 §6.2: Used by MeteringService to block calls to
        unregistered or deactivated models.

        Args:
            provider: Provider identifier.
            model: Exact model identifier.

        Returns:
            True if model exists and is active, False otherwise.
        """
        stmt = select(ModelRegistry.id).where(
            ModelRegistry.provider == provider,
            ModelRegistry.model == model,
            ModelRegistry.is_active.is_(True),
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_system_config(
        self, key: str, default: str | None = None
    ) -> str | None:
        """Get a system config value by key.

        Args:
            key: Config key (e.g. 'signup_grant_credits').
            default: Value to return if key not found.

        Returns:
            Config value string, or default if key not found.
        """
        stmt = select(SystemConfig.value).where(SystemConfig.key == key)
        result = await self._db.execute(stmt)
        value = result.scalar_one_or_none()
        return value if value is not None else default

    async def get_system_config_int(self, key: str, default: int = 0) -> int:
        """Get a system config value as integer.

        Args:
            key: Config key.
            default: Value to return if key not found or not parseable.

        Returns:
            Parsed integer value, or default.
        """
        value = await self.get_system_config(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            logger.warning(
                "System config '%s' is not a valid integer, using default %d",
                key,
                default,
            )
            return default
