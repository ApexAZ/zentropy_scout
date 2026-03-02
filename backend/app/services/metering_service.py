"""Metering service — DB-backed pricing and cost recording.

REQ-022 §7: Calculates costs for LLM/embedding API calls using
admin-configured pricing from the pricing_config table, with per-model
margin multipliers. Records usage and debits the user's balance atomically.
"""

import logging
import uuid
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NoPricingConfigError, UnregisteredModelError
from app.models.usage import CreditTransaction, LLMUsageRecord
from app.services.admin_config_service import AdminConfigService

logger = logging.getLogger(__name__)

_THOUSAND = Decimal(1000)


class MeteringService:
    """Records LLM/embedding usage and debits user balances.

    REQ-022 §7: Pricing and margins come from the pricing_config table
    via AdminConfigService, enabling per-model margin configuration.

    Args:
        db: Async database session for recording usage.
        admin_config: Service for reading pricing from the database.
    """

    def __init__(
        self,
        db: AsyncSession,
        admin_config: AdminConfigService,
    ) -> None:
        self._db = db
        self._admin_config = admin_config

    async def _get_pricing(
        self, provider: str, model: str
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Get (input_per_1k, output_per_1k, margin) from DB.

        REQ-022 §7.3: Checks model registry first, then pricing config.

        Args:
            provider: Provider name (claude, openai, gemini).
            model: Exact model identifier.

        Returns:
            Tuple of (input_cost_per_1k, output_cost_per_1k, margin_multiplier).

        Raises:
            UnregisteredModelError: If model not in registry or inactive.
            NoPricingConfigError: If no effective pricing exists.
        """
        if not await self._admin_config.is_model_registered(provider, model):
            raise UnregisteredModelError(provider=provider, model=model)

        pricing = await self._admin_config.get_pricing(provider, model)
        if pricing is None:
            raise NoPricingConfigError(provider=provider, model=model)

        return (
            pricing.input_cost_per_1k,
            pricing.output_cost_per_1k,
            pricing.margin_multiplier,
        )

    async def calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> tuple[Decimal, Decimal]:
        """Calculate raw and billed cost for an API call.

        REQ-022 §7.4: cost = (tokens/1K * price/1K) * per-model margin.

        Args:
            provider: Provider name (claude, openai, gemini).
            model: Exact model identifier.
            input_tokens: Input/prompt tokens consumed.
            output_tokens: Output/completion tokens consumed.

        Returns:
            Tuple of (raw_cost_usd, billed_cost_usd).

        Raises:
            UnregisteredModelError: If model not in registry.
            NoPricingConfigError: If no pricing exists for model.
        """
        input_per_1k, output_per_1k, margin = await self._get_pricing(provider, model)

        raw_cost = (
            Decimal(input_tokens) * input_per_1k
            + Decimal(output_tokens) * output_per_1k
        ) / _THOUSAND
        billed_cost = raw_cost * margin
        return raw_cost, billed_cost

    async def record_and_debit(
        self,
        user_id: uuid.UUID,
        provider: str,
        model: str,
        task_type: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record API usage and debit user balance.

        REQ-022 §7.4: Full pipeline — calculate cost with per-model margin,
        insert records, debit balance. Never raises; errors are logged.

        Args:
            user_id: User who made the API call.
            provider: Provider name (claude, openai, gemini).
            model: Exact model identifier.
            task_type: Task type (extraction, cover_letter, etc.).
            input_tokens: Input tokens consumed.
            output_tokens: Output tokens consumed.
        """
        try:
            input_per_1k, output_per_1k, margin = await self._get_pricing(
                provider, model
            )
            raw_cost = (
                Decimal(input_tokens) * input_per_1k
                + Decimal(output_tokens) * output_per_1k
            ) / _THOUSAND
            billed_cost = raw_cost * margin

            # Insert usage record
            usage_id = uuid.uuid4()
            usage_record = LLMUsageRecord(
                id=usage_id,
                user_id=user_id,
                provider=provider,
                model=model,
                task_type=task_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                raw_cost_usd=raw_cost,
                billed_cost_usd=billed_cost,
                margin_multiplier=margin,
            )
            self._db.add(usage_record)

            # Insert debit transaction
            credit_txn = CreditTransaction(
                id=uuid.uuid4(),
                user_id=user_id,
                amount_usd=-billed_cost,
                transaction_type="usage_debit",
                reference_id=str(usage_id),
                description=f"{provider}/{model} - {task_type}",
            )
            self._db.add(credit_txn)

            # Atomic debit
            result = cast(
                CursorResult[Any],
                await self._db.execute(
                    text(
                        "UPDATE users SET balance_usd = balance_usd - :amount "
                        "WHERE id = :user_id AND balance_usd >= :amount"
                    ),
                    {"amount": billed_cost, "user_id": user_id},
                ),
            )

            # Log insufficient balance (REQ-020 §6.3)
            rows_updated: int = result.rowcount
            if rows_updated == 0:
                logger.warning(
                    "Insufficient balance for user %s (debit: $%s)",
                    user_id,
                    billed_cost,
                )

            await self._db.flush()

        except Exception:
            # Fire-and-forget: the user already received the LLM response.
            # Don't interrupt their flow — log for operator investigation.
            logger.exception(
                "Failed to record usage for user %s",
                user_id,
            )
