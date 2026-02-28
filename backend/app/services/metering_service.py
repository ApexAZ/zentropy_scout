"""Metering service — pricing and cost recording.

REQ-020 §5, §6.3: Calculates costs for LLM/embedding API calls using
a hardcoded pricing table with configurable margin, then records usage
and debits the user's balance atomically.
"""

import logging
import uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.usage import CreditTransaction, LLMUsageRecord

logger = logging.getLogger(__name__)

# =============================================================================
# Pricing Tables (REQ-020 §5.1–§5.2)
# =============================================================================

# (provider, model) → { input_per_1k, output_per_1k } in USD
_LLM_PRICING: dict[tuple[str, str], dict[str, Decimal]] = {
    # Claude (REQ-020 §5.1)
    ("claude", "claude-3-5-haiku-20241022"): {
        "input_per_1k": Decimal("0.0008"),
        "output_per_1k": Decimal("0.004"),
    },
    ("claude", "claude-3-5-sonnet-20241022"): {
        "input_per_1k": Decimal("0.003"),
        "output_per_1k": Decimal("0.015"),
    },
    # OpenAI (REQ-020 §5.1)
    ("openai", "gpt-4o-mini"): {
        "input_per_1k": Decimal("0.00015"),
        "output_per_1k": Decimal("0.0006"),
    },
    ("openai", "gpt-4o"): {
        "input_per_1k": Decimal("0.0025"),
        "output_per_1k": Decimal("0.01"),
    },
    # Gemini (REQ-020 §5.1)
    ("gemini", "gemini-2.0-flash"): {
        "input_per_1k": Decimal("0.0001"),
        "output_per_1k": Decimal("0.0004"),
    },
    ("gemini", "gemini-2.5-flash"): {
        "input_per_1k": Decimal("0.00015"),
        "output_per_1k": Decimal("0.0035"),
    },
    # Embeddings (REQ-020 §5.2) — output is always 0
    ("openai", "text-embedding-3-small"): {
        "input_per_1k": Decimal("0.00002"),
        "output_per_1k": Decimal("0"),
    },
    ("openai", "text-embedding-3-large"): {
        "input_per_1k": Decimal("0.00013"),
        "output_per_1k": Decimal("0"),
    },
}

# Fallback pricing per provider: highest-tier model pricing.
# Used when an unknown model is encountered for a known provider.
_FALLBACK_PRICING: dict[str, dict[str, Decimal]] = {
    "claude": {
        "input_per_1k": Decimal("0.003"),
        "output_per_1k": Decimal("0.015"),
    },
    "openai": {
        "input_per_1k": Decimal("0.0025"),
        "output_per_1k": Decimal("0.01"),
    },
    "gemini": {
        "input_per_1k": Decimal("0.00015"),
        "output_per_1k": Decimal("0.0035"),
    },
}

_THOUSAND = Decimal(1000)


# =============================================================================
# Service
# =============================================================================


class MeteringService:
    """Records LLM/embedding usage and debits user balances.

    REQ-020 §5, §6.3: Pricing, cost calculation, and recording pipeline.

    Args:
        db: Async database session for recording usage.
        margin_multiplier: Override for margin (default: from settings).
    """

    def __init__(
        self,
        db: AsyncSession,
        margin_multiplier: Decimal | None = None,
    ) -> None:
        self._db = db
        self._margin = margin_multiplier or Decimal(
            str(settings.metering_margin_multiplier)
        )

    def calculate_cost(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> tuple[Decimal, Decimal]:
        """Calculate raw and billed cost for an API call.

        REQ-020 §5.4: cost = (tokens/1K * price/1K) * margin.

        Args:
            provider: Provider name (claude, openai, gemini).
            model: Exact model identifier.
            input_tokens: Input/prompt tokens consumed.
            output_tokens: Output/completion tokens consumed.

        Returns:
            Tuple of (raw_cost_usd, billed_cost_usd).
        """
        pricing = _LLM_PRICING.get((provider, model))
        if pricing is None:
            pricing = _FALLBACK_PRICING.get(provider)
            if pricing is not None:
                logger.warning(
                    "Unknown model '%s' for provider '%s', using fallback pricing",
                    model,
                    provider,
                )
            else:
                logger.warning(
                    "No pricing available for provider '%s' model '%s'",
                    provider,
                    model,
                )
                return Decimal("0"), Decimal("0")

        raw_cost = (
            Decimal(input_tokens) * pricing["input_per_1k"]
            + Decimal(output_tokens) * pricing["output_per_1k"]
        ) / _THOUSAND
        billed_cost = raw_cost * self._margin
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

        REQ-020 §6.3: Full pipeline — calculate cost, insert records,
        debit balance. Never raises; errors are logged.

        Args:
            user_id: User who made the API call.
            provider: Provider name (claude, openai, gemini).
            model: Exact model identifier.
            task_type: Task type (extraction, cover_letter, etc.).
            input_tokens: Input tokens consumed.
            output_tokens: Output tokens consumed.
        """
        try:
            raw_cost, billed_cost = self.calculate_cost(
                provider, model, input_tokens, output_tokens
            )

            # Step 4: Insert usage record
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
                margin_multiplier=self._margin,
            )
            self._db.add(usage_record)

            # Step 5: Insert debit transaction
            credit_txn = CreditTransaction(
                id=uuid.uuid4(),
                user_id=user_id,
                amount_usd=-billed_cost,
                transaction_type="usage_debit",
                reference_id=str(usage_id),
                description=f"{provider}/{model} - {task_type}",
            )
            self._db.add(credit_txn)

            # Step 6: Atomic debit
            result = await self._db.execute(
                text(
                    "UPDATE users SET balance_usd = balance_usd - :amount "
                    "WHERE id = :user_id AND balance_usd >= :amount"
                ),
                {"amount": billed_cost, "user_id": user_id},
            )

            # Step 7: Log insufficient balance (REQ-020 §6.3)
            rows_updated: int = result.rowcount  # type: ignore[attr-defined]  # CursorResult from UPDATE
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
