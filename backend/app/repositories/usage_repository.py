"""Repository for LLM usage record operations.

REQ-020 §4, §8: Provides database access for the llm_usage_records table.
Supports CRUD, paginated listing, and aggregation for the usage API.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import LLMUsageRecord

# =============================================================================
# Return types
# =============================================================================


class _TaskBreakdown(TypedDict):
    task_type: str
    call_count: int
    input_tokens: int
    output_tokens: int
    billed_cost_usd: Decimal


class _ProviderBreakdown(TypedDict):
    provider: str
    call_count: int
    billed_cost_usd: Decimal


class UsageSummary(TypedDict):
    """Typed return value for UsageRepository.get_summary()."""

    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    total_raw_cost_usd: Decimal
    total_billed_cost_usd: Decimal
    by_task_type: list[_TaskBreakdown]
    by_provider: list[_ProviderBreakdown]


# =============================================================================
# Label constants (shared between SQL .label() and dict keys)
# =============================================================================

_LABEL_CALL_COUNT = "call_count"
_LABEL_BILLED_COST = "billed_cost_usd"


class UsageRepository:
    """Stateless repository for LLMUsageRecord table operations.

    All methods are static — no instance state. Pass an AsyncSession
    for every call so the caller controls transaction boundaries.
    """

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        provider: str,
        model: str,
        task_type: str,
        input_tokens: int,
        output_tokens: int,
        raw_cost_usd: Decimal,
        billed_cost_usd: Decimal,
        margin_multiplier: Decimal,
    ) -> LLMUsageRecord:
        """Create a new usage record.

        Args:
            db: Async database session.
            user_id: User who made the API call.
            provider: Provider name (claude, openai, gemini).
            model: Exact model identifier.
            task_type: Task type (extraction, cover_letter, etc.).
            input_tokens: Input/prompt tokens consumed.
            output_tokens: Output/completion tokens consumed.
            raw_cost_usd: Raw provider cost before margin.
            billed_cost_usd: User-facing cost after margin.
            margin_multiplier: Margin at time of call.

        Returns:
            Created LLMUsageRecord with database-generated fields.
        """
        record = LLMUsageRecord(
            user_id=user_id,
            provider=provider,
            model=model,
            task_type=task_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw_cost_usd=raw_cost_usd,
            billed_cost_usd=billed_cost_usd,
            margin_multiplier=margin_multiplier,
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)
        return record

    @staticmethod
    async def list_by_user(
        db: AsyncSession,
        user_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 50,
        task_type: str | None = None,
        provider: str | None = None,
    ) -> tuple[list[LLMUsageRecord], int]:
        """List usage records for a user with pagination and filters.

        Args:
            db: Async database session.
            user_id: User to query records for.
            offset: Number of records to skip.
            limit: Maximum records to return.
            task_type: Optional filter by task type.
            provider: Optional filter by provider.

        Returns:
            Tuple of (records list, total count).
        """
        conditions = [LLMUsageRecord.user_id == user_id]
        if task_type is not None:
            conditions.append(LLMUsageRecord.task_type == task_type)
        if provider is not None:
            conditions.append(LLMUsageRecord.provider == provider)

        count_stmt = select(func.count()).select_from(LLMUsageRecord).where(*conditions)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        data_stmt = (
            select(LLMUsageRecord)
            .where(*conditions)
            .order_by(LLMUsageRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(data_stmt)
        records = list(result.scalars().all())

        return records, total

    @staticmethod
    async def get_summary(
        db: AsyncSession,
        user_id: uuid.UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> UsageSummary:
        """Aggregate usage for a time period.

        REQ-020 §8.2: Returns totals and breakdowns by task_type and provider.
        Period range is [period_start, period_end) — start inclusive, end exclusive.

        Args:
            db: Async database session.
            user_id: User to aggregate for.
            period_start: Start of period (inclusive).
            period_end: End of period (exclusive).

        Returns:
            Dict with total_calls, total_input_tokens, total_output_tokens,
            total_raw_cost_usd, total_billed_cost_usd, by_task_type, by_provider.
        """
        period_conditions = [
            LLMUsageRecord.user_id == user_id,
            LLMUsageRecord.created_at >= period_start,
            LLMUsageRecord.created_at < period_end,
        ]

        # 1. Aggregate totals
        totals_stmt = select(
            func.count().label("total_calls"),
            func.coalesce(func.sum(LLMUsageRecord.input_tokens), 0).label(
                "total_input_tokens"
            ),
            func.coalesce(func.sum(LLMUsageRecord.output_tokens), 0).label(
                "total_output_tokens"
            ),
            func.coalesce(func.sum(LLMUsageRecord.raw_cost_usd), 0).label(
                "total_raw_cost_usd"
            ),
            func.coalesce(func.sum(LLMUsageRecord.billed_cost_usd), 0).label(
                "total_billed_cost_usd"
            ),
        ).where(*period_conditions)

        totals_result = await db.execute(totals_stmt)
        totals_row = totals_result.one()

        # 2. By task_type
        task_stmt = (
            select(
                LLMUsageRecord.task_type,
                func.count().label(_LABEL_CALL_COUNT),
                func.sum(LLMUsageRecord.input_tokens).label("input_tokens"),
                func.sum(LLMUsageRecord.output_tokens).label("output_tokens"),
                func.sum(LLMUsageRecord.billed_cost_usd).label(_LABEL_BILLED_COST),
            )
            .where(*period_conditions)
            .group_by(LLMUsageRecord.task_type)
        )
        task_result = await db.execute(task_stmt)
        by_task_type: list[_TaskBreakdown] = [
            _TaskBreakdown(
                task_type=row.task_type,
                call_count=row.call_count,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                billed_cost_usd=row.billed_cost_usd,
            )
            for row in task_result.all()
        ]

        # 3. By provider
        provider_stmt = (
            select(
                LLMUsageRecord.provider,
                func.count().label(_LABEL_CALL_COUNT),
                func.sum(LLMUsageRecord.billed_cost_usd).label(_LABEL_BILLED_COST),
            )
            .where(*period_conditions)
            .group_by(LLMUsageRecord.provider)
        )
        provider_result = await db.execute(provider_stmt)
        by_provider: list[_ProviderBreakdown] = [
            _ProviderBreakdown(
                provider=row.provider,
                call_count=row.call_count,
                billed_cost_usd=row.billed_cost_usd,
            )
            for row in provider_result.all()
        ]

        return {
            "total_calls": totals_row.total_calls,
            "total_input_tokens": totals_row.total_input_tokens,
            "total_output_tokens": totals_row.total_output_tokens,
            "total_raw_cost_usd": totals_row.total_raw_cost_usd,
            "total_billed_cost_usd": totals_row.total_billed_cost_usd,
            "by_task_type": by_task_type,
            "by_provider": by_provider,
        }
